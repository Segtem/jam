#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Brushes/SlateImageBrush.h"
#include "Styling/SlateTypes.h"

class SEditableTextBox;

/** Un parámetro del nodo: valor, tipo de control, dominio opcional y tipo/color del cable esperado. */
struct FJamNodeParam
{
	FString Name;
	FString Value;
	FString Type;             // "bool" | "int" | "float" | "str" (del spec)
	TArray<FString> Options;  // dominio cerrado (enum) → dropdown en vez de texto libre
	FString DataType;         // tipo del cable esperado: N/N[]/T/B/A/A[]/AF/H/S/F/P/M
	FLinearColor PinColor = FLinearColor(0.28f, 0.30f, 0.34f, 1.0f);
	/** Nombre del PIN, cuando no es el de la etiqueta. La fila `asset` de un verbo que recibe un
	    asset por su entrada principal se llama «asset» —que es lo que hay que leer— pero SU PIN es
	    «in»: es la entrada del nodo, no un parámetro aparte. Sin esto habría dos pines (el nub del
	    header y el de la fila) para la misma cosa, y los grafos guardados anclarían su cable en un
	    pin que ya no se dibuja. */
	FString PinName;

	FJamNodeParam() = default;
	FJamNodeParam(const FString& InName, const FString& InValue,
		const FString& InType = FString(), const TArray<FString>& InOptions = TArray<FString>(),
		const FString& InDataType = FString(),
		const FLinearColor& InPinColor = FLinearColor(0.28f, 0.30f, 0.34f, 1.0f))
		: Name(InName), Value(InValue), Type(InType), Options(InOptions),
		  DataType(InDataType), PinColor(InPinColor) {}
};

/** Pin nombrado de una función: no es un parámetro editable, es parte de su firma. */
struct FJamNodePin
{
	FString Name;
	FString DataType;
	FString TypeLabel;
	FLinearColor Color = FLinearColor(0.28f, 0.30f, 0.34f, 1.0f);
};

DECLARE_DELEGATE_OneParam(FOnNodeDragDelta, const FVector2D&);
/** Clic en un pin de ENTRADA: pasa el nombre del pin — «in» = stream, o el nombre de un parámetro
 *  (count, spacing…). Cada parámetro es un pin propio, como en Grasshopper. */
DECLARE_DELEGATE_OneParam(FOnPinClicked, const FString& /*pin*/);
/** Clic en el CUERPO del nodo, con los modificadores: Shift agrega a la selección, Ctrl alterna.
 *  El nodo no sabe qué está seleccionado —eso es del editor—; sólo reporta el gesto. */
DECLARE_DELEGATE_TwoParams(FOnNodeClicked, bool /*bShift*/, bool /*bCtrl*/);

/**
 * Un componente del canvas «Grasshopper» de Jam: título flotante, cuerpo biselado, controles de
 * parámetros, grips de entrada/salida sobre los bordes y nombre central (futuro icono). Es sólo la VISTA; el
 * grafo/ejecución viven en `jam.graph`. Cualquier zona no interactiva arrastra el componente.
 */
class SJamGraphNode : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SJamGraphNode) {}
		SLATE_ARGUMENT(FString, Verb)
		/** Título humano separado del verbo interno. */
		SLATE_ARGUMENT(FString, DisplayName)
		/** Ruta absoluta del SVG que ocupa el centro del componente. */
		SLATE_ARGUMENT(FString, IconPath)
		SLATE_ARGUMENT(FLinearColor, IconColor)
		/** Nombre de la salida (la «variable» del pin de salida, estilo GH: P/N/T/A…). */
		SLATE_ARGUMENT(FString, OutName)
		/** Colores semánticos de los bordes de los grips de stream y salida. */
		SLATE_ARGUMENT(FLinearColor, InputColor)
		SLATE_ARGUMENT(FLinearColor, OutputColor)
		/** Nombre legible del tipo que entra/sale. Un pin no puede identificarse sólo por su color:
		    eso obliga a memorizar la paleta y no sirve con daltonismo ni con un monitor malo. */
		SLATE_ARGUMENT(FString, InputLabel)
		SLATE_ARGUMENT(FString, OutputLabel)
		/** (nombre, default) por cada param. */
		SLATE_ARGUMENT(TArray<FJamNodeParam>, Params)
		/** Firma dinámica. Se dibuja en filas enfrentadas, sin campos de valor. */
		SLATE_ARGUMENT(TArray<FJamNodePin>, InputPins)
		SLATE_ARGUMENT(TArray<FJamNodePin>, OutputPins)
		/** false en los nodos FUENTE (asset, create_spline): no reciben nada, van sin pin de entrada
		 *  — la convención de Grasshopper para componentes sin inputs. */
		SLATE_ARGUMENT(bool, HasInput)
		/** Si el nodo está en la selección del editor: pinta el halo aunque no tenga el foco. La
		    selección es un ESTADO del editor, no el foco de teclado — por eso llega como atributo y
		    no como un bool que habría que ir sincronizando nodo por nodo. */
		SLATE_ATTRIBUTE(bool, IsSelected)
		SLATE_EVENT(FOnNodeDragDelta, OnDragDelta)
		SLATE_EVENT(FOnPinClicked, OnOutputClicked)
		/** Recibe el nombre del pin: «in» (stream) o el de un parámetro. */
		SLATE_EVENT(FOnPinClicked, OnInputClicked)
		SLATE_EVENT(FSimpleDelegate, OnDeleteClicked)
		/** Clic en el cuerpo (con modificadores): el editor actualiza la selección. */
		SLATE_EVENT(FOnNodeClicked, OnClicked)
		/** `Supr` sobre el nodo. Lo resuelve el editor, que es el que sabe si hay varios elegidos. */
		SLATE_EVENT(FSimpleDelegate, OnDeleteSelection)
		/** Se soltó el nodo DESPUÉS de haberlo movido. Un paso del historial es el arrastre entero,
		    no cada frame; y un clic que no movió nada no es un paso. */
		SLATE_EVENT(FSimpleDelegate, OnDragEnd)
		/** Se confirmó el valor de un parámetro (Enter, perder el foco, soltar el slider, elegir del
		    dropdown). Sin este aviso el editor no se entera de lo que tipeás: los valores viven en
		    los widgets y `BuildJson` los lee recién cuando alguien los pide. */
		SLATE_EVENT(FSimpleDelegate, OnParamChanged)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	/** Valores actuales de los params (leídos de los text boxes). */
	TMap<FString, FString> GetParamValues() const;
	/** Fija los valores de los params (al cargar un diagrama desde archivo). */
	void SetParamValues(const TMap<FString, FString>& Values);
	/** Marca qué pines de parámetro tienen un CABLE entrando: su input se deshabilita (grisea), porque
	 *  el valor lo manda el cable y no el campo — el look de Grasshopper cuando un input está wired. */
	void SetCabledPins(const TSet<FString>& Pins) { CabledPins = Pins; }
	const FString& GetVerb() const { return Verb; }

	// Métrica FIJA del layout del nodo (filas de alto conocido) para que el editor calcule dónde cae
	// cada pin y ancle los wires exactamente ahí — como los grips por parámetro de Grasshopper.
	static constexpr float TitleH = 18.0f;   // cartela flotante con el nombre, estilo GH
	static constexpr float PadTop = TitleH + 5.0f;
	static constexpr float HeaderH = 26.0f;
	static constexpr float RowH = 23.0f;
	static constexpr float PadBottom = 6.0f;
	static constexpr float PinColW = 14.0f;    // ancho de las columnas de pines (izq/der)
	static constexpr float ParamColW = 104.0f; // ancho de la columna de params (nombre+valor)
	/** Y local del pin: índice de parámetro (0..n-1) o -1 para el header (stream «in» / salida «out»). */
	static float PinLocalY(int32 ParamIndex)
	{
		return ParamIndex < 0 ? PadTop + HeaderH * 0.5f
		                      : PadTop + HeaderH + ParamIndex * RowH + RowH * 0.5f;
	}
	/** Alto total del nodo con N parámetros (una fila fija por parámetro). */
	static float NodeHeight(int32 NumParams) { return PadTop + HeaderH + NumParams * RowH + PadBottom; }

	/**
	 * Pinta el nodo con el veredicto del ORÁCULO tras correr el grafo. Es la convención de estados de
	 * Grasshopper (naranja = warning, rojo = error) pero alimentada por lo que Jam sabe verificar:
	 * "ok" ✓ verde · "warn" (REVISAR ✗) naranja · "error" rojo · "" vuelve a neutro. El texto queda
	 * como tooltip del nodo.
	 */
	void SetResult(const FString& State, const FString& Text);

	// Arrastre/selección: si el click no lo toma un hijo interactivo, enfoca y arrastra el nodo.
	// El foco es también su selección persistente: Supr ejecuta el mismo borrado seguro que la ×.
	virtual bool SupportsKeyboardFocus() const override { return true; }
	virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
	virtual FReply OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	virtual FReply OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
	// Dibuja cartela, selección, cuerpo biselado y nombre central detrás de los controles, como GH.
	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

private:
	/** Color del borde del componente según el veredicto del oráculo (verde/naranja/rojo/neutro). */
	FLinearColor StateColor() const;
	/** Rehace el pincel del cuerpo con el borde del estado actual. */
	void RebuildBodyBrush();

	FString Verb;
	FString DisplayName;
	FString IconPath;
	FString OutName;
	FLinearColor IconColor = FLinearColor(0.35f, 0.35f, 0.38f, 1.0f);
	FString ResultState;
	bool bDragging = false;
	/** Estilo CLARO de los campos de valor (fondo claro, texto negro), como los inputs de GH. */
	FEditableTextBoxStyle FieldStyle;
	/** Spinboxes con el mismo acabado claro y compacto que los campos de texto. */
	FSpinBoxStyle SpinStyle;
	/** Booleanos claros: conserva la marca nativa, pero no hereda el fondo oscuro del editor. */
	FCheckBoxStyle CheckStyle;
	/** Cuerpo redondeado GH: gris normal, naranja/rojo para warning/error, borde = veredicto. */
	FSlateRoundedBoxBrush BodyBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.80f, 0.80f, 0.78f, 1.0f), 6.0f, FLinearColor(0.10f, 0.10f, 0.10f, 1.0f), 1.0f);
	/** Sombra, cartela y halo lavanda de hover/arrastre — equivalentes a relieve y selección de GH. */
	FSlateRoundedBoxBrush ShadowBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.0f, 0.0f, 0.0f, 0.26f), 6.0f);
	FSlateRoundedBoxBrush TitleBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.94f, 0.94f, 0.91f, 1.0f), 1.5f,
		FLinearColor(0.12f, 0.12f, 0.12f, 1.0f), 1.0f);
	FSlateRoundedBoxBrush SelectionBrush = FSlateRoundedBoxBrush(
		FLinearColor(0.55f, 0.35f, 0.82f, 0.22f), 7.0f,
		FLinearColor(0.43f, 0.24f, 0.70f, 0.90f), 2.0f);
	/** Pictograma SVG central; es propiedad del nodo para que el puntero usado por Slate siga vivo. */
	TSharedPtr<FSlateVectorImageBrush> IconBrush;
	FOnNodeDragDelta OnDragDelta;
	FOnPinClicked OnInputClickedDelegate;
	FOnPinClicked OnOutputClickedDelegate;
	FSimpleDelegate OnDeleteClickedDelegate;
	FOnNodeClicked OnClickedDelegate;
	FSimpleDelegate OnDeleteSelectionDelegate;
	FSimpleDelegate OnDragEndDelegate;
	FSimpleDelegate OnParamChangedDelegate;
	/** El arrastre movió el nodo de verdad (y no fue un clic con el pulso). */
	bool bMovioAlgo = false;
	/** Lo lee `OnPaint` para pintar el halo; la fuente es el `TSet` del editor. */
	TAttribute<bool> IsSelectedAttr;

public:
	/** Flag de debug del nodo: el display flag de Houdini / la tecla D de PCG. Cuando está
	 *  prendido, el Run dibuja la salida de ESTE nodo y vuelca sus datos al reporte. */
	bool IsDebugEnabled() const { return bDebugEnabled; }
	void SetDebugEnabled(bool bEnabled) { bDebugEnabled = bEnabled; }

private:
	bool bDebugEnabled = false;
	// Por cada param: cómo LEER su valor y cómo FIJARLO, sin que el resto del nodo sepa si el widget es
	// un text box, un checkbox (bool) o un dropdown (enum). Reemplaza al viejo mapa de sólo text boxes.
	TMap<FString, TFunction<FString()>> ParamGetters;
	TMap<FString, TFunction<void(const FString&)>> ParamSetters;
	/** Pines de parámetro que hoy tienen un cable entrando → su input se muestra deshabilitado. Lo
	 *  actualiza el editor tras cada cambio de aristas; los inputs lo leen por atributo (IsEnabled). */
	TSet<FString> CabledPins;
};
