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
/** Acción del ciclo Preview propia del Graph (Bake/Discard), sin argumentos. */
DECLARE_DELEGATE_RetVal(FString, FOnGraphPreviewAction);
/** Acomodar la selección: (JSON de rectángulos, acción) → JSON {ok, pos}. Las cuentas las hace
 *  `jam.layout`, que es puro y testeado; el editor sólo manda rectángulos y aplica posiciones. */
DECLARE_DELEGATE_RetVal_TwoParams(FString, FOnLayout, const FString& /*nodos*/, const FString& /*accion*/);
/** Inspector de datos: (node_id, filtro) → JSON {nodos, filas}. Node vacío = sólo la lista. */
DECLARE_DELEGATE_RetVal_FourParams(FString, FOnInspect, const FString& /*node*/,
	const FString& /*filtro*/, const FString& /*orden*/, bool /*descendente*/);

/** Una fila del inspector: sus celdas ya formateadas por Python, una por columna. */
struct FJamInspectRow
{
	TArray<FString> Cells;
};

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
		/** Compile/Preflight puro: mismo JSON de entrada/salida, sin ejecutar ni abrir Preview. */
		SLATE_EVENT(FOnRunGraph, OnCompileGraph)
		SLATE_EVENT(FOnGraphPreviewAction, OnBakePreview)
		SLATE_EVENT(FOnGraphPreviewAction, OnDiscardPreview)
		/** Nombre del asset activo (lo elegido en Content): precarga el nodo «asset». */
		SLATE_ATTRIBUTE(FString, ActiveAsset)
		/** Abre la ventana de Content (para elegir el asset sin salir del grafo). */
		SLATE_EVENT(FSimpleDelegate, OnOpenContent)
		/** Guarda el grafo (JSON) como preset compound. */
		SLATE_EVENT(FOnRunGraph, OnSaveGraph)
		/** Datos del último Run para el inspector. */
		SLATE_EVENT(FOnInspect, OnInspect)
		/** Alinear/distribuir: lo resuelve `jam.layout`. */
		SLATE_EVENT(FOnLayout, OnLayout)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools);

	/** Un wire a dibujar: puntas (inicio,fin) en coords locales del canvas + COLOR por tipo de dato
	 *  (como Blueprint/Substance: el color dice QUÉ fluye por el cable). */
	struct FJamWire
	{
		FVector2D A = FVector2D::ZeroVector;
		FVector2D B = FVector2D::ZeroVector;
		FLinearColor Color = FLinearColor::White;
	};
	/** Wires a dibujar (con color por tipo) — los usa la capa de wires. */
	TArray<FJamWire> GetWireEndpoints() const;
	/** Cable-fantasma mientras se conecta: del pin de salida armado al cursor. Devuelve false si no hay
	 *  conexión en curso. Es el «rubber band» de Houdini/GH/Blueprint que hace visible el gesto. */
	bool GetPendingWire(FVector2D& OutFrom, FVector2D& OutTo, FLinearColor& OutColor) const;

	// Iconografía del ribbon (pública para que la Dash Bar reuse el mismo look):
	/** Color de la categoría (cada tab su tono, como los tabs de Grasshopper). */
	static FLinearColor CategoryColor(const FString& Cat);
	/** Color compartido por cable y grip según el tipo de dato (P/N/T/B/A/S/M), estilo Blueprint. */
	static FLinearColor DataColor(const FString& OutName);
	/** NOMBRE legible del tipo, para etiquetar el pin. El color acompaña; el que identifica es esto. */
	static FString DataName(const FString& Type);
	/** Código corto del verbo para el badge del icono (curado; si no, derivado del verbo). */
	static FString VerbCode(const FString& Verb);
	/** Ruta absoluta del SVG asignado al verbo por Resources/Icons/Lucide/icon-map.json. */
	static FString IconPathForVerb(const FString& Verb);
	/** Ficha con icono SVG; si falta, cae al código corto para no dejar un hueco vacío. */
	static TSharedRef<SWidget> MakeBadge(const FLinearColor& Color, const FString& Code, float Size,
		const FString& IconPath = FString());

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

	// ---- el gesto de la paleta: clic = al centro de la vista · arrastre = donde soltás ----
	/** Crea el nodo en el centro de lo que se está VIENDO. Con el canvas paneado, ese punto y el
	    origen del grafo están en lugares distintos, y sólo uno es donde vas a buscar el nodo. */
	FString AddNodeAlCentro(const FString& Verb);
	virtual FReply OnDragOver(const FGeometry& MyGeometry, const FDragDropEvent& DragDropEvent) override;
	virtual FReply OnDrop(const FGeometry& MyGeometry, const FDragDropEvent& DragDropEvent) override;
	void DeleteNode(const FString& Id);

	// ---- selección: un ESTADO del editor, no el foco de teclado ----
	// Mientras la selección fue «el nodo con foco» no había forma de mover, borrar, copiar ni
	// alinear más de uno. Todo lo de abajo cuelga de este TSet.
	/** Clic en el cuerpo de un nodo. Shift agrega, Ctrl alterna; sin modificadores reemplaza —
	 *  salvo que el nodo YA esté elegido, para no romper un grupo justo antes de arrastrarlo. */
	void ClickNode(const FString& Id, bool bShift, bool bCtrl);
	void ClearSelection();
	void SelectAll();
	/** Borra todos los elegidos con sus cables, en UNA operación (un solo refresco de pines). */
	void DeleteSelection();
	/** Mueve la selección entera el mismo delta (en unidades de modelo). */
	void MoveSelection(const FVector2D& DeltaModelo);
	/** Alinear/distribuir por `jam.layout`: «izquierda…centro-y», «dist-x», «dist-y». */
	void AcomodarSeleccion(const FString& Accion);
	/** Rectángulo del marquee en coordenadas de MODELO; false si no hay uno en curso. */
	bool GetMarquee(FVector2D& OutA, FVector2D& OutB) const;

	// ---- menú principal estilo Grasshopper (File / Edit / View / Display / Solution) ----
	void FillFileMenu(class FMenuBuilder& MB);
	void FillEditMenu(class FMenuBuilder& MB);
	void FillViewMenu(class FMenuBuilder& MB);
	void FillDisplayMenu(class FMenuBuilder& MB);
	void FillSolutionMenu(class FMenuBuilder& MB);
	/** Vacía el grafo (nodos + wires). */
	void NewGraph();
	/** Valida y reconstruye el grafo desde JSON. Un fallo no modifica canvas, vista ni CurrentPath. */
	bool LoadGraphJson(const FString& Json);
	/** Diálogos de archivo (DesktopPlatform): guardar/abrir un diagrama .jamgraph (JSON). */
	void SaveDiagram(bool bForceDialog);
	void OpenDiagram();
	/** Carga uno de los tutoriales del tab «Aprender». El catálogo es `Resources/Examples/examples.json`:
	    cada ficha de ese tab llama acá con su archivo, así que sumar un tutorial no toca C++. */

	// ---- inspector de datos (el Geometry Spreadsheet de Jam) ----
	/** Relee del último Run: repuebla el selector de nodos y la tabla del nodo elegido. */
	void RefreshInspector();
	TSharedRef<class SWidget> BuildInspector();
	void LoadBundledExample(const FString& Filename, const FText& LoadedMessage);
	/** Galería: reemplaza el grafo por UNO DE CADA nodo en grilla (para sacarle un screenshot). */
	void InsertAllNodes();
	/** Reencuadra: pan/zoom a un estado legible. */
	void ResetView();
	/** Índice del parámetro `Pin` en el verbo del nodo `Id`, o -1 si es «in»/«out» (header). */
	int32 PinIndex(const FString& Id, const FString& Pin) const;
	/** Tipos efectivos de los extremos y validación central de un cable. */
	FString OutputDataTypeFor(const FString& NodeId, const FString& Pin) const;
	FString InputDataTypeFor(const FString& NodeId, const FString& Pin) const;
	bool CanConnect(const FString& From, const FString& FromPin, const FString& To,
		const FString& ToPin, FString& OutError) const;

	/** Ribbon estilo Grasshopper: al elegir un tab (categoría) se rellenan sus fichas con icono. */
	void RebuildTabContent();
	/** El tab «Aprender»: fichas que CARGAN un tutorial en vez de crear un nodo. */
	void RebuildLearnTab();
	void OnPinClicked(const FString& Id, const FString& Pin, bool bOutput);
	/** Recomputa, por cada nodo, qué pines de parámetro tienen cable entrando y se lo dice a su widget
	 *  (para que grisee esos inputs). Se llama tras cualquier cambio de aristas. */
	void RefreshCabledPins();
	void ValidateGraph();
	void RunGraph();
	void BakePreview();
	void DiscardPreview();
	/** Aplica el envelope {report,nodes} de Compile o Run al output y a los estados de los nodos. */
	void ApplyGraphResult(const FString& Result);
	FString BuildJson() const;
	const FJamTool* FindTool(const FString& Verb) const;
	FGNode* FindNode(const FString& Id);
	/** Color del cable que SALE de un nodo (según el tipo de su salida). */
	FLinearColor WireColorFor(const FString& NodeId) const;

	/** Buscador de nodos al doble clic en el canvas vacío (como el search box de Grasshopper). */
	/** Abre el buscador en coordenadas locales al overlay del canvas (mismo espacio que WireLayer). */
	void OpenSearch(const FVector2D& AtCanvas);
	void CloseSearch();
	void RebuildSearchResults(const FString& Query);
	/** Crea el primer resultado del buscador (Enter). */
	void CommitSearch();

	// Canvas: doble clic → buscador · arrastre con botón derecho/medio → pan.
	// Es focusable para que un clic en el fondo quite el foco/selección del nodo anterior.
	virtual bool SupportsKeyboardFocus() const override { return true; }
	/** Atajos del canvas: `Ctrl+A` todo, `Esc` nada, `Supr` la selección. Sólo corren si el foco NO
	 *  está en un campo de edición — ahí esas teclas son del campo. */
	virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
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

	/** Filas de fichas que apila cada subgrupo del ribbon. Grasshopper usa dos; el tab Mesh tiene 43
	    verbos y con dos seguía siendo una tira que obligaba a scrollear. Tres entra en la altura de
	    un nodo del canvas. El reparto por subgrupo lo decide `jam/ribbon.py`. */
	static constexpr int32 RibbonRows = 3;
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
	FOnRunGraph OnCompileGraph;
	FOnGraphPreviewAction OnBakePreview;
	FOnGraphPreviewAction OnDiscardPreview;
	FOnRunGraph OnSaveGraph;
	FOnInspect OnInspect;
	FOnLayout OnLayout;

	/** Nodos del último Run (id + tipo + cantidad) que alimentan el selector del inspector. */
	TArray<TSharedPtr<FString>> InspectNodes;
	/** Filas del nodo elegido, ya filtradas y ordenadas por Python. */
	TArray<TSharedPtr<FJamInspectRow>> InspectRows;
	/** Nombres de columna del tipo que se inspecciona (cambian según el nodo). */
	TArray<FString> InspectColumns;
	/** Columna por la que se ordena y sentido; vacío = orden natural del stream. */
	FString InspectSort;
	bool bInspectDescending = false;
	TSharedPtr<class SComboBox<TSharedPtr<FString>>> InspectPicker;
	TSharedPtr<class SListView<TSharedPtr<FJamInspectRow>>> InspectList;
	TSharedPtr<class SHeaderRow> InspectHeader;
	TSharedPtr<class SEditableTextBox> InspectFilter;
	TSharedPtr<class STextBlock> InspectStatus;
	/** Id del nodo elegido; vacío = ninguno todavía. */
	FString InspectNodeId;

	FSimpleDelegate OnOpenContent;
	TAttribute<FString> ActiveAsset;
	TSharedPtr<SCanvas> Canvas;
	TSharedPtr<SMultiLineEditableTextBox> Output;

	// Buscador estilo Grasshopper (doble clic en el canvas).
	TSharedPtr<SBorder> SearchPopup;
	TSharedPtr<SEditableTextBox> SearchField;
	TSharedPtr<SVerticalBox> SearchResults;
	TArray<FString> SearchHits;
	/** Punto del doble clic local al overlay del canvas; posiciona el popup y luego pasa por LocalToModel. */
	FVector2D SearchAt = FVector2D::ZeroVector;
	bool bSearchOpen = false;

	// Pan del canvas (botón derecho arrastrando sobre el fondo) + zoom con la rueda (ZUI).
	FVector2D PanOffset = FVector2D::ZeroVector;
	bool bPanning = false;
	float Zoom = 1.0f;

	/** Nodos elegidos. Es LA fuente de la selección: el halo, el arrastre en grupo, `Supr`, alinear
	 *  y (más adelante) copiar y colapsar a función leen todos de acá. */
	TSet<FString> SelectedNodeIds;
	// Marquee (arrastre con el izquierdo sobre el fondo). Se guarda en coordenadas de MODELO para
	// que el cuadro quede pegado al grafo y no a la pantalla.
	bool bMarquee = false;
	FVector2D MarqueeA = FVector2D::ZeroVector;
	FVector2D MarqueeB = FVector2D::ZeroVector;
	/** Selección de antes de empezar el marquee: con Shift/Ctrl el cuadro SUMA a lo que ya había. */
	TSet<FString> MarqueeBase;
	bool bMarqueeAgrega = false;
	/** Capa que pinta el cuadro por encima de los nodos (sin recibir clics). */
	TSharedPtr<class SWidget> MarqueeLayer;

	// Para el cable-fantasma: última posición del cursor (local a la capa de wires) + esa capa (para
	// repintarla mientras se arrastra una conexión).
	FVector2D LastMousePos = FVector2D::ZeroVector;
	TSharedPtr<class SWidget> WireLayer;

	static constexpr float NodeWidth = 184.0f;   // pines(14) + params(104) + centro(~52) + pines(14)
};
