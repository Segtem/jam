// Copyright Jam.
#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

/**
 * Perilla de ángulo (el «Control Knob» del tab Params de Grasshopper).
 *
 * Existe porque Jam tiene **~50 parámetros que son rotaciones** —yaw/pitch/roll, ángulos de rama,
 * `start_angle`, `degrees`— y todos se editaban tipeando o arrastrando un número horizontal. Un
 * ángulo no es una cantidad cualquiera: es una DIRECCIÓN, y una aguja dice hacia dónde apunta de un
 * vistazo mientras que «137.5» hay que imaginárselo.
 *
 * **Acompaña al número, no lo reemplaza.** Se dibuja al lado del spinbox, que sigue estando para
 * tipear un valor exacto: una perilla sola sacaría la capacidad de escribir 137,5 y dejaría al
 * usuario peleando con el mouse por medio grado. Es también la postura de riesgo correcta para un
 * widget dibujado a mano — si la aguja pinta mal, el campo sigue funcionando.
 *
 * El valor NO se acota ni se envuelve: un yaw de 720° es dos vueltas y significa algo distinto de
 * 0° en cuanto alguien lo anima o lo acumula. La aguja muestra el resto de 360; el número, todo.
 */
class SJamKnob : public SCompoundWidget
{
public:
	DECLARE_DELEGATE_OneParam(FOnAngleChanged, float);

	SLATE_BEGIN_ARGS(SJamKnob)
		: _Angle(0.0f)
		, _Diameter(26.0f)
		// Ámbar OSCURO y no el del pin `N`. El ámbar saturado se lee lindo sobre la insignia
		// oscura de un icono, pero contra el cuerpo gris claro de la ficha da 1,46:1 — por debajo
		// del 3:1 que pide WCAG para un control—. Éste da 3,61:1 y sigue siendo ámbar.
		, _Color(FLinearColor(0.32f, 0.15f, 0.02f, 1.0f))
	{}
		/** Grados actuales. Se lee en cada pintada: la perilla no guarda estado propio. */
		SLATE_ATTRIBUTE(float, Angle)
		SLATE_ARGUMENT(float, Diameter)
		SLATE_ARGUMENT(FLinearColor, Color)
		/** Mientras se arrastra, por cada movimiento (para el live view). */
		SLATE_EVENT(FOnAngleChanged, OnAngleChanged)
		/** Al soltar: UN paso de historial por arrastre, no uno por frame. */
		SLATE_EVENT(FOnAngleChanged, OnAngleCommitted)
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
	/** Los grados que corresponden a la posición del mouse dentro del widget. */
	float AnguloDelPuntero(const FGeometry& Geometry, const FPointerEvent& Event) const;

	TAttribute<float> Angle;
	float Diameter = 26.0f;
	FLinearColor Color = FLinearColor::White;
	FOnAngleChanged OnAngleChanged;
	FOnAngleChanged OnAngleCommitted;

	/** Acumula vueltas: arrastrar más allá de 360 sigue sumando en vez de saltar a cero. */
	bool bArrastrando = false;
	float AnguloAlAgarrar = 0.0f;
	float ValorAlAgarrar = 0.0f;
};
