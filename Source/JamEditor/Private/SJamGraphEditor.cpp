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
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/AppStyle.h"
#include "Rendering/DrawElements.h"
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

	// Paleta: un botón por verbo → agrega un nodo.
	TSharedRef<SHorizontalBox> Palette = SNew(SHorizontalBox);
	for (const FJamTool& T : Tools)
	{
		const FString Verb = T.Verb;
		Palette->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
		[
			SNew(SButton)
			.Text(FText::FromString(Verb))
			.ToolTipText(FText::FromString(T.Doc))
			.OnClicked_Lambda([this, Verb]() { AddNode(Verb); return FReply::Handled(); })
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
			+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(8.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock).Text(LOCTEXT("Hint", "agregá nodos desde la paleta · arrastrá · ○→○ conecta · Run"))
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

void SJamGraphEditor::AddNode(const FString& Verb)
{
	const FJamTool* T = FindTool(Verb);
	if (T == nullptr || !Canvas.IsValid())
	{
		return;
	}

	FGNode Node;
	Node.Id = FString::Printf(TEXT("n%d"), NextId++);
	Node.Verb = Verb;
	// cascada para que no se apilen exactamente encima
	const int32 K = Nodes.Num();
	Node.Pos = FVector2D(30.0f + (K % 4) * 190.0f, 30.0f + (K / 4) * 40.0f + (K % 4) * 20.0f);

	TArray<FJamNodeParam> Params;
	for (const TPair<FString, FString>& P : T->Params)
	{
		Params.Add(FJamNodeParam(P.Key, P.Value));
	}

	const FString Id = Node.Id;
	TSharedRef<SJamGraphNode> Widget = SNew(SJamGraphNode)
		.Verb(Verb)
		.Params(Params)
		.OnDragDelta_Lambda([this, Id](const FVector2D& D)
		{
			if (FGNode* N = FindNode(Id)) { N->Pos += D; }
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
			return N ? N->Pos : FVector2D::ZeroVector;
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
			Out.Add(TPair<FVector2D, FVector2D>(
				FVector2D(A->Pos.X + NodeWidth, A->Pos.Y + HeaderY),
				FVector2D(B->Pos.X, B->Pos.Y + HeaderY)));
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
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Result));
	}
}

#undef LOCTEXT_NAMESPACE
