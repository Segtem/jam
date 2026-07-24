#include "JamEditorModule.h"
#include "SJamGraphEditor.h"

#include "Modules/ModuleManager.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SSpinBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "ToolMenus.h"
#include "IPythonScriptPlugin.h"
#include "AssetThumbnail.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "AssetRegistry/AssetData.h"
#include "UObject/SoftObjectPath.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/PlatformProcess.h"
#include "LevelEditorViewport.h"
#include "Editor.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"

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
	for (TSharedPtr<SWindow>* W : { &DashWindow, &GraphWindow, &ContentWindow })
	{
		if (W->IsValid())
		{
			(*W)->RequestDestroyWindow();
			W->Reset();
		}
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
	Section.AddMenuEntry(
		"OpenJamContent",
		LOCTEXT("OpenJamContent", "Jam: Content"),
		LOCTEXT("OpenJamContentTip", "Navegador de assets con miniaturas (ventana propia)"),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateRaw(this, &FJamEditorModule::OpenContentWindow)));
	Section.AddMenuEntry(
		"OpenJamGraph",
		LOCTEXT("OpenJamGraph", "Jam: Graph (Grasshopper)"),
		LOCTEXT("OpenJamGraphTip", "Editor de nodos: cada nodo es un comando; correr = orden topológico + oráculo"),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateRaw(this, &FJamEditorModule::OpenGraph)));
	Section.AddMenuEntry(
		"OpenJamWeb",
		LOCTEXT("OpenJamWeb", "Jam: abrir web"),
		LOCTEXT("OpenJamWebTip", "Arranca el server web de Jam y lo abre en el navegador (http://127.0.0.1:8790)"),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateRaw(this, &FJamEditorModule::OpenWebUI)));
}

void FJamEditorModule::OpenWebUI()
{
	// Arranca el server HTTP dentro del editor (idempotente) y abre el navegador por defecto.
	ExecPythonCapture(TEXT("import jam.web; jam.web.iniciar()"));
	FPlatformProcess::LaunchURL(TEXT("http://127.0.0.1:8790"), nullptr, nullptr);
}

void FJamEditorModule::OpenGraph()
{
	if (GraphWindow.IsValid())
	{
		GraphWindow->BringToFront();
		return;
	}
	LoadSpec(/*bIncludeFlow*/ true);

	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(LOCTEXT("GraphTitle", "Jam — Graph (Grasshopper)"))
		.ClientSize(FVector2D(780.0f, 560.0f))
		.AutoCenter(EAutoCenter::PreferredWorkArea);

	Win->SetContent(
		SNew(SJamGraphEditor, Tools)
		.OnRunGraph_Raw(this, &FJamEditorModule::RunGraphJson)
		.ActiveAsset_Lambda([this]() { return SelectedAssetName; })
		.OnOpenContent_Raw(this, &FJamEditorModule::OpenContentWindow)
		.OnSaveGraph_Raw(this, &FJamEditorModule::SaveGraphAsPreset));
	Win->SetOnWindowClosed(FOnWindowClosed::CreateLambda(
		[this](const TSharedRef<SWindow>&) { GraphWindow.Reset(); }));

	FSlateApplication::Get().AddWindow(Win);
	GraphWindow = Win;
}

FString FJamEditorModule::SaveGraphAsPreset(const FString& Json)
{
	const FString Nombre = FString::Printf(TEXT("Compound %s"), *FDateTime::Now().ToString(TEXT("%H%M%S")));
	const FString Stmt = FString::Printf(
		TEXT("import jam.api as _a; print(_a.preset_save_graph(%s, %s))"),
		*ToPyStr(Nombre), *ToPyStr(Json));
	const FString Out = ExecPythonCapture(Stmt);
	UE_LOG(LogTemp, Display, TEXT("[JamEditor] %s"), *Out);
	return Out;
}

FString FJamEditorModule::RunGraphJson(const FString& Json)
{
	// `run_graph_json` devuelve {report, nodes:{nid:{estado,texto}}} para que el canvas pinte cada
	// nodo con el veredicto de SU oráculo.
	const FString Stmt = FString::Printf(
		TEXT("import jam.api as _a; print(_a.run_graph_json(%s))"), *ToPyStr(Json));
	return ExecPythonCapture(Stmt);
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

	// Refresco del punto de mira a 20 Hz, todo en C++ (los campos x/y/z en vivo no pagan Python).
	Win->RegisterActiveTimer(0.05f, FWidgetActiveTimerDelegate::CreateLambda(
		[this](double, float) -> EActiveTimerReturnType
		{
			if (!DashWindow.IsValid())
			{
				return EActiveTimerReturnType::Stop;
			}
			const bool bLive = IsLiveAim();
			if (bLive)
			{
				FVector P;
				if (ComputeAimPoint(P))
				{
					LiveAim = P;
				}
			}
			else if (bWasLiveAim)
			{
				// se soltó el modo vivo: dejar la última posición cargada para retocarla a mano
				FreezeAimIntoParams();
			}
			bWasLiveAim = bLive;
			return EActiveTimerReturnType::Continue;
		}));

	if (Tools.Num() > 0)
	{
		// Arrancar en una herramienta VISIBLE del ribbon: el 1º del registro es `asset`, que vive en la
		// ventana de Content y no tiene tab propia → se abría en un verbo que no se ve en ninguna tab.
		FString Inicial = ActiveVerb;
		if (Inicial.IsEmpty())
		{
			Inicial = (FindTool(TEXT("place")) != nullptr) ? TEXT("place") : Tools[0].Verb;
		}
		SelectTool(Inicial);
	}
}

void FJamEditorModule::OnDashClosed(const TSharedRef<SWindow>& /*Window*/)
{
	DashWindow.Reset();
	ParamsBox.Reset();
	CmdBox.Reset();
	OutputBox.Reset();
	ParamFields.Empty();
	AssetLabel.Reset();
	LogText.Empty();
}

void FJamEditorModule::LoadSpec(bool bIncludeFlow)
{
	Tools.Reset();
	Categories.Reset();
	// El canvas del grafo pide el spec COMBINADO (verbos + ops de flow); la Dash Bar sólo los verbos.
	const TCHAR* Fn = bIncludeFlow ? TEXT("spec_all") : TEXT("spec");
	const FString Raw = ExecPythonCapture(
		FString::Printf(TEXT("import jam.api as _a; print('JAMSPEC:' + _a.%s())"), Fn));

	const FString Marker(TEXT("JAMSPEC:"));
	const int32 M = Raw.Find(Marker);
	if (M == INDEX_NONE)
	{
		UE_LOG(LogTemp, Warning, TEXT("[JamEditor] no pude leer el spec de jam.tools."));
		return;
	}
	FString Json = Raw.Mid(M + Marker.Len());
	Json.TrimStartAndEndInline();

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("[JamEditor] spec no parseó como JSON."));
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Cats = nullptr;
	if (Root->TryGetArrayField(TEXT("categorias"), Cats) && Cats)
	{
		for (const TSharedPtr<FJsonValue>& CV : *Cats)
		{
			Categories.Add(CV->AsString());
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* Ts = nullptr;
	if (!Root->TryGetArrayField(TEXT("tools"), Ts) || !Ts)
	{
		return;
	}
	for (const TSharedPtr<FJsonValue>& V : *Ts)
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		if (!O.IsValid())
		{
			continue;
		}
		FJamTool T;
		T.Verb = O->GetStringField(TEXT("verbo"));
		O->TryGetStringField(TEXT("cat"), T.Cat);
		O->TryGetStringField(TEXT("doc"), T.Doc);
		O->TryGetBoolField(TEXT("source"), T.bSource);
		O->TryGetBoolField(TEXT("asset_pin"), T.bAssetPin);
		O->TryGetStringField(TEXT("out_name"), T.OutName);
		const TArray<TSharedPtr<FJsonValue>>* Ps = nullptr;
		if (O->TryGetArrayField(TEXT("params"), Ps) && Ps)
		{
			for (const TSharedPtr<FJsonValue>& PV : *Ps)
			{
				const TSharedPtr<FJsonObject> PO = PV->AsObject();
				if (PO.IsValid())
				{
					FJamParam P;
					P.Name = PO->GetStringField(TEXT("nombre"));
					P.Default = PO->GetStringField(TEXT("default"));
					if (!PO->TryGetStringField(TEXT("tipo"), P.Type))
					{
						P.Type = TEXT("str");
					}
					const TArray<TSharedPtr<FJsonValue>>* Opts = nullptr;
					if (PO->TryGetArrayField(TEXT("opciones"), Opts) && Opts)
					{
						for (const TSharedPtr<FJsonValue>& OV : *Opts)
						{
							P.Options.Add(MakeShared<FString>(OV->AsString()));
						}
					}
					T.Params.Add(P);
				}
			}
		}
		Tools.Add(T);
	}
}

bool FJamEditorModule::CategoryHasTools(const FString& Category) const
{
	return Tools.ContainsByPredicate([&Category](const FJamTool& T) { return T.Cat == Category; });
}

TSharedRef<SWidget> FJamEditorModule::MakeCategoryMenu(const FString& Category)
{
	FMenuBuilder MenuBuilder(/*bShouldCloseWindowAfterMenuSelection*/ true, nullptr);
	for (const FJamTool& T : Tools)
	{
		if (T.Cat != Category)
		{
			continue;
		}
		const FString Verb = T.Verb;
		MenuBuilder.AddMenuEntry(
			FText::FromString(T.Verb),
			FText::FromString(T.Doc),
			FSlateIcon(),
			FUIAction(FExecuteAction::CreateLambda([this, Verb]() { SelectTool(Verb); })));
	}
	return MenuBuilder.MakeWidget();
}

const FJamTool* FJamEditorModule::FindTool(const FString& Verb) const
{
	return Tools.FindByPredicate([&Verb](const FJamTool& T) { return T.Verb == Verb; });
}

TSharedRef<SWidget> FJamEditorModule::BuildDashContent()
{
	// Barra horizontal estilo Dash: un combo por categoría (Content/Place/Scatter/Create/Edit)
	// + un buscador «Find Tools». Las categorías vacías se saltan.
	TSharedRef<SHorizontalBox> Bar = SNew(SHorizontalBox);

	// Content: abre el navegador de assets en SU PROPIA VENTANA (los paneles de Dash son ventanas
	// aparte; embebido acá le comía la mitad de la Dash Bar).
	Bar->AddSlot()
		.AutoWidth()
		.Padding(2.0f, 0.0f)
		[
			SNew(SButton)
			.Text(LOCTEXT("Content", "Content"))
			.ToolTipText(LOCTEXT("ContentTip", "Navegador de assets con miniaturas (ventana aparte)"))
			.OnClicked_Lambda([this]() { OpenContentWindow(); return FReply::Handled(); })
		];

	// Puente con el flujo normal del editor: usar lo que esté marcado en el Content Browser de UE.
	Bar->AddSlot()
		.AutoWidth()
		.Padding(2.0f, 0.0f)
		[
			SNew(SButton)
			.Text(LOCTEXT("PickUE", "◧ Selección de UE"))
			.ToolTipText(LOCTEXT("PickUETip",
				"Usar la malla seleccionada en el Content Browser de Unreal como asset activo"))
			.OnClicked_Lambda([this]() { PickFromUnrealSelection(); return FReply::Handled(); })
		];

	Bar->AddSlot()
		.FillWidth(1.0f)
		.Padding(8.0f, 0.0f, 0.0f, 0.0f)
		.VAlign(VAlign_Center)
		[
			SAssignNew(SearchBox, SEditableTextBox)
			.HintText(LOCTEXT("FindTools", "Find Tools…"))
			.OnTextCommitted_Lambda([this](const FText& Text, ETextCommit::Type Type)
			{
				if (Type == ETextCommit::OnEnter)
				{
					FindAndSelectTool(Text.ToString());
				}
			})
		];

	// Ribbon estilo Grasshopper (mismo look que el Graph): fila de TABS por categoría; el tab activo se
	// pinta con su tono. Content queda como botón propio (browser), no como tab de verbos.
	if (ActiveDashTab.IsEmpty())
	{
		for (const FString& Cat : Categories)
		{
			if (Cat != TEXT("Content") && CategoryHasTools(Cat)) { ActiveDashTab = Cat; break; }
		}
	}
	TSharedRef<SHorizontalBox> TabStrip = SNew(SHorizontalBox);
	for (const FString& Cat : Categories)
	{
		if (Cat == TEXT("Content") || !CategoryHasTools(Cat))
		{
			continue;
		}
		TabStrip->AddSlot().AutoWidth().Padding(1.0f, 0.0f)
		[
			SNew(SButton)
			.ToolTipText(FText::FromString(FString::Printf(TEXT("Tab «%s»"), *Cat)))
			.ButtonColorAndOpacity_Lambda([this, Cat]()
			{
				return ActiveDashTab == Cat ? SJamGraphEditor::CategoryColor(Cat)
				                            : FLinearColor(0.22f, 0.22f, 0.24f, 1.0f);
			})
			.OnClicked_Lambda([this, Cat]() { ActiveDashTab = Cat; RebuildDashTabContent(); return FReply::Handled(); })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[ SJamGraphEditor::MakeBadge(SJamGraphEditor::CategoryColor(Cat), Cat.Left(2).ToUpper(), 14.0f) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f, 2.0f, 0.0f)
				[ SNew(STextBlock).Text(FText::FromString(Cat)) ]
			]
		];
	}

	TSharedRef<SWidget> Content = SNew(SVerticalBox)

		// Fila utilitaria: Content · Selección UE · Find Tools.
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 6.0f, 6.0f, 2.0f)
		[
			Bar
		]

		// Ribbon: fila de TABS (categorías).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 0.0f, 6.0f, 0.0f)
		[
			SNew(SScrollBox).Orientation(Orient_Horizontal)
			+ SScrollBox::Slot()[ TabStrip ]
		]

		// Ribbon: fichas con icono de la categoría activa (SelectTool activa el verbo → panel de params).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f, 6.0f, 4.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Header"))
			.Padding(2.0f)
			[
				SNew(SScrollBox).Orientation(Orient_Horizontal)
				+ SScrollBox::Slot()[ SAssignNew(DashTabContent, SHorizontalBox) ]
			]
		]

		// Asset activo: miniatura GRANDE + nombre (lo elegido alimenta todas las herramientas), y el
		// interruptor del gizmo que marca dónde está parado Jam en el viewport.
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 6.0f, 0.0f)
			[
				SNew(SBox).WidthOverride(48.0f).HeightOverride(48.0f)
				[
					SAssignNew(ActiveThumbBox, SBox)
				]
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.VAlign(VAlign_Center)
			[
				SAssignNew(AssetLabel, STextBlock)
				.Text(LOCTEXT("NoAsset", "Asset: (elegí uno en Content)"))
				.AutoWrapText(true)
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("Ghost", "👻 Fantasma"))
				.ToolTipText(LOCTEXT("GhostTip",
					"Muestra la malla que se va a colocar siguiendo el punto de mira (sin colisión, fuera del oráculo)"))
				.OnClicked_Lambda([this]()
				{
					bGhostOn = !bGhostOn;
					RunCommand(bGhostOn ? TEXT("ghost on=true") : TEXT("ghost on=false"));
					PushGhostTarget();   // que el gris nazca en los valores actuales
					return FReply::Handled();
				})
				.ButtonColorAndOpacity_Lambda([this]()
				{
					return bGhostOn ? FLinearColor(0.75f, 0.45f, 1.0f, 1.0f)
					                : FLinearColor(0.09f, 0.09f, 0.1f, 1.0f);
				})
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(SButton)
				.Text(LOCTEXT("Gizmo", "◎ Gizmo"))
				.ToolTipText(LOCTEXT("GizmoTip",
					"Marca en el viewport dónde está parado Jam (el punto de mira donde coloca) y la huella del asset activo"))
				.OnClicked_Lambda([this]()
				{
					bGizmoOn = !bGizmoOn;
					RunCommand(bGizmoOn ? TEXT("gizmo on=true") : TEXT("gizmo on=false"));
					return FReply::Handled();
				})
				.ButtonColorAndOpacity_Lambda([this]()
				{
					return bGizmoOn ? FLinearColor(0.0f, 0.75f, 0.85f, 1.0f)
					                : FLinearColor(0.09f, 0.09f, 0.1f, 1.0f);
				})
			]
		]

		// Presets: aplicar uno (combo) o guardar el comando actual como preset. Como en Dash.
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(SComboButton)
				.ButtonContent()[ SNew(STextBlock).Text(LOCTEXT("Presets", "★ Presets")) ]
				.OnGetMenuContent_Raw(this, &FJamEditorModule::MakePresetMenu)
			]
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(SButton)
				.Text(LOCTEXT("SavePreset", "★ Guardar preset"))
				.ToolTipText(LOCTEXT("SavePresetTip", "Guarda el comando actual como preset local reusable"))
				.OnClicked_Raw(this, &FJamEditorModule::OnSavePresetClicked)
			]
		]

		// Params vivos del tool activo (se reconstruyen al elegir sección).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f)
		[
			SAssignNew(ParamsBox, SVerticalBox)
		]

		// OUTPUT LOG (estilo Rhino): historia acumulativa de comandos + veredictos. Ocupa el grueso.
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		.Padding(6.0f, 2.0f)
		[
			SAssignNew(OutputBox, SMultiLineEditableTextBox)
			.IsReadOnly(true)
			.AllowMultiLine(true)
			.Text(LOCTEXT("Welcome", "Jam — todo es un comando. Elegí una herramienta y Enter, o escribí «help» abajo."))
		]

		// Acciones del preview (también son comandos: se loguean como «> confirm/discard»).
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
				.Text(LOCTEXT("Confirmar", "✓ Confirmar / Colocar"))
				.ToolTipText(LOCTEXT("ConfirmarTip",
					"Fija la preview activa; si no hay ninguna, ejecuta el comando de la línea y lo coloca (con el gizmo encendido: coloca donde apunta)"))
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

		// BARRA DE COMANDOS ABAJO (estilo Rhino: «Command:» + input, Enter ejecuta).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f, 6.0f, 6.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(0.0f, 0.0f, 6.0f, 0.0f)
			[
				SNew(STextBlock).Text(LOCTEXT("CommandPrompt", "Command:"))
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.VAlign(VAlign_Center)
			[
				SAssignNew(CmdBox, SEditableTextBox)
				.HintText(LOCTEXT("CmdHint", "escribí un comando (o elegí una herramienta arriba) y Enter · ↑↓ historial"))
				.OnTextCommitted_Raw(this, &FJamEditorModule::OnCmdCommitted)
				// ↑/↓ recorren el historial, como la línea de comando de Rhino.
				.OnKeyDownHandler_Lambda([this](const FGeometry&, const FKeyEvent& Key)
				{
					if (Key.GetKey() == EKeys::Up)   { RecallHistory(-1); return FReply::Handled(); }
					if (Key.GetKey() == EKeys::Down) { RecallHistory(+1); return FReply::Handled(); }
					return FReply::Unhandled();
				})
			]
		];

	RebuildDashTabContent();   // llena el tab activo con sus fichas
	return Content;
}

void FJamEditorModule::RebuildDashTabContent()
{
	if (!DashTabContent.IsValid())
	{
		return;
	}
	DashTabContent->ClearChildren();
	for (const FJamTool& T : Tools)
	{
		if (T.Cat != ActiveDashTab)
		{
			continue;
		}
		const FString Verb = T.Verb;
		const FLinearColor Color = SJamGraphEditor::CategoryColor(T.Cat);
		DashTabContent->AddSlot().AutoWidth().Padding(3.0f, 2.0f)
		[
			SNew(SButton)
			.ToolTipText(FText::FromString(FString::Printf(TEXT("%s — %s"), *T.Verb, *T.Doc)))
			.ContentPadding(FMargin(3.0f, 3.0f))
			// el verbo activo se resalta (como el tool seleccionado en Dash)
			.ButtonColorAndOpacity_Lambda([this, Verb]()
			{
				return ActiveVerb == Verb ? FLinearColor(0.30f, 0.55f, 0.85f, 1.0f) : FLinearColor::White;
			})
			.OnClicked_Lambda([this, Verb]() { SelectTool(Verb); return FReply::Handled(); })
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
				[ SJamGraphEditor::MakeBadge(Color, SJamGraphEditor::VerbCode(Verb), 30.0f) ]
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 2.0f, 0.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text(FText::FromString(Verb))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				]
			]
		];
	}
}

bool FJamEditorModule::ComputeAimPoint(FVector& Out) const
{
	// Mismo punto que calcula `jam.ue.punto_de_mira()`, pero en C++: se refresca a 20 Hz para los
	// campos en vivo sin pagar una llamada a Python (ni ensuciar el Output Log) por frame.
	FEditorViewportClient* VC = GCurrentLevelEditingViewportClient;
	if (VC == nullptr || GEditor == nullptr)
	{
		return false;
	}
	UWorld* World = GEditor->GetEditorWorldContext().World();
	if (World == nullptr)
	{
		return false;
	}
	const FVector Start = VC->GetViewLocation();
	const FVector Dir = VC->GetViewRotation().Vector();
	const FVector End = Start + Dir * 100000.0;

	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(JamAim), /*bTraceComplex*/ true);
	if (World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
	{
		Out = Hit.ImpactPoint;
	}
	else
	{
		Out = Start + Dir * 1000.0;   // sin superficie: 10 m adelante, igual que en Python
	}
	return true;
}

void FJamEditorModule::PushGhostTarget()
{
	// El fantasma GRIS vive en los valores de los campos: cada vez que cambian, se lo avisamos.
	// Sólo mientras esté encendido (si no, sería una llamada a Python al cuete por cada tecla).
	if (!bGhostOn)
	{
		return;
	}
	const float X = ParamValues.Contains(TEXT("x")) ? ParamValues[TEXT("x")] : 0.0f;
	const float Y = ParamValues.Contains(TEXT("y")) ? ParamValues[TEXT("y")] : 0.0f;
	const float Z = ParamValues.Contains(TEXT("z")) ? ParamValues[TEXT("z")] : 0.0f;

	bool bView = false;
	if (const TSharedPtr<SCheckBox>* V = ParamChecks.Find(TEXT("view")))
	{
		bView = (*V)->IsChecked();
	}
	FString Anchor(TEXT("base"));
	if (const FString* A = ParamChoice.Find(TEXT("anchor")))
	{
		if (!A->IsEmpty())
		{
			Anchor = *A;
		}
	}

	ExecPythonCapture(FString::Printf(
		TEXT("import jam.api as _a; _a.ghost_target(%f, %f, %f, %s, '%s')"),
		X, Y, Z, bView ? TEXT("True") : TEXT("False"), *Anchor));
}

void FJamEditorModule::FreezeAimIntoParams()
{
	if (!ParamSpins.Contains(TEXT("x")))
	{
		return;   // la herramienta activa no tiene ejes (no hay nada que congelar)
	}
	ParamValues.Add(TEXT("x"), static_cast<float>(LiveAim.X));
	ParamValues.Add(TEXT("y"), static_cast<float>(LiveAim.Y));
	ParamValues.Add(TEXT("z"), static_cast<float>(LiveAim.Z));

	// x/y/z ahora son ABSOLUTAS: con `view` tildado el tool las tomaría como offset y sumaría dos
	// veces el punto de mira, así que se destilda.
	if (const TSharedPtr<SCheckBox>* View = ParamChecks.Find(TEXT("view")))
	{
		if ((*View)->IsChecked())
		{
			(*View)->SetIsChecked(ECheckBoxState::Unchecked);
		}
	}
	ComposeCommandFromParams();
}

bool FJamEditorModule::IsLiveAim() const
{
	if (!bGizmoOn)
	{
		return false;
	}
	const TSharedPtr<SCheckBox>* View = ParamChecks.Find(TEXT("view"));
	return View != nullptr && (*View)->IsChecked();
}

void FJamEditorModule::SelectTool(const FString& Verb)
{
	ActiveVerb = Verb;
	// El ribbon SIGUE al verbo activo: si el verbo vive en otra tab (p.ej. lo eligió «Find Tools»),
	// se abre esa tab. Si no, quedaba resaltada una tab que NO contiene la herramienta en uso.
	if (const FJamTool* T = FindTool(Verb))
	{
		if (!T->Cat.IsEmpty() && T->Cat != TEXT("Content"))
		{
			ActiveDashTab = T->Cat;
		}
	}
	RebuildDashTabContent();
	RebuildParams();
}

void FJamEditorModule::FindAndSelectTool(const FString& Query)
{
	const FString Q = Query.TrimStartAndEnd();
	if (Q.IsEmpty())
	{
		return;
	}
	// coincide por verbo o por doc (case-insensitive), como el «Find Tools» de Dash.
	const FJamTool* Hit = Tools.FindByPredicate([&Q](const FJamTool& T)
	{
		return T.Verb.Contains(Q) || T.Doc.Contains(Q);
	});
	if (Hit)
	{
		SelectTool(Hit->Verb);
	}
	else if (OutputBox.IsValid())
	{
		OutputBox->SetText(FText::FromString(FString::Printf(TEXT("sin herramienta para «%s»."), *Q)));
	}
}

void FJamEditorModule::OpenContentWindow()
{
	if (ContentWindow.IsValid())
	{
		ContentWindow->BringToFront();
		return;
	}
	if (!ThumbnailPool.IsValid())
	{
		ThumbnailPool = MakeShareable(new FAssetThumbnailPool(256));
	}

	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(LOCTEXT("ContentTitle", "Jam — Content"))
		.ClientSize(FVector2D(820.0f, 620.0f))
		.AutoCenter(EAutoCenter::PreferredWorkArea);

	Win->SetContent(BuildContentBrowser());
	Win->SetOnWindowClosed(FOnWindowClosed::CreateRaw(this, &FJamEditorModule::OnContentClosed));

	FSlateApplication::Get().AddWindow(Win);
	ContentWindow = Win;

	PopulateContent(FString());
}

void FJamEditorModule::OnContentClosed(const TSharedRef<SWindow>& /*Window*/)
{
	ContentWindow.Reset();
	ContentGrid.Reset();
	ContentFolderList.Reset();
	ContentSearchBox.Reset();
	ContentCountLabel.Reset();
	ThumbnailsKeepAlive.Reset();
}

TSharedRef<SWidget> FJamEditorModule::BuildContentBrowser()
{
	return SNew(SVerticalBox)

		// Buscador + conteo real (total vs mostrados: nunca más "parece que faltan mallas").
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 6.0f, 6.0f, 4.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SAssignNew(ContentSearchBox, SEditableTextBox)
				.HintText(LOCTEXT("SearchAssets", "buscar mallas…  (Enter)"))
				.OnTextCommitted_Lambda([this](const FText& Text, ETextCommit::Type Type)
				{
					if (Type == ETextCommit::OnEnter)
					{
						ContentLimit = 200;   // buscar arranca de nuevo el paginado
						PopulateContent(Text.ToString());
					}
				})
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(6.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("PickUE2", "◧ Selección de UE"))
				.ToolTipText(LOCTEXT("PickUETip2",
					"Usar la malla marcada en el Content Browser de Unreal (sin buscarla de nuevo acá)"))
				.OnClicked_Lambda([this]() { PickFromUnrealSelection(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(8.0f, 0.0f, 0.0f, 0.0f)
			[
				SAssignNew(ContentCountLabel, STextBlock)
				.Text(LOCTEXT("Loading", "cargando…"))
			]
		]

		// Carpetas (izq, el "árbol" del pack) + grilla de miniaturas (der).
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		.Padding(6.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SBox)
				.WidthOverride(200.0f)
				[
					SNew(SScrollBox)
					+ SScrollBox::Slot()
					[
						SAssignNew(ContentFolderList, SVerticalBox)
					]
				]
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.Padding(6.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SScrollBox)
				+ SScrollBox::Slot()
				[
					SAssignNew(ContentGrid, SWrapBox).UseAllottedSize(true)
				]
			]
		]

		// Paginado: el resto de las mallas está a un clic (no escondidas por un límite mudo).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f, 6.0f, 6.0f)
		[
			SNew(SButton)
			.Text(LOCTEXT("MasAssets", "▼ mostrar más (+200)"))
			.Visibility_Lambda([this]()
			{
				return ContentTotal > ContentLimit ? EVisibility::Visible : EVisibility::Collapsed;
			})
			.OnClicked_Lambda([this]()
			{
				ContentLimit += 200;
				RefreshContent();
				return FReply::Handled();
			})
		];
}

void FJamEditorModule::ShowActiveThumbnail(const FString& Path)
{
	if (!ActiveThumbBox.IsValid() || Path.IsEmpty())
	{
		return;
	}
	if (!ThumbnailPool.IsValid())
	{
		ThumbnailPool = MakeShareable(new FAssetThumbnailPool(256));
	}
	FAssetRegistryModule& ARM = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	const FAssetData Data = ARM.Get().GetAssetByObjectPath(FSoftObjectPath(Path));
	if (!Data.IsValid())
	{
		return;
	}
	ActiveThumb = MakeShareable(new FAssetThumbnail(Data, 48, 48, ThumbnailPool));
	FAssetThumbnailConfig Cfg;
	Cfg.bAllowFadeIn = true;
	ActiveThumbBox->SetContent(ActiveThumb->MakeThumbnailWidget(Cfg));
}

TSharedRef<SWidget> FJamEditorModule::MakePresetMenu()
{
	FMenuBuilder MB(true, nullptr);
	// leer la lista de presets (JSON) y armar una entrada por cada uno; aplicar corre por preview.
	const FString Raw = ExecPythonCapture(
		TEXT("import jam.api as _a; print('JAMPRE:' + _a.presets())"));
	const int32 M = Raw.Find(TEXT("JAMPRE:"));
	if (M != INDEX_NONE)
	{
		FString Json = Raw.Mid(M + 7);
		Json.TrimStartAndEndInline();
		TArray<TSharedPtr<FJsonValue>> Arr;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (FJsonSerializer::Deserialize(Reader, Arr))
		{
			for (const TSharedPtr<FJsonValue>& V : Arr)
			{
				const TSharedPtr<FJsonObject> O = V->AsObject();
				if (!O.IsValid())
				{
					continue;
				}
				const FString Nombre = O->GetStringField(TEXT("nombre"));
				FString Kind = TEXT("tool");
				O->TryGetStringField(TEXT("kind"), Kind);
				FString Desc;
				O->TryGetStringField(TEXT("descripcion"), Desc);
				const FString Etiqueta = FString::Printf(TEXT("%s  [%s]"), *Nombre, *Kind);
				MB.AddMenuEntry(FText::FromString(Etiqueta), FText::FromString(Desc), FSlateIcon(),
					FUIAction(FExecuteAction::CreateLambda([this, Nombre]()
					{
						RunCommand(FString::Printf(TEXT("preset %s"), *Nombre));
					})));
			}
		}
	}
	return MB.MakeWidget();
}

FReply FJamEditorModule::OnSavePresetClicked()
{
	const FString Cmd = CmdBox.IsValid() ? CmdBox->GetText().ToString().TrimStartAndEnd() : FString();
	if (Cmd.IsEmpty())
	{
		AppendLog(FString(), TEXT("no hay comando para guardar como preset."));
		return FReply::Handled();
	}
	// nombre autogenerado a partir del verbo + timestamp; el usuario lo renombra editando el JSON.
	const FString Nombre = FString::Printf(TEXT("Preset %s"), *FDateTime::Now().ToString(TEXT("%H%M%S")));
	const FString Stmt = FString::Printf(
		TEXT("import jam.api as _a; print(_a.preset_save_command(%s, %s))"),
		*ToPyStr(Nombre), *ToPyStr(Cmd));
	AppendLog(TEXT("save preset"), ExecPythonCapture(Stmt));
	return FReply::Handled();
}

void FJamEditorModule::PickFromUnrealSelection()
{
	// El verbo `pick` lee la selección del Content Browser de Unreal y fija el asset activo en el
	// cerebro. La UI sólo refleja lo que el cerebro ya decidió.
	const FString Out = ExecPythonCapture(
		TEXT("import jam.api as _a; print(_a.run('pick'))"));
	AppendLog(TEXT("pick"), Out);

	// leer de vuelta el activo (nombre|ruta) para el rótulo, la miniatura y el comando compuesto
	const FString Raw = ExecPythonCapture(
		TEXT("import jam.session as _s; print('JAMSEL:' + (_s.nombre() or '') + '|' + (_s.asset() or ''))"));
	const FString Marker(TEXT("JAMSEL:"));
	const int32 M = Raw.Find(Marker);
	if (M == INDEX_NONE)
	{
		return;
	}
	FString Payload = Raw.Mid(M + Marker.Len());
	Payload.TrimStartAndEndInline();
	FString Name, Path;
	if (!Payload.Split(TEXT("|"), &Name, &Path) || Name.IsEmpty())
	{
		return;
	}
	SelectedAssetName = Name;
	SelectedAssetPath = Path;
	if (AssetLabel.IsValid())
	{
		AssetLabel->SetText(FText::FromString(
			FString::Printf(TEXT("Asset: %s  (selección de Unreal)"), *Name)));
	}
	ShowActiveThumbnail(Path);
	ComposeCommandFromParams();
}

void FJamEditorModule::RefreshContent()
{
	PopulateContent(ContentSearchBox.IsValid() ? ContentSearchBox->GetText().ToString() : FString());
}

void FJamEditorModule::PopulateContent(const FString& Query)
{
	if (!ContentGrid.IsValid())
	{
		return;
	}
	ContentGrid->ClearChildren();
	ThumbnailsKeepAlive.Reset();

	const FString Stmt = FString::Printf(
		TEXT("import jam.api as _a; print('JAMASSETS:' + _a.assets(%s, %d, %s))"),
		*ToPyStr(Query), ContentLimit, *ToPyStr(ContentFolder));
	const FString Raw = ExecPythonCapture(Stmt);

	const FString Marker(TEXT("JAMASSETS:"));
	const int32 M = Raw.Find(Marker);
	if (M == INDEX_NONE)
	{
		return;
	}
	FString Json = Raw.Mid(M + Marker.Len());
	Json.TrimStartAndEndInline();

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return;
	}
	ContentTotal = static_cast<int32>(Root->GetNumberField(TEXT("total")));
	ContentAll = static_cast<int32>(Root->GetNumberField(TEXT("all")));

	// carpetas (el árbol se rearma con los conteos frescos)
	ContentFolders.Reset();
	const TArray<TSharedPtr<FJsonValue>>* Fs = nullptr;
	if (Root->TryGetArrayField(TEXT("folders"), Fs) && Fs)
	{
		for (const TSharedPtr<FJsonValue>& FV : *Fs)
		{
			const TSharedPtr<FJsonObject> FO = FV->AsObject();
			if (!FO.IsValid())
			{
				continue;
			}
			FJamFolder F;
			F.Path = FO->GetStringField(TEXT("ruta"));
			F.Name = FO->GetStringField(TEXT("nombre"));
			F.Count = static_cast<int32>(FO->GetNumberField(TEXT("count")));
			ContentFolders.Add(F);
		}
	}
	RebuildFolderList();

	const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
	if (Root->TryGetArrayField(TEXT("assets"), Arr) && Arr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Arr)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			if (!O.IsValid())
			{
				continue;
			}
			ContentGrid->AddSlot().Padding(4.0f)
			[
				MakeAssetTile(O->GetStringField(TEXT("nombre")), O->GetStringField(TEXT("ruta")))
			];
		}
	}

	if (ContentCountLabel.IsValid())
	{
		const int32 Shown = FMath::Min(ContentTotal, ContentLimit);
		const FString Filtro = ContentFolder.IsEmpty() ? TEXT("todo") : ContentFolder;
		ContentCountLabel->SetText(FText::FromString(FString::Printf(
			TEXT("%d de %d  ·  %d mallas en el proyecto  ·  %s"),
			Shown, ContentTotal, ContentAll, *Filtro)));
	}
}

void FJamEditorModule::RebuildFolderList()
{
	if (!ContentFolderList.IsValid())
	{
		return;
	}
	ContentFolderList->ClearChildren();

	auto AddFolderButton = [this](const FString& Path, const FString& Label, int32 Count)
	{
		ContentFolderList->AddSlot()
			.AutoHeight()
			.Padding(0.0f, 1.0f)
			[
				SNew(SButton)
				.HAlign(HAlign_Left)
				.Text(FText::FromString(FString::Printf(TEXT("%s  (%d)"), *Label, Count)))
				.ToolTipText(FText::FromString(Path.IsEmpty() ? TEXT("/Game") : Path))
				// alto contraste sobre la carpeta activa (misma regla que las miniaturas)
				.ButtonColorAndOpacity_Lambda([this, Path]()
				{
					return ContentFolder == Path
						? FLinearColor(0.12f, 0.5f, 1.0f, 1.0f)
						: FLinearColor(0.09f, 0.09f, 0.1f, 1.0f);
				})
				.OnClicked_Lambda([this, Path]()
				{
					ContentFolder = Path;
					ContentLimit = 200;
					RefreshContent();
					return FReply::Handled();
				})
			];
	};

	AddFolderButton(FString(), TEXT("Todo"), ContentAll);
	for (const FJamFolder& F : ContentFolders)
	{
		AddFolderButton(F.Path, F.Name, F.Count);
	}
}

TSharedRef<SWidget> FJamEditorModule::MakeAssetTile(const FString& Name, const FString& Path)
{
	TSharedRef<SWidget> ThumbWidget = SNullWidget::NullWidget;

	FAssetRegistryModule& ARM = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	const FAssetData Data = ARM.Get().GetAssetByObjectPath(FSoftObjectPath(Path));
	if (Data.IsValid() && ThumbnailPool.IsValid())
	{
		TSharedPtr<FAssetThumbnail> Thumb = MakeShareable(new FAssetThumbnail(Data, 88, 88, ThumbnailPool));
		ThumbnailsKeepAlive.Add(Thumb);
		FAssetThumbnailConfig Cfg;
		Cfg.bAllowFadeIn = true;
		ThumbWidget = Thumb->MakeThumbnailWidget(Cfg);
	}

	return SNew(SBox)
		.WidthOverride(108.0f)
		[
			SNew(SButton)
			.OnClicked_Lambda([this, Name, Path]() { SelectAsset(Name, Path); return FReply::Handled(); })
			// Resalte de alto contraste cuando está elegido (azul); si no, gris oscuro.
			.ButtonColorAndOpacity_Lambda([this, Name]()
			{
				return SelectedAssetName == Name
					? FLinearColor(0.12f, 0.5f, 1.0f, 1.0f)
					: FLinearColor(0.09f, 0.09f, 0.1f, 1.0f);
			})
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot()
				.AutoHeight()
				.HAlign(HAlign_Center)
				[
					SNew(SBox).WidthOverride(88.0f).HeightOverride(88.0f)[ ThumbWidget ]
				]
				+ SVerticalBox::Slot()
				.AutoHeight()
				.HAlign(HAlign_Center)
				.Padding(0.0f, 2.0f, 0.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text(FText::FromString(Name))
					.Justification(ETextJustify::Center)
					.AutoWrapText(true)
				]
			]
		];
}

void FJamEditorModule::SelectAsset(const FString& Name, const FString& Path)
{
	SelectedAssetName = Name;
	SelectedAssetPath = Path;

	// El asset activo vive en el CEREBRO (jam.session), no en esta ventana: así lo heredan por igual
	// la línea de comando, el grafo y cualquier interfaz futura, esté abierta la Dash Bar o no.
	const FString Out = ExecPythonCapture(FString::Printf(
		TEXT("import jam.api as _a; print(_a.select_asset(%s))"), *ToPyStr(Path)));

	if (AssetLabel.IsValid())
	{
		AssetLabel->SetText(FText::FromString(FString::Printf(TEXT("Asset: %s"), *Name)));
	}
	ShowActiveThumbnail(Path);
	if (DashWindow.IsValid())
	{
		AppendLog(FString::Printf(TEXT("asset %s"), *Name), Out);
	}
	ComposeCommandFromParams();  // que el comando incluya asset=…
}

void FJamEditorModule::RebuildParams()
{
	ParamFields.Empty();
	ParamChecks.Empty();
	ParamSpins.Empty();
	ParamIsInt.Empty();
	ParamValues.Empty();
	ParamOptions.Empty();
	ParamChoice.Empty();
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

	for (const FJamParam& P : T->Params)
	{
		const FString Key = P.Name;

		// Control expresivo por tipo: checkbox para los bool, spinner para los números, texto para
		// el resto. Un bool NO debería obligarte a tipear "True".
		TSharedRef<SWidget> Control = SNullWidget::NullWidget;
		if (P.Type == TEXT("bool"))
		{
			const bool bOn = P.Default.Equals(TEXT("True"), ESearchCase::IgnoreCase);
			TSharedPtr<SCheckBox> Check;
			Control = SAssignNew(Check, SCheckBox)
				.IsChecked(bOn ? ECheckBoxState::Checked : ECheckBoxState::Unchecked)
				.OnCheckStateChanged_Lambda([this](ECheckBoxState) { ComposeCommandFromParams(); });
			ParamChecks.Add(Key, Check);
		}
		else if (P.Type == TEXT("int") || P.Type == TEXT("float"))
		{
			const bool bInt = (P.Type == TEXT("int"));
			// x/y/z son los ejes que el gizmo maneja en modo vivo: ahí se bloquean y muestran el
			// punto de mira en tiempo real en vez del offset editable.
			const int32 Axis = (Key == TEXT("x")) ? 0 : (Key == TEXT("y")) ? 1 : (Key == TEXT("z")) ? 2 : INDEX_NONE;
			ParamValues.Add(Key, FCString::Atof(*P.Default));

			TSharedPtr<SSpinBox<float>> Spin;
			Control = SAssignNew(Spin, SSpinBox<float>)
				.Value_Lambda([this, Key, Axis]()
				{
					if (Axis != INDEX_NONE && IsLiveAim())
					{
						return static_cast<float>(LiveAim[Axis]);
					}
					const float* V = ParamValues.Find(Key);
					return V ? *V : 0.0f;
				})
				.IsEnabled_Lambda([this, Axis]() { return !(Axis != INDEX_NONE && IsLiveAim()); })
				.ToolTipText_Lambda([this, Axis]()
				{
					return (Axis != INDEX_NONE && IsLiveAim())
						? LOCTEXT("LiveAxis", "lo manda el gizmo: es el punto de mira del viewport (Confirmar coloca ahí)")
						: LOCTEXT("FreeAxis", "offset respecto del punto de colocación");
				})
				.MinValue(TOptional<float>())     // sin tope: son cm, semillas, cantidades…
				.MaxValue(TOptional<float>())
				.MinSliderValue(bInt ? 0.0f : -1000.0f)
				.MaxSliderValue(bInt ? 100.0f : 1000.0f)
				.Delta(bInt ? 1.0f : 0.0f)
				.MinDesiredWidth(70.0f)
				.OnValueChanged_Lambda([this, Key](float V)
				{
					ParamValues.Add(Key, V);
					ComposeCommandFromParams();
				});
			ParamSpins.Add(Key, Spin);
			ParamIsInt.Add(Key, bInt);
		}
		else if (P.Options.Num() > 0)
		{
			// Param con dominio cerrado (las anclas): lista, no texto libre — no hay que acordarse
			// los nombres ni se puede escribir mal uno.
			ParamOptions.Add(Key, P.Options);
			ParamChoice.Add(Key, P.Default);
			TSharedPtr<STextBlock> Etiqueta;
			Control = SNew(SComboButton)
				.OnGetMenuContent_Lambda([this, Key]()
				{
					FMenuBuilder MB(true, nullptr);
					if (const TArray<TSharedPtr<FString>>* Opts = ParamOptions.Find(Key))
					{
						for (const TSharedPtr<FString>& O : *Opts)
						{
							const FString V = *O;
							MB.AddMenuEntry(
								FText::FromString(V.IsEmpty() ? TEXT("(ninguna)") : V),
								FText::GetEmpty(), FSlateIcon(),
								FUIAction(FExecuteAction::CreateLambda([this, Key, V]()
								{
									ParamChoice.Add(Key, V);
									ComposeCommandFromParams();
								})));
						}
					}
					return MB.MakeWidget();
				})
				.ButtonContent()
				[
					SNew(STextBlock).Text_Lambda([this, Key]()
					{
						const FString* V = ParamChoice.Find(Key);
						return FText::FromString((V && !V->IsEmpty()) ? *V : TEXT("(ninguna)"));
					})
				];
		}
		else
		{
			TSharedPtr<SEditableTextBox> Field;
			Control = SAssignNew(Field, SEditableTextBox)
				.Text(FText::FromString(P.Default))
				.OnTextChanged_Lambda([this](const FText&) { ComposeCommandFromParams(); });
			ParamFields.Add(Key, Field);
		}

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
				.VAlign(VAlign_Center)
				[
					Control
				]
			];
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
		for (const FJamParam& P : T->Params)
		{
			FString Val;
			if (const TSharedPtr<SCheckBox>* Check = ParamChecks.Find(P.Name))
			{
				Val = (*Check)->IsChecked() ? TEXT("true") : TEXT("false");
			}
			else if (ParamSpins.Contains(P.Name))
			{
				// En modo vivo, x/y/z NO viajan en el comando: el punto lo resuelve `view=true` al
				// ejecutar (mandarlos sería sumar dos veces el punto de mira).
				const bool bAxis = (P.Name == TEXT("x") || P.Name == TEXT("y") || P.Name == TEXT("z"));
				if (bAxis && IsLiveAim())
				{
					continue;
				}
				const float* Stored = ParamValues.Find(P.Name);
				const float V = Stored ? *Stored : 0.0f;
				const bool* bInt = ParamIsInt.Find(P.Name);
				Val = (bInt && *bInt) ? FString::FromInt(FMath::RoundToInt(V))
				                      : FString::SanitizeFloat(V);
			}
			else if (const FString* Choice = ParamChoice.Find(P.Name))
			{
				Val = *Choice;
			}
			else if (const TSharedPtr<SEditableTextBox>* Field = ParamFields.Find(P.Name))
			{
				Val = (*Field)->GetText().ToString().TrimStartAndEnd();
			}
			if (!Val.IsEmpty())
			{
				Cmd += FString::Printf(TEXT(" %s=%s"), *P.Name, *Val);
			}
		}
	}
	PushGhostTarget();
	if (!SelectedAssetName.IsEmpty())
	{
		Cmd += FString::Printf(TEXT(" asset=%s"), *SelectedAssetName);
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
	// «Confirmar» = PONÉ ESTO. Si hay una preview, la fija; si no hay ninguna (el caso típico
	// apuntando con el gizmo), corre el comando compuesto y lo fija en el acto: apretás y el objeto
	// aparece donde está el gizmo. La decisión la toma el cerebro (`jam.api.commit`).
	const FString Cmd = CmdBox.IsValid() ? CmdBox->GetText().ToString() : FString();
	const FString Statement = FString::Printf(
		TEXT("import jam.api as _a; print(_a.commit(%s))"), *ToPyStr(Cmd));
	FString Out = ExecPythonCapture(Statement);
	if (Out.IsEmpty())
	{
		Out = TEXT("(sin salida)");
	}
	AppendLog(TEXT("confirm"), Out);
	return FReply::Handled();
}

FReply FJamEditorModule::OnDescartarClicked()
{
	RunCommand(TEXT("discard"));
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

void FJamEditorModule::RecallHistory(int32 Step)
{
	if (History.Num() == 0 || !CmdBox.IsValid())
	{
		return;
	}
	if (HistoryPos == INDEX_NONE)
	{
		HistoryPos = History.Num();   // arranca "después del último"
	}
	HistoryPos = FMath::Clamp(HistoryPos + Step, 0, History.Num() - 1);
	CmdBox->SetText(FText::FromString(History[HistoryPos]));
}

void FJamEditorModule::RunCommand(const FString& Command)
{
	const FString Trimmed = Command.TrimStartAndEnd();
	if (!Trimmed.IsEmpty() && (History.Num() == 0 || History.Last() != Trimmed))
	{
		History.Add(Trimmed);
	}
	HistoryPos = INDEX_NONE;

	const FString Statement = FString::Printf(
		TEXT("import jam.api as _a; print(_a.run(%s))"), *ToPyStr(Command));

	FString Out = ExecPythonCapture(Statement);
	if (Out.IsEmpty())
	{
		Out = TEXT("(sin salida)");
	}
	AppendLog(Command.TrimStartAndEnd(), Out);
}

void FJamEditorModule::AppendLog(const FString& Command, const FString& Result)
{
	if (!Command.IsEmpty())
	{
		LogText += FString::Printf(TEXT("> %s\n"), *Command);
	}
	LogText += Result;
	LogText += TEXT("\n\n");
	if (OutputBox.IsValid())
	{
		OutputBox->SetText(FText::FromString(LogText));
		OutputBox->ScrollTo(ETextLocation::EndOfDocument);
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FJamEditorModule, JamEditor)
