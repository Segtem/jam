#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "JamEditorModule.h"   // FJamTool

class SBorder;
class SCanvas;
class SEditableTextBox;
class SJamGraphNode;
class SMultiLineEditableTextBox;
class SVerticalBox;

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
		/** Nombre del asset activo (lo elegido en Content): precarga el nodo «asset». */
		SLATE_ATTRIBUTE(FString, ActiveAsset)
		/** Abre la ventana de Content (para elegir el asset sin salir del grafo). */
		SLATE_EVENT(FSimpleDelegate, OnOpenContent)
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

	void AddNode(const FString& Verb, const FVector2D* At = nullptr);
	void DeleteNode(const FString& Id);
	void OnPinClicked(const FString& Id, bool bOutput);
	void RunGraph();
	FString BuildJson() const;
	const FJamTool* FindTool(const FString& Verb) const;
	FGNode* FindNode(const FString& Id);

	/** Buscador de nodos al doble clic en el canvas vacío (como el search box de Grasshopper). */
	void OpenSearch(const FVector2D& AtLocal);
	void CloseSearch();
	void RebuildSearchResults(const FString& Query);
	/** Crea el primer resultado del buscador (Enter). */
	void CommitSearch();

	// Canvas: doble clic → buscador · arrastre con botón derecho/medio → pan.
	virtual FReply OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseButtonDoubleClick(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;

	TArray<FJamTool> Tools;
	TArray<FGNode> Nodes;
	TArray<TPair<FString, FString>> Edges;   // (origen, destino)
	FString PendingSource;                    // pin de salida armado, esperando una entrada
	int32 NextId = 1;

	FOnRunGraph OnRunGraph;
	FSimpleDelegate OnOpenContent;
	TAttribute<FString> ActiveAsset;
	TSharedPtr<SCanvas> Canvas;
	TSharedPtr<SMultiLineEditableTextBox> Output;

	// Buscador estilo Grasshopper (doble clic en el canvas).
	TSharedPtr<SBorder> SearchPopup;
	TSharedPtr<SEditableTextBox> SearchField;
	TSharedPtr<SVerticalBox> SearchResults;
	TArray<FString> SearchHits;
	FVector2D SearchAt = FVector2D::ZeroVector;
	bool bSearchOpen = false;

	// Pan del canvas (botón derecho arrastrando sobre el fondo).
	FVector2D PanOffset = FVector2D::ZeroVector;
	bool bPanning = false;

	static constexpr float NodeWidth = 168.0f;
	static constexpr float HeaderY = 14.0f;
};
