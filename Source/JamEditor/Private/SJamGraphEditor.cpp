#include "SJamGraphEditor.h"
#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SCanvas.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Layout/SExpandableArea.h"
#include "Widgets/Layout/SSeparator.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "Brushes/SlateImageBrush.h"
#include "Interfaces/IPluginManager.h"
#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Rendering/DrawElements.h"
#include "Math/TransformCalculus2D.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Dom/JsonObject.h"

#define LOCTEXT_NAMESPACE "JamGraphEditor"

// Tipo visual de un pin de parámetro. Es la misma clave que usa DataColor para cables y grips.
static FString JamParamDataType(const FString& Name, const FString& Type)
{
	if (Name.Contains(TEXT("spline"), ESearchCase::IgnoreCase)) { return TEXT("S"); }
	if (Type == TEXT("bool")) { return TEXT("B"); }
	if (Type == TEXT("int") || Type == TEXT("float")) { return TEXT("N"); }
	if (Type == TEXT("str")) { return TEXT("T"); }
	return FString();
}

// El mapping vive junto a los SVG para que cambiar un pictograma no obligue a recompilar C++.
// Se lee una vez al abrir la UI; si el JSON está roto o no existe, los badges/nodos usan su fallback.
static const TMap<FString, FString>& JamIconMap()
{
	static const TMap<FString, FString> Map = []()
	{
		TMap<FString, FString> Loaded;
		const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
		if (!Plugin.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] no encontré el plugin Jam para cargar iconos."));
			return Loaded;
		}

		const FString MapPath = FPaths::Combine(
			Plugin->GetBaseDir(), TEXT("Resources/Icons/Lucide/icon-map.json"));
		FString Json;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Json, *MapPath))
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] icon-map.json no se pudo leer: %s"), *MapPath);
			return Loaded;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] icon-map.json no es JSON válido: %s"), *MapPath);
			return Loaded;
		}

		for (const TPair<FString, TSharedPtr<FJsonValue>>& Entry : Root->Values)
		{
			FString IconName;
			if (Entry.Value.IsValid() && Entry.Value->TryGetString(IconName) && !IconName.IsEmpty())
			{
				Loaded.Add(Entry.Key, IconName);
			}
		}
		return Loaded;
	}();
	return Map;
}

// ---- el tab Aprender: los tutoriales, leídos de un manifiesto ----
// Estaban como cinco entradas «Abrir ejemplo: …» dentro del menú File, que es donde nadie mira
// cuando está empezando, y como cinco funciones C++ que sólo se diferenciaban en un nombre de
// archivo. Ahora son DATO: `Resources/Examples/examples.json` los lista, y agregar un tutorial es
// soltar el .jamgraph y sumarle una línea — sin recompilar el plugin, igual que los iconos.

struct FJamExample
{
	FString File;
	FString Title;
	FString Doc;
	FString Group;
	FString Icon;
	FString Message;
};

// El nombre del tab. No sale del spec de verbos porque no es una categoría de verbos: no hay
// ningún `FJamTool` con esta categoría, y sus fichas CARGAN un grafo en vez de crear un nodo.
static const TCHAR* JamLearnTab = TEXT("Aprender");

static const TArray<FJamExample>& JamExamples()
{
	static const TArray<FJamExample> Cargados = []()
	{
		TArray<FJamExample> Salida;
		const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
		if (!Plugin.IsValid())
		{
			return Salida;
		}
		const FString Path = FPaths::Combine(
			Plugin->GetBaseDir(), TEXT("Resources/Examples/examples.json"));
		FString Json;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Json, *Path))
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] examples.json no se pudo leer: %s"), *Path);
			return Salida;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] examples.json no es JSON válido: %s"), *Path);
			return Salida;
		}
		const TArray<TSharedPtr<FJsonValue>>* Lista = nullptr;
		if (!Root->TryGetArrayField(TEXT("ejemplos"), Lista) || Lista == nullptr)
		{
			return Salida;
		}
		for (const TSharedPtr<FJsonValue>& Valor : *Lista)
		{
			const TSharedPtr<FJsonObject>* Objeto = nullptr;
			if (!Valor.IsValid() || !Valor->TryGetObject(Objeto) || Objeto == nullptr)
			{
				continue;
			}
			FJamExample E;
			(*Objeto)->TryGetStringField(TEXT("archivo"), E.File);
			(*Objeto)->TryGetStringField(TEXT("titulo"), E.Title);
			(*Objeto)->TryGetStringField(TEXT("doc"), E.Doc);
			(*Objeto)->TryGetStringField(TEXT("grupo"), E.Group);
			(*Objeto)->TryGetStringField(TEXT("icono"), E.Icon);
			(*Objeto)->TryGetStringField(TEXT("mensaje"), E.Message);
			if (!E.File.IsEmpty())
			{
				Salida.Add(MoveTemp(E));
			}
		}
		return Salida;
	}();
	return Cargados;
}

static FString JamIconPath(const FString& IconName)
{
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
	if (IconName.IsEmpty() || !Plugin.IsValid())
	{
		return FString();
	}
	const FString Path = FPaths::Combine(
		Plugin->GetBaseDir(), TEXT("Resources/Icons/Lucide"), IconName + TEXT(".svg"));
	return IFileManager::Get().FileExists(*Path) ? Path : FString();
}

// Capa de fondo del canvas (como el de Grasshopper): pinta el color de fondo, una GRILLA fina
// alineada al pan/zoom, y los WIRES (splines) — todo detrás de los nodos.
class SJamWireLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamWireLayer) {}
	SLATE_END_ARGS()

	void Construct(const FArguments&,
		TFunction<TArray<SJamGraphEditor::FJamWire>()> InGetter,
		TFunction<void(FVector2D&, float&)> InXform,
		TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)> InPending)
	{
		Getter = MoveTemp(InGetter);
		XformGetter = MoveTemp(InXform);
		PendingGetter = MoveTemp(InPending);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		const FSlateBrush* White = FAppStyle::GetBrush("WhiteBrush");
		const FVector2D Size = AllottedGeometry.GetLocalSize();

		// Fondo del canvas: gris claro clásico de Grasshopper/Rhino 7.
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId, AllottedGeometry.ToPaintGeometry(),
			White, ESlateDrawEffect::None, FLinearColor(0.827f, 0.835f, 0.812f, 1.0f));

		// Grilla: líneas cada 24 u de modelo, mayores cada 4. Alineada al pan/zoom (se mueve y escala
		// con el lienzo, como GH). Se saltea si el paso en pantalla es muy chico (zoom out).
		FVector2D Pan = FVector2D::ZeroVector;
		float Zoom = 1.0f;
		if (XformGetter) { XformGetter(Pan, Zoom); }
		const float Step = 24.0f * Zoom;
		if (Step >= 9.0f)
		{
			const FLinearColor Minor(0.0f, 0.0f, 0.0f, 0.06f);
			const FLinearColor Major(0.0f, 0.0f, 0.0f, 0.13f);
			auto Line = [&](const FVector2D& A, const FVector2D& B, const FLinearColor& C)
			{
				TArray<FVector2D> Pts; Pts.Add(A); Pts.Add(B);
				FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 1,
					AllottedGeometry.ToPaintGeometry(), Pts, ESlateDrawEffect::None, C, false, 1.0f);
			};
			float ox = FMath::Fmod(Pan.X * Zoom, Step); if (ox < 0) { ox += Step; }
			for (float x = ox; x < Size.X; x += Step)
			{
				const int32 k = FMath::RoundToInt((x / Zoom - Pan.X) / 24.0f);
				Line(FVector2D(x, 0.0f), FVector2D(x, Size.Y), (k % 4 == 0) ? Major : Minor);
			}
			float oy = FMath::Fmod(Pan.Y * Zoom, Step); if (oy < 0) { oy += Step; }
			for (float y = oy; y < Size.Y; y += Step)
			{
				const int32 k = FMath::RoundToInt((y / Zoom - Pan.Y) / 24.0f);
				Line(FVector2D(0.0f, y), FVector2D(Size.X, y), (k % 4 == 0) ? Major : Minor);
			}
		}

		// Wires (splines) entre nodos, sobre la grilla. Cada uno con su COLOR por tipo de dato (como
		// Blueprint/Substance): el color dice QUÉ fluye. Un halo claro debajo levanta el contraste sobre
		// el lienzo gris y ayuda a seguir el cable donde se cruzan.
		const FSlateBrush* Dot = FAppStyle::GetBrush("WhiteBrush");
		if (Getter)
		{
			const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry();
			for (const SJamGraphEditor::FJamWire& W : Getter())
			{
				const float dx = FMath::Max(50.0f, FMath::Abs(W.B.X - W.A.X) * 0.6f);
				const FVector2D T1(dx, 0.0f), T2(dx, 0.0f);
				// halo claro (más grueso, translúcido) + cable de color encima.
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 2, PG,
					W.A, T1, W.B, T2, 5.0f, ESlateDrawEffect::None,
					FLinearColor(1.0f, 1.0f, 1.0f, 0.55f));
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 3, PG,
					W.A, T1, W.B, T2, 2.6f, ESlateDrawEffect::None, W.Color);
				// punto en cada punta: ancla la conexión visualmente (como los pines de Blueprint).
				for (const FVector2D& P : {W.A, W.B})
				{
					FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 4,
						AllottedGeometry.ToPaintGeometry(FVector2D(6.0f, 6.0f),
							FSlateLayoutTransform(P - FVector2D(3.0f, 3.0f))),
						Dot, ESlateDrawEffect::None, W.Color);
				}
			}
		}

		// Cable-fantasma: del pin de salida armado al cursor, mientras se conecta (el rubber band de
		// Houdini/GH/Blueprint). Punteado-suave (semitransparente) para distinguirlo de los fijos.
		FVector2D PF, PT; FLinearColor PC;
		if (PendingGetter && PendingGetter(PF, PT, PC))
		{
			const float dx = FMath::Max(50.0f, FMath::Abs(PT.X - PF.X) * 0.6f);
			FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 5, AllottedGeometry.ToPaintGeometry(),
				PF, FVector2D(dx, 0.0f), PT, FVector2D(dx, 0.0f), 2.4f, ESlateDrawEffect::None,
				FLinearColor(PC.R, PC.G, PC.B, 0.7f));
			FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 6,
				AllottedGeometry.ToPaintGeometry(FVector2D(7.0f, 7.0f),
					FSlateLayoutTransform(PF - FVector2D(3.5f, 3.5f))),
				Dot, ESlateDrawEffect::None, PC);
		}
		return LayerId + 6;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<TArray<SJamGraphEditor::FJamWire>()> Getter;
	TFunction<void(FVector2D&, float&)> XformGetter;
	TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)> PendingGetter;
};


void SJamGraphEditor::Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools)
{
	Tools = InTools;
	OnRunGraph = InArgs._OnRunGraph;
	OnCompileGraph = InArgs._OnCompileGraph;
	OnBakePreview = InArgs._OnBakePreview;
	OnDiscardPreview = InArgs._OnDiscardPreview;
	OnSaveGraph = InArgs._OnSaveGraph;
	OnInspect = InArgs._OnInspect;
	ActiveAsset = InArgs._ActiveAsset;
	OnOpenContent = InArgs._OnOpenContent;

	// Ribbon estilo Grasshopper: una fila de TABS (categorías) y, debajo, las fichas de la categoría
	// activa con ICONO (badge de color + código) + nombre. El tab activo se pinta con el tono de su
	// categoría. El doble clic en el lienzo abre el buscador igual (los dos caminos conviven).
	Categories.Reset();
	for (const FJamTool& T : Tools)
	{
		Categories.AddUnique(T.Cat);
	}
	if (ActiveTab.IsEmpty() && Categories.Num() > 0)
	{
		ActiveTab = Categories[0];
	}

	TSharedRef<SHorizontalBox> TabStrip = SNew(SHorizontalBox);
	TabStrip->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
	[
		SNew(SButton)
		.Text(LOCTEXT("PaletteContent", "Content…"))
		.ToolTipText(LOCTEXT("PaletteContentTip", "Elegir el asset activo (abre la ventana de Content)"))
		.OnClicked_Lambda([this]() { OnOpenContent.ExecuteIfBound(); return FReply::Handled(); })
	];
	// «Aprender» va PRIMERO —es lo que busca alguien que recién llega— pero NO es el tab por
	// defecto: quien usa Jam todos los días no quiere una pantalla de bienvenida entre él y sus
	// verbos. Se abre en el primer tab de trabajo y este queda a un clic, a la vista.
	Categories.Insert(JamLearnTab, 0);
	for (const FString& Cat : Categories)
	{
		TabStrip->AddSlot().AutoWidth().Padding(1.0f, 0.0f)
		[
			SNew(SButton)
			.ToolTipText(Cat == JamLearnTab
				? LOCTEXT("LearnTabTip", "Tutoriales y ejemplos: grafos armados para abrir, correr y desarmar")
				: FText::FromString(FString::Printf(TEXT("Tab «%s»"), *Cat)))
			// activo = tono de la categoría; inactivo = gris apagado (así se lee cuál está abierto)
			.ButtonColorAndOpacity_Lambda([this, Cat]()
			{
				return ActiveTab == Cat ? CategoryColor(Cat) : FLinearColor(0.22f, 0.22f, 0.24f, 1.0f);
			})
			.OnClicked_Lambda([this, Cat]() { ActiveTab = Cat; RebuildTabContent(); return FReply::Handled(); })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[ MakeBadge(CategoryColor(Cat), Cat.Left(2).ToUpper(), 14.0f) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f, 2.0f, 0.0f)
				[ SNew(STextBlock).Text(FText::FromString(Cat)) ]
			]
		];
	}

	// Menú principal estilo Grasshopper (File / Edit / View / Display / Solution).
	FMenuBarBuilder MenuBar(nullptr);
	MenuBar.AddPullDownMenu(LOCTEXT("MenuFile", "File"), LOCTEXT("MenuFileTip", "Diagrama: nuevo, abrir, guardar"),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillFileMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuEdit", "Edit"), FText::GetEmpty(),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillEditMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuView", "View"), FText::GetEmpty(),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillViewMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuDisplay", "Display"), FText::GetEmpty(),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillDisplayMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuSolution", "Solution"), LOCTEXT("MenuSolutionTip", "Correr el grafo"),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillSolutionMenu));

	ChildSlot
	[
		SNew(SVerticalBox)

		// Barra de menú (File / Edit / View / Display / Solution), como Grasshopper.
		+ SVerticalBox::Slot().AutoHeight()
		[
			MenuBar.MakeWidget()
		]

		// Ribbon: fila de TABS (categorías).
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 6.0f, 6.0f, 0.0f)
		[
			SNew(SScrollBox).Orientation(Orient_Horizontal)
			+ SScrollBox::Slot()[ TabStrip ]
		]

		// Ribbon: fichas con icono de la categoría activa (se rellena en RebuildTabContent).
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f, 6.0f, 2.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Header"))
			.Padding(2.0f)
			[
				SNew(SScrollBox).Orientation(Orient_Horizontal)
				+ SScrollBox::Slot()[ SAssignNew(TabContentBox, SHorizontalBox) ]
			]
		]

		// Canvas: wires detrás, nodos encima. RECORTADO a su área: sin esto, un nodo arrastrado cerca
		// del borde superior se dibuja por encima del ribbon y del menú.
		+ SVerticalBox::Slot().FillHeight(1.0f).Padding(6.0f, 2.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Recessed"))
			.Padding(0.0f)
			.Clipping(EWidgetClipping::ClipToBounds)
			[
				SNew(SOverlay)
				+ SOverlay::Slot()
				[
					SAssignNew(WireLayer, SJamWireLayer,
						TFunction<TArray<FJamWire>()>(
							[this]() { return GetWireEndpoints(); }),
						TFunction<void(FVector2D&, float&)>(
							[this](FVector2D& P, float& Z) { P = PanOffset; Z = Zoom; }),
						TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)>(
							[this](FVector2D& F, FVector2D& T, FLinearColor& C) { return GetPendingWire(F, T, C); }))
				]
				+ SOverlay::Slot()
				[
					SAssignNew(Canvas, SCanvas)
				]
				// Buscador de nodos (doble clic en el fondo), como el search box de Grasshopper.
				+ SOverlay::Slot()
				.HAlign(HAlign_Left)
				.VAlign(VAlign_Top)
				[
					SAssignNew(SearchPopup, SBorder)
					.BorderImage(FAppStyle::GetBrush("Menu.Background"))
					.Padding(4.0f)
					.Visibility_Lambda([this]() { return bSearchOpen ? EVisibility::Visible : EVisibility::Collapsed; })
					.RenderTransform_Lambda([this]() { return FSlateRenderTransform(SearchAt); })
					[
						SNew(SBox).WidthOverride(220.0f)
						[
							SNew(SVerticalBox)
							+ SVerticalBox::Slot().AutoHeight()
							[
								SAssignNew(SearchField, SEditableTextBox)
								.HintText(LOCTEXT("SearchNode", "buscar nodo…"))
								.OnTextChanged_Lambda([this](const FText& T) { RebuildSearchResults(T.ToString()); })
								.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type Type)
								{
									if (Type == ETextCommit::OnEnter) { CommitSearch(); }
									else if (Type == ETextCommit::OnCleared) { CloseSearch(); }
								})
							]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f)
							[
								SAssignNew(SearchResults, SVerticalBox)
							]
						]
					]
				]
			]
		]

		// Compile/Run + salida.
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(SButton).Text(LOCTEXT("Compile", "✓ Compile"))
				.ToolTipText(LOCTEXT("CompileTip", "Valida nodos, cables, parámetros y assets sin tocar la escena"))
				.OnClicked_Lambda([this]() { ValidateGraph(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("Run", "▶ Run graph"))
				.OnClicked_Lambda([this]() { RunGraph(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("BakePreview", "✓ Bake"))
				.ToolTipText(LOCTEXT("BakePreviewTip", "Fija únicamente el Preview creado por este Graph"))
				.OnClicked_Lambda([this]() { BakePreview(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("DiscardPreview", "✗ Discard"))
				.ToolTipText(LOCTEXT("DiscardPreviewTip", "Elimina únicamente el Preview creado por este Graph"))
				.OnClicked_Lambda([this]() { DiscardPreview(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("SaveCompound", "★ Guardar como preset"))
				.ToolTipText(LOCTEXT("SaveCompoundTip", "Guarda este grafo como preset compound reusable"))
				.OnClicked_Lambda([this]()
				{
					if (Nodes.Num() > 0 && OnSaveGraph.IsBound())
					{
						OnSaveGraph.Execute(BuildJson());
					}
					return FReply::Handled();
				})
			]
			+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(8.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock).Text(LOCTEXT("Hint",
					"doble clic = buscar nodo · botón derecho arrastra el lienzo · ○→○ conecta · Run pinta cada nodo con su veredicto"))
			]
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f, 6.0f, 2.0f).MaxHeight(140.0f)
		[
			SAssignNew(Output, SMultiLineEditableTextBox).IsReadOnly(true).AllowMultiLine(true)
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 0.0f, 6.0f, 6.0f)
		[
			BuildInspector()
		]
	];

	RebuildTabContent();   // abre el primer tab con sus fichas
}


// ---- Inspector de datos: el Geometry Spreadsheet de Jam ----
//
// Houdini, Blender y PCG tienen todos un inspector NUMÉRICO separado de la visualización 3D, y es el
// que más se usa: el flujo documentado de PCG es «recorrer hacia adelante y ver dónde el conteo cae a
// cero». Ver geometría contesta «¿dónde está?»; esto contesta «¿qué valores tiene?».
//
// Los datos salen del último Run, que Python cachea por node id, así que abrir el panel no recalcula
// nada. La tabla ya viene formateada y filtrada desde `jam.api.inspect_json`: la regla de filtrado
// vive en UN solo lado.

/** Fila del inspector: una celda por columna, monoespaciada y alineada a la derecha como una
 *  planilla. Los textos ya vienen formateados de Python, así que acá sólo se ubican. */
class SJamInspectRowWidget : public SMultiColumnTableRow<TSharedPtr<FJamInspectRow>>
{
public:
	SLATE_BEGIN_ARGS(SJamInspectRowWidget) {}
		SLATE_ARGUMENT(TSharedPtr<FJamInspectRow>, Item)
		SLATE_ARGUMENT(const TArray<FString>*, Columns)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& Owner)
	{
		Item = InArgs._Item;
		Columns = InArgs._Columns;
		SMultiColumnTableRow<TSharedPtr<FJamInspectRow>>::Construct(FSuperRowType::FArguments(), Owner);
	}

	virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
	{
		const int32 Index = (Columns != nullptr)
			? Columns->IndexOfByKey(ColumnName.ToString()) : INDEX_NONE;
		const FString Texto = (Item.IsValid() && Item->Cells.IsValidIndex(Index))
			? Item->Cells[Index] : FString();
		return SNew(STextBlock)
			.Text(FText::FromString(Texto))
			.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
			.Justification(ETextJustify::Right)
			.Margin(FMargin(4.0f, 1.0f));
	}

private:
	TSharedPtr<FJamInspectRow> Item;
	const TArray<FString>* Columns = nullptr;
};

TSharedRef<SWidget> SJamGraphEditor::BuildInspector()
{
	return SNew(SExpandableArea)
		.InitiallyCollapsed(true)
		.AreaTitle(LOCTEXT("InspectorTitle", "Inspector de datos (último Run)"))
		.Padding(FMargin(4.0f))
		.BodyContent()
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[
					SNew(SBox).WidthOverride(220.0f)
					[
						SAssignNew(InspectPicker, SComboBox<TSharedPtr<FString>>)
						.OptionsSource(&InspectNodes)
						.OnGenerateWidget_Lambda([](TSharedPtr<FString> Item)
						{
							return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : FString()));
						})
						.OnSelectionChanged_Lambda([this](TSharedPtr<FString> Item, ESelectInfo::Type)
						{
							if (!Item.IsValid()) { return; }
							// La etiqueta es «id  ·  tipo  ·  N», así que el id es lo de antes del ·.
							FString Id = *Item;
							int32 Corte = INDEX_NONE;
							if (Id.FindChar(TEXT('\u00b7'), Corte)) { Id = Id.Left(Corte); }
							InspectNodeId = Id.TrimStartAndEnd();
							// Otro nodo puede tener otras columnas: el orden anterior ya no aplica.
							InspectSort.Empty();
							bInspectDescending = false;
							RefreshInspector();
						})
						[
							SNew(STextBlock)
							.Text_Lambda([this]()
							{
								return InspectNodeId.IsEmpty()
									? LOCTEXT("PickNode", "elegí un nodo…")
									: FText::FromString(InspectNodeId);
							})
						]
					]
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(6.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SBox).WidthOverride(180.0f)
					[
						SAssignNew(InspectFilter, SEditableTextBox)
						.HintText(LOCTEXT("InspectFilterHint", "filtrar filas…"))
						.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type)
						{
							RefreshInspector();
						})
					]
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(6.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("InspectRefresh", "actualizar"))
					.ToolTipText(LOCTEXT("InspectRefreshTip", "releer los datos del último Run"))
					.OnClicked_Lambda([this]() { RefreshInspector(); return FReply::Handled(); })
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					SAssignNew(InspectStatus, STextBlock)
					.Text(LOCTEXT("InspectIdle", "corré el grafo y elegí un nodo"))
				]
			]
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SBox).HeightOverride(180.0f)
				[
					SAssignNew(InspectList, SListView<TSharedPtr<FJamInspectRow>>)
					.ListItemsSource(&InspectRows)
					.SelectionMode(ESelectionMode::Single)
					.HeaderRow(SAssignNew(InspectHeader, SHeaderRow))
					.OnGenerateRow_Lambda([this](TSharedPtr<FJamInspectRow> Item,
						const TSharedRef<STableViewBase>& Owner)
					{
						return SNew(SJamInspectRowWidget, Owner)
							.Item(Item)
							.Columns(&InspectColumns);
					})
				]
			]
		];
}

void SJamGraphEditor::RefreshInspector()
{
	InspectNodes.Reset();
	InspectRows.Reset();
	if (!OnInspect.IsBound())
	{
		if (InspectStatus.IsValid()) { InspectStatus->SetText(LOCTEXT("InspectNoBridge", "sin puente a Python")); }
		return;
	}
	const FString Filtro = InspectFilter.IsValid() ? InspectFilter->GetText().ToString() : FString();
	const FString Raw = OnInspect.Execute(InspectNodeId, Filtro, InspectSort, bInspectDescending);

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		if (InspectStatus.IsValid()) { InspectStatus->SetText(FText::FromString(Raw.Left(120))); }
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Nodos = nullptr;
	if (Root->TryGetArrayField(TEXT("nodos"), Nodos) && Nodos != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Nodos)
		{
			const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
			if (!O.IsValid()) { continue; }
			FString Id, Tipo;
			double Cantidad = 0.0;
			O->TryGetStringField(TEXT("id"), Id);
			O->TryGetStringField(TEXT("tipo"), Tipo);
			O->TryGetNumberField(TEXT("cantidad"), Cantidad);
			InspectNodes.Add(MakeShared<FString>(FString::Printf(
				TEXT("%s \u00b7 %s \u00b7 %d"), *Id, *Tipo, static_cast<int32>(Cantidad))));
		}
	}

	// Las columnas cambian con el TIPO del nodo (P tiene peso, F tiene escala y tangente…), así que
	// el encabezado se reconstruye en cada refresco en vez de ser fijo.
	InspectColumns.Reset();
	const TArray<TSharedPtr<FJsonValue>>* Columnas = nullptr;
	if (Root->TryGetArrayField(TEXT("columnas"), Columnas) && Columnas != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Columnas)
		{
			const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
			FString Nombre;
			if (O.IsValid() && O->TryGetStringField(TEXT("nombre"), Nombre))
			{
				InspectColumns.Add(Nombre);
			}
		}
	}
	if (InspectHeader.IsValid())
	{
		InspectHeader->ClearColumns();
		for (const FString& Nombre : InspectColumns)
		{
			const FName Id(*Nombre);
			InspectHeader->AddColumn(
				SHeaderRow::Column(Id)
				.DefaultLabel(FText::FromString(Nombre))
				.FillWidth(1.0f)
				.SortMode_Lambda([this, Nombre]()
				{
					if (InspectSort != Nombre) { return EColumnSortMode::None; }
					return bInspectDescending ? EColumnSortMode::Descending : EColumnSortMode::Ascending;
				})
				// Ordenar lo resuelve Python sobre TODAS las filas y recorta después; si ordenara
				// la UI, sólo ordenaría las 200 que ya recibió.
				.OnSort_Lambda([this](EColumnSortPriority::Type, const FName& ColumnId,
					EColumnSortMode::Type NuevoModo)
				{
					InspectSort = ColumnId.ToString();
					bInspectDescending = (NuevoModo == EColumnSortMode::Descending);
					RefreshInspector();
				}));
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* Filas = nullptr;
	if (Root->TryGetArrayField(TEXT("filas"), Filas) && Filas != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Filas)
		{
			const TArray<TSharedPtr<FJsonValue>>* Celdas = nullptr;
			if (!V.IsValid() || !V->TryGetArray(Celdas) || Celdas == nullptr) { continue; }
			TSharedRef<FJamInspectRow> Fila = MakeShared<FJamInspectRow>();
			for (const TSharedPtr<FJsonValue>& C : *Celdas)
			{
				Fila->Cells.Add(C.IsValid() ? C->AsString() : FString());
			}
			InspectRows.Add(Fila);
		}
	}

	FString Estado;
	bool bOk = false;
	Root->TryGetBoolField(TEXT("ok"), bOk);
	if (!bOk)
	{
		Root->TryGetStringField(TEXT("error"), Estado);
	}
	else if (InspectNodeId.IsEmpty())
	{
		Estado = FString::Printf(TEXT("%d nodo(s) en el último Run"), InspectNodes.Num());
	}
	else
	{
		double Total = 0.0;
		Root->TryGetNumberField(TEXT("total"), Total);
		Estado = (static_cast<int32>(Total) > InspectRows.Num())
			? FString::Printf(TEXT("%d de %d fila(s)"), InspectRows.Num(), static_cast<int32>(Total))
			: FString::Printf(TEXT("%d fila(s)"), InspectRows.Num());
	}
	if (InspectStatus.IsValid()) { InspectStatus->SetText(FText::FromString(Estado)); }
	if (InspectPicker.IsValid()) { InspectPicker->RefreshOptions(); }
	if (InspectList.IsValid()) { InspectList->RequestListRefresh(); }
}


// ---- Ribbon estilo Grasshopper: tabs + fichas con icono ----

FLinearColor SJamGraphEditor::CategoryColor(const FString& Cat)
{
	// un tono por categoría (como los tabs de Grasshopper): tools + flow.
	if (Cat == TEXT("Content"))  { return FLinearColor(0.40f, 0.44f, 0.50f, 1.0f); }
	if (Cat == TEXT("Place"))    { return FLinearColor(0.20f, 0.52f, 0.72f, 1.0f); }
	if (Cat == TEXT("Scatter"))  { return FLinearColor(0.24f, 0.60f, 0.32f, 1.0f); }
	if (Cat == TEXT("Create"))   { return FLinearColor(0.62f, 0.34f, 0.66f, 1.0f); }
	if (Cat == TEXT("Mesh"))     { return FLinearColor(0.18f, 0.56f, 0.56f, 1.0f); }
	if (Cat == TEXT("Edit"))     { return FLinearColor(0.72f, 0.50f, 0.16f, 1.0f); }
	if (Cat == TEXT("Params"))   { return FLinearColor(0.44f, 0.44f, 0.48f, 1.0f); }
	if (Cat == TEXT("Maths"))    { return FLinearColor(0.78f, 0.28f, 0.42f, 1.0f); }
	if (Cat == TEXT("Source"))   { return FLinearColor(0.24f, 0.58f, 0.40f, 1.0f); }
	if (Cat == TEXT("Vector"))   { return FLinearColor(0.36f, 0.44f, 0.62f, 1.0f); }
	if (Cat == TEXT("Mask"))     { return FLinearColor(0.78f, 0.46f, 0.14f, 1.0f); }
	if (Cat == TEXT("Weight"))   { return FLinearColor(0.46f, 0.52f, 0.58f, 1.0f); }   // gris frío = máscara gris
	if (Cat == TEXT("Sets"))     { return FLinearColor(0.30f, 0.52f, 0.56f, 1.0f); }
	if (Cat == TEXT("Transform")){ return FLinearColor(0.50f, 0.40f, 0.24f, 1.0f); }
	if (Cat == TEXT("Combine"))  { return FLinearColor(0.26f, 0.46f, 0.70f, 1.0f); }
	if (Cat == TEXT("Output"))   { return FLinearColor(0.58f, 0.30f, 0.62f, 1.0f); }
	if (Cat == TEXT("Shader"))   { return FLinearColor(0.66f, 0.42f, 0.20f, 1.0f); }
	if (Cat == TEXT("Display"))  { return FLinearColor(0.62f, 0.60f, 0.24f, 1.0f); }
	// «Aprender» no es una categoría de verbos: es el tab de tutoriales. Azul frío, que no se
	// confunde con ninguno de los tabs de trabajo.
	if (Cat == TEXT("Aprender")) { return FLinearColor(0.22f, 0.40f, 0.62f, 1.0f); }
	return FLinearColor(0.35f, 0.35f, 0.38f, 1.0f);
}

FString SJamGraphEditor::VerbCode(const FString& Verb)
{
	// código curado de 2 letras para el badge (legible siempre, sin depender de glifos raros).
	static const TMap<FString, FString> Codes = {
		{TEXT("asset"), TEXT("AS")}, {TEXT("pick"), TEXT("PK")},
		{TEXT("place"), TEXT("PL")}, {TEXT("drop"), TEXT("DR")}, {TEXT("snap"), TEXT("SN")},
		{TEXT("scatter"), TEXT("SC")}, {TEXT("spline"), TEXT("SP")}, {TEXT("pcg"), TEXT("PC")},
		{TEXT("replace"), TEXT("RP")}, {TEXT("create_spline"), TEXT("CS")},
		{TEXT("pivot"), TEXT("PV")}, {TEXT("pivot_set"), TEXT("PS")}, {TEXT("normalize"), TEXT("NR")},
		{TEXT("gizmo"), TEXT("GZ")}, {TEXT("ghost"), TEXT("GH")},
		{TEXT("source_surface"), TEXT("SF")}, {TEXT("source_grid"), TEXT("GR")},
		{TEXT("source_poisson"), TEXT("PO")}, {TEXT("source_radial"), TEXT("RA")},
		{TEXT("mask_slope"), TEXT("SL")}, {TEXT("mask_height"), TEXT("HT")},
		{TEXT("mask_noise"), TEXT("NO")}, {TEXT("mask_density"), TEXT("DN")},
		{TEXT("mask_circle"), TEXT("CI")}, {TEXT("merge"), TEXT("MG")}, {TEXT("instance"), TEXT("IN")},
		{TEXT("number"), TEXT("N#")}, {TEXT("math"), TEXT("fx")}, {TEXT("text"), TEXT("Tx")},
		{TEXT("cull_nth"), TEXT("CN")}, {TEXT("sub_list"), TEXT("SB")}, {TEXT("shift"), TEXT("SH")},
		{TEXT("reverse"), TEXT("RV")}, {TEXT("move"), TEXT("MV")}, {TEXT("scale_pts"), TEXT("SZ")},
		{TEXT("rotate_pts"), TEXT("RT")}, {TEXT("jitter"), TEXT("JT")},
		{TEXT("pts_line"), TEXT("LN")}, {TEXT("pts_circle"), TEXT("CR")}, {TEXT("pts_rect"), TEXT("RC")},
		{TEXT("pts_arc"), TEXT("AR")}, {TEXT("relax"), TEXT("RX")}, {TEXT("weave"), TEXT("WV")},
		{TEXT("info"), TEXT("i")},
		{TEXT("weight_slope"), TEXT("WS")}, {TEXT("weight_height"), TEXT("WH")},
		{TEXT("weight_noise"), TEXT("WN")}, {TEXT("weight_radial"), TEXT("WR")},
		{TEXT("weight_invert"), TEXT("1-")}, {TEXT("weight_power"), TEXT("W^")},
		{TEXT("weight_curve"), TEXT("WC")}, {TEXT("weight_combine"), TEXT("WX")},
		{TEXT("weight_cull"), TEXT("WK")},
	};
	if (const FString* Found = Codes.Find(Verb))
	{
		return *Found;
	}
	// derivado: iniciales de las partes separadas por «_», o las 2 primeras letras.
	FString A, B;
	if (Verb.Split(TEXT("_"), &A, &B) && A.Len() > 0 && B.Len() > 0)
	{
		return (A.Left(1) + B.Left(1)).ToUpper();
	}
	return Verb.Left(2).ToUpper();
}

FString SJamGraphEditor::IconPathForVerb(const FString& Verb)
{
	const FString* IconName = JamIconMap().Find(Verb);
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
	if (IconName == nullptr || !Plugin.IsValid())
	{
		return FString();
	}

	const FString Path = FPaths::Combine(
		Plugin->GetBaseDir(), TEXT("Resources/Icons/Lucide"), *IconName + TEXT(".svg"));
	return IFileManager::Get().FileExists(*Path) ? Path : FString();
}

TSharedRef<SWidget> SJamGraphEditor::MakeBadge(const FLinearColor& Color, const FString& Code,
	float Size, const FString& IconPath)
{
	TSharedRef<SWidget> Glyph = SNew(STextBlock)
		.Text(FText::FromString(Code))
		.ColorAndOpacity(FLinearColor::White)
		.Font(FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(6, FMath::RoundToInt(Size * 0.42f))));

	// Los iconos PROPIOS de Jam (prefijo «jam-») traen su propio color: cada tipo de dato se dibuja
	// con el color de su pin, así que el icono enseña la firma del verbo. Los de Lucide, en cambio,
	// son máscaras blancas que hay que teñir. Se distinguen por el nombre del archivo.
	const bool bIconoPropio = FPaths::GetBaseFilename(IconPath).StartsWith(TEXT("jam-"));
	if (!IconPath.IsEmpty())
	{
		const TSharedRef<FSlateVectorImageBrush> BadgeBrush = MakeShared<FSlateVectorImageBrush>(
			IconPath, FVector2D(Size * (bIconoPropio ? 0.92f : 0.68f)),
			bIconoPropio ? FLinearColor::White : FLinearColor(0.08f, 0.08f, 0.09f, 1.0f));
		Glyph = SNew(SImage)
			.Image_Lambda([BadgeBrush]() -> const FSlateBrush* { return &BadgeBrush.Get(); });
	}

	// Un icono a color necesita fondo neutro para que sus propios colores se lean; uno teñido de
	// tinta necesita el color de categoría detrás.
	const FLinearColor Fondo = bIconoPropio ? FLinearColor(0.94f, 0.94f, 0.95f, 1.0f) : Color;
	return SNew(SBox).WidthOverride(Size).HeightOverride(Size)
	[
		SNew(SBorder)
		.BorderImage(FAppStyle::GetBrush("WhiteBrush"))
		.BorderBackgroundColor(Fondo)
		.HAlign(HAlign_Center).VAlign(VAlign_Center)
		.Padding(0.0f)
		[
			Glyph
		]
	];
}

void SJamGraphEditor::RebuildTabContent()
{
	if (!TabContentBox.IsValid())
	{
		return;
	}
	TabContentBox->ClearChildren();

	if (ActiveTab == JamLearnTab)
	{
		RebuildLearnTab();
		return;
	}

	// El tab se parte en SUBGRUPOS (los «paneles» de Grasshopper) y cada uno apila `RibbonRows`
	// filas. El spec ya llega ordenado por la tabla de layout de `jam/ribbon.py`, así que basta con
	// respetar el orden de aparición: agrupar sin reordenar.
	TArray<FString> GroupOrder;
	TMap<FString, TArray<const FJamTool*>> ByGroup;
	for (const FJamTool& T : Tools)
	{
		if (T.Cat != ActiveTab)
		{
			continue;
		}
		if (!ByGroup.Contains(T.Group))
		{
			GroupOrder.Add(T.Group);
		}
		ByGroup.FindOrAdd(T.Group).Add(&T);
	}

	for (int32 GroupIndex = 0; GroupIndex < GroupOrder.Num(); ++GroupIndex)
	{
		const TArray<const FJamTool*>& Verbs = ByGroup[GroupOrder[GroupIndex]];
		// Relleno por COLUMNAS: se lee de arriba abajo y se salta a la derecha. Es lo que hace
		// Grasshopper, y mantiene juntos los verbos vecinos de la tabla aunque cambie el alto.
		const int32 Columns = FMath::DivideAndRoundUp(Verbs.Num(), RibbonRows);
		TSharedRef<SHorizontalBox> Grid = SNew(SHorizontalBox);
		for (int32 Column = 0; Column < Columns; ++Column)
		{
			TSharedRef<SVerticalBox> ColumnBox = SNew(SVerticalBox);
			for (int32 Row = 0; Row < RibbonRows; ++Row)
			{
				const int32 Index = Column * RibbonRows + Row;
				if (!Verbs.IsValidIndex(Index))
				{
					break;   // la última columna queda corta, no se rellena con huecos
				}
				const FJamTool& T = *Verbs[Index];
				const FString Verb = T.Verb;
				// Sólo el icono; el nombre y la FIRMA DE TIPOS van en el tooltip. «S → M» dice más
				// que cualquier nombre a la hora de decidir si un verbo sirve donde estás parado.
				const FString Firma = T.bSource
					? FString::Printf(TEXT("\u2192 %s"), *T.OutName)
					: FString::Printf(TEXT("%s \u2192 %s"), *T.InName, *T.OutName);
				ColumnBox->AddSlot().AutoHeight().Padding(1.0f)
				[
					SNew(SButton)
					.ToolTipText(FText::FromString(FString::Printf(
						TEXT("%s   [%s]\n%s"), *T.Verb, *Firma, *T.Doc)))
					.ContentPadding(FMargin(1.0f))
					.OnClicked_Lambda([this, Verb]() { AddNode(Verb); return FReply::Handled(); })
					[
						MakeBadge(CategoryColor(T.Cat), VerbCode(Verb), 30.0f, IconPathForVerb(Verb))
					]
				];
			}
			Grid->AddSlot().AutoWidth()[ ColumnBox ];
		}

		// El bloque: la grilla arriba y la etiqueta del grupo abajo, como el pie de panel de GH.
		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 0.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ Grid ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f).HAlign(HAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(GroupOrder[GroupIndex]))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.62f, 0.62f, 0.66f, 1.0f)))
			]
		];

		if (GroupIndex + 1 < GroupOrder.Num())
		{
			TabContentBox->AddSlot().AutoWidth().Padding(2.0f, 2.0f)
			[
				SNew(SSeparator).Orientation(Orient_Vertical).Thickness(1.0f)
			];
		}
	}
}

void SJamGraphEditor::RebuildLearnTab()
{
	// Mismo dibujo que un tab de verbos —fichas con icono, agrupadas, con el nombre del panel
	// abajo— para que se sienta parte del mismo ribbon y no una pantalla aparte. Las diferencias
	// son dos: la ficha CARGA un grafo en vez de crear un nodo, y el título va debajo del icono,
	// porque acá el nombre sí importa (un tutorial se elige por su nombre, un verbo por su firma).
	const TArray<FJamExample>& Ejemplos = JamExamples();
	if (Ejemplos.Num() == 0)
	{
		TabContentBox->AddSlot().AutoWidth().Padding(6.0f)
		[
			SNew(STextBlock).Text(LOCTEXT("NoExamples",
				"No encontré Resources/Examples/examples.json — el catálogo de tutoriales."))
		];
		return;
	}

	TArray<FString> Orden;
	TMap<FString, TArray<const FJamExample*>> PorGrupo;
	for (const FJamExample& E : Ejemplos)
	{
		if (!PorGrupo.Contains(E.Group))
		{
			Orden.Add(E.Group);
		}
		PorGrupo.FindOrAdd(E.Group).Add(&E);
	}

	for (int32 Indice = 0; Indice < Orden.Num(); ++Indice)
	{
		TSharedRef<SHorizontalBox> Fila = SNew(SHorizontalBox);
		for (const FJamExample* E : PorGrupo[Orden[Indice]])
		{
			const FString Archivo = E->File;
			const FString Mensaje = E->Message;
			Fila->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
			[
				SNew(SButton)
				.ToolTipText(FText::FromString(FString::Printf(
					TEXT("%s\n\n%s"), *E->Title, *E->Doc)))
				.ContentPadding(FMargin(3.0f))
				.OnClicked_Lambda([this, Archivo, Mensaje]()
				{
					LoadBundledExample(Archivo, FText::FromString(Mensaje));
					return FReply::Handled();
				})
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
					[ MakeBadge(CategoryColor(JamLearnTab), TEXT("EJ"), 42.0f, JamIconPath(E->Icon)) ]
					+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 2.0f, 0.0f, 0.0f)
					[
						SNew(STextBlock)
						.Text(FText::FromString(E->Title))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					]
				]
			];
		}

		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 0.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ Fila ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f).HAlign(HAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Orden[Indice]))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.62f, 0.62f, 0.66f, 1.0f)))
			]
		];

		if (Indice + 1 < Orden.Num())
		{
			TabContentBox->AddSlot().AutoWidth().Padding(2.0f, 2.0f)
			[
				SNew(SSeparator).Orientation(Orient_Vertical).Thickness(1.0f)
			];
		}
	}
}

const FJamTool* SJamGraphEditor::FindTool(const FString& Verb) const
{
	return Tools.FindByPredicate([&Verb](const FJamTool& T) { return T.Verb == Verb; });
}

SJamGraphEditor::FGNode* SJamGraphEditor::FindNode(const FString& Id)
{
	return Nodes.FindByPredicate([&Id](const FGNode& N) { return N.Id == Id; });
}

FString SJamGraphEditor::AddNode(const FString& Verb, const FVector2D* At)
{
	const FJamTool* T = FindTool(Verb);
	if (T == nullptr || !Canvas.IsValid())
	{
		return FString();
	}

	FGNode Node;
	Node.Id = FString::Printf(TEXT("n%d"), NextId++);
	Node.Verb = Verb;
	if (At != nullptr)
	{
		Node.Pos = *At;   // nace donde hiciste doble clic (como Grasshopper)
	}
	else
	{
		// cascada para que no se apilen exactamente encima
		const int32 K = Nodes.Num();
		Node.Pos = FVector2D(30.0f + (K % 4) * 190.0f, 30.0f + (K / 4) * 40.0f + (K % 4) * 20.0f);
	}

	TArray<FJamNodeParam> Params;
	// Pin «asset» EXPLÍCITO primero (es la entrada principal): se puede cablear la salida de un nodo
	// `asset` acá, o escribir el nombre. Vacío es un error de Compile; el Graph nunca hereda en silencio
	// el asset activo ni el primero de la biblioteca (esa comodidad queda limitada a la Dash Bar).
	if (T->bAssetPin)
	{
		Params.Add(FJamNodeParam(TEXT("asset"), FString(), TEXT("str"), TArray<FString>(),
			TEXT("A"), DataColor(TEXT("A"))));
		Node.PinNames.Add(TEXT("asset"));
	}
	for (const FJamParam& P : T->Params)
	{
		FString Value = P.Default;
		// El nodo «asset» nace apuntando a lo elegido en Content (Content → nodo, sin tipear).
		if (Verb == TEXT("asset") && P.Name == TEXT("name") && Value.IsEmpty() && ActiveAsset.IsSet())
		{
			Value = ActiveAsset.Get();
		}
		// Tipo + opciones del spec → el nodo pinta el widget correcto (toggle/dropdown/texto).
		TArray<FString> Opts;
		for (const TSharedPtr<FString>& O : P.Options)
		{
			if (O.IsValid()) { Opts.Add(*O); }
		}
		const FString DataType = P.DataType.IsEmpty() ? JamParamDataType(P.Name, P.Type) : P.DataType;
		Params.Add(FJamNodeParam(P.Name, Value, P.Type, Opts, DataType, DataColor(DataType)));
		Node.PinNames.Add(P.Name);
	}

	const FString Id = Node.Id;
	// Nodos FUENTE (producen el dato, no lo reciben): sin pin de entrada, convención de Grasshopper.
	// El flag viene del spec (data-driven): asset/pick/create_spline y las fuentes de flow.
	const bool bHasInput = !T->bSource;

	TSharedRef<SJamGraphNode> Widget = SNew(SJamGraphNode)
		.Verb(Verb)
		.IconPath(IconPathForVerb(Verb))
		.IconColor(CategoryColor(T->Cat))
		.OutName(T->OutName)
		.InputColor(DataColor(T->InName))
		.OutputColor(DataColor(T->OutName))
		.Params(Params)
		.HasInput(bHasInput)
		.OnDragDelta_Lambda([this, Id](const FVector2D& D)
		{
			// D viene en píxeles de pantalla; el modelo vive antes del zoom (render transform).
			if (FGNode* N = FindNode(Id)) { N->Pos += D / Zoom; }
		})
		.OnOutputClicked_Lambda([this, Id]() { OnPinClicked(Id, TEXT("out"), true); })
		.OnInputClicked_Lambda([this, Id](const FString& Pin) { OnPinClicked(Id, Pin, false); })
		.OnDeleteClicked_Lambda([this, Id]() { DeleteNode(Id); });

	Node.Widget = Widget;

	const float Height = SJamGraphNode::NodeHeight(Params.Num());
	Node.Height = Height;
	Canvas->AddSlot()
		.Position(TAttribute<FVector2D>::CreateLambda([this, Id]()
		{
			const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
			return N ? N->Pos + PanOffset : FVector2D::ZeroVector;   // el modelo no se mueve: se mueve la vista
		}))
		.Size(FVector2D(NodeWidth, Height))
		[
			Widget
		];

	Nodes.Add(Node);
	return Id;
}

void SJamGraphEditor::DeleteNode(const FString& Id)
{
	FGNode* N = FindNode(Id);
	if (N == nullptr)
	{
		return;
	}
	if (N->Widget.IsValid() && Canvas.IsValid())
	{
		Canvas->RemoveSlot(N->Widget.ToSharedRef());
	}
	Edges.RemoveAll([&Id](const FGEdge& E) { return E.From == Id || E.To == Id; });
	if (PendingSource == Id) { PendingSource.Empty(); }
	Nodes.RemoveAll([&Id](const FGNode& X) { return X.Id == Id; });
	RefreshCabledPins();   // borrar un nodo pudo dejar pines de otros sin su cable
}

int32 SJamGraphEditor::PinIndex(const FString& Id, const FString& Pin) const
{
	if (Pin == TEXT("in") || Pin == TEXT("out"))
	{
		return -1;   // header (stream / salida)
	}
	const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
	if (N == nullptr) { return -1; }
	return N->PinNames.IndexOfByKey(Pin);
}

FString SJamGraphEditor::OutputDataTypeFor(const FString& NodeId, const FString& Pin) const
{
	if (Pin != TEXT("out"))
	{
		return FString();
	}
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	return T ? T->OutName : FString();
}

FString SJamGraphEditor::InputDataTypeFor(const FString& NodeId, const FString& Pin) const
{
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	if (N == nullptr || T == nullptr)
	{
		return FString();
	}
	if (Pin == TEXT("in"))
	{
		return (!T->bSource && T->Arity != 0) ? T->InName : FString();
	}
	if (!N->PinNames.Contains(Pin))
	{
		return FString();
	}
	if (Pin == TEXT("asset") && T->bAssetPin)
	{
		return TEXT("A");
	}
	const FJamParam* P = T->Params.FindByPredicate(
		[&Pin](const FJamParam& Param) { return Param.Name == Pin; });
	return P ? (P->DataType.IsEmpty() ? JamParamDataType(P->Name, P->Type) : P->DataType) : FString();
}

/** Regla ÚNICA de compatibilidad de tipos entre un pin de salida y uno de entrada.
 *
 *  Vivía duplicada en `CanConnect` (al tender un cable) y en `LoadGraphJson` (al abrir un archivo).
 *  Agregar el comodín en una sola dejó el otro camino rechazando lo que la UI aceptaba: un ejemplo
 *  con un nodo Debug se tendía bien a mano pero no se podía abrir. Con la regla en un solo lugar el
 *  desfasaje no puede volver a pasar.
 *
 *  «*» es un pin COMODÍN: lo usa el ayudante de Debug, que dibuja cualquier cosa que llegue. */
static bool JamTiposCompatibles(const FString& OutType, const FString& InType)
{
	if (OutType.IsEmpty() || InType.IsEmpty())
	{
		return false;
	}
	return InType == TEXT("*") || OutType == InType;
}

bool SJamGraphEditor::CanConnect(const FString& From, const FString& FromPin, const FString& To,
	const FString& ToPin, FString& OutError) const
{
	if (From == To)
	{
		OutError = TEXT("un nodo no puede conectarse a sí mismo");
		return false;
	}
	const FString OutType = OutputDataTypeFor(From, FromPin);
	if (OutType.IsEmpty())
	{
		OutError = FString::Printf(TEXT("%s.%s no es una salida válida"), *From, *FromPin);
		return false;
	}
	const FString InType = InputDataTypeFor(To, ToPin);
	if (InType.IsEmpty())
	{
		OutError = FString::Printf(TEXT("%s.%s no es una entrada válida"), *To, *ToPin);
		return false;
	}
	if (!JamTiposCompatibles(OutType, InType))
	{
		OutError = FString::Printf(TEXT("tipo incompatible: %s.%s entrega %s; %s.%s espera %s"),
			*From, *FromPin, *OutType, *To, *ToPin, *InType);
		return false;
	}
	return true;
}

void SJamGraphEditor::OnPinClicked(const FString& Id, const FString& Pin, bool bOutput)
{
	// Convención de editores nodales: Alt+clic rompe las conexiones del pin. Una entrada elimina los
	// cables que llegan a ESE pin; una salida elimina todos los que parten de ella. También cancela el
	// cable fantasma para que soltar Alt no deje una conexión pendiente accidentalmente.
	if (FSlateApplication::Get().GetModifierKeys().IsAltDown())
	{
		const int32 Removed = Edges.RemoveAll([&](const FGEdge& E)
		{
			return bOutput
				? (E.From == Id && E.FromPin == Pin)
				: (E.To == Id && E.ToPin == Pin);
		});
		PendingSource.Empty();
		PendingSourcePin.Empty();
		RefreshCabledPins();
		if (WireLayer.IsValid())
		{
			WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
		}
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(Removed > 0
				? FString::Printf(TEXT("desconectado: %s.%s (%d cable%s)"),
					*Id, *Pin, Removed, Removed == 1 ? TEXT("") : TEXT("s"))
				: FString::Printf(TEXT("%s.%s no tiene conexiones"), *Id, *Pin)));
		}
		return;
	}

	if (bOutput)
	{
		PendingSource = Id;       // armar la salida
		PendingSourcePin = Pin;   // (por ahora siempre «out»)
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("conectá: %s.%s → (clic en un pin de entrada)"), *Id, *Pin)));
		}
		return;
	}
	// clic en una entrada: cierra la conexión si hay una salida armada
	if (!PendingSource.IsEmpty())
	{
		const FString SourceId = PendingSource;
		const FString SourcePin = PendingSourcePin;
		FString Error;
		if (!CanConnect(SourceId, SourcePin, Id, Pin, Error))
		{
			if (Output.IsValid())
			{
				Output->SetText(FText::FromString(FString::Printf(TEXT("conexión rechazada: %s"), *Error)));
			}
			PendingSource.Empty();
			PendingSourcePin.Empty();
			if (WireLayer.IsValid())
			{
				WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
			}
			return;
		}
		const bool bDup = Edges.ContainsByPredicate([&](const FGEdge& E)
		{
			return E.From == SourceId && E.FromPin == SourcePin && E.To == Id && E.ToPin == Pin;
		});
		int32 Replaced = 0;
		if (!bDup)
		{
			const FGNode* DestNode = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
			const FJamTool* DestTool = DestNode ? FindTool(DestNode->Verb) : nullptr;
			// Parámetros y nodos unarios reciben UN cable. Sólo aridad -1 conserva varias entradas `in`.
			if (Pin != TEXT("in") || DestTool == nullptr || DestTool->Arity != -1)
			{
				Replaced = Edges.RemoveAll([&](const FGEdge& E) { return E.To == Id && E.ToPin == Pin; });
			}
			Edges.Add(FGEdge{SourceId, SourcePin, Id, Pin});
		}
		if (Output.IsValid())
		{
			const FString Message = Replaced > 0
				? FString::Printf(TEXT("wire reemplazado: %s.%s → %s.%s"),
					*SourceId, *SourcePin, *Id, *Pin)
				: FString::Printf(TEXT("wire: %s.%s → %s.%s"),
					*SourceId, *SourcePin, *Id, *Pin);
			Output->SetText(FText::FromString(Message));
		}
	}
	PendingSource.Empty();
	PendingSourcePin.Empty();
	RefreshCabledPins();
	if (WireLayer.IsValid())
	{
		WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
	}
}

void SJamGraphEditor::RefreshCabledPins()
{
	// Por cada nodo, el conjunto de pines de parámetro que hoy reciben un cable. El pin «in» (stream) no
	// cuenta: no es un campo editable. Cada widget griseará esos inputs.
	for (FGNode& N : Nodes)
	{
		TSet<FString> Pins;
		for (const FGEdge& E : Edges)
		{
			if (E.To == N.Id && E.ToPin != TEXT("in"))
			{
				Pins.Add(E.ToPin);
			}
		}
		if (N.Widget.IsValid())
		{
			N.Widget->SetCabledPins(Pins);
		}
	}
}

FLinearColor SJamGraphEditor::DataColor(const FString& OutName)
{
	// Color por TIPO de dato (como los pines/cables tipados de Blueprint): P=stream de puntos · N=número
	// · T=texto · B=booleano · A/A[]=asset/set · AF=asset por frame · N[]=serie · H=HISM · S=spline · F=frames · M=malla procedural
	// · MT=grafo de material (el shader que se está armando, todavía sin hornear).
	if (OutName == TEXT("P")) { return FLinearColor(0.13f, 0.44f, 0.64f, 1.0f); }   // azul  (puntos)
	if (OutName == TEXT("N")) { return FLinearColor(0.82f, 0.46f, 0.10f, 1.0f); }   // ámbar (número)
	if (OutName == TEXT("N[]")) { return FLinearColor(0.92f, 0.58f, 0.16f, 1.0f); } // ámbar claro (serie)
	if (OutName == TEXT("T")) { return FLinearColor(0.52f, 0.30f, 0.66f, 1.0f); }   // violeta (texto)
	if (OutName == TEXT("B")) { return FLinearColor(0.72f, 0.16f, 0.22f, 1.0f); }   // rojo  (booleano)
	if (OutName == TEXT("A")) { return FLinearColor(0.20f, 0.52f, 0.28f, 1.0f); }   // verde (actor)
	if (OutName == TEXT("A[]")) { return FLinearColor(0.28f, 0.62f, 0.36f, 1.0f); } // verde (set assets)
	if (OutName == TEXT("AF")) { return FLinearColor(0.38f, 0.66f, 0.28f, 1.0f); }  // lima (asset/frame)
	if (OutName == TEXT("H")) { return FLinearColor(0.16f, 0.50f, 0.46f, 1.0f); }   // verde azulado (HISM)
	if (OutName == TEXT("*")) { return FLinearColor(0.72f, 0.72f, 0.76f, 1.0f); }   // gris claro (comodín: acepta cualquier cable)
	if (OutName == TEXT("S")) { return FLinearColor(0.60f, 0.42f, 0.14f, 1.0f); }   // dorado (spline)
	if (OutName == TEXT("F")) { return FLinearColor(0.70f, 0.28f, 0.48f, 1.0f); }   // rosa  (frames)
	if (OutName == TEXT("M")) { return FLinearColor(0.08f, 0.58f, 0.62f, 1.0f); }   // cian (DynamicMesh)
	// Cobre, no el dorado del tab Shader: ése cae a un pelo del dorado de `S` (spline) y dos cables
	// distintos no se pueden distinguir por un pelo.
	if (OutName == TEXT("MT")) { return FLinearColor(0.55f, 0.24f, 0.10f, 1.0f); }  // cobre (grafo de material)
	return FLinearColor(0.28f, 0.30f, 0.34f, 1.0f);                                 // neutro
}

FLinearColor SJamGraphEditor::WireColorFor(const FString& NodeId) const
{
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	return DataColor(T ? T->OutName : FString());
}

TArray<SJamGraphEditor::FJamWire> SJamGraphEditor::GetWireEndpoints() const
{
	TArray<FJamWire> Out;
	const float Half = SJamGraphNode::PinColW * 0.5f;
	for (const FGEdge& E : Edges)
	{
		const FGNode* A = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.From; });
		const FGNode* B = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.To; });
		if (A && B)
		{
			// La capa de wires NO está bajo el render transform del canvas → se aplica acá a mano.
			// Salida por el centro del pin «out» (header, derecha); entrada por el pin exacto (por su
			// índice de parámetro), como los grips por parámetro de Grasshopper.
			const float AY = SJamGraphNode::PinLocalY(-1);
			const float BY = SJamGraphNode::PinLocalY(PinIndex(E.To, E.ToPin));
			FJamWire W;
			W.A = (FVector2D(A->Pos.X + NodeWidth - Half, A->Pos.Y + AY) + PanOffset) * Zoom;
			W.B = (FVector2D(B->Pos.X + Half, B->Pos.Y + BY) + PanOffset) * Zoom;
			W.Color = WireColorFor(E.From);   // color = tipo del dato que SALE del origen
			Out.Add(W);
		}
	}
	return Out;
}

bool SJamGraphEditor::GetPendingWire(FVector2D& OutFrom, FVector2D& OutTo, FLinearColor& OutColor) const
{
	if (PendingSource.IsEmpty())
	{
		return false;
	}
	const FGNode* A = Nodes.FindByPredicate([this](const FGNode& N) { return N.Id == PendingSource; });
	if (A == nullptr)
	{
		return false;
	}
	const float Half = SJamGraphNode::PinColW * 0.5f;
	const float AY = SJamGraphNode::PinLocalY(-1);
	OutFrom = (FVector2D(A->Pos.X + NodeWidth - Half, A->Pos.Y + AY) + PanOffset) * Zoom;
	OutTo = LastMousePos;
	OutColor = WireColorFor(PendingSource);
	return true;
}

FString SJamGraphEditor::BuildJson() const
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("schema_version"), 1);
	TSharedRef<FJsonObject> NodesObj = MakeShared<FJsonObject>();
	for (const FGNode& N : Nodes)
	{
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetStringField(TEXT("verb"), N.Verb);
		TSharedRef<FJsonObject> P = MakeShared<FJsonObject>();
		if (N.Widget.IsValid())
		{
			for (const TPair<FString, FString>& KV : N.Widget->GetParamValues())
			{
				P->SetStringField(KV.Key, KV.Value);
			}
		}
		J->SetObjectField(TEXT("params"), P);
		J->SetField(TEXT("asset"), MakeShared<FJsonValueNull>());
		J->SetNumberField(TEXT("x"), N.Pos.X);
		J->SetNumberField(TEXT("y"), N.Pos.Y);
		// El flag de debug viaja con el grafo: se guarda en el .jamgraph y lo lee el runner.
		if (N.Widget.IsValid() && N.Widget->IsDebugEnabled())
		{
			J->SetBoolField(TEXT("debug"), true);
		}
		NodesObj->SetObjectField(N.Id, J);
	}
	Root->SetObjectField(TEXT("nodes"), NodesObj);

	TArray<TSharedPtr<FJsonValue>> EdgesArr;
	for (const FGEdge& E : Edges)
	{
		// [from, from_pin, to, to_pin] — conexión por pin (jam.flow lo entiende; también acepta [from,to]).
		TArray<TSharedPtr<FJsonValue>> Quad;
		Quad.Add(MakeShared<FJsonValueString>(E.From));
		Quad.Add(MakeShared<FJsonValueString>(E.FromPin));
		Quad.Add(MakeShared<FJsonValueString>(E.To));
		Quad.Add(MakeShared<FJsonValueString>(E.ToPin));
		EdgesArr.Add(MakeShared<FJsonValueArray>(Quad));
	}
	Root->SetArrayField(TEXT("edges"), EdgesArr);

	FString Json;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	FJsonSerializer::Serialize(Root, Writer);
	return Json;
}

void SJamGraphEditor::ValidateGraph()
{
	if (Nodes.Num() == 0)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("Empty", "grafo vacío — agregá nodos.")); }
		return;
	}
	const FString Json = BuildJson();
	const FString Result = OnCompileGraph.IsBound()
		? OnCompileGraph.Execute(Json) : FString(TEXT("(sin compilador)"));
	ApplyGraphResult(Result);
}

void SJamGraphEditor::RunGraph()
{
	if (Nodes.Num() == 0)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("Empty", "grafo vacío — agregá nodos.")); }
		return;
	}
	const FString Json = BuildJson();
	const FString Result = OnRunGraph.IsBound() ? OnRunGraph.Execute(Json) : FString(TEXT("(sin runner)"));
	ApplyGraphResult(Result);
	// El inspector mira la última corrida: sin esto habría que apretar «actualizar» a mano después
	// de cada Run, y lo que muestra sería del Run ANTERIOR — el peor error posible en un inspector.
	RefreshInspector();
}

void SJamGraphEditor::BakePreview()
{
	const FString Result = OnBakePreview.IsBound()
		? OnBakePreview.Execute() : FString(TEXT("(sin acción Bake)"));
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Result));
	}
}

void SJamGraphEditor::DiscardPreview()
{
	const FString Result = OnDiscardPreview.IsBound()
		? OnDiscardPreview.Execute() : FString(TEXT("(sin acción Discard)"));
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Result));
	}
}

void SJamGraphEditor::ApplyGraphResult(const FString& Result)
{

	// El runner devuelve {report, nodes:{nid:{estado,texto}}}: el reporte va al log y CADA NODO se
	// pinta con su veredicto del oráculo (verde ✓ / naranja REVISAR / rojo error), como los estados
	// de Grasshopper. Si no parsea (versión vieja), se muestra el texto tal cual.
	FString Report = Result;
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Result);
	if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())
	{
		Root->TryGetStringField(TEXT("report"), Report);
		const TSharedPtr<FJsonObject>* NodesObj = nullptr;
		if (Root->TryGetObjectField(TEXT("nodes"), NodesObj) && NodesObj)
		{
			for (FGNode& N : Nodes)
			{
				const TSharedPtr<FJsonObject>* R = nullptr;
				if (N.Widget.IsValid() && (*NodesObj)->TryGetObjectField(N.Id, R) && R)
				{
					N.Widget->SetResult((*R)->GetStringField(TEXT("estado")),
						(*R)->GetStringField(TEXT("texto")));
				}
			}
		}
	}
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Report));
	}
}


// ---- buscador de nodos (doble clic en el canvas) + pan, como el canvas de Grasshopper ----

void SJamGraphEditor::OpenSearch(const FVector2D& AtCanvas)
{
	SearchAt = AtCanvas;
	bSearchOpen = true;
	if (SearchField.IsValid())
	{
		SearchField->SetText(FText::GetEmpty());
		FSlateApplication::Get().SetKeyboardFocus(SearchField, EFocusCause::SetDirectly);
	}
	RebuildSearchResults(FString());
}

void SJamGraphEditor::CloseSearch()
{
	bSearchOpen = false;
	SearchHits.Reset();
}

void SJamGraphEditor::RebuildSearchResults(const FString& Query)
{
	SearchHits.Reset();
	if (!SearchResults.IsValid())
	{
		return;
	}
	SearchResults->ClearChildren();

	const FString Q = Query.TrimStartAndEnd();
	for (const FJamTool& T : Tools)
	{
		if (!Q.IsEmpty() && !T.Verb.Contains(Q) && !T.Doc.Contains(Q))
		{
			continue;
		}
		SearchHits.Add(T.Verb);
		const FString Verb = T.Verb;
		const FVector2D At = SearchAt;
		SearchResults->AddSlot().AutoHeight().Padding(0.0f, 1.0f)
		[
			SNew(SButton)
			.HAlign(HAlign_Left)
			.Text(FText::FromString(FString::Printf(TEXT("%s  —  %s"), *T.Verb, *T.Doc)))
			.OnClicked_Lambda([this, Verb, At]()
			{
				const FVector2D Local = LocalToModel(At);   // el nodo vive en coords del modelo
				AddNode(Verb, &Local);
				CloseSearch();
				return FReply::Handled();
			})
		];
		if (SearchHits.Num() >= 8)
		{
			break;
		}
	}
}

void SJamGraphEditor::CommitSearch()
{
	if (SearchHits.Num() > 0)
	{
		const FVector2D Local = LocalToModel(SearchAt);
		AddNode(SearchHits[0], &Local);
	}
	CloseSearch();
}

FReply SJamGraphEditor::OnMouseButtonDoubleClick(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		// El popup es hijo del overlay del CANVAS, no del editor completo. Usar MyGeometry sumaba al Y
		// la altura de menú+ribbon (~50 px), igual que el antiguo bug del cable fantasma. WireLayer llena
		// ese mismo overlay y por eso es la referencia correcta incluso con DPI o alturas distintas.
		const FVector2D AtCanvas = WireLayer.IsValid()
			? WireLayer->GetCachedGeometry().AbsoluteToLocal(MouseEvent.GetScreenSpacePosition())
			: MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
		OpenSearch(AtCanvas);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

void SJamGraphEditor::ApplyZoom()
{
	if (Canvas.IsValid())
	{
		Canvas->SetRenderTransformPivot(FVector2D::ZeroVector);
		Canvas->SetRenderTransform(FSlateRenderTransform(FScale2D(Zoom, Zoom)));
	}
}

FReply SJamGraphEditor::OnMouseWheel(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	// ZUI: la rueda acerca/aleja el lienzo entero (nodos y wires), como en Grasshopper.
	const float Antes = Zoom;
	Zoom = FMath::Clamp(Zoom * (1.0f + MouseEvent.GetWheelDelta() * 0.1f), 0.35f, 2.5f);
	if (FMath::IsNearlyEqual(Antes, Zoom))
	{
		return FReply::Handled();
	}
	// zoom "hacia el cursor": el punto del modelo bajo el mouse se queda donde está
	const FVector2D Local = MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
	PanOffset += Local / Zoom - Local / Antes;
	ApplyZoom();
	return FReply::Handled();
}

FReply SJamGraphEditor::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton
		|| MouseEvent.GetEffectingButton() == EKeys::MiddleMouseButton)
	{
		bPanning = true;
		return FReply::Handled().CaptureMouse(SharedThis(this));
	}
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton && bSearchOpen)
	{
		CloseSearch();   // clic afuera cierra el buscador
		return FReply::Handled().SetUserFocus(SharedThis(this), EFocusCause::Mouse);
	}
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		// El fondo recibe foco para deseleccionar el nodo anterior; Supr ya no puede borrar un nodo
		// después de que el usuario hizo clic en un espacio vacío del canvas.
		return FReply::Handled().SetUserFocus(SharedThis(this), EFocusCause::Mouse);
	}
	return FReply::Unhandled();
}

FReply SJamGraphEditor::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	// La geometría recibida es la del editor completo (incluye menú + ribbon), pero el cable-fantasma
	// se pinta en la capa del lienzo. Convertir desde pantalla contra ESA capa evita sumar al extremo
	// del wire la altura de la cabecera y mantiene cursor/cable alineados con cualquier DPI.
	if (WireLayer.IsValid())
	{
		LastMousePos = WireLayer->GetCachedGeometry().AbsoluteToLocal(
			MouseEvent.GetScreenSpacePosition());
	}
	if (!PendingSource.IsEmpty() && WireLayer.IsValid())
	{
		// hay una conexión en curso: repintar la capa de wires para que el cable siga al mouse.
		WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
	}
	if (bPanning && HasMouseCapture())
	{
		const float S = MyGeometry.GetAccumulatedLayoutTransform().GetScale();
		PanOffset += MouseEvent.GetCursorDelta() / ((S > 0.0f ? S : 1.0f) * Zoom);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SJamGraphEditor::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bPanning && (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton
		|| MouseEvent.GetEffectingButton() == EKeys::MiddleMouseButton))
	{
		bPanning = false;
		return FReply::Handled().ReleaseMouseCapture();
	}
	return FReply::Unhandled();
}

// ---- menú principal estilo Grasshopper ----

void SJamGraphEditor::FillFileMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("New", "Nuevo"), LOCTEXT("NewTip", "Vaciar el grafo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::NewGraph)));
	MB.AddMenuEntry(LOCTEXT("Open", "Abrir diagrama…"), LOCTEXT("OpenTip", "Cargar un .jamgraph"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::OpenDiagram)));
	// Los ejemplos vivían acá, como cinco «Abrir ejemplo: …». Están en el tab «Aprender», que es un
	// lugar donde alguien que recién empieza los va a encontrar sin abrir un menú.
	MB.AddMenuSeparator();
	MB.AddMenuEntry(LOCTEXT("Save", "Guardar"), LOCTEXT("SaveTip", "Guardar en el archivo actual"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::SaveDiagram, false)));
	MB.AddMenuEntry(LOCTEXT("SaveAs", "Guardar como…"), LOCTEXT("SaveAsTip", "Elegir archivo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::SaveDiagram, true)));
}

void SJamGraphEditor::FillEditMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("ClearAll", "Vaciar el grafo"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::NewGraph)));
}

void SJamGraphEditor::FillViewMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("ResetView", "Reencuadrar (reset zoom/pan)"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::ResetView)));
}

void SJamGraphEditor::FillDisplayMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("Gallery", "Galería: insertar todos los nodos"),
		LOCTEXT("GalleryTip", "Reemplaza el grafo por UNO DE CADA nodo en grilla (para un screenshot)"),
		FSlateIcon(), FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::InsertAllNodes)));
}

void SJamGraphEditor::FillSolutionMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("CompileGraph", "Compile / Validate"),
		LOCTEXT("CompileGraphTip", "Valida todo el grafo sin ejecutar ni modificar la escena"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::ValidateGraph)));
	MB.AddMenuEntry(LOCTEXT("Recompute", "Run graph (recompute)"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::RunGraph)));
	MB.AddMenuSeparator();
	MB.AddMenuEntry(LOCTEXT("BakeGraphPreview", "Bake / Confirm Preview"),
		LOCTEXT("BakeGraphPreviewTip", "Fija el Preview creado por este Graph"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::BakePreview)));
	MB.AddMenuEntry(LOCTEXT("DiscardGraphPreview", "Discard Preview"),
		LOCTEXT("DiscardGraphPreviewTip", "Elimina el Preview creado por este Graph"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::DiscardPreview)));
}

void SJamGraphEditor::NewGraph()
{
	if (Canvas.IsValid())
	{
		for (const FGNode& N : Nodes)
		{
			if (N.Widget.IsValid())
			{
				Canvas->RemoveSlot(N.Widget.ToSharedRef());
			}
		}
	}
	Nodes.Reset();
	Edges.Reset();
	PendingSource.Empty();
	PendingSourcePin.Empty();
	NextId = 1;
	// `New` inicia un DOCUMENTO nuevo. Conservar esta ruta hacía que el Save siguiente sobrescribiera
	// silenciosamente el .jamgraph anterior.
	CurrentPath.Empty();
	if (Output.IsValid())
	{
		Output->SetText(LOCTEXT("NewDone", "grafo vacío."));
	}
}

bool SJamGraphEditor::LoadGraphJson(const FString& Json)
{
	auto Fail = [this](const FString& Message)
	{
		if (Output.IsValid()) { Output->SetText(FText::FromString(Message)); }
		return false;
	};

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return Fail(TEXT("el archivo no es JSON válido; el grafo actual no se modificó."));
	}
	double SchemaVersion = 1.0;
	if (Root->HasField(TEXT("schema_version"))
		&& !Root->TryGetNumberField(TEXT("schema_version"), SchemaVersion))
	{
		return Fail(TEXT("schema_version debe ser numérico; el grafo actual no se modificó."));
	}
	if (SchemaVersion > 1.0)
	{
		return Fail(FString::Printf(
			TEXT("schema_version %.0f no soportada (máxima: 1); el grafo actual no se modificó."),
			SchemaVersion));
	}

	struct FLoadedNode
	{
		FString FileId;
		FString Verb;
		FVector2D Pos;
		TMap<FString, FString> Params;
		bool bDebug = false;
	};
	struct FLoadedEdge
	{
		FString From;
		FString FromPin;
		FString To;
		FString ToPin;
	};

	// Fase 1: validar y convertir TODO a un modelo temporal. Hasta completar esta fase no se llama a
	// NewGraph ni se toca CurrentPath, selección, zoom o widgets actuales.
	TArray<FLoadedNode> LoadedNodes;
	TMap<FString, int32> LoadedNodeIndex;
	const TSharedPtr<FJsonObject>* NodesObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("nodes"), NodesObj) || NodesObj == nullptr)
	{
		return Fail(TEXT("el diagrama no contiene un objeto 'nodes'; el grafo actual no se modificó."));
	}
	for (const TPair<FString, TSharedPtr<FJsonValue>>& KV : (*NodesObj)->Values)
	{
		const TSharedPtr<FJsonObject> NO = KV.Value.IsValid() ? KV.Value->AsObject() : nullptr;
		if (!NO.IsValid())
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' no es un objeto JSON."), *KV.Key));
		}
		FString Verb;
		double X = 0.0, Y = 0.0;
		if (!NO->TryGetStringField(TEXT("verb"), Verb) || Verb.IsEmpty())
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' no declara un verbo válido."), *KV.Key));
		}
		const FJamTool* Tool = FindTool(Verb);
		if (Tool == nullptr)
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' usa el verbo desconocido '%s'."),
				*KV.Key, *Verb));
		}
		if (!NO->TryGetNumberField(TEXT("x"), X) || !NO->TryGetNumberField(TEXT("y"), Y))
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' necesita posiciones x/y numéricas."), *KV.Key));
		}

		FLoadedNode Loaded{KV.Key, Verb, FVector2D(X, Y), {}};
		// El flag de debug es OPCIONAL: un .jamgraph viejo sin el campo carga con el flag apagado.
		NO->TryGetBoolField(TEXT("debug"), Loaded.bDebug);
		const TSharedPtr<FJsonObject>* ParamsObj = nullptr;
		if (NO->HasField(TEXT("params"))
			&& (!NO->TryGetObjectField(TEXT("params"), ParamsObj) || ParamsObj == nullptr))
		{
			return Fail(FString::Printf(TEXT("params de '%s' debe ser un objeto."), *KV.Key));
		}
		if (ParamsObj != nullptr)
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& PV : (*ParamsObj)->Values)
			{
				const bool bKnownParam = (PV.Key == TEXT("asset") && Tool->bAssetPin)
					|| Tool->Params.ContainsByPredicate(
						[&PV](const FJamParam& Param) { return Param.Name == PV.Key; });
				if (!bKnownParam)
				{
					return Fail(FString::Printf(TEXT("parámetro desconocido '%s' en nodo '%s'."),
						*PV.Key, *KV.Key));
				}
				FString Value;
				double Number = 0.0;
				bool Boolean = false;
				if (PV.Value.IsValid() && PV.Value->TryGetString(Value)) {}
				else if (PV.Value.IsValid() && PV.Value->TryGetNumber(Number))
				{
					Value = FString::Printf(TEXT("%.17g"), Number);
				}
				else if (PV.Value.IsValid() && PV.Value->TryGetBool(Boolean))
				{
					Value = Boolean ? TEXT("True") : TEXT("False");
				}
				else
				{
					return Fail(FString::Printf(
						TEXT("parámetro '%s' de '%s' debe ser string, número o booleano."),
						*PV.Key, *KV.Key));
				}
				Loaded.Params.Add(PV.Key, Value);
			}
		}
		LoadedNodeIndex.Add(KV.Key, LoadedNodes.Num());
		LoadedNodes.Add(MoveTemp(Loaded));
	}

	TArray<FLoadedEdge> LoadedEdges;
	const TArray<TSharedPtr<FJsonValue>>* EdgesArr = nullptr;
	if (Root->HasField(TEXT("edges"))
		&& (!Root->TryGetArrayField(TEXT("edges"), EdgesArr) || EdgesArr == nullptr))
	{
		return Fail(TEXT("'edges' debe ser un array; el grafo actual no se modificó."));
	}
	if (EdgesArr != nullptr)
	{
		TSet<FString> SeenEdges;
		TSet<FString> OccupiedInputs;
		for (int32 EdgeIndex = 0; EdgeIndex < EdgesArr->Num(); ++EdgeIndex)
		{
			const TSharedPtr<FJsonValue>& EV = (*EdgesArr)[EdgeIndex];
			const TArray<TSharedPtr<FJsonValue>>* E = nullptr;
			if (!EV.IsValid() || !EV->TryGetArray(E) || E == nullptr || (E->Num() != 2 && E->Num() != 4))
			{
				return Fail(FString::Printf(TEXT("edge %d debe tener 2 o 4 strings."), EdgeIndex));
			}
			FString From, FromPin = TEXT("out"), To, ToPin = TEXT("in");
			const bool bStrings = E->Num() == 2
				? (*E)[0]->TryGetString(From) && (*E)[1]->TryGetString(To)
				: (*E)[0]->TryGetString(From) && (*E)[1]->TryGetString(FromPin)
					&& (*E)[2]->TryGetString(To) && (*E)[3]->TryGetString(ToPin);
			if (!bStrings)
			{
				return Fail(FString::Printf(TEXT("edge %d contiene un endpoint no textual."), EdgeIndex));
			}
			const int32* FromIdx = LoadedNodeIndex.Find(From);
			const int32* ToIdx = LoadedNodeIndex.Find(To);
			if (FromIdx == nullptr || ToIdx == nullptr)
			{
				return Fail(FString::Printf(TEXT("edge %d referencia un nodo inexistente."), EdgeIndex));
			}
			const FJamTool* FromTool = FindTool(LoadedNodes[*FromIdx].Verb);
			const FJamTool* ToTool = FindTool(LoadedNodes[*ToIdx].Verb);
			const FString OutType = (FromPin == TEXT("out") && FromTool) ? FromTool->OutName : FString();
			FString InType;
			if (ToPin == TEXT("in") && ToTool && !ToTool->bSource && ToTool->Arity != 0)
			{
				InType = ToTool->InName;
			}
			else if (ToPin == TEXT("asset") && ToTool && ToTool->bAssetPin)
			{
				InType = TEXT("A");
			}
			else if (ToTool)
			{
				if (const FJamParam* Param = ToTool->Params.FindByPredicate(
					[&ToPin](const FJamParam& P) { return P.Name == ToPin; }))
				{
					InType = Param->DataType.IsEmpty()
						? JamParamDataType(Param->Name, Param->Type) : Param->DataType;
				}
			}
			if (!JamTiposCompatibles(OutType, InType))
			{
				return Fail(FString::Printf(TEXT("edge %d tiene pines o tipos incompatibles."), EdgeIndex));
			}
			const FString EdgeKey = From + TEXT("\x1f") + FromPin + TEXT("\x1f") + To + TEXT("\x1f") + ToPin;
			if (SeenEdges.Contains(EdgeKey))
			{
				return Fail(FString::Printf(TEXT("edge %d está duplicado."), EdgeIndex));
			}
			SeenEdges.Add(EdgeKey);
			const bool bSingle = ToPin != TEXT("in") || ToTool == nullptr || ToTool->Arity != -1;
			const FString InputKey = To + TEXT("\x1f") + ToPin;
			if (bSingle && OccupiedInputs.Contains(InputKey))
			{
				return Fail(FString::Printf(TEXT("el pin %s.%s recibe más de un cable."), *To, *ToPin));
			}
			if (bSingle) { OccupiedInputs.Add(InputKey); }
			LoadedEdges.Add(FLoadedEdge{From, FromPin, To, ToPin});
		}
	}

	// Fase 2: el modelo completo es válido; recién ahora reemplazar el documento visible.
	NewGraph();
	TMap<FString, FString> IdMap;
	for (const FLoadedNode& Loaded : LoadedNodes)
	{
		const FString NewId = AddNode(Loaded.Verb, &Loaded.Pos);
		if (NewId.IsEmpty())
		{
			return Fail(FString::Printf(TEXT("no pude crear el nodo validado '%s'."), *Loaded.FileId));
		}
		IdMap.Add(Loaded.FileId, NewId);
		if (FGNode* Node = FindNode(NewId); Node && Node->Widget.IsValid())
		{
			Node->Widget->SetParamValues(Loaded.Params);
			Node->Widget->SetDebugEnabled(Loaded.bDebug);
		}
	}
	for (const FLoadedEdge& Loaded : LoadedEdges)
	{
		Edges.Add(FGEdge{IdMap[Loaded.From], Loaded.FromPin, IdMap[Loaded.To], Loaded.ToPin});
	}
	RefreshCabledPins();   // reflejar en los inputs los cables recién cargados
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(
			FString::Printf(TEXT("cargado: %d nodos, %d wires."), Nodes.Num(), Edges.Num())));
	}
	return true;
}

void SJamGraphEditor::SaveDiagram(bool bForceDialog)
{
	FString Path = CurrentPath;
	if (Path.IsEmpty() || bForceDialog)
	{
		IDesktopPlatform* DP = FDesktopPlatformModule::Get();
		if (DP == nullptr) { return; }
		const FString Dir = FPaths::ProjectSavedDir() / TEXT("JamGraphs");
		IFileManager::Get().MakeDirectory(*Dir, true);
		TArray<FString> Files;
		const bool bOk = DP->SaveFileDialog(nullptr, TEXT("Guardar diagrama Jam"), Dir,
			TEXT("diagrama.jamgraph"), TEXT("Jam Graph (*.jamgraph)|*.jamgraph|JSON (*.json)|*.json"),
			EFileDialogFlags::None, Files);
		if (!bOk || Files.Num() == 0) { return; }
		Path = Files[0];
	}
	const FString TempPath = Path + TEXT(".tmp");
	IFileManager::Get().Delete(*TempPath, false, true, true);
	const bool bWroteTemp = FFileHelper::SaveStringToFile(BuildJson(), *TempPath);
	const bool bPromoted = bWroteTemp
		&& IFileManager::Get().Move(*Path, *TempPath, true, true, false, true);
	if (bPromoted)
	{
		CurrentPath = Path;
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(TEXT("guardado: %s"), *Path)));
		}
	}
	else if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("ERROR: no se pudo guardar %s; el archivo anterior no se modificó."), *Path)));
	}
	IFileManager::Get().Delete(*TempPath, false, true, true);
}

void SJamGraphEditor::OpenDiagram()
{
	IDesktopPlatform* DP = FDesktopPlatformModule::Get();
	if (DP == nullptr) { return; }
	const FString Dir = FPaths::ProjectSavedDir() / TEXT("JamGraphs");
	TArray<FString> Files;
	const bool bOk = DP->OpenFileDialog(nullptr, TEXT("Abrir diagrama Jam"), Dir, TEXT(""),
		TEXT("Jam Graph (*.jamgraph)|*.jamgraph|JSON (*.json)|*.json"), EFileDialogFlags::None, Files);
	if (!bOk || Files.Num() == 0) { return; }
	FString Json;
	if (FFileHelper::LoadFileToString(Json, *Files[0]))
	{
		if (LoadGraphJson(Json))
		{
			CurrentPath = Files[0];
		}
	}
}

void SJamGraphEditor::LoadBundledExample(const FString& Filename, const FText& LoadedMessage)
{
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
	if (!Plugin.IsValid())
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("TreeExampleNoPlugin", "ERROR: no encontré el plugin Jam.")); }
		return;
	}
	const FString Path = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Resources/Examples"), Filename);
	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("ERROR: no pude leer el ejemplo: %s"), *Path)));
		}
		return;
	}
	if (LoadGraphJson(Json))
	{
		// Es una plantilla: Guardar debe pedir una ruta y nunca escribir sobre el archivo distribuido.
		CurrentPath.Empty();
		if (Output.IsValid())
		{
			Output->SetText(LoadedMessage);
		}
	}
}

void SJamGraphEditor::InsertAllNodes()
{
	NewGraph();
	// una ficha de CADA verbo/op, en grilla, agrupadas por su orden en el spec. Alto generoso para que
	// los nodos altos (place tiene muchos params) no pisen la fila de abajo.
	const int32 Cols = 6;
	const float StepX = 210.0f;
	const float StepY = 340.0f;
	int32 K = 0;
	for (const FJamTool& T : Tools)
	{
		const FVector2D At(30.0f + (K % Cols) * StepX, 30.0f + (K / Cols) * StepY);
		AddNode(T.Verb, &At);
		++K;
	}
	ResetView();
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("galería: %d nodos (uno de cada tipo). Reencuadrá con la rueda para el screenshot."),
			Nodes.Num())));
	}
}

void SJamGraphEditor::ResetView()
{
	PanOffset = FVector2D(20.0f, 20.0f);
	Zoom = 1.0f;
	ApplyZoom();
}

#undef LOCTEXT_NAMESPACE
