#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "JamEditorModule.h"   // FJamTool

class SCanvas;
class SJamGraphNode;
class SMultiLineEditableTextBox;

/** Devuelve el reporte de correr un grafo (JSON JamGraph) — la implementa el módulo (llama a Python). */
DECLARE_DELEGATE_RetVal_OneParam(FString, FOnRunGraph, const FString& /*json*/);

/**
 * Canvas «Grasshopper» propio (Slate): paleta de verbos que agregan nodos, nodos arrastrables con
 * params, wires (spline) entre salida→entrada dibujados a mano, y «Run graph» que serializa a
 * JamGraph JSON y lo corre por el mismo sustrato (jam.graph → tools → oráculo).
 */
class SJamGraphEditor : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SJamGraphEditor) {}
		SLATE_EVENT(FOnRunGraph, OnRunGraph)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools);

	/** Endpoints (inicio,fin) de cada wire, en coords locales del canvas — los usa la capa de wires. */
	TArray<TPair<FVector2D, FVector2D>> GetWireEndpoints() const;

private:
	struct FGNode
	{
		FString Id;
		FString Verb;
		FVector2D Pos = FVector2D::ZeroVector;
		TSharedPtr<SJamGraphNode> Widget;
	};

	void AddNode(const FString& Verb);
	void DeleteNode(const FString& Id);
	void OnPinClicked(const FString& Id, bool bOutput);
	void RunGraph();
	FString BuildJson() const;
	const FJamTool* FindTool(const FString& Verb) const;
	FGNode* FindNode(const FString& Id);

	TArray<FJamTool> Tools;
	TArray<FGNode> Nodes;
	TArray<TPair<FString, FString>> Edges;   // (origen, destino)
	FString PendingSource;                    // pin de salida armado, esperando una entrada
	int32 NextId = 1;

	FOnRunGraph OnRunGraph;
	TSharedPtr<SCanvas> Canvas;
	TSharedPtr<SMultiLineEditableTextBox> Output;

	static constexpr float NodeWidth = 168.0f;
	static constexpr float HeaderY = 14.0f;
};
