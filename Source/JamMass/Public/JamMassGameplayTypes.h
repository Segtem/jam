#pragma once

#include "CoreMinimal.h"
#include "MassEntitySpawnDataGeneratorBase.h"
#include "MassEntityTraitBase.h"
#include "MassLODCollectorProcessor.h"
#include "MassSpawner.h"
#include "MassRepresentationProcessor.h"
#include "MassStationaryVisualizationTrait.h"
#include "MassVisualizationLODProcessor.h"

#include "JamMassGameplayTypes.generated.h"

class UStaticMesh;

/** Dominio de los procesadores LOD de Jam; evita competir con Crowd u otros dominios. */
USTRUCT()
struct JAMMASS_API FJamMassAmbientTag : public FMassTag
{
	GENERATED_BODY()
};

/** Habilita el cálculo de distancia a viewers para entidades ambientales de Jam. */
UCLASS(meta = (DisplayName = "Jam Ambient LOD Collection"))
class JAMMASS_API UJamMassLODCollectorProcessor final : public UMassLODCollectorProcessor
{
	GENERATED_BODY()

public:
	UJamMassLODCollectorProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
};

/** Convierte la distancia recolectada en High/Medium/Low/Off para Jam. */
UCLASS(meta = (DisplayName = "Jam Ambient Visualization LOD"))
class JAMMASS_API UJamMassVisualizationLODProcessor final : public UMassVisualizationLODProcessor
{
	GENERATED_BODY()

public:
	UJamMassVisualizationLODProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
};

/** Materializa la representación elegida por LOD para el dominio ambiental de Jam. */
UCLASS(meta = (DisplayName = "Jam Ambient Visualization"))
class JAMMASS_API UJamMassVisualizationProcessor final : public UMassVisualizationProcessor
{
	GENERATED_BODY()

public:
	UJamMassVisualizationProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
};

/** Trait espacial mínimo: permite que los frames de Jam inicialicen FTransformFragment. */
UCLASS(EditInlineNew, meta = (DisplayName = "Jam Transform"))
class JAMMASS_API UJamMassTransformTrait final : public UMassEntityTraitBase
{
	GENERATED_BODY()

protected:
	virtual void BuildTemplate(
		FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const override;
};

/** Representación ambiental mínima: ISM estacionario en High/Medium/Low y nula en Off. */
UCLASS(EditInlineNew, meta = (DisplayName = "Jam Ambient ISM"))
class JAMMASS_API UJamMassAmbientISMTrait final : public UMassStationaryVisualizationTrait
{
	GENERATED_BODY()

public:
	UJamMassAmbientISMTrait(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());

	bool Configure(UStaticMesh& Mesh, float MediumDistance, float LowDistance, float OffDistance);
	bool ConfigureBudget(
		UStaticMesh& Mesh,
		float MediumDistance,
		float LowDistance,
		float OffDistance,
		int32 HighMaxCount,
		int32 MediumMaxCount,
		int32 LowMaxCount);

protected:
	virtual void BuildTemplate(
		FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const override;
};

/** Generador determinista que entrega al MassSpawner los transforms ya calculados por Jam. */
UCLASS(Transient)
class JAMMASS_API UJamMassFramesGenerator final : public UMassEntitySpawnDataGeneratorBase
{
	GENERATED_BODY()

public:
	void SetFrames(const TArray<FTransform>& InFrames) { Frames = InFrames; }

	virtual void Generate(
		UObject& QueryOwner,
		TConstArrayView<FMassSpawnedEntityType> EntityTypes,
		int32 Count,
		FFinishedGeneratingSpawnDataSignature& FinishedDelegate) const override;

private:
	TArray<FTransform> Frames;
};

/** AMassSpawner pequeño y configurable desde el puente reflejado de Jam. */
UCLASS(Transient, NotPlaceable)
class JAMMASS_API AJamMassSpawner final : public AMassSpawner
{
	GENERATED_BODY()

public:
	bool Configure(UMassEntityConfigAsset& Config, const TArray<FTransform>& Frames);
	void AppendSpawnedEntities(TArray<FMassEntityHandle>& OutEntities) const;
};
