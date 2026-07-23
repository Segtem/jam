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
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
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
	LoadSpec();

	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(LOCTEXT("GraphTitle", "Jam — Graph (Grasshopper)"))
		.ClientSize(FVector2D(780.0f, 560.0f))
		.AutoCenter(EAutoCenter::PreferredWorkArea);

	Win->SetContent(
		SNew(SJamGraphEditor, Tools)
		.OnRunGraph_Raw(this, &FJamEditorModule::RunGraphJson)
		.ActiveAsset_Lambda([this]() { return SelectedAssetName; })
		.OnOpenContent_Raw(this, &FJamEditorModule::OpenContentWindow));
	Win->SetOnWindowClosed(FOnWindowClosed::CreateLambda(
		[this](const TSharedRef<SWindow>&) { GraphWindow.Reset(); }));

	FSlateApplication::Get().AddWindow(Win);
	GraphWindow = Win;
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
	AssetLabel.Reset();
	LogText.Empty();
}

void FJamEditorModule::LoadSpec()
{
	Tools.Reset();
	Categories.Reset();
	const FString Raw = ExecPythonCapture(
		TEXT("import jam.api as _a; print('JAMSPEC:' + _a.spec())"));

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

	for (const FString& Cat : Categories)
	{
		if (Cat == TEXT("Content"))
		{
			continue;  // Content ya está como botón propio (browser), no como combo de verbos
		}
		if (!CategoryHasTools(Cat))
		{
			continue;
		}
		Bar->AddSlot()
			.AutoWidth()
			.Padding(2.0f, 0.0f)
			[
				SNew(SComboButton)
				.ButtonContent()
				[
					SNew(STextBlock).Text(FText::FromString(Cat))
				]
				.OnGetMenuContent_Lambda([this, Cat]() { return MakeCategoryMenu(Cat); })
			];
	}
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

	return SNew(SVerticalBox)

		// Barra de secciones horizontal (Dash bar).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 6.0f, 6.0f, 4.0f)
		[
			Bar
		]

		// Asset activo (lo elegido en la ventana de Content alimenta las herramientas).
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(6.0f, 2.0f)
		[
			SAssignNew(AssetLabel, STextBlock)
			.Text(LOCTEXT("NoAsset", "Asset: (elegí uno en Content)"))
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
				.HintText(LOCTEXT("CmdHint", "escribí un comando (o elegí una herramienta arriba) y Enter"))
				.OnTextCommitted_Raw(this, &FJamEditorModule::OnCmdCommitted)
			]
		];
}

void FJamEditorModule::SelectTool(const FString& Verb)
{
	ActiveVerb = Verb;
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

void FJamEditorModule::PickFromUnrealSelection()
{
	// El verbo `pick` lee la selección del Content Browser de Unreal y fija el asset activo en el
	// cerebro. La UI sólo refleja lo que el cerebro ya decidió.
	const FString Out = ExecPythonCapture(
		TEXT("import jam.api as _a; print(_a.run('pick'))"));
	AppendLog(TEXT("pick"), Out);

	// leer de vuelta el nombre del activo para el rótulo/composición del comando
	const FString Raw = ExecPythonCapture(
		TEXT("import jam.session as _s; print('JAMSEL:' + (_s.nombre() or ''))"));
	const FString Marker(TEXT("JAMSEL:"));
	const int32 M = Raw.Find(Marker);
	if (M != INDEX_NONE)
	{
		FString Name = Raw.Mid(M + Marker.Len());
		Name.TrimStartAndEndInline();
		if (!Name.IsEmpty())
		{
			SelectedAssetName = Name;
			if (AssetLabel.IsValid())
			{
				AssetLabel->SetText(FText::FromString(
					FString::Printf(TEXT("Asset: %s  (selección de Unreal)"), *Name)));
			}
			ComposeCommandFromParams();
		}
	}
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
	if (DashWindow.IsValid())
	{
		AppendLog(FString::Printf(TEXT("asset %s"), *Name), Out);
	}
	ComposeCommandFromParams();  // que el comando incluya asset=…
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
	RunCommand(TEXT("confirm"));
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

void FJamEditorModule::RunCommand(const FString& Command)
{
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
