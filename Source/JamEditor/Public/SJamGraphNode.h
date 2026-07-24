#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Brushes/SlateRoundedBoxBrush.h"

class SEditableTextBox;

/** (nombre, default) de un param — typedef para no romper los macros SLATE_* con la coma del TPair. */
using FJamNodeParam = TPair<FString, FString>;

DECLARE_DELEGATE_OneParam(FOnNodeDragDelta, const FVector2D&);

/**
 * Un nodo del canvas «Grasshopper» de Jam: caja arrastrable con título (verbo), campos de params,
 * pin de entrada (izq) y salida (der), y botón borrar. Es sólo la VISTA; el grafo/ejecución viven
 * en `jam.graph`. El header (o cualquier zona no interactiva) arrastra el nodo.
 */
class SJamGraphNode : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SJamGraphNode) {}
		SLATE_ARGUMENT(FString, Verb)
		/** Código corto del badge (icono) y su color de categoría — como el ribbon. */
		SLATE_ARGUMENT(FString, Icon)
		SLATE_ARGUMENT(FLinearColor, IconColor)
		/** (nombre, default) por cada param. */
		SLATE_ARGUMENT(TArray<FJamNodeParam>, Params)
		/** false en los nodos FUENTE (asset, create_spline): no reciben nada, van sin pin de entrada
		 *  — la convención de Grasshopper para componentes sin inputs. */
		SLATE_ARGUMENT(bool, HasInput)
		SLATE_EVENT(FOnNodeDragDelta, OnDragDelta)
		SLATE_EVENT(FSimpleDelegate, OnOutputClicked)
		SLATE_EVENT(FSimpleDelegate, OnInputClicked)
		SLATE_EVENT(FSimpleDelegate, OnDeleteClicked)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	/** Valores actuales de los params (leídos de los text boxes). */
	TMap<FString, FString> GetParamValues() const;
	const FString& GetVerb() const { return Verb; }

	/**
	 * Pinta el nodo con el veredicto del ORÁCULO tras correr el grafo. Es la convención de estados de
	 * Grasshopper (naranja = warning, rojo = error) pero alimentada por lo que Jam sabe verificar:
	 * "ok" ✓ verde · "warn" (REVISAR ✗) naranja · "error" rojo · "" vuelve a neutro. El texto queda
	 * como tooltip del nodo.
	 */
	void SetResult(const FString& State, const FString& Text);

	// Arrastre: si el click no lo toma un hijo interactivo (param/pin), arrastra el nodo.
	virtual FReply OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	// Dibuja el cuerpo CÁPSULA (redondeado, con borde = veredicto) detrás de los hijos, como GH.
	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

private:
	/** Color del borde de la cápsula según el veredicto del oráculo (verde/naranja/rojo/neutro). */
	FLinearColor StateColor() const;
	/** Rehace el pincel del cuerpo con el borde del estado actual. */
	void RebuildBodyBrush();

	FString Verb;
	FString Icon;
	FLinearColor IconColor = FLinearColor(0.35f, 0.35f, 0.38f, 1.0f);
	FString ResultState;
	bool bDragging = false;
	/** Cuerpo redondeado (cápsula GH): relleno gris claro + borde = veredicto. */
	FSlateRoundedBoxBrush BodyBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.80f, 0.80f, 0.78f, 1.0f), 6.0f, FLinearColor(0.10f, 0.10f, 0.10f, 1.0f), 1.0f);
	FOnNodeDragDelta OnDragDelta;
	FSimpleDelegate OnInputClickedDelegate;
	FSimpleDelegate OnOutputClickedDelegate;
	FSimpleDelegate OnDeleteClickedDelegate;
	TMap<FString, TSharedPtr<SEditableTextBox>> Fields;
};
