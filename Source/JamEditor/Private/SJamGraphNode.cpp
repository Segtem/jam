#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Images/SImage.h"
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

	// El GRIP (pin) al estilo Grasshopper: una pastilla oscura sobre el borde de la cápsula, en vez de
	// un punto. Es estático (todos los grips son iguales; el color no cambia) → vive lo que el widget.
	const FSlateRoundedBoxBrush GGripBrush(FLinearColor(0.16f, 0.16f, 0.17f, 1.0f), 4.0f);

	// Nub = botón sin borde con la pastilla del grip (clicable para conectar), como el grip de GH.
	TSharedRef<SWidget> MakeNub(const FString& Tip, TFunction<void()> OnClick)
	{
		return SNew(SButton)
			.ButtonStyle(&FAppStyle::Get(), "NoBorder")
			.ToolTipText(FText::FromString(Tip))
			.ContentPadding(FMargin(0.0f))
			.HAlign(HAlign_Center).VAlign(VAlign_Center)
			.OnClicked_Lambda([OnClick]() { OnClick(); return FReply::Handled(); })
			[
				SNew(SBox).WidthOverride(8.0f).HeightOverride(11.0f)
				[ SNew(SImage).Image(&GGripBrush) ]
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
	IconBrush = FSlateRoundedBoxBrush(IconColor, 3.0f);   // slot del icono en el color de su categoría

	// Celda de alto FIJO (los pines se alinean a las filas por construcción; la métrica la comparte el
	// editor para anclar los wires exactamente en cada pin — como los grips por parámetro de GH).
	auto Cell = [](float H, TSharedRef<SWidget> W)
	{
		return SNew(SBox).HeightOverride(H).VAlign(VAlign_Center)[ W ];
	};
	auto Spacer = [](float H) { return SNew(SBox).HeightOverride(H); };

	// Header del cuerpo: ICONO (badge de categoría) · título (zona de arrastre) · borrar.
	TSharedRef<SHorizontalBox> Header = SNew(SHorizontalBox);
	if (!Icon.IsEmpty())
	{
		Header->AddSlot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(SBox).WidthOverride(19.0f).HeightOverride(19.0f)
			[
				SNew(SBorder)
				.BorderImage(&IconBrush)
				.HAlign(HAlign_Center).VAlign(VAlign_Center)
				.Padding(0.0f)
				[
					SNew(STextBlock).Text(FText::FromString(Icon))
					.ColorAndOpacity(FLinearColor::White)
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 8))
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
	Header->AddSlot().AutoWidth().VAlign(VAlign_Center)
	[
		SNew(SButton)
		.ButtonStyle(&FAppStyle::Get(), "NoBorder")
		.ToolTipText(LOCTEXT("Del", "borrar nodo"))
		.ContentPadding(FMargin(2.0f, 0.0f))
		.OnClicked_Lambda([this]() { OnDeleteClickedDelegate.ExecuteIfBound(); return FReply::Handled(); })
		[ SNew(STextBlock).Text(FText::FromString(TEXT("×"))).ColorAndOpacity(JamInk) ]
	];

	// TRES columnas: pines de ENTRADA (izq, uno por parámetro), cuerpo, pin de SALIDA (der). Cada
	// columna tiene la MISMA estructura vertical (spacer + header + una fila por parámetro) → los pines
	// quedan alineados a su fila. Cablear a un pin de parámetro ata una variable a ese parámetro.
	TSharedRef<SVerticalBox> LeftCol  = SNew(SVerticalBox);
	TSharedRef<SVerticalBox> BodyCol  = SNew(SVerticalBox);
	TSharedRef<SVerticalBox> RightCol = SNew(SVerticalBox);

	LeftCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	BodyCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	RightCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];

	// fila header
	LeftCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH, InArgs._HasInput
			? MakeNub(TEXT("entrada de stream (clic para conectar)"),
				[this]() { OnInputClickedDelegate.ExecuteIfBound(TEXT("in")); })
			: StaticCastSharedRef<SWidget>(SNullWidget::NullWidget))
	];
	BodyCol->AddSlot().AutoHeight()[ Cell(HeaderH, Header) ];
	RightCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH, MakeNub(TEXT("salida (clic para conectar)"),
			[this]() { OnOutputClickedDelegate.ExecuteIfBound(); }))
	];

	// una fila por parámetro: pin de entrada · [label + campo] · (sin salida)
	for (const FJamNodeParam& P : InArgs._Params)
	{
		const FString Key = P.Key;
		TSharedPtr<SEditableTextBox> Field;

		LeftCol->AddSlot().AutoHeight()
		[
			Cell(RowH, MakeNub(FString::Printf(TEXT("pin «%s» (cableá una variable para manejarlo)"), *Key),
				[this, Key]() { OnInputClickedDelegate.ExecuteIfBound(Key); }))
		];
		BodyCol->AddSlot().AutoHeight()
		[
			Cell(RowH,
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(0.42f).VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::FromString(Key))
					.ColorAndOpacity(JamInk)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				]
				+ SHorizontalBox::Slot().FillWidth(0.58f).VAlign(VAlign_Center)
				[
					SAssignNew(Field, SEditableTextBox).Text(FText::FromString(P.Value))
				])
		];
		RightCol->AddSlot().AutoHeight()[ Cell(RowH, StaticCastSharedRef<SWidget>(SNullWidget::NullWidget)) ];
		Fields.Add(Key, Field);
	}

	ChildSlot
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ LeftCol ] ]
		+ SHorizontalBox::Slot().FillWidth(1.0f)[ BodyCol ]
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ RightCol ] ]
	];
}

void SJamGraphNode::RebuildBodyBrush()
{
	// relleno gris claro (cápsula GH, tema claro clásico) + borde = veredicto del oráculo.
	BodyBrush = FSlateRoundedBoxBrush(FLinearColor(0.90f, 0.90f, 0.88f, 1.0f), 5.0f, StateColor(), 1.4f);
}

int32 SJamGraphNode::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
	const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	// Cápsula redondeada detrás de los hijos, insetada para que los grips queden sobre el borde.
	const FVector2D Size = AllottedGeometry.GetLocalSize();
	const float BodyW = FMath::Max(0.0f, (float)Size.X - 14.0f);
	const float BodyH = FMath::Max(0.0f, (float)Size.Y - 2.0f);
	const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry(
		FVector2D(BodyW, BodyH), FSlateLayoutTransform(FVector2D(7.0f, 1.0f)));
	FSlateDrawElement::MakeBox(OutDrawElements, LayerId, PG, &BodyBrush);

	// Bevel suave estilo GH: un degradé vertical (transparente arriba → sombra abajo) inset por el
	// radio para no asomar en las esquinas, + una línea de luz apenas bajo el borde superior.
	const float R = 5.0f;
	if (BodyW > 2.0f * R && BodyH > 2.0f * R)
	{
		const FVector2D GSize(BodyW - 2.0f * R, BodyH - 2.0f * R);
		const FPaintGeometry GPG = AllottedGeometry.ToPaintGeometry(
			GSize, FSlateLayoutTransform(FVector2D(7.0f + R, 1.0f + R)));
		TArray<FSlateGradientStop> Stops;
		Stops.Add(FSlateGradientStop(FVector2D(0.0f, 0.0f), FLinearColor(0.0f, 0.0f, 0.0f, 0.0f)));
		Stops.Add(FSlateGradientStop(FVector2D(0.0f, GSize.Y), FLinearColor(0.0f, 0.0f, 0.0f, 0.09f)));
		FSlateDrawElement::MakeGradient(OutDrawElements, LayerId + 1, GPG, Stops, Orient_Vertical);

		TArray<FVector2D> Hi;
		Hi.Add(FVector2D(7.0f + R, 2.0f));
		Hi.Add(FVector2D(7.0f + BodyW - R, 2.0f));
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 1, AllottedGeometry.ToPaintGeometry(),
			Hi, ESlateDrawEffect::None, FLinearColor(1.0f, 1.0f, 1.0f, 0.35f), true, 1.0f);
	}

	return SCompoundWidget::OnPaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements,
		LayerId + 2, InWidgetStyle, bParentEnabled);
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
	if (ResultState == TEXT("ok"))    { return FLinearColor(0.13f, 0.55f, 0.22f, 1.0f); }
	if (ResultState == TEXT("warn"))  { return FLinearColor(0.85f, 0.48f, 0.03f, 1.0f); }
	if (ResultState == TEXT("error")) { return FLinearColor(0.80f, 0.12f, 0.12f, 1.0f); }
	return FLinearColor(0.34f, 0.34f, 0.33f, 1.0f);   // neutro: borde gris medio (sobre cápsula clara)
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
