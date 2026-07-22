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

	void LoadSpec();
	TSharedRef<SWidget> BuildDashContent();
	TSharedRef<SWidget> MakeCategoryMenu(const FString& Category);
	void SelectTool(const FString& Verb);
	void FindAndSelectTool(const FString& Query);
	void RebuildParams();
	void ComposeCommandFromParams();
	const FJamTool* FindTool(const FString& Verb) const;
	bool CategoryHasTools(const FString& Category) const;

	// Content browser (miniaturas de assets).
	TSharedRef<SWidget> BuildContentBrowser();
	void ToggleContent();
	void PopulateContent(const FString& Query);
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
	TSharedPtr<SVerticalBox> ParamsBox;
	TSharedPtr<SEditableTextBox> CmdBox;
	TSharedPtr<SEditableTextBox> SearchBox;
	TSharedPtr<SMultiLineEditableTextBox> OutputBox;
	TMap<FString, TSharedPtr<SEditableTextBox>> ParamFields;

	// Content browser.
	bool bContentOpen = false;
	FString SelectedAssetName;
	FString SelectedAssetPath;
	TSharedPtr<STextBlock> AssetLabel;
	TSharedPtr<SWrapBox> ContentGrid;
	TSharedPtr<SEditableTextBox> ContentSearchBox;
	TSharedPtr<FAssetThumbnailPool> ThumbnailPool;
	TArray<TSharedPtr<FAssetThumbnail>> ThumbnailsKeepAlive;
};
