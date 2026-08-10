#include "JamMassGameplayTypes.h"

#include "Mass/EntityFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplateRegistry.h"
#include "MassSpawnLocationProcessor.h"

void UJamMassTransformTrait::BuildTemplate(
	FMassEntityTemplateBuildContext& BuildContext, const UWorld&) const
{
	BuildContext.AddFragment<FTransformFragment>();
}

void UJamMassFramesGenerator::Generate(
	UObject&,
	TConstArrayView<FMassSpawnedEntityType> EntityTypes,
	int32 Count,
	FFinishedGeneratingSpawnDataSignature& FinishedDelegate) const
{
	TArray<FMassEntitySpawnDataGeneratorResult> Results;
	if (Count <= 0 || Frames.IsEmpty())
	{
		FinishedDelegate.Execute(Results);
		return;
	}

	BuildResultsFromEntityTypes(Count, EntityTypes, Results);
	int32 FrameIndex = 0;
	for (FMassEntitySpawnDataGeneratorResult& Result : Results)
	{
		Result.SpawnDataProcessor = UMassSpawnLocationProcessor::StaticClass();
		Result.SpawnData.InitializeAs<FMassTransformsSpawnData>();
		FMassTransformsSpawnData& SpawnData =
			Result.SpawnData.GetMutable<FMassTransformsSpawnData>();
		SpawnData.bRandomize = false;
		SpawnData.Transforms.Reserve(Result.NumEntities);
		for (int32 Index = 0; Index < Result.NumEntities; ++Index)
		{
			SpawnData.Transforms.Add(Frames[FrameIndex % Frames.Num()]);
			++FrameIndex;
		}
	}
	FinishedDelegate.Execute(Results);
}

bool AJamMassSpawner::Configure(
	UMassEntityConfigAsset& Config, const TArray<FTransform>& Frames)
{
	if (Frames.IsEmpty())
	{
		return false;
	}

	Count = Frames.Num();
	bAutoSpawnOnBeginPlay = false;
	EntityTypes.Reset();
	FMassSpawnedEntityType& EntityType = EntityTypes.AddDefaulted_GetRef();
	EntityType.EntityConfig = &Config;
	EntityType.Proportion = 1.0f;
	// Evita que DoSpawning difiera el trabajo: la vertical necesita hechos al volver a Python.
	EntityType.GetEntityConfig();

	SpawnDataGenerators.Reset();
	FMassSpawnDataGenerator& Generator = SpawnDataGenerators.AddDefaulted_GetRef();
	UJamMassFramesGenerator* FramesGenerator = NewObject<UJamMassFramesGenerator>(this);
	FramesGenerator->SetFrames(Frames);
	Generator.GeneratorClass = UJamMassFramesGenerator::StaticClass();
	Generator.GeneratorInstance = FramesGenerator;
	Generator.Proportion = 1.0f;
	return true;
}

void AJamMassSpawner::AppendSpawnedEntities(TArray<FMassEntityHandle>& OutEntities) const
{
	for (const FSpawnedEntities& Spawned : AllSpawnedEntities)
	{
		OutEntities.Append(Spawned.Entities);
	}
}
