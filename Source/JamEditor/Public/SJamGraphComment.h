#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Styling/SlateTypes.h"

class SEditableTextBox;

/** Clic en el cuerpo de una caja, con modificadores — misma forma que `FOnNodeClicked`. */
DECLARE_DELEGATE_TwoParams(FOnCommentClicked, bool /*bShift*/, bool /*bCtrl*/);
/** Delta de arrastre del cuerpo O del handle de resize, según cuál dispare el delegado. */
DECLARE_DELEGATE_OneParam(FOnCommentDelta, const FVector2D&);

/**
 * Caja de comentario/grupo del canvas (Fase 7.1): la comment box de Blueprint, el network box de
 * Houdini. Sólo la VISTA — «qué nodos contiene» no lo sabe esta clase; lo decide el editor por
 * contención espacial (`SJamGraphEditor::NodeIdsTouchingRect`) al empezar cada arrastre del cuerpo.
 *
 * Arrastrar el CUERPO mueve la caja (y lo que el editor decida que contiene). Arrastrar el HANDLE
 * de la esquina inferior-derecha la redimensiona. Las dos cosas comparten un solo ciclo de mouse
 * —`OnMouseButtonDown` decide cuál de las dos por geometría— para no anidar una segunda captura de
 * mouse dentro de este `SCompoundWidget`, que ya captura la suya.
 */
class SJamGraphComment : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SJamGraphComment)
		: _Color(FLinearColor(0.65f, 0.60f, 0.50f, 1.0f))
	{}
		SLATE_ARGUMENT(FString, Title)
		SLATE_ATTRIBUTE(bool, IsSelected)
		SLATE_ARGUMENT(FLinearColor, Color)
		SLATE_EVENT(FOnCommentClicked, OnClicked)
		/** Antes de mover el cuerpo: el editor congela qué nodos toca la caja EN ESE MOMENTO. */
		SLATE_EVENT(FSimpleDelegate, OnDragBegin)
		SLATE_EVENT(FOnCommentDelta, OnDragDelta)
		SLATE_EVENT(FSimpleDelegate, OnDragEnd)
		SLATE_EVENT(FOnCommentDelta, OnResizeDelta)
		SLATE_EVENT(FSimpleDelegate, OnResizeEnd)
		SLATE_EVENT(FSimpleDelegate, OnDeleteSelection)
		/** Se confirmó el título (Enter / perder el foco). Un paso de historial, como `OnParamChanged`
		 *  en `SJamGraphNode`. */
		SLATE_EVENT(FSimpleDelegate, OnTitleChanged)
		/** Se cerró el color picker: un paso de historial. Mientras está abierto, `OnColorCommitted`
		 *  actualiza el color EN VIVO (el swatch y el cuerpo lo reflejan al toque) sin tocar el
		 *  historial — mismo patrón que arrastrar/redimensionar. */
		SLATE_EVENT(FSimpleDelegate, OnColorChanged)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	/** Título VIVO, leído del text box — la caja es la fuente, igual que `GetParamValues()` en
	 *  `SJamGraphNode` para sus parámetros. */
	FString GetTitle() const;
	void SetTitle(const FString& NewTitle);

	/** Color de la caja (tinte base; el cuerpo/borde/franja de título derivan su propia opacidad de
	 *  éste). La caja es la fuente viva, igual que el título. */
	FLinearColor GetColor() const { return CurrentColor; }
	/** Por valor (no `const&`): así `FOnLinearColorValueChanged::CreateSP` puede apuntar acá
	 *  directamente sin un lambda intermedio — el delegado del picker entrega `FLinearColor` por
	 *  valor. */
	void SetColor(FLinearColor NewColor);

	virtual bool SupportsKeyboardFocus() const override { return true; }
	virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
	virtual FReply OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FCursorReply OnCursorQuery(const FGeometry& MyGeometry, const FPointerEvent& CursorEvent) const override;
	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

	/** Zona de la esquina inferior-derecha que dispara el resize en vez del arrastre del cuerpo.
	 *  Pública para que el test de layout pueda confirmarla contra `HandleSize` sin duplicarla. */
	static constexpr float HandleSize = 14.0f;

private:
	bool bOverHandle(const FGeometry& MyGeometry, const FVector2D& ScreenSpacePos) const;

	TSharedPtr<SEditableTextBox> TitleBox;
	FEditableTextBoxStyle TitleStyle;
	FSlateRoundedBoxBrush BodyBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.65f, 0.60f, 0.50f, 0.10f), 6.0f, FLinearColor(0.65f, 0.60f, 0.50f, 0.55f), 1.0f);
	FSlateRoundedBoxBrush TitleStripBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.65f, 0.60f, 0.50f, 0.55f), 0.0f);
	FSlateRoundedBoxBrush SelectionBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.55f, 0.35f, 0.82f, 0.22f), 7.0f,
		FLinearColor(0.43f, 0.24f, 0.70f, 0.90f), 2.0f);
	static constexpr float TitleStripH = 28.0f;

	FLinearColor CurrentColor = FLinearColor(0.65f, 0.60f, 0.50f, 1.0f);

	bool bDragging = false;
	bool bResizing = false;
	bool bMovioAlgo = false;

	FOnCommentClicked OnClickedDelegate;
	FSimpleDelegate OnDragBeginDelegate;
	FOnCommentDelta OnDragDeltaDelegate;
	FSimpleDelegate OnDragEndDelegate;
	FOnCommentDelta OnResizeDeltaDelegate;
	FSimpleDelegate OnResizeEndDelegate;
	FSimpleDelegate OnDeleteSelectionDelegate;
	FSimpleDelegate OnTitleChangedDelegate;
	FSimpleDelegate OnColorChangedDelegate;
	TAttribute<bool> IsSelectedAttr;
};
