#include "JamEditorModule.h"

#include "Modules/ModuleManager.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "ToolMenus.h"
#include "IPythonScriptPlugin.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

#define LOCTEXT_NAMESPACE "JamEditor"

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
	UToolMenus::RegisterStartupCallback(
		FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FJamEditorModule::RegisterMenus));

	UE_LOG(LogTemp, Display, TEXT("[JamEditor] módulo C++ cargado — Dash Bar disponible en Tools."));
}

void FJamEditorModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);
	UToolMenus::UnregisterOwner(this);
	if (DashWindow.IsValid())
	{
		DashWindow->RequestDestroyWindow();
		DashWindow.Reset();
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
		"OpenJamDashBar",
		LOCTEXT("OpenJamDashBar", "Jam: Dash Bar"),
		LOCTEXT("OpenJamDashBarTip", "Abrir la Dash Bar de Jam (secciones + params + oráculo)"),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateRaw(this, &FJamEditorModule::OpenDashBar)));
}

void FJamEditorModule::OpenDashBar()
{
	if (DashWindow.IsValid())
	{
		DashWindow->BringToFront();
		return;
	}

	LoadSpec();

	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(LOCTEXT("DashTitle", "Jam — Dash Bar"))
		.ClientSize(FVector2D(560.0f, 440.0f))
		.AutoCenter(EAutoCenter::PreferredWorkArea)
		.SupportsMaximize(false)
		.SupportsMinimize(false);

	Win->SetContent(BuildDashContent());
	Win->SetOnWindowClosed(FOnWindowClosed::CreateRaw(this, &FJamEditorModule::OnDashClosed));

	FSlateApplication::Get().AddWindow(Win);
	DashWindow = Win;

	if (Tools.Num() > 0)
	{
		SelectTool(ActiveVerb.IsEmpty() ? Tools[0].Verb : ActiveVerb);
	}
}

void FJamEditorModule::OnDashClosed(const TSharedRef<SWindow>& /*Window*/)
{
	DashWindow.Reset();
	ParamsBox.Reset();
	CmdBox.Reset();
	OutputBox.Reset();
	ParamFields.Empty();
}

void FJamEditorModule::LoadSpec()
{
	Tools.Reset();
	const FString Raw = ExecPythonCapture(
		TEXT("import jam.tools as _t; print('JAMSPEC:' + _t.spec_json())"));

	const FString Marker(TEXT("JAMSPEC:"));
	const int32 M = Raw.Find(Marker);
	if (M == INDEX_NONE)
	{
		UE_LOG(LogTemp, Warning, TEXT("[JamEditor] no pude leer el spec de jam.tools."));
		return;
	}
	FString Json = Raw.Mid(M + Marker.Len());
	Json.TrimStartAndEndInline();

	TArray<TSharedPtr<FJsonValue>> Arr;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Arr))
	{
		UE_LOG(LogTemp, Warning, TEXT("[JamEditor] spec no parseó como JSON."));
		return;
	}

	for (const TSharedPtr<FJsonValue>& V : Arr)
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		if (!O.IsValid())
		{
			continue;
		}
		FJamTool T;
		T.Verb = O->GetStringField(TEXT("verbo"));
		O->TryGetStringField(TEXT("doc"), T.Doc);
		const TArray<TSharedPtr<FJsonValue>>* Ps = nullptr;
		if (O->TryGetArrayField(TEXT("params"), Ps) && Ps)
		{
			for (const TSharedPtr<FJsonValue>& PV : *Ps)
			{
				const TSharedPtr<FJsonObject> PO = PV->AsObject();
				if (PO.IsValid())
				{
					T.Params.Add(TPair<FString, FString>(
						PO->GetStringField(TEXT("nombre")),
						PO->GetStringField(TEXT("default"))));
				}
			}
		}
		Tools.Add(T);
	}
}

const FJamTool* FJamEditorModule::FindTool(const FString& Verb) const
{
	return Tools.FindByPredicate([&Verb](const FJamTool& T) { return T.Verb == Verb; });
}

TSharedRef<SWidget> FJamEditorModule::BuildDashContent()
{
	TSharedRef<SWrapBox> Toolbar = SNew(SWrapBox).UseAllottedSize(true);
	for (const FJamTool& T : Tools)
	{
		const FString Verb = T.Verb;
		Toolbar->AddSlot().Padding(2.0f)
		[
			SNew(SButton)
			.Text(FText::FromString(Verb))
			.ToolTipText(FText::FromString(T.Doc))
			.OnClicked_Lambda([this, Verb]() { SelectTool(Verb); return FReply::Handled(); })
		];
	}

	return SNew(SVerticalBox)

		// Barra de secciones (una por herramienta, generada desde el spec).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 6.0f, 6.0f, 2.0f)
		[
			Toolbar
		]

		// Params vivos del tool activo (se reconstruyen al elegir sección).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f)
		[
			SAssignNew(ParamsBox, SVerticalBox)
		]

		// Línea de comando (CLI) = fuente de verdad + Preview.
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 4.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.VAlign(VAlign_Center)
			[
				SAssignNew(CmdBox, SEditableTextBox)
				.HintText(LOCTEXT("CmdHint", "comando Jam — o editá los params de arriba"))
				.OnTextCommitted_Raw(this, &FJamEditorModule::OnCmdCommitted)
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("Preview", "Preview"))
				.OnClicked_Raw(this, &FJamEditorModule::OnPreviewClicked)
			]
		]

		// Acciones del preview.
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

		// Salida: veredicto del oráculo.
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
				.Text(LOCTEXT("Welcome", "Elegí una herramienta arriba, ajustá params y Preview. También podés escribir el comando directo y Enter («help»)."))
			]
		];
}

void FJamEditorModule::SelectTool(const FString& Verb)
{
	ActiveVerb = Verb;
	RebuildParams();
}

void FJamEditorModule::RebuildParams()
{
	ParamFields.Empty();
	if (!ParamsBox.IsValid())
	{
		return;
	}
	ParamsBox->ClearChildren();

	const FJamTool* T = FindTool(ActiveVerb);
	if (T == nullptr)
	{
		return;
	}

	ParamsBox->AddSlot()
		.AutoHeight()
		.Padding(0.0f, 0.0f, 0.0f, 2.0f)
		[
			SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("%s  —  %s"), *T->Verb, *T->Doc)))
		];

	for (const TPair<FString, FString>& P : T->Params)
	{
		const FString Key = P.Key;
		TSharedPtr<SEditableTextBox> Field;
		ParamsBox->AddSlot()
			.AutoHeight()
			.Padding(0.0f, 1.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.FillWidth(0.4f)
				.VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::FromString(Key))
				]
				+ SHorizontalBox::Slot()
				.FillWidth(0.6f)
				[
					SAssignNew(Field, SEditableTextBox)
					.Text(FText::FromString(P.Value))
					.OnTextChanged_Lambda([this](const FText&) { ComposeCommandFromParams(); })
				]
			];
		ParamFields.Add(Key, Field);
	}

	ComposeCommandFromParams();
}

void FJamEditorModule::ComposeCommandFromParams()
{
	if (!CmdBox.IsValid())
	{
		return;
	}
	FString Cmd = ActiveVerb;
	if (const FJamTool* T = FindTool(ActiveVerb))
	{
		for (const TPair<FString, FString>& P : T->Params)
		{
			if (const TSharedPtr<SEditableTextBox>* Field = ParamFields.Find(P.Key))
			{
				const FString Val = (*Field)->GetText().ToString().TrimStartAndEnd();
				if (!Val.IsEmpty())
				{
					Cmd += FString::Printf(TEXT(" %s=%s"), *P.Key, *Val);
				}
			}
		}
	}
	CmdBox->SetText(FText::FromString(Cmd));
}

FReply FJamEditorModule::OnPreviewClicked()
{
	if (CmdBox.IsValid())
	{
		RunCommand(CmdBox->GetText().ToString());
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

void FJamEditorModule::OnCmdCommitted(const FText& Text, ETextCommit::Type CommitType)
{
	if (CommitType == ETextCommit::OnEnter)
	{
		RunCommand(Text.ToString());
	}
}

FString FJamEditorModule::ExecPythonCapture(const FString& Statement)
{
	FString Out;
	IPythonScriptPlugin* Py = IPythonScriptPlugin::Get();
	if (Py == nullptr || !Py->IsPythonAvailable())
	{
		return TEXT("Python no está disponible en este editor.");
	}

	FPythonCommandEx Cmd;
	Cmd.ExecutionMode = EPythonCommandExecutionMode::ExecuteStatement;
	Cmd.FileExecutionScope = EPythonFileExecutionScope::Private;
	Cmd.Command = Statement;

	Py->ExecPythonCommandEx(Cmd);

	for (const FPythonLogOutputEntry& Entry : Cmd.LogOutput)
	{
		Out += Entry.Output;
	}
	Out.TrimEndInline();
	return Out;
}

void FJamEditorModule::RunCommand(const FString& Command)
{
	const FString Statement = FString::Printf(
		TEXT("import jam.panel as _p; print(_p.ejecutar_dsl(%s, None))"), *ToPyStr(Command));

	FString Out = ExecPythonCapture(Statement);
	if (Out.IsEmpty())
	{
		Out = TEXT("(sin salida)");
	}
	if (OutputBox.IsValid())
	{
		OutputBox->SetText(FText::FromString(Out));
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FJamEditorModule, JamEditor)
