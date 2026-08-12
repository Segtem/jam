// Copyright Jam.
#include "SJamScrub.h"

#include "Rendering/DrawElements.h"

namespace
{
	/** Unidades por píxel arrastrado. Uno es lo predecible: el número sigue al mouse. */
	constexpr float UnidadesPorPixel = 1.0f;

	/** La tinta de la ficha, la misma del texto y del aro de la perilla. Contra el cuerpo gris
	 *  claro —(0.76, 0.77, 0.78)— da 4,45:1, arriba del 3:1 que pide WCAG para un control. */
	const FLinearColor Tinta(0.10f, 0.10f, 0.11f, 0.95f);

	/** ¿Este texto es un número y no una expresión?
	 *
	 *  Un param numérico puede llevar `=radio * 2` o el nombre pelado de una variable. Arrastrar
	 *  sobre eso lo reemplazaría por un número y rompería en silencio un vínculo que alguien armó
	 *  a propósito — y el nodo seguiría dando un resultado plausible, que es lo que lo vuelve caro
	 *  de encontrar.
	 */
	bool EsNumeroPelado(const FString& Texto)
	{
		const FString Limpio = Texto.TrimStartAndEnd();
		if (Limpio.IsEmpty() || Limpio.StartsWith(TEXT("=")))
		{
			return false;
		}
		return Limpio.IsNumeric();
	}
}

void SJamScrub::Construct(const FArguments& InArgs)
{
	TextoActual = InArgs._TextoActual;
	bEntero = InArgs._Entero;
	Alto = FMath::Max(10.0f, InArgs._Alto);
	OnValueChanged = InArgs._OnValueChanged;
	OnValueCommitted = InArgs._OnValueCommitted;
	SetCursor(EMouseCursor::ResizeLeftRight);
}

FVector2D SJamScrub::ComputeDesiredSize(float) const
{
	return FVector2D(9.0f, Alto);
}

FReply SJamScrub::OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event)
{
	if (Event.GetEffectingButton() != EKeys::LeftMouseButton || !TextoActual.IsBound())
	{
		return FReply::Unhandled();
	}
	const FString Texto = TextoActual.Execute();
	if (!EsNumeroPelado(Texto))
	{
		// Sin agarrar: el campo tiene una expresión y arrastrarlo la destruiría. No hacer nada es
		// la respuesta correcta — el campo sigue ahí para editarla a mano.
		return FReply::Unhandled();
	}
	bArrastrando = true;
	XAlAgarrar = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition()).X;
	ValorAlAgarrar = FCString::Atof(*Texto);
	UltimoValor = ValorAlAgarrar;
	// El tirador mide 9 px: sin capturar el mouse, el arrastre se cortaría apenas se sale de él.
	return FReply::Handled().CaptureMouse(SharedThis(this));
}

FReply SJamScrub::OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event)
{
	if (!bArrastrando)
	{
		return FReply::Unhandled();
	}
	const float X = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition()).X;
	float Nuevo = ValorAlAgarrar + (X - XAlAgarrar) * UnidadesPorPixel;

	// SHIFT acomoda a enteros, con el mismo sentido que en la perilla: la tecla lleva a valores
	// redondos. Un param declarado `int` se acomoda SIEMPRE — arrastrar `count` hasta 7,4 no
	// significa nada y el nodo lo truncaría después sin decirlo.
	if (bEntero || Event.IsShiftDown())
	{
		Nuevo = FMath::RoundToFloat(Nuevo);
	}
	UltimoValor = Nuevo;
	OnValueChanged.ExecuteIfBound(Nuevo);
	return FReply::Handled();
}

FReply SJamScrub::OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event)
{
	if (!bArrastrando || Event.GetEffectingButton() != EKeys::LeftMouseButton)
	{
		return FReply::Unhandled();
	}
	bArrastrando = false;
	OnValueCommitted.ExecuteIfBound(UltimoValor);
	return FReply::Handled().ReleaseMouseCapture();
}

int32 SJamScrub::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
	int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	const FVector2D Size = AllottedGeometry.GetLocalSize();
	const float Medio = Size.Y * 0.5f;

	// Tres rayitas verticales: la señal universal de «esto se agarra». Se dibujan con el mismo
	// grosor y tinta que el aro de la perilla, para que los dos controles se lean como familia.
	for (int32 i = 0; i < 3; ++i)
	{
		const float X = Size.X * 0.5f + (i - 1) * 2.5f;
		TArray<FVector2D> Raya;
		Raya.Add(FVector2D(X, Medio - 4.0f));
		Raya.Add(FVector2D(X, Medio + 4.0f));
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 1,
			AllottedGeometry.ToPaintGeometry(), Raya, ESlateDrawEffect::None, Tinta, true, 1.2f);
	}
	return LayerId + 1;
}
