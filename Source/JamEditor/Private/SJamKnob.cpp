// Copyright Jam.
#include "SJamKnob.h"

#include "Rendering/DrawElements.h"
#include "Styling/AppStyle.h"

void SJamKnob::Construct(const FArguments& InArgs)
{
	Angle = InArgs._Angle;
	Diameter = FMath::Max(12.0f, InArgs._Diameter);
	Color = InArgs._Color;
	OnAngleChanged = InArgs._OnAngleChanged;
	OnAngleCommitted = InArgs._OnAngleCommitted;
	SetCursor(EMouseCursor::GrabHand);
}

FVector2D SJamKnob::ComputeDesiredSize(float) const
{
	return FVector2D(Diameter, Diameter);
}

float SJamKnob::AnguloDelPuntero(const FGeometry& Geometry, const FPointerEvent& Event) const
{
	const FVector2D Local = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition());
	const FVector2D Centro = Geometry.GetLocalSize() * 0.5f;
	const FVector2D D = Local - Centro;
	// Cero ARRIBA y creciendo en el sentido de las agujas del reloj, que es como se lee un ángulo
	// en el viewport de Unreal cuando se mira desde arriba. En pantalla la Y crece hacia abajo, así
	// que el atan2 va con la Y invertida.
	return FMath::RadiansToDegrees(FMath::Atan2(D.X, -D.Y));
}

FReply SJamKnob::OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event)
{
	if (Event.GetEffectingButton() != EKeys::LeftMouseButton)
	{
		return FReply::Unhandled();
	}
	bArrastrando = true;
	AnguloAlAgarrar = AnguloDelPuntero(Geometry, Event);
	ValorAlAgarrar = Angle.Get();
	// Capturar el mouse: sin esto, arrastrar afuera del círculo suelta la perilla a mitad de gesto,
	// que es justo lo que pasa siempre porque el círculo mide 26 px.
	return FReply::Handled().CaptureMouse(SharedThis(this));
}

FReply SJamKnob::OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event)
{
	if (!bArrastrando)
	{
		return FReply::Unhandled();
	}
	// El DELTA desde donde se agarró, no el ángulo absoluto del puntero: así la aguja no salta al
	// tocarla, que es la diferencia entre una perilla y un selector.
	float Delta = AnguloDelPuntero(Geometry, Event) - AnguloAlAgarrar;
	// Normalizar el salto de ±360 al cruzar el tope de atan2; sin esto una vuelta completa hace
	// pegar un salto de 360 en el valor.
	while (Delta > 180.0f) { Delta -= 360.0f; }
	while (Delta < -180.0f) { Delta += 360.0f; }
	const float Nuevo = ValorAlAgarrar + Delta;
	OnAngleChanged.ExecuteIfBound(Nuevo);
	return FReply::Handled();
}

FReply SJamKnob::OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event)
{
	if (!bArrastrando || Event.GetEffectingButton() != EKeys::LeftMouseButton)
	{
		return FReply::Unhandled();
	}
	bArrastrando = false;
	OnAngleCommitted.ExecuteIfBound(Angle.Get());
	return FReply::Handled().ReleaseMouseCapture();
}

int32 SJamKnob::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
	int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	const FVector2D Size = AllottedGeometry.GetLocalSize();
	const FVector2D Centro = Size * 0.5f;
	const float Radio = FMath::Min(Size.X, Size.Y) * 0.5f - 1.5f;
	if (Radio <= 1.0f)
	{
		return LayerId;
	}

	// La TINTA de la ficha, la misma que su texto (`JamInk` en SJamGraphNode.cpp). El cuerpo del
	// nodo es gris claro —(0.76, 0.77, 0.78)— así que un aro gris medio a media transparencia
	// prácticamente no existe: la primera versión se dibujaba en (0.55, 0.55, 0.58) al 55% y de la
	// perilla sólo se veía la aguja, un guioncito suelto al lado del campo. Contra ese fondo, lo
	// estructural va en tinta oscura, igual que las letras.
	//
	// Medido, no elegido a ojo: el aro viejo daba **1,17:1** contra el cuerpo de la ficha y éste da
	// **4,45:1**. El mínimo para un control de interfaz es 3:1 (WCAG 1.4.11, «Non-text Contrast»),
	// y el alfa CUENTA — mezclar 55% de gris medio con el fondo es casi el fondo.
	const FLinearColor Tinta(0.10f, 0.10f, 0.11f, 0.95f);

	auto Lineas = [&](const TArray<FVector2D>& Puntos, const FLinearColor& C, float Grosor)
	{
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 1,
			AllottedGeometry.ToPaintGeometry(), Puntos, ESlateDrawEffect::None, C, true, Grosor);
	};

	// El aro. 24 segmentos alcanzan para que se lea como círculo a 26 px y no cuesta nada.
	TArray<FVector2D> Aro;
	const int32 Segmentos = 24;
	for (int32 i = 0; i <= Segmentos; ++i)
	{
		const float T = (2.0f * PI * i) / Segmentos;
		Aro.Add(Centro + FVector2D(FMath::Sin(T), -FMath::Cos(T)) * Radio);
	}
	Lineas(Aro, Tinta, 1.4f);

	// La marca del cero, arriba: sin una referencia fija la aguja no dice de dónde mide.
	TArray<FVector2D> Cero;
	Cero.Add(Centro + FVector2D(0.0f, -Radio));
	Cero.Add(Centro + FVector2D(0.0f, -Radio * 0.62f));
	Lineas(Cero, Tinta, 1.4f);

	// La aguja. Se dibuja el RESTO de 360 —dos vueltas apuntan igual que ninguna— mientras el
	// número del costado sigue diciendo el valor entero, que es lo que distingue 720 de 0.
	const float Grados = FMath::Fmod(Angle.Get(), 360.0f);
	const float Radianes = FMath::DegreesToRadians(Grados);
	TArray<FVector2D> Aguja;
	Aguja.Add(Centro);
	Aguja.Add(Centro + FVector2D(FMath::Sin(Radianes), -FMath::Cos(Radianes)) * (Radio * 0.86f));
	Lineas(Aguja, Color, 2.4f);

	return LayerId + 1;
}
