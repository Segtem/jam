#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"
#include "Input/Reply.h"
#include "Types/SlateEnums.h"

class SWindow;
class SWidget;
class SVerticalBox;
class SWrapBox;
class SEditableTextBox;
class SMultiLineEditableTextBox;
class STextBlock;
class FAssetThumbnail;
class FAssetThumbnailPool;

/** Una herramienta de Jam vista desde la UI: verbo + doc + params (nombre → default). */
struct FJamTool
{
	FString Verb;
	FString Cat;
	FString Doc;
	TArray<TPair<FString, FString>> Params;
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

	void LoadSpec();
	TSharedRef<SWidget> BuildDashContent();
	TSharedRef<SWidget> MakeCategoryMenu(const FString& Category);
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

	/** Corre un statement de Python y devuelve lo capturado por LogOutput (stdout/log). */
	FString ExecPythonCapture(const FString& Statement);
	/** Manda una línea de DSL a `jam.panel.ejecutar_dsl` y agrega comando + veredicto al log. */
	void RunCommand(const FString& Command);
	/** Agrega «> comando» + resultado al log acumulativo (estilo Rhino) y hace autoscroll. */
	void AppendLog(const FString& Command, const FString& Result);

	FReply OnPreviewClicked();
	FReply OnConfirmarClicked();
	FReply OnDescartarClicked();
	void OnCmdCommitted(const FText& Text, ETextCommit::Type CommitType);

	TArray<FJamTool> Tools;
	TArray<FString> Categories;
	FString ActiveVerb;
	FString LogText;

	TSharedPtr<SWindow> DashWindow;
	TSharedPtr<SWindow> GraphWindow;
	TSharedPtr<SWindow> ContentWindow;
	TSharedPtr<SVerticalBox> ParamsBox;
	TSharedPtr<SEditableTextBox> CmdBox;
	TSharedPtr<SEditableTextBox> SearchBox;
	TSharedPtr<SMultiLineEditableTextBox> OutputBox;
	TMap<FString, TSharedPtr<SEditableTextBox>> ParamFields;

	// Content browser.
	FString SelectedAssetName;
	FString SelectedAssetPath;
	FString ContentFolder;               // "" = todas las carpetas
	int32 ContentLimit = 200;            // tope de miniaturas; «mostrar más» lo sube
	int32 ContentTotal = 0;              // cuántas matchean de verdad (para no ocultar assets)
	int32 ContentAll = 0;                // cuántas mallas tiene el proyecto entero
	TArray<FJamFolder> ContentFolders;
	TSharedPtr<STextBlock> AssetLabel;
	TSharedPtr<STextBlock> ContentCountLabel;
	TSharedPtr<SWrapBox> ContentGrid;
	TSharedPtr<SVerticalBox> ContentFolderList;
	TSharedPtr<SEditableTextBox> ContentSearchBox;
	TSharedPtr<FAssetThumbnailPool> ThumbnailPool;
	TArray<TSharedPtr<FAssetThumbnail>> ThumbnailsKeepAlive;
};
