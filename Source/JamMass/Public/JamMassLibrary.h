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
	/**
	 * Prueba atómica del núcleo MassEntity: crea una entidad por transform, lee sus fragments y las
	 * destruye antes de volver. Devuelve hechos JSON; el juicio vive en el cerebro puro de Jam.
	 */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString ProbeEntities(UObject* WorldContextObject, const TArray<FTransform>& Transforms);

	/** Crea una población administrada que sobrevive a la llamada y devuelve su identidad JSON. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString SpawnPopulation(UObject* WorldContextObject, const TArray<FTransform>& Transforms);

	/** Inspecciona una población sin modificarla. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString InspectPopulation(UObject* WorldContextObject, const FString& PopulationId);

	/** Destruye una población. Repetir Clear es una operación válida e idempotente. */
	UFUNCTION(BlueprintCallable, Category = "Jam|Mass", meta = (WorldContext = "WorldContextObject"))
	static FString ClearPopulation(UObject* WorldContextObject, const FString& PopulationId);

	/** Frontera de ciclo de vida usada por OnWorldCleanup y ShutdownModule. */
	static void ClearAllPopulations(UWorld* World = nullptr);
};
