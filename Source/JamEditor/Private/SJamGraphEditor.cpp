#include "SJamGraphEditor.h"
#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SCanvas.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
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

// Capa de fondo del canvas (como el de Grasshopper): pinta el color de fondo, una GRILLA fina
// alineada al pan/zoom, y los WIRES (splines) — todo detrás de los nodos.
class SJamWireLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamWireLayer) {}
	SLATE_END_ARGS()

	void Construct(const FArguments&,
		TFunction<TArray<TPair<FVector2D, FVector2D>>()> InGetter,
		TFunction<void(FVector2D&, float&)> InXform)
	{
		Getter = MoveTemp(InGetter);
		XformGetter = MoveTemp(InXform);
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

		// Wires (splines) entre nodos, sobre la grilla.
		if (Getter)
		{
			const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry();
			const FLinearColor Tint(0.20f, 0.22f, 0.25f, 0.95f);
			for (const TPair<FVector2D, FVector2D>& W : Getter())
			{
				const float dx = FMath::Max(50.0f, FMath::Abs(W.Value.X - W.Key.X) * 0.6f);
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 2, PG,
					W.Key, FVector2D(dx, 0.0f), W.Value, FVector2D(dx, 0.0f), 2.2f,
					ESlateDrawEffect::None, Tint);
			}
		}
		return LayerId + 2;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<TArray<TPair<FVector2D, FVector2D>>()> Getter;
	TFunction<void(FVector2D&, float&)> XformGetter;
};


void SJamGraphEditor::Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools)
{
	Tools = InTools;
	OnRunGraph = InArgs._OnRunGraph;
	OnSaveGraph = InArgs._OnSaveGraph;
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
	for (const FString& Cat : Categories)
	{
		TabStrip->AddSlot().AutoWidth().Padding(1.0f, 0.0f)
		[
			SNew(SButton)
			.ToolTipText(FText::FromString(FString::Printf(TEXT("Tab «%s»"), *Cat)))
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
					SNew(SJamWireLayer,
						TFunction<TArray<TPair<FVector2D, FVector2D>>()>(
							[this]() { return GetWireEndpoints(); }),
						TFunction<void(FVector2D&, float&)>(
							[this](FVector2D& P, float& Z) { P = PanOffset; Z = Zoom; }))
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

		// Run + salida.
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(SButton).Text(LOCTEXT("Run", "▶ Run graph"))
				.OnClicked_Lambda([this]() { RunGraph(); return FReply::Handled(); })
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
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f, 6.0f, 6.0f).MaxHeight(140.0f)
		[
			SAssignNew(Output, SMultiLineEditableTextBox).IsReadOnly(true).AllowMultiLine(true)
		]
	];

	RebuildTabContent();   // abre el primer tab con sus fichas
}


// ---- Ribbon estilo Grasshopper: tabs + fichas con icono ----

FLinearColor SJamGraphEditor::CategoryColor(const FString& Cat)
{
	// un tono por categoría (como los tabs de Grasshopper): tools + flow.
	if (Cat == TEXT("Content"))  { return FLinearColor(0.40f, 0.44f, 0.50f, 1.0f); }
	if (Cat == TEXT("Place"))    { return FLinearColor(0.20f, 0.52f, 0.72f, 1.0f); }
	if (Cat == TEXT("Scatter"))  { return FLinearColor(0.24f, 0.60f, 0.32f, 1.0f); }
	if (Cat == TEXT("Create"))   { return FLinearColor(0.62f, 0.34f, 0.66f, 1.0f); }
	if (Cat == TEXT("Edit"))     { return FLinearColor(0.72f, 0.50f, 0.16f, 1.0f); }
	if (Cat == TEXT("Params"))   { return FLinearColor(0.44f, 0.44f, 0.48f, 1.0f); }
	if (Cat == TEXT("Maths"))    { return FLinearColor(0.78f, 0.28f, 0.42f, 1.0f); }
	if (Cat == TEXT("Source"))   { return FLinearColor(0.24f, 0.58f, 0.40f, 1.0f); }
	if (Cat == TEXT("Mask"))     { return FLinearColor(0.78f, 0.46f, 0.14f, 1.0f); }
	if (Cat == TEXT("Combine"))  { return FLinearColor(0.26f, 0.46f, 0.70f, 1.0f); }
	if (Cat == TEXT("Output"))   { return FLinearColor(0.58f, 0.30f, 0.62f, 1.0f); }
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
		{TEXT("number"), TEXT("N#")}, {TEXT("math"), TEXT("fx")},
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

TSharedRef<SWidget> SJamGraphEditor::MakeBadge(const FLinearColor& Color, const FString& Code, float Size)
{
	return SNew(SBox).WidthOverride(Size).HeightOverride(Size)
	[
		SNew(SBorder)
		.BorderImage(FAppStyle::GetBrush("WhiteBrush"))
		.BorderBackgroundColor(Color)
		.HAlign(HAlign_Center).VAlign(VAlign_Center)
		.Padding(0.0f)
		[
			SNew(STextBlock)
			.Text(FText::FromString(Code))
			.ColorAndOpacity(FLinearColor::White)
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(6, FMath::RoundToInt(Size * 0.42f))))
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
	for (const FJamTool& T : Tools)
	{
		if (T.Cat != ActiveTab)
		{
			continue;
		}
		const FString Verb = T.Verb;
		const FLinearColor Color = CategoryColor(T.Cat);
		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 2.0f)
		[
			SNew(SButton)
			.ToolTipText(FText::FromString(FString::Printf(TEXT("%s — %s"), *T.Verb, *T.Doc)))
			.ContentPadding(FMargin(3.0f, 3.0f))
			.OnClicked_Lambda([this, Verb]() { AddNode(Verb); return FReply::Handled(); })
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
				[ MakeBadge(Color, VerbCode(Verb), 30.0f) ]
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
	// `asset` acá, o escribir el nombre. Sin cable ni texto, cae al asset activo/heredado como antes.
	if (T->bAssetPin)
	{
		Params.Add(FJamNodeParam(TEXT("asset"), FString()));
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
		Params.Add(FJamNodeParam(P.Name, Value));
		Node.PinNames.Add(P.Name);
	}

	const FString Id = Node.Id;
	// Nodos FUENTE (producen el dato, no lo reciben): sin pin de entrada, convención de Grasshopper.
	// El flag viene del spec (data-driven): asset/pick/create_spline y las fuentes de flow.
	const bool bHasInput = !T->bSource;

	TSharedRef<SJamGraphNode> Widget = SNew(SJamGraphNode)
		.Verb(Verb)
		.Icon(VerbCode(Verb))
		.IconColor(CategoryColor(T->Cat))
		.OutName(T->OutName)
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

void SJamGraphEditor::OnPinClicked(const FString& Id, const FString& Pin, bool bOutput)
{
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
	if (!PendingSource.IsEmpty() && PendingSource != Id)
	{
		const bool bDup = Edges.ContainsByPredicate([&](const FGEdge& E)
		{
			return E.From == PendingSource && E.FromPin == PendingSourcePin && E.To == Id && E.ToPin == Pin;
		});
		if (!bDup)
		{
			// un pin de entrada acepta UN cable (salvo «in», que junta varios): reemplazá el previo.
			if (Pin != TEXT("in"))
			{
				Edges.RemoveAll([&](const FGEdge& E) { return E.To == Id && E.ToPin == Pin; });
			}
			Edges.Add(FGEdge{PendingSource, PendingSourcePin, Id, Pin});
		}
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("wire: %s.%s → %s.%s"), *PendingSource, *PendingSourcePin, *Id, *Pin)));
		}
	}
	PendingSource.Empty();
	PendingSourcePin.Empty();
}

TArray<TPair<FVector2D, FVector2D>> SJamGraphEditor::GetWireEndpoints() const
{
	TArray<TPair<FVector2D, FVector2D>> Out;
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
			Out.Add(TPair<FVector2D, FVector2D>(
				(FVector2D(A->Pos.X + NodeWidth - Half, A->Pos.Y + AY) + PanOffset) * Zoom,
				(FVector2D(B->Pos.X + Half, B->Pos.Y + BY) + PanOffset) * Zoom));
		}
	}
	return Out;
}

FString SJamGraphEditor::BuildJson() const
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
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

void SJamGraphEditor::RunGraph()
{
	if (Nodes.Num() == 0)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("Empty", "grafo vacío — agregá nodos.")); }
		return;
	}
	const FString Json = BuildJson();
	const FString Result = OnRunGraph.IsBound() ? OnRunGraph.Execute(Json) : FString(TEXT("(sin runner)"));

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

void SJamGraphEditor::OpenSearch(const FVector2D& AtLocal)
{
	SearchAt = AtLocal;
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
		OpenSearch(MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition()));
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
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SJamGraphEditor::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
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
	MB.AddMenuEntry(LOCTEXT("Recompute", "Run graph (recompute)"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::RunGraph)));
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
	if (Output.IsValid())
	{
		Output->SetText(LOCTEXT("NewDone", "grafo vacío."));
	}
}

void SJamGraphEditor::LoadGraphJson(const FString& Json)
{
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("BadFile", "el archivo no es un diagrama válido.")); }
		return;
	}
	NewGraph();

	// nodos: crear por verbo, fijar posición y valores de params; mapear id-de-archivo → id-nuevo.
	TMap<FString, FString> IdMap;
	const TSharedPtr<FJsonObject>* NodesObj = nullptr;
	if (Root->TryGetObjectField(TEXT("nodes"), NodesObj) && NodesObj)
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& KV : (*NodesObj)->Values)
		{
			const TSharedPtr<FJsonObject> NO = KV.Value->AsObject();
			if (!NO.IsValid()) { continue; }
			const FString Verb = NO->GetStringField(TEXT("verb"));
			const FString NewId = AddNode(Verb);
			if (NewId.IsEmpty()) { continue; }
			IdMap.Add(KV.Key, NewId);
			if (FGNode* N = FindNode(NewId))
			{
				N->Pos = FVector2D(NO->GetNumberField(TEXT("x")), NO->GetNumberField(TEXT("y")));
				const TSharedPtr<FJsonObject>* PO = nullptr;
				if (NO->TryGetObjectField(TEXT("params"), PO) && PO && N->Widget.IsValid())
				{
					TMap<FString, FString> Vals;
					for (const TPair<FString, TSharedPtr<FJsonValue>>& PV : (*PO)->Values)
					{
						FString S;
						if (PV.Value->TryGetString(S)) { Vals.Add(PV.Key, S); }
					}
					N->Widget->SetParamValues(Vals);
				}
			}
		}
	}
	// aristas: [from,to] o [from,from_pin,to,to_pin], con ids traducidos.
	const TArray<TSharedPtr<FJsonValue>>* EdgesArr = nullptr;
	if (Root->TryGetArrayField(TEXT("edges"), EdgesArr) && EdgesArr)
	{
		for (const TSharedPtr<FJsonValue>& EV : *EdgesArr)
		{
			const TArray<TSharedPtr<FJsonValue>>* E = nullptr;
			if (!EV->TryGetArray(E) || !E) { continue; }
			FString From, FromPin = TEXT("out"), To, ToPin = TEXT("in");
			if (E->Num() == 2) { From = (*E)[0]->AsString(); To = (*E)[1]->AsString(); }
			else if (E->Num() == 4)
			{
				From = (*E)[0]->AsString(); FromPin = (*E)[1]->AsString();
				To = (*E)[2]->AsString();   ToPin = (*E)[3]->AsString();
			}
			const FString* NF = IdMap.Find(From);
			const FString* NT = IdMap.Find(To);
			if (NF && NT) { Edges.Add(FGEdge{*NF, FromPin, *NT, ToPin}); }
		}
	}
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(TEXT("cargado: %d nodos, %d wires."),
			Nodes.Num(), Edges.Num())));
	}
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
	if (FFileHelper::SaveStringToFile(BuildJson(), *Path))
	{
		CurrentPath = Path;
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(TEXT("guardado: %s"), *Path)));
		}
	}
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
		LoadGraphJson(Json);
		CurrentPath = Files[0];
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
