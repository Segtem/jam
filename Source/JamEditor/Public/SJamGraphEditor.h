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
/** Visor 2D: (node_id, lado en px, canal de UV) → JSON `{ok, ruta, tipo, detalle}` o `{ok:false,
 *  error}`. Dibuja lo que NO se ve en el viewport: el desplegado de UVs de una malla y la máscara
 *  que calcula un grafo de material. El PNG lo escribe Python en `Saved/JamPreview2D/`. */
DECLARE_DELEGATE_RetVal_FourParams(FString, FOnPreview2D,
	const FString& /*node*/, int32 /*lado*/, int32 /*canal*/, const FString& /*sufijo*/);
/** Colapsar selección: (nombre humano, grafo completo, ids elegidos) → {ok,graph,tool,report}. */
DECLARE_DELEGATE_RetVal_ThreeParams(FString, FOnCollapseFunction,
	const FString& /*nombre*/, const FString& /*graph*/, const FString& /*selected*/);
/** ABM de función: (acción, verbo/id, payload) → envelope JSON. */
DECLARE_DELEGATE_RetVal_ThreeParams(FString, FOnFunctionManage,
	const FString& /*accion*/, const FString& /*id*/, const FString& /*payload*/);

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
		SLATE_EVENT(FOnPreview2D, OnPreview2D)
		/** Miniaturas de TODOS los nodos dibujables del último Run, en un solo viaje. */
		SLATE_EVENT(FOnRunGraph, OnPreview2DTodos)
		/** Variables del grafo para el desplegable de `math`: recibe el JSON, devuelve `{ok, variables}`. */
		SLATE_EVENT(FOnRunGraph, OnGraphVariables)
		/** Qué cable hay bajo un punto: lo calcula `jam.layout`, puro y testeado. */
		SLATE_EVENT(FOnRunGraph, OnCableBajoPunto)
		/** Alinear/distribuir: lo resuelve `jam.layout`. */
		SLATE_EVENT(FOnLayout, OnLayout)
		SLATE_EVENT(FOnCollapseFunction, OnCollapseFunction)
		SLATE_EVENT(FOnFunctionManage, OnFunctionManage)
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

	// ---- estado del canvas, para sobrevivir al cierre del panel ----
	// El panel es un tab: cerrarlo destruye el widget. Sin esto, cerrar Jam ▸ Graph tiraba el
	// diagrama sin preguntar. Viaja el grafo Y la vista, porque volver a un grafo que está en otro
	// zoom y en otro lado se siente como que no volvió.
	FString EstadoDelCanvas() const;
	void RestaurarCanvas(const FString& Json);

	// ---- cerrar el panel sin perder el diagrama ----
	/** ¿El diagrama tiene cambios que NO están en disco? Compara el JSON vivo contra la foto del
	 *  último Guardar/Abrir, así que deshacer hasta el estado guardado vuelve a dar «limpio». */
	bool HayCambiosSinGuardar() const;
	/** Diálogo «¿guardar antes de cerrar?». Devuelve false si el cierre debe ABORTARSE: o el usuario
	 *  eligió Cancelar, o dijo que sí guardar y el guardado no llegó a concretarse. */
	bool ConfirmarCierre();

private:
	struct FGNode
	{
		FString Id;
		FString Verb;
		FVector2D Pos = FVector2D::ZeroVector;
		float Height = 34.0f;
		/** Ancho REAL de este nodo: `NodeWidth`, o `NodeWidthCompacto` si está comprimido. Deja de
		 *  ser una constante porque lo leen los cables, el marquee, el encuadre y el auto-layout —
		 *  si alguno usara el valor fijo, un nodo comprimido tendría los cables colgando en el aire
		 *  a 110 px de su borde. */
		float Width = 184.0f;
		/** Pines de entrada en ORDEN de fila (incluye «asset» si el verbo lo tiene): el índice acá es
		 *  la fila donde se ancla el wire. */
		TArray<FString> PinNames;
		/** Pines de salida nombrados de una función, en orden de fila. */
		TArray<FString> OutputPinNames;
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
		/** Puntos de paso (reroute), en espacio MODELO. Son PURAMENTE visuales: el grafo que se
		 *  compila y se corre es exactamente el mismo con o sin ellos. Por eso no viajan dentro de
		 *  la arista —una arista de 5 elementos la descarta en silencio `JamGraph.from_json`— sino
		 *  en una clave propia del JSON (ver `BuildJson`). */
		TArray<FVector2D> Vias;
	};

	/** Una caja de comentario/grupo (Fase 7.1): la comment box de Blueprint, el network box de
	 *  Houdini. NO tiene lista de nodos miembro — «qué contiene» se recalcula por contención
	 *  espacial (ver `NodeIdsTouchingRect`) cada vez que se empieza a arrastrar el cuerpo, nunca se
	 *  persiste. Es organizativa, no dueña de nada: borrar la caja no borra lo que encierra. */
	struct FGComment
	{
		FString Id;
		FVector2D Pos = FVector2D::ZeroVector;        // espacio MODELO, como FGNode::Pos
		FVector2D Size = FVector2D(240.0f, 160.0f);
		FString Title;
		FLinearColor Color = FLinearColor(0.65f, 0.60f, 0.50f, 1.0f);
		TSharedPtr<class SJamGraphComment> Widget;    // el widget es la fuente viva del título Y del color, igual que GetParamValues() en FGNode
	};

	/** Agrega un nodo; devuelve su Id (para reconstruir grafos al cargar un diagrama).
	 *  `PreferredId` conserva el id que traía el archivo en vez de renumerar: sin eso, cada Deshacer
	 *  reescribiría los ids del grafo (y el orden de un TMap de JSON ni siquiera es estable), así que
	 *  el veredicto del oráculo y el inspector quedarían apuntando a nodos que cambiaron de nombre. */
	FString AddNode(const FString& Verb, const FVector2D* At = nullptr,
		const FString& PreferredId = FString());

	// ---- el gesto de la paleta: clic = al centro de la vista · arrastre = donde soltás ----
	/** Crea el nodo en el centro de lo que se está VIENDO. Con el canvas paneado, ese punto y el
	    origen del grafo están en lugares distintos, y sólo uno es donde vas a buscar el nodo. */
	FString AddNodeAlCentro(const FString& Verb);
	virtual FReply OnDragOver(const FGeometry& MyGeometry, const FDragDropEvent& DragDropEvent) override;
	virtual FReply OnDrop(const FGeometry& MyGeometry, const FDragDropEvent& DragDropEvent) override;
	void DeleteNode(const FString& Id);

	// ---- cajas de comentario/grupo (Fase 7.1) ----
	/** Agrega una caja; devuelve su Id. `PreferredId` conserva el id del archivo, igual que `AddNode`. */
	FString AddComment(const FVector2D& Pos, const FVector2D& Size, const FString& Title,
		const FString& PreferredId = FString(),
		const FLinearColor& Color = FLinearColor(0.65f, 0.60f, 0.50f, 1.0f));
	void DeleteComment(const FString& Id);
	FGComment* FindComment(const FString& Id);
	/** Clic en el cuerpo de una caja. Misma regla que `ClickNode`, sobre `SelectedCommentIds`. */
	void ClickComment(const FString& Id, bool bShift, bool bCtrl);
	/** Atajo `C`: encierra la selección de nodos en una caja nueva (bounding box + margen). */
	void CreateCommentFromSelection();
	/** Congela qué nodos toca la caja AHORA — se llama al iniciar cada arrastre del cuerpo, nunca se
	 *  persiste (ver `CommentDragNodeIds`). */
	void BeginCommentDrag(const FString& Id);
	void DragComment(const FString& Id, const FVector2D& DeltaModelo);
	void ResizeComment(const FString& Id, const FVector2D& DeltaModelo);

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
	/** `D`: apaga/prende los elegidos que ADMITAN bypass, en un solo paso de historial. Los que no
	 *  lo admiten se saltean en silencio — el gesto es «apagá lo que se pueda de esto», no una
	 *  operación que falla entera porque uno de doce nodos cambia de tipo. */
	void AlternarBypassDeLaSeleccion();
	/** Alinear/distribuir por `jam.layout`: «izquierda…centro-y», «dist-x», «dist-y». */
	void AcomodarSeleccion(const FString& Accion);
	/** Rectángulo del marquee en coordenadas de MODELO; false si no hay uno en curso. */
	bool GetMarquee(FVector2D& OutA, FVector2D& OutB) const;
	/** Ids de nodo cuyo AABB toca `[Min,Max)` — cruce con desigualdad ESTRICTA. ÚNICA fuente de esta
	 *  fórmula en todo el archivo: la usan tanto el marquee como el arrastre de una caja de
	 *  comentario, para que las dos reglas no puedan divergir en silencio. */
	TArray<FString> NodeIdsTouchingRect(const FVector2D& Min, const FVector2D& Max) const;

	// ---- historial (Ctrl+Z / Ctrl+Shift+Z): el grafo YA sabe serializarse ----
	// No hace falta un motor de comandos: un paso deshacible es el JSON del grafo entero. Un diagrama
	// pesa kilobytes, y así el historial no puede desincronizarse del modelo, porque ES el modelo.
	/** Registra un paso deshacible. Se llama DESPUÉS de la mutación: apila el estado ANTERIOR (que
	 *  `Anterior` viene guardando) y vuelve a fotografiar el actual. */
	void Marcar();
	void Deshacer();
	void Rehacer();
	bool PuedeDeshacer() const { return Deshechos.Num() > 0; }
	bool PuedeRehacer() const { return Rehechos.Num() > 0; }
	/** Carga un snapshot sin que la carga misma cuente como un paso nuevo. */
	void RestaurarSnapshot(const FString& Json);

	// ---- menú principal estilo Grasshopper (File / Edit / View / Display / Solution) ----
	void FillFileMenu(class FMenuBuilder& MB);
	void FillEditMenu(class FMenuBuilder& MB);
	void FillViewMenu(class FMenuBuilder& MB);
	void FillDisplayMenu(class FMenuBuilder& MB);
	void FillSolutionMenu(class FMenuBuilder& MB);
	/** Vacía el grafo (nodos + wires). */
	void NewGraph();
	/** Valida y reconstruye el grafo desde JSON. Un fallo no modifica canvas, vista ni CurrentPath. */
	bool LoadGraphJson(const FString& Json, bool bConservarEdicionFuncion = false);
	/** Diálogos de archivo (DesktopPlatform): guardar/abrir un diagrama .jamgraph (JSON).
	 *  `SaveDiagram` devuelve si el archivo QUEDÓ escrito — cancelar el diálogo o fallar al escribir
	 *  dan false, y de eso depende que cerrar el panel se aborte en vez de tirar el trabajo. */
	bool SaveDiagram(bool bForceDialog);
	void OpenDiagram();
	/** Carga uno de los tutoriales del tab «Aprender». El catálogo es `Resources/Examples/examples.json`:
	    cada ficha de ese tab llama acá con su archivo, así que sumar un tutorial no toca C++. */

	// ---- inspector de datos (el Geometry Spreadsheet de Jam) ----
	/** Relee del último Run: repuebla el selector de nodos y la tabla del nodo elegido. */
	void RefreshInspector();
	TSharedRef<class SWidget> BuildInspector();

	// ---- visor 2D: la vista VISUAL del mismo dato que el inspector muestra en números ----
	// Comparte con él el selector de nodo (`InspectNodeId`): un solo control de «qué nodo», dos
	// vistas. Un segundo selector es lo que después se desincroniza.
	TSharedRef<class SWidget> BuildPreview2D();
	/** Repinta el visor con el nodo del inspector. Lo llama `RefreshInspector`, así que corre
	 *  después de cada Run y al cambiar de nodo — sin disparadores propios. */
	void RefreshPreview2D();
	/** Suelta la textura del brush anterior. Slate cachea las texturas dinámicas POR NOMBRE de
	 *  archivo, y `api.preview_2d` escribe siempre la misma ruta por nodo: sin esto, el segundo Run
	 *  del mismo nodo seguiría mostrando la imagen del primero para siempre. */
	void SoltarPreview2D();
	/** Pide las miniaturas de todos los nodos dibujables y se las reparte, al estilo de Substance
	 *  Designer. Un solo viaje a Python: con un grafo de 30 nodos, una llamada por nodo serían 30
	 *  `ExecPythonCapture` por Run. */
	void RefrescarMiniaturas();
	/** Suelta las texturas de las miniaturas ANTES de recrearlas: Slate las cachea por nombre de
	 *  archivo y la ruta por nodo es estable, así que sin esto el segundo Run mostraría la miniatura
	 *  del primero. Es la misma trampa que `SoltarPreview2D`, multiplicada por N nodos. */
	void SoltarMiniaturas();
	/** Ventana emergente con el dibujo a resolución grande, para mirarlo en detalle. NO modal: se
	 *  deja abierta al lado mientras se sigue tocando el grafo, que es para lo que sirve. */
	void AbrirVisorFullRes(const FString& NodeId);
	void SoltarVisorFullRes();
	/** Nombres de variable usables en una expresión, preguntándole al cerebro por el grafo VIVO.
	 *  Los calcula `jam.api.variables` con el mismo código que después resuelve la expresión, así
	 *  el desplegable no puede ofrecer algo que el evaluador vaya a rechazar. */
	TArray<FString> VariablesDelGrafo() const;
	void LoadBundledExample(const FString& Filename, const FText& LoadedMessage);
	/** Galería: reemplaza el grafo por UNO DE CADA nodo en grilla (para sacarle un screenshot). */
	void InsertAllNodes();
	/** Reencuadra: pan/zoom a un estado legible. */
	void ResetView();
	/** Índice del parámetro `Pin` en el verbo del nodo `Id`, o -1 si es «in»/«out» (header). */
	int32 PinIndex(const FString& Id, const FString& Pin) const;
	int32 OutputPinIndex(const FString& Id, const FString& Pin) const;
	/** Tipos efectivos de los extremos y validación central de un cable. */
	FString OutputDataTypeFor(const FString& NodeId, const FString& Pin) const;
	FString InputDataTypeFor(const FString& NodeId, const FString& Pin) const;
	bool CanConnect(const FString& From, const FString& FromPin, const FString& To,
		const FString& ToPin, FString& OutError) const;

	/** Ribbon estilo Grasshopper: al elegir un tab (categoría) se rellenan sus fichas con icono. */
	void RebuildTabContent();
	/** Cambia la familia principal y elige una categoría válida dentro de ella. */
	void SelectSection(const FString& Section);
	/** Segunda fila corta: categorías de la familia principal activa. */
	void RebuildCategoryStrip();
	/** El tab «Aprender»: fichas que CARGAN un tutorial en vez de crear un nodo. */
	void RebuildLearnTab();
	void OnPinClicked(const FString& Id, const FString& Pin, bool bOutput);
	/** Suelta la conexión a medias (el cable-fantasma). Devuelve si había una: quien llama decide
	 *  qué hacer cuando NO la había — `Esc` limpia la selección, el botón derecho panea. */
	bool CancelarConexion();

	// ---- reroute: puntos de paso sobre un cable ----
	/** Inserta un punto de paso donde se hizo doble clic, o SACA el que ya estaba ahí. Devuelve si
	 *  tocó algo — quien llama decide qué hacer si no (abrir el buscador). */
	bool AlternarViaEnCable(const FVector2D& EnCanvas);
	/** Qué cable hay bajo un punto del canvas: arista, segmento y el punto SOBRE la curva. Lo
	 *  resuelve `jam.layout`; lo comparten la vía y el nodo reroute. */
	bool CableBajoPunto(const FVector2D& EnCanvas, int32& OutArista, int32& OutSegmento,
		FVector2D& OutPuntoModelo) const;
	/** Ctrl+doble clic: parte el cable e inserta un NODO reroute del tipo que lleva ese cable. El
	 *  verbo se busca en el registro, no en una tabla escrita a mano. */
	bool InsertarRerouteEnCable(const FVector2D& EnCanvas);
	/** Índice de (arista, vía) bajo un punto del canvas; false si no hay ninguna. */
	bool ViaBajoElCursor(const FVector2D& EnCanvas, int32& OutArista, int32& OutVia) const;
	/** Recomputa, por cada nodo, qué pines de parámetro tienen cable entrando y se lo dice a su widget
	 *  (para que grisee esos inputs). Se llama tras cualquier cambio de aristas. */
	void RefreshCabledPins();
	void ValidateGraph();
	void RunGraph();
	void BakePreview();
	void DiscardPreview();
	/** Aplica el envelope {report,nodes} de Compile o Run al output y a los estados de los nodos. */
	void ApplyGraphResult(const FString& Result);
	/** JSON del grafo. Con `Solo`, únicamente esos nodos y las aristas con LAS DOS puntas adentro —
	 *  un cable a medias no es un grafo, y pegarlo dejaría una entrada conectada a la nada.
	 *  `SoloComentarios` filtra igual las cajas; por defecto (nullptr) van todas. */
	FString BuildJson(const TSet<FString>* Solo = nullptr,
		const TSet<FString>* SoloComentarios = nullptr) const;

	// ---- portapapeles: es el mismo JSON, así que se pega entre ventanas y se lee a ojo ----
	void Copiar(bool bCortar);
	void Pegar();
	/** Duplicar = copiar y pegar sin pisar el portapapeles del sistema. */
	void Duplicar();
	/** Ctrl+G: el cerebro puro decide el borde; Slate instala el tool devuelto y carga el padre. */
	void ColapsarSeleccion();
	/** Biblioteca de funciones: alta, edición del cuerpo, guardado, renombre y baja. */
	void NuevaFuncion();
	void EditarFuncion(const FString& Verb);
	void GuardarFuncion();
	void GuardarYCerrarFuncion();
	void VolverDeFuncion(bool bCambiosGuardados);
	void RenombrarFuncion(const FString& Verb, const FString& NombreActual);
	void EliminarFuncion(const FString& Verb, const FString& NombreActual);
	/** Publica/despublica: cambia si la herramienta aparece en la Dash, sin tocar su cuerpo. */
	void PublicarFuncion(const FString& Verb, bool bPublicar);
	/** Escribe la herramienta como `.jamtool` portable (JSON, transparente — no compilado). */
	void ExportarFuncion(const FString& Verb, const FString& NombreActual);
	bool AplicarRespuestaFuncion(const FString& Res, bool bCargarCuerpo);
	/** Inserta un fragmento JSON en el grafo actual con ids NUEVOS, corrido para que no tape al
	 *  original, y deja lo pegado seleccionado. Ignora en silencio lo que no sea un fragmento
	 *  válido: el portapapeles del sistema puede tener cualquier cosa.
	 *  Devuelve si pegó algo — el que llama decide si eso fue un paso del historial. Todo el pegado
	 *  corre callado, así que N nodos con sus cables son UN Ctrl+Z. */
	bool PegarJson(const FString& Json, bool bDesplazar);

	/** Encuadra la selección (o todo el grafo si no hay ninguna): la tecla `F` de siempre. */
	void Encuadrar(bool bSoloSeleccion);
	const FJamTool* FindTool(const FString& Verb) const;
	FGNode* FindNode(const FString& Id);
	/** Color del cable que SALE de un nodo (según el tipo de su salida). */
	FLinearColor WireColorFor(const FString& NodeId, const FString& Pin = TEXT("out")) const;

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
	TArray<FString> Categories;        // categorías reales del protocolo, en orden de aparición
	TArray<FString> Sections;          // familias compactas de navegación
	FString ActiveSection;             // familia abierta en la fila principal
	FString ActiveTab;                 // categoría abierta dentro de la familia
	TSharedPtr<SHorizontalBox> CategoryStripBox; // segunda fila de categorías
	TSharedPtr<SHorizontalBox> TabContentBox;   // fichas de la categoría activa
	TArray<FGNode> Nodes;
	TArray<FGEdge> Edges;                      // aristas con pin (origen.out → destino.pin)
	TArray<FGComment> Comments;                // cajas de comentario/grupo (Fase 7.1)
	FString PendingSource;                     // nodo de salida armado, esperando una entrada
	FString PendingSourcePin;                  // pin de salida armado (por ahora «out»)
	FString CurrentPath;                       // archivo del diagrama actual (para «Guardar» sin diálogo)
	/** Foto del JSON tal como quedó en el último Guardar/Abrir — contra esto se decide si hay cambios
	 *  sin guardar. Vacío = nunca se escribió ni se abrió nada, así que cualquier nodo cuenta como
	 *  cambio. A propósito NO lo tocan `LoadGraphJson` ni `NewGraph`: los usan Deshacer/Rehacer y
	 *  Ctrl+G, y marcar «guardado» ahí diría que el disco tiene algo que nunca se escribió. */
	FString GuardadoEn;
	int32 NextId = 1;
	int32 NextCommentId = 1;                   // contador propio: «cN», namespace separado del de nodos

	FOnRunGraph OnRunGraph;
	FOnRunGraph OnCompileGraph;
	FOnGraphPreviewAction OnBakePreview;
	FOnGraphPreviewAction OnDiscardPreview;
	FOnRunGraph OnSaveGraph;
	FOnInspect OnInspect;
	FOnPreview2D OnPreview2D;
	FOnRunGraph OnPreview2DTodos;
	FOnRunGraph OnGraphVariables;
	/** Hit-test de cables: recibe los tramos, devuelve cuál está bajo el punto. Lo resuelve
	 *  `jam.layout.cable_mas_cercano`, que reproduce la misma curva que se dibuja. */
	FOnRunGraph OnCableBajoPunto;
	/** Arrastre de un punto de paso: (arista, vía) o -1. No se persiste. */
	int32 ArrastrandoAristaVia = -1;
	int32 ArrastrandoVia = -1;
	/** Un brush por nodo con miniatura. Vive acá y no en el nodo porque soltar la textura es
	 *  responsabilidad de quien la creó, y porque un nodo puede morir mientras su brush sigue en el
	 *  caché de Slate. */
	TMap<FString, TSharedPtr<struct FSlateDynamicImageBrush>> Miniaturas;
	static constexpr int32 MiniaturaLado = 64;
	/** Resolución del popup. Para una máscara de material cada píxel es una evaluación del IR en
	 *  CPU, así que 768² ya son ~590k: es el techo razonable para que abrirlo no cuelgue el editor. */
	static constexpr int32 VisorFullLado = 768;
	TSharedPtr<struct FSlateDynamicImageBrush> VisorFullBrush;
	TWeakPtr<class SWindow> VisorFullVentana;
	FOnLayout OnLayout;
	FOnCollapseFunction OnCollapseFunction;
	FOnFunctionManage OnFunctionManage;
	FString FuncionEnEdicion;
	FString NombreFuncionEnEdicion;
	/** Estado completo del documento que estaba abierto antes de entrar al cuerpo de una función. */
	FString EstadoAntesDeEditarFuncion;

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

	// ---- visor 2D ----
	/** Brush con el PNG del último dibujo. Se conserva porque `SImage` lo referencia mientras vive;
	 *  soltarlo es responsabilidad de `SoltarPreview2D` (ver el porqué del caché ahí). */
	TSharedPtr<struct FSlateDynamicImageBrush> Preview2DBrush;
	/** Texto bajo la imagen: el `detalle` cuando hay dibujo, o el `error` explicando por qué no lo
	 *  hay. Nunca un panel en blanco: «no se puede dibujar esto» también es información. */
	TSharedPtr<class STextBlock> Preview2DEstado;
	TSharedPtr<class SImage> Preview2DImagen;
	/** Canal de UV a desplegar. Una malla puede tener varios y el que importa no siempre es el 0. */
	int32 Preview2DCanal = 0;
	static constexpr int32 Preview2DLado = 320;

	FSimpleDelegate OnOpenContent;
	TAttribute<FString> ActiveAsset;
	TSharedPtr<SCanvas> Canvas;
	/** Canvas hermano para las cajas de comentario/grupo: mismo RenderTransform de zoom que `Canvas`
	 *  (ver `ApplyZoom`), insertado ANTES en el SOverlay para pintarse detrás de los nodos. */
	TSharedPtr<SCanvas> CommentCanvas;
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
	/** Cajas de comentario elegidas. INDEPENDIENTE de `SelectedNodeIds` a propósito: un clic simple
	 *  en un nodo o en una caja reemplaza sólo su propio set (así se puede tener nodos Y cajas
	 *  elegidos a la vez con Shift, como en Blueprint). */
	TSet<FString> SelectedCommentIds;
	/** Ids de nodo que el arrastre EN CURSO del cuerpo de una caja mueve junto con ella. Recalculado
	 *  en `BeginCommentDrag` al iniciar cada arrastre — nunca persistido en `FGComment`. */
	TArray<FString> CommentDragNodeIds;
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

	// Historial: dos pilas de snapshots JSON + la foto del estado actual.
	TArray<FString> Deshechos;   // estados anteriores, el último es el que devuelve Ctrl+Z
	TArray<FString> Rehechos;    // estados que Ctrl+Z dejó atrás
	/** Foto del estado tal como quedó después del último paso registrado.
	 *  Es lo que hace que editar un parámetro y DESPUÉS borrar un nodo sean dos pasos y no uno:
	 *  `BuildJson` lee los valores VIVOS de los widgets, así que la foto siempre refleja lo tipeado. */
	FString Anterior;
	/** Mientras está prendido no se registra nada: cargar un diagrama o restaurar un snapshot crea
	 *  muchas mutaciones internas que son UN solo paso para el usuario. */
	bool bSinHistorial = false;
	static constexpr int32 MaxHistorial = 50;

	// Para el cable-fantasma: última posición del cursor (local a la capa de wires) + esa capa (para
	// repintarla mientras se arrastra una conexión).
	FVector2D LastMousePos = FVector2D::ZeroVector;
	TSharedPtr<class SWidget> WireLayer;

	static constexpr float NodeWidth = 184.0f;   // pines(14) + params(104) + centro(~52) + pines(14)
	/** Comprimido: pines(14) + letra(~22) + icono(24) + pines(14). Sin campos de valor ni etiquetas,
	 *  como un componente colapsado de Grasshopper. El ALTO no cambia —sigue habiendo una fila por
	 *  pin— así que el anclaje vertical de los cables queda intacto. */
	static constexpr float NodeWidthCompacto = 82.0f;
	static_assert(NodeWidthCompacto - 2 * 14.0f - 22.0f >= 28.0f,
		"el centro comprimido tiene que dejar entrar el icono de 24 px con algo de aire: "
		"NodeWidthCompacto - 2*PinColW - LetraColW");
};
