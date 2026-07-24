#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "Rendering/DrawElements.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Math/TransformCalculus2D.h"

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
	OutName = InArgs._OutName;
	IconColor = InArgs._IconColor;
	OnDragDelta = InArgs._OnDragDelta;
	OnInputClickedDelegate = InArgs._OnInputClicked;
	OnOutputClickedDelegate = InArgs._OnOutputClicked;
	OnDeleteClickedDelegate = InArgs._OnDeleteClicked;
	RebuildBodyBrush();
	IconBrush = FSlateRoundedBoxBrush(IconColor, 3.0f);   // slot del icono en el color de su categoría

	// Campos de valor CLAROS con texto negro (como los inputs de GH), en vez del text-box oscuro del
	// editor. Fondo claro redondeado + foreground negro en todos los estados.
	FieldStyle = FAppStyle::Get().GetWidgetStyle<FEditableTextBoxStyle>("NormalEditableTextBox");
	const FSlateRoundedBoxBrush FieldBg(FLinearColor(0.95f, 0.95f, 0.93f, 1.0f), 2.0f,
		FLinearColor(0.45f, 0.45f, 0.43f, 1.0f), 1.0f);
	FieldStyle.SetBackgroundImageNormal(FieldBg);
	FieldStyle.SetBackgroundImageHovered(FieldBg);
	FieldStyle.SetBackgroundImageFocused(FieldBg);
	FieldStyle.SetBackgroundImageReadOnly(FieldBg);
	FieldStyle.SetForegroundColor(FLinearColor::Black);

	// Celda de alto FIJO (los pines se alinean a las filas por construcción; la métrica la comparte el
	// editor para anclar los wires exactamente en cada pin — como los grips por parámetro de GH).
	auto Cell = [](float H, TSharedRef<SWidget> W)
	{
		return SNew(SBox).HeightOverride(H).VAlign(VAlign_Center)[ W ];
	};
	auto Spacer = [](float H) { return SNew(SBox).HeightOverride(H); };

	// Anatomía de componente de Grasshopper: NO hay barra de título arriba. El NOMBRE del verbo va
	// VERTICAL en el centro (lo dibuja OnPaint); los PARÁMETROS son filas a la izquierda [nub][nombre]
	// [valor]; el pin de SALIDA a la derecha. Sin Execution Pins (Jam es dataflow como GH).
	//   col pines-in (izq) · col params (nombre+valor) · centro libre (nombre vertical) · col pin-out (der)
	TSharedRef<SVerticalBox> LeftCol  = SNew(SVerticalBox);
	TSharedRef<SVerticalBox> ParamCol = SNew(SVerticalBox);
	TSharedRef<SVerticalBox> RightCol = SNew(SVerticalBox);

	LeftCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	ParamCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	RightCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];

	// fila header: nub de stream «in» (izq) · botón borrar (der de la col de params) · nub «out» (der)
	LeftCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH, InArgs._HasInput
			? MakeNub(TEXT("entrada de stream (clic para conectar)"),
				[this]() { OnInputClickedDelegate.ExecuteIfBound(TEXT("in")); })
			: StaticCastSharedRef<SWidget>(SNullWidget::NullWidget))
	];
	ParamCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH,
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]   // zona de arrastre
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(SButton)
				.ButtonStyle(&FAppStyle::Get(), "NoBorder")
				.ToolTipText(LOCTEXT("Del", "borrar nodo"))
				.ContentPadding(FMargin(2.0f, 0.0f))
				.OnClicked_Lambda([this]() { OnDeleteClickedDelegate.ExecuteIfBound(); return FReply::Handled(); })
				[ SNew(STextBlock).Text(FText::FromString(TEXT("×"))).ColorAndOpacity(JamInk) ]
			])
	];
	RightCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH, MakeNub(TEXT("salida (clic para conectar)"),
			[this]() { OnOutputClickedDelegate.ExecuteIfBound(); }))
	];

	// una fila por parámetro: [nub] · [nombre][valor] · (sin salida)
	for (const FJamNodeParam& P : InArgs._Params)
	{
		const FString Key = P.Key;
		TSharedPtr<SEditableTextBox> Field;

		LeftCol->AddSlot().AutoHeight()
		[
			Cell(RowH, MakeNub(FString::Printf(TEXT("pin «%s» (cableá una variable para manejarlo)"), *Key),
				[this, Key]() { OnInputClickedDelegate.ExecuteIfBound(Key); }))
		];
		ParamCol->AddSlot().AutoHeight()
		[
			Cell(RowH,
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(1.0f, 0.0f, 3.0f, 0.0f)
				[
					SNew(STextBlock).Text(FText::FromString(Key))
					.ColorAndOpacity(JamInk)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
				[
					SAssignNew(Field, SEditableTextBox).Style(&FieldStyle).Text(FText::FromString(P.Value))
				])
		];
		RightCol->AddSlot().AutoHeight()[ Cell(RowH, StaticCastSharedRef<SWidget>(SNullWidget::NullWidget)) ];
		Fields.Add(Key, Field);
	}

	ChildSlot
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ LeftCol ] ]
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(ParamColW)[ ParamCol ] ]
		+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]   // centro: nombre vertical (OnPaint)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ RightCol ] ]
	];
}

void SJamGraphNode::RebuildBodyBrush()
{
	// cápsula tintada por su CATEGORÍA (como los componentes lavanda/color de GH): un pastel claro del
	// color de categoría; borde = veredicto del oráculo.
	const FLinearColor Fill = FMath::Lerp(IconColor, FLinearColor(0.96f, 0.96f, 0.95f, 1.0f), 0.74f);
	BodyBrush = FSlateRoundedBoxBrush(Fill, 5.0f, StateColor(), 1.4f);
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

	// NOMBRE DEL VERBO en VERTICAL, centrado en la zona libre (como los componentes en modo texto de
	// GH): rotado -90° alrededor de su centro. Se dibuja acá para no pelear con el layout de Slate.
	{
		const FSlateFontInfo Font = FCoreStyle::GetDefaultFontStyle("Bold", 9);
		const TSharedRef<FSlateFontMeasure> FM =
			FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
		const FVector2D TS = FM->Measure(Verb, Font);
		const float FreeLeft = PinColW + ParamColW;
		const float Cx = FMath::Min((FreeLeft + (Size.X - PinColW)) * 0.5f, Size.X - PinColW - 4.0f);
		const FVector2D TopLeft(Cx - TS.X * 0.5f, Size.Y * 0.5f - TS.Y * 0.5f);
		const FPaintGeometry TPG = AllottedGeometry.ToPaintGeometry(
			TS, FSlateLayoutTransform(TopLeft),
			FSlateRenderTransform(FQuat2D(FMath::DegreesToRadians(-90.0f))), FVector2D(0.5f, 0.5f));
		FSlateDrawElement::MakeText(OutDrawElements, LayerId + 1, TPG, Verb, Font,
			ESlateDrawEffect::None, JamInk);
	}

	// NOMBRE DE LA SALIDA (la «variable» del pin de salida, estilo GH: S/E/P/T…), pegado a la
	// izquierda del nub «out» a la altura del header.
	if (!OutName.IsEmpty())
	{
		const FSlateFontInfo OFont = FCoreStyle::GetDefaultFontStyle("Bold", 8);
		const TSharedRef<FSlateFontMeasure> FM2 =
			FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
		const FVector2D OS = FM2->Measure(OutName, OFont);
		const FVector2D OTL(Size.X - PinColW - OS.X - 1.0f, PinLocalY(-1) - OS.Y * 0.5f);
		FSlateDrawElement::MakeText(OutDrawElements, LayerId + 1,
			AllottedGeometry.ToPaintGeometry(OS, FSlateLayoutTransform(OTL)), OutName, OFont,
			ESlateDrawEffect::None, JamInk);
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

void SJamGraphNode::SetParamValues(const TMap<FString, FString>& Values)
{
	for (const TPair<FString, FString>& KV : Values)
	{
		if (const TSharedPtr<SEditableTextBox>* F = Fields.Find(KV.Key))
		{
			if (F->IsValid())
			{
				(*F)->SetText(FText::FromString(KV.Value));
			}
		}
	}
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
