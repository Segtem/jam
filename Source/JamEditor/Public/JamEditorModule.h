#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"
#include "Input/Reply.h"
#include "Types/SlateEnums.h"

class SWindow;
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
	FString Default;
	FString Type;
	/** Si viene con valores, el param se dibuja como LISTA (anclas, modos…) y no como texto libre. */
	TArray<TSharedPtr<FString>> Options;
};

/** Una herramienta de Jam vista desde la UI: verbo + doc + params. */
struct FJamTool
{
	FString Verb;
	FString Cat;
	FString Doc;
	bool bSource = false;     // en el grafo, nodo FUENTE (sin pin de entrada)
	bool bAssetPin = false;   // consume un asset → en el grafo lleva un pin «asset» explícito
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
	void OpenDashBar();
	void OnDashClosed(const TSharedRef<SWindow>& Window);
	void OpenGraph();
	void OpenWebUI();
	/** Corre un JamGraph (JSON) vía Python (jam.panel.ejecutar_grafo) y devuelve el reporte. */
	FString RunGraphJson(const FString& Json);
	/** Guarda el grafo del canvas como preset compound. */
	FString SaveGraphAsPreset(const FString& Json);

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
	void OnContentClosed(const TSharedRef<SWindow>& Window);
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

	TSharedPtr<SWindow> DashWindow;
	TSharedPtr<SWindow> GraphWindow;
	TSharedPtr<SWindow> ContentWindow;
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
