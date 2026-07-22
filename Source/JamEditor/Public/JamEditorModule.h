#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"
#include "Input/Reply.h"
#include "Types/SlateEnums.h"

class SDockTab;
class FSpawnTabArgs;
class SEditableTextBox;
class SMultiLineEditableTextBox;

/**
 * Módulo de editor de Jam. Registra un tab dockeable ("Consola Jam") armado 100% en Slate/C++
 * (sin UMG, sin widgets a mano) y un ítem de menú para abrirlo. La lógica de las herramientas
 * sigue viviendo en Python: el tab manda cada línea a `jam.panel.ejecutar_dsl` y muestra el veredicto.
 */
class FJamEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

private:
	TSharedRef<SDockTab> SpawnJamTab(const FSpawnTabArgs& Args);
	void RegisterMenus();
	void OpenTab();

	/** Corre una línea de DSL en Python y vuelca el veredicto en el cuadro de salida. */
	void RunCommand(const FString& Command);

	FReply OnRunClicked();
	FReply OnConfirmarClicked();
	FReply OnDescartarClicked();
	void OnInputCommitted(const FText& Text, ETextCommit::Type CommitType);

	TSharedPtr<SEditableTextBox> InputBox;
	TSharedPtr<SMultiLineEditableTextBox> OutputBox;
};
