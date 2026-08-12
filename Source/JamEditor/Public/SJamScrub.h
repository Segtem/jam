// Copyright Jam.
#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

/**
 * Tirador para arrastrar un número (el «Digit Scroller» del tab Params de Grasshopper).
 *
 * Jam tiene **505 parámetros numéricos** y hasta ahora todos se tipeaban: el campo de un param es un
 * cuadro de texto pelado, sin arrastre. Eso no fue un descuido —**cualquier param numérico puede
 * llevar una expresión** (`=radio * 2`, o el nombre de una variable), y un spinbox no puede
 * contenerla—, pero deja al usuario tecleando para probar un valor, que es lo contrario de tantear.
 *
 * Por eso el tirador va AL LADO del campo y no en su lugar: el texto sigue aceptando expresiones y
 * valores exactos, y el tirador agrega la única cosa que faltaba, que es tantear con el mouse.
 *
 * **No toca un campo que tenga una expresión.** Arrastrar sobre `=radio * 2` lo reemplazaría por un
 * número y rompería en silencio un vínculo que alguien armó a propósito — el peor cambio posible,
 * porque el nodo sigue dando un resultado plausible.
 */
class SJamScrub : public SCompoundWidget
{
public:
	DECLARE_DELEGATE_OneParam(FOnValueChanged, float);
	DECLARE_DELEGATE_RetVal(FString, FOnPedirTexto);

	SLATE_BEGIN_ARGS(SJamScrub)
		: _Entero(false)
		, _Alto(16.0f)
	{}
		/** El texto actual del campo. Se pide al agarrar: si tiene una expresión, no se arrastra. */
		SLATE_EVENT(FOnPedirTexto, TextoActual)
		/** `true` para params declarados `int`: nunca produce decimales. */
		SLATE_ARGUMENT(bool, Entero)
		SLATE_ARGUMENT(float, Alto)
		/** Por cada movimiento, para el live view. */
		SLATE_EVENT(FOnValueChanged, OnValueChanged)
		/** Al soltar: UN paso de historial por arrastre. */
		SLATE_EVENT(FOnValueChanged, OnValueCommitted)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
		int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

	virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FVector2D ComputeDesiredSize(float) const override;

private:
	FOnPedirTexto TextoActual;
	bool bEntero = false;
	float Alto = 16.0f;
	FOnValueChanged OnValueChanged;
	FOnValueChanged OnValueCommitted;

	bool bArrastrando = false;
	float XAlAgarrar = 0.0f;
	float ValorAlAgarrar = 0.0f;
	float UltimoValor = 0.0f;
};
