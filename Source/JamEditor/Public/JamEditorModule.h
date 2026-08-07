#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"
#include "Input/Reply.h"
#include "Types/SlateEnums.h"

class SWindow;
class SDockTab;
class SJamGraphEditor;
class FSpawnTabArgs;
class SWidget;
class SBox;
class SHorizontalBox;
class SVerticalBox;
class SWrapBox;
class SEditableTextBox;
class SMultiLineEditableTextBox;
class STextBlock;
class SCheckBox;
template <typename NumericType> class SSpinBox;
class FAssetThumbnail;
class FAssetThumbnailPool;

/** Un parámetro de una herramienta: nombre + valor por defecto + tipo (bool/int/float/str).
 *  El tipo llega en el spec para que la UI use el control que corresponde (checkbox, spinner…). */
struct FJamParam
{
	FString Name;
	/** Etiqueta visible independiente del nombre estable que se serializa y cablea. */
	FString Label;
	FString Default;
	FString Type;
	/** Override del tipo de cable para parámetros que transportan datos ricos (ej. A[]). */
	FString DataType;
	/** Letra del pin para el modo COMPACTO (una o dos, ej. `X`, `SX`). La calcula `jam.letras` y
	 *  viaja en el spec: la regla vive una sola vez, del lado que está testeado. */
	FString Letra;
	/** Si viene con valores, el param se dibuja como LISTA (anclas, modos…) y no como texto libre. */
	TArray<TSharedPtr<FString>> Options;
	/** Etiquetas humanas paralelas a Options. El valor persistido sigue siendo el de Options. */
	TArray<TSharedPtr<FString>> OptionLabels;
};

/** Una herramienta de Jam vista desde la UI: verbo + doc + params. */
struct FJamTool
{
	struct FPin
	{
		FString Name;
		FString Type;
	};

	FString Verb;
	/** Etiqueta humana. `Verb` es protocolo estable (`fn:f_…`) y no debe filtrarse a la UI. */
	FString Label;
	FString Cat;
	/** Familia visual compacta del ribbon; no forma parte del protocolo ni de los presets. */
	FString Section;
	FString Group;            // subgrupo dentro del tab (el «panel» de Grasshopper); puede ir vacío
	FString Doc;
	bool bSource = false;     // en el grafo, nodo FUENTE (sin pin de entrada)
	bool bAssetPin = false;   // CONSUME un asset (hay que resolvérselo)
	/** Además dibuja su PROPIO pin «asset» en el canvas. No es lo mismo que consumirlo: `place`
	    consume uno pero lo recibe por su entrada principal, y una fila aparte serían dos pines para
	    la misma cosa. Lo deriva el registro (`tools.asset_row`), no la UI. */
	bool bAssetRow = false;
	int32 Arity = 1;          // 0=fuente · 1=unario · -1=variádico (varios cables en «in»)
	FString InName;           // tipo que recibe el pin gordo: A=asset/actor · P=stream de puntos
	FString OutName;          // código de tipo legado del pin estable `out` (A/P/N/M…)
	/** Nombre humano opcional del pin de salida; OutName conserva el código de tipo/protocolo. */
	FString OutLabel;
	/** Firma dinámica de `fn:<nombre>`. Vacíos = contrato clásico de un solo `in`/`out`. */
	TArray<FPin> InputPins;
	TArray<FPin> OutputPins;
	TArray<FJamParam> Params;
};

/** Una carpeta del proyecto con mallas: ruta + nombre corto + cuántas tiene (árbol de Content). */
struct FJamFolder
{
	FString Path;
	FString Name;
	int32 Count = 0;
};

/**
 * Módulo de editor de Jam. Arma en Slate/C++ una "Dash Bar" flotante estilo PolygonFlow Dash:
 * barra de herramientas por sección (una por verbo), panel de params vivo del tool activo, una
 * línea de comando (CLI) que es la fuente de verdad, y preview + veredicto + Confirmar/Descartar.
 * La UI se genera desde `jam.tools.spec_json()` (agregar una herramienta en Python la hace aparecer
 * sola). La ejecución sigue en Python: cada acción compone una línea de DSL y llama a
 * `jam.panel.ejecutar_dsl`. Sin UMG, sin widgets a mano.
 */
class FJamEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

private:
	void RegisterMenus();
	/** Libera lo que retiene UObjects (miniaturas) ANTES de que el motor tire abajo sus
	 * subsistemas de editor. Atada a `FEditorDelegates::OnEditorPreExit` — ver la definición
	 * para el porqué exacto del assert que esto evita. Idempotente: puede llamarse de nuevo
	 * desde `ShutdownModule()` sin efecto si ya corrió. */
	void ReleaseThumbnailResources();

	// ---- los tres paneles son NOMAD TABS, no ventanas sueltas ----
	// Una `SWindow` no se puede acoplar: el docking de Unreal sólo conoce tabs. Como tabs, los
	// paneles se anclan a cualquier lado del editor (o al costado, como sidebar), aparecen en
	// Window ▸ Tools, y **su posición queda guardada en el layout** — que es el «siempre visible».
	void RegisterTabs();
	void UnregisterTabs();
	TSharedRef<SDockTab> SpawnDashTab(const FSpawnTabArgs& Args);
	TSharedRef<SDockTab> SpawnGraphTab(const FSpawnTabArgs& Args);
	TSharedRef<SDockTab> SpawnContentTab(const FSpawnTabArgs& Args);

	void OpenDashBar();
	void OnDashClosed(TSharedRef<SDockTab> Tab);
	void OpenGraph();
	void OnGraphClosed(TSharedRef<SDockTab> Tab);
	/** Veto de cierre del panel Graph: si hay cambios sin guardar, pregunta antes. Devolver false
	 *  cancela el cierre y `OnGraphClosed` no llega a correr. */
	bool PuedeCerrarGraph();
	void OpenWebUI();
	/** Corre un JamGraph (JSON) vía Python (jam.panel.ejecutar_grafo) y devuelve el reporte. */
	FString RunGraphJson(const FString& Json);
	/** Compile/Preflight puro del Graph: valida sin ejecutar tools ni crear Preview. */
	FString CompileGraphJson(const FString& Json);
	/** Inspector: datos del último Run de un nodo, filtrados. Sin nodo devuelve la lista. */
	FString InspectGraphNode(const FString& NodeId, const FString& Filter,
		const FString& Sort, bool bDescending);
	/** Visor 2D del MISMO nodo que mira el inspector: PNG en `Saved/JamPreview2D/` y
	 *  `{ok, ruta, tipo, detalle}`. Dibuja lo que no se ve en el viewport (UVs, máscaras). */
	FString PreviewGraphNode2D(const FString& NodeId, int32 Lado, int32 Canal,
		const FString& Sufijo);
	/** Miniaturas de todos los nodos dibujables del último Run, en UN viaje: `{ok, thumbs:{id:ruta}}`.
	 *  El argumento va sin usar — el delegado reusa `FOnRunGraph` para no declarar una firma nueva
	 *  de un solo uso; los datos salen de la última corrida que ya vive en Python. */
	FString PreviewGraphThumbnails(const FString& Unused);
	/** Variables del grafo para el desplegable de `math`: `{ok, variables:[...]}`. */
	FString GraphVariables(const FString& Json);
	/** Trae una herramienta `.jamtool` a la biblioteca local y refresca la Dash. */
	void ImportarHerramienta();
	/** Hit-test de cables para el reroute: lo resuelve `jam.layout.cable_mas_cercano`. */
	FString CableBajoPunto(const FString& Payload);
	/** Alinear/distribuir la selección del Graph: las cuentas las hace `jam.layout` (puro). */
	FString LayoutGraphNodes(const FString& NodesJson, const FString& Action);
	/** Fija o descarta únicamente el Preview propiedad de la ventana Graph. */
	FString BakeGraphPreview();
	FString DiscardGraphPreview();
	/** Guarda el grafo del canvas como preset compound. */
	FString SaveGraphAsPreset(const FString& Json);
	/** Guarda la selección como función y devuelve el grafo padre para reemplazar el canvas. */
	FString CollapseGraphFunction(const FString& Nombre, const FString& Json,
		const FString& SelectedJson);
	/** ABM de una definición: create/get/update/rename/delete. */
	FString ManageGraphFunction(const FString& Action, const FString& FuncionId,
		const FString& Payload);

	/** Carga el spec en `Tools`. `bIncludeFlow`=true suma las ops de flow (source/mask/instance) para
	 *  el canvas estilo Houdini; false = sólo verbos (Dash Bar). */
	void LoadSpec(bool bIncludeFlow = false);
	TSharedRef<SWidget> BuildDashContent();
	TSharedRef<SWidget> MakeCategoryMenu(const FString& Category);
	/** Ribbon estilo Grasshopper en la Dash Bar: al elegir un tab, sus verbos como fichas con icono. */
	void RebuildDashTabContent();
	void SelectTool(const FString& Verb);
	void FindAndSelectTool(const FString& Query);
	void RebuildParams();
	void ComposeCommandFromParams();
	const FJamTool* FindTool(const FString& Verb) const;
	bool CategoryHasTools(const FString& Category) const;

	// Content browser — VENTANA APARTE (como los paneles de Dash): no le come lugar a la Dash Bar
	// y se puede dejar abierta al lado. Trae árbol de carpetas + conteo real + «mostrar más».
	void OpenContentWindow();
	void OnContentClosed(TSharedRef<SDockTab> Tab);
	TSharedRef<SWidget> BuildContentBrowser();
	void PopulateContent(const FString& Query);
	void RefreshContent();
	void RebuildFolderList();
	TSharedRef<SWidget> MakeAssetTile(const FString& Name, const FString& Path);
	void SelectAsset(const FString& Name, const FString& Path);
	/** Toma como asset activo lo seleccionado en el Content Browser DE UNREAL (verbo `pick`). */
	void PickFromUnrealSelection();
	/** Pone la miniatura grande del asset activo en la Dash Bar. */
	void ShowActiveThumbnail(const FString& Path);

	/** Corre un statement de Python y devuelve lo capturado por LogOutput (stdout/log). */
	FString ExecPythonCapture(const FString& Statement);

public:
	/** Params con los que nace un nodo del canvas: los defaults del registro, y para los verbos que
	    colocan, el punto de mira ya capturado. Vacío si Python no contesta (el nodo usa sus
	    defaults, que es el comportamiento de antes). Público porque lo llama el editor de grafo. */
	TMap<FString, FString> ParamsDeNodoNuevo(const FString& Verb);

private:
	/** Manda una línea de DSL a `jam.panel.ejecutar_dsl` y agrega comando + veredicto al log. */
	void RunCommand(const FString& Command);
	/** Agrega «> comando» + resultado al log acumulativo (estilo Rhino) y hace autoscroll. */
	void AppendLog(const FString& Command, const FString& Result);
	/** Recorre el historial de comandos con ↑ (-1) / ↓ (+1) y lo vuelca en la línea. */
	void RecallHistory(int32 Step);

	/**
	 * MODO VIVO: con el gizmo encendido y `view` tildado, la posición la manda el viewport — los
	 * campos x/y/z se bloquean y muestran EN VIVO dónde está apuntando Jam (y el comando deja de
	 * mandar x/y/z, porque el punto lo resuelve `view=true` al ejecutar).
	 */
	bool IsLiveAim() const;
	/** Punto de mira calculado en C++ (línea desde la cámara del viewport). false si no hay viewport. */
	bool ComputeAimPoint(FVector& Out) const;
	/**
	 * Al salir del modo vivo, x/y/z se quedan con la ÚLTIMA posición del gizmo (ya absolutas) para
	 * poder retocarlas a mano. Como pasan a ser absolutas, `view` queda destildado: es la condición
	 * que mantiene coherente el comando (con view=true esos campos serían offsets).
	 */
	void FreezeAimIntoParams();
	/** Avisa al fantasma GRIS dónde va a caer la pieza (x/y/z + view + anchor de los campos). */
	void PushGhostTarget();

	// Presets: menú para aplicar uno (corre por preview) y botón para guardar el comando actual.
	TSharedRef<SWidget> MakePresetMenu();
	FReply OnSavePresetClicked();

	FReply OnPreviewClicked();
	FReply OnConfirmarClicked();
	FReply OnDescartarClicked();
	void OnCmdCommitted(const FText& Text, ETextCommit::Type CommitType);

	TArray<FJamTool> Tools;
	TArray<FString> Categories;
	FString ActiveVerb;
	FString ActiveDashTab;                        // tab (categoría) abierto en el ribbon de la Dash Bar
	TSharedPtr<SHorizontalBox> DashTabContent;    // fichas con icono de la categoría activa
	FString LogText;

	// Débiles: el dueño del tab es el tab manager. Si los tuviéramos fuertes, cerrar el panel no
	// liberaría nada y «¿está abierto?» diría que sí para siempre.
	TWeakPtr<SDockTab> DashTab;
	TWeakPtr<SDockTab> GraphTab;
	TWeakPtr<SDockTab> ContentTab;
	/** El canvas vivo, para poder guardar su estado cuando cierran el panel. */
	TWeakPtr<SJamGraphEditor> GraphWidget;
	/** Grafo de la última vez que se cerró el panel: al reabrirlo vuelve el trabajo.
	 *  Antes cerrar la ventana perdía el diagrama sin preguntar. */
	FString GraphEstadoGuardado;
	TSharedPtr<SVerticalBox> ParamsBox;
	TSharedPtr<SEditableTextBox> CmdBox;
	TSharedPtr<SEditableTextBox> SearchBox;
	TSharedPtr<SMultiLineEditableTextBox> OutputBox;
	// Un control por tipo de param: checkbox (bool), spinner (números), texto (el resto).
	TMap<FString, TSharedPtr<SEditableTextBox>> ParamFields;
	TMap<FString, TSharedPtr<SCheckBox>> ParamChecks;
	TMap<FString, TSharedPtr<SSpinBox<float>>> ParamSpins;
	TMap<FString, bool> ParamIsInt;
	TMap<FString, TArray<TSharedPtr<FString>>> ParamOptions;   // dominio cerrado → lista
	TMap<FString, TArray<TSharedPtr<FString>>> ParamOptionLabels; // presentación, mismo índice
	TMap<FString, FString> ParamChoice;                        // opción elegida por param

	// Valor vivo de cada spinner (la fuente de verdad cuando NO está en modo vivo).
	TMap<FString, float> ParamValues;
	// Última posición del gizmo, refrescada por un timer del propio Slate (sin tocar Python).
	FVector LiveAim = FVector::ZeroVector;

	// Historial de comandos (↑/↓ en la línea, como Rhino).
	TArray<FString> History;
	int32 HistoryPos = INDEX_NONE;

	// Content browser.
	FString SelectedAssetName;
	FString SelectedAssetPath;
	FString ContentFolder;               // "" = todas las carpetas
	int32 ContentLimit = 200;            // tope de miniaturas; «mostrar más» lo sube
	int32 ContentTotal = 0;              // cuántas matchean de verdad (para no ocultar assets)
	int32 ContentAll = 0;                // cuántas mallas tiene el proyecto entero
	TArray<FJamFolder> ContentFolders;
	bool bGizmoOn = false;
	bool bGhostOn = false;
	bool bWasLiveAim = false;   // para detectar cuándo se SALE del modo vivo y congelar x/y/z
	TSharedPtr<STextBlock> AssetLabel;
	TSharedPtr<SBox> ActiveThumbBox;          // miniatura grande del asset activo
	TSharedPtr<FAssetThumbnail> ActiveThumb;
	TSharedPtr<STextBlock> ContentCountLabel;
	TSharedPtr<SWrapBox> ContentGrid;
	TSharedPtr<SVerticalBox> ContentFolderList;
	TSharedPtr<SEditableTextBox> ContentSearchBox;
	TSharedPtr<FAssetThumbnailPool> ThumbnailPool;
	TArray<TSharedPtr<FAssetThumbnail>> ThumbnailsKeepAlive;
};
