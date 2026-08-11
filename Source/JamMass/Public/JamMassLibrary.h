#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "JamMassLibrary.generated.h"

/** Frontera reflejada y pequeña para que el adaptador Python no imite MassEntity. */
UCLASS()
class JAMMASS_API UJamMassLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Valida un UMassEntityConfigAsset y devuelve hechos de traits/template para construir MC. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString InspectConfig(UObject* WorldContextObject, const FString& ConfigPath);

	/** Agrega el trait espacial mínimo de Jam a un config asset. Sólo modifica assets en editor. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass")
	static FString PrepareTransformConfig(UObject* ConfigAsset);

	/** Agrega la representación ambiental ISM/None autocontenida y sus umbrales LOD. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass")
	static FString PrepareAmbientISMConfig(
		UObject* ConfigAsset,
		const FString& MeshPath,
		float MediumDistance,
		float LowDistance,
		float OffDistance);

	/** Variante con máximos por LOD para medir degradación por presupuesto. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass")
	static FString PrepareAmbientISMBudgetConfig(
		UObject* ConfigAsset,
		const FString& MeshPath,
		float MediumDistance,
		float LowDistance,
		float OffDistance,
		int32 HighMaxCount,
		int32 MediumMaxCount,
		int32 LowMaxCount);

	/** Agrega ISM dinámica y una patrulla lineal acotada alrededor de cada transform inicial. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass")
	static FString PrepareAmbientPatrolConfig(
		UObject* ConfigAsset,
		const FString& MeshPath,
		float MediumDistance,
		float LowDistance,
		float OffDistance,
		float Speed,
		float Radius,
		float Variation);

	/**
	 * Prueba atómica del núcleo MassEntity: crea una entidad por transform, lee sus fragments y las
	 * destruye antes de volver. Devuelve hechos JSON; el juicio vive en el cerebro puro de Jam.
	 */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString ProbeEntities(UObject* WorldContextObject, const TArray<FTransform>& Transforms);

	/** Crea una población administrada que sobrevive a la llamada y devuelve su identidad JSON. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString SpawnPopulation(UObject* WorldContextObject, const TArray<FTransform>& Transforms);

	/** Crea la población mediante AMassSpawner usando el template de un config asset MC. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString SpawnConfiguredPopulation(
		UObject* WorldContextObject,
		const TArray<FTransform>& Transforms,
		const FString& ConfigPath);

	/** Inspecciona una población sin modificarla. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString InspectPopulation(UObject* WorldContextObject, const FString& PopulationId);

	/** Destruye una población. Repetir Clear es una operación válida e idempotente. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString ClearPopulation(UObject* WorldContextObject, const FString& PopulationId);

	/** Frontera de ciclo de vida usada por OnWorldCleanup y ShutdownModule. */
	static void ClearAllPopulations(UWorld* World = nullptr);
};
