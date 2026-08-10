#include "JamMassLibrary.h"

#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/Guid.h"

namespace
{
constexpr int32 MaxEntities = 4096;

struct FJamPopulation
{
	TWeakObjectPtr<UWorld> World;
	TArray<FMassEntityHandle> Entities;
	TArray<FVector> ExpectedLocations;
};

TMap<FString, FJamPopulation> Populations;

FString WorldId(const UWorld* World)
{
	return World == nullptr
		? FString()
		: FString::Printf(TEXT("%s@%p"), *World->GetPathName(), World);
}

FString SerializeJson(const TSharedRef<FJsonObject>& Root)
{
	FString Result;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result);
	FJsonSerializer::Serialize(Root, Writer);
	return Result;
}

FString JsonError(const FString& Message, const int32 Requested)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), false);
	Root->SetStringField(TEXT("error"), Message);
	Root->SetNumberField(TEXT("requested"), Requested);
	return SerializeJson(Root);
}

UWorld* ResolveWorld(UObject* WorldContextObject)
{
	return GEngine == nullptr
		? nullptr
		: GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull);
}

bool ValidateTransforms(const TArray<FTransform>& Transforms, FString& Error)
{
	if (Transforms.IsEmpty() || Transforms.Num() > MaxEntities)
	{
		Error = FString::Printf(TEXT("se requieren entre 1 y %d transforms"), MaxEntities);
		return false;
	}
	for (const FTransform& Transform : Transforms)
	{
		if (Transform.ContainsNaN())
		{
			Error = TEXT("los transforms tienen que ser finitos");
			return false;
		}
	}
	return true;
}

FMassEntityManager* ResolveManager(UWorld* World)
{
	UMassEntitySubsystem* Subsystem = World == nullptr
		? nullptr
		: World->GetSubsystem<UMassEntitySubsystem>();
	return Subsystem == nullptr ? nullptr : &Subsystem->GetMutableEntityManager();
}
}

FString UJamMassLibrary::ProbeEntities(
	UObject* WorldContextObject, const TArray<FTransform>& Transforms)
{
	FString Error;
	if (!ValidateTransforms(Transforms, Error))
	{
		return JsonError(Error, Transforms.Num());
	}

	UWorld* World = ResolveWorld(WorldContextObject);
	if (World == nullptr)
	{
		return JsonError(TEXT("el contexto no pertenece a un UWorld"), Transforms.Num());
	}

	FMassEntityManager* ManagerPtr = ResolveManager(World);
	if (ManagerPtr == nullptr)
	{
		return JsonError(TEXT("UMassEntitySubsystem no está disponible"), Transforms.Num());
	}

	FMassEntityManager& Manager = *ManagerPtr;
	const TArray<const UScriptStruct*> FragmentTypes{FTransformFragment::StaticStruct()};
	const FMassArchetypeHandle Archetype = Manager.CreateArchetype(FragmentTypes);
	if (!Archetype.IsValid())
	{
		return JsonError(TEXT("MassEntity no creó el arquetipo"), Transforms.Num());
	}

	TArray<FMassEntityHandle> Entities;
	{
		// Los observadores reciben el lote completo cuando sale de scope el contexto de creación.
		const TSharedRef<FMassEntityManager::FEntityCreationContext> Creation =
			Manager.BatchCreateEntities(Archetype, Transforms.Num(), Entities);
		for (int32 Index = 0; Index < Entities.Num(); ++Index)
		{
			Manager.GetFragmentDataChecked<FTransformFragment>(Entities[Index])
				.SetTransform(Transforms[Index]);
		}
	}

	int32 ValidBefore = 0;
	int32 SameArchetype = 0;
	int32 TransformMismatches = 0;
	FVector InputSum = FVector::ZeroVector;
	FVector ObservedSum = FVector::ZeroVector;
	for (int32 Index = 0; Index < Entities.Num(); ++Index)
	{
		const FMassEntityHandle Entity = Entities[Index];
		InputSum += Transforms[Index].GetLocation();
		if (!Manager.IsEntityValid(Entity))
		{
			continue;
		}
		++ValidBefore;
		SameArchetype += Manager.GetArchetypeForEntity(Entity) == Archetype ? 1 : 0;
		const FVector Observed =
			Manager.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation();
		ObservedSum += Observed;
		TransformMismatches += Observed.Equals(Transforms[Index].GetLocation(), 0.001) ? 0 : 1;
	}

	Manager.BatchDestroyEntities(Entities);
	int32 ValidAfter = 0;
	for (const FMassEntityHandle Entity : Entities)
	{
		ValidAfter += Manager.IsEntityValid(Entity) ? 1 : 0;
	}

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), true);
	Root->SetNumberField(TEXT("requested"), Transforms.Num());
	Root->SetNumberField(TEXT("created"), Entities.Num());
	Root->SetNumberField(TEXT("valid_before"), ValidBefore);
	Root->SetNumberField(TEXT("valid_after"), ValidAfter);
	Root->SetNumberField(TEXT("same_archetype"), SameArchetype);
	Root->SetNumberField(TEXT("transform_mismatches"), TransformMismatches);
	Root->SetNumberField(TEXT("input_sum_x"), InputSum.X);
	Root->SetNumberField(TEXT("input_sum_y"), InputSum.Y);
	Root->SetNumberField(TEXT("input_sum_z"), InputSum.Z);
	Root->SetNumberField(TEXT("observed_sum_x"), ObservedSum.X);
	Root->SetNumberField(TEXT("observed_sum_y"), ObservedSum.Y);
	Root->SetNumberField(TEXT("observed_sum_z"), ObservedSum.Z);

	return SerializeJson(Root);
}

FString UJamMassLibrary::SpawnPopulation(
	UObject* WorldContextObject, const TArray<FTransform>& Transforms)
{
	FString Error;
	if (!ValidateTransforms(Transforms, Error))
	{
		return JsonError(Error, Transforms.Num());
	}
	UWorld* World = ResolveWorld(WorldContextObject);
	FMassEntityManager* Manager = ResolveManager(World);
	if (World == nullptr || Manager == nullptr)
	{
		return JsonError(TEXT("UMassEntitySubsystem no está disponible"), Transforms.Num());
	}

	const TArray<const UScriptStruct*> FragmentTypes{FTransformFragment::StaticStruct()};
	const FMassArchetypeHandle Archetype = Manager->CreateArchetype(FragmentTypes);
	if (!Archetype.IsValid())
	{
		return JsonError(TEXT("MassEntity no creó el arquetipo"), Transforms.Num());
	}

	FJamPopulation Population;
	Population.World = World;
	Population.ExpectedLocations.Reserve(Transforms.Num());
	{
		const TSharedRef<FMassEntityManager::FEntityCreationContext> Creation =
			Manager->BatchCreateEntities(Archetype, Transforms.Num(), Population.Entities);
		for (int32 Index = 0; Index < Population.Entities.Num(); ++Index)
		{
			Manager->GetFragmentDataChecked<FTransformFragment>(Population.Entities[Index])
				.SetTransform(Transforms[Index]);
			Population.ExpectedLocations.Add(Transforms[Index].GetLocation());
		}
	}

	int32 Valid = 0;
	for (const FMassEntityHandle Entity : Population.Entities)
	{
		Valid += Manager->IsEntityValid(Entity) ? 1 : 0;
	}
	const int32 Created = Population.Entities.Num();
	const FString PopulationId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
	Populations.Add(PopulationId, MoveTemp(Population));

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), true);
	Root->SetStringField(TEXT("population_id"), PopulationId);
	Root->SetStringField(TEXT("world_id"), WorldId(World));
	Root->SetNumberField(TEXT("requested"), Transforms.Num());
	Root->SetNumberField(TEXT("created"), Created);
	Root->SetNumberField(TEXT("valid"), Valid);
	return SerializeJson(Root);
}

FString UJamMassLibrary::InspectPopulation(
	UObject* WorldContextObject, const FString& PopulationId)
{
	UWorld* World = ResolveWorld(WorldContextObject);
	FJamPopulation* Population = Populations.Find(PopulationId);
	if (Population == nullptr)
	{
		return JsonError(TEXT("población Mass inexistente o ya liberada"), 0);
	}
	if (World == nullptr || Population->World.Get() != World)
	{
		return JsonError(TEXT("el MH pertenece a otro UWorld"), Population->Entities.Num());
	}
	FMassEntityManager* Manager = ResolveManager(World);
	if (Manager == nullptr)
	{
		return JsonError(TEXT("UMassEntitySubsystem no está disponible"), Population->Entities.Num());
	}

	int32 Valid = 0;
	int32 TransformMismatches = 0;
	FVector ObservedSum = FVector::ZeroVector;
	for (int32 Index = 0; Index < Population->Entities.Num(); ++Index)
	{
		const FMassEntityHandle Entity = Population->Entities[Index];
		if (!Manager->IsEntityValid(Entity))
		{
			continue;
		}
		++Valid;
		const FVector Observed = Manager->GetFragmentDataChecked<FTransformFragment>(Entity)
			.GetTransform().GetLocation();
		ObservedSum += Observed;
		TransformMismatches += Observed.Equals(Population->ExpectedLocations[Index], 0.001) ? 0 : 1;
	}

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), true);
	Root->SetStringField(TEXT("population_id"), PopulationId);
	Root->SetStringField(TEXT("world_id"), WorldId(World));
	Root->SetNumberField(TEXT("requested"), Population->Entities.Num());
	Root->SetNumberField(TEXT("valid"), Valid);
	Root->SetNumberField(TEXT("transform_mismatches"), TransformMismatches);
	Root->SetNumberField(TEXT("observed_sum_x"), ObservedSum.X);
	Root->SetNumberField(TEXT("observed_sum_y"), ObservedSum.Y);
	Root->SetNumberField(TEXT("observed_sum_z"), ObservedSum.Z);
	return SerializeJson(Root);
}

FString UJamMassLibrary::ClearPopulation(
	UObject* WorldContextObject, const FString& PopulationId)
{
	UWorld* World = ResolveWorld(WorldContextObject);
	FJamPopulation* Population = Populations.Find(PopulationId);
	if (Population == nullptr)
	{
		TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
		Root->SetBoolField(TEXT("ok"), true);
		Root->SetStringField(TEXT("population_id"), PopulationId);
		Root->SetStringField(TEXT("world_id"), WorldId(World));
		Root->SetNumberField(TEXT("valid_before"), 0);
		Root->SetNumberField(TEXT("valid_after"), 0);
		return SerializeJson(Root);
	}
	if (World == nullptr || Population->World.Get() != World)
	{
		return JsonError(TEXT("el MH pertenece a otro UWorld"), Population->Entities.Num());
	}
	FMassEntityManager* Manager = ResolveManager(World);
	if (Manager == nullptr)
	{
		return JsonError(TEXT("UMassEntitySubsystem no está disponible"), Population->Entities.Num());
	}
	TArray<FMassEntityHandle> ValidEntities;
	for (const FMassEntityHandle Entity : Population->Entities)
	{
		if (Manager->IsEntityValid(Entity))
		{
			ValidEntities.Add(Entity);
		}
	}
	Manager->BatchDestroyEntities(ValidEntities);
	int32 ValidAfter = 0;
	for (const FMassEntityHandle Entity : Population->Entities)
	{
		ValidAfter += Manager->IsEntityValid(Entity) ? 1 : 0;
	}
	const FString Id = WorldId(World);
	Populations.Remove(PopulationId);

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), true);
	Root->SetStringField(TEXT("population_id"), PopulationId);
	Root->SetStringField(TEXT("world_id"), Id);
	Root->SetNumberField(TEXT("valid_before"), ValidEntities.Num());
	Root->SetNumberField(TEXT("valid_after"), ValidAfter);
	return SerializeJson(Root);
}

void UJamMassLibrary::ClearAllPopulations(UWorld* World)
{
	TArray<FString> ToRemove;
	for (TPair<FString, FJamPopulation>& Pair : Populations)
	{
		UWorld* PopulationWorld = Pair.Value.World.Get();
		if (World != nullptr && PopulationWorld != World)
		{
			continue;
		}
		if (FMassEntityManager* Manager = ResolveManager(PopulationWorld))
		{
			TArray<FMassEntityHandle> ValidEntities;
			for (const FMassEntityHandle Entity : Pair.Value.Entities)
			{
				if (Manager->IsEntityValid(Entity))
				{
					ValidEntities.Add(Entity);
				}
			}
			Manager->BatchDestroyEntities(ValidEntities);
		}
		ToRemove.Add(Pair.Key);
	}
	for (const FString& PopulationId : ToRemove)
	{
		Populations.Remove(PopulationId);
	}
}
