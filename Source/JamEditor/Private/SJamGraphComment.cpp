#include "SJamGraphComment.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Colors/SColorPicker.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "Rendering/DrawElements.h"

#define LOCTEXT_NAMESPACE "JamGraphComment"

namespace
{
	const FLinearColor JamCommentInk(0.10f, 0.10f, 0.11f, 1.0f);
}

void SJamGraphComment::Construct(const FArguments& InArgs)
{
	OnClickedDelegate = InArgs._OnClicked;
	OnDragBeginDelegate = InArgs._OnDragBegin;
	OnDragDeltaDelegate = InArgs._OnDragDelta;
	OnDragEndDelegate = InArgs._OnDragEnd;
	OnResizeDeltaDelegate = InArgs._OnResizeDelta;
	OnResizeEndDelegate = InArgs._OnResizeEnd;
	OnDeleteSelectionDelegate = InArgs._OnDeleteSelection;
	OnTitleChangedDelegate = InArgs._OnTitleChanged;
	OnColorChangedDelegate = InArgs._OnColorChanged;
	IsSelectedAttr = InArgs._IsSelected;

	// El fondo lo pinta OnPaint (la franja de título es parte del cuerpo, no un widget aparte); el
	// text box queda transparente para no duplicar el color debajo de las letras.
	TitleStyle = FAppStyle::Get().GetWidgetStyle<FEditableTextBoxStyle>("NormalEditableTextBox");
	const FSlateRoundedBoxBrush Transparente(FLinearColor(0.0f, 0.0f, 0.0f, 0.0f), 0.0f);
	TitleStyle.SetBackgroundImageNormal(Transparente);
	TitleStyle.SetBackgroundImageHovered(Transparente);
	TitleStyle.SetBackgroundImageFocused(Transparente);
	TitleStyle.SetBackgroundImageReadOnly(Transparente);
	TitleStyle.SetForegroundColor(JamCommentInk);
	TitleStyle.SetFocusedForegroundColor(JamCommentInk);
	TitleStyle.SetPadding(FMargin(2.0f, 1.0f));
	FTextBlockStyle TextStyle = TitleStyle.TextStyle;
	TextStyle.SetFont(FCoreStyle::GetDefaultFontStyle("Bold", 9));
	TextStyle.SetColorAndOpacity(JamCommentInk);
	TextStyle.SetSelectedBackgroundColor(FLinearColor(0.20f, 0.45f, 0.85f, 1.0f));
	TitleStyle.SetTextStyle(TextStyle);

	ChildSlot
	[
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SBox).HeightOverride(TitleStripH).Padding(FMargin(6.0f, 5.0f, 6.0f, 3.0f))
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.0f)
				[
					SAssignNew(TitleBox, SEditableTextBox)
					.Style(&TitleStyle)
					.Text(FText::FromString(InArgs._Title))
					.HintText(LOCTEXT("CommentHint", "Comentario"))
					.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type)
					{
						OnTitleChangedDelegate.ExecuteIfBound();
					})
				]
				// Swatch del color: clic abre el picker del motor. El cuerpo/borde/franja lo reflejan
				// EN VIVO mientras se elige (OnColorCommitted); el paso de historial lo registra el
				// editor recién al CERRAR el picker (OnColorPickerWindowClosed) — mismo patrón que
				// arrastrar/redimensionar: mutar en vivo, un solo Marcar() al final del gesto.
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SColorBlock)
					.Color_Lambda([this]() { return CurrentColor; })
					.Size(FVector2D(16.0f, 16.0f))
					.CornerRadius(FVector4(3.0f, 3.0f, 3.0f, 3.0f))
					.ShowBackgroundForAlpha(false)
					.ColorIsHSV(false)
					.OnMouseButtonDown_Lambda([this](const FGeometry&, const FPointerEvent& MouseEvent)
					{
						if (MouseEvent.GetEffectingButton() != EKeys::LeftMouseButton)
						{
							return FReply::Unhandled();
						}
						FColorPickerArgs Args;
						Args.InitialColor = CurrentColor;
						Args.bIsModal = false;
						// `bOpenAsMenu` empuja el picker por PushMenu (el mecanismo liviano de menús
						// contextuales) en vez de una ventana nativa propia — en este Linux/Wayland eso
						// dejaba bloques negros sólidos pintados sobre el canvas del Graph mientras se
						// arrastraba la rueda de color. Ventana nativa normal: mismo picker, sin ese artefacto.
						Args.bOpenAsMenu = false;
						Args.ParentWidget = SharedThis(this);
						Args.OnColorCommitted = FOnLinearColorValueChanged::CreateSP(
							this, &SJamGraphComment::SetColor);
						Args.OnColorPickerWindowClosed = FOnWindowClosed::CreateLambda(
							[this](const TSharedRef<SWindow>&) { OnColorChangedDelegate.ExecuteIfBound(); });
						OpenColorPicker(Args);
						return FReply::Handled();
					})
				]
			]
		]
		// Sin más hijos abajo: el resto del cuerpo es zona de arrastre. Un SSpacer no consume el
		// clic — bubblea a este widget, igual que "cualquier zona no interactiva arrastra el
		// componente" en SJamGraphNode.
		+ SVerticalBox::Slot().FillHeight(1.0f)
		[
			SNew(SSpacer)
		]
	];

	SetColor(InArgs._Color);
}

FString SJamGraphComment::GetTitle() const
{
	return TitleBox.IsValid() ? TitleBox->GetText().ToString() : FString();
}

void SJamGraphComment::SetTitle(const FString& NewTitle)
{
	if (TitleBox.IsValid())
	{
		TitleBox->SetText(FText::FromString(NewTitle));
	}
}

void SJamGraphComment::SetColor(FLinearColor NewColor)
{
	// El tinte base llega a opacidad plena (para el swatch); cuerpo/borde/franja derivan su propia
	// opacidad de éste. El relleno queda translúcido a propósito: la caja tiñe el fondo pero deja
	// leer la grilla y los nodos que encierra, como la comment box de Blueprint. Estos tres alfas son
	// LA perilla del look de la caja — se ven de verdad recién desde que `OnPaint` pasa el tint
	// explícito a MakeBox (ver el comentario ahí).
	NewColor.A = 1.0f;
	CurrentColor = NewColor;
	BodyBrush.TintColor = FSlateColor(FLinearColor(NewColor.R, NewColor.G, NewColor.B, 0.35f));
	BodyBrush.OutlineSettings.Color = FSlateColor(FLinearColor(NewColor.R, NewColor.G, NewColor.B, 0.90f));
	TitleStripBrush.TintColor = FSlateColor(FLinearColor(NewColor.R, NewColor.G, NewColor.B, 0.75f));
	Invalidate(EInvalidateWidgetReason::Paint);
}

bool SJamGraphComment::bOverHandle(const FGeometry& MyGeometry, const FVector2D& ScreenSpacePos) const
{
	const FVector2D Local = MyGeometry.AbsoluteToLocal(ScreenSpacePos);
	const FVector2D Size = MyGeometry.GetLocalSize();
	return Local.X >= Size.X - HandleSize && Local.Y >= Size.Y - HandleSize;
}

FReply SJamGraphComment::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
	if (InKeyEvent.GetKey() == EKeys::Delete)
	{
		// Un text box enfocado consume Supr antes de que llegue acá — mismo trato que SJamGraphNode.
		OnDeleteSelectionDelegate.ExecuteIfBound();
		return FReply::Handled();
	}
	return SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
}

FReply SJamGraphComment::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() != EKeys::LeftMouseButton)
	{
		return FReply::Unhandled();
	}
	// Primero la selección, después decidir arrastre-o-resize: misma razón que en SJamGraphNode —
	// clickear una caja ya elegida no debe desarmar el grupo justo antes de moverlo.
	OnClickedDelegate.ExecuteIfBound(MouseEvent.IsShiftDown(), MouseEvent.IsControlDown());

	bResizing = bOverHandle(MyGeometry, MouseEvent.GetScreenSpacePosition());
	bDragging = !bResizing;
	bMovioAlgo = false;
	if (bDragging)
	{
		// Congela qué nodos toca la caja ANTES de mover nada — nunca se persiste (ver FGComment).
		OnDragBeginDelegate.ExecuteIfBound();
	}
	return FReply::Handled()
		.CaptureMouse(SharedThis(this))
		.SetUserFocus(SharedThis(this), EFocusCause::Mouse);
}

FReply SJamGraphComment::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if ((bDragging || bResizing) && HasMouseCapture())
	{
		const float S = MyGeometry.GetAccumulatedLayoutTransform().GetScale();
		const FVector2D Delta = MouseEvent.GetCursorDelta() / (S > 0.0f ? S : 1.0f);
		if (!Delta.IsNearlyZero())
		{
			bMovioAlgo = true;
		}
		if (bResizing) { OnResizeDeltaDelegate.ExecuteIfBound(Delta); }
		else            { OnDragDeltaDelegate.ExecuteIfBound(Delta); }
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SJamGraphComment::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if ((bDragging || bResizing) && MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		const bool bWasResizing = bResizing;
		bDragging = false;
		bResizing = false;
		if (bMovioAlgo)
		{
			// UN paso por arrastre, al soltar — igual que SJamGraphNode: marcarlo por frame llenaría
			// el historial con las posiciones/tamaños intermedios de un solo gesto.
			bMovioAlgo = false;
			if (bWasResizing) { OnResizeEndDelegate.ExecuteIfBound(); }
			else               { OnDragEndDelegate.ExecuteIfBound(); }
		}
		return FReply::Handled().ReleaseMouseCapture();
	}
	return FReply::Unhandled();
}

FCursorReply SJamGraphComment::OnCursorQuery(const FGeometry& MyGeometry, const FPointerEvent& CursorEvent) const
{
	if (bResizing || bOverHandle(MyGeometry, CursorEvent.GetScreenSpacePosition()))
	{
		return FCursorReply::Cursor(EMouseCursor::ResizeSouthEast);
	}
	return FCursorReply::Unhandled();
}

int32 SJamGraphComment::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
	const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	const FVector2D Size = AllottedGeometry.GetLocalSize();

	// El RELLENO de un brush sale del `InTint` de MakeBox, NO de `Brush.TintColor`: `FSlateBoxPayload::
	// SetBrush` copia margen/UV/tiling/recurso y nunca mira el tint del brush. El BORDE sí se lee del
	// brush (`Element.SetOutline(InBrush->OutlineSettings.Color...)`), y por eso omitir el tint acá
	// pintaba el borde del color elegido pero el fondo blanco opaco (el default `FLinearColor::White`).
	// Por eso cada relleno pasa su tint explícito.
	if (IsSelectedAttr.Get(false))
	{
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId,
			AllottedGeometry.ToPaintGeometry(Size + FVector2D(6.0f, 6.0f),
				FSlateLayoutTransform(FVector2D(-3.0f, -3.0f))),
			&SelectionBrush, ESlateDrawEffect::None,
			SelectionBrush.TintColor.GetSpecifiedColor());
	}

	FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 1,
		AllottedGeometry.ToPaintGeometry(Size, FSlateLayoutTransform(FVector2D::ZeroVector)),
		&BodyBrush, ESlateDrawEffect::None,
		BodyBrush.TintColor.GetSpecifiedColor());

	FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 2,
		AllottedGeometry.ToPaintGeometry(
			FVector2D(Size.X, FMath::Min(TitleStripH, (float)Size.Y)),
			FSlateLayoutTransform(FVector2D::ZeroVector)),
		&TitleStripBrush, ESlateDrawEffect::None,
		TitleStripBrush.TintColor.GetSpecifiedColor());

	// Glifo del handle de resize: tres líneas diagonales crecientes, el grip clásico de esquina.
	if (Size.X > HandleSize && Size.Y > HandleSize)
	{
		const FVector2D Corner(Size.X - 3.0f, Size.Y - 3.0f);
		const FLinearColor HandleColor(0.35f, 0.32f, 0.26f, 0.65f);
		for (float Offset : { 4.0f, 8.0f, 12.0f })
		{
			TArray<FVector2D> Line;
			Line.Add(Corner - FVector2D(Offset, 0.0f));
			Line.Add(Corner - FVector2D(0.0f, Offset));
			FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 3,
				AllottedGeometry.ToPaintGeometry(), Line, ESlateDrawEffect::None,
				HandleColor, true, 1.5f);
		}
	}

	return SCompoundWidget::OnPaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements,
		LayerId + 4, InWidgetStyle, bParentEnabled);
}

#undef LOCTEXT_NAMESPACE
