#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "Rendering/DrawElements.h"

#define LOCTEXT_NAMESPACE "JamGraphNode"

namespace
{
	// Texto oscuro sobre el cuerpo gris claro de la cápsula (como GH).
	const FLinearColor JamInk(0.10f, 0.10f, 0.11f, 1.0f);
	const FLinearColor JamNub(0.16f, 0.16f, 0.17f, 1.0f);

	// Nub redondo (pin) al estilo Grasshopper: botón sin borde con un ● en el color del nub.
	TSharedRef<SWidget> MakeNub(const FString& Tip, TFunction<void()> OnClick)
	{
		return SNew(SButton)
			.ButtonStyle(&FAppStyle::Get(), "NoBorder")
			.ToolTipText(FText::FromString(Tip))
			.ContentPadding(FMargin(0.0f))
			.OnClicked_Lambda([OnClick]() { OnClick(); return FReply::Handled(); })
			[
				SNew(STextBlock).Text(FText::FromString(TEXT("●")))
				.ColorAndOpacity(JamNub)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 11))
			];
	}
}

void SJamGraphNode::Construct(const FArguments& InArgs)
{
	Verb = InArgs._Verb;
	Icon = InArgs._Icon;
	IconColor = InArgs._IconColor;
	OnDragDelta = InArgs._OnDragDelta;
	OnInputClickedDelegate = InArgs._OnInputClicked;
	OnOutputClickedDelegate = InArgs._OnOutputClicked;
	OnDeleteClickedDelegate = InArgs._OnDeleteClicked;
	RebuildBodyBrush();

	TSharedRef<SVerticalBox> Params = SNew(SVerticalBox);
	for (const FJamNodeParam& P : InArgs._Params)
	{
		const FString Key = P.Key;
		TSharedPtr<SEditableTextBox> Field;
		Params->AddSlot()
			.AutoHeight()
			.Padding(0.0f, 1.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(0.42f).VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::FromString(Key))
					.ColorAndOpacity(JamInk)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				]
				+ SHorizontalBox::Slot().FillWidth(0.58f)
				[
					SAssignNew(Field, SEditableTextBox).Text(FText::FromString(P.Value))
				]
			];
		Fields.Add(Key, Field);
	}

	// Header: ICONO grande (badge de categoría) · título (zona de arrastre) · borrar.
	TSharedRef<SHorizontalBox> Header = SNew(SHorizontalBox);
	if (!Icon.IsEmpty())
	{
		Header->AddSlot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(SBox).WidthOverride(22.0f).HeightOverride(22.0f)
			[
				SNew(SBorder)
				.BorderImage(FAppStyle::GetBrush("WhiteBrush"))
				.BorderBackgroundColor(IconColor)
				.HAlign(HAlign_Center).VAlign(VAlign_Center)
				.Padding(0.0f)
				[
					SNew(STextBlock).Text(FText::FromString(Icon))
					.ColorAndOpacity(FLinearColor::White)
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
				]
			]
		];
	}
	Header->AddSlot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(5.0f, 0.0f, 2.0f, 0.0f)
	[
		SNew(STextBlock).Text(FText::FromString(Verb))
		.ColorAndOpacity(JamInk)
		.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
	];
	Header->AddSlot().AutoWidth().VAlign(VAlign_Top)
	[
		SNew(SButton)
		.ButtonStyle(&FAppStyle::Get(), "NoBorder")
		.ToolTipText(LOCTEXT("Del", "borrar nodo"))
		.ContentPadding(FMargin(2.0f, 0.0f))
		.OnClicked_Lambda([this]() { OnDeleteClickedDelegate.ExecuteIfBound(); return FReply::Handled(); })
		[ SNew(STextBlock).Text(FText::FromString(TEXT("×"))).ColorAndOpacity(JamInk) ]
	];

	// Cuerpo (header + params), con margen L/R para que los nubs de los bordes no lo tapen.
	TSharedRef<SVerticalBox> Body = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 2.0f)
		[ Header ]
		+ SVerticalBox::Slot().AutoHeight()
		[ Params ];

	// Cápsula GH: cuerpo redondeado (lo pinta OnPaint) con los nubs sobre los bordes izq/der,
	// verticalmente centrados (entrada a la izquierda, salida a la derecha).
	TSharedRef<SOverlay> Root = SNew(SOverlay)
		+ SOverlay::Slot().Padding(11.0f, 5.0f)
		[ Body ];
	if (InArgs._HasInput)
	{
		Root->AddSlot().HAlign(HAlign_Left).VAlign(VAlign_Center)
		[ MakeNub(TEXT("entrada (clic para conectar)"),
			[this]() { OnInputClickedDelegate.ExecuteIfBound(); }) ];
	}
	Root->AddSlot().HAlign(HAlign_Right).VAlign(VAlign_Center)
	[ MakeNub(TEXT("salida (clic para conectar)"),
		[this]() { OnOutputClickedDelegate.ExecuteIfBound(); }) ];

	ChildSlot [ Root ];
}

void SJamGraphNode::RebuildBodyBrush()
{
	// relleno gris claro (cápsula GH) + borde = veredicto del oráculo.
	BodyBrush = FSlateRoundedBoxBrush(FLinearColor(0.80f, 0.80f, 0.78f, 1.0f), 6.0f, StateColor(), 1.4f);
}

int32 SJamGraphNode::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
	const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	// Cápsula redondeada detrás de los hijos, insetada para que los nubs queden sobre el borde.
	const FVector2D Size = AllottedGeometry.GetLocalSize();
	const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry(
		FVector2D(FMath::Max(0.0f, (float)Size.X - 14.0f), FMath::Max(0.0f, (float)Size.Y - 2.0f)),
		FSlateLayoutTransform(FVector2D(7.0f, 1.0f)));
	FSlateDrawElement::MakeBox(OutDrawElements, LayerId, PG, &BodyBrush);
	return SCompoundWidget::OnPaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements,
		LayerId + 1, InWidgetStyle, bParentEnabled);
}

void SJamGraphNode::SetResult(const FString& State, const FString& Text)
{
	ResultState = State;
	RebuildBodyBrush();
	SetToolTipText(Text.IsEmpty()
		? FText::FromString(Verb)
		: FText::FromString(FString::Printf(TEXT("%s\n%s"), *Verb, *Text)));
}

FLinearColor SJamGraphNode::StateColor() const
{
	if (ResultState == TEXT("ok"))    { return FLinearColor(0.13f, 0.62f, 0.25f, 1.0f); }
	if (ResultState == TEXT("warn"))  { return FLinearColor(0.90f, 0.52f, 0.04f, 1.0f); }
	if (ResultState == TEXT("error")) { return FLinearColor(0.85f, 0.14f, 0.14f, 1.0f); }
	return FLinearColor(0.10f, 0.10f, 0.10f, 1.0f);   // neutro: borde oscuro fino
}

TMap<FString, FString> SJamGraphNode::GetParamValues() const
{
	TMap<FString, FString> Out;
	for (const TPair<FString, TSharedPtr<SEditableTextBox>>& F : Fields)
	{
		if (F.Value.IsValid())
		{
			Out.Add(F.Key, F.Value->GetText().ToString());
		}
	}
	return Out;
}

FReply SJamGraphNode::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bDragging = true;
		return FReply::Handled().CaptureMouse(SharedThis(this));
	}
	return FReply::Unhandled();
}

FReply SJamGraphNode::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bDragging && HasMouseCapture())
	{
		// El delta del cursor viene en píxeles de pantalla; el modelo está en unidades locales del
		// canvas → dividir por la escala de layout (DPI) para que el nodo siga al mouse 1:1.
		const float S = MyGeometry.GetAccumulatedLayoutTransform().GetScale();
		const FVector2D Delta = MouseEvent.GetCursorDelta() / (S > 0.0f ? S : 1.0f);
		OnDragDelta.ExecuteIfBound(Delta);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SJamGraphNode::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bDragging && MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bDragging = false;
		return FReply::Handled().ReleaseMouseCapture();
	}
	return FReply::Unhandled();
}

#undef LOCTEXT_NAMESPACE
