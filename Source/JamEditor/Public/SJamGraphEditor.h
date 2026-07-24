#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "JamEditorModule.h"   // FJamTool

class SBorder;
class SCanvas;
class SEditableTextBox;
class SHorizontalBox;
class SJamGraphNode;
class SMultiLineEditableTextBox;
class SVerticalBox;
class SWidget;

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
		/** Guarda el grafo (JSON) como preset compound. */
		SLATE_EVENT(FOnRunGraph, OnSaveGraph)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools);

	/** Endpoints (inicio,fin) de cada wire, en coords locales del canvas — los usa la capa de wires. */
	TArray<TPair<FVector2D, FVector2D>> GetWireEndpoints() const;

	// Iconografía del ribbon (pública para que la Dash Bar reuse el mismo look):
	/** Color de la categoría (cada tab su tono, como los tabs de Grasshopper). */
	static FLinearColor CategoryColor(const FString& Cat);
	/** Código corto del verbo para el badge del icono (curado; si no, derivado del verbo). */
	static FString VerbCode(const FString& Verb);
	/** Ficha con ICONO (badge de color + código) — se usa en el ribbon y como header de nodo. */
	static TSharedRef<SWidget> MakeBadge(const FLinearColor& Color, const FString& Code, float Size);

private:
	struct FGNode
	{
		FString Id;
		FString Verb;
		FVector2D Pos = FVector2D::ZeroVector;
		float Height = 34.0f;
		/** Pines de entrada en ORDEN de fila (incluye «asset» si el verbo lo tiene): el índice acá es
		 *  la fila donde se ancla el wire. */
		TArray<FString> PinNames;
		TSharedPtr<SJamGraphNode> Widget;
	};

	/** Una arista con PIN en ambas puntas (como Grasshopper): salida de un nodo → un pin de otro
	 *  («in» = stream, o el nombre de un parámetro). */
	struct FGEdge
	{
		FString From;
		FString FromPin;   // siempre «out» por ahora
		FString To;
		FString ToPin;     // «in» (stream) o el nombre de un parámetro
	};

	/** Agrega un nodo; devuelve su Id (para reconstruir grafos al cargar un diagrama). */
	FString AddNode(const FString& Verb, const FVector2D* At = nullptr);
	void DeleteNode(const FString& Id);

	// ---- menú principal estilo Grasshopper (File / Edit / View / Display / Solution) ----
	void FillFileMenu(class FMenuBuilder& MB);
	void FillEditMenu(class FMenuBuilder& MB);
	void FillViewMenu(class FMenuBuilder& MB);
	void FillDisplayMenu(class FMenuBuilder& MB);
	void FillSolutionMenu(class FMenuBuilder& MB);
	/** Vacía el grafo (nodos + wires). */
	void NewGraph();
	/** Reconstruye el grafo desde JSON (nodos con sus params/posición + aristas por pin). */
	void LoadGraphJson(const FString& Json);
	/** Diálogos de archivo (DesktopPlatform): guardar/abrir un diagrama .jamgraph (JSON). */
	void SaveDiagram(bool bForceDialog);
	void OpenDiagram();
	/** Galería: reemplaza el grafo por UNO DE CADA nodo en grilla (para sacarle un screenshot). */
	void InsertAllNodes();
	/** Reencuadra: pan/zoom a un estado legible. */
	void ResetView();
	/** Índice del parámetro `Pin` en el verbo del nodo `Id`, o -1 si es «in»/«out» (header). */
	int32 PinIndex(const FString& Id, const FString& Pin) const;

	/** Ribbon estilo Grasshopper: al elegir un tab (categoría) se rellenan sus fichas con icono. */
	void RebuildTabContent();
	void OnPinClicked(const FString& Id, const FString& Pin, bool bOutput);
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
	virtual FReply OnMouseWheel(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;

	/** Local (píxeles del canvas) → coords del MODELO, deshaciendo zoom y pan. */
	FVector2D LocalToModel(const FVector2D& Local) const { return Local / Zoom - PanOffset; }
	/** Aplica el zoom actual como render transform del canvas (ZUI). */
	void ApplyZoom();

	TArray<FJamTool> Tools;
	TArray<FString> Categories;        // tabs del ribbon, en orden de aparición
	FString ActiveTab;                 // categoría abierta ahora
	TSharedPtr<SHorizontalBox> TabContentBox;   // fichas de la categoría activa
	TArray<FGNode> Nodes;
	TArray<FGEdge> Edges;                      // aristas con pin (origen.out → destino.pin)
	FString PendingSource;                     // nodo de salida armado, esperando una entrada
	FString PendingSourcePin;                  // pin de salida armado (por ahora «out»)
	FString CurrentPath;                       // archivo del diagrama actual (para «Guardar» sin diálogo)
	int32 NextId = 1;

	FOnRunGraph OnRunGraph;
	FOnRunGraph OnSaveGraph;
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

	// Pan del canvas (botón derecho arrastrando sobre el fondo) + zoom con la rueda (ZUI).
	FVector2D PanOffset = FVector2D::ZeroVector;
	bool bPanning = false;
	float Zoom = 1.0f;

	static constexpr float NodeWidth = 184.0f;   // pines(14) + params(104) + centro(~52) + pines(14)
};
