#include "JamEditorModule.h"

#include "Modules/ModuleManager.h"
#include "Framework/Docking/TabManager.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SScrollBox.h"
#include "ToolMenus.h"
#include "IPythonScriptPlugin.h"

#define LOCTEXT_NAMESPACE "JamEditor"

static const FName JamTabName(TEXT("JamConsole"));

// Convierte un FString a un literal de string de Python entre comillas simples (escapando lo justo).
static FString ToPyStr(const FString& In)
{
	FString S = In;
	S.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	S.ReplaceInline(TEXT("'"), TEXT("\\'"));
	S.ReplaceInline(TEXT("\r"), TEXT(""));
	S.ReplaceInline(TEXT("\n"), TEXT("\\n"));
	return FString::Printf(TEXT("'%s'"), *S);
}

void FJamEditorModule::StartupModule()
{
	FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
			JamTabName,
			FOnSpawnTab::CreateRaw(this, &FJamEditorModule::SpawnJamTab))
		.SetDisplayName(LOCTEXT("JamTabTitle", "Consola Jam"))
		.SetTooltipText(LOCTEXT("JamTabTooltip", "Consola de Jam (DSL + oráculo determinista)"))
		.SetMenuType(ETabSpawnerMenuType::Hidden);

	UToolMenus::RegisterStartupCallback(
		FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FJamEditorModule::RegisterMenus));

	UE_LOG(LogTemp, Display, TEXT("[JamEditor] módulo C++ cargado — tab «Consola Jam» registrado."));
}

void FJamEditorModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);
	UToolMenus::UnregisterOwner(this);
	if (FSlateApplication::IsInitialized())
	{
		FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(JamTabName);
	}
}

void FJamEditorModule::RegisterMenus()
{
	FToolMenuOwnerScoped OwnerScoped(this);

	UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools");
	if (!Menu)
	{
		return;
	}
	FToolMenuSection& Section = Menu->FindOrAddSection("Jam");
	Section.AddMenuEntry(
		"OpenJamConsole",
		LOCTEXT("OpenJamConsole", "Jam: Consola (C++)"),
		LOCTEXT("OpenJamConsoleTip", "Abrir la consola Jam nativa (DSL + oráculo)"),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateRaw(this, &FJamEditorModule::OpenTab)));
}

void FJamEditorModule::OpenTab()
{
	FGlobalTabmanager::Get()->TryInvokeTab(JamTabName);
}

TSharedRef<SDockTab> FJamEditorModule::SpawnJamTab(const FSpawnTabArgs& Args)
{
	return SNew(SDockTab)
		.TabRole(ETabRole::NomadTab)
		[
			SNew(SVerticalBox)

			// Fila de comando: caja de texto (Enter ejecuta) + Run.
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(6.0f, 6.0f, 6.0f, 2.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.FillWidth(1.0f)
				.VAlign(VAlign_Center)
				[
					SAssignNew(InputBox, SEditableTextBox)
					.HintText(LOCTEXT("CmdHint", "comando Jam — ej: scatter cantidad=20 area=650 seed=7   ·   help"))
					.OnTextCommitted_Raw(this, &FJamEditorModule::OnInputCommitted)
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("Run", "Ejecutar"))
					.OnClicked_Raw(this, &FJamEditorModule::OnRunClicked)
				]
			]

			// Fila de acciones del preview.
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(6.0f, 2.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 4.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("Confirmar", "✓ Confirmar"))
					.OnClicked_Raw(this, &FJamEditorModule::OnConfirmarClicked)
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text(LOCTEXT("Descartar", "✗ Descartar"))
					.OnClicked_Raw(this, &FJamEditorModule::OnDescartarClicked)
				]
			]

			// Salida: veredicto del oráculo (solo lectura, con scroll).
			+ SVerticalBox::Slot()
			.FillHeight(1.0f)
			.Padding(6.0f, 2.0f, 6.0f, 6.0f)
			[
				SNew(SScrollBox)
				+ SScrollBox::Slot()
				[
					SAssignNew(OutputBox, SMultiLineEditableTextBox)
					.IsReadOnly(true)
					.AllowMultiLine(true)
					.Text(LOCTEXT("Welcome", "Jam — consola nativa lista. Escribí «help» y Enter."))
				]
			]
		];
}

FReply FJamEditorModule::OnRunClicked()
{
	if (InputBox.IsValid())
	{
		RunCommand(InputBox->GetText().ToString());
	}
	return FReply::Handled();
}

FReply FJamEditorModule::OnConfirmarClicked()
{
	RunCommand(TEXT("confirmar"));
	return FReply::Handled();
}

FReply FJamEditorModule::OnDescartarClicked()
{
	RunCommand(TEXT("descartar"));
	return FReply::Handled();
}

void FJamEditorModule::OnInputCommitted(const FText& Text, ETextCommit::Type CommitType)
{
	if (CommitType == ETextCommit::OnEnter)
	{
		RunCommand(Text.ToString());
	}
}

void FJamEditorModule::RunCommand(const FString& Command)
{
	FString Out;
	IPythonScriptPlugin* Py = IPythonScriptPlugin::Get();
	if (Py == nullptr || !Py->IsPythonAvailable())
	{
		Out = TEXT("Python no está disponible en este editor.");
	}
	else
	{
		FPythonCommandEx Cmd;
		Cmd.ExecutionMode = EPythonCommandExecutionMode::ExecuteStatement;
		Cmd.FileExecutionScope = EPythonFileExecutionScope::Private;
		Cmd.Command = FString::Printf(
			TEXT("import jam.panel as _p; print(_p.ejecutar_dsl(%s, None))"), *ToPyStr(Command));

		Py->ExecPythonCommandEx(Cmd);

		for (const FPythonLogOutputEntry& Entry : Cmd.LogOutput)
		{
			Out += Entry.Output;
		}
		Out.TrimEndInline();
		if (Out.IsEmpty())
		{
			Out = Cmd.CommandResult.IsEmpty() ? TEXT("(sin salida)") : Cmd.CommandResult;
		}
	}

	if (OutputBox.IsValid())
	{
		OutputBox->SetText(FText::FromString(Out));
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FJamEditorModule, JamEditor)
