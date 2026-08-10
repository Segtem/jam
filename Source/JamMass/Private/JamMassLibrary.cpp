#include "JamMassLibrary.h"
#include "JamMassGameplayTypes.h"

#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplate.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/Guid.h"

namespace
{
constexpr int32 MaxEntities = 4096;

struct FJamPopulation
{
	TWeakObjectPtr<UWorld> World;
	TWeakObjectPtr<AJamMassSpawner> Spawner;
	TArray<FMassEntityHandle> Entities;
	TArray<FVector> ExpectedLocations;
	FString ConfigPath;
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

UMassEntityConfigAsset* ResolveConfig(const FString& ConfigPath)
{
	return Cast<UMassEntityConfigAsset>(FSoftObjectPath(ConfigPath).TryLoad());
}

int32 CountValid(const FJamPopulation& Population, const FMassEntityManager& Manager)
{
	int32 Valid = 0;
	for (const FMassEntityHandle Entity : Population.Entities)
	{
		Valid += Manager.IsEntityValid(Entity) ? 1 : 0;
	}
	return Valid;
}

void DestroyPopulation(FJamPopulation& Population, FMassEntityManager* Manager)
{
	if (AJamMassSpawner* Spawner = Population.Spawner.Get())
	{
		Spawner->DoDespawning();
		Spawner->Destroy();
		return;
	}
	if (Manager != nullptr)
	{
		TArray<FMassEntityHandle> ValidEntities;
		for (const FMassEntityHandle Entity : Population.Entities)
		{
			if (Manager->IsEntityValid(Entity))
			{
				ValidEntities.Add(Entity);
			}
		}
		Manager->BatchDestroyEntities(ValidEntities);
	}
}
}

FString UJamMassLibrary::InspectConfig(UObject* WorldContextObject, const FString& ConfigPath)
{
	UWorld* World = ResolveWorld(WorldContextObject);
	UMassEntityConfigAsset* Config = ResolveConfig(ConfigPath);
	if (World == nullptr)
	{
		return JsonError(TEXT("el contexto no pertenece a un UWorld"), 0);
	}
	if (Config == nullptr)
	{
		return JsonError(TEXT("no se encontró el UMassEntityConfigAsset indicado"), 0);
	}

	const FMassEntityTemplate& EntityTemplate = Config->GetOrCreateEntityTemplate(*World);
	const bool bTemplateValid = EntityTemplate.IsValid();
	const bool bHasTransform = bTemplateValid
		&& EntityTemplate.GetTemplateData().HasFragment<FTransformFragment>();
	TArray<TSharedPtr<FJsonValue>> TraitNames;
	for (const UMassEntityTraitBase* Trait : Config->GetConfig().GetTraits())
	{
		TraitNames.Add(MakeShared<FJsonValueString>(GetNameSafe(Trait == nullptr
			? nullptr : Trait->GetClass())));
	}

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), bTemplateValid && bHasTransform);
	Root->SetStringField(TEXT("config_path"), Config->GetPathName());
	Root->SetNumberField(TEXT("trait_count"), TraitNames.Num());
	Root->SetArrayField(TEXT("traits"), TraitNames);
	Root->SetBoolField(TEXT("template_valid"), bTemplateValid);
	Root->SetBoolField(TEXT("has_transform"), bHasTransform);
	Root->SetStringField(TEXT("template_id"), bTemplateValid
		? EntityTemplate.GetTemplateID().ToString() : FString());
	if (!bTemplateValid || !bHasTransform)
	{
		Root->SetStringField(TEXT("error"),
			TEXT("la configuración no produce un template espacial válido"));
	}
	return SerializeJson(Root);
}

FString UJamMassLibrary::PrepareTransformConfig(UObject* ConfigAsset)
{
	UMassEntityConfigAsset* Config = Cast<UMassEntityConfigAsset>(ConfigAsset);
	if (Config == nullptr)
	{
		return JsonError(TEXT("el objeto no es un UMassEntityConfigAsset"), 0);
	}
#if WITH_EDITOR
	UMassEntityTraitBase* Trait = Config->AddTrait(UJamMassTransformTrait::StaticClass());
	Config->MarkPackageDirty();
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), Trait != nullptr);
	Root->SetStringField(TEXT("config_path"), Config->GetPathName());
	Root->SetStringField(TEXT("trait"), GetNameSafe(Trait == nullptr ? nullptr : Trait->GetClass()));
	return SerializeJson(Root);
#else
	return JsonError(TEXT("preparar un config asset sólo está disponible en editor"), 0);
#endif
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

FString UJamMassLibrary::SpawnConfiguredPopulation(
	UObject* WorldContextObject,
	const TArray<FTransform>& Transforms,
	const FString& ConfigPath)
{
	FString Error;
	if (!ValidateTransforms(Transforms, Error))
	{
		return JsonError(Error, Transforms.Num());
	}
	UWorld* World = ResolveWorld(WorldContextObject);
	FMassEntityManager* Manager = ResolveManager(World);
	UMassEntityConfigAsset* Config = ResolveConfig(ConfigPath);
	if (World == nullptr || Manager == nullptr)
	{
		return JsonError(TEXT("UMassEntitySubsystem no está disponible"), Transforms.Num());
	}
	if (Config == nullptr)
	{
		return JsonError(TEXT("no se encontró el UMassEntityConfigAsset indicado"), Transforms.Num());
	}
	const FMassEntityTemplate& EntityTemplate = Config->GetOrCreateEntityTemplate(*World);
	if (!EntityTemplate.IsValid()
		|| !EntityTemplate.GetTemplateData().HasFragment<FTransformFragment>())
	{
		return JsonError(TEXT("el config no produce un template con FTransformFragment"),
			Transforms.Num());
	}

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.ObjectFlags |= RF_Transient;
	SpawnParameters.Name = MakeUniqueObjectName(World, AJamMassSpawner::StaticClass(),
		TEXT("JamMassSpawner"));
	AJamMassSpawner* Spawner = World->SpawnActor<AJamMassSpawner>(SpawnParameters);
	if (Spawner == nullptr || !Spawner->Configure(*Config, Transforms))
	{
		return JsonError(TEXT("JamMassSpawner no pudo configurarse"), Transforms.Num());
	}
	Spawner->DoSpawning();

	FJamPopulation Population;
	Population.World = World;
	Population.Spawner = Spawner;
	Population.ConfigPath = Config->GetPathName();
	Spawner->AppendSpawnedEntities(Population.Entities);
	for (const FTransform& Transform : Transforms)
	{
		Population.ExpectedLocations.Add(Transform.GetLocation());
	}
	const int32 Valid = CountValid(Population, *Manager);
	if (Population.Entities.Num() != Transforms.Num() || Valid != Transforms.Num())
	{
		DestroyPopulation(Population, Manager);
		return JsonError(TEXT("JamMassSpawner no creó la población completa"), Transforms.Num());
	}

	const FString PopulationId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
	Populations.Add(PopulationId, MoveTemp(Population));
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), true);
	Root->SetStringField(TEXT("population_id"), PopulationId);
	Root->SetStringField(TEXT("world_id"), WorldId(World));
	Root->SetStringField(TEXT("config_path"), Config->GetPathName());
	Root->SetStringField(TEXT("spawner_class"), TEXT("JamMassSpawner"));
	Root->SetNumberField(TEXT("requested"), Transforms.Num());
	Root->SetNumberField(TEXT("created"), Transforms.Num());
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
	Root->SetStringField(TEXT("config_path"), Population->ConfigPath);
	Root->SetStringField(TEXT("spawner_class"), Population->Spawner.IsValid()
		? TEXT("JamMassSpawner") : TEXT(""));
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
	const int32 ValidBefore = CountValid(*Population, *Manager);
	DestroyPopulation(*Population, Manager);
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
	Root->SetNumberField(TEXT("valid_before"), ValidBefore);
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
		DestroyPopulation(Pair.Value, ResolveManager(PopulationWorld));
		ToRemove.Add(Pair.Key);
	}
	for (const FString& PopulationId : ToRemove)
	{
		Populations.Remove(PopulationId);
	}
}
