#pragma once

#include "CoreMinimal.h"
#include "MassEntitySpawnDataGeneratorBase.h"
#include "MassEntityTraitBase.h"
#include "MassSpawner.h"

#include "JamMassGameplayTypes.generated.h"

/** Trait espacial mínimo: permite que los frames de Jam inicialicen FTransformFragment. */
UCLASS(EditInlineNew, meta = (DisplayName = "Jam Transform"))
class JAMMASS_API UJamMassTransformTrait final : public UMassEntityTraitBase
{
	GENERATED_BODY()

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
