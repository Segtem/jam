#include "JamMassGameplayTypes.h"

#include "Mass/EntityFragments.h"
#include "MassActorSubsystem.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplateRegistry.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "MassLODFragments.h"
#include "MassSpawnLocationProcessor.h"

UJamMassLODCollectorProcessor::UJamMassLODCollectorProcessor()
{
	bAutoRegisterWithProcessingPhases = true;
}

void UJamMassLODCollectorProcessor::ConfigureQueries(
	const TSharedRef<FMassEntityManager>& EntityManager)
{
	Super::ConfigureQueries(EntityManager);
	EntityQuery_VisibleRangeAndOnLOD.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	EntityQuery_VisibleRangeOnly.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	EntityQuery_OnLODOnly.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	EntityQuery_NotVisibleRangeAndOffLOD.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
}

UJamMassVisualizationLODProcessor::UJamMassVisualizationLODProcessor()
{
	bAutoRegisterWithProcessingPhases = true;
	ExecutionFlags = static_cast<int32>(
		EProcessorExecutionFlags::Client | EProcessorExecutionFlags::Standalone);
}

void UJamMassVisualizationLODProcessor::ConfigureQueries(
	const TSharedRef<FMassEntityManager>& EntityManager)
{
	Super::ConfigureQueries(EntityManager);
	CloseEntityQuery.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	CloseEntityAdjustDistanceQuery.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	FarEntityQuery.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	DebugEntityQuery.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
	FilterTag = FJamMassAmbientTag::StaticStruct();
}

UJamMassVisualizationProcessor::UJamMassVisualizationProcessor()
{
	bAutoRegisterWithProcessingPhases = true;
	ExecutionFlags = static_cast<int32>(
		EProcessorExecutionFlags::Client | EProcessorExecutionFlags::Standalone);
}

void UJamMassVisualizationProcessor::ConfigureQueries(
	const TSharedRef<FMassEntityManager>& EntityManager)
{
	Super::ConfigureQueries(EntityManager);
	EntityQuery.AddTagRequirement<FJamMassAmbientTag>(EMassFragmentPresence::All);
}

void UJamMassTransformTrait::BuildTemplate(
	FMassEntityTemplateBuildContext& BuildContext, const UWorld&) const
{
	BuildContext.AddFragment<FTransformFragment>();
}

UJamMassPatrolProcessor::UJamMassPatrolProcessor()
	: EntityQuery(*this)
{
	bAutoRegisterWithProcessingPhases = true;
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::AllNetModes);
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Movement;
}

void UJamMassPatrolProcessor::ConfigureQueries(
	const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FJamMassPatrolFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddConstSharedRequirement<FJamMassPatrolParameters>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FJamMassPatrolTag>(EMassFragmentPresence::All);
}

void UJamMassPatrolProcessor::Execute(
	FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	const float DeltaTime = FMath::Clamp(Context.GetDeltaTimeSeconds(), 0.0f, 0.1f);
	EntityQuery.ForEachEntityChunk(Context, [DeltaTime](FMassExecutionContext& ChunkContext)
	{
		const FJamMassPatrolParameters& Parameters =
			ChunkContext.GetConstSharedFragment<FJamMassPatrolParameters>();
		const TArrayView<FTransformFragment> Transforms =
			ChunkContext.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FJamMassPatrolFragment> Patrols =
			ChunkContext.GetMutableFragmentView<FJamMassPatrolFragment>();
		for (FMassExecutionContext::FEntityIterator It = ChunkContext.CreateEntityIterator(); It; ++It)
		{
			FTransform& Transform = Transforms[It].GetMutableTransform();
			FJamMassPatrolFragment& Patrol = Patrols[It];
			if (!Patrol.bInitialized)
			{
				Patrol.Origin = Transform.GetLocation();
				Patrol.Axis = Transform.GetRotation().GetForwardVector().GetSafeNormal();
				Patrol.Axis = Patrol.Axis.IsNearlyZero() ? FVector::ForwardVector : Patrol.Axis;
				Patrol.bInitialized = true;
			}
			Patrol.Distance += Patrol.Direction * Parameters.Speed * DeltaTime;
			while (Patrol.Distance > Parameters.Radius || Patrol.Distance < -Parameters.Radius)
			{
				if (Patrol.Distance > Parameters.Radius)
				{
					Patrol.Distance = 2.0f * Parameters.Radius - Patrol.Distance;
					Patrol.Direction = -1;
				}
				else
				{
					Patrol.Distance = -2.0f * Parameters.Radius - Patrol.Distance;
					Patrol.Direction = 1;
				}
				++Patrol.Reversals;
			}
			Transform.SetTranslation(Patrol.Origin + Patrol.Axis * Patrol.Distance);
		}
	});
}

UJamMassAmbientISMTrait::UJamMassAmbientISMTrait(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Params.LODRepresentation[EMassLOD::High] = EMassRepresentationType::StaticMeshInstance;
	Params.LODRepresentation[EMassLOD::Medium] = EMassRepresentationType::StaticMeshInstance;
	Params.LODRepresentation[EMassLOD::Low] = EMassRepresentationType::StaticMeshInstance;
	Params.LODRepresentation[EMassLOD::Off] = EMassRepresentationType::None;
	Params.bKeepLowResActors = false;
	HighResTemplateActor = nullptr;
	LowResTemplateActor = nullptr;
	LODParams.FilterTag = FJamMassAmbientTag::StaticStruct();
}

bool UJamMassAmbientISMTrait::Configure(
	UStaticMesh& Mesh, const float MediumDistance, const float LowDistance, const float OffDistance)
{
	if (!(0.0f < MediumDistance && MediumDistance < LowDistance && LowDistance < OffDistance))
	{
		return false;
	}
	LODParams.FilterTag = FJamMassAmbientTag::StaticStruct();

	StaticMeshInstanceDesc.Reset();
	FMassStaticMeshInstanceVisualizationMeshDesc& MeshDesc =
		StaticMeshInstanceDesc.Meshes.AddDefaulted_GetRef();
	MeshDesc.Mesh = &Mesh;
	MeshDesc.SetSignificanceRange(EMassLOD::High, EMassLOD::Off);
	MeshDesc.bCastShadows = false;

	LODParams.BaseLODDistance[EMassLOD::High] = 0.0f;
	LODParams.BaseLODDistance[EMassLOD::Medium] = MediumDistance;
	LODParams.BaseLODDistance[EMassLOD::Low] = LowDistance;
	LODParams.BaseLODDistance[EMassLOD::Off] = OffDistance;
	LODParams.VisibleLODDistance[EMassLOD::High] = 0.0f;
	LODParams.VisibleLODDistance[EMassLOD::Medium] = MediumDistance;
	LODParams.VisibleLODDistance[EMassLOD::Low] = LowDistance;
	LODParams.VisibleLODDistance[EMassLOD::Off] = OffDistance;
	for (int32 LOD = 0; LOD < EMassLOD::Max; ++LOD)
	{
		LODParams.LODMaxCount[LOD] = MAX_int32;
	}
	return true;
}

bool UJamMassAmbientISMTrait::ConfigureBudget(
	UStaticMesh& Mesh,
	const float MediumDistance,
	const float LowDistance,
	const float OffDistance,
	const int32 HighMaxCount,
	const int32 MediumMaxCount,
	const int32 LowMaxCount)
{
	if (HighMaxCount < 0 || MediumMaxCount < 0 || LowMaxCount < 0
		|| !Configure(Mesh, MediumDistance, LowDistance, OffDistance))
	{
		return false;
	}
	LODParams.LODMaxCount[EMassLOD::High] = HighMaxCount;
	LODParams.LODMaxCount[EMassLOD::Medium] = MediumMaxCount;
	LODParams.LODMaxCount[EMassLOD::Low] = LowMaxCount;
	LODParams.LODMaxCount[EMassLOD::Off] = MAX_int32;
	return true;
}

void UJamMassAmbientISMTrait::BuildTemplate(
	FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
	BuildContext.AddTag<FJamMassAmbientTag>();
	BuildContext.AddFragment<FMassViewerInfoFragment>();
	BuildContext.AddFragment<FMassActorFragment>();
	BuildContext.AddTag<FMassCollectLODViewerInfoTag>();
	Super::BuildTemplate(BuildContext, World);
}

UJamMassMovingISMTrait::UJamMassMovingISMTrait()
{
	Params.LODRepresentation[EMassLOD::High] = EMassRepresentationType::StaticMeshInstance;
	Params.LODRepresentation[EMassLOD::Medium] = EMassRepresentationType::StaticMeshInstance;
	Params.LODRepresentation[EMassLOD::Low] = EMassRepresentationType::StaticMeshInstance;
	Params.LODRepresentation[EMassLOD::Off] = EMassRepresentationType::None;
	Params.bKeepLowResActors = false;
	HighResTemplateActor = nullptr;
	LowResTemplateActor = nullptr;
	LODParams.FilterTag = FJamMassAmbientTag::StaticStruct();
}

bool UJamMassMovingISMTrait::Configure(
	UStaticMesh& Mesh, const float MediumDistance, const float LowDistance, const float OffDistance)
{
	if (!(0.0f < MediumDistance && MediumDistance < LowDistance && LowDistance < OffDistance))
	{
		return false;
	}
	StaticMeshInstanceDesc.Reset();
	FMassStaticMeshInstanceVisualizationMeshDesc& MeshDesc =
		StaticMeshInstanceDesc.Meshes.AddDefaulted_GetRef();
	MeshDesc.Mesh = &Mesh;
	MeshDesc.SetSignificanceRange(EMassLOD::High, EMassLOD::Off);
	MeshDesc.bCastShadows = false;
	LODParams.FilterTag = FJamMassAmbientTag::StaticStruct();
	LODParams.BaseLODDistance[EMassLOD::High] = 0.0f;
	LODParams.BaseLODDistance[EMassLOD::Medium] = MediumDistance;
	LODParams.BaseLODDistance[EMassLOD::Low] = LowDistance;
	LODParams.BaseLODDistance[EMassLOD::Off] = OffDistance;
	LODParams.VisibleLODDistance[EMassLOD::High] = 0.0f;
	LODParams.VisibleLODDistance[EMassLOD::Medium] = MediumDistance;
	LODParams.VisibleLODDistance[EMassLOD::Low] = LowDistance;
	LODParams.VisibleLODDistance[EMassLOD::Off] = OffDistance;
	for (int32 LOD = 0; LOD < EMassLOD::Max; ++LOD)
	{
		LODParams.LODMaxCount[LOD] = MAX_int32;
	}
	return true;
}

void UJamMassMovingISMTrait::BuildTemplate(
	FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
	BuildContext.AddTag<FJamMassAmbientTag>();
	BuildContext.AddFragment<FMassViewerInfoFragment>();
	BuildContext.AddFragment<FMassActorFragment>();
	BuildContext.AddTag<FMassCollectLODViewerInfoTag>();
	Super::BuildTemplate(BuildContext, World);
}

bool UJamMassPatrolTrait::Configure(const float Speed, const float Radius)
{
	if (!FMath::IsFinite(Speed) || !FMath::IsFinite(Radius) || Speed <= 0.0f || Radius <= 0.0f)
	{
		return false;
	}
	Parameters.Speed = Speed;
	Parameters.Radius = Radius;
	return true;
}

void UJamMassPatrolTrait::BuildTemplate(
	FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
	BuildContext.AddTag<FJamMassPatrolTag>();
	BuildContext.AddFragment<FJamMassPatrolFragment>();
	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(World);
	BuildContext.AddConstSharedFragment(EntityManager.GetOrCreateConstSharedFragment(Parameters));
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
