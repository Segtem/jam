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
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Framework/Application/SlateApplication.h"
#include "Styling/AppStyle.h"
#include "Rendering/DrawElements.h"
#include "Math/TransformCalculus2D.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Dom/JsonObject.h"

#define LOCTEXT_NAMESPACE "JamGraphEditor"

// Capa que dibuja los wires (splines) detrás de los nodos. Pide los endpoints por delegate.
class SJamWireLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamWireLayer) {}
		SLATE_EVENT(FSimpleDelegate, Unused)
	SLATE_END_ARGS()

	void Construct(const FArguments&, TFunction<TArray<TPair<FVector2D, FVector2D>>()> InGetter)
	{
		Getter = MoveTemp(InGetter);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		if (Getter)
		{
			const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry();
			const FLinearColor Tint(0.55f, 0.75f, 1.0f, 1.0f);
			for (const TPair<FVector2D, FVector2D>& W : Getter())
			{
				const float dx = FMath::Max(50.0f, FMath::Abs(W.Value.X - W.Key.X) * 0.6f);
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId, PG,
					W.Key, FVector2D(dx, 0.0f), W.Value, FVector2D(dx, 0.0f), 2.0f,
					ESlateDrawEffect::None, Tint);
			}
		}
		return LayerId;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<TArray<TPair<FVector2D, FVector2D>>()> Getter;
};


void SJamGraphEditor::Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools)
{
	Tools = InTools;
	OnRunGraph = InArgs._OnRunGraph;
	OnSaveGraph = InArgs._OnSaveGraph;
	ActiveAsset = InArgs._ActiveAsset;
	OnOpenContent = InArgs._OnOpenContent;

	// Paleta agrupada por categoría (como Dash): un combo por categoría → sus nodos. Con verbos +
	// flow serían ~21 botones sueltos; agrupados es navegable. El doble clic en el lienzo busca igual.
	TSharedRef<SHorizontalBox> Palette = SNew(SHorizontalBox);
	Palette->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
	[
		SNew(SButton)
		.Text(LOCTEXT("PaletteContent", "Content…"))
		.ToolTipText(LOCTEXT("PaletteContentTip", "Elegir el asset activo (abre la ventana de Content)"))
		.OnClicked_Lambda([this]() { OnOpenContent.ExecuteIfBound(); return FReply::Handled(); })
	];
	// orden de categorías: primero las de las tools, después las de flow
	TArray<FString> Cats;
	for (const FJamTool& T : Tools)
	{
		Cats.AddUnique(T.Cat);
	}
	for (const FString& Cat : Cats)
	{
		Palette->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
		[
			SNew(SComboButton)
			.ButtonContent()[ SNew(STextBlock).Text(FText::FromString(Cat)) ]
			.OnGetMenuContent_Lambda([this, Cat]()
			{
				FMenuBuilder MB(true, nullptr);
				for (const FJamTool& T : Tools)
				{
					if (T.Cat != Cat)
					{
						continue;
					}
					const FString Verb = T.Verb;
					MB.AddMenuEntry(FText::FromString(T.Verb), FText::FromString(T.Doc), FSlateIcon(),
						FUIAction(FExecuteAction::CreateLambda([this, Verb]() { AddNode(Verb); })));
				}
				return MB.MakeWidget();
			})
		];
	}

	ChildSlot
	[
		SNew(SVerticalBox)

		// Paleta (con scroll horizontal por si hay muchos verbos).
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 6.0f, 6.0f, 2.0f)
		[
			SNew(SScrollBox).Orientation(Orient_Horizontal)
			+ SScrollBox::Slot()[ Palette ]
		]

		// Canvas: wires detrás, nodos encima.
		+ SVerticalBox::Slot().FillHeight(1.0f).Padding(6.0f, 2.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Recessed"))
			[
				SNew(SOverlay)
				+ SOverlay::Slot()
				[
					SNew(SJamWireLayer, TFunction<TArray<TPair<FVector2D, FVector2D>>()>(
						[this]() { return GetWireEndpoints(); }))
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
}

const FJamTool* SJamGraphEditor::FindTool(const FString& Verb) const
{
	return Tools.FindByPredicate([&Verb](const FJamTool& T) { return T.Verb == Verb; });
}

SJamGraphEditor::FGNode* SJamGraphEditor::FindNode(const FString& Id)
{
	return Nodes.FindByPredicate([&Id](const FGNode& N) { return N.Id == Id; });
}

void SJamGraphEditor::AddNode(const FString& Verb, const FVector2D* At)
{
	const FJamTool* T = FindTool(Verb);
	if (T == nullptr || !Canvas.IsValid())
	{
		return;
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
	for (const FJamParam& P : T->Params)
	{
		FString Value = P.Default;
		// El nodo «asset» nace apuntando a lo elegido en Content (Content → nodo, sin tipear).
		if (Verb == TEXT("asset") && P.Name == TEXT("name") && Value.IsEmpty() && ActiveAsset.IsSet())
		{
			Value = ActiveAsset.Get();
		}
		Params.Add(FJamNodeParam(P.Name, Value));
	}

	const FString Id = Node.Id;
	// Nodos FUENTE (producen el dato, no lo reciben): sin pin de entrada, convención de Grasshopper.
	// El flag viene del spec (data-driven): asset/pick/create_spline y las fuentes de flow.
	const bool bHasInput = !T->bSource;

	TSharedRef<SJamGraphNode> Widget = SNew(SJamGraphNode)
		.Verb(Verb)
		.Params(Params)
		.HasInput(bHasInput)
		.OnDragDelta_Lambda([this, Id](const FVector2D& D)
		{
			// D viene en píxeles de pantalla; el modelo vive antes del zoom (render transform).
			if (FGNode* N = FindNode(Id)) { N->Pos += D / Zoom; }
		})
		.OnOutputClicked_Lambda([this, Id]() { OnPinClicked(Id, true); })
		.OnInputClicked_Lambda([this, Id]() { OnPinClicked(Id, false); })
		.OnDeleteClicked_Lambda([this, Id]() { DeleteNode(Id); });

	Node.Widget = Widget;

	const float Height = 34.0f + T->Params.Num() * 28.0f;
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
	Edges.RemoveAll([&Id](const TPair<FString, FString>& E) { return E.Key == Id || E.Value == Id; });
	if (PendingSource == Id) { PendingSource.Empty(); }
	Nodes.RemoveAll([&Id](const FGNode& X) { return X.Id == Id; });
}

void SJamGraphEditor::OnPinClicked(const FString& Id, bool bOutput)
{
	if (bOutput)
	{
		PendingSource = Id;   // armar la salida
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(TEXT("conectá: %s → (clic en una entrada)"), *Id)));
		}
		return;
	}
	// clic en una entrada: cierra la conexión si hay una salida armada
	if (!PendingSource.IsEmpty() && PendingSource != Id)
	{
		const TPair<FString, FString> Wire(PendingSource, Id);
		if (!Edges.Contains(Wire))   // sin duplicar
		{
			Edges.Add(Wire);
		}
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(TEXT("wire: %s → %s"), *PendingSource, *Id)));
		}
	}
	PendingSource.Empty();
}

TArray<TPair<FVector2D, FVector2D>> SJamGraphEditor::GetWireEndpoints() const
{
	TArray<TPair<FVector2D, FVector2D>> Out;
	for (const TPair<FString, FString>& E : Edges)
	{
		const FGNode* A = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.Key; });
		const FGNode* B = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.Value; });
		if (A && B)
		{
			// La capa de wires NO está bajo el render transform del canvas → se aplica acá a mano.
			Out.Add(TPair<FVector2D, FVector2D>(
				(FVector2D(A->Pos.X + NodeWidth, A->Pos.Y + HeaderY) + PanOffset) * Zoom,
				(FVector2D(B->Pos.X, B->Pos.Y + HeaderY) + PanOffset) * Zoom));
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
	for (const TPair<FString, FString>& E : Edges)
	{
		TArray<TSharedPtr<FJsonValue>> Pair;
		Pair.Add(MakeShared<FJsonValueString>(E.Key));
		Pair.Add(MakeShared<FJsonValueString>(E.Value));
		EdgesArr.Add(MakeShared<FJsonValueArray>(Pair));
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

#undef LOCTEXT_NAMESPACE
