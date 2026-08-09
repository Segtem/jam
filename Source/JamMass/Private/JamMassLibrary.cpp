#include "JamMassLibrary.h"

#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
FString JsonError(const FString& Message, const int32 Requested)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetBoolField(TEXT("ok"), false);
	Root->SetStringField(TEXT("error"), Message);
	Root->SetNumberField(TEXT("requested"), Requested);
	FString Result;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result);
	FJsonSerializer::Serialize(Root, Writer);
	return Result;
}
}

FString UJamMassLibrary::ProbeEntities(
	UObject* WorldContextObject, const TArray<FTransform>& Transforms)
{
	constexpr int32 MaxEntities = 4096;
	if (Transforms.IsEmpty() || Transforms.Num() > MaxEntities)
	{
		return JsonError(
			FString::Printf(TEXT("se requieren entre 1 y %d transforms"), MaxEntities),
			Transforms.Num());
	}
	for (const FTransform& Transform : Transforms)
	{
		if (Transform.ContainsNaN())
		{
			return JsonError(TEXT("los transforms tienen que ser finitos"), Transforms.Num());
		}
	}

	UWorld* World = GEngine == nullptr
		? nullptr
		: GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull);
	if (World == nullptr)
	{
		return JsonError(TEXT("el contexto no pertenece a un UWorld"), Transforms.Num());
	}

	UMassEntitySubsystem* Subsystem = World->GetSubsystem<UMassEntitySubsystem>();
	if (Subsystem == nullptr)
	{
		return JsonError(TEXT("UMassEntitySubsystem no está disponible"), Transforms.Num());
	}

	FMassEntityManager& Manager = Subsystem->GetMutableEntityManager();
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

	FString Result;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result);
	FJsonSerializer::Serialize(Root, Writer);
	return Result;
}
