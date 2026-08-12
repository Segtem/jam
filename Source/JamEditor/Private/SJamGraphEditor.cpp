#include "SJamGraphEditor.h"
#include "SJamGraphNode.h"
#include "SJamGraphComment.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SCanvas.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SWindow.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SSpinBox.h"
#include "Widgets/Input/SCheckBox.h"
#include "Brushes/SlateDynamicImageBrush.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Layout/SExpandableArea.h"
#include "Widgets/Layout/SSeparator.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/PlatformApplicationMisc.h"   // portapapeles del sistema (copiar/pegar nodos)
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "Brushes/SlateImageBrush.h"
#include "Interfaces/IPluginManager.h"
#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/MessageDialog.h"
#include "HAL/FileManager.h"
#include "Rendering/DrawElements.h"
#include "Math/TransformCalculus2D.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Dom/JsonObject.h"

#define LOCTEXT_NAMESPACE "JamGraphEditor"

// Tipo visual de un pin de parámetro. Es la misma clave que usa DataColor para cables y grips.
static FString JamParamDataType(const FString& Name, const FString& Type)
{
	if (Name.Contains(TEXT("spline"), ESearchCase::IgnoreCase)) { return TEXT("S"); }
	if (Type == TEXT("bool")) { return TEXT("B"); }
	if (Type == TEXT("int") || Type == TEXT("float")) { return TEXT("N"); }
	if (Type == TEXT("str")) { return TEXT("T"); }
	return FString();
}

/** Lee los params de una ficha JSON a un `FJamTool`.
 *
 *  Existe porque había TRES lectores de ficha escritos a mano —`LoadSpec`, `AplicarRespuestaFuncion`
 *  y `ColapsarSeleccion`— y sólo el primero leía `params`. Consecuencia: una función instalada en
 *  vivo perdía sus perillas y aparecía con los pines pelados; recién reaparecían al reiniciar, que
 *  es el peor síntoma posible (funciona a veces). */
static void JamLeerParamsDeFicha(const TSharedPtr<FJsonObject>& Ficha, TArray<FJamParam>& Destino)
{
	const TArray<TSharedPtr<FJsonValue>>* Ps = nullptr;
	if (!Ficha.IsValid() || !Ficha->TryGetArrayField(TEXT("params"), Ps) || Ps == nullptr)
	{
		return;
	}
	for (const TSharedPtr<FJsonValue>& PV : *Ps)
	{
		const TSharedPtr<FJsonObject> PO = PV.IsValid() ? PV->AsObject() : nullptr;
		if (!PO.IsValid()) { continue; }
		FJamParam P;
		if (!PO->TryGetStringField(TEXT("nombre"), P.Name)) { continue; }
		if (!PO->TryGetStringField(TEXT("label"), P.Label)) { P.Label = P.Name; }
		PO->TryGetStringField(TEXT("default"), P.Default);
		if (!PO->TryGetStringField(TEXT("tipo"), P.Type)) { P.Type = TEXT("str"); }
		PO->TryGetStringField(TEXT("data_type"), P.DataType);
		PO->TryGetStringField(TEXT("letra"), P.Letra);
		const TArray<TSharedPtr<FJsonValue>>* Opts = nullptr;
		if (PO->TryGetArrayField(TEXT("opciones"), Opts) && Opts != nullptr)
		{
			for (const TSharedPtr<FJsonValue>& OV : *Opts)
			{
				P.Options.Add(MakeShared<FString>(OV->AsString()));
			}
		}
		Destino.Add(MoveTemp(P));
	}
}

/** ¿Este verbo se puede apagar dejando pasar el stream?
 *
 *  ÚNICA copia en C++ de la regla; la fuente es `jam.graph.puede_bypass`, y las dos están atadas
 *  por `BypassSoloConMismoTipoTests`, que LEE este archivo. Se duplica en vez de preguntarle a
 *  Python porque decide si un nodo dibuja o no su botón: es una respuesta por nodo y por frame.
 *
 *  Sólo si recibe y produce el MISMO tipo. Un verbo M → A apagado sacaría una M por un pin que
 *  promete A y rompería a todo lo que tenga cableado abajo. Una FUENTE tampoco: no tiene entrada
 *  que dejar pasar. */
static bool JamPuedeBypass(const FJamTool& T)
{
	return !T.bSource && T.Arity != 0 && !T.InName.IsEmpty() && T.InName == T.OutName;
}

/** Diálogo modal mínimo para nombres. Devuelve false al cancelar o cerrar la ventana. */
static bool JamPedirNombre(const FText& Titulo, const FString& Inicial,
	const TSharedRef<SWidget>& Owner, FString& OutNombre)
{
	bool bAceptado = false;
	TSharedPtr<SEditableTextBox> Campo;
	TSharedPtr<SWindow> Dialogo;
	SAssignNew(Dialogo, SWindow)
		.Title(Titulo).ClientSize(FVector2D(420.0f, 125.0f))
		.SupportsMaximize(false).SupportsMinimize(false)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(12.0f, 10.0f, 12.0f, 4.0f)
			[ SNew(STextBlock).Text(LOCTEXT("FunctionNamePrompt", "Nombre de la función")) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(12.0f, 0.0f, 12.0f, 10.0f)
			[
				SAssignNew(Campo, SEditableTextBox)
				.Text(FText::FromString(Inicial))
				.HintText(LOCTEXT("FunctionNameHint", "Ej.: Preparar roca para fractura"))
				.SelectAllTextWhenFocused(true)
			]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(12.0f, 0.0f, 12.0f, 10.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 6.0f, 0.0f)
				[
					SNew(SButton).Text(LOCTEXT("FunctionNameCancel", "Cancelar"))
					.OnClicked_Lambda([&Dialogo]()
					{ Dialogo->RequestDestroyWindow(); return FReply::Handled(); })
				]
				+ SHorizontalBox::Slot().AutoWidth()
				[
					SNew(SButton).Text(LOCTEXT("FunctionNameAccept", "Aceptar"))
					.IsEnabled_Lambda([&Campo]()
					{ return Campo.IsValid() && !Campo->GetText().IsEmptyOrWhitespace(); })
					.OnClicked_Lambda([&OutNombre, &bAceptado, &Campo, &Dialogo]()
					{
						OutNombre = Campo->GetText().ToString().TrimStartAndEnd();
						bAceptado = !OutNombre.IsEmpty();
						Dialogo->RequestDestroyWindow();
						return FReply::Handled();
					})
				]
			]
		];
	FSlateApplication::Get().AddModalWindow(
		Dialogo.ToSharedRef(), FSlateApplication::Get().FindBestParentWindowForDialogs(Owner));
	return bAceptado;
}

// El mapping vive junto a los SVG para que cambiar un pictograma no obligue a recompilar C++.
// Se lee una vez al abrir la UI; si el JSON está roto o no existe, los badges/nodos usan su fallback.
static const TMap<FString, FString>& JamIconMap()
{
	static const TMap<FString, FString> Map = []()
	{
		TMap<FString, FString> Loaded;
		const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
		if (!Plugin.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] no encontré el plugin Jam para cargar iconos."));
			return Loaded;
		}

		const FString MapPath = FPaths::Combine(
			Plugin->GetBaseDir(), TEXT("Resources/Icons/Lucide/icon-map.json"));
		FString Json;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Json, *MapPath))
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] icon-map.json no se pudo leer: %s"), *MapPath);
			return Loaded;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] icon-map.json no es JSON válido: %s"), *MapPath);
			return Loaded;
		}

		for (const TPair<FString, TSharedPtr<FJsonValue>> Entry : Root->Values)
		{
			FString IconName;
			if (Entry.Value.IsValid() && Entry.Value->TryGetString(IconName) && !IconName.IsEmpty())
			{
				Loaded.Add(Entry.Key, IconName);
			}
		}
		return Loaded;
	}();
	return Map;
}

// ---- el tab Aprender: los tutoriales, leídos de un manifiesto ----
// Estaban como cinco entradas «Abrir ejemplo: …» dentro del menú File, que es donde nadie mira
// cuando está empezando, y como cinco funciones C++ que sólo se diferenciaban en un nombre de
// archivo. Ahora son DATO: `Resources/Examples/examples.json` los lista, y agregar un tutorial es
// soltar el .jamgraph y sumarle una línea — sin recompilar el plugin, igual que los iconos.

struct FJamExample
{
	FString File;
	FString Title;
	FString Doc;
	FString Group;
	FString Icon;
	FString Message;
	/** 1..N si el tutorial forma parte del CAMINO (la ruta ordenada); 0 si es de los otros.
	 *  Vive en el manifiesto y no acá para que reordenar lo que alguien aprende primero no
	 *  necesite recompilar el plugin. */
	int32 Paso = 0;
	/** La razón del paso en UNA línea. `Doc` es el texto largo, que va al tooltip. */
	FString Why;
};

// El nombre del tab. No sale del spec de verbos porque no es una categoría de verbos: no hay
// ningún `FJamTool` con esta categoría, y sus fichas CARGAN un grafo en vez de crear un nodo.
static const TCHAR* JamLearnTab = TEXT("Aprender");

// ---- el progreso: qué tutoriales ya abrió esta persona ----
// Va al ini del editor y no al proyecto: es de la PERSONA, no del juego. Dos personas en el mismo
// repo aprenden por su cuenta, y el progreso de una no tiene por qué aparecerle a la otra en un
// diff. Guardar una lista de archivos y no un contador permite además reordenar el camino sin que
// el progreso quede sin sentido — el paso 3 de ayer puede ser el 4 de mañana.
static const TCHAR* JamAprenderSeccion = TEXT("JamAprender");
static const TCHAR* JamAprenderClave = TEXT("Vistos");

static TSet<FString>& JamVistos()
{
	static TSet<FString> Vistos = []()
	{
		TSet<FString> Salida;
		FString Guardado;
		if (GConfig && GConfig->GetString(JamAprenderSeccion, JamAprenderClave, Guardado,
		                                 GEditorPerProjectIni))
		{
			TArray<FString> Partes;
			Guardado.ParseIntoArray(Partes, TEXT("|"), true);
			for (const FString& Parte : Partes)
			{
				Salida.Add(Parte.TrimStartAndEnd());
			}
		}
		return Salida;
	}();
	return Vistos;
}

static void JamMarcarVisto(const FString& Archivo)
{
	if (Archivo.IsEmpty() || JamVistos().Contains(Archivo))
	{
		return;
	}
	JamVistos().Add(Archivo);
	if (GConfig)
	{
		GConfig->SetString(JamAprenderSeccion, JamAprenderClave,
			*FString::Join(JamVistos().Array(), TEXT("|")), GEditorPerProjectIni);
		GConfig->Flush(false, GEditorPerProjectIni);
	}
}

static const TArray<FJamExample>& JamExamples()
{
	static const TArray<FJamExample> Cargados = []()
	{
		TArray<FJamExample> Salida;
		const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
		if (!Plugin.IsValid())
		{
			return Salida;
		}
		const FString Path = FPaths::Combine(
			Plugin->GetBaseDir(), TEXT("Resources/Examples/examples.json"));
		FString Json;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Json, *Path))
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] examples.json no se pudo leer: %s"), *Path);
			return Salida;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("[JamEditor] examples.json no es JSON válido: %s"), *Path);
			return Salida;
		}
		const TArray<TSharedPtr<FJsonValue>>* Lista = nullptr;
		if (!Root->TryGetArrayField(TEXT("ejemplos"), Lista) || Lista == nullptr)
		{
			return Salida;
		}
		for (const TSharedPtr<FJsonValue>& Valor : *Lista)
		{
			const TSharedPtr<FJsonObject>* Objeto = nullptr;
			if (!Valor.IsValid() || !Valor->TryGetObject(Objeto) || Objeto == nullptr)
			{
				continue;
			}
			FJamExample E;
			(*Objeto)->TryGetStringField(TEXT("archivo"), E.File);
			(*Objeto)->TryGetStringField(TEXT("titulo"), E.Title);
			(*Objeto)->TryGetStringField(TEXT("doc"), E.Doc);
			(*Objeto)->TryGetStringField(TEXT("grupo"), E.Group);
			(*Objeto)->TryGetStringField(TEXT("icono"), E.Icon);
			(*Objeto)->TryGetStringField(TEXT("mensaje"), E.Message);
			(*Objeto)->TryGetStringField(TEXT("porque"), E.Why);
			(*Objeto)->TryGetNumberField(TEXT("paso"), E.Paso);
			if (!E.File.IsEmpty())
			{
				Salida.Add(MoveTemp(E));
			}
		}
		return Salida;
	}();
	return Cargados;
}

static FString JamIconPath(const FString& IconName)
{
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
	if (IconName.IsEmpty() || !Plugin.IsValid())
	{
		return FString();
	}
	const FString Path = FPaths::Combine(
		Plugin->GetBaseDir(), TEXT("Resources/Icons/Lucide"), IconName + TEXT(".svg"));
	return IFileManager::Get().FileExists(*Path) ? Path : FString();
}

// ---- el gesto de la paleta: clic = al medio, arrastre = donde soltás ----
//
// Son los dos gestos que uno ya tiene en los dedos, y cada uno resuelve un caso distinto:
//
//  · CLIC suelto — «quiero este nodo, no me importa dónde». Cae en el centro de lo que estás
//    mirando, que es donde lo vas a buscar. Antes caía en una cascada desde la esquina, así que
//    con el canvas paneado el nodo aparecía fuera de cuadro y parecía que el botón no hacía nada.
//  · ARRASTRAR — «quiero este nodo ACÁ». Es lo que hace cualquiera que ya usó Grasshopper o un
//    editor de nodos, y no requiere aprender nada.

class FJamVerbDrag : public FDragDropOperation
{
public:
	DRAG_DROP_OPERATOR_TYPE(FJamVerbDrag, FDragDropOperation)

	static TSharedRef<FJamVerbDrag> New(const FString& InVerb, const FSlateBrush* InIcon)
	{
		TSharedRef<FJamVerbDrag> Op = MakeShared<FJamVerbDrag>();
		Op->Verb = InVerb;
		Op->Icon = InIcon;
		Op->Construct();
		return Op;
	}

	/** El cursor lleva el ICONO del verbo mientras arrastrás: sin eso no se ve qué estás soltando. */
	virtual TSharedPtr<SWidget> GetDefaultDecorator() const override
	{
		return SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Menu.Background"))
			.Padding(4.0f)
			[
				SNew(STextBlock).Text(FText::FromString(Verb))
			];
	}

	FString Verb;
	const FSlateBrush* Icon = nullptr;
};

/** Ficha del ribbon. Distingue el clic del arrastre sin que el usuario tenga que saberlo. */
class SJamVerbTile : public SCompoundWidget
{
public:
	DECLARE_DELEGATE_OneParam(FOnVerbClicked, FString);

	SLATE_BEGIN_ARGS(SJamVerbTile) {}
		SLATE_ARGUMENT(FString, Verb)
		SLATE_EVENT(FOnVerbClicked, OnClicked)
		SLATE_DEFAULT_SLOT(FArguments, Content)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs)
	{
		Verb = InArgs._Verb;
		OnClicked = InArgs._OnClicked;
		ChildSlot[ InArgs._Content.Widget ];
	}

	virtual FReply OnMouseButtonDown(const FGeometry&, const FPointerEvent& E) override
	{
		if (E.GetEffectingButton() == EKeys::LeftMouseButton)
		{
			// `DetectDrag` es lo que deja que el MISMO botón sirva para las dos cosas: si el mouse
			// se mueve, Slate llama a OnDragDetected; si se suelta sin moverse, llega OnMouseButtonUp.
			return FReply::Handled().DetectDrag(SharedThis(this), EKeys::LeftMouseButton);
		}
		return FReply::Unhandled();
	}

	virtual FReply OnDragDetected(const FGeometry&, const FPointerEvent&) override
	{
		return FReply::Handled().BeginDragDrop(FJamVerbDrag::New(Verb, nullptr));
	}

	virtual FReply OnMouseButtonUp(const FGeometry&, const FPointerEvent& E) override
	{
		if (E.GetEffectingButton() == EKeys::LeftMouseButton)
		{
			OnClicked.ExecuteIfBound(Verb);
			return FReply::Handled();
		}
		return FReply::Unhandled();
	}

private:
	FString Verb;
	FOnVerbClicked OnClicked;
};

// Fondo del canvas (como el de Grasshopper): color de fondo + una GRILLA fina alineada al pan/zoom.
// Es la capa MÁS de atrás de todas — las cajas de comentario pintan (y tiñen) por encima de ella,
// igual que en Blueprint, donde el color de una comment box tapa la grilla dentro de su área.
class SJamGridLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamGridLayer) {}
	SLATE_END_ARGS()

	void Construct(const FArguments&, TFunction<void(FVector2D&, float&)> InXform)
	{
		XformGetter = MoveTemp(InXform);
		// Sólo pinta: si fuera hit-testeable, al llenar TODO el canvas se robaría los clics de
		// cualquier cosa apilada encima de ella en el SOverlay (mismo trato que SJamMarqueeLayer).
		SetVisibility(EVisibility::HitTestInvisible);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		const FVector2D Size = AllottedGeometry.GetLocalSize();

		// Fondo del canvas: gris claro clásico de Grasshopper/Rhino 7.
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId, AllottedGeometry.ToPaintGeometry(),
			FAppStyle::GetBrush("WhiteBrush"), ESlateDrawEffect::None,
			FLinearColor(0.827f, 0.835f, 0.812f, 1.0f));

		// Grilla: líneas cada 24 u de modelo, mayores cada 4. Alineada al pan/zoom (se mueve y escala
		// con el lienzo, como GH). Se saltea si el paso en pantalla es muy chico (zoom out).
		FVector2D Pan = FVector2D::ZeroVector;
		float Zoom = 1.0f;
		if (XformGetter) { XformGetter(Pan, Zoom); }
		const float Step = 24.0f * Zoom;
		if (Step >= 9.0f)
		{
			const FLinearColor Minor(0.0f, 0.0f, 0.0f, 0.06f);
			const FLinearColor Major(0.0f, 0.0f, 0.0f, 0.13f);
			auto Line = [&](const FVector2D& A, const FVector2D& B, const FLinearColor& C)
			{
				TArray<FVector2D> Pts; Pts.Add(A); Pts.Add(B);
				FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 1,
					AllottedGeometry.ToPaintGeometry(), Pts, ESlateDrawEffect::None, C, false, 1.0f);
			};
			float ox = FMath::Fmod(Pan.X * Zoom, Step); if (ox < 0) { ox += Step; }
			for (float x = ox; x < Size.X; x += Step)
			{
				const int32 k = FMath::RoundToInt((x / Zoom - Pan.X) / 24.0f);
				Line(FVector2D(x, 0.0f), FVector2D(x, Size.Y), (k % 4 == 0) ? Major : Minor);
			}
			float oy = FMath::Fmod(Pan.Y * Zoom, Step); if (oy < 0) { oy += Step; }
			for (float y = oy; y < Size.Y; y += Step)
			{
				const int32 k = FMath::RoundToInt((y / Zoom - Pan.Y) / 24.0f);
				Line(FVector2D(0.0f, y), FVector2D(Size.X, y), (k % 4 == 0) ? Major : Minor);
			}
		}
		return LayerId + 1;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<void(FVector2D&, float&)> XformGetter;
};

// Capa de WIRES (splines): en una capa PROPIA, por ENCIMA de las cajas de comentario — así una caja
// con el fondo bien tintado no tapa ni atenúa los cables que pasan por (o nacen/mueren dentro de) su
// área. Sigue yendo por debajo de los nodos: el pin es la punta visible del cable, no el cable el que
// tapa al nodo.
class SJamWireLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamWireLayer) {}
	SLATE_END_ARGS()

	void Construct(const FArguments&,
		TFunction<TArray<SJamGraphEditor::FJamWire>()> InGetter,
		TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)> InPending)
	{
		Getter = MoveTemp(InGetter);
		PendingGetter = MoveTemp(InPending);
		// Sólo pinta: ahora va POR ENCIMA de las cajas de comentario (para que no atenúen los cables),
		// y si fuera hit-testeable se robaría el clic de cualquier caja que tenga debajo — el hit-test
		// de Slate no sigue bajando a hermanos tapados, sólo burbujea hacia arriba en el árbol.
		SetVisibility(EVisibility::HitTestInvisible);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		// Cada wire con su COLOR por tipo de dato (como Blueprint/Substance): el color dice QUÉ
		// fluye. Un halo claro debajo levanta el contraste y ayuda a seguir el cable donde se cruzan.
		const FSlateBrush* Dot = FAppStyle::GetBrush("WhiteBrush");
		if (Getter)
		{
			const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry();
			for (const SJamGraphEditor::FJamWire& W : Getter())
			{
				const float dx = FMath::Max(50.0f, FMath::Abs(W.B.X - W.A.X) * 0.6f);
				const FVector2D T1(dx, 0.0f), T2(dx, 0.0f);
				// Halo OSCURO, no claro. El original era blanco al 55% «para levantar el contraste
				// sobre el lienzo gris», pero el lienzo es CLARO: un halo blanco lo aclaraba todavía
				// más y los 14 colores de cable quedaban entre 1.14:1 y 2.64:1 contra el fondo —
				// ninguno llegaba al mínimo de 3:1 que pide un elemento gráfico.
				//
				// Los colores de cable no se pueden oscurecer: están atados a los iconos por
				// `test_paleta`. El halo sí, y alcanza — le da a CUALQUIER cable un contorno que se
				// lee, sin tocar la paleta. Apenas más ancho que el cable: es un contorno, no una
				// línea negra que se coma el color.
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId, PG,
					W.A, T1, W.B, T2, 4.6f, ESlateDrawEffect::None,
					FLinearColor(0.10f, 0.10f, 0.11f, 0.85f));
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 1, PG,
					W.A, T1, W.B, T2, 2.6f, ESlateDrawEffect::None, W.Color);
				// punto en cada punta: ancla la conexión visualmente (como los pines de Blueprint).
				for (const FVector2D& P : {W.A, W.B})
				{
					FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 2,
						AllottedGeometry.ToPaintGeometry(FVector2D(6.0f, 6.0f),
							FSlateLayoutTransform(P - FVector2D(3.0f, 3.0f))),
						Dot, ESlateDrawEffect::None, W.Color);
				}
			}
		}

		// Cable-fantasma: del pin de salida armado al cursor, mientras se conecta (el rubber band de
		// Houdini/GH/Blueprint). Punteado-suave (semitransparente) para distinguirlo de los fijos.
		FVector2D PF, PT; FLinearColor PC;
		if (PendingGetter && PendingGetter(PF, PT, PC))
		{
			const float dx = FMath::Max(50.0f, FMath::Abs(PT.X - PF.X) * 0.6f);
			FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 3, AllottedGeometry.ToPaintGeometry(),
				PF, FVector2D(dx, 0.0f), PT, FVector2D(dx, 0.0f), 2.4f, ESlateDrawEffect::None,
				FLinearColor(PC.R, PC.G, PC.B, 0.7f));
			FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 4,
				AllottedGeometry.ToPaintGeometry(FVector2D(7.0f, 7.0f),
					FSlateLayoutTransform(PF - FVector2D(3.5f, 3.5f))),
				Dot, ESlateDrawEffect::None, PC);
		}
		return LayerId + 4;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<TArray<SJamGraphEditor::FJamWire>()> Getter;
	TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)> PendingGetter;
};


/**
 * El cuadro de selección (marquee). Va en una capa PROPIA por encima de los nodos: dibujado en la
 * capa de wires quedaría tapado justo por lo que se está tratando de encerrar. No recibe clics
 * (HitTestInvisible) — sólo pinta.
 */
class SJamMarqueeLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamMarqueeLayer) {}
	SLATE_END_ARGS()

	void Construct(const FArguments&,
		TFunction<bool(FVector2D&, FVector2D&)> InGetter,
		TFunction<void(FVector2D&, float&)> InXform)
	{
		Getter = MoveTemp(InGetter);
		XformGetter = MoveTemp(InXform);
		SetVisibility(EVisibility::HitTestInvisible);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		FVector2D A, B;
		if (!Getter || !Getter(A, B))
		{
			return LayerId;
		}
		FVector2D Pan = FVector2D::ZeroVector;
		float Zoom = 1.0f;
		if (XformGetter) { XformGetter(Pan, Zoom); }

		// El cuadro se guarda en MODELO; se lleva a pantalla con el mismo pan/zoom que los nodos,
		// así queda pegado al grafo aunque el lienzo esté paneado.
		const FVector2D P0((A + Pan) * Zoom);
		const FVector2D P1((B + Pan) * Zoom);
		const FVector2D Min(FMath::Min(P0.X, P1.X), FMath::Min(P0.Y, P1.Y));
		const FVector2D Max(FMath::Max(P0.X, P1.X), FMath::Max(P0.Y, P1.Y));

		const FSlateBrush* White = FAppStyle::GetBrush("WhiteBrush");
		// Relleno lavanda muy tenue + borde: el mismo idioma que el halo de selección del nodo, para
		// que se lea «esto va a quedar elegido» y no «esto es otra herramienta».
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId,
			AllottedGeometry.ToPaintGeometry(Max - Min, FSlateLayoutTransform(Min)),
			White, ESlateDrawEffect::None, FLinearColor(0.55f, 0.35f, 0.82f, 0.14f));

		TArray<FVector2D> Borde;
		Borde.Add(Min);
		Borde.Add(FVector2D(Max.X, Min.Y));
		Borde.Add(Max);
		Borde.Add(FVector2D(Min.X, Max.Y));
		Borde.Add(Min);
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 1, AllottedGeometry.ToPaintGeometry(),
			Borde, ESlateDrawEffect::None, FLinearColor(0.43f, 0.24f, 0.70f, 0.95f), true, 1.0f);
		return LayerId + 1;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<bool(FVector2D&, FVector2D&)> Getter;
	TFunction<void(FVector2D&, float&)> XformGetter;
};


void SJamGraphEditor::Construct(const FArguments& InArgs, const TArray<FJamTool>& InTools)
{
	Tools = InTools;
	OnRunGraph = InArgs._OnRunGraph;
	OnCompileGraph = InArgs._OnCompileGraph;
	OnBakePreview = InArgs._OnBakePreview;
	OnDiscardPreview = InArgs._OnDiscardPreview;
	OnSaveGraph = InArgs._OnSaveGraph;
	OnInspect = InArgs._OnInspect;
	OnPreview2D = InArgs._OnPreview2D;
	OnPreview2DTodos = InArgs._OnPreview2DTodos;
	OnGraphVariables = InArgs._OnGraphVariables;
	OnCableBajoPunto = InArgs._OnCableBajoPunto;
	OnLayout = InArgs._OnLayout;
	OnCollapseFunction = InArgs._OnCollapseFunction;
	OnFunctionManage = InArgs._OnFunctionManage;
	ActiveAsset = InArgs._ActiveAsset;
	OnOpenContent = InArgs._OnOpenContent;

	// El antiguo ribbon ponía unas veinte categorías en una sola tira horizontal. Ahora la primera
	// fila contiene FAMILIAS estables y una segunda fila corta elige la categoría real. `cat` sigue
	// siendo protocolo/color y `section` es sólo navegación: ningún preset cambia de identidad.
	Categories.Reset();
	Sections.Reset();
	for (const FJamTool& T : Tools)
	{
		Categories.AddUnique(T.Cat);
		Sections.AddUnique(T.Section.IsEmpty() ? T.Cat : T.Section);
	}
	if (ActiveTab.IsEmpty() && Categories.Num() > 0)
	{
		ActiveTab = Categories[0];
	}
	for (const FJamTool& T : Tools)
	{
		if (T.Cat == ActiveTab)
		{
			ActiveSection = T.Section.IsEmpty() ? T.Cat : T.Section;
			break;
		}
	}
	if (ActiveSection.IsEmpty() && Sections.Num() > 0) { ActiveSection = Sections[0]; }

	TSharedRef<SHorizontalBox> TabStrip = SNew(SHorizontalBox);
	TabStrip->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
	[
		SNew(SButton)
		.Text(LOCTEXT("PaletteContent", "Content…"))
		.ToolTipText(LOCTEXT("PaletteContentTip", "Elegir el asset activo (abre la ventana de Content)"))
		.OnClicked_Lambda([this]() { OnOpenContent.ExecuteIfBound(); return FReply::Handled(); })
	];
	// «Aprender» va PRIMERO —es lo que busca alguien que recién llega— pero NO es la familia por
	// defecto: quien usa Jam todos los días no quiere una pantalla de bienvenida entre él y sus
	// verbos. Se abre en el primer tab de trabajo y este queda a un clic, a la vista.
	Sections.Insert(JamLearnTab, 0);
	for (const FString& Section : Sections)
	{
		TabStrip->AddSlot().AutoWidth().Padding(1.0f, 0.0f)
		[
			SNew(SButton)
			.ToolTipText(Section == JamLearnTab
				? LOCTEXT("LearnTabTip", "Tutoriales y ejemplos: grafos armados para abrir, correr y desarmar")
				: FText::FromString(FString::Printf(TEXT("Familia «%s»"), *Section)))
			// activo = tono de la familia; inactivo = gris apagado.
			.ButtonColorAndOpacity_Lambda([this, Section]()
			{
				return ActiveSection == Section
					? CategoryColor(Section) : FLinearColor(0.22f, 0.22f, 0.24f, 1.0f);
			})
			.OnClicked_Lambda([this, Section]()
			{ SelectSection(Section); return FReply::Handled(); })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[ MakeBadge(CategoryColor(Section), Section.Left(2).ToUpper(), 14.0f) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f, 2.0f, 0.0f)
				[ SNew(STextBlock).Text(FText::FromString(Section)) ]
			]
		];
	}

	// Menú principal estilo Grasshopper (File / Edit / View / Display / Solution).
	FMenuBarBuilder MenuBar(nullptr);
	MenuBar.AddPullDownMenu(LOCTEXT("MenuFile", "File"), LOCTEXT("MenuFileTip", "Diagrama: nuevo, abrir, guardar"),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillFileMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuEdit", "Edit"), FText::GetEmpty(),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillEditMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuView", "View"), FText::GetEmpty(),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillViewMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuDisplay", "Display"), FText::GetEmpty(),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillDisplayMenu));
	MenuBar.AddPullDownMenu(LOCTEXT("MenuSolution", "Solution"), LOCTEXT("MenuSolutionTip", "Correr el grafo"),
		FNewMenuDelegate::CreateSP(this, &SJamGraphEditor::FillSolutionMenu));

	ChildSlot
	[
		SNew(SVerticalBox)

		// Barra de menú (File / Edit / View / Display / Solution), como Grasshopper.
		+ SVerticalBox::Slot().AutoHeight()
		[
			MenuBar.MakeWidget()
		]

		// Ribbon: fila de TABS (categorías).
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 6.0f, 6.0f, 0.0f)
		[
			SNew(SScrollBox).Orientation(Orient_Horizontal)
			+ SScrollBox::Slot()[ TabStrip ]
		]

		// Categorías reales de la familia activa. Son pocas y conservan nombre/color existentes.
		+ SVerticalBox::Slot().AutoHeight().Padding(8.0f, 2.0f, 8.0f, 0.0f)
		[
			SNew(SScrollBox).Orientation(Orient_Horizontal)
			.Visibility_Lambda([this]()
			{ return ActiveSection == JamLearnTab ? EVisibility::Collapsed : EVisibility::Visible; })
			+ SScrollBox::Slot()[ SAssignNew(CategoryStripBox, SHorizontalBox) ]
		]

		// Ribbon: fichas con icono de la categoría activa (se rellena en RebuildTabContent).
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f, 6.0f, 2.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Header"))
			.Padding(2.0f)
			[
				SNew(SScrollBox).Orientation(Orient_Horizontal)
				+ SScrollBox::Slot()[ SAssignNew(TabContentBox, SHorizontalBox) ]
			]
		]

		// Editar una función reemplaza temporalmente el canvas. La barra permanece visible aunque se
		// cambie de tab y ofrece el viaje de vuelta al documento anterior; antes File > Nuevo era el
		// único camino práctico y además dejaba el modo de edición prendido.
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 1.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Header"))
			.BorderBackgroundColor(FLinearColor(0.16f, 0.11f, 0.04f, 1.0f))
			.Padding(FMargin(8.0f, 4.0f))
			.Visibility_Lambda([this]()
			{
				return FuncionEnEdicion.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible;
			})
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
				[
					SNew(STextBlock)
					.Text_Lambda([this]()
					{
						return FText::FromString(FString(TEXT("Editando función: "))
							+ NombreFuncionEnEdicion
							+ TEXT(" · input/output definen sus pines"));
					})
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f)
				[
					SNew(SButton).Text(LOCTEXT("SaveAndCloseFunction", "Guardar y volver al grafo"))
					.OnClicked_Lambda([this]()
					{ GuardarYCerrarFuncion(); return FReply::Handled(); })
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f)
				[
					SNew(SButton).Text(LOCTEXT("CloseFunctionWithoutSave", "Volver sin guardar"))
					.ToolTipText(LOCTEXT("CloseFunctionWithoutSaveTip",
						"Descarta los cambios desde el último guardado y recupera el grafo anterior"))
					.OnClicked_Lambda([this]()
					{ VolverDeFuncion(false); return FReply::Handled(); })
				]
			]
		]

		// Canvas: wires detrás, nodos encima. RECORTADO a su área: sin esto, un nodo arrastrado cerca
		// del borde superior se dibuja por encima del ribbon y del menú.
		+ SVerticalBox::Slot().FillHeight(1.0f).Padding(6.0f, 2.0f)
		[
			SNew(SBorder)
			.BorderImage(FAppStyle::GetBrush("Brushes.Recessed"))
			.Padding(0.0f)
			.Clipping(EWidgetClipping::ClipToBounds)
			[
				SNew(SOverlay)
				// La capa MÁS de atrás: fondo gris + grilla. Las cajas de comentario tiñen por
				// encima de ella dentro de su área, igual que la comment box de Blueprint.
				+ SOverlay::Slot()
				[
					SNew(SJamGridLayer, TFunction<void(FVector2D&, float&)>(
						[this](FVector2D& P, float& Z) { P = PanOffset; Z = Zoom; }))
				]
				// Cajas de comentario/grupo: por encima de la grilla (para poder teñirla), por
				// debajo de los WIRES (para no atenuar un cable que pasa por, o nace/muere dentro
				// de, su área) y de los nodos (un nodo adentro se sigue clickeando/arrastrando
				// normal — el cuerpo de la caja sólo captura clics en el área libre, como Blueprint).
				+ SOverlay::Slot()
				[
					SAssignNew(CommentCanvas, SCanvas)
				]
				+ SOverlay::Slot()
				[
					SAssignNew(WireLayer, SJamWireLayer,
						TFunction<TArray<FJamWire>()>(
							[this]() { return GetWireEndpoints(); }),
						TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)>(
							[this](FVector2D& F, FVector2D& T, FLinearColor& C) { return GetPendingWire(F, T, C); }))
				]
				+ SOverlay::Slot()
				[
					SAssignNew(Canvas, SCanvas)
				]
				// Cuadro de selección, POR ENCIMA de los nodos (si no, lo tapa lo que estás encerrando).
				+ SOverlay::Slot()
				[
					SAssignNew(MarqueeLayer, SJamMarqueeLayer,
						TFunction<bool(FVector2D&, FVector2D&)>(
							[this](FVector2D& A, FVector2D& B) { return GetMarquee(A, B); }),
						TFunction<void(FVector2D&, float&)>(
							[this](FVector2D& P, float& Z) { P = PanOffset; Z = Zoom; }))
				]
				// Buscador de nodos (doble clic en el fondo), como el search box de Grasshopper.
				+ SOverlay::Slot()
				.HAlign(HAlign_Left)
				.VAlign(VAlign_Top)
				[
					SAssignNew(SearchPopup, SBorder)
					.BorderImage(FAppStyle::GetBrush("Menu.Background"))
					.Padding(4.0f)
					.Visibility_Lambda([this]() { return bSearchOpen ? EVisibility::Visible : EVisibility::Collapsed; })
					.RenderTransform_Lambda([this]() { return FSlateRenderTransform(SearchAt); })
					[
						SNew(SBox).WidthOverride(220.0f)
						[
							SNew(SVerticalBox)
							+ SVerticalBox::Slot().AutoHeight()
							[
								SAssignNew(SearchField, SEditableTextBox)
								.HintText(LOCTEXT("SearchNode", "buscar nodo…"))
								.OnTextChanged_Lambda([this](const FText& T) { RebuildSearchResults(T.ToString()); })
								.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type Type)
								{
									if (Type == ETextCommit::OnEnter) { CommitSearch(); }
									else if (Type == ETextCommit::OnCleared) { CloseSearch(); }
								})
							]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f)
							[
								SAssignNew(SearchResults, SVerticalBox)
							]
						]
					]
				]
			]
		]

		// Compile/Run + salida.
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(SButton).Text(LOCTEXT("Compile", "✓ Compile"))
				.ToolTipText(LOCTEXT("CompileTip", "Valida nodos, cables, parámetros y assets sin tocar la escena"))
				.OnClicked_Lambda([this]() { ValidateGraph(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("Run", "▶ Run graph"))
				.OnClicked_Lambda([this]() { RunGraph(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				// El live view de Houdini: recocina mientras arrastrás, sin apretar Run.
				SNew(SCheckBox)
				.Style(FAppStyle::Get(), "ToggleButtonCheckbox")
				.IsChecked_Lambda([this]()
					{ return bLiveView ? ECheckBoxState::Checked : ECheckBoxState::Unchecked; })
				.OnCheckStateChanged_Lambda([this](ECheckBoxState) { AlternarLiveView(); })
				.ToolTipText(LOCTEXT("LiveViewTip",
					"Live view: recocina el grafo mientras arrastrás un slider, sin apretar Run.\n"
					"Conviene con «Ver sin hornear» al final de la cadena: mostrar cuesta 1,7 ms por "
					"vuelta y hornear ~35 ms.\nArranca apagado porque correr el grafo tiene efectos "
					"en la escena."))
				[
					SNew(STextBlock).Text(LOCTEXT("LiveView", "⟳ Live"))
				]
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("BakePreview", "✓ Bake"))
				.ToolTipText(LOCTEXT("BakePreviewTip", "Fija únicamente el Preview creado por este Graph"))
				.OnClicked_Lambda([this]() { BakePreview(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("DiscardPreview", "✗ Discard"))
				.ToolTipText(LOCTEXT("DiscardPreviewTip", "Elimina únicamente el Preview creado por este Graph"))
				.OnClicked_Lambda([this]() { DiscardPreview(); return FReply::Handled(); })
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton).Text(LOCTEXT("SaveCompound", "★ Guardar como preset"))
				.ToolTipText(LOCTEXT("SaveCompoundTip", "Guarda este grafo como preset compound reusable"))
				.OnClicked_Lambda([this]()
				{
					if (Nodes.Num() > 0 && OnSaveGraph.IsBound())
					{
						OnSaveGraph.Execute(BuildJson());
					}
					return FReply::Handled();
				})
			]
			+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(8.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock).Text(LOCTEXT("Hint",
					"doble clic = buscar nodo · botón derecho arrastra el lienzo · ○→○ conecta · Run pinta cada nodo con su veredicto"))
			]
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 2.0f, 6.0f, 2.0f).MaxHeight(140.0f)
		[
			SAssignNew(Output, SMultiLineEditableTextBox).IsReadOnly(true).AllowMultiLine(true)
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(6.0f, 0.0f, 6.0f, 6.0f)
		[
			BuildInspector()
		]
	];

	RebuildCategoryStrip();
	RebuildTabContent();   // abre la primera categoría con sus fichas
	Anterior = BuildJson();   // la foto de arranque: el grafo vacío del que parte el historial
}


// ---- Inspector de datos: el Geometry Spreadsheet de Jam ----
//
// Houdini, Blender y PCG tienen todos un inspector NUMÉRICO separado de la visualización 3D, y es el
// que más se usa: el flujo documentado de PCG es «recorrer hacia adelante y ver dónde el conteo cae a
// cero». Ver geometría contesta «¿dónde está?»; esto contesta «¿qué valores tiene?».
//
// Los datos salen del último Run, que Python cachea por node id, así que abrir el panel no recalcula
// nada. La tabla ya viene formateada y filtrada desde `jam.api.inspect_json`: la regla de filtrado
// vive en UN solo lado.

/** Fila del inspector: una celda por columna, monoespaciada y alineada a la derecha como una
 *  planilla. Los textos ya vienen formateados de Python, así que acá sólo se ubican. */
class SJamInspectRowWidget : public SMultiColumnTableRow<TSharedPtr<FJamInspectRow>>
{
public:
	SLATE_BEGIN_ARGS(SJamInspectRowWidget) {}
		SLATE_ARGUMENT(TSharedPtr<FJamInspectRow>, Item)
		SLATE_ARGUMENT(const TArray<FString>*, Columns)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& Owner)
	{
		Item = InArgs._Item;
		Columns = InArgs._Columns;
		SMultiColumnTableRow<TSharedPtr<FJamInspectRow>>::Construct(FSuperRowType::FArguments(), Owner);
	}

	virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
	{
		const int32 Index = (Columns != nullptr)
			? Columns->IndexOfByKey(ColumnName.ToString()) : INDEX_NONE;
		const FString Texto = (Item.IsValid() && Item->Cells.IsValidIndex(Index))
			? Item->Cells[Index] : FString();
		return SNew(STextBlock)
			.Text(FText::FromString(Texto))
			.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
			.Justification(ETextJustify::Right)
			.Margin(FMargin(4.0f, 1.0f));
	}

private:
	TSharedPtr<FJamInspectRow> Item;
	const TArray<FString>* Columns = nullptr;
};

TSharedRef<SWidget> SJamGraphEditor::BuildInspector()
{
	return SNew(SExpandableArea)
		.InitiallyCollapsed(true)
		.AreaTitle(LOCTEXT("InspectorTitle", "Inspector de datos (último Run)"))
		.Padding(FMargin(4.0f))
		.BodyContent()
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[
					SNew(SBox).WidthOverride(220.0f)
					[
						SAssignNew(InspectPicker, SComboBox<TSharedPtr<FString>>)
						.OptionsSource(&InspectNodes)
						.OnGenerateWidget_Lambda([](TSharedPtr<FString> Item)
						{
							return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : FString()));
						})
						.OnSelectionChanged_Lambda([this](TSharedPtr<FString> Item, ESelectInfo::Type)
						{
							if (!Item.IsValid()) { return; }
							// La etiqueta es «id  ·  tipo  ·  N», así que el id es lo de antes del ·.
							FString Id = *Item;
							int32 Corte = INDEX_NONE;
							if (Id.FindChar(TEXT('\u00b7'), Corte)) { Id = Id.Left(Corte); }
							InspectNodeId = Id.TrimStartAndEnd();
							// Otro nodo puede tener otras columnas: el orden anterior ya no aplica.
							InspectSort.Empty();
							bInspectDescending = false;
							RefreshInspector();
						})
						[
							SNew(STextBlock)
							.Text_Lambda([this]()
							{
								return InspectNodeId.IsEmpty()
									? LOCTEXT("PickNode", "elegí un nodo…")
									: FText::FromString(InspectNodeId);
							})
						]
					]
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(6.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SBox).WidthOverride(180.0f)
					[
						SAssignNew(InspectFilter, SEditableTextBox)
						.HintText(LOCTEXT("InspectFilterHint", "filtrar filas…"))
						.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type)
						{
							RefreshInspector();
						})
					]
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(6.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("InspectRefresh", "actualizar"))
					.ToolTipText(LOCTEXT("InspectRefreshTip", "releer los datos del último Run"))
					.OnClicked_Lambda([this]() { RefreshInspector(); return FReply::Handled(); })
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					SAssignNew(InspectStatus, STextBlock)
					.Text(LOCTEXT("InspectIdle", "corré el grafo y elegí un nodo"))
				]
			]
			// Tabla y visor lado a lado: los números y el dibujo del MISMO nodo. Es la separación
			// que tienen Houdini y Blender, y por eso comparten el selector de arriba.
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.0f)
				[
					SNew(SBox).HeightOverride(180.0f)
					[
						SAssignNew(InspectList, SListView<TSharedPtr<FJamInspectRow>>)
						.ListItemsSource(&InspectRows)
						.SelectionMode(ESelectionMode::Single)
						.HeaderRow(SAssignNew(InspectHeader, SHeaderRow))
						.OnGenerateRow_Lambda([this](TSharedPtr<FJamInspectRow> Item,
							const TSharedRef<STableViewBase>& Owner)
						{
							return SNew(SJamInspectRowWidget, Owner)
								.Item(Item)
								.Columns(&InspectColumns);
						})
					]
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					BuildPreview2D()
				]
			]
		];
}

TSharedRef<SWidget> SJamGraphEditor::BuildPreview2D()
{
	return SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(STextBlock).Text(LOCTEXT("Preview2DUV", "canal UV"))
			]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SBox).WidthOverride(52.0f)
				[
					SNew(SSpinBox<int32>)
					.MinValue(0).MaxValue(7).MinDesiredWidth(40.0f)
					.ToolTipText(LOCTEXT("Preview2DUVTip",
						"Qué canal de UV desplegar. Una malla puede tener varios y el que importa no siempre es el 0"))
					.Value_Lambda([this]() { return Preview2DCanal; })
					.OnValueChanged_Lambda([this](int32 V) { Preview2DCanal = V; })
					.OnValueCommitted_Lambda([this](int32 V, ETextCommit::Type)
					{
						Preview2DCanal = V;
						RefreshPreview2D();
					})
				]
			]
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 4.0f, 0.0f, 0.0f)
		[
			SNew(SBox)
			.WidthOverride(static_cast<float>(Preview2DLado))
			.HeightOverride(static_cast<float>(Preview2DLado))
			[
				SAssignNew(Preview2DImagen, SImage)
				// Sin brush no dibuja nada; el texto de abajo explica por qué.
				.Visibility_Lambda([this]()
				{
					return Preview2DBrush.IsValid() ? EVisibility::Visible : EVisibility::Collapsed;
				})
			]
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 4.0f, 0.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(static_cast<float>(Preview2DLado))
			[
				SAssignNew(Preview2DEstado, STextBlock)
				.AutoWrapText(true)
				.Text(LOCTEXT("Preview2DIdle", "corré el grafo y elegí un nodo"))
			]
		];
}

void SJamGraphEditor::SoltarPreview2D()
{
	if (!Preview2DBrush.IsValid())
	{
		return;
	}
	// Slate cachea las texturas dinámicas POR NOMBRE DE ARCHIVO
	// (`FSlateRHIResourceManager::GetDynamicTextureResourceByName`), y `api.preview_2d` escribe
	// siempre la MISMA ruta por nodo —a propósito, para poder abrir el PNG por fuera—. Sin soltar
	// el recurso, el segundo Run del mismo nodo mostraría la imagen del primero para siempre: el
	// visor parecería andar en la demo y mentiría en el uso real.
	if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer() != nullptr)
	{
		FSlateApplication::Get().GetRenderer()->ReleaseDynamicResource(*Preview2DBrush);
	}
	Preview2DBrush->ReleaseResource();
	if (Preview2DImagen.IsValid())
	{
		Preview2DImagen->SetImage(nullptr);
	}
	Preview2DBrush.Reset();
}

void SJamGraphEditor::SoltarMiniaturas()
{
	// Misma trampa que en `SoltarPreview2D`, por N: Slate cachea la textura por nombre de archivo y
	// la ruta de cada miniatura es estable por nodo, así que sin soltarla el segundo Run seguiría
	// mostrando la del primero.
	const bool bHayRenderer = FSlateApplication::IsInitialized()
		&& FSlateApplication::Get().GetRenderer() != nullptr;
	for (const TPair<FString, TSharedPtr<FSlateDynamicImageBrush>>& KV : Miniaturas)
	{
		if (!KV.Value.IsValid()) { continue; }
		if (FGNode* N = FindNode(KV.Key); N && N->Widget.IsValid())
		{
			N->Widget->SetThumbnail(nullptr);   // el nodo no puede quedar apuntando a un brush muerto
		}
		if (bHayRenderer)
		{
			FSlateApplication::Get().GetRenderer()->ReleaseDynamicResource(*KV.Value);
		}
		KV.Value->ReleaseResource();
	}
	Miniaturas.Reset();
}

void SJamGraphEditor::RefrescarMiniaturas()
{
	SoltarMiniaturas();
	if (!OnPreview2DTodos.IsBound())
	{
		return;
	}
	// El delegado no recibe grafo: las miniaturas salen de la ÚLTIMA CORRIDA que ya vive en Python,
	// no de reejecutar nada. Por eso aparecen después de Run y no de Compile — Compile no produce
	// datos, valida.
	const FString Res = OnPreview2DTodos.Execute(FString());
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	bool bOk = false;
	const TSharedPtr<FJsonObject>* Thumbs = nullptr;
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
		|| !Root->TryGetBoolField(TEXT("ok"), bOk) || !bOk
		|| !Root->TryGetObjectField(TEXT("thumbs"), Thumbs) || Thumbs == nullptr)
	{
		return;   // sin miniaturas los nodos siguen mostrando su icono: no es un error que reportar
	}

	// Por VALOR y no por referencia: la clave del mapa de FJsonObject no es FString, así que un
	// `const&` se ataría a un temporal (es como itera el resto del archivo).
	for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*Thumbs)->Values)
	{
		FString Ruta;
		if (!KV.Value.IsValid() || !KV.Value->TryGetString(Ruta) || !FPaths::FileExists(Ruta))
		{
			continue;
		}
		FGNode* N = FindNode(KV.Key);
		if (N == nullptr || !N->Widget.IsValid())
		{
			continue;
		}
		TSharedPtr<FSlateDynamicImageBrush> Brush = MakeShared<FSlateDynamicImageBrush>(
			FName(*Ruta), FVector2D(MiniaturaLado, MiniaturaLado));
		N->Widget->SetThumbnail(Brush.Get());
		Miniaturas.Add(KV.Key, Brush);
	}
}

TArray<FString> SJamGraphEditor::VariablesDelGrafo() const
{
	TArray<FString> Nombres;
	if (!OnGraphVariables.IsBound())
	{
		return Nombres;
	}
	// Se manda el grafo VIVO: `BuildJson` lee los valores de los widgets, así que renombrar una
	// variable y desplegar el menú enseguida ya muestra el nombre nuevo.
	const FString Res = OnGraphVariables.Execute(BuildJson());
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	bool bOk = false;
	const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
	if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid()
		&& Root->TryGetBoolField(TEXT("ok"), bOk) && bOk
		&& Root->TryGetArrayField(TEXT("variables"), Arr) && Arr != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Arr)
		{
			FString Nombre;
			if (V.IsValid() && V->TryGetString(Nombre) && !Nombre.IsEmpty())
			{
				Nombres.Add(Nombre);
			}
		}
	}
	return Nombres;
}

void SJamGraphEditor::AbrirVisorFullRes(const FString& NodeId)
{
	if (!OnPreview2D.IsBound() || NodeId.IsEmpty())
	{
		return;
	}
	// Una sola ventana: abrir el visor de otro nodo reemplaza la anterior en vez de ir dejando
	// ventanas por la pantalla.
	if (const TSharedPtr<SWindow> Vieja = VisorFullVentana.Pin())
	{
		// Desatar su handler ANTES de pedir el cierre: `RequestDestroyWindow` es diferido, así que
		// el `OnWindowClosed` de la vieja correría DESPUÉS de que creemos el brush nuevo y se lo
		// soltaría — la ventana nueva abriría en blanco, y de forma intermitente.
		Vieja->SetOnWindowClosed(FOnWindowClosed());
		Vieja->RequestDestroyWindow();
	}

	// Sufijo propio: el PNG grande no puede pisar ni al del panel (`{id}.png`) ni a la miniatura
	// (`{id}_thumb.png`) — Slate cachea la textura por nombre de archivo y se mostrarían entre sí.
	const FString Res = OnPreview2D.Execute(NodeId, VisorFullLado, Preview2DCanal, TEXT("_full"));
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	bool bOk = false;
	FString Ruta, Detalle, Error;
	if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())
	{
		Root->TryGetBoolField(TEXT("ok"), bOk);
		Root->TryGetStringField(TEXT("ruta"), Ruta);
		Root->TryGetStringField(TEXT("detalle"), Detalle);
		Root->TryGetStringField(TEXT("error"), Error);
	}
	if (!bOk || Ruta.IsEmpty() || !FPaths::FileExists(Ruta))
	{
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(Error.IsEmpty()
				? FString::Printf(TEXT("no pude dibujar «%s» en grande."), *NodeId) : Error));
		}
		return;
	}

	SoltarVisorFullRes();
	VisorFullBrush = MakeShared<FSlateDynamicImageBrush>(
		FName(*Ruta), FVector2D(VisorFullLado, VisorFullLado));

	TSharedRef<SWindow> Ventana = SNew(SWindow)
		.Title(FText::FromString(FString::Printf(TEXT("Jam · %s"), *NodeId)))
		.ClientSize(FVector2D(VisorFullLado + 24, VisorFullLado + 72))
		.SupportsMaximize(false)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().FillHeight(1.0f).Padding(12.0f, 12.0f, 12.0f, 4.0f)
			[
				SNew(SImage).Image(VisorFullBrush.Get())
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(12.0f, 0.0f, 12.0f, 12.0f)
			[
				SNew(STextBlock).AutoWrapText(true).Text(FText::FromString(Detalle))
			]
		];
	// Al cerrarla se suelta la textura: si no, el próximo dibujo del mismo nodo mostraría ésta,
	// porque Slate la tiene cacheada bajo la misma ruta.
	Ventana->SetOnWindowClosed(FOnWindowClosed::CreateLambda(
		[this](const TSharedRef<SWindow>&) { SoltarVisorFullRes(); }));
	// NO modal: el punto es dejarla al lado mientras se sigue tocando el grafo.
	FSlateApplication::Get().AddWindow(Ventana);
	VisorFullVentana = Ventana;
}

void SJamGraphEditor::SoltarVisorFullRes()
{
	if (!VisorFullBrush.IsValid())
	{
		return;
	}
	if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer() != nullptr)
	{
		FSlateApplication::Get().GetRenderer()->ReleaseDynamicResource(*VisorFullBrush);
	}
	VisorFullBrush->ReleaseResource();
	VisorFullBrush.Reset();
}

void SJamGraphEditor::RefreshPreview2D()
{
	auto Decir = [this](const FText& Texto)
	{
		if (Preview2DEstado.IsValid()) { Preview2DEstado->SetText(Texto); }
	};

	SoltarPreview2D();
	if (!OnPreview2D.IsBound() || InspectNodeId.IsEmpty())
	{
		Decir(LOCTEXT("Preview2DIdle", "corré el grafo y elegí un nodo"));
		return;
	}

	const FString Res = OnPreview2D.Execute(InspectNodeId, Preview2DLado, Preview2DCanal, FString());
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		Decir(FText::FromString(FString::Printf(TEXT("respuesta ilegible del visor: %s"), *Res)));
		return;
	}

	bool bOk = false;
	if (!Root->TryGetBoolField(TEXT("ok"), bOk) || !bOk)
	{
		// «No se puede dibujar esto» TAMBIÉN es información: el texto dice qué falta hacer
		// (proyectar UVs, correr el grafo) en vez de dejar un cuadro vacío sin explicación.
		FString Error;
		Root->TryGetStringField(TEXT("error"), Error);
		Decir(FText::FromString(Error.IsEmpty() ? TEXT("no hay nada que dibujar de este nodo.") : Error));
		return;
	}

	FString Ruta, Detalle;
	Root->TryGetStringField(TEXT("ruta"), Ruta);
	Root->TryGetStringField(TEXT("detalle"), Detalle);
	if (Ruta.IsEmpty() || !FPaths::FileExists(Ruta))
	{
		Decir(FText::FromString(FString::Printf(
			TEXT("el visor dijo que escribió «%s», pero el archivo no está."), *Ruta)));
		return;
	}

	Preview2DBrush = MakeShared<FSlateDynamicImageBrush>(
		FName(*Ruta), FVector2D(Preview2DLado, Preview2DLado));
	if (Preview2DImagen.IsValid())
	{
		Preview2DImagen->SetImage(Preview2DBrush.Get());
	}
	Decir(FText::FromString(Detalle));
}

void SJamGraphEditor::RefreshInspector()
{
	InspectNodes.Reset();
	InspectRows.Reset();
	if (!OnInspect.IsBound())
	{
		if (InspectStatus.IsValid()) { InspectStatus->SetText(LOCTEXT("InspectNoBridge", "sin puente a Python")); }
		return;
	}
	const FString Filtro = InspectFilter.IsValid() ? InspectFilter->GetText().ToString() : FString();
	const FString Raw = OnInspect.Execute(InspectNodeId, Filtro, InspectSort, bInspectDescending);

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		if (InspectStatus.IsValid()) { InspectStatus->SetText(FText::FromString(Raw.Left(120))); }
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Nodos = nullptr;
	if (Root->TryGetArrayField(TEXT("nodos"), Nodos) && Nodos != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Nodos)
		{
			const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
			if (!O.IsValid()) { continue; }
			FString Id, Tipo;
			double Cantidad = 0.0;
			O->TryGetStringField(TEXT("id"), Id);
			O->TryGetStringField(TEXT("tipo"), Tipo);
			O->TryGetNumberField(TEXT("cantidad"), Cantidad);
			InspectNodes.Add(MakeShared<FString>(FString::Printf(
				TEXT("%s \u00b7 %s \u00b7 %d"), *Id, *Tipo, static_cast<int32>(Cantidad))));
		}
	}

	// Las columnas cambian con el TIPO del nodo (P tiene peso, F tiene escala y tangente…), así que
	// el encabezado se reconstruye en cada refresco en vez de ser fijo.
	InspectColumns.Reset();
	const TArray<TSharedPtr<FJsonValue>>* Columnas = nullptr;
	if (Root->TryGetArrayField(TEXT("columnas"), Columnas) && Columnas != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Columnas)
		{
			const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
			FString Nombre;
			if (O.IsValid() && O->TryGetStringField(TEXT("nombre"), Nombre))
			{
				InspectColumns.Add(Nombre);
			}
		}
	}
	if (InspectHeader.IsValid())
	{
		InspectHeader->ClearColumns();
		for (const FString& Nombre : InspectColumns)
		{
			const FName Id(*Nombre);
			InspectHeader->AddColumn(
				SHeaderRow::Column(Id)
				.DefaultLabel(FText::FromString(Nombre))
				.FillWidth(1.0f)
				.SortMode_Lambda([this, Nombre]()
				{
					if (InspectSort != Nombre) { return EColumnSortMode::None; }
					return bInspectDescending ? EColumnSortMode::Descending : EColumnSortMode::Ascending;
				})
				// Ordenar lo resuelve Python sobre TODAS las filas y recorta después; si ordenara
				// la UI, sólo ordenaría las 200 que ya recibió.
				.OnSort_Lambda([this](EColumnSortPriority::Type, const FName& ColumnId,
					EColumnSortMode::Type NuevoModo)
				{
					InspectSort = ColumnId.ToString();
					bInspectDescending = (NuevoModo == EColumnSortMode::Descending);
					RefreshInspector();
				}));
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* Filas = nullptr;
	if (Root->TryGetArrayField(TEXT("filas"), Filas) && Filas != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& V : *Filas)
		{
			const TArray<TSharedPtr<FJsonValue>>* Celdas = nullptr;
			if (!V.IsValid() || !V->TryGetArray(Celdas) || Celdas == nullptr) { continue; }
			TSharedRef<FJamInspectRow> Fila = MakeShared<FJamInspectRow>();
			for (const TSharedPtr<FJsonValue>& C : *Celdas)
			{
				Fila->Cells.Add(C.IsValid() ? C->AsString() : FString());
			}
			InspectRows.Add(Fila);
		}
	}

	FString Estado;
	bool bOk = false;
	Root->TryGetBoolField(TEXT("ok"), bOk);
	if (!bOk)
	{
		Root->TryGetStringField(TEXT("error"), Estado);
	}
	else if (InspectNodeId.IsEmpty())
	{
		Estado = FString::Printf(TEXT("%d nodo(s) en el último Run"), InspectNodes.Num());
	}
	else
	{
		double Total = 0.0;
		Root->TryGetNumberField(TEXT("total"), Total);
		Estado = (static_cast<int32>(Total) > InspectRows.Num())
			? FString::Printf(TEXT("%d de %d fila(s)"), InspectRows.Num(), static_cast<int32>(Total))
			: FString::Printf(TEXT("%d fila(s)"), InspectRows.Num());
	}
	if (InspectStatus.IsValid()) { InspectStatus->SetText(FText::FromString(Estado)); }
	if (InspectPicker.IsValid()) { InspectPicker->RefreshOptions(); }
	if (InspectList.IsValid()) { InspectList->RequestListRefresh(); }
	// El visor es la otra vista del MISMO nodo: se refresca acá y no por su cuenta, así no hay dos
	// caminos que puedan quedar mostrando nodos distintos.
	RefreshPreview2D();
}


// ---- Ribbon estilo Grasshopper: tabs + fichas con icono ----

FLinearColor SJamGraphEditor::CategoryColor(const FString& Cat)
{
	// un tono por categoría (como los tabs de Grasshopper): tools + flow.
	if (Cat == TEXT("Inicio"))       { return FLinearColor(0.34f, 0.44f, 0.58f, 1.0f); }
	if (Cat == TEXT("Geometría"))    { return FLinearColor(0.18f, 0.56f, 0.56f, 1.0f); }
	if (Cat == TEXT("Distribución")) { return FLinearColor(0.24f, 0.56f, 0.34f, 1.0f); }
	if (Cat == TEXT("Datos"))        { return FLinearColor(0.68f, 0.30f, 0.44f, 1.0f); }
	if (Cat == TEXT("Materiales"))   { return FLinearColor(0.66f, 0.42f, 0.20f, 1.0f); }
	if (Cat == TEXT("Funciones"))    { return FLinearColor(0.50f, 0.32f, 0.62f, 1.0f); }
	if (Cat == TEXT("Content"))  { return FLinearColor(0.40f, 0.44f, 0.50f, 1.0f); }
	if (Cat == TEXT("Place"))    { return FLinearColor(0.20f, 0.52f, 0.72f, 1.0f); }
	if (Cat == TEXT("Scatter"))  { return FLinearColor(0.24f, 0.60f, 0.32f, 1.0f); }
	if (Cat == TEXT("Create"))   { return FLinearColor(0.62f, 0.34f, 0.66f, 1.0f); }
	if (Cat == TEXT("Mesh"))     { return FLinearColor(0.18f, 0.56f, 0.56f, 1.0f); }
	if (Cat == TEXT("Edit"))     { return FLinearColor(0.72f, 0.50f, 0.16f, 1.0f); }
	if (Cat == TEXT("Params"))   { return FLinearColor(0.44f, 0.44f, 0.48f, 1.0f); }
	if (Cat == TEXT("Maths"))    { return FLinearColor(0.78f, 0.28f, 0.42f, 1.0f); }
	if (Cat == TEXT("Source"))   { return FLinearColor(0.24f, 0.58f, 0.40f, 1.0f); }
	if (Cat == TEXT("Vector"))   { return FLinearColor(0.36f, 0.44f, 0.62f, 1.0f); }
	if (Cat == TEXT("Mask"))     { return FLinearColor(0.78f, 0.46f, 0.14f, 1.0f); }
	if (Cat == TEXT("Weight"))   { return FLinearColor(0.46f, 0.52f, 0.58f, 1.0f); }   // gris frío = máscara gris
	if (Cat == TEXT("Sets"))     { return FLinearColor(0.30f, 0.52f, 0.56f, 1.0f); }
	if (Cat == TEXT("Transform")){ return FLinearColor(0.50f, 0.40f, 0.24f, 1.0f); }
	if (Cat == TEXT("Combine"))  { return FLinearColor(0.26f, 0.46f, 0.70f, 1.0f); }
	if (Cat == TEXT("Output"))   { return FLinearColor(0.58f, 0.30f, 0.62f, 1.0f); }
	if (Cat == TEXT("Shader"))   { return FLinearColor(0.66f, 0.42f, 0.20f, 1.0f); }
	if (Cat == TEXT("Display"))  { return FLinearColor(0.62f, 0.60f, 0.24f, 1.0f); }
	// «Aprender» no es una categoría de verbos: es el tab de tutoriales. Azul frío, que no se
	// confunde con ninguno de los tabs de trabajo.
	if (Cat == TEXT("Aprender")) { return FLinearColor(0.22f, 0.40f, 0.62f, 1.0f); }
	return FLinearColor(0.35f, 0.35f, 0.38f, 1.0f);
}

FString SJamGraphEditor::VerbCode(const FString& Verb)
{
	// código curado de 2 letras para el badge (legible siempre, sin depender de glifos raros).
	static const TMap<FString, FString> Codes = {
		{TEXT("asset"), TEXT("AS")}, {TEXT("pick"), TEXT("PK")},
		{TEXT("place"), TEXT("PL")}, {TEXT("drop"), TEXT("DR")}, {TEXT("snap"), TEXT("SN")},
		{TEXT("scatter"), TEXT("SC")}, {TEXT("spline"), TEXT("SP")}, {TEXT("pcg"), TEXT("PC")},
		{TEXT("replace"), TEXT("RP")}, {TEXT("create_spline"), TEXT("CS")},
		{TEXT("pivot"), TEXT("PV")}, {TEXT("pivot_set"), TEXT("PS")}, {TEXT("normalize"), TEXT("NR")},
		{TEXT("gizmo"), TEXT("GZ")}, {TEXT("ghost"), TEXT("GH")},
		{TEXT("source_surface"), TEXT("SF")}, {TEXT("source_grid"), TEXT("GR")},
		{TEXT("source_poisson"), TEXT("PO")}, {TEXT("source_radial"), TEXT("RA")},
		{TEXT("mask_slope"), TEXT("SL")}, {TEXT("mask_height"), TEXT("HT")},
		{TEXT("mask_noise"), TEXT("NO")}, {TEXT("mask_density"), TEXT("DN")},
		{TEXT("mask_circle"), TEXT("CI")}, {TEXT("merge"), TEXT("MG")}, {TEXT("instance"), TEXT("IN")},
		{TEXT("number"), TEXT("N#")}, {TEXT("math"), TEXT("fx")}, {TEXT("text"), TEXT("Tx")},
		{TEXT("cull_nth"), TEXT("CN")}, {TEXT("sub_list"), TEXT("SB")}, {TEXT("shift"), TEXT("SH")},
		{TEXT("reverse"), TEXT("RV")}, {TEXT("move"), TEXT("MV")}, {TEXT("scale_pts"), TEXT("SZ")},
		{TEXT("rotate_pts"), TEXT("RT")}, {TEXT("jitter"), TEXT("JT")},
		{TEXT("pts_line"), TEXT("LN")}, {TEXT("pts_circle"), TEXT("CR")}, {TEXT("pts_rect"), TEXT("RC")},
		{TEXT("pts_arc"), TEXT("AR")}, {TEXT("relax"), TEXT("RX")}, {TEXT("weave"), TEXT("WV")},
		{TEXT("info"), TEXT("i")},
		{TEXT("weight_slope"), TEXT("WS")}, {TEXT("weight_height"), TEXT("WH")},
		{TEXT("weight_noise"), TEXT("WN")}, {TEXT("weight_radial"), TEXT("WR")},
		{TEXT("weight_invert"), TEXT("1-")}, {TEXT("weight_power"), TEXT("W^")},
		{TEXT("weight_curve"), TEXT("WC")}, {TEXT("weight_combine"), TEXT("WX")},
		{TEXT("weight_cull"), TEXT("WK")},
	};
	if (const FString* Found = Codes.Find(Verb))
	{
		return *Found;
	}
	// derivado: iniciales de las partes separadas por «_», o las 2 primeras letras.
	FString A, B;
	if (Verb.Split(TEXT("_"), &A, &B) && A.Len() > 0 && B.Len() > 0)
	{
		return (A.Left(1) + B.Left(1)).ToUpper();
	}
	return Verb.Left(2).ToUpper();
}

FString SJamGraphEditor::IconPathForVerb(const FString& Verb)
{
	const FString FuncionIcon(TEXT("jam-function-call"));
	const FString* IconName = Verb.StartsWith(TEXT("fn:")) ? &FuncionIcon : JamIconMap().Find(Verb);
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
	if (IconName == nullptr || !Plugin.IsValid())
	{
		return FString();
	}

	const FString Path = FPaths::Combine(
		Plugin->GetBaseDir(), TEXT("Resources/Icons/Lucide"), *IconName + TEXT(".svg"));
	return IFileManager::Get().FileExists(*Path) ? Path : FString();
}

TSharedRef<SWidget> SJamGraphEditor::MakeBadge(const FLinearColor& Color, const FString& Code,
	float Size, const FString& IconPath)
{
	TSharedRef<SWidget> Glyph = SNew(STextBlock)
		.Text(FText::FromString(Code))
		.ColorAndOpacity(FLinearColor::White)
		.Font(FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(6, FMath::RoundToInt(Size * 0.42f))));

	// Los iconos PROPIOS de Jam (prefijo «jam-») traen su propio color: cada tipo de dato se dibuja
	// con el color de su pin, así que el icono enseña la firma del verbo. Los de Lucide, en cambio,
	// son máscaras blancas que hay que teñir. Se distinguen por el nombre del archivo.
	const bool bIconoPropio = FPaths::GetBaseFilename(IconPath).StartsWith(TEXT("jam-"));
	if (!IconPath.IsEmpty())
	{
		const TSharedRef<FSlateVectorImageBrush> BadgeBrush = MakeShared<FSlateVectorImageBrush>(
			IconPath, FVector2D(Size * (bIconoPropio ? 0.92f : 0.68f)),
			bIconoPropio ? FLinearColor::White : FLinearColor(0.08f, 0.08f, 0.09f, 1.0f));
		Glyph = SNew(SImage)
			.Image_Lambda([BadgeBrush]() -> const FSlateBrush* { return &BadgeBrush.Get(); });
	}

	// Un icono a color necesita fondo neutro para que sus propios colores se lean; uno teñido de
	// tinta necesita el color de categoría detrás.
	const FLinearColor Fondo = bIconoPropio ? FLinearColor(0.94f, 0.94f, 0.95f, 1.0f) : Color;
	return SNew(SBox).WidthOverride(Size).HeightOverride(Size)
	[
		SNew(SBorder)
		.BorderImage(FAppStyle::GetBrush("WhiteBrush"))
		.BorderBackgroundColor(Fondo)
		.HAlign(HAlign_Center).VAlign(VAlign_Center)
		.Padding(0.0f)
		[
			Glyph
		]
	];
}

void SJamGraphEditor::SelectSection(const FString& Section)
{
	ActiveSection = Section;
	if (Section == JamLearnTab)
	{
		ActiveTab = JamLearnTab;
	}
	else
	{
		bool bCategoriaActualPertenece = false;
		for (const FJamTool& T : Tools)
		{
			const FString Familia = T.Section.IsEmpty() ? T.Cat : T.Section;
			if (T.Cat == ActiveTab && Familia == Section)
			{
				bCategoriaActualPertenece = true;
				break;
			}
		}
		if (!bCategoriaActualPertenece)
		{
			for (const FJamTool& T : Tools)
			{
				const FString Familia = T.Section.IsEmpty() ? T.Cat : T.Section;
				if (Familia == Section)
				{
					ActiveTab = T.Cat;
					break;
				}
			}
		}
	}
	RebuildCategoryStrip();
	RebuildTabContent();
}

void SJamGraphEditor::RebuildCategoryStrip()
{
	if (!CategoryStripBox.IsValid()) { return; }
	CategoryStripBox->ClearChildren();
	if (ActiveSection == JamLearnTab) { return; }

	TArray<FString> CategoriasDeFamilia;
	for (const FJamTool& T : Tools)
	{
		const FString Familia = T.Section.IsEmpty() ? T.Cat : T.Section;
		if (Familia == ActiveSection) { CategoriasDeFamilia.AddUnique(T.Cat); }
	}
	for (const FString& Cat : CategoriasDeFamilia)
	{
		CategoryStripBox->AddSlot().AutoWidth().Padding(1.0f, 0.0f)
		[
			SNew(SButton)
			.Text(FText::FromString(Cat))
			.ToolTipText(FText::FromString(FString::Printf(
				TEXT("Categoría «%s» dentro de %s"), *Cat, *ActiveSection)))
			.ButtonColorAndOpacity_Lambda([this, Cat]()
			{
				return ActiveTab == Cat
					? CategoryColor(Cat) : FLinearColor(0.18f, 0.18f, 0.20f, 1.0f);
			})
			.OnClicked_Lambda([this, Cat]()
			{
				ActiveTab = Cat;
				RebuildTabContent();
				return FReply::Handled();
			})
		];
	}
}

void SJamGraphEditor::RebuildTabContent()
{
	if (!TabContentBox.IsValid())
	{
		return;
	}
	TabContentBox->ClearChildren();

	if (ActiveTab == JamLearnTab)
	{
		RebuildLearnTab();
		return;
	}
	if (ActiveTab == TEXT("Funciones"))
	{
		TabContentBox->AddSlot().AutoWidth().Padding(4.0f, 1.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(1.0f)
			[
				SNew(SButton).Text(LOCTEXT("NewFunction", "+ Nueva función"))
				.ToolTipText(LOCTEXT("NewFunctionTip", "Crea una firma vacía y abre su cuerpo para editar"))
				.IsEnabled_Lambda([this]() { return FuncionEnEdicion.IsEmpty(); })
				.OnClicked_Lambda([this]() { NuevaFuncion(); return FReply::Handled(); })
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(1.0f)
			[
				SNew(SButton).Text(LOCTEXT("SaveFunction", "Guardar cambios"))
				.IsEnabled_Lambda([this]() { return !FuncionEnEdicion.IsEmpty(); })
				.OnClicked_Lambda([this]() { GuardarFuncion(); return FReply::Handled(); })
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(2.0f, 3.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([this]()
				{
					return FText::FromString(FuncionEnEdicion.IsEmpty()
						? TEXT("Sin función abierta")
						: FString(TEXT("Editando: ")) + NombreFuncionEnEdicion);
				})
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
			]
		];
		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 2.0f)
		[ SNew(SSeparator).Orientation(Orient_Vertical).Thickness(1.0f) ];
	}

	// El tab se parte en SUBGRUPOS (los «paneles» de Grasshopper) y cada uno apila `RibbonRows`
	// filas. El spec ya llega ordenado por la tabla de layout de `jam/ribbon.py`, así que basta con
	// respetar el orden de aparición: agrupar sin reordenar.
	TArray<FString> GroupOrder;
	TMap<FString, TArray<const FJamTool*>> ByGroup;
	for (const FJamTool& T : Tools)
	{
		if (T.Cat != ActiveTab)
		{
			continue;
		}
		if (!ByGroup.Contains(T.Group))
		{
			GroupOrder.Add(T.Group);
		}
		ByGroup.FindOrAdd(T.Group).Add(&T);
	}

	for (int32 GroupIndex = 0; GroupIndex < GroupOrder.Num(); ++GroupIndex)
	{
		const TArray<const FJamTool*>& Verbs = ByGroup[GroupOrder[GroupIndex]];
		// Relleno por COLUMNAS: se lee de arriba abajo y se salta a la derecha. Es lo que hace
		// Grasshopper, y mantiene juntos los verbos vecinos de la tabla aunque cambie el alto.
		const int32 Columns = FMath::DivideAndRoundUp(Verbs.Num(), RibbonRows);
		TSharedRef<SHorizontalBox> Grid = SNew(SHorizontalBox);
		for (int32 Column = 0; Column < Columns; ++Column)
		{
			TSharedRef<SVerticalBox> ColumnBox = SNew(SVerticalBox);
			for (int32 Row = 0; Row < RibbonRows; ++Row)
			{
				const int32 Index = Column * RibbonRows + Row;
				if (!Verbs.IsValidIndex(Index))
				{
					break;   // la última columna queda corta, no se rellena con huecos
				}
				const FJamTool& T = *Verbs[Index];
				const FString Verb = T.Verb;
				// Sólo el icono; el nombre y la FIRMA DE TIPOS van en el tooltip. «S → M» dice más
				// que cualquier nombre a la hora de decidir si un verbo sirve donde estás parado.
				FString Firma;
				if (T.InputPins.Num() > 0 || T.OutputPins.Num() > 0)
				{
					TArray<FString> Entradas, Salidas;
					for (const FJamTool::FPin& P : T.InputPins)
					{
						Entradas.Add(FString::Printf(TEXT("%s:%s"), *P.Name, *P.Type));
					}
					for (const FJamTool::FPin& P : T.OutputPins)
					{
						Salidas.Add(FString::Printf(TEXT("%s:%s"), *P.Name, *P.Type));
					}
					Firma = FString::Join(Entradas, TEXT(", ")) + TEXT(" \u2192 ")
						+ FString::Join(Salidas, TEXT(", "));
				}
				else
				{
					Firma = T.bSource
						? FString::Printf(TEXT("\u2192 %s"), *T.OutName)
						: FString::Printf(TEXT("%s \u2192 %s"), *T.InName, *T.OutName);
				}
				TSharedRef<SJamVerbTile> Tile = SNew(SJamVerbTile)
					.Verb(Verb)
					.OnClicked_Lambda([this](FString V) { AddNodeAlCentro(V); })
					.ToolTipText(FText::FromString(FString::Printf(
						TEXT("%s   [%s]\n%s\n\nclic = al centro de la vista · arrastrá = donde sueltes"),
						*(T.Label.IsEmpty() ? T.Verb : T.Label), *Firma, *T.Doc)))
					[ MakeBadge(CategoryColor(T.Cat), VerbCode(Verb), 30.0f, IconPathForVerb(Verb)) ];
				if (T.Group == TEXT("Biblioteca"))
				{
					const FString Nombre = T.Label.IsEmpty() ? T.Verb : T.Label;
					ColumnBox->AddSlot().AutoHeight().Padding(2.0f)
					[
						SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ Tile ]
						+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(1.0f)
						[
							SNew(STextBlock).Text(FText::FromString(Nombre))
							.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
						]
						+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
						[
							SNew(SHorizontalBox)
							+ SHorizontalBox::Slot().AutoWidth().Padding(1.0f)
							[
								SNew(SButton).Text(LOCTEXT("EditFunctionShort", "Editar"))
								.OnClicked_Lambda([this, Verb]()
								{ EditarFuncion(Verb); return FReply::Handled(); })
							]
							+ SHorizontalBox::Slot().AutoWidth().Padding(1.0f)
							[
								SNew(SButton).Text(LOCTEXT("RenameFunctionShort", "Nombre"))
								.OnClicked_Lambda([this, Verb, Nombre]()
								{ RenombrarFuncion(Verb, Nombre); return FReply::Handled(); })
							]
							+ SHorizontalBox::Slot().AutoWidth().Padding(1.0f)
							[
								SNew(SButton).Text(LOCTEXT("PublishFunctionShort", "Dash"))
								.ToolTipText(LOCTEXT("PublishFunctionTip",
									"Publica la herramienta en la Dash (o la saca). No toca el cuerpo: "
									"los grafos que ya la usan siguen andando igual"))
								.OnClicked_Lambda([this, Verb]()
								{ PublicarFuncion(Verb, true); return FReply::Handled(); })
							]
							+ SHorizontalBox::Slot().AutoWidth().Padding(1.0f)
							[
								SNew(SButton).Text(LOCTEXT("ExportFunctionShort", "Exportar"))
								.ToolTipText(LOCTEXT("ExportFunctionTip",
									"Guarda la herramienta como archivo .jamtool para pasarla a otro proyecto"))
								.OnClicked_Lambda([this, Verb, Nombre]()
								{ ExportarFuncion(Verb, Nombre); return FReply::Handled(); })
							]
							+ SHorizontalBox::Slot().AutoWidth().Padding(1.0f)
							[
								SNew(SButton).Text(LOCTEXT("DeleteFunctionShort", "Eliminar"))
								.OnClicked_Lambda([this, Verb, Nombre]()
								{ EliminarFuncion(Verb, Nombre); return FReply::Handled(); })
							]
						]
					];
				}
				else
				{
					ColumnBox->AddSlot().AutoHeight().Padding(1.0f)[ Tile ];
				}
			}
			Grid->AddSlot().AutoWidth()[ ColumnBox ];
		}

		// El bloque: la grilla arriba y la etiqueta del grupo abajo, como el pie de panel de GH.
		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 0.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ Grid ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f).HAlign(HAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(GroupOrder[GroupIndex]))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.62f, 0.62f, 0.66f, 1.0f)))
			]
		];

		if (GroupIndex + 1 < GroupOrder.Num())
		{
			TabContentBox->AddSlot().AutoWidth().Padding(2.0f, 2.0f)
			[
				SNew(SSeparator).Orientation(Orient_Vertical).Thickness(1.0f)
			];
		}
	}
}

void SJamGraphEditor::RebuildLearnTab()
{
	// Antes: los 19 tutoriales en UNA fila horizontal, con insignia de 42 px y título debajo. La
	// tira se iba de largo y había que recorrerla entera para ver qué había, con 19 puertas del
	// mismo tamaño diciendo que daba igual por cuál entrar. Y no daba igual.
	//
	// Ahora Aprender es un CAMINO: seis pasos ordenados que estrenan una idea cada uno y usan la
	// del anterior, con el progreso marcado y el próximo señalado. Los otros trece quedan abajo,
	// agrupados por tema, para cuando alguien busca algo puntual. El orden vive en el manifiesto
	// (`paso`), no acá: reordenar lo que se aprende primero no debería necesitar recompilar.
	const TArray<FJamExample>& Ejemplos = JamExamples();
	if (Ejemplos.Num() == 0)
	{
		TabContentBox->AddSlot().AutoWidth().Padding(6.0f)
		[
			SNew(STextBlock).Text(LOCTEXT("NoExamples",
				"No encontré Resources/Examples/examples.json — el catálogo de tutoriales."))
		];
		return;
	}

	TArray<const FJamExample*> Camino;
	TArray<FString> Orden;
	TMap<FString, TArray<const FJamExample*>> PorGrupo;
	for (const FJamExample& E : Ejemplos)
	{
		if (E.Paso > 0)
		{
			Camino.Add(&E);
			continue;
		}
		if (!PorGrupo.Contains(E.Group))
		{
			Orden.Add(E.Group);
		}
		PorGrupo.FindOrAdd(E.Group).Add(&E);
	}
	Camino.Sort([](const FJamExample& A, const FJamExample& B) { return A.Paso < B.Paso; });

	// El próximo paso es el PRIMERO sin marcar, no el siguiente al último marcado: quien saltea el
	// 3 y hace el 4 tiene el 3 pendiente, y decirle que va por el 5 sería mentirle.
	const FJamExample* Proximo = nullptr;
	int32 Hechos = 0;
	for (const FJamExample* E : Camino)
	{
		if (JamVistos().Contains(E->File)) { ++Hechos; }
		else if (Proximo == nullptr) { Proximo = E; }
	}

	const FLinearColor ColorCamino = CategoryColor(JamLearnTab);
	const FLinearColor Tenue(0.62f, 0.62f, 0.66f, 1.0f);

	// ---- la ficha compacta, la misma para el camino y para el resto ----
	auto Ficha = [this, &ColorCamino, &Tenue](const FJamExample* E, bool bEnElCamino,
	                                          bool bEsProximo) -> TSharedRef<SWidget>
	{
		const FString Archivo = E->File;
		const FString Mensaje = E->Message;
		const bool bVisto = JamVistos().Contains(Archivo);
		// El número del paso, un tilde si ya lo hiciste, o nada. Es lo único que distingue a las
		// fichas entre sí de un vistazo, así que va primero y no al final.
		const FString Marca = bVisto ? TEXT("✓")
			: (bEnElCamino ? FString::Printf(TEXT("%d"), E->Paso) : FString());
		// Una línea por ficha: el «porqué» si lo tiene, y si no el título solo. El texto largo
		// (`doc`) queda en el tooltip, que es donde se lee cuando se lo busca y no antes.
		const FString Subtitulo = bEnElCamino ? E->Why : FString();

		TSharedRef<SHorizontalBox> Contenido = SNew(SHorizontalBox);
		if (!Marca.IsEmpty())
		{
			Contenido->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Marca))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
				.ColorAndOpacity(FSlateColor(bVisto ? FLinearColor(0.36f, 0.68f, 0.42f, 1.0f)
				                                    : ColorCamino))
			];
		}
		// 20 px y no 42: en el camino el nombre es lo que se lee, no el dibujo.
		Contenido->AddSlot().AutoWidth().VAlign(VAlign_Center)
		[ MakeBadge(ColorCamino, TEXT("EJ"), 20.0f, JamIconPath(E->Icon)) ];

		TSharedRef<SVerticalBox> Textos = SNew(SVerticalBox);
		Textos->AddSlot().AutoHeight()
		[
			SNew(STextBlock)
			.Text(FText::FromString(E->Title))
			.Font(FCoreStyle::GetDefaultFontStyle(bEsProximo ? "Bold" : "Regular", 9))
		];
		if (!Subtitulo.IsEmpty())
		{
			Textos->AddSlot().AutoHeight()
			[
				SNew(STextBlock)
				.Text(FText::FromString(Subtitulo))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(Tenue))
			];
		}
		Contenido->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(5.0f, 0.0f, 2.0f, 0.0f)
		[ Textos ];

		return SNew(SButton)
			.ToolTipText(FText::FromString(FString::Printf(TEXT("%s\n\n%s"), *E->Title, *E->Doc)))
			.ContentPadding(FMargin(4.0f, 3.0f))
			.OnClicked_Lambda([this, Archivo, Mensaje]()
			{
				JamMarcarVisto(Archivo);
				LoadBundledExample(Archivo, FText::FromString(Mensaje));
				// Redibujar para que el tilde y el «próximo» se muevan en el acto: un progreso que
				// aparece recién al reabrir el tab no se lee como progreso.
				RebuildTabContent();
				return FReply::Handled();
			})
		// El contenido va ADENTRO del botón. Sin este bloque el `SButton` se construye vacío, mide
		// cero y no dibuja nada: quedan el encabezado y el nombre del grupo, y ninguna ficha. Los
		// 13 tests de este tab pasaban igual, porque miran el catálogo y las reglas del `.cpp` y
		// ninguno mira el árbol de widgets. Lo encontró Brian en dos minutos con una captura.
		[ Contenido ];
	};

	// ---- el camino ----
	if (Camino.Num() > 0)
	{
		TSharedRef<SHorizontalBox> FilaCamino = SNew(SHorizontalBox);
		for (const FJamExample* E : Camino)
		{
			FilaCamino->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
			[ Ficha(E, true, E == Proximo) ];
		}

		const FString Encabezado = (Proximo == nullptr)
			? FString::Printf(TEXT("TU CAMINO · los %d pasos, hechos"), Camino.Num())
			: FString::Printf(TEXT("TU CAMINO · paso %d de %d"), Hechos + 1, Camino.Num());

		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 0.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 2.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Encabezado))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 7))
				.ColorAndOpacity(FSlateColor(ColorCamino))
			]
			+ SVerticalBox::Slot().AutoHeight()[ FilaCamino ]
		];
	}

	if (Orden.Num() == 0)
	{
		return;
	}

	TabContentBox->AddSlot().AutoWidth().Padding(4.0f, 2.0f)
	[ SNew(SSeparator).Orientation(Orient_Vertical).Thickness(1.0f) ];

	// ---- el resto, en DOS filas por grupo para que entren a lo alto en vez de a lo largo ----
	// Es el cambio que mata la tira infinita: la altura del ribbon es fija y sobraba, mientras el
	// ancho se acababa. Con dos filas la misma cantidad de fichas ocupa la mitad de largo.
	TSharedRef<SHorizontalBox> FilaGrupos = SNew(SHorizontalBox);
	for (const FString& Grupo : Orden)
	{
		TSharedRef<SVerticalBox> Columna = SNew(SVerticalBox);
		TSharedRef<SHorizontalBox> Arriba = SNew(SHorizontalBox);
		TSharedRef<SHorizontalBox> Abajo = SNew(SHorizontalBox);
		const TArray<const FJamExample*>& Delgrupo = PorGrupo[Grupo];
		for (int32 i = 0; i < Delgrupo.Num(); ++i)
		{
			const TSharedRef<SHorizontalBox> Destino = (i % 2 == 0) ? Arriba : Abajo;
			Destino->AddSlot().AutoWidth().Padding(1.0f, 1.0f)
			[ Ficha(Delgrupo[i], false, false) ];
		}
		Columna->AddSlot().AutoHeight()[ Arriba ];
		Columna->AddSlot().AutoHeight()[ Abajo ];
		Columna->AddSlot().AutoHeight().Padding(0.0f, 1.0f, 0.0f, 0.0f).HAlign(HAlign_Center)
		[
			SNew(STextBlock)
			.Text(FText::FromString(Grupo))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
			.ColorAndOpacity(FSlateColor(Tenue))
		];
		FilaGrupos->AddSlot().AutoWidth().Padding(3.0f, 0.0f)[ Columna ];
	}

	TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 0.0f)
	[
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 2.0f)
		[
			SNew(STextBlock)
			.Text(LOCTEXT("MasTutoriales", "MÁS TUTORIALES"))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", 7))
			.ColorAndOpacity(FSlateColor(Tenue))
		]
		+ SVerticalBox::Slot().AutoHeight()[ FilaGrupos ]
	];
}

const FJamTool* SJamGraphEditor::FindTool(const FString& Verb) const
{
	return Tools.FindByPredicate([&Verb](const FJamTool& T) { return T.Verb == Verb; });
}

SJamGraphEditor::FGNode* SJamGraphEditor::FindNode(const FString& Id)
{
	return Nodes.FindByPredicate([&Id](const FGNode& N) { return N.Id == Id; });
}

FString SJamGraphEditor::AddNodeAlCentro(const FString& Verb)
{
	// El centro de lo que estás MIRANDO, no el de la escena ni el origen del grafo. Con el canvas
	// paneado las tres cosas están en lugares distintos, y sólo una es donde vas a buscar el nodo.
	if (WireLayer.IsValid())
	{
		const FVector2D Centro = WireLayer->GetCachedGeometry().GetLocalSize() * 0.5f;
		const FVector2D Modelo = LocalToModel(Centro) - FVector2D(NodeWidth * 0.5f, 20.0f);
		return AddNode(Verb, &Modelo);
	}
	return AddNode(Verb);
}

FReply SJamGraphEditor::OnDragOver(const FGeometry&, const FDragDropEvent& E)
{
	return E.GetOperationAs<FJamVerbDrag>().IsValid() ? FReply::Handled() : FReply::Unhandled();
}

FReply SJamGraphEditor::OnDrop(const FGeometry& MyGeometry, const FDragDropEvent& E)
{
	const TSharedPtr<FJamVerbDrag> Op = E.GetOperationAs<FJamVerbDrag>();
	if (!Op.IsValid())
	{
		return FReply::Unhandled();
	}
	// Misma referencia que el doble clic: el overlay del CANVAS y no el editor completo, o el nodo
	// cae desplazado hacia abajo la altura del menú y del ribbon.
	const FVector2D Local = WireLayer.IsValid()
		? WireLayer->GetCachedGeometry().AbsoluteToLocal(E.GetScreenSpacePosition())
		: MyGeometry.AbsoluteToLocal(E.GetScreenSpacePosition());
	const FVector2D Modelo = LocalToModel(Local) - FVector2D(NodeWidth * 0.5f, 20.0f);

	// El nodo NO se crea acá. `AddNode` agrega slots al canvas, y hacerlo dentro del manejo del drop
	// muta la jerarquía de widgets mientras Slate la está recorriendo: el crash aparece en
	// `Prepass_Internal` → `ForEachWidget` → `GetChildRefAt` con un índice fuera de rango. Es
	// intermitente porque depende de que el drop caiga dentro de ese recorrido, y por eso costó
	// tanto de atrapar. Se difiere un frame, cuando Slate ya terminó.
	DropPendienteVerbo = Op->Verb;
	DropPendientePos = Modelo;
	RegisterActiveTimer(0.0f, FWidgetActiveTimerDelegate::CreateSP(
		this, &SJamGraphEditor::CrearNodoDiferido));
	return FReply::Handled();
}

EActiveTimerReturnType SJamGraphEditor::CrearNodoDiferido(const double, const float)
{
	if (!DropPendienteVerbo.IsEmpty())
	{
		const FVector2D Donde = DropPendientePos;
		const FString Verbo = DropPendienteVerbo;
		// Se limpia ANTES de crear: si `AddNode` fallara, un pendiente sin borrar volvería a
		// intentarlo en cada frame.
		DropPendienteVerbo.Reset();
		AddNode(Verbo, &Donde);
	}
	return EActiveTimerReturnType::Stop;
}

FString SJamGraphEditor::AddNode(const FString& Verb, const FVector2D* At,
	const FString& PreferredId)
{
	const FJamTool* T = FindTool(Verb);
	if (T == nullptr || !Canvas.IsValid())
	{
		return FString();
	}

	FGNode Node;
	const bool bIdLibre = !PreferredId.IsEmpty()
		&& !Nodes.ContainsByPredicate([&PreferredId](const FGNode& X) { return X.Id == PreferredId; });
	if (bIdLibre)
	{
		Node.Id = PreferredId;
		// El contador no puede volver a emitir un número que ya está en uso: si el archivo trae
		// «n7», el próximo nodo nuevo tiene que ser «n8» y no «n2».
		if (PreferredId.StartsWith(TEXT("n")))
		{
			const int32 K = FCString::Atoi(*PreferredId.Mid(1));
			if (K >= NextId) { NextId = K + 1; }
		}
	}
	else
	{
		Node.Id = FString::Printf(TEXT("n%d"), NextId++);
	}
	Node.Verb = Verb;
	if (At != nullptr)
	{
		Node.Pos = *At;   // nace donde hiciste doble clic (como Grasshopper)
	}
	else
	{
		// cascada para que no se apilen exactamente encima
		const int32 K = Nodes.Num();
		Node.Pos = FVector2D(30.0f + (K % 4) * 190.0f, 30.0f + (K / 4) * 40.0f + (K % 4) * 20.0f);
	}

	TArray<FJamNodeParam> Params;
	// La fila `asset`: pin con NOMBRE y campo de texto, que se grisea solo cuando le entra un cable.
	// Vacío es un error de Compile; el Graph nunca hereda en silencio el asset activo ni el primero
	// de la biblioteca (esa comodidad queda limitada a la Dash Bar).
	//
	// Cuando el asset es la entrada PRINCIPAL del verbo, esta fila ES esa entrada —y por eso no hay
	// además un nub anónimo en el header: sería la misma cosa dos veces—. Los que reciben otra cosa
	// arriba la conservan como parámetro aparte: `mesh_leaf` toma una curva por el header.
	const bool bFilaEsLaEntrada = (T->InName == TEXT("A") && T->bAssetRow);
	if (T->bAssetRow)
	{
		FJamNodeParam Fila(TEXT("asset"), FString(), TEXT("str"), TArray<FString>(),
			TArray<FString>(), TEXT("A"), DataColor(TEXT("A")));
		// Cuando el asset ES la entrada principal, esta fila no es un parámetro aparte: es LA
		// entrada. Su pin se llama «in», así el cable de un grafo guardado ancla acá y no en un nub
		// del header que ya no se dibuja.
		const FString PinDeLaFila = bFilaEsLaEntrada ? TEXT("in") : TEXT("asset");
		Fila.PinName = PinDeLaFila;
		Params.Add(Fila);
		Node.PinNames.Add(PinDeLaFila);
	}
	// Params con los que NACE el nodo. Para los que colocan algo, Python devuelve el punto de mira
	// ya escrito en x/y/z: capturado UNA vez, acá, y no leído en cada Run.
	//
	// Es la salida de una tensión real. Leer la cámara al correr hace que lo que colocás aparezca
	// donde estás mirando —sin eso todo aterriza en el origen del mundo y parece que la herramienta
	// no hizo nada— pero rompe que dos Run del mismo grafo den lo mismo. Capturar al crear da las
	// dos cosas, y deja las coordenadas a la vista para editarlas. Es lo que hace Houdini cuando
	// soltás un nodo.
	const TMap<FString, FString> Iniciales =
		FModuleManager::LoadModuleChecked<FJamEditorModule>("JamEditor").ParamsDeNodoNuevo(Verb);

	for (const FJamParam& P : T->Params)
	{
		FString Value = P.Default;
		if (const FString* Capturado = Iniciales.Find(P.Name))
		{
			Value = *Capturado;
		}
		// El nodo «asset» nace apuntando a lo elegido en Content (Content → nodo, sin tipear).
		if (Verb == TEXT("asset") && P.Name == TEXT("name") && Value.IsEmpty() && ActiveAsset.IsSet())
		{
			Value = ActiveAsset.Get();
		}
		// Tipo + opciones del spec → el nodo pinta el widget correcto (toggle/dropdown/texto).
		TArray<FString> Opts;
		TArray<FString> OptionLabels;
		for (const TSharedPtr<FString>& O : P.Options)
		{
			if (O.IsValid()) { Opts.Add(*O); }
		}
		for (const TSharedPtr<FString>& L : P.OptionLabels)
		{
			if (L.IsValid()) { OptionLabels.Add(*L); }
		}
		const FString DataType = P.DataType.IsEmpty() ? JamParamDataType(P.Name, P.Type) : P.DataType;
		FJamNodeParam Param(P.Name, Value, P.Type, Opts, OptionLabels,
			DataType, DataColor(DataType));
		Param.Label = P.Label;
		Params.Add(MoveTemp(Param));
		Node.PinNames.Add(P.Name);
	}

	TArray<FJamNodePin> NamedInputs;
	for (const FJamTool::FPin& P : T->InputPins)
	{
		NamedInputs.Add(FJamNodePin{P.Name, P.Type, DataName(P.Type), DataColor(P.Type)});
		Node.PinNames.Add(P.Name);   // después de Params: ése es también su índice visual de fila
	}
	TArray<FJamNodePin> NamedOutputs;
	for (const FJamTool::FPin& P : T->OutputPins)
	{
		NamedOutputs.Add(FJamNodePin{P.Name, P.Type, DataName(P.Type), DataColor(P.Type)});
		Node.OutputPinNames.Add(P.Name);
	}

	const FString Id = Node.Id;
	// Nodos FUENTE (producen el dato, no lo reciben): sin pin de entrada, convención de Grasshopper.
	// El flag viene del spec (data-driven): asset/pick/create_spline y las fuentes de flow.
	const bool bHasInput = !T->bSource && !bFilaEsLaEntrada;
	const bool bHasHeaderInput = T->InputPins.Num() == 0 && bHasInput;

	TSharedRef<SJamGraphNode> Widget = SNew(SJamGraphNode)
		.Verb(Verb)
		.DisplayName(T->Label.IsEmpty() ? Verb : T->Label)
		.IconPath(IconPathForVerb(Verb))
		.IconColor(CategoryColor(T->Cat))
		.OutputPinName(TEXT("out"))
		.OutputDataType(T->OutName)
		.InputColor(DataColor(T->InName))
		.OutputColor(DataColor(T->OutName))
		.InputLabel(DataName(T->InName))
		.OutputLabel(T->OutLabel.IsEmpty() ? DataName(T->OutName)
			: FString::Printf(TEXT("%s (%s)"), *T->OutLabel, *DataName(T->OutName)))
		.Params(Params)
		.InputPins(NamedInputs)
		.OutputPins(NamedOutputs)
		.HasInput(bHasHeaderInput)
		.CanBypass(JamPuedeBypass(*T))
		.IsSelected_Lambda([this, Id]() { return SelectedNodeIds.Contains(Id); })
		.OnDragDelta_Lambda([this, Id](const FVector2D& D)
		{
			// D viene en píxeles de pantalla; el modelo vive antes del zoom (render transform).
			// Arrastrar un nodo elegido mueve TODO el grupo, conservando las distancias — es el
			// gesto que hace que la selección múltiple sirva para algo.
			if (SelectedNodeIds.Contains(Id))
			{
				MoveSelection(D / Zoom);
			}
			else if (FGNode* N = FindNode(Id))
			{
				N->Pos += D / Zoom;
			}
		})
		.OnOutputClicked_Lambda([this, Id](const FString& Pin) { OnPinClicked(Id, Pin, true); })
		.OnInputClicked_Lambda([this, Id](const FString& Pin) { OnPinClicked(Id, Pin, false); })
		.OnClicked_Lambda([this, Id](bool bShift, bool bCtrl) { ClickNode(Id, bShift, bCtrl); })
		.OnDragEnd_Lambda([this]() { Marcar(); })
		// Confirmar un parámetro es un paso del historial Y algo que puede cambiar el resultado.
		.OnParamChanged_Lambda([this]() { Marcar(); PedirRecoccion(); })
		// Arrastrando: sólo recocina. Meter esto en el historial lo llenaría de un paso por frame.
		.OnParamLive_Lambda([this]() { PedirRecoccion(); })
		.OnBypassChanged_Lambda([this]() { Marcar(); PedirRecoccion(); })
		.OnDebugChanged_Lambda([this, Id]() { SoloVerNodo(Id); })
		.OnCompactoCambiado_Lambda([this, Id]()
		{
			// El ancho es del EDITOR, no del widget: lo leen los cables, el marquee y el encuadre.
			if (FGNode* N = FindNode(Id); N && N->Widget.IsValid())
			{
				N->Width = N->Widget->IsCompacto() ? NodeWidthCompacto : NodeWidth;
			}
			Marcar();
		})
		.OnThumbnailOpen_Lambda([this, Id]() { AbrirVisorFullRes(Id); })
		.OnPedirVariables_Lambda([this]() { return VariablesDelGrafo(); })
		.OnDeleteSelection_Lambda([this, Id]()
		{
			// `Supr` sobre un nodo de un grupo borra el grupo; sobre uno suelto, ese nodo.
			if (SelectedNodeIds.Contains(Id)) { DeleteSelection(); } else { DeleteNode(Id); }
		})
		.OnDeleteClicked_Lambda([this, Id]() { DeleteNode(Id); });

	Node.Widget = Widget;

	const float Height = SJamGraphNode::NodeHeight(
		Params.Num() + FMath::Max(NamedInputs.Num(), NamedOutputs.Num()));
	Node.Height = Height;
	Canvas->AddSlot()
		.Position(TAttribute<FVector2D>::CreateLambda([this, Id]()
		{
			const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
			return N ? N->Pos + PanOffset : FVector2D::ZeroVector;   // el modelo no se mueve: se mueve la vista
		}))
		.Size(TAttribute<FVector2D>::CreateLambda([this, Id]()
		{
			const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
			return N ? FVector2D(N->Width, N->Height) : FVector2D(NodeWidth, 34.0f);
		}))
		[
			Widget
		];

	Nodes.Add(Node);
	Marcar();
	return Id;
}

void SJamGraphEditor::DeleteNode(const FString& Id)
{
	FGNode* N = FindNode(Id);
	if (N == nullptr)
	{
		return;
	}
	if (N->Widget.IsValid() && Canvas.IsValid())
	{
		Canvas->RemoveSlot(N->Widget.ToSharedRef());
	}
	Edges.RemoveAll([&Id](const FGEdge& E) { return E.From == Id || E.To == Id; });
	if (PendingSource == Id) { PendingSource.Empty(); }
	Nodes.RemoveAll([&Id](const FGNode& X) { return X.Id == Id; });
	SelectedNodeIds.Remove(Id);   // un id borrado que queda elegido reaparece al reusarse el número
	RefreshCabledPins();   // borrar un nodo pudo dejar pines de otros sin su cable
	Marcar();
}

// ---- cajas de comentario/grupo (Fase 7.1) ----

SJamGraphEditor::FGComment* SJamGraphEditor::FindComment(const FString& Id)
{
	return Comments.FindByPredicate([&Id](const FGComment& C) { return C.Id == Id; });
}

FString SJamGraphEditor::AddComment(const FVector2D& Pos, const FVector2D& Size, const FString& Title,
	const FString& PreferredId, const FLinearColor& Color)
{
	if (!CommentCanvas.IsValid())
	{
		return FString();
	}

	FGComment Comment;
	const bool bIdLibre = !PreferredId.IsEmpty()
		&& !Comments.ContainsByPredicate([&PreferredId](const FGComment& X) { return X.Id == PreferredId; });
	if (bIdLibre)
	{
		Comment.Id = PreferredId;
		// Mismo trato que AddNode: el contador no puede volver a emitir un número ya usado por el
		// archivo que se está cargando.
		if (PreferredId.StartsWith(TEXT("c")))
		{
			const int32 K = FCString::Atoi(*PreferredId.Mid(1));
			if (K >= NextCommentId) { NextCommentId = K + 1; }
		}
	}
	else
	{
		Comment.Id = FString::Printf(TEXT("c%d"), NextCommentId++);
	}
	Comment.Pos = Pos;
	Comment.Size = Size;
	Comment.Title = Title;
	Comment.Color = Color;

	const FString Id = Comment.Id;
	TSharedRef<SJamGraphComment> Widget = SNew(SJamGraphComment)
		.Title(Title)
		.Color(Color)
		.IsSelected_Lambda([this, Id]() { return SelectedCommentIds.Contains(Id); })
		.OnClicked_Lambda([this, Id](bool bShift, bool bCtrl) { ClickComment(Id, bShift, bCtrl); })
		.OnDragBegin_Lambda([this, Id]() { BeginCommentDrag(Id); })
		.OnDragDelta_Lambda([this, Id](const FVector2D& D) { DragComment(Id, D); })
		.OnDragEnd_Lambda([this]() { Marcar(); })
		.OnResizeDelta_Lambda([this, Id](const FVector2D& D) { ResizeComment(Id, D); })
		.OnResizeEnd_Lambda([this]() { Marcar(); })
		.OnDeleteSelection_Lambda([this, Id]()
		{
			// `Supr` sobre una caja de un grupo elegido borra el grupo; sobre una suelta, esa caja.
			if (SelectedCommentIds.Contains(Id)) { DeleteSelection(); } else { DeleteComment(Id); }
		})
		.OnTitleChanged_Lambda([this]() { Marcar(); })
		.OnColorChanged_Lambda([this]() { Marcar(); });

	Comment.Widget = Widget;

	CommentCanvas->AddSlot()
		.Position(TAttribute<FVector2D>::CreateLambda([this, Id]()
		{
			const FGComment* C = Comments.FindByPredicate([&Id](const FGComment& X) { return X.Id == Id; });
			return C ? C->Pos + PanOffset : FVector2D::ZeroVector;   // el modelo no se mueve: se mueve la vista
		}))
		.Size(TAttribute<FVector2D>::CreateLambda([this, Id]()
		{
			const FGComment* C = Comments.FindByPredicate([&Id](const FGComment& X) { return X.Id == Id; });
			return C ? C->Size : FVector2D(240.0f, 160.0f);
		}))
		[
			Widget
		];

	Comments.Add(Comment);
	Marcar();
	return Id;
}

void SJamGraphEditor::DeleteComment(const FString& Id)
{
	FGComment* C = FindComment(Id);
	if (C == nullptr)
	{
		return;
	}
	if (C->Widget.IsValid() && CommentCanvas.IsValid())
	{
		CommentCanvas->RemoveSlot(C->Widget.ToSharedRef());
	}
	Comments.RemoveAll([&Id](const FGComment& X) { return X.Id == Id; });
	SelectedCommentIds.Remove(Id);
	Marcar();
}

void SJamGraphEditor::ClickComment(const FString& Id, bool bShift, bool bCtrl)
{
	// Mismo trato que ClickNode, sobre su propio set: independiente de SelectedNodeIds a propósito
	// (ver el comentario de SelectedCommentIds en el header).
	if (bCtrl)
	{
		if (SelectedCommentIds.Contains(Id)) { SelectedCommentIds.Remove(Id); }
		else { SelectedCommentIds.Add(Id); }
		return;
	}
	if (bShift)
	{
		SelectedCommentIds.Add(Id);
		return;
	}
	if (!SelectedCommentIds.Contains(Id))
	{
		SelectedCommentIds.Reset();
		SelectedCommentIds.Add(Id);
	}
}

void SJamGraphEditor::CreateCommentFromSelection()
{
	if (SelectedNodeIds.Num() == 0)
	{
		return;
	}
	// Mismo cálculo de bounding box que Encuadrar(bSoloSeleccion=true), sin la parte de fit-to-viewport.
	FVector2D Min(TNumericLimits<float>::Max(), TNumericLimits<float>::Max());
	FVector2D Max(TNumericLimits<float>::Lowest(), TNumericLimits<float>::Lowest());
	int32 Contados = 0;
	for (const FGNode& N : Nodes)
	{
		if (!SelectedNodeIds.Contains(N.Id)) { continue; }
		Min.X = FMath::Min(Min.X, N.Pos.X);
		Min.Y = FMath::Min(Min.Y, N.Pos.Y);
		Max.X = FMath::Max(Max.X, N.Pos.X + N.Width);
		Max.Y = FMath::Max(Max.Y, N.Pos.Y + N.Height);
		++Contados;
	}
	if (Contados == 0)
	{
		return;
	}
	// Margen generoso + la franja de título: sin eso el borde de la caja tapa el nodo de más arriba.
	const float Margen = 60.0f;
	const float FranjaTitulo = 28.0f;
	const FVector2D Pos = Min - FVector2D(Margen, Margen + FranjaTitulo);
	const FVector2D Size = (Max - Min) + FVector2D(Margen * 2.0f, Margen * 2.0f + FranjaTitulo);
	const FString Id = AddComment(Pos, Size, LOCTEXT("NuevoComentario", "Comentario").ToString());
	if (!Id.IsEmpty())
	{
		SelectedCommentIds.Reset();
		SelectedCommentIds.Add(Id);
	}
}

void SJamGraphEditor::BeginCommentDrag(const FString& Id)
{
	// Se congela ACÁ, al empezar el gesto — nunca se persiste (ver FGComment en el header).
	CommentDragNodeIds.Reset();
	if (const FGComment* C = FindComment(Id))
	{
		CommentDragNodeIds = NodeIdsTouchingRect(C->Pos, C->Pos + C->Size);
	}
}

void SJamGraphEditor::DragComment(const FString& Id, const FVector2D& DeltaModelo)
{
	if (FGComment* C = FindComment(Id)) { C->Pos += DeltaModelo; }
	for (const FString& NodeId : CommentDragNodeIds)
	{
		if (FGNode* N = FindNode(NodeId)) { N->Pos += DeltaModelo; }
	}
}

void SJamGraphEditor::ResizeComment(const FString& Id, const FVector2D& DeltaModelo)
{
	FGComment* C = FindComment(Id);
	if (C == nullptr)
	{
		return;
	}
	// Mínimo para que no se invierta ni desaparezca arrastrando el handle hacia el título.
	const FVector2D MinSize(80.0f, 60.0f);
	C->Size.X = FMath::Max(C->Size.X + DeltaModelo.X, MinSize.X);
	C->Size.Y = FMath::Max(C->Size.Y + DeltaModelo.Y, MinSize.Y);
}

// ---- historial ----

void SJamGraphEditor::Marcar()
{
	if (bSinHistorial)
	{
		return;
	}
	Deshechos.Add(Anterior);
	if (Deshechos.Num() > MaxHistorial)
	{
		Deshechos.RemoveAt(0);   // el tope corre la ventana; se pierde lo más viejo, no lo reciente
	}
	// Un paso nuevo corta la rama de Rehacer: es la convención de todo editor, y sin esto Ctrl+Y
	// después de editar traería de vuelta un estado que ya no encaja con lo que hay en pantalla.
	Rehechos.Reset();
	Anterior = BuildJson();
}

void SJamGraphEditor::RestaurarSnapshot(const FString& Json)
{
	// Deshacer NO cambia de documento: `LoadGraphJson` pasa por `NewGraph`, que borra `CurrentPath`
	// porque abrir uno vacío sí empieza un archivo nuevo. Sin esto, un Ctrl+Z hacía que el próximo
	// «Guardar» pidiera nombre en vez de sobrescribir el .jamgraph en el que venías trabajando.
	const FString Documento = CurrentPath;
	TGuardValue<bool> Callado(bSinHistorial, true);
	if (LoadGraphJson(Json, /*bConservarEdicionFuncion*/ true))
	{
		Anterior = BuildJson();
	}
	CurrentPath = Documento;
}

void SJamGraphEditor::Deshacer()
{
	if (Deshechos.Num() == 0)
	{
		return;
	}
	Rehechos.Add(Anterior);
	const FString Destino = Deshechos.Pop();
	RestaurarSnapshot(Destino);
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("deshecho (quedan %d)"), Deshechos.Num())));
	}
}

void SJamGraphEditor::Rehacer()
{
	if (Rehechos.Num() == 0)
	{
		return;
	}
	Deshechos.Add(Anterior);
	const FString Destino = Rehechos.Pop();
	RestaurarSnapshot(Destino);
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("rehecho (quedan %d)"), Rehechos.Num())));
	}
}

// ---- estado del canvas (cerrar el panel ya no tira el trabajo) ----

FString SJamGraphEditor::EstadoDelCanvas() const
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	TSharedRef<FJsonObject> Vista = MakeShared<FJsonObject>();
	Vista->SetNumberField(TEXT("x"), PanOffset.X);
	Vista->SetNumberField(TEXT("y"), PanOffset.Y);
	Vista->SetNumberField(TEXT("zoom"), Zoom);
	Root->SetObjectField(TEXT("view"), Vista);

	// El grafo se guarda como OBJETO y no como string: así el estado entero sigue siendo un JSON que
	// se puede leer y diffear, en vez de un JSON con otro JSON escapado adentro.
	TSharedPtr<FJsonObject> Grafo;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(BuildJson());
	if (FJsonSerializer::Deserialize(Reader, Grafo) && Grafo.IsValid())
	{
		Root->SetObjectField(TEXT("graph"), Grafo);
	}
	Root->SetStringField(TEXT("path"), CurrentPath);
	if (!FuncionEnEdicion.IsEmpty())
	{
		Root->SetStringField(TEXT("function_edit_verb"), FuncionEnEdicion);
		Root->SetStringField(TEXT("function_edit_name"), NombreFuncionEnEdicion);
		Root->SetStringField(TEXT("function_return_state"), EstadoAntesDeEditarFuncion);
	}

	FString Json;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	FJsonSerializer::Serialize(Root, Writer);
	return Json;
}

void SJamGraphEditor::RestaurarCanvas(const FString& Json)
{
	if (Json.IsEmpty())
	{
		return;
	}
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	const TSharedPtr<FJsonObject>* Grafo = nullptr;
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
		|| !Root->TryGetObjectField(TEXT("graph"), Grafo) || Grafo == nullptr)
	{
		return;
	}
	FString GrafoJson;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&GrafoJson);
	FJsonSerializer::Serialize(Grafo->ToSharedRef(), Writer);

	// Reabrir el panel NO es un paso deshacible: el historial arranca de cero con el grafo puesto.
	TGuardValue<bool> Callado(bSinHistorial, true);
	if (!LoadGraphJson(GrafoJson))
	{
		return;
	}
	Anterior = BuildJson();
	Deshechos.Reset();
	Rehechos.Reset();

	const TSharedPtr<FJsonObject>* Vista = nullptr;
	if (Root->TryGetObjectField(TEXT("view"), Vista) && Vista != nullptr)
	{
		double X = 0.0, Y = 0.0, Z = 1.0;
		(*Vista)->TryGetNumberField(TEXT("x"), X);
		(*Vista)->TryGetNumberField(TEXT("y"), Y);
		(*Vista)->TryGetNumberField(TEXT("zoom"), Z);
		PanOffset = FVector2D(static_cast<float>(X), static_cast<float>(Y));
		Zoom = FMath::Clamp(static_cast<float>(Z), 0.35f, 2.5f);
		ApplyZoom();
	}
	// `LoadGraphJson` pasa por `NewGraph`, que limpia el archivo actual: recuperarlo es lo que hace
	// que «Guardar» siga sobrescribiendo el .jamgraph en el que venías y no pida nombre de nuevo.
	FString Documento;
	if (Root->TryGetStringField(TEXT("path"), Documento))
	{
		CurrentPath = Documento;
	}
	Root->TryGetStringField(TEXT("function_edit_verb"), FuncionEnEdicion);
	Root->TryGetStringField(TEXT("function_edit_name"), NombreFuncionEnEdicion);
	Root->TryGetStringField(TEXT("function_return_state"), EstadoAntesDeEditarFuncion);
	if (ActiveTab == TEXT("Funciones")) { RebuildTabContent(); }
}

// ---- portapapeles ----

void SJamGraphEditor::Copiar(bool bCortar)
{
	if (SelectedNodeIds.Num() == 0 && SelectedCommentIds.Num() == 0)
	{
		return;
	}
	// Al portapapeles DEL SISTEMA y no a un buffer interno: así se pega entre dos ventanas de Graph,
	// y el fragmento se puede pegar en un chat o en el vault — es el mismo JSON de un .jamgraph.
	const FString Recorte = BuildJson(&SelectedNodeIds, &SelectedCommentIds);
	FPlatformApplicationMisc::ClipboardCopy(*Recorte);
	const int32 Cuantos = SelectedNodeIds.Num() + SelectedCommentIds.Num();
	if (bCortar)
	{
		DeleteSelection();
	}
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("%s: %d elemento%s"), bCortar ? TEXT("cortado") : TEXT("copiado"),
			Cuantos, Cuantos == 1 ? TEXT("") : TEXT("s"))));
	}
}

void SJamGraphEditor::Pegar()
{
	FString Recorte;
	FPlatformApplicationMisc::ClipboardPaste(Recorte);
	if (PegarJson(Recorte, /*bDesplazar*/ true)) { Marcar(); }
}

void SJamGraphEditor::Duplicar()
{
	if (SelectedNodeIds.Num() == 0 && SelectedCommentIds.Num() == 0)
	{
		return;
	}
	// Sin tocar el portapapeles: duplicar no puede pisar lo que tenías copiado.
	if (PegarJson(BuildJson(&SelectedNodeIds, &SelectedCommentIds), /*bDesplazar*/ true)) { Marcar(); }
}

void SJamGraphEditor::ColapsarSeleccion()
{
	if (SelectedNodeIds.Num() == 0 || !OnCollapseFunction.IsBound()) { return; }

	FString Nombre;
	if (!JamPedirNombre(LOCTEXT("CollapseNameTitle", "Nueva función"), TEXT(""), AsShared(), Nombre))
	{ return; }

	TArray<TSharedPtr<FJsonValue>> Elegidos;
	for (const FString& Id : SelectedNodeIds)
	{
		Elegidos.Add(MakeShared<FJsonValueString>(Id));
	}
	FString SelectedJson;
	const TSharedRef<TJsonWriter<>> SelectedWriter = TJsonWriterFactory<>::Create(&SelectedJson);
	FJsonSerializer::Serialize(Elegidos, SelectedWriter);

	const FString Res = OnCollapseFunction.Execute(Nombre, BuildJson(), SelectedJson);
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		if (Output.IsValid()) { Output->SetText(FText::FromString(TEXT("FUNCIÓN ✗ — respuesta ilegible: ") + Res)); }
		return;
	}
	FString Report;
	Root->TryGetStringField(TEXT("report"), Report);
	bool bOk = false;
	if (!Root->TryGetBoolField(TEXT("ok"), bOk) || !bOk)
	{
		if (Output.IsValid()) { Output->SetText(FText::FromString(Report)); }
		return;
	}

	// El preset acaba de nacer y el canvas ya estaba construido: instalar su ficha antes de cargar
	// el padre, porque `LoadGraphJson` rechaza correctamente cualquier verbo que no conoce.
	const TSharedPtr<FJsonObject>* ToolObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("tool"), ToolObj) || ToolObj == nullptr)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("CollapseNoTool", "FUNCIÓN ✗ — falta el spec de la instancia")); }
		return;
	}
	FJamTool Tool;
	(*ToolObj)->TryGetStringField(TEXT("verbo"), Tool.Verb);
	if (!(*ToolObj)->TryGetStringField(TEXT("label"), Tool.Label)) { Tool.Label = Tool.Verb; }
	(*ToolObj)->TryGetStringField(TEXT("cat"), Tool.Cat);
	(*ToolObj)->TryGetStringField(TEXT("seccion"), Tool.Section);
	if (Tool.Section.IsEmpty()) { Tool.Section = Tool.Cat; }
	(*ToolObj)->TryGetStringField(TEXT("grupo"), Tool.Group);
	(*ToolObj)->TryGetStringField(TEXT("doc"), Tool.Doc);
	(*ToolObj)->TryGetBoolField(TEXT("source"), Tool.bSource);
	double Arity = Tool.bSource ? 0.0 : 1.0;
	(*ToolObj)->TryGetNumberField(TEXT("aridad"), Arity);
	Tool.Arity = static_cast<int32>(Arity);
	auto LeerPines = [&ToolObj](const TCHAR* Campo, TArray<FJamTool::FPin>& Destino)
	{
		const TArray<TSharedPtr<FJsonValue>>* Pines = nullptr;
		if (!(*ToolObj)->TryGetArrayField(Campo, Pines) || Pines == nullptr) { return; }
		for (const TSharedPtr<FJsonValue>& V : *Pines)
		{
			const TSharedPtr<FJsonObject> P = V.IsValid() ? V->AsObject() : nullptr;
			FJamTool::FPin Pin;
			if (P.IsValid() && P->TryGetStringField(TEXT("name"), Pin.Name)
				&& P->TryGetStringField(TEXT("tipo"), Pin.Type))
			{
				Destino.Add(Pin);
			}
		}
	};
	LeerPines(TEXT("inputs"), Tool.InputPins);
	LeerPines(TEXT("outputs"), Tool.OutputPins);
	JamLeerParamsDeFicha(*ToolObj, Tool.Params);   // las perillas de la función
	if (Tool.Verb.IsEmpty())
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("CollapseBadTool", "FUNCIÓN ✗ — spec sin verbo")); }
		return;
	}
	Tools.RemoveAll([&Tool](const FJamTool& T) { return T.Verb == Tool.Verb; });
	Tools.Add(MoveTemp(Tool));
	if (ActiveTab == TEXT("Funciones")) { RebuildTabContent(); }

	const TSharedPtr<FJsonObject>* GraphObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("graph"), GraphObj) || GraphObj == nullptr)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("CollapseNoGraph", "FUNCIÓN ✗ — falta el grafo padre")); }
		return;
	}
	FString GraphJson;
	const TSharedRef<TJsonWriter<>> GraphWriter = TJsonWriterFactory<>::Create(&GraphJson);
	FJsonSerializer::Serialize(GraphObj->ToSharedRef(), GraphWriter);

	// `ColapsarSeleccion` reconstruye el grafo padre en PYTHON (jam.funcion), que no sabe nada de
	// cajas de comentario: sin este parche, cualquier caja desaparecería en silencio en cada Ctrl+G.
	// Se saca una foto ANTES de `LoadGraphJson` (que vacía todo vía NewGraph) y se reinyecta después,
	// bajo el mismo TGuardValue que ya usa `LoadGraphJson` para que todo sea UN solo paso de undo.
	const TArray<FGComment> ComentariosDeAntes = Comments;
	bool bCargado = false;
	{
		TGuardValue<bool> Callado(bSinHistorial, true);
		bCargado = LoadGraphJson(GraphJson);
		if (bCargado)
		{
			// La caja es organizativa, no dueña de nada: no hace falta filtrar las que encerraban
			// nodos ahora colapsados, sigue existiendo conteniendo (o no) la nueva instancia de función.
			for (const FGComment& C : ComentariosDeAntes)
			{
				AddComment(C.Pos, C.Size, C.Widget.IsValid() ? C.Widget->GetTitle() : C.Title, C.Id,
					C.Widget.IsValid() ? C.Widget->GetColor() : C.Color);
			}
		}
	}
	if (bCargado)
	{
		Marcar();
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(Report));
		}
	}
}

bool SJamGraphEditor::AplicarRespuestaFuncion(const FString& Res, bool bCargarCuerpo)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		if (Output.IsValid()) { Output->SetText(FText::FromString(TEXT("FUNCIÓN ✗ — respuesta ilegible: ") + Res)); }
		return false;
	}
	FString Report;
	Root->TryGetStringField(TEXT("report"), Report);
	bool bOk = false;
	if (!Root->TryGetBoolField(TEXT("ok"), bOk) || !bOk)
	{
		if (Output.IsValid()) { Output->SetText(FText::FromString(Report)); }
		return false;
	}

	const TSharedPtr<FJsonObject>* ToolObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("tool"), ToolObj) || ToolObj == nullptr)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("ManageNoTool", "FUNCIÓN ✗ — falta el spec")); }
		return false;
	}
	FJamTool Tool;
	(*ToolObj)->TryGetStringField(TEXT("verbo"), Tool.Verb);
	if (!(*ToolObj)->TryGetStringField(TEXT("label"), Tool.Label)) { Tool.Label = Tool.Verb; }
	(*ToolObj)->TryGetStringField(TEXT("cat"), Tool.Cat);
	(*ToolObj)->TryGetStringField(TEXT("seccion"), Tool.Section);
	if (Tool.Section.IsEmpty()) { Tool.Section = Tool.Cat; }
	(*ToolObj)->TryGetStringField(TEXT("grupo"), Tool.Group);
	(*ToolObj)->TryGetStringField(TEXT("doc"), Tool.Doc);
	(*ToolObj)->TryGetBoolField(TEXT("source"), Tool.bSource);
	double Arity = Tool.bSource ? 0.0 : 1.0;
	(*ToolObj)->TryGetNumberField(TEXT("aridad"), Arity);
	Tool.Arity = static_cast<int32>(Arity);
	auto LeerPines = [&ToolObj](const TCHAR* Campo, TArray<FJamTool::FPin>& Destino)
	{
		const TArray<TSharedPtr<FJsonValue>>* Pines = nullptr;
		if (!(*ToolObj)->TryGetArrayField(Campo, Pines) || Pines == nullptr) { return; }
		for (const TSharedPtr<FJsonValue>& V : *Pines)
		{
			const TSharedPtr<FJsonObject> P = V.IsValid() ? V->AsObject() : nullptr;
			FJamTool::FPin Pin;
			if (P.IsValid() && P->TryGetStringField(TEXT("name"), Pin.Name)
				&& P->TryGetStringField(TEXT("tipo"), Pin.Type)) { Destino.Add(Pin); }
		}
	};
	LeerPines(TEXT("inputs"), Tool.InputPins);
	LeerPines(TEXT("outputs"), Tool.OutputPins);
	JamLeerParamsDeFicha(*ToolObj, Tool.Params);   // las perillas de la función
	if (Tool.Verb.IsEmpty()) { return false; }

	const FString Verb = Tool.Verb;
	const FString Nombre = Tool.Label;
	Tools.RemoveAll([&Verb](const FJamTool& T) { return T.Verb == Verb; });
	Tools.Add(MoveTemp(Tool));
	if (FuncionEnEdicion == Verb) { NombreFuncionEnEdicion = Nombre; }

	if (bCargarCuerpo)
	{
		const TSharedPtr<FJsonObject>* GraphObj = nullptr;
		if (!Root->TryGetObjectField(TEXT("graph"), GraphObj) || GraphObj == nullptr) { return false; }
		FString GraphJson;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&GraphJson);
		FJsonSerializer::Serialize(GraphObj->ToSharedRef(), Writer);
		if (!LoadGraphJson(GraphJson, /*bConservarEdicionFuncion*/ true)) { return false; }
		FuncionEnEdicion = Verb;
		NombreFuncionEnEdicion = Nombre;
	}
	if (ActiveTab == TEXT("Funciones")) { RebuildTabContent(); }
	if (Output.IsValid()) { Output->SetText(FText::FromString(Report)); }
	return true;
}

void SJamGraphEditor::NuevaFuncion()
{
	if (!FuncionEnEdicion.IsEmpty() || !OnFunctionManage.IsBound()) { return; }
	FString Nombre;
	if (!JamPedirNombre(LOCTEXT("NewFunctionTitle", "Nueva función"), TEXT(""), AsShared(), Nombre))
	{ return; }
	EstadoAntesDeEditarFuncion = EstadoDelCanvas();
	if (!AplicarRespuestaFuncion(
		OnFunctionManage.Execute(TEXT("create"), TEXT(""), Nombre), true))
	{
		EstadoAntesDeEditarFuncion.Reset();
	}
}

void SJamGraphEditor::EditarFuncion(const FString& Verb)
{
	if (FuncionEnEdicion.IsEmpty() && OnFunctionManage.IsBound())
	{
		EstadoAntesDeEditarFuncion = EstadoDelCanvas();
		if (!AplicarRespuestaFuncion(
			OnFunctionManage.Execute(TEXT("get"), Verb, TEXT("")), true))
		{
			EstadoAntesDeEditarFuncion.Reset();
		}
	}
}

void SJamGraphEditor::GuardarFuncion()
{
	if (FuncionEnEdicion.IsEmpty() || !OnFunctionManage.IsBound()) { return; }
	AplicarRespuestaFuncion(
		OnFunctionManage.Execute(TEXT("update"), FuncionEnEdicion, BuildJson()), false);
}

void SJamGraphEditor::GuardarYCerrarFuncion()
{
	if (FuncionEnEdicion.IsEmpty() || !OnFunctionManage.IsBound()) { return; }
	if (AplicarRespuestaFuncion(
		OnFunctionManage.Execute(TEXT("update"), FuncionEnEdicion, BuildJson()), false))
	{
		VolverDeFuncion(true);
	}
}

void SJamGraphEditor::VolverDeFuncion(bool bCambiosGuardados)
{
	if (FuncionEnEdicion.IsEmpty()) { return; }
	const FString Nombre = NombreFuncionEnEdicion;
	const FString Destino = EstadoAntesDeEditarFuncion;
	FuncionEnEdicion.Reset();
	NombreFuncionEnEdicion.Reset();
	EstadoAntesDeEditarFuncion.Reset();
	if (Destino.IsEmpty())
	{
		NewGraph();
	}
	else
	{
		RestaurarCanvas(Destino);
	}
	if (ActiveTab == TEXT("Funciones")) { RebuildTabContent(); }
	if (Output.IsValid())
	{
		const FString Mensaje = bCambiosGuardados
			? FString::Printf(TEXT("FUNCIÓN guardada ✓ — «%s» · de vuelta en el grafo"), *Nombre)
			: FString::Printf(
				TEXT("Cambios sin guardar descartados — «%s» · de vuelta en el grafo"), *Nombre);
		Output->SetText(FText::FromString(Mensaje));
	}
}

void SJamGraphEditor::PublicarFuncion(const FString& Verb, bool bPublicar)
{
	if (!OnFunctionManage.IsBound()) { return; }
	const FString Res = OnFunctionManage.Execute(
		TEXT("publish"), Verb, bPublicar ? TEXT("true") : TEXT("false"));
	// El cuerpo no cambió, así que no hace falta recargar el canvas: sólo el reporte y el ribbon.
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	FString Report = Res;
	if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())
	{
		Root->TryGetStringField(TEXT("report"), Report);
	}
	if (Output.IsValid()) { Output->SetText(FText::FromString(Report)); }
}

void SJamGraphEditor::ExportarFuncion(const FString& Verb, const FString& NombreActual)
{
	IDesktopPlatform* DP = FDesktopPlatformModule::Get();
	if (DP == nullptr || !OnFunctionManage.IsBound()) { return; }
	const FString Dir = FPaths::ProjectSavedDir() / TEXT("JamTools");
	IFileManager::Get().MakeDirectory(*Dir, true);
	TArray<FString> Files;
	const bool bOk = DP->SaveFileDialog(nullptr, TEXT("Exportar herramienta de Jam"), Dir,
		NombreActual + TEXT(".jamtool"), TEXT("Herramienta de Jam (*.jamtool)|*.jamtool"),
		EFileDialogFlags::None, Files);
	if (!bOk || Files.Num() == 0) { return; }

	// La ruta viaja como payload: `function_manage` ya es el único puente de ABM de definiciones.
	const FString Res = OnFunctionManage.Execute(TEXT("export"), Verb, Files[0]);
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	FString Report = Res;
	if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())
	{
		if (!Root->TryGetStringField(TEXT("report"), Report))
		{
			Root->TryGetStringField(TEXT("error"), Report);
		}
	}
	if (Output.IsValid()) { Output->SetText(FText::FromString(Report)); }
}

void SJamGraphEditor::RenombrarFuncion(const FString& Verb, const FString& NombreActual)
{
	if (!OnFunctionManage.IsBound()) { return; }
	FString Nombre;
	if (!JamPedirNombre(LOCTEXT("RenameFunctionTitle", "Renombrar función"),
		NombreActual, AsShared(), Nombre)) { return; }
	AplicarRespuestaFuncion(OnFunctionManage.Execute(TEXT("rename"), Verb, Nombre), false);
}

void SJamGraphEditor::EliminarFuncion(const FString& Verb, const FString& NombreActual)
{
	if (!OnFunctionManage.IsBound()) { return; }
	if (Nodes.ContainsByPredicate([&Verb](const FGNode& N) { return N.Verb == Verb; }))
	{
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("FUNCIÓN ✗ — el grafo abierto todavía usa «%s»"), *NombreActual)));
		}
		return;
	}
	const FText Pregunta = FText::FromString(FString::Printf(
		TEXT("¿Eliminar «%s»?\n\nLos presets externos todavía no tienen índice de referencias."),
		*NombreActual));
	if (FMessageDialog::Open(EAppMsgType::YesNo, Pregunta) != EAppReturnType::Yes) { return; }

	const FString Res = OnFunctionManage.Execute(TEXT("delete"), Verb, TEXT(""));
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	FString Report;
	bool bOk = false;
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
		|| !Root->TryGetBoolField(TEXT("ok"), bOk) || !bOk)
	{
		if (Root.IsValid()) { Root->TryGetStringField(TEXT("report"), Report); }
		if (Output.IsValid()) { Output->SetText(FText::FromString(Report.IsEmpty() ? Res : Report)); }
		return;
	}
	Root->TryGetStringField(TEXT("report"), Report);
	Tools.RemoveAll([&Verb](const FJamTool& T) { return T.Verb == Verb; });
	if (FuncionEnEdicion == Verb)
	{
		FuncionEnEdicion.Reset();
		NombreFuncionEnEdicion.Reset();
	}
	RebuildTabContent();
	if (Output.IsValid()) { Output->SetText(FText::FromString(Report)); }
}

bool SJamGraphEditor::PegarJson(const FString& Json, bool bDesplazar)
{
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	const TSharedPtr<FJsonObject>* NodesObj = nullptr;
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
		|| !Root->TryGetObjectField(TEXT("nodes"), NodesObj) || NodesObj == nullptr)
	{
		// El portapapeles del sistema puede tener cualquier cosa: no es un error del usuario.
		if (Output.IsValid())
		{
			Output->SetText(LOCTEXT("PasteNotGraph", "el portapapeles no tiene nodos de Jam."));
		}
		return false;
	}

	// Corrimiento fijo para que lo pegado no quede exactamente encima del original y parezca que no
	// pasó nada. Pegar dos veces escalona, que es lo que hace todo editor nodal.
	const FVector2D Corrimiento = bDesplazar ? FVector2D(26.0f, 26.0f) : FVector2D::ZeroVector;

	// Todo el pegado corre callado: N nodos con sus cables son UN Ctrl+Z. El paso lo registra el que
	// llamó, según lo que devolvamos — así el `Marcar()` no queda adentro del silencio. Con
	// `TGuardValue` porque acá abajo hay `return`s: una bandera a mano se quedaría prendida y mataría
	// el historial en silencio por el resto de la sesión.
	TGuardValue<bool> Callado(bSinHistorial, true);
	TMap<FString, FString> IdMap;
	TSet<FString> Pegados;
	for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*NodesObj)->Values)
	{
		const TSharedPtr<FJsonObject> NO = KV.Value.IsValid() ? KV.Value->AsObject() : nullptr;
		FString Verb;
		double X = 0.0, Y = 0.0;
		if (!NO.IsValid() || !NO->TryGetStringField(TEXT("verb"), Verb) || FindTool(Verb) == nullptr
			|| !NO->TryGetNumberField(TEXT("x"), X) || !NO->TryGetNumberField(TEXT("y"), Y))
		{
			continue;   // nodo ilegible o de un verbo que este Jam no tiene: se saltea, no se aborta
		}
		const FVector2D At(static_cast<float>(X) + Corrimiento.X, static_cast<float>(Y) + Corrimiento.Y);
		// Ids NUEVOS a propósito: los del recorte casi seguro ya existen en este grafo.
		const FString NewId = AddNode(Verb, &At);
		if (NewId.IsEmpty())
		{
			continue;
		}
		IdMap.Add(KV.Key, NewId);
		Pegados.Add(NewId);
		if (FGNode* Node = FindNode(NewId); Node && Node->Widget.IsValid())
		{
			TMap<FString, FString> Params;
			const TSharedPtr<FJsonObject>* PO = nullptr;
			if (NO->TryGetObjectField(TEXT("params"), PO) && PO != nullptr)
			{
				for (const TPair<FString, TSharedPtr<FJsonValue>> PV : (*PO)->Values)
				{
					FString Value;
					if (PV.Value.IsValid() && PV.Value->TryGetString(Value))
					{
						Params.Add(PV.Key, Value);
					}
				}
			}
			Node->Widget->SetParamValues(Params);
			bool bDebug = false;
			if (NO->TryGetBoolField(TEXT("debug"), bDebug)) { Node->Widget->SetDebugEnabled(bDebug); }
			bool bBypass = false;
			if (NO->TryGetBoolField(TEXT("bypass"), bBypass)) { Node->Widget->SetBypassed(bBypass); }
			bool bComp = false;
			if (NO->TryGetBoolField(TEXT("compact"), bComp))
			{
				Node->Widget->SetCompacto(bComp);
				Node->Width = bComp ? NodeWidthCompacto : NodeWidth;
			}
		}
	}
	const TArray<TSharedPtr<FJsonValue>>* EdgesArr = nullptr;
	if (Root->TryGetArrayField(TEXT("edges"), EdgesArr) && EdgesArr != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& EV : *EdgesArr)
		{
			const TArray<TSharedPtr<FJsonValue>>* E = nullptr;
			if (!EV.IsValid() || !EV->TryGetArray(E) || E == nullptr || (E->Num() != 2 && E->Num() != 4))
			{
				continue;
			}
			FString From, FromPin = TEXT("out"), To, ToPin = TEXT("in");
			const bool bStrings = E->Num() == 2
				? (*E)[0]->TryGetString(From) && (*E)[1]->TryGetString(To)
				: (*E)[0]->TryGetString(From) && (*E)[1]->TryGetString(FromPin)
					&& (*E)[2]->TryGetString(To) && (*E)[3]->TryGetString(ToPin);
			const FString* NuevoFrom = bStrings ? IdMap.Find(From) : nullptr;
			const FString* NuevoTo = bStrings ? IdMap.Find(To) : nullptr;
			if (NuevoFrom == nullptr || NuevoTo == nullptr)
			{
				continue;   // una punta quedó afuera del pegado
			}
			// La MISMA compuerta que usa conectar a mano: un cable pegado no puede entrar por una
			// puerta que un cable dibujado no podría cruzar.
			FString Error;
			if (CanConnect(*NuevoFrom, FromPin, *NuevoTo, ToPin, Error))
			{
				Edges.Add(FGEdge{*NuevoFrom, FromPin, *NuevoTo, ToPin});
			}
		}
	}
	RefreshCabledPins();

	// Cajas de comentario/grupo: a diferencia de las aristas, NO hay ninguna referencia cruzada que
	// remapear — la contención se recalcula al primer arrastre (`BeginCommentDrag`) y nunca se
	// persiste, así que pegar una caja es más simple que pegar un nodo. Id NUEVO siempre: el del
	// recorte casi seguro ya existe en este grafo.
	TSet<FString> PegadosComentarios;
	const TSharedPtr<FJsonObject>* CommentsObj = nullptr;
	if (Root->TryGetObjectField(TEXT("comments"), CommentsObj) && CommentsObj != nullptr)
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*CommentsObj)->Values)
		{
			const TSharedPtr<FJsonObject> CO = KV.Value.IsValid() ? KV.Value->AsObject() : nullptr;
			double X = 0.0, Y = 0.0, W = 0.0, H = 0.0;
			FString Title;
			if (!CO.IsValid()
				|| !CO->TryGetNumberField(TEXT("x"), X) || !CO->TryGetNumberField(TEXT("y"), Y)
				|| !CO->TryGetNumberField(TEXT("w"), W) || !CO->TryGetNumberField(TEXT("h"), H))
			{
				continue;   // caja ilegible: se saltea, no aborta el resto del pegado
			}
			CO->TryGetStringField(TEXT("title"), Title);
			FLinearColor Color(0.65f, 0.60f, 0.50f, 1.0f);
			const TArray<TSharedPtr<FJsonValue>>* ColorArr = nullptr;
			double R = 0.0, G = 0.0, B = 0.0;
			if (CO->TryGetArrayField(TEXT("color"), ColorArr) && ColorArr != nullptr && ColorArr->Num() == 3
				&& (*ColorArr)[0]->TryGetNumber(R) && (*ColorArr)[1]->TryGetNumber(G) && (*ColorArr)[2]->TryGetNumber(B))
			{
				Color = FLinearColor(R, G, B);
			}
			const FVector2D At(static_cast<float>(X) + Corrimiento.X, static_cast<float>(Y) + Corrimiento.Y);
			const FString NewId = AddComment(At, FVector2D(W, H), Title, FString(), Color);
			if (!NewId.IsEmpty())
			{
				PegadosComentarios.Add(NewId);
			}
		}
	}

	if (Pegados.Num() == 0 && PegadosComentarios.Num() == 0)
	{
		if (Output.IsValid())
		{
			Output->SetText(LOCTEXT("PasteNothing", "no había nada pegable en el portapapeles."));
		}
		return false;
	}

	// Lo pegado queda elegido: es lo que uno quiere mover o volver a pegar enseguida.
	SelectedNodeIds = Pegados;
	SelectedCommentIds = PegadosComentarios;
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(TEXT("pegado: %d nodos, %d comentarios"),
			Pegados.Num(), PegadosComentarios.Num())));
	}
	return true;
}

void SJamGraphEditor::Encuadrar(bool bSoloSeleccion)
{
	if (!WireLayer.IsValid() || Nodes.Num() == 0)
	{
		return;
	}
	const bool bRecorte = bSoloSeleccion && SelectedNodeIds.Num() > 0;
	FVector2D Min(TNumericLimits<float>::Max(), TNumericLimits<float>::Max());
	FVector2D Max(TNumericLimits<float>::Lowest(), TNumericLimits<float>::Lowest());
	int32 Contados = 0;
	for (const FGNode& N : Nodes)
	{
		if (bRecorte && !SelectedNodeIds.Contains(N.Id)) { continue; }
		Min.X = FMath::Min(Min.X, N.Pos.X);
		Min.Y = FMath::Min(Min.Y, N.Pos.Y);
		Max.X = FMath::Max(Max.X, N.Pos.X + N.Width);
		Max.Y = FMath::Max(Max.Y, N.Pos.Y + N.Height);
		++Contados;
	}
	if (Contados == 0)
	{
		return;
	}
	const FVector2D Lienzo = WireLayer->GetCachedGeometry().GetLocalSize();
	if (Lienzo.X <= 1.0f || Lienzo.Y <= 1.0f)
	{
		return;
	}
	const float Margen = 40.0f;
	const FVector2D Cuadro = (Max - Min) + FVector2D(Margen * 2.0f, Margen * 2.0f);
	// El mismo clamp que el zoom con la rueda: encuadrar no puede dejar la vista en un zoom al que
	// después no se puede volver arrastrando.
	Zoom = FMath::Clamp(FMath::Min(Lienzo.X / Cuadro.X, Lienzo.Y / Cuadro.Y), 0.35f, 2.5f);
	// pantalla = (modelo + Pan) * Zoom  ⇒  centrar el cuadro es despejar Pan.
	PanOffset = Lienzo / (2.0f * Zoom) - (Min + Max) * 0.5f;
	ApplyZoom();
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("encuadrado: %d nodo%s"), Contados, Contados == 1 ? TEXT("") : TEXT("s"))));
	}
}

// ---- selección ----

void SJamGraphEditor::ClickNode(const FString& Id, bool bShift, bool bCtrl)
{
	if (bCtrl)
	{
		if (SelectedNodeIds.Contains(Id)) { SelectedNodeIds.Remove(Id); }
		else { SelectedNodeIds.Add(Id); }
		return;
	}
	if (bShift)
	{
		SelectedNodeIds.Add(Id);
		return;
	}
	// Sin modificadores: reemplaza la selección… salvo que el nodo YA esté elegido. Sin esa
	// excepción, agarrar un grupo por cualquiera de sus nodos lo desarmaría en el mismo gesto con
	// el que se lo quiere mover.
	if (!SelectedNodeIds.Contains(Id))
	{
		SelectedNodeIds.Reset();
		SelectedNodeIds.Add(Id);
	}
}

void SJamGraphEditor::ClearSelection()
{
	SelectedNodeIds.Reset();
	SelectedCommentIds.Reset();
}

void SJamGraphEditor::SelectAll()
{
	SelectedNodeIds.Reset();
	for (const FGNode& N : Nodes)
	{
		SelectedNodeIds.Add(N.Id);
	}
}

void SJamGraphEditor::DeleteSelection()
{
	// Copia: `DeleteNode`/`DeleteComment` tocan estos sets, y recorrer un TSet mientras se modifica
	// es UB.
	TArray<FString> Ids = SelectedNodeIds.Array();
	TArray<FString> CommentIds = SelectedCommentIds.Array();
	if (Ids.Num() == 0 && CommentIds.Num() == 0)
	{
		return;
	}
	{
		// Borrar 12 nodos es UN paso para el usuario: sin esto, deshacerlo pediría 12 Ctrl+Z.
		TGuardValue<bool> Callado(bSinHistorial, true);
		for (const FString& Id : Ids)
		{
			DeleteNode(Id);
		}
		// Borrar la caja NO borra lo que contiene: es organizativa, no dueña de nada.
		for (const FString& Id : CommentIds)
		{
			DeleteComment(Id);
		}
	}
	SelectedNodeIds.Reset();
	SelectedCommentIds.Reset();
	Marcar();
}

void SJamGraphEditor::AlternarBypassDeLaSeleccion()
{
	// Los que admiten bypass, nada más. Si TODOS los elegibles ya están apagados se prenden; si hay
	// aunque sea uno prendido, se apagan todos — así el gesto sobre un grupo mixto tiene un
	// resultado predecible en vez de invertir cada nodo por su cuenta.
	TArray<SJamGraphNode*> Elegibles;
	for (const FString& Id : SelectedNodeIds)
	{
		if (FGNode* N = FindNode(Id); N && N->Widget.IsValid() && N->Widget->CanBypass())
		{
			Elegibles.Add(N->Widget.Get());
		}
	}
	if (Elegibles.Num() == 0)
	{
		if (Output.IsValid())
		{
			Output->SetText(LOCTEXT("BypassNoAplica",
				"bypass: ninguno de los nodos elegidos lo admite (sólo los que reciben y producen el mismo tipo)."));
		}
		return;
	}

	bool bHayPrendido = false;
	for (const SJamGraphNode* W : Elegibles)
	{
		bHayPrendido = bHayPrendido || !W->IsBypassed();
	}
	for (SJamGraphNode* W : Elegibles)
	{
		W->SetBypassed(bHayPrendido);
	}
	Marcar();   // apagar N nodos es UN paso, como borrarlos
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("%s %d nodo%s"), bHayPrendido ? TEXT("apagados:") : TEXT("prendidos:"),
			Elegibles.Num(), Elegibles.Num() == 1 ? TEXT("") : TEXT("s"))));
	}
}

void SJamGraphEditor::MoveSelection(const FVector2D& DeltaModelo)
{
	for (const FString& Id : SelectedNodeIds)
	{
		if (FGNode* N = FindNode(Id)) { N->Pos += DeltaModelo; }
	}
}

bool SJamGraphEditor::GetMarquee(FVector2D& OutA, FVector2D& OutB) const
{
	if (!bMarquee)
	{
		return false;
	}
	OutA = MarqueeA;
	OutB = MarqueeB;
	return true;
}

TArray<FString> SJamGraphEditor::NodeIdsTouchingRect(const FVector2D& Min, const FVector2D& Max) const
{
	// Cruzar alcanza: si el rectángulo TOCA el nodo, entra. Desigualdad ESTRICTA — la MISMA regla
	// que `jam.layout.en_marco`, y la ÚNICA copia de esta fórmula en todo el archivo (la comparte el
	// marquee y el arrastre del cuerpo de una caja de comentario).
	TArray<FString> Out;
	if (Min.X < Max.X && Min.Y < Max.Y)
	{
		for (const FGNode& N : Nodes)
		{
			if (N.Pos.X < Max.X && N.Pos.X + N.Width > Min.X
				&& N.Pos.Y < Max.Y && N.Pos.Y + N.Height > Min.Y)
			{
				Out.Add(N.Id);
			}
		}
	}
	return Out;
}

void SJamGraphEditor::AcomodarSeleccion(const FString& Accion)
{
	if (!OnLayout.IsBound())
	{
		return;
	}
	// `auto` acomoda el GRAFO ENTERO cuando no hay nada elegido: es el gesto de «ordename esto»,
	// y pedir que selecciones todo antes sería un paso de más. Alinear y distribuir siguen
	// necesitando 2+ elegidos — no hay a qué alinear un grafo entero.
	// `auto` y `snap` acomodan el GRAFO ENTERO cuando no hay nada elegido: son gestos de
	// «ordename esto» y pedir que selecciones todo antes sería un paso de más.
	const bool bAuto = Accion == TEXT("auto");
	const bool bTodoElGrafo = bAuto || Accion == TEXT("snap");
	const bool bTodo = bTodoElGrafo && SelectedNodeIds.Num() < 2;
	if (!bTodo && SelectedNodeIds.Num() < 2)
	{
		return;
	}
	auto Entra = [this, bTodo](const FString& Id)
	{
		return bTodo || SelectedNodeIds.Contains(Id);
	};

	// Rectángulos en coordenadas de MODELO: lo que `jam.layout` sabe leer. El ancho es fijo; el
	// alto NO (depende de cuántos params tiene el verbo), y es justo el que hace que alinear
	// «abajo» sea distinto de alinear por `y`.
	TArray<FString> Filas;
	for (const FGNode& N : Nodes)
	{
		if (!Entra(N.Id)) { continue; }
		Filas.Add(FString::Printf(
			TEXT("{\"id\":\"%s\",\"x\":%.3f,\"y\":%.3f,\"w\":%.3f,\"h\":%.3f}"),
			*N.Id, N.Pos.X, N.Pos.Y, N.Width, N.Height));
	}
	if (Filas.Num() == 0)
	{
		return;
	}
	FString Json = FString::Printf(TEXT("[%s]"), *FString::Join(Filas, TEXT(",")));
	if (bAuto)
	{
		// `auto` es el único que necesita saber cómo están CABLEADOS los nodos, no sólo dónde
		// están: las capas salen del grafo, no de las posiciones. Van todos los cables con las dos
		// puntas adentro, sin importar por qué pin entran — para el orden topológico da igual.
		TArray<FString> Cables;
		for (const FGEdge& E : Edges)
		{
			if (Entra(E.From) && Entra(E.To))
			{
				Cables.Add(FString::Printf(TEXT("[\"%s\",\"%s\"]"), *E.From, *E.To));
			}
		}
		Json = FString::Printf(TEXT("{\"nodos\":%s,\"edges\":[%s]}"),
			*Json, *FString::Join(Cables, TEXT(",")));
	}

	const FString Res = OnLayout.Execute(Json, Accion);
	TSharedPtr<FJsonObject> Obj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Res);
	if (!FJsonSerializer::Deserialize(Reader, Obj) || !Obj.IsValid()
		|| !Obj->GetBoolField(TEXT("ok")))
	{
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("No se pudo acomodar: %s"), *Res)));
		}
		return;
	}
	const TSharedPtr<FJsonObject>* Pos = nullptr;
	if (!Obj->TryGetObjectField(TEXT("pos"), Pos) || Pos == nullptr)
	{
		return;
	}
	for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*Pos)->Values)
	{
		const TArray<TSharedPtr<FJsonValue>>* XY = nullptr;
		if (!KV.Value->TryGetArray(XY) || XY == nullptr || XY->Num() != 2) { continue; }
		if (FGNode* N = FindNode(KV.Key))
		{
			N->Pos = FVector2D((*XY)[0]->AsNumber(), (*XY)[1]->AsNumber());
		}
	}
	Marcar();
}

int32 SJamGraphEditor::PinIndex(const FString& Id, const FString& Pin) const
{
	if (Pin == TEXT("out"))
	{
		return -1;   // header
	}
	const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
	if (N == nullptr) { return -1; }
	// «in» normalmente vive en el header (-1), pero en los verbos cuya entrada es un asset vive en
	// la FILA `asset`. Buscarlo siempre en PinNames resuelve los dos casos: si no está, es header.
	return N->PinNames.IndexOfByKey(Pin);
}

int32 SJamGraphEditor::OutputPinIndex(const FString& Id, const FString& Pin) const
{
	const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
	if (N == nullptr) { return -1; }
	const int32 FirmaIndex = N->OutputPinNames.IndexOfByKey(Pin);
	if (FirmaIndex == INDEX_NONE) { return Pin == TEXT("out") ? -1 : INDEX_NONE; }
	// Las filas de firma empiezan después de todos los params/asset. `PinNames` contiene esos params
	// y luego las entradas nombradas; restarlas recupera exactamente el offset visual.
	const FJamTool* T = FindTool(N->Verb);
	const int32 EntradasDeFirma = T ? T->InputPins.Num() : 0;
	return N->PinNames.Num() - EntradasDeFirma + FirmaIndex;
}

FString SJamGraphEditor::OutputDataTypeFor(const FString& NodeId, const FString& Pin) const
{
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	if (T == nullptr) { return FString(); }
	if (const FJamTool::FPin* P = T->OutputPins.FindByPredicate(
		[&Pin](const FJamTool::FPin& X) { return X.Name == Pin; }))
	{
		return P->Type;
	}
	if (Pin == TEXT("out")) { return T->OutName; }
	return FString();
}

FString SJamGraphEditor::InputDataTypeFor(const FString& NodeId, const FString& Pin) const
{
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	if (N == nullptr || T == nullptr)
	{
		return FString();
	}
	if (const FJamTool::FPin* P = T->InputPins.FindByPredicate(
		[&Pin](const FJamTool::FPin& X) { return X.Name == Pin; }))
	{
		return P->Type;
	}
	if (Pin == TEXT("in"))
	{
		return (!T->bSource && T->Arity != 0) ? T->InName : FString();
	}
	if (!N->PinNames.Contains(Pin))
	{
		return FString();
	}
	if (Pin == TEXT("asset") && T->bAssetRow)
	{
		return TEXT("A");
	}
	const FJamParam* P = T->Params.FindByPredicate(
		[&Pin](const FJamParam& Param) { return Param.Name == Pin; });
	return P ? (P->DataType.IsEmpty() ? JamParamDataType(P->Name, P->Type) : P->DataType) : FString();
}

/** Regla ÚNICA de compatibilidad de tipos entre un pin de salida y uno de entrada.
 *
 *  Vivía duplicada en `CanConnect` (al tender un cable) y en `LoadGraphJson` (al abrir un archivo).
 *  Agregar el comodín en una sola dejó el otro camino rechazando lo que la UI aceptaba: un ejemplo
 *  con un nodo Debug se tendía bien a mano pero no se podía abrir. Con la regla en un solo lugar el
 *  desfasaje no puede volver a pasar.
 *
 *  «*» es un pin COMODÍN: lo usa el ayudante de Debug, que dibuja cualquier cosa que llegue. */
static bool JamTiposCompatibles(const FString& OutType, const FString& InType,
	const TArray<FString>* Extras = nullptr)
{
	if (OutType.IsEmpty() || InType.IsEmpty())
	{
		return false;
	}
	if (InType == TEXT("*") || OutType == TEXT("*") || OutType == InType)
	{
		return true;
	}
	// Tipos EXTRA declarados por el verbo de destino (`in_accepts` del registro): `place`
	// admite A y también la colección A[]. NO es un comodín — la lista es cerrada, y quien
	// la escribe es Python. Que falte un pin compañero (A[] sin `points`) lo dice el
	// Compile: tender el cable es legal, y el oráculo es quien juzga.
	return Extras != nullptr && Extras->Contains(OutType);
}

bool SJamGraphEditor::CanConnect(const FString& From, const FString& FromPin, const FString& To,
	const FString& ToPin, FString& OutError) const
{
	if (From == To)
	{
		OutError = TEXT("un nodo no puede conectarse a sí mismo");
		return false;
	}
	const FString OutType = OutputDataTypeFor(From, FromPin);
	if (OutType.IsEmpty())
	{
		OutError = FString::Printf(TEXT("%s.%s no es una salida válida"), *From, *FromPin);
		return false;
	}
	const FString InType = InputDataTypeFor(To, ToPin);
	if (InType.IsEmpty())
	{
		OutError = FString::Printf(TEXT("%s.%s no es una entrada válida"), *To, *ToPin);
		return false;
	}
	const FGNode* NodoDestino = Nodes.FindByPredicate(
		[&To](const FGNode& X) { return X.Id == To; });
	const FJamTool* ToolDestino = NodoDestino ? FindTool(NodoDestino->Verb) : nullptr;
	const TArray<FString>* Extras = (ToPin == TEXT("in") && ToolDestino != nullptr)
		? &ToolDestino->InAccepts : nullptr;
	if (!JamTiposCompatibles(OutType, InType, Extras))
	{
		OutError = FString::Printf(TEXT("tipo incompatible: %s.%s entrega %s; %s.%s espera %s"),
			*From, *FromPin, *OutType, *To, *ToPin, *InType);
		return false;
	}
	return true;
}

bool SJamGraphEditor::ViaBajoElCursor(const FVector2D& EnCanvas, int32& OutArista, int32& OutVia) const
{
	// El mismo radio de agarre que usa el hit-test del cable, para que sacar un punto y ponerlo
	// respondan igual de generosos.
	const float Agarre = 14.0f * Zoom;
	for (int32 a = 0; a < Edges.Num(); ++a)
	{
		for (int32 v = 0; v < Edges[a].Vias.Num(); ++v)
		{
			const FVector2D EnPantalla = (Edges[a].Vias[v] + PanOffset) * Zoom;
			if (FVector2D::Distance(EnPantalla, EnCanvas) <= Agarre)
			{
				OutArista = a;
				OutVia = v;
				return true;
			}
		}
	}
	return false;
}

bool SJamGraphEditor::CableBajoPunto(const FVector2D& EnCanvas, int32& OutArista,
	int32& OutSegmento, FVector2D& OutPuntoModelo) const
{
	if (!OnCableBajoPunto.IsBound())
	{
		return false;
	}
	// Los tramos en coordenadas de MODELO, con «arista:segmento» como id. Se manda por tramo y no
	// por arista para saber ENTRE QUÉ DOS puntos cae el clic cuando el cable ya tiene vías.
	const FVector2D Modelo = LocalToModel(EnCanvas);
	const float Half = SJamGraphNode::PinColW * 0.5f;
	TArray<FString> Tramos;
	for (int32 a = 0; a < Edges.Num(); ++a)
	{
		const FGEdge& E = Edges[a];
		const FGNode* NA = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.From; });
		const FGNode* NB = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.To; });
		if (NA == nullptr || NB == nullptr) { continue; }
		TArray<FVector2D> Puntos;
		Puntos.Add(FVector2D(NA->Pos.X + NA->Width - Half,
			NA->Pos.Y + SJamGraphNode::PinLocalY(OutputPinIndex(E.From, E.FromPin))));
		Puntos.Append(E.Vias);
		Puntos.Add(FVector2D(NB->Pos.X + Half,
			NB->Pos.Y + SJamGraphNode::PinLocalY(PinIndex(E.To, E.ToPin))));
		for (int32 i = 0; i + 1 < Puntos.Num(); ++i)
		{
			Tramos.Add(FString::Printf(
				TEXT("{\"id\":\"%d:%d\",\"ax\":%.3f,\"ay\":%.3f,\"bx\":%.3f,\"by\":%.3f}"),
				a, i, Puntos[i].X, Puntos[i].Y, Puntos[i + 1].X, Puntos[i + 1].Y));
		}
	}
	if (Tramos.Num() == 0)
	{
		return false;
	}

	const FString Json = FString::Printf(
		TEXT("{\"x\":%.3f,\"y\":%.3f,\"cables\":[%s]}"),
		Modelo.X, Modelo.Y, *FString::Join(Tramos, TEXT(",")));
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(OnCableBajoPunto.Execute(Json));
	FString Cable;
	double PX = 0.0, PY = 0.0;
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
		|| !Root->TryGetStringField(TEXT("cable"), Cable)
		|| !Root->TryGetNumberField(TEXT("x"), PX) || !Root->TryGetNumberField(TEXT("y"), PY))
	{
		return false;   // no había cable bajo el cursor
	}
	FString AristaTxt, SegmentoTxt;
	if (!Cable.Split(TEXT(":"), &AristaTxt, &SegmentoTxt)) { return false; }
	OutArista = FCString::Atoi(*AristaTxt);
	OutSegmento = FCString::Atoi(*SegmentoTxt);
	// El punto llega SOBRE la curva (lo devuelve `jam.layout`), no donde se hizo clic.
	OutPuntoModelo = FVector2D(PX, PY);
	return Edges.IsValidIndex(OutArista);
}

bool SJamGraphEditor::AlternarViaEnCable(const FVector2D& EnCanvas)
{
	// Doble clic SOBRE un punto que ya está: lo saca. Es el mismo gesto que lo puso, que es lo que
	// uno prueba primero para deshacerlo.
	int32 Arista = -1, Via = -1;
	if (ViaBajoElCursor(EnCanvas, Arista, Via))
	{
		Edges[Arista].Vias.RemoveAt(Via);
		if (WireLayer.IsValid()) { WireLayer->Invalidate(EInvalidateWidgetReason::Paint); }
		Marcar();
		return true;
	}
	int32 Segmento = -1;
	FVector2D Punto = FVector2D::ZeroVector;
	if (!CableBajoPunto(EnCanvas, Arista, Segmento, Punto))
	{
		return false;   // que el doble clic siga su camino y abra el buscador
	}
	Edges[Arista].Vias.Insert(Punto, FMath::Clamp(Segmento, 0, Edges[Arista].Vias.Num()));
	if (WireLayer.IsValid()) { WireLayer->Invalidate(EInvalidateWidgetReason::Paint); }
	Marcar();
	return true;
}

bool SJamGraphEditor::InsertarRerouteEnCable(const FVector2D& EnCanvas)
{
	int32 Arista = -1, Segmento = -1;
	FVector2D Punto = FVector2D::ZeroVector;
	if (!CableBajoPunto(EnCanvas, Arista, Segmento, Punto))
	{
		return false;
	}
	const FGEdge Original = Edges[Arista];

	// El verbo sale del REGISTRO y no de una tabla a mano: se busca el `reroute_*` cuya entrada sea
	// del tipo que lleva este cable. Sumar `reroute_points` mañana lo hace funcionar solo.
	const FString Tipo = OutputDataTypeFor(Original.From, Original.FromPin);
	const FJamTool* Verbo = Tools.FindByPredicate([&Tipo](const FJamTool& T)
	{
		return T.Verb.StartsWith(TEXT("reroute_")) && T.InName == Tipo;
	});
	if (Verbo == nullptr)
	{
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("no hay un reroute para cables de tipo %s."), *DataName(Tipo))));
		}
		return false;
	}

	// Centrado en el punto del cable: nace donde estaba el cable, no corrido media pantalla.
	const FVector2D At = Punto - FVector2D(NodeWidth * 0.5f, SJamGraphNode::PinLocalY(-1));
	FString NuevoId;
	{
		// Crear el nodo y recablear son UN paso: deshacerlo tiene que devolver el cable entero,
		// no dejar un reroute suelto con el cable ya cortado.
		TGuardValue<bool> Callado(bSinHistorial, true);
		NuevoId = AddNode(Verbo->Verb, &At);
		if (!NuevoId.IsEmpty())
		{
			Edges.RemoveAt(Arista);
			Edges.Add(FGEdge{Original.From, Original.FromPin, NuevoId, TEXT("in")});
			// Las vías que tenía el cable se quedan en el tramo de ABAJO: el reroute ya cumple el
			// papel de las de arriba, y conservarlas todas dejaría el cable con dos codos seguidos.
			FGEdge Segunda{NuevoId, TEXT("out"), Original.To, Original.ToPin};
			Segunda.Vias = Original.Vias;
			Edges.Add(Segunda);
			RefreshCabledPins();
		}
	}
	if (NuevoId.IsEmpty())
	{
		return false;
	}
	if (WireLayer.IsValid()) { WireLayer->Invalidate(EInvalidateWidgetReason::Paint); }
	Marcar();
	return true;
}

bool SJamGraphEditor::CancelarConexion()
{
	if (PendingSource.IsEmpty())
	{
		return false;
	}
	PendingSource.Empty();
	PendingSourcePin.Empty();
	// Repintar YA: el cable-fantasma sólo se redibuja con el movimiento del mouse, así que sin esto
	// quedaría colgado en pantalla hasta que el cursor se mueva.
	if (WireLayer.IsValid())
	{
		WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
	}
	if (Output.IsValid())
	{
		Output->SetText(LOCTEXT("ConexionCancelada", "conexión cancelada."));
	}
	return true;   // no es un paso del historial: no se llegó a cambiar el grafo
}

void SJamGraphEditor::OnPinClicked(const FString& Id, const FString& Pin, bool bOutput)
{
	// Convención de editores nodales: Alt+clic rompe las conexiones del pin. Una entrada elimina los
	// cables que llegan a ESE pin; una salida elimina todos los que parten de ella. También cancela el
	// cable fantasma para que soltar Alt no deje una conexión pendiente accidentalmente.
	if (FSlateApplication::Get().GetModifierKeys().IsAltDown())
	{
		const int32 Removed = Edges.RemoveAll([&](const FGEdge& E)
		{
			return bOutput
				? (E.From == Id && E.FromPin == Pin)
				: (E.To == Id && E.ToPin == Pin);
		});
		PendingSource.Empty();
		PendingSourcePin.Empty();
		RefreshCabledPins();
		if (WireLayer.IsValid())
		{
			WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
		}
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(Removed > 0
				? FString::Printf(TEXT("desconectado: %s.%s (%d cable%s)"),
					*Id, *Pin, Removed, Removed == 1 ? TEXT("") : TEXT("s"))
				: FString::Printf(TEXT("%s.%s no tiene conexiones"), *Id, *Pin)));
		}
		if (Removed > 0) { Marcar(); }   // Alt+clic sin cables no cambió nada: no es un paso
		return;
	}

	if (bOutput)
	{
		PendingSource = Id;       // armar la salida
		PendingSourcePin = Pin;   // (por ahora siempre «out»)
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("conectá: %s.%s → (clic en un pin de entrada)"), *Id, *Pin)));
		}
		return;
	}
	// clic en una entrada: cierra la conexión si hay una salida armada
	if (!PendingSource.IsEmpty())
	{
		const FString SourceId = PendingSource;
		const FString SourcePin = PendingSourcePin;
		FString Error;
		if (!CanConnect(SourceId, SourcePin, Id, Pin, Error))
		{
			if (Output.IsValid())
			{
				Output->SetText(FText::FromString(FString::Printf(TEXT("conexión rechazada: %s"), *Error)));
			}
			PendingSource.Empty();
			PendingSourcePin.Empty();
			if (WireLayer.IsValid())
			{
				WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
			}
			return;
		}
		const bool bDup = Edges.ContainsByPredicate([&](const FGEdge& E)
		{
			return E.From == SourceId && E.FromPin == SourcePin && E.To == Id && E.ToPin == Pin;
		});
		int32 Replaced = 0;
		if (!bDup)
		{
			const FGNode* DestNode = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
			const FJamTool* DestTool = DestNode ? FindTool(DestNode->Verb) : nullptr;
			// Parámetros y nodos unarios reciben UN cable. Sólo aridad -1 conserva varias entradas `in`.
			if (Pin != TEXT("in") || DestTool == nullptr || DestTool->Arity != -1)
			{
				Replaced = Edges.RemoveAll([&](const FGEdge& E) { return E.To == Id && E.ToPin == Pin; });
			}
			Edges.Add(FGEdge{SourceId, SourcePin, Id, Pin});
			Marcar();   // conectar es un paso; volver a hacer el mismo cable (bDup) no cambió nada
		}
		if (Output.IsValid())
		{
			const FString Message = Replaced > 0
				? FString::Printf(TEXT("wire reemplazado: %s.%s → %s.%s"),
					*SourceId, *SourcePin, *Id, *Pin)
				: FString::Printf(TEXT("wire: %s.%s → %s.%s"),
					*SourceId, *SourcePin, *Id, *Pin);
			Output->SetText(FText::FromString(Message));
		}
	}
	PendingSource.Empty();
	PendingSourcePin.Empty();
	RefreshCabledPins();
	if (WireLayer.IsValid())
	{
		WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
	}
}

void SJamGraphEditor::RefreshCabledPins()
{
	// Por cada nodo, el conjunto de pines de parámetro que hoy reciben un cable. El pin «in» (stream) no
	// cuenta: no es un campo editable. Cada widget griseará esos inputs.
	for (FGNode& N : Nodes)
	{
		TSet<FString> Pins;
		for (const FGEdge& E : Edges)
		{
			// Se incluye «in»: en los verbos cuya entrada es un asset, ese pin ES una fila con
			// campo de texto, y cableado tiene que grisearse como cualquier otro. En los demás el
			// «in» es el nub del header, que no tiene campo, así que sumarlo no cambia nada.
			if (E.To == N.Id)
			{
				Pins.Add(E.ToPin);
			}
		}
		if (N.Widget.IsValid())
		{
			N.Widget->SetCabledPins(Pins);
		}
	}
}

FLinearColor SJamGraphEditor::DataColor(const FString& OutName)
{
	// Color por TIPO de dato (como los pines/cables tipados de Blueprint): P=stream de puntos · N=número
	// · T=texto · B=booleano · A/A[]=asset/set · AF=asset por frame · N[]=serie · H=HISM · S=spline · F=frames · M=malla procedural
	// · MT=grafo de material (el shader que se está armando, todavía sin hornear) · V=vector.
	if (OutName == TEXT("P")) { return FLinearColor(0.13f, 0.44f, 0.64f, 1.0f); }   // azul  (puntos)
	if (OutName == TEXT("N")) { return FLinearColor(0.82f, 0.46f, 0.10f, 1.0f); }   // ámbar (número)
	if (OutName == TEXT("N[]")) { return FLinearColor(0.92f, 0.58f, 0.16f, 1.0f); } // ámbar claro (serie)
	if (OutName == TEXT("T")) { return FLinearColor(0.52f, 0.30f, 0.66f, 1.0f); }   // violeta (texto)
	if (OutName == TEXT("B")) { return FLinearColor(0.72f, 0.16f, 0.22f, 1.0f); }   // rojo  (booleano)
	if (OutName == TEXT("A")) { return FLinearColor(0.20f, 0.52f, 0.28f, 1.0f); }   // verde (actor)
	if (OutName == TEXT("A[]")) { return FLinearColor(0.28f, 0.62f, 0.36f, 1.0f); } // verde (set assets)
	if (OutName == TEXT("AF")) { return FLinearColor(0.38f, 0.66f, 0.28f, 1.0f); }  // lima (asset/frame)
	if (OutName == TEXT("H")) { return FLinearColor(0.16f, 0.50f, 0.46f, 1.0f); }   // verde azulado (HISM)
	if (OutName == TEXT("*")) { return FLinearColor(0.72f, 0.72f, 0.76f, 1.0f); }   // gris claro (comodín: acepta cualquier cable)
	if (OutName == TEXT("S")) { return FLinearColor(0.60f, 0.42f, 0.14f, 1.0f); }   // dorado (spline)
	if (OutName == TEXT("F")) { return FLinearColor(0.70f, 0.28f, 0.48f, 1.0f); }   // rosa  (frames)
	if (OutName == TEXT("MC")) { return FLinearColor(0.20f, 0.52f, 0.28f, 1.0f); }  // verde (config Mass)
	if (OutName == TEXT("MS")) { return FLinearColor(0.70f, 0.28f, 0.48f, 1.0f); }  // rosa (receta Mass)
	if (OutName == TEXT("MH")) { return FLinearColor(0.16f, 0.50f, 0.46f, 1.0f); }  // verde azulado (handle Mass)
	if (OutName == TEXT("M")) { return FLinearColor(0.08f, 0.58f, 0.62f, 1.0f); }   // cian (DynamicMesh)
	// Índigo claro, lejos del azul de `P`: un vector y un stream de puntos son las dos cosas que
	// más se van a cablear cerca, y distinguirlas por un pelo de tono no es distinguirlas.
	if (OutName == TEXT("V")) { return FLinearColor(0.42f, 0.42f, 0.82f, 1.0f); }   // índigo (vector)
	// Cobre, no el dorado del tab Shader: ése cae a un pelo del dorado de `S` (spline) y dos cables
	// distintos no se pueden distinguir por un pelo.
	if (OutName == TEXT("MT")) { return FLinearColor(0.55f, 0.24f, 0.10f, 1.0f); }  // cobre (grafo de material)
	return FLinearColor(0.28f, 0.30f, 0.34f, 1.0f);                                 // neutro
}

FString SJamGraphEditor::DataName(const FString& Type)
{
	// El NOMBRE del tipo, para que un pin no dependa de distinguir un color.
	//
	// Un punto verde y un punto celeste no son una etiqueta: hay que haber memorizado la paleta, y
	// con daltonismo o un monitor malo directamente no se puede. Los colores siguen —ayudan a
	// seguir un cable de un vistazo— pero la que dice qué entra es la palabra.
	if (Type == TEXT("A"))   { return TEXT("asset"); }
	if (Type == TEXT("A[]")) { return TEXT("assets"); }
	if (Type == TEXT("AF"))  { return TEXT("asset/frame"); }
	if (Type == TEXT("M"))   { return TEXT("malla"); }
	if (Type == TEXT("S"))   { return TEXT("curva"); }
	if (Type == TEXT("F"))   { return TEXT("frames"); }
	if (Type == TEXT("MC"))  { return TEXT("config Mass"); }
	if (Type == TEXT("MS"))  { return TEXT("receta Mass"); }
	if (Type == TEXT("MH"))  { return TEXT("población Mass"); }
	if (Type == TEXT("P"))   { return TEXT("puntos"); }
	if (Type == TEXT("N"))   { return TEXT("número"); }
	if (Type == TEXT("N[]")) { return TEXT("serie"); }
	if (Type == TEXT("T"))   { return TEXT("texto"); }
	if (Type == TEXT("B"))   { return TEXT("bool"); }
	if (Type == TEXT("MT"))  { return TEXT("material"); }
	if (Type == TEXT("H"))   { return TEXT("HISM"); }
	if (Type == TEXT("*"))   { return TEXT("dato"); }
	return Type;
}

FLinearColor SJamGraphEditor::WireColorFor(const FString& NodeId, const FString& Pin) const
{
	return DataColor(OutputDataTypeFor(NodeId, Pin));
}

TArray<SJamGraphEditor::FJamWire> SJamGraphEditor::GetWireEndpoints() const
{
	TArray<FJamWire> Out;
	const float Half = SJamGraphNode::PinColW * 0.5f;
	for (const FGEdge& E : Edges)
	{
		const FGNode* A = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.From; });
		const FGNode* B = Nodes.FindByPredicate([&E](const FGNode& N) { return N.Id == E.To; });
		if (A && B)
		{
			// La capa de wires NO está bajo el render transform del canvas → se aplica acá a mano.
			// Salida por el centro del pin «out» (header, derecha); entrada por el pin exacto (por su
			// índice de parámetro), como los grips por parámetro de Grasshopper.
			const float AY = SJamGraphNode::PinLocalY(OutputPinIndex(E.From, E.FromPin));
			const float BY = SJamGraphNode::PinLocalY(PinIndex(E.To, E.ToPin));
			// Un TRAMO por segmento: con puntos de paso, el cable pasa a ser varias curvas
			// encadenadas. La capa de cables no cambia — y de yapa dibuja su punto en cada vía,
			// que es exactamente cómo se ve un reroute.
			TArray<FVector2D> Puntos;
			Puntos.Add((FVector2D(A->Pos.X + A->Width - Half, A->Pos.Y + AY) + PanOffset) * Zoom);
			for (const FVector2D& Via : E.Vias)
			{
				Puntos.Add((Via + PanOffset) * Zoom);
			}
			Puntos.Add((FVector2D(B->Pos.X + Half, B->Pos.Y + BY) + PanOffset) * Zoom);
			const FLinearColor Color = WireColorFor(E.From, E.FromPin);   // tipo del dato que SALE
			for (int32 i = 0; i + 1 < Puntos.Num(); ++i)
			{
				FJamWire W;
				W.A = Puntos[i];
				W.B = Puntos[i + 1];
				W.Color = Color;
				Out.Add(W);
			}
		}
	}
	return Out;
}

bool SJamGraphEditor::GetPendingWire(FVector2D& OutFrom, FVector2D& OutTo, FLinearColor& OutColor) const
{
	if (PendingSource.IsEmpty())
	{
		return false;
	}
	const FGNode* A = Nodes.FindByPredicate([this](const FGNode& N) { return N.Id == PendingSource; });
	if (A == nullptr)
	{
		return false;
	}
	const float Half = SJamGraphNode::PinColW * 0.5f;
	const float AY = SJamGraphNode::PinLocalY(OutputPinIndex(PendingSource, PendingSourcePin));
	OutFrom = (FVector2D(A->Pos.X + A->Width - Half, A->Pos.Y + AY) + PanOffset) * Zoom;
	OutTo = LastMousePos;
	OutColor = WireColorFor(PendingSource, PendingSourcePin);
	return true;
}

FString SJamGraphEditor::BuildJson(const TSet<FString>* Solo, const TSet<FString>* SoloComentarios) const
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("schema_version"), 1);
	TSharedRef<FJsonObject> NodesObj = MakeShared<FJsonObject>();
	for (const FGNode& N : Nodes)
	{
		if (Solo != nullptr && !Solo->Contains(N.Id))
		{
			continue;
		}
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetStringField(TEXT("verb"), N.Verb);
		TSharedRef<FJsonObject> P = MakeShared<FJsonObject>();
		if (N.Widget.IsValid())
		{
			for (const TPair<FString, FString>& KV : N.Widget->GetParamValues())
			{
				P->SetStringField(KV.Key, KV.Value);
			}
		}
		J->SetObjectField(TEXT("params"), P);
		J->SetField(TEXT("asset"), MakeShared<FJsonValueNull>());
		J->SetNumberField(TEXT("x"), N.Pos.X);
		J->SetNumberField(TEXT("y"), N.Pos.Y);
		// El flag de debug viaja con el grafo: se guarda en el .jamgraph y lo lee el runner.
		if (N.Widget.IsValid() && N.Widget->IsDebugEnabled())
		{
			J->SetBoolField(TEXT("debug"), true);
		}
		// El bypass viaja igual: sólo cuando está prendido, para no ensuciar el JSON de un grafo
		// donde nadie apagó nada (y para que un .jamgraph viejo siga siendo idéntico byte a byte).
		if (N.Widget.IsValid() && N.Widget->IsBypassed())
		{
			J->SetBoolField(TEXT("bypass"), true);
		}
		// Comprimido: es estado de VISTA, pero viaja igual — reabrir un diagrama y encontrarlo todo
		// expandido sería perder el orden que uno le dio.
		if (N.Widget.IsValid() && N.Widget->IsCompacto())
		{
			J->SetBoolField(TEXT("compact"), true);
		}
		NodesObj->SetObjectField(N.Id, J);
	}
	Root->SetObjectField(TEXT("nodes"), NodesObj);

	TArray<TSharedPtr<FJsonValue>> EdgesArr;
	for (const FGEdge& E : Edges)
	{
		if (Solo != nullptr && (!Solo->Contains(E.From) || !Solo->Contains(E.To)))
		{
			continue;   // cable con una punta afuera del recorte: no viaja
		}
		// [from, from_pin, to, to_pin] — conexión por pin (jam.flow lo entiende; también acepta [from,to]).
		TArray<TSharedPtr<FJsonValue>> Quad;
		Quad.Add(MakeShared<FJsonValueString>(E.From));
		Quad.Add(MakeShared<FJsonValueString>(E.FromPin));
		Quad.Add(MakeShared<FJsonValueString>(E.To));
		Quad.Add(MakeShared<FJsonValueString>(E.ToPin));
		EdgesArr.Add(MakeShared<FJsonValueArray>(Quad));
	}
	Root->SetArrayField(TEXT("edges"), EdgesArr);

	// Puntos de paso: clave PROPIA y no dentro de la arista, porque `JamGraph.from_json` acepta
	// aristas de 2 o 4 elementos y descartaría en silencio una de 5. Como clave, el índice de la
	// arista dentro de "edges" — el mismo orden que se acaba de escribir.
	TSharedRef<FJsonObject> ViasObj = MakeShared<FJsonObject>();
	{
		int32 Indice = 0;
		for (const FGEdge& E : Edges)
		{
			if (Solo != nullptr && (!Solo->Contains(E.From) || !Solo->Contains(E.To)))
			{
				continue;   // no viajó la arista: tampoco sus vías
			}
			if (E.Vias.Num() > 0)
			{
				TArray<TSharedPtr<FJsonValue>> Puntos;
				for (const FVector2D& V : E.Vias)
				{
					TArray<TSharedPtr<FJsonValue>> XY;
					XY.Add(MakeShared<FJsonValueNumber>(V.X));
					XY.Add(MakeShared<FJsonValueNumber>(V.Y));
					Puntos.Add(MakeShared<FJsonValueArray>(XY));
				}
				ViasObj->SetArrayField(FString::FromInt(Indice), Puntos);
			}
			++Indice;
		}
	}
	Root->SetObjectField(TEXT("reroutes"), ViasObj);

	// Cajas de comentario/grupo (Fase 7.1): mismo shape que "nodes", campo opcional — un .jamgraph
	// viejo sin esta clave carga igual (ver LoadGraphJson).
	TSharedRef<FJsonObject> CommentsObj = MakeShared<FJsonObject>();
	for (const FGComment& C : Comments)
	{
		if (SoloComentarios != nullptr && !SoloComentarios->Contains(C.Id))
		{
			continue;
		}
		const FLinearColor Col = C.Widget.IsValid() ? C.Widget->GetColor() : C.Color;
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetStringField(TEXT("title"), C.Widget.IsValid() ? C.Widget->GetTitle() : C.Title);
		J->SetNumberField(TEXT("x"), C.Pos.X);
		J->SetNumberField(TEXT("y"), C.Pos.Y);
		J->SetNumberField(TEXT("w"), C.Size.X);
		J->SetNumberField(TEXT("h"), C.Size.Y);
		TArray<TSharedPtr<FJsonValue>> ColorArr;
		ColorArr.Add(MakeShared<FJsonValueNumber>(Col.R));
		ColorArr.Add(MakeShared<FJsonValueNumber>(Col.G));
		ColorArr.Add(MakeShared<FJsonValueNumber>(Col.B));
		J->SetArrayField(TEXT("color"), ColorArr);
		CommentsObj->SetObjectField(C.Id, J);
	}
	Root->SetObjectField(TEXT("comments"), CommentsObj);

	FString Json;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	FJsonSerializer::Serialize(Root, Writer);
	return Json;
}

void SJamGraphEditor::ValidateGraph()
{
	if (Nodes.Num() == 0)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("Empty", "grafo vacío — agregá nodos.")); }
		return;
	}
	const FString Json = BuildJson();
	const FString Result = OnCompileGraph.IsBound()
		? OnCompileGraph.Execute(Json) : FString(TEXT("(sin compilador)"));
	ApplyGraphResult(Result);
}

void SJamGraphEditor::RunGraph()
{
	if (Nodes.Num() == 0)
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("Empty", "grafo vacío — agregá nodos.")); }
		return;
	}
	const FString Json = BuildJson();
	const FString Result = OnRunGraph.IsBound() ? OnRunGraph.Execute(Json) : FString(TEXT("(sin runner)"));
	ApplyGraphResult(Result);
	// El inspector mira la última corrida: sin esto habría que apretar «actualizar» a mano después
	// de cada Run, y lo que muestra sería del Run ANTERIOR — el peor error posible en un inspector.
	RefreshInspector();
	// Y cada nodo muestra lo que produjo, como en Substance Designer.
	RefrescarMiniaturas();
}

void SJamGraphEditor::SoloVerNodo(const FString& Id)
{
	// El nodo ya se prendió o apagó solo; acá se resuelve lo que es de alcance global.
	const FGNode* Marcado = nullptr;
	for (const FGNode& N : Nodes)
	{
		if (N.Id == Id && N.Widget.IsValid() && N.Widget->IsDebugEnabled())
		{
			Marcado = &N;
			break;
		}
	}
	if (Marcado)
	{
		// El display flag de Houdini se MUEVE: prender uno apaga el anterior. Acumularlos haría que
		// «ver sólo esto» significara «ver esto y aquello», que es justamente lo que no se quería.
		for (FGNode& N : Nodes)
		{
			if (N.Id != Id && N.Widget.IsValid())
			{
				N.Widget->SetDebugEnabled(false);
			}
		}
	}
	Marcar();
	// Mover el flag cambia QUÉ nodos corren, así que es un cambio de resultado y no sólo de vista.
	PedirRecoccion();
}

void SJamGraphEditor::AlternarLiveView()
{
	bLiveView = !bLiveView;
	if (bLiveView)
	{
		// Cocinar de una al prender: si no, el live view queda «prendido» mostrando el resultado
		// viejo hasta que alguien toque algo, y no habría forma de distinguirlo de que no anda.
		PedirRecoccion();
	}
	else if (Output.IsValid())
	{
		Output->SetText(LOCTEXT("LiveOff",
			"live view apagado — el grafo vuelve a correr sólo con Run."));
	}
}

void SJamGraphEditor::PedirRecoccion()
{
	if (!bLiveView || Nodes.Num() == 0)
	{
		return;
	}
	bRecoccionPendiente = true;
	// Un temporizador y no uno por aviso: durante un arrastre esto entra decenas de veces por
	// segundo, y registrar uno cada vez dejaría todos latiendo en paralelo contra el mismo grafo.
	if (!TemporizadorLive.IsValid())
	{
		TemporizadorLive = RegisterActiveTimer(LiveDebounceSegundos,
			FWidgetActiveTimerDelegate::CreateSP(this, &SJamGraphEditor::CocinarSiHayPendiente));
	}
}

EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente(const double, const float)
{
	if (!bRecoccionPendiente || !bLiveView)
	{
		// Nada que hacer: se apaga y suelta el handle. La próxima petición registra uno nuevo.
		TemporizadorLive.Reset();
		return EActiveTimerReturnType::Stop;
	}
	// Se baja la bandera ANTES de cocinar: lo que llegue mientras corre el grafo tiene que quedar
	// anotado para la vuelta siguiente. Bajarla después se comería ese aviso y el live view se
	// quedaría mostrando el penúltimo valor del arrastre.
	bRecoccionPendiente = false;
	RunGraph();
	return EActiveTimerReturnType::Continue;
}

void SJamGraphEditor::BakePreview()
{
	const FString Result = OnBakePreview.IsBound()
		? OnBakePreview.Execute() : FString(TEXT("(sin acción Bake)"));
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Result));
	}
}

void SJamGraphEditor::DiscardPreview()
{
	const FString Result = OnDiscardPreview.IsBound()
		? OnDiscardPreview.Execute() : FString(TEXT("(sin acción Discard)"));
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Result));
	}
}

void SJamGraphEditor::ApplyGraphResult(const FString& Result)
{

	// El runner devuelve {report, nodes:{nid:{estado,texto}}}: el reporte va al log y CADA NODO se
	// pinta con su veredicto del oráculo (verde ✓ / naranja REVISAR / rojo error), como los estados
	// de Grasshopper. Si no parsea (versión vieja), se muestra el texto tal cual.
	FString Report = Result;
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Result);
	if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())
	{
		Root->TryGetStringField(TEXT("report"), Report);
		const TSharedPtr<FJsonObject>* NodesObj = nullptr;
		if (Root->TryGetObjectField(TEXT("nodes"), NodesObj) && NodesObj)
		{
			for (FGNode& N : Nodes)
			{
				const TSharedPtr<FJsonObject>* R = nullptr;
				if (N.Widget.IsValid() && (*NodesObj)->TryGetObjectField(N.Id, R) && R)
				{
					N.Widget->SetResult((*R)->GetStringField(TEXT("estado")),
						(*R)->GetStringField(TEXT("texto")));
				}
			}
		}
	}
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(Report));
	}
}


// ---- buscador de nodos (doble clic en el canvas) + pan, como el canvas de Grasshopper ----

void SJamGraphEditor::OpenSearch(const FVector2D& AtCanvas)
{
	SearchAt = AtCanvas;
	bSearchOpen = true;
	if (SearchField.IsValid())
	{
		SearchField->SetText(FText::GetEmpty());
		FSlateApplication::Get().SetKeyboardFocus(SearchField, EFocusCause::SetDirectly);
	}
	RebuildSearchResults(FString());
}

void SJamGraphEditor::CloseSearch()
{
	bSearchOpen = false;
	SearchHits.Reset();
}

void SJamGraphEditor::RebuildSearchResults(const FString& Query)
{
	SearchHits.Reset();
	if (!SearchResults.IsValid())
	{
		return;
	}
	SearchResults->ClearChildren();

	const FString Q = Query.TrimStartAndEnd();
	for (const FJamTool& T : Tools)
	{
		if (!Q.IsEmpty() && !T.Verb.Contains(Q) && !T.Doc.Contains(Q))
		{
			continue;
		}
		SearchHits.Add(T.Verb);
		const FString Verb = T.Verb;
		const FVector2D At = SearchAt;
		SearchResults->AddSlot().AutoHeight().Padding(0.0f, 1.0f)
		[
			SNew(SButton)
			.HAlign(HAlign_Left)
			.Text(FText::FromString(FString::Printf(TEXT("%s  —  %s"), *T.Verb, *T.Doc)))
			.OnClicked_Lambda([this, Verb, At]()
			{
				const FVector2D Local = LocalToModel(At);   // el nodo vive en coords del modelo
				AddNode(Verb, &Local);
				CloseSearch();
				return FReply::Handled();
			})
		];
		if (SearchHits.Num() >= 8)
		{
			break;
		}
	}
}

void SJamGraphEditor::CommitSearch()
{
	if (SearchHits.Num() > 0)
	{
		const FVector2D Local = LocalToModel(SearchAt);
		AddNode(SearchHits[0], &Local);
	}
	CloseSearch();
}

FReply SJamGraphEditor::OnMouseButtonDoubleClick(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		// El popup es hijo del overlay del CANVAS, no del editor completo. Usar MyGeometry sumaba al Y
		// la altura de menú+ribbon (~50 px), igual que el antiguo bug del cable fantasma. WireLayer llena
		// ese mismo overlay y por eso es la referencia correcta incluso con DPI o alturas distintas.
		const FVector2D AtCanvas = WireLayer.IsValid()
			? WireLayer->GetCachedGeometry().AbsoluteToLocal(MouseEvent.GetScreenSpacePosition())
			: MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
		// Primero el cable. Con Ctrl, un NODO reroute (se selecciona, se mueve con el grupo,
		// sobrevive a copiar/pegar); sin Ctrl, una vía, que es más liviana. Sólo si no había cable
		// ahí se abre el buscador, que es el gesto del canvas VACÍO.
		if (MouseEvent.IsControlDown())
		{
			if (InsertarRerouteEnCable(AtCanvas))
			{
				return FReply::Handled();
			}
		}
		else if (AlternarViaEnCable(AtCanvas))
		{
			return FReply::Handled();
		}
		OpenSearch(AtCanvas);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

void SJamGraphEditor::ApplyZoom()
{
	if (Canvas.IsValid())
	{
		Canvas->SetRenderTransformPivot(FVector2D::ZeroVector);
		Canvas->SetRenderTransform(FSlateRenderTransform(FScale2D(Zoom, Zoom)));
	}
	if (CommentCanvas.IsValid())
	{
		// Mismo transform que Canvas: cada slot de comentario sólo maneja Pos + PanOffset, sin
		// multiplicar por zoom a mano, igual que los nodos.
		CommentCanvas->SetRenderTransformPivot(FVector2D::ZeroVector);
		CommentCanvas->SetRenderTransform(FSlateRenderTransform(FScale2D(Zoom, Zoom)));
	}
}

FReply SJamGraphEditor::OnMouseWheel(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	// ZUI: la rueda acerca/aleja el lienzo entero (nodos y wires), como en Grasshopper.
	const float Antes = Zoom;
	Zoom = FMath::Clamp(Zoom * (1.0f + MouseEvent.GetWheelDelta() * 0.1f), 0.35f, 2.5f);
	if (FMath::IsNearlyEqual(Antes, Zoom))
	{
		return FReply::Handled();
	}
	// zoom "hacia el cursor": el punto del modelo bajo el mouse se queda donde está
	const FVector2D Local = MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
	PanOffset += Local / Zoom - Local / Antes;
	ApplyZoom();
	return FReply::Handled();
}

FReply SJamGraphEditor::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton
		|| MouseEvent.GetEffectingButton() == EKeys::MiddleMouseButton)
	{
		// El derecho cancela la conexión en curso en vez de panear — es la convención de todo editor
		// nodal, y el pan sigue disponible con el del medio (o soltando el cable primero). El del
		// medio NO cancela: es sólo pan, y cancelar con él sorprendería a mitad de un desplazamiento.
		if (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton && CancelarConexion())
		{
			return FReply::Handled();
		}
		bPanning = true;
		return FReply::Handled().CaptureMouse(SharedThis(this));
	}
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton && bSearchOpen)
	{
		CloseSearch();   // clic afuera cierra el buscador
		return FReply::Handled().SetUserFocus(SharedThis(this), EFocusCause::Mouse);
	}
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		// Arrastrar sobre el FONDO abre el cuadro de selección. Los nodos manejan su propio clic,
		// así que si el evento llegó hasta acá es porque el punto está vacío.
		if (WireLayer.IsValid())
		{
			const FGeometry& Lienzo = WireLayer->GetCachedGeometry();
			const FVector2D Local = Lienzo.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
			const FVector2D Tam = Lienzo.GetLocalSize();
			// Un punto de paso bajo el cursor se arrastra ÉL, no abre un marquee: es lo único
			// agarrable que vive en el fondo del canvas, así que va antes en la cadena.
			if (ViaBajoElCursor(Local, ArrastrandoAristaVia, ArrastrandoVia))
			{
				return FReply::Handled()
					.CaptureMouse(SharedThis(this))
					.SetUserFocus(SharedThis(this), EFocusCause::Mouse);
			}
			// Sólo dentro del lienzo: un clic en el menú o en el ribbon no puede abrir un marquee.
			if (Local.X >= 0.0f && Local.Y >= 0.0f && Local.X <= Tam.X && Local.Y <= Tam.Y)
			{
				bMarquee = true;
				MarqueeA = MarqueeB = LocalToModel(Local);
				bMarqueeAgrega = MouseEvent.IsShiftDown() || MouseEvent.IsControlDown();
				MarqueeBase = bMarqueeAgrega ? SelectedNodeIds : TSet<FString>();
				if (!bMarqueeAgrega) { ClearSelection(); }
				return FReply::Handled()
					.CaptureMouse(SharedThis(this))
					.SetUserFocus(SharedThis(this), EFocusCause::Mouse);
			}
		}
		// El fondo recibe foco para deseleccionar el nodo anterior; Supr ya no puede borrar un nodo
		// después de que el usuario hizo clic en un espacio vacío del canvas.
		return FReply::Handled().SetUserFocus(SharedThis(this), EFocusCause::Mouse);
	}
	return FReply::Unhandled();
}

FReply SJamGraphEditor::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
	const FKey Tecla = InKeyEvent.GetKey();
	// Ctrl+Z / Ctrl+Shift+Z. Si el foco está en un campo de texto, el campo se los queda primero
	// (tiene su propio deshacer) y el evento nunca llega acá — que es lo correcto.
	if (Tecla == EKeys::Z && InKeyEvent.IsControlDown())
	{
		if (InKeyEvent.IsShiftDown()) { Rehacer(); } else { Deshacer(); }
		return FReply::Handled();
	}
	if (Tecla == EKeys::Y && InKeyEvent.IsControlDown())
	{
		Rehacer();   // el otro Rehacer que tiene todo el mundo en el dedo
		return FReply::Handled();
	}
	if (Tecla == EKeys::C && InKeyEvent.IsControlDown())
	{
		Copiar(/*bCortar*/ false);
		return FReply::Handled();
	}
	if (Tecla == EKeys::X && InKeyEvent.IsControlDown())
	{
		Copiar(/*bCortar*/ true);
		return FReply::Handled();
	}
	if (Tecla == EKeys::V && InKeyEvent.IsControlDown())
	{
		Pegar();
		return FReply::Handled();
	}
	if (Tecla == EKeys::D && InKeyEvent.IsControlDown())
	{
		Duplicar();
		return FReply::Handled();
	}
	if (Tecla == EKeys::G && InKeyEvent.IsControlDown())
	{
		ColapsarSeleccion();
		return FReply::Handled();
	}
	if (Tecla == EKeys::F && !InKeyEvent.IsControlDown())
	{
		Encuadrar(/*bSoloSeleccion*/ true);
		return FReply::Handled();
	}
	if (Tecla == EKeys::C && !InKeyEvent.IsControlDown())
	{
		CreateCommentFromSelection();
		return FReply::Handled();
	}
	if (Tecla == EKeys::D && !InKeyEvent.IsControlDown())
	{
		AlternarBypassDeLaSeleccion();
		return FReply::Handled();
	}
	if (Tecla == EKeys::L && !InKeyEvent.IsControlDown())
	{
		AcomodarSeleccion(TEXT("auto"));
		return FReply::Handled();
	}
	if (Tecla == EKeys::Home)
	{
		Encuadrar(/*bSoloSeleccion*/ false);
		return FReply::Handled();
	}
	if (Tecla == EKeys::A && InKeyEvent.IsControlDown())
	{
		SelectAll();
		return FReply::Handled();
	}
	if (Tecla == EKeys::Escape)
	{
		// Un cable a medias se suelta ANTES que la selección: es un gesto EN CURSO, y lo que Esc
		// cancela siempre es lo que está pasando ahora. Sin esto no había ninguna forma de
		// arrepentirse de haber armado una conexión — el cable-fantasma seguía al cursor para
		// siempre hasta acertarle a un pin válido.
		if (!CancelarConexion())
		{
			ClearSelection();
		}
		return FReply::Handled();
	}
	if (Tecla == EKeys::Delete && (SelectedNodeIds.Num() > 0 || SelectedCommentIds.Num() > 0))
	{
		DeleteSelection();
		return FReply::Handled();
	}
	return SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
}

FReply SJamGraphEditor::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	// La geometría recibida es la del editor completo (incluye menú + ribbon), pero el cable-fantasma
	// se pinta en la capa del lienzo. Convertir desde pantalla contra ESA capa evita sumar al extremo
	// del wire la altura de la cabecera y mantiene cursor/cable alineados con cualquier DPI.
	if (WireLayer.IsValid())
	{
		LastMousePos = WireLayer->GetCachedGeometry().AbsoluteToLocal(
			MouseEvent.GetScreenSpacePosition());
	}
	if (!PendingSource.IsEmpty() && WireLayer.IsValid())
	{
		// hay una conexión en curso: repintar la capa de wires para que el cable siga al mouse.
		WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
	}
	if (ArrastrandoAristaVia >= 0 && HasMouseCapture() && WireLayer.IsValid())
	{
		const FVector2D Local = WireLayer->GetCachedGeometry().AbsoluteToLocal(
			MouseEvent.GetScreenSpacePosition());
		if (Edges.IsValidIndex(ArrastrandoAristaVia)
			&& Edges[ArrastrandoAristaVia].Vias.IsValidIndex(ArrastrandoVia))
		{
			// En vivo y sin Marcar(): un arrastre es UN paso, y se registra al soltar.
			Edges[ArrastrandoAristaVia].Vias[ArrastrandoVia] = LocalToModel(Local);
			WireLayer->Invalidate(EInvalidateWidgetReason::Paint);
		}
		return FReply::Handled();
	}
	if (bMarquee && HasMouseCapture() && WireLayer.IsValid())
	{
		MarqueeB = LocalToModel(
			WireLayer->GetCachedGeometry().AbsoluteToLocal(MouseEvent.GetScreenSpacePosition()));
		if (MarqueeLayer.IsValid())
		{
			MarqueeLayer->Invalidate(EInvalidateWidgetReason::Paint);
		}
		return FReply::Handled();
	}
	if (bPanning && HasMouseCapture())
	{
		const float S = MyGeometry.GetAccumulatedLayoutTransform().GetScale();
		PanOffset += MouseEvent.GetCursorDelta() / ((S > 0.0f ? S : 1.0f) * Zoom);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SJamGraphEditor::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bPanning && (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton
		|| MouseEvent.GetEffectingButton() == EKeys::MiddleMouseButton))
	{
		bPanning = false;
		return FReply::Handled().ReleaseMouseCapture();
	}
	if (ArrastrandoAristaVia >= 0 && MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		ArrastrandoAristaVia = -1;
		ArrastrandoVia = -1;
		Marcar();   // el arrastre entero es un paso, como el de un nodo
		return FReply::Handled().ReleaseMouseCapture();
	}
	if (bMarquee && MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bMarquee = false;
		// Cruzar alcanza: si el cuadro TOCA el nodo, entra. Exigir contención completa obliga a
		// arrastrar por fuera de todo. Es la misma regla que `jam.layout.en_marco`, donde está
		// testeada; acá se aplica sobre los rectángulos vivos del canvas.
		const FVector2D Min(FMath::Min(MarqueeA.X, MarqueeB.X), FMath::Min(MarqueeA.Y, MarqueeB.Y));
		const FVector2D Max(FMath::Max(MarqueeA.X, MarqueeB.X), FMath::Max(MarqueeA.Y, MarqueeB.Y));
		SelectedNodeIds = MarqueeBase;
		// Área cero (un clic sin arrastrar) no toca nada: por eso el clic en el fondo LIMPIA en vez
		// de agarrar lo que hubiera abajo del cursor.
		for (const FString& Id : NodeIdsTouchingRect(Min, Max))
		{
			SelectedNodeIds.Add(Id);
		}
		MarqueeBase.Reset();
		return FReply::Handled().ReleaseMouseCapture();
	}
	return FReply::Unhandled();
}

// ---- menú principal estilo Grasshopper ----

void SJamGraphEditor::FillFileMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("New", "Nuevo"), LOCTEXT("NewTip", "Vaciar el grafo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::NewGraph)));
	MB.AddMenuEntry(LOCTEXT("Open", "Abrir diagrama…"), LOCTEXT("OpenTip", "Cargar un .jamgraph"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::OpenDiagram)));
	// Los ejemplos vivían acá, como cinco «Abrir ejemplo: …». Están en el tab «Aprender», que es un
	// lugar donde alguien que recién empieza los va a encontrar sin abrir un menú.
	MB.AddMenuSeparator();
	// Por lambda y no por `CreateSP(..., &SaveDiagram, bool)`: `SaveDiagram` devuelve si el archivo
	// quedó escrito (lo necesita `ConfirmarCierre`) y `FExecuteAction` es void.
	MB.AddMenuEntry(LOCTEXT("Save", "Guardar"), LOCTEXT("SaveTip", "Guardar en el archivo actual"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateLambda([this]() { SaveDiagram(/*bForceDialog*/ false); })));
	MB.AddMenuEntry(LOCTEXT("SaveAs", "Guardar como…"), LOCTEXT("SaveAsTip", "Elegir archivo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateLambda([this]() { SaveDiagram(/*bForceDialog*/ true); })));
}

void SJamGraphEditor::FillEditMenu(FMenuBuilder& MB)
{
	MB.BeginSection(TEXT("Historial"), LOCTEXT("SectionHistory", "Historial"));
	MB.AddMenuEntry(LOCTEXT("Undo", "Deshacer\tCtrl+Z"),
		LOCTEXT("UndoTip", "Vuelve al estado anterior del grafo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::Deshacer),
			FCanExecuteAction::CreateSP(this, &SJamGraphEditor::PuedeDeshacer)));
	MB.AddMenuEntry(LOCTEXT("Redo", "Rehacer\tCtrl+Shift+Z"),
		LOCTEXT("RedoTip", "Vuelve a aplicar lo último que deshiciste"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::Rehacer),
			FCanExecuteAction::CreateSP(this, &SJamGraphEditor::PuedeRehacer)));
	MB.EndSection();

	MB.AddMenuEntry(LOCTEXT("ClearAll", "Vaciar el grafo"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::NewGraph)));

	MB.BeginSection(TEXT("Portapapeles"), LOCTEXT("SectionClip", "Portapapeles"));
	{
		// Todas piden 2+… no: piden AL MENOS UNO elegido (nodo O caja). Pegar es la excepción, siempre
		// se puede intentar (el portapapeles puede venir de otra ventana de Graph). Colapsar a función
		// es sólo de NODOS: una caja no se colapsa, viaja con lo que contenga.
		const FCanExecuteAction HayAlgo = FCanExecuteAction::CreateLambda(
			[this]() { return SelectedNodeIds.Num() > 0 || SelectedCommentIds.Num() > 0; });
		const FCanExecuteAction HayNodos = FCanExecuteAction::CreateLambda(
			[this]() { return SelectedNodeIds.Num() > 0; });
		MB.AddMenuEntry(LOCTEXT("Copy", "Copiar\tCtrl+C"),
			LOCTEXT("CopyTip", "Copia lo elegido como JSON al portapapeles del sistema"),
			FSlateIcon(), FUIAction(FExecuteAction::CreateLambda(
				[this]() { Copiar(false); }), HayAlgo));
		MB.AddMenuEntry(LOCTEXT("Cut", "Cortar\tCtrl+X"), FText::GetEmpty(), FSlateIcon(),
			FUIAction(FExecuteAction::CreateLambda([this]() { Copiar(true); }), HayAlgo));
		MB.AddMenuEntry(LOCTEXT("Paste", "Pegar\tCtrl+V"),
			LOCTEXT("PasteTip", "Pega nodos copiados acá o en otra ventana de Graph"), FSlateIcon(),
			FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::Pegar)));
		MB.AddMenuEntry(LOCTEXT("Duplicate", "Duplicar\tCtrl+D"),
			LOCTEXT("DuplicateTip", "Copia y pega sin tocar el portapapeles"), FSlateIcon(),
			FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::Duplicar), HayAlgo));
		MB.AddMenuEntry(LOCTEXT("CollapseFunction", "Colapsar a función\tCtrl+G"),
			LOCTEXT("CollapseFunctionTip", "Guarda lo elegido como función y lo reemplaza por una instancia"),
			FSlateIcon(), FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::ColapsarSeleccion), HayNodos));
	}
	MB.EndSection();

	MB.BeginSection(TEXT("Comentarios"), LOCTEXT("SectionComments", "Comentarios"));
	MB.AddMenuEntry(LOCTEXT("CreateComment", "Comentario\tC"),
		LOCTEXT("CreateCommentTip", "Encierra los nodos elegidos en una caja de comentario/grupo"),
		FSlateIcon(), FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::CreateCommentFromSelection),
			FCanExecuteAction::CreateLambda([this]() { return SelectedNodeIds.Num() > 0; })));
	MB.EndSection();

	MB.BeginSection(TEXT("Seleccion"), LOCTEXT("SectionSelect", "Selección"));
	MB.AddMenuEntry(LOCTEXT("SelectAll", "Seleccionar todo\tCtrl+A"),
		LOCTEXT("SelectAllTip", "Elige todos los nodos del grafo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::SelectAll)));
	MB.AddMenuEntry(LOCTEXT("SelectNone", "No seleccionar nada\tEsc"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::ClearSelection)));
	MB.AddMenuEntry(LOCTEXT("DeleteSel", "Borrar la selección\tSupr"),
		LOCTEXT("DeleteSelTip", "Borra los nodos elegidos y sus cables"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::DeleteSelection)));
	MB.AddMenuEntry(LOCTEXT("Bypass", "Apagar / prender\tD"),
		LOCTEXT("BypassTip",
			"El nodo sigue cableado pero no corre: el stream lo atraviesa. Sólo en los verbos que "
			"reciben y producen el mismo tipo"),
		FSlateIcon(), FUIAction(
			FExecuteAction::CreateSP(this, &SJamGraphEditor::AlternarBypassDeLaSeleccion),
			FCanExecuteAction::CreateLambda([this]() { return SelectedNodeIds.Num() > 0; })));
	MB.EndSection();

	// Alinear y distribuir: las posiciones las decide `jam.layout` (puro y testeado). Requieren 2+
	// nodos elegidos; con menos, la acción no hace nada porque no hay contra qué alinear.
	MB.BeginSection(TEXT("Acomodar"), LOCTEXT("SectionAlign", "Alinear y distribuir"));
	// Auto-layout no pide 2+ elegidos: sin selección acomoda el grafo entero, que es el caso
	// habitual («ordename esto»).
	MB.AddMenuEntry(LOCTEXT("AutoLayout", "Acomodar el grafo\tL"),
		LOCTEXT("AutoLayoutTip",
			"Ordena por capas de izquierda a derecha: cada nodo a la derecha de lo que lo alimenta. "
			"Sin selección acomoda todo; con selección, sólo esa parte"),
		FSlateIcon(), FUIAction(FExecuteAction::CreateLambda(
			[this]() { AcomodarSeleccion(TEXT("auto")); })));
	MB.AddMenuEntry(LOCTEXT("SnapGrid", "Ajustar a la grilla"),
		LOCTEXT("SnapGridTip",
			"Lleva cada nodo al cruce de grilla más cercano. Sin selección ajusta todo el grafo"),
		FSlateIcon(), FUIAction(FExecuteAction::CreateLambda(
			[this]() { AcomodarSeleccion(TEXT("snap")); })));
	MB.AddMenuSeparator();
	auto Entrada = [&MB, this](const TCHAR* Etiqueta, const TCHAR* Tip, const TCHAR* Accion)
	{
		const FString A(Accion);
		MB.AddMenuEntry(FText::FromString(Etiqueta), FText::FromString(Tip), FSlateIcon(),
			FUIAction(
				FExecuteAction::CreateLambda([this, A]() { AcomodarSeleccion(A); }),
				FCanExecuteAction::CreateLambda([this]() { return SelectedNodeIds.Num() >= 2; })));
	};
	Entrada(TEXT("Alinear a la izquierda"),
		TEXT("Todos al borde izquierdo del cuadro que los envuelve"), TEXT("izquierda"));
	Entrada(TEXT("Alinear a la derecha"),
		TEXT("Alinea el borde DERECHO, no la x"), TEXT("derecha"));
	Entrada(TEXT("Alinear arriba"), TEXT("Todos al borde superior"), TEXT("arriba"));
	Entrada(TEXT("Alinear abajo"),
		TEXT("Alinea el borde INFERIOR — los nodos con más params son más altos"), TEXT("abajo"));
	Entrada(TEXT("Centrar en columna"), TEXT("Centros alineados en X"), TEXT("centro-x"));
	Entrada(TEXT("Centrar en fila"), TEXT("Centros alineados en Y"), TEXT("centro-y"));
	Entrada(TEXT("Distribuir en horizontal"),
		TEXT("Mismo hueco entre uno y el siguiente; los extremos no se mueven"), TEXT("dist-x"));
	Entrada(TEXT("Distribuir en vertical"),
		TEXT("Mismo hueco entre uno y el siguiente; los extremos no se mueven"), TEXT("dist-y"));
	MB.EndSection();
}

void SJamGraphEditor::FillViewMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("FrameSelected", "Encuadrar la selección\tF"),
		LOCTEXT("FrameSelectedTip", "Lleva la vista a lo elegido (o a todo, si no hay nada elegido)"),
		FSlateIcon(), FUIAction(FExecuteAction::CreateLambda([this]() { Encuadrar(true); })));
	MB.AddMenuEntry(LOCTEXT("FrameAll", "Encuadrar todo\tInicio"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateLambda([this]() { Encuadrar(false); })));
	MB.AddMenuEntry(LOCTEXT("ResetView", "Reencuadrar (reset zoom/pan)"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::ResetView)));
}

void SJamGraphEditor::FillDisplayMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("Gallery", "Galería: insertar todos los nodos"),
		LOCTEXT("GalleryTip", "Reemplaza el grafo por UNO DE CADA nodo en grilla (para un screenshot)"),
		FSlateIcon(), FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::InsertAllNodes)));
}

void SJamGraphEditor::FillSolutionMenu(FMenuBuilder& MB)
{
	MB.AddMenuEntry(LOCTEXT("CompileGraph", "Compile / Validate"),
		LOCTEXT("CompileGraphTip", "Valida todo el grafo sin ejecutar ni modificar la escena"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::ValidateGraph)));
	MB.AddMenuEntry(LOCTEXT("Recompute", "Run graph (recompute)"), FText::GetEmpty(), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::RunGraph)));
	MB.AddMenuEntry(LOCTEXT("LiveViewMenu", "Live view (recocinar al arrastrar)"),
		LOCTEXT("LiveViewMenuTip",
			"Recocina el grafo mientras movés un slider, sin apretar Run. Se marca cuando está "
			"prendido; conviene con «Ver sin hornear» al final de la cadena."),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::AlternarLiveView),
			FCanExecuteAction(),
			FIsActionChecked::CreateSP(this, &SJamGraphEditor::EstaLiveView)),
		NAME_None, EUserInterfaceActionType::ToggleButton);
	MB.AddMenuSeparator();
	MB.AddMenuEntry(LOCTEXT("BakeGraphPreview", "Bake / Confirm Preview"),
		LOCTEXT("BakeGraphPreviewTip", "Fija el Preview creado por este Graph"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::BakePreview)));
	MB.AddMenuEntry(LOCTEXT("DiscardGraphPreview", "Discard Preview"),
		LOCTEXT("DiscardGraphPreviewTip", "Elimina el Preview creado por este Graph"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::DiscardPreview)));
}

void SJamGraphEditor::NewGraph()
{
	if (Canvas.IsValid())
	{
		for (const FGNode& N : Nodes)
		{
			if (N.Widget.IsValid())
			{
				Canvas->RemoveSlot(N.Widget.ToSharedRef());
			}
		}
	}
	if (CommentCanvas.IsValid())
	{
		for (const FGComment& C : Comments)
		{
			if (C.Widget.IsValid())
			{
				CommentCanvas->RemoveSlot(C.Widget.ToSharedRef());
			}
		}
	}
	// Los nodos se van: sus miniaturas también, o quedarían brushes vivos apuntando a widgets muertos.
	SoltarMiniaturas();
	Nodes.Reset();
	Edges.Reset();
	Comments.Reset();
	SelectedNodeIds.Reset();
	SelectedCommentIds.Reset();
	CommentDragNodeIds.Reset();
	PendingSource.Empty();
	PendingSourcePin.Empty();
	NextId = 1;
	NextCommentId = 1;
	// `New` inicia un DOCUMENTO nuevo. Conservar esta ruta hacía que el Save siguiente sobrescribiera
	// silenciosamente el .jamgraph anterior.
	CurrentPath.Empty();
	FuncionEnEdicion.Reset();
	NombreFuncionEnEdicion.Reset();
	EstadoAntesDeEditarFuncion.Reset();
	if (Output.IsValid())
	{
		Output->SetText(LOCTEXT("NewDone", "grafo vacío."));
	}
	Marcar();   // vaciar el grafo también se deshace (queda callado cuando lo llama LoadGraphJson)
}

bool SJamGraphEditor::LoadGraphJson(const FString& Json, bool bConservarEdicionFuncion)
{
	// Si ya venimos callados es porque nos llamó Deshacer/Rehacer: ese viaje NO es un paso nuevo.
	// Abrir un diagrama o cargar un tutorial sí lo es, y se registra como UNO solo.
	const bool bRestaurando = bSinHistorial;
	auto Fail = [this](const FString& Message)
	{
		if (Output.IsValid()) { Output->SetText(FText::FromString(Message)); }
		return false;
	};

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return Fail(TEXT("el archivo no es JSON válido; el grafo actual no se modificó."));
	}
	double SchemaVersion = 1.0;
	if (Root->HasField(TEXT("schema_version"))
		&& !Root->TryGetNumberField(TEXT("schema_version"), SchemaVersion))
	{
		return Fail(TEXT("schema_version debe ser numérico; el grafo actual no se modificó."));
	}
	if (SchemaVersion > 1.0)
	{
		return Fail(FString::Printf(
			TEXT("schema_version %.0f no soportada (máxima: 1); el grafo actual no se modificó."),
			SchemaVersion));
	}

	struct FLoadedNode
	{
		FString FileId;
		FString Verb;
		FVector2D Pos;
		TMap<FString, FString> Params;
		bool bDebug = false;
		bool bBypass = false;
		bool bCompacto = false;
	};
	struct FLoadedEdge
	{
		FString From;
		FString FromPin;
		FString To;
		FString ToPin;
	};

	// Fase 1: validar y convertir TODO a un modelo temporal. Hasta completar esta fase no se llama a
	// NewGraph ni se toca CurrentPath, selección, zoom o widgets actuales.
	TArray<FLoadedNode> LoadedNodes;
	TMap<FString, int32> LoadedNodeIndex;
	const TSharedPtr<FJsonObject>* NodesObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("nodes"), NodesObj) || NodesObj == nullptr)
	{
		return Fail(TEXT("el diagrama no contiene un objeto 'nodes'; el grafo actual no se modificó."));
	}
	for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*NodesObj)->Values)
	{
		const TSharedPtr<FJsonObject> NO = KV.Value.IsValid() ? KV.Value->AsObject() : nullptr;
		if (!NO.IsValid())
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' no es un objeto JSON."), *KV.Key));
		}
		FString Verb;
		double X = 0.0, Y = 0.0;
		if (!NO->TryGetStringField(TEXT("verb"), Verb) || Verb.IsEmpty())
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' no declara un verbo válido."), *KV.Key));
		}
		const FJamTool* Tool = FindTool(Verb);
		if (Tool == nullptr)
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' usa el verbo desconocido '%s'."),
				*KV.Key, *Verb));
		}
		if (!NO->TryGetNumberField(TEXT("x"), X) || !NO->TryGetNumberField(TEXT("y"), Y))
		{
			return Fail(FString::Printf(TEXT("el nodo '%s' necesita posiciones x/y numéricas."), *KV.Key));
		}

		FLoadedNode Loaded{KV.Key, Verb, FVector2D(X, Y), {}};
		// El flag de debug es OPCIONAL: un .jamgraph viejo sin el campo carga con el flag apagado.
		NO->TryGetBoolField(TEXT("debug"), Loaded.bDebug);
		// Opcional igual que `debug`: un .jamgraph anterior al bypass carga con el flag apagado.
		NO->TryGetBoolField(TEXT("bypass"), Loaded.bBypass);
		NO->TryGetBoolField(TEXT("compact"), Loaded.bCompacto);
		const TSharedPtr<FJsonObject>* ParamsObj = nullptr;
		if (NO->HasField(TEXT("params"))
			&& (!NO->TryGetObjectField(TEXT("params"), ParamsObj) || ParamsObj == nullptr))
		{
			return Fail(FString::Printf(TEXT("params de '%s' debe ser un objeto."), *KV.Key));
		}
		if (ParamsObj != nullptr)
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>> PV : (*ParamsObj)->Values)
			{
				const bool bKnownParam = (PV.Key == TEXT("asset") && Tool->bAssetRow)
					|| Tool->Params.ContainsByPredicate(
						[&PV](const FJamParam& Param) { return Param.Name == PV.Key; });
				if (!bKnownParam)
				{
					return Fail(FString::Printf(TEXT("parámetro desconocido '%s' en nodo '%s'."),
						*PV.Key, *KV.Key));
				}
				FString Value;
				double Number = 0.0;
				bool Boolean = false;
				if (PV.Value.IsValid() && PV.Value->TryGetString(Value)) {}
				else if (PV.Value.IsValid() && PV.Value->TryGetNumber(Number))
				{
					Value = FString::Printf(TEXT("%.17g"), Number);
				}
				else if (PV.Value.IsValid() && PV.Value->TryGetBool(Boolean))
				{
					Value = Boolean ? TEXT("True") : TEXT("False");
				}
				else
				{
					return Fail(FString::Printf(
						TEXT("parámetro '%s' de '%s' debe ser string, número o booleano."),
						*PV.Key, *KV.Key));
				}
				Loaded.Params.Add(PV.Key, Value);
			}
		}
		LoadedNodeIndex.Add(KV.Key, LoadedNodes.Num());
		LoadedNodes.Add(MoveTemp(Loaded));
	}

	TArray<FLoadedEdge> LoadedEdges;
	const TArray<TSharedPtr<FJsonValue>>* EdgesArr = nullptr;
	if (Root->HasField(TEXT("edges"))
		&& (!Root->TryGetArrayField(TEXT("edges"), EdgesArr) || EdgesArr == nullptr))
	{
		return Fail(TEXT("'edges' debe ser un array; el grafo actual no se modificó."));
	}
	if (EdgesArr != nullptr)
	{
		TSet<FString> SeenEdges;
		TSet<FString> OccupiedInputs;
		for (int32 EdgeIndex = 0; EdgeIndex < EdgesArr->Num(); ++EdgeIndex)
		{
			const TSharedPtr<FJsonValue>& EV = (*EdgesArr)[EdgeIndex];
			const TArray<TSharedPtr<FJsonValue>>* E = nullptr;
			if (!EV.IsValid() || !EV->TryGetArray(E) || E == nullptr || (E->Num() != 2 && E->Num() != 4))
			{
				return Fail(FString::Printf(TEXT("edge %d debe tener 2 o 4 strings."), EdgeIndex));
			}
			FString From, FromPin = TEXT("out"), To, ToPin = TEXT("in");
			const bool bStrings = E->Num() == 2
				? (*E)[0]->TryGetString(From) && (*E)[1]->TryGetString(To)
				: (*E)[0]->TryGetString(From) && (*E)[1]->TryGetString(FromPin)
					&& (*E)[2]->TryGetString(To) && (*E)[3]->TryGetString(ToPin);
			if (!bStrings)
			{
				return Fail(FString::Printf(TEXT("edge %d contiene un endpoint no textual."), EdgeIndex));
			}
			const int32* FromIdx = LoadedNodeIndex.Find(From);
			const int32* ToIdx = LoadedNodeIndex.Find(To);
			if (FromIdx == nullptr || ToIdx == nullptr)
			{
				return Fail(FString::Printf(TEXT("edge %d referencia un nodo inexistente."), EdgeIndex));
			}
			const FJamTool* FromTool = FindTool(LoadedNodes[*FromIdx].Verb);
			const FJamTool* ToTool = FindTool(LoadedNodes[*ToIdx].Verb);
			FString OutType;
			if (FromTool)
			{
				if (const FJamTool::FPin* Pin = FromTool->OutputPins.FindByPredicate(
					[&FromPin](const FJamTool::FPin& P) { return P.Name == FromPin; }))
				{
					OutType = Pin->Type;
				}
				else if (FromPin == TEXT("out")) { OutType = FromTool->OutName; }
			}
			FString InType;
			if (ToTool)
			{
				if (const FJamTool::FPin* Pin = ToTool->InputPins.FindByPredicate(
					[&ToPin](const FJamTool::FPin& P) { return P.Name == ToPin; }))
				{
					InType = Pin->Type;
				}
			}
			if (InType.IsEmpty() && ToPin == TEXT("in") && ToTool && !ToTool->bSource && ToTool->Arity != 0)
			{
				InType = ToTool->InName;
			}
			else if (ToPin == TEXT("asset") && ToTool && ToTool->bAssetRow)
			{
				InType = TEXT("A");
			}
			else if (ToTool)
			{
				if (const FJamParam* Param = ToTool->Params.FindByPredicate(
					[&ToPin](const FJamParam& P) { return P.Name == ToPin; }))
				{
					InType = Param->DataType.IsEmpty()
						? JamParamDataType(Param->Name, Param->Type) : Param->DataType;
				}
			}
			const TArray<FString>* Extras = (ToPin == TEXT("in") && ToTool != nullptr)
				? &ToTool->InAccepts : nullptr;
			if (!JamTiposCompatibles(OutType, InType, Extras))
			{
				return Fail(FString::Printf(TEXT("edge %d tiene pines o tipos incompatibles."), EdgeIndex));
			}
			const FString EdgeKey = From + TEXT("\x1f") + FromPin + TEXT("\x1f") + To + TEXT("\x1f") + ToPin;
			if (SeenEdges.Contains(EdgeKey))
			{
				return Fail(FString::Printf(TEXT("edge %d está duplicado."), EdgeIndex));
			}
			SeenEdges.Add(EdgeKey);
			const bool bSingle = ToPin != TEXT("in") || ToTool == nullptr || ToTool->Arity != -1;
			const FString InputKey = To + TEXT("\x1f") + ToPin;
			if (bSingle && OccupiedInputs.Contains(InputKey))
			{
				return Fail(FString::Printf(TEXT("el pin %s.%s recibe más de un cable."), *To, *ToPin));
			}
			if (bSingle) { OccupiedInputs.Add(InputKey); }
			LoadedEdges.Add(FLoadedEdge{From, FromPin, To, ToPin});
		}
	}

	// Cajas de comentario/grupo (Fase 7.1): campo OPCIONAL. Un .jamgraph viejo sin "comments", o si
	// llegara mal formada, no rompe la carga — degrada en silencio, mismo trato que "debug" ausente.
	struct FLoadedComment
	{
		FString FileId;
		FString Title;
		FVector2D Pos;
		FVector2D Size;
		FLinearColor Color = FLinearColor(0.65f, 0.60f, 0.50f, 1.0f);
	};
	TArray<FLoadedComment> LoadedComments;
	const TSharedPtr<FJsonObject>* CommentsObj = nullptr;
	if (Root->TryGetObjectField(TEXT("comments"), CommentsObj) && CommentsObj != nullptr)
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*CommentsObj)->Values)
		{
			const TSharedPtr<FJsonObject> CO = KV.Value.IsValid() ? KV.Value->AsObject() : nullptr;
			double X = 0.0, Y = 0.0, W = 0.0, H = 0.0;
			FString Title;
			if (!CO.IsValid()
				|| !CO->TryGetNumberField(TEXT("x"), X) || !CO->TryGetNumberField(TEXT("y"), Y)
				|| !CO->TryGetNumberField(TEXT("w"), W) || !CO->TryGetNumberField(TEXT("h"), H))
			{
				continue;   // caja mal formada: se ignora, no aborta la carga del resto del grafo
			}
			CO->TryGetStringField(TEXT("title"), Title);
			FLoadedComment Loaded{KV.Key, Title, FVector2D(X, Y), FVector2D(W, H)};
			// "color" es OPCIONAL: un .jamgraph de antes de este color por caja carga con el neutro
			// de siempre — mismo trato que "debug" ausente en los nodos.
			const TArray<TSharedPtr<FJsonValue>>* ColorArr = nullptr;
			double R = 0.0, G = 0.0, B = 0.0;
			if (CO->TryGetArrayField(TEXT("color"), ColorArr) && ColorArr != nullptr && ColorArr->Num() == 3
				&& (*ColorArr)[0]->TryGetNumber(R) && (*ColorArr)[1]->TryGetNumber(G) && (*ColorArr)[2]->TryGetNumber(B))
			{
				Loaded.Color = FLinearColor(R, G, B);
			}
			LoadedComments.Add(Loaded);
		}
	}

	// Fase 2: el modelo completo es válido; recién ahora reemplazar el documento visible.
	// El silencio va en un BLOQUE propio: vaciar + crear N nodos + N wires es UN paso deshacible y no
	// 2N+1, pero el `Marcar()` tiene que quedar afuera. Con `TGuardValue` y no con un bool a mano,
	// porque acá adentro hay `return Fail(...)`: dejar la bandera prendida mataría el historial en
	// silencio para el resto de la sesión.
	{
		TGuardValue<bool> Callado(bSinHistorial, true);
		const FString FuncionActiva = FuncionEnEdicion;
		const FString NombreActivo = NombreFuncionEnEdicion;
		const FString EstadoRetorno = EstadoAntesDeEditarFuncion;
		NewGraph();
		if (bConservarEdicionFuncion)
		{
			FuncionEnEdicion = FuncionActiva;
			NombreFuncionEnEdicion = NombreActivo;
			EstadoAntesDeEditarFuncion = EstadoRetorno;
		}
		TMap<FString, FString> IdMap;
		for (const FLoadedNode& Loaded : LoadedNodes)
		{
			const FString NewId = AddNode(Loaded.Verb, &Loaded.Pos, Loaded.FileId);
			if (NewId.IsEmpty())
			{
				return Fail(FString::Printf(TEXT("no pude crear el nodo validado '%s'."), *Loaded.FileId));
			}
			IdMap.Add(Loaded.FileId, NewId);
			if (FGNode* Node = FindNode(NewId); Node && Node->Widget.IsValid())
			{
				Node->Widget->SetParamValues(Loaded.Params);
				Node->Widget->SetDebugEnabled(Loaded.bDebug);
				// `SetBypassed` ignora el flag si el verbo no lo admite (ver SJamGraphNode).
				Node->Widget->SetBypassed(Loaded.bBypass);
				Node->Widget->SetCompacto(Loaded.bCompacto);
				Node->Width = Loaded.bCompacto ? NodeWidthCompacto : NodeWidth;
			}
		}
		for (const FLoadedEdge& Loaded : LoadedEdges)
		{
			Edges.Add(FGEdge{IdMap[Loaded.From], Loaded.FromPin, IdMap[Loaded.To], Loaded.ToPin});
		}
		// Puntos de paso: OPCIONALES, con el índice de la arista como clave. Un .jamgraph anterior
		// al reroute no los trae, y una entrada mal formada se ignora — son decoración, no pueden
		// impedir que el grafo cargue.
		const TSharedPtr<FJsonObject>* ViasObj = nullptr;
		if (Root->TryGetObjectField(TEXT("reroutes"), ViasObj) && ViasObj != nullptr)
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>> KV : (*ViasObj)->Values)
			{
				const int32 Indice = FCString::Atoi(*KV.Key);
				const TArray<TSharedPtr<FJsonValue>>* Puntos = nullptr;
				if (!Edges.IsValidIndex(Indice) || !KV.Value.IsValid()
					|| !KV.Value->TryGetArray(Puntos) || Puntos == nullptr)
				{
					continue;
				}
				for (const TSharedPtr<FJsonValue>& PV : *Puntos)
				{
					const TArray<TSharedPtr<FJsonValue>>* XY = nullptr;
					if (PV.IsValid() && PV->TryGetArray(XY) && XY != nullptr && XY->Num() == 2)
					{
						Edges[Indice].Vias.Add(
							FVector2D((*XY)[0]->AsNumber(), (*XY)[1]->AsNumber()));
					}
				}
			}
		}
		RefreshCabledPins();   // reflejar en los inputs los cables recién cargados
		for (const FLoadedComment& Loaded : LoadedComments)
		{
			AddComment(Loaded.Pos, Loaded.Size, Loaded.Title, Loaded.FileId, Loaded.Color);
		}
	}
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(
			FString::Printf(TEXT("cargado: %d nodos, %d wires."), Nodes.Num(), Edges.Num())));
	}
	// `Anterior` todavía tiene el grafo de antes de abrir: es a donde vuelve Ctrl+Z.
	if (!bRestaurando)
	{
		Marcar();
	}
	return true;
}

bool SJamGraphEditor::SaveDiagram(bool bForceDialog)
{
	FString Path = CurrentPath;
	if (Path.IsEmpty() || bForceDialog)
	{
		IDesktopPlatform* DP = FDesktopPlatformModule::Get();
		if (DP == nullptr) { return false; }
		const FString Dir = FPaths::ProjectSavedDir() / TEXT("JamGraphs");
		IFileManager::Get().MakeDirectory(*Dir, true);
		TArray<FString> Files;
		const bool bOk = DP->SaveFileDialog(nullptr, TEXT("Guardar diagrama Jam"), Dir,
			TEXT("diagrama.jamgraph"), TEXT("Jam Graph (*.jamgraph)|*.jamgraph|JSON (*.json)|*.json"),
			EFileDialogFlags::None, Files);
		if (!bOk || Files.Num() == 0) { return false; }
		Path = Files[0];
	}
	// El MISMO string que se escribe es el que queda de referencia: recalcular con otro `BuildJson()`
	// abriría la puerta a que la foto y el archivo no digan exactamente lo mismo.
	const FString Json = BuildJson();
	const FString TempPath = Path + TEXT(".tmp");
	IFileManager::Get().Delete(*TempPath, false, true, true);
	const bool bWroteTemp = FFileHelper::SaveStringToFile(Json, *TempPath);
	const bool bPromoted = bWroteTemp
		&& IFileManager::Get().Move(*Path, *TempPath, true, true, false, true);
	if (bPromoted)
	{
		CurrentPath = Path;
		GuardadoEn = Json;   // desde acá el documento está en sync con el disco
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(TEXT("guardado: %s"), *Path)));
		}
	}
	else if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("ERROR: no se pudo guardar %s; el archivo anterior no se modificó."), *Path)));
	}
	IFileManager::Get().Delete(*TempPath, false, true, true);
	return bPromoted;
}

bool SJamGraphEditor::HayCambiosSinGuardar() const
{
	// Un lienzo vacío que nunca se guardó no tiene nada que perder: preguntar ahí es puro ruido.
	if (Nodes.Num() == 0 && Comments.Num() == 0 && CurrentPath.IsEmpty())
	{
		return false;
	}
	// `BuildJson` lee los valores VIVOS de los widgets, así que un parámetro tipeado y todavía no
	// confirmado también cuenta como cambio — que es lo que uno esperaría al cerrar.
	return BuildJson() != GuardadoEn;
}

bool SJamGraphEditor::ConfirmarCierre()
{
	if (!HayCambiosSinGuardar())
	{
		return true;
	}
	const FText Nombre = CurrentPath.IsEmpty()
		? LOCTEXT("DiagramaSinTitulo", "sin título")
		: FText::FromString(FPaths::GetCleanFilename(CurrentPath));
	const EAppReturnType::Type Respuesta = FMessageDialog::Open(EAppMsgType::YesNoCancel,
		FText::Format(LOCTEXT("CerrarConCambios",
			"El diagrama «{0}» tiene cambios sin guardar.\n\n¿Guardarlos antes de cerrar el panel?"),
			Nombre),
		LOCTEXT("CerrarConCambiosTitulo", "Jam · Graph"));

	if (Respuesta == EAppReturnType::Cancel) { return false; }   // seguir editando
	if (Respuesta == EAppReturnType::No)     { return true; }    // cerrar y descartar
	// Dijo que sí: si cancela el diálogo de archivo o el guardado falla, NO se cierra. Cerrar igual
	// sería tirar justo lo que acaba de pedir conservar.
	return SaveDiagram(/*bForceDialog*/ false);
}

void SJamGraphEditor::OpenDiagram()
{
	IDesktopPlatform* DP = FDesktopPlatformModule::Get();
	if (DP == nullptr) { return; }
	const FString Dir = FPaths::ProjectSavedDir() / TEXT("JamGraphs");
	TArray<FString> Files;
	const bool bOk = DP->OpenFileDialog(nullptr, TEXT("Abrir diagrama Jam"), Dir, TEXT(""),
		TEXT("Jam Graph (*.jamgraph)|*.jamgraph|JSON (*.json)|*.json"), EFileDialogFlags::None, Files);
	if (!bOk || Files.Num() == 0) { return; }
	FString Json;
	if (FFileHelper::LoadFileToString(Json, *Files[0]))
	{
		if (LoadGraphJson(Json))
		{
			CurrentPath = Files[0];
			// Recién abierto: lo que hay en pantalla ES lo que hay en disco. Se refotografía en vez
			// de guardar `Json` tal cual porque el archivo pudo venir con otro formato/orden.
			GuardadoEn = BuildJson();
		}
	}
}

void SJamGraphEditor::LoadBundledExample(const FString& Filename, const FText& LoadedMessage)
{
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("Jam"));
	if (!Plugin.IsValid())
	{
		if (Output.IsValid()) { Output->SetText(LOCTEXT("TreeExampleNoPlugin", "ERROR: no encontré el plugin Jam.")); }
		return;
	}
	const FString Path = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Resources/Examples"), Filename);
	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		if (Output.IsValid())
		{
			Output->SetText(FText::FromString(FString::Printf(
				TEXT("ERROR: no pude leer el ejemplo: %s"), *Path)));
		}
		return;
	}
	if (LoadGraphJson(Json))
	{
		// Es una plantilla: Guardar debe pedir una ruta y nunca escribir sobre el archivo distribuido.
		CurrentPath.Empty();
		if (Output.IsValid())
		{
			Output->SetText(LoadedMessage);
		}
	}
}

void SJamGraphEditor::InsertAllNodes()
{
	{
		// La galería son ~200 nodos: sin el silencio serían 200 pasos de historial para deshacer
		// una sola acción del menú.
		TGuardValue<bool> Callado(bSinHistorial, true);
		NewGraph();
		// una ficha de CADA verbo/op, en grilla, agrupadas por su orden en el spec. Alto generoso para
		// que los nodos altos (place tiene muchos params) no pisen la fila de abajo.
		const int32 Cols = 6;
		const float StepX = 210.0f;
		const float StepY = 340.0f;
		int32 K = 0;
		for (const FJamTool& T : Tools)
		{
			const FVector2D At(30.0f + (K % Cols) * StepX, 30.0f + (K / Cols) * StepY);
			AddNode(T.Verb, &At);
			++K;
		}
	}
	Marcar();
	ResetView();
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("galería: %d nodos (uno de cada tipo). Reencuadrá con la rueda para el screenshot."),
			Nodes.Num())));
	}
}

void SJamGraphEditor::ResetView()
{
	PanOffset = FVector2D(20.0f, 20.0f);
	Zoom = 1.0f;
	ApplyZoom();
}

#undef LOCTEXT_NAMESPACE
