#include "SJamGraphEditor.h"
#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SCanvas.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SComboBox.h"
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

		for (const TPair<FString, TSharedPtr<FJsonValue>>& Entry : Root->Values)
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
};

// El nombre del tab. No sale del spec de verbos porque no es una categoría de verbos: no hay
// ningún `FJamTool` con esta categoría, y sus fichas CARGAN un grafo en vez de crear un nodo.
static const TCHAR* JamLearnTab = TEXT("Aprender");

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

// Capa de fondo del canvas (como el de Grasshopper): pinta el color de fondo, una GRILLA fina
// alineada al pan/zoom, y los WIRES (splines) — todo detrás de los nodos.
class SJamWireLayer : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SJamWireLayer) {}
	SLATE_END_ARGS()

	void Construct(const FArguments&,
		TFunction<TArray<SJamGraphEditor::FJamWire>()> InGetter,
		TFunction<void(FVector2D&, float&)> InXform,
		TFunction<bool(FVector2D&, FVector2D&, FLinearColor&)> InPending)
	{
		Getter = MoveTemp(InGetter);
		XformGetter = MoveTemp(InXform);
		PendingGetter = MoveTemp(InPending);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
		const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		const FSlateBrush* White = FAppStyle::GetBrush("WhiteBrush");
		const FVector2D Size = AllottedGeometry.GetLocalSize();

		// Fondo del canvas: gris claro clásico de Grasshopper/Rhino 7.
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId, AllottedGeometry.ToPaintGeometry(),
			White, ESlateDrawEffect::None, FLinearColor(0.827f, 0.835f, 0.812f, 1.0f));

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

		// Wires (splines) entre nodos, sobre la grilla. Cada uno con su COLOR por tipo de dato (como
		// Blueprint/Substance): el color dice QUÉ fluye. Un halo claro debajo levanta el contraste sobre
		// el lienzo gris y ayuda a seguir el cable donde se cruzan.
		const FSlateBrush* Dot = FAppStyle::GetBrush("WhiteBrush");
		if (Getter)
		{
			const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry();
			for (const SJamGraphEditor::FJamWire& W : Getter())
			{
				const float dx = FMath::Max(50.0f, FMath::Abs(W.B.X - W.A.X) * 0.6f);
				const FVector2D T1(dx, 0.0f), T2(dx, 0.0f);
				// halo claro (más grueso, translúcido) + cable de color encima.
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 2, PG,
					W.A, T1, W.B, T2, 5.0f, ESlateDrawEffect::None,
					FLinearColor(1.0f, 1.0f, 1.0f, 0.55f));
				FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 3, PG,
					W.A, T1, W.B, T2, 2.6f, ESlateDrawEffect::None, W.Color);
				// punto en cada punta: ancla la conexión visualmente (como los pines de Blueprint).
				for (const FVector2D& P : {W.A, W.B})
				{
					FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 4,
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
			FSlateDrawElement::MakeSpline(OutDrawElements, LayerId + 5, AllottedGeometry.ToPaintGeometry(),
				PF, FVector2D(dx, 0.0f), PT, FVector2D(dx, 0.0f), 2.4f, ESlateDrawEffect::None,
				FLinearColor(PC.R, PC.G, PC.B, 0.7f));
			FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 6,
				AllottedGeometry.ToPaintGeometry(FVector2D(7.0f, 7.0f),
					FSlateLayoutTransform(PF - FVector2D(3.5f, 3.5f))),
				Dot, ESlateDrawEffect::None, PC);
		}
		return LayerId + 6;
	}

	virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }

private:
	TFunction<TArray<SJamGraphEditor::FJamWire>()> Getter;
	TFunction<void(FVector2D&, float&)> XformGetter;
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
	OnLayout = InArgs._OnLayout;
	ActiveAsset = InArgs._ActiveAsset;
	OnOpenContent = InArgs._OnOpenContent;

	// Ribbon estilo Grasshopper: una fila de TABS (categorías) y, debajo, las fichas de la categoría
	// activa con ICONO (badge de color + código) + nombre. El tab activo se pinta con el tono de su
	// categoría. El doble clic en el lienzo abre el buscador igual (los dos caminos conviven).
	Categories.Reset();
	for (const FJamTool& T : Tools)
	{
		Categories.AddUnique(T.Cat);
	}
	if (ActiveTab.IsEmpty() && Categories.Num() > 0)
	{
		ActiveTab = Categories[0];
	}

	TSharedRef<SHorizontalBox> TabStrip = SNew(SHorizontalBox);
	TabStrip->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
	[
		SNew(SButton)
		.Text(LOCTEXT("PaletteContent", "Content…"))
		.ToolTipText(LOCTEXT("PaletteContentTip", "Elegir el asset activo (abre la ventana de Content)"))
		.OnClicked_Lambda([this]() { OnOpenContent.ExecuteIfBound(); return FReply::Handled(); })
	];
	// «Aprender» va PRIMERO —es lo que busca alguien que recién llega— pero NO es el tab por
	// defecto: quien usa Jam todos los días no quiere una pantalla de bienvenida entre él y sus
	// verbos. Se abre en el primer tab de trabajo y este queda a un clic, a la vista.
	Categories.Insert(JamLearnTab, 0);
	for (const FString& Cat : Categories)
	{
		TabStrip->AddSlot().AutoWidth().Padding(1.0f, 0.0f)
		[
			SNew(SButton)
			.ToolTipText(Cat == JamLearnTab
				? LOCTEXT("LearnTabTip", "Tutoriales y ejemplos: grafos armados para abrir, correr y desarmar")
				: FText::FromString(FString::Printf(TEXT("Tab «%s»"), *Cat)))
			// activo = tono de la categoría; inactivo = gris apagado (así se lee cuál está abierto)
			.ButtonColorAndOpacity_Lambda([this, Cat]()
			{
				return ActiveTab == Cat ? CategoryColor(Cat) : FLinearColor(0.22f, 0.22f, 0.24f, 1.0f);
			})
			.OnClicked_Lambda([this, Cat]() { ActiveTab = Cat; RebuildTabContent(); return FReply::Handled(); })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[ MakeBadge(CategoryColor(Cat), Cat.Left(2).ToUpper(), 14.0f) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f, 2.0f, 0.0f)
				[ SNew(STextBlock).Text(FText::FromString(Cat)) ]
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
				+ SOverlay::Slot()
				[
					SAssignNew(WireLayer, SJamWireLayer,
						TFunction<TArray<FJamWire>()>(
							[this]() { return GetWireEndpoints(); }),
						TFunction<void(FVector2D&, float&)>(
							[this](FVector2D& P, float& Z) { P = PanOffset; Z = Zoom; }),
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

	RebuildTabContent();   // abre el primer tab con sus fichas
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
			+ SVerticalBox::Slot().AutoHeight()
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
		];
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
}


// ---- Ribbon estilo Grasshopper: tabs + fichas con icono ----

FLinearColor SJamGraphEditor::CategoryColor(const FString& Cat)
{
	// un tono por categoría (como los tabs de Grasshopper): tools + flow.
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
	const FString* IconName = JamIconMap().Find(Verb);
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
				const FString Firma = T.bSource
					? FString::Printf(TEXT("\u2192 %s"), *T.OutName)
					: FString::Printf(TEXT("%s \u2192 %s"), *T.InName, *T.OutName);
				ColumnBox->AddSlot().AutoHeight().Padding(1.0f)
				[
					SNew(SJamVerbTile)
					.Verb(Verb)
					.OnClicked_Lambda([this](FString V) { AddNodeAlCentro(V); })
					.ToolTipText(FText::FromString(FString::Printf(
						TEXT("%s   [%s]\n%s\n\nclic = al centro de la vista · arrastrá = donde sueltes"),
						*T.Verb, *Firma, *T.Doc)))
					[
						MakeBadge(CategoryColor(T.Cat), VerbCode(Verb), 30.0f, IconPathForVerb(Verb))
					]
				];
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
	// Mismo dibujo que un tab de verbos —fichas con icono, agrupadas, con el nombre del panel
	// abajo— para que se sienta parte del mismo ribbon y no una pantalla aparte. Las diferencias
	// son dos: la ficha CARGA un grafo en vez de crear un nodo, y el título va debajo del icono,
	// porque acá el nombre sí importa (un tutorial se elige por su nombre, un verbo por su firma).
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

	TArray<FString> Orden;
	TMap<FString, TArray<const FJamExample*>> PorGrupo;
	for (const FJamExample& E : Ejemplos)
	{
		if (!PorGrupo.Contains(E.Group))
		{
			Orden.Add(E.Group);
		}
		PorGrupo.FindOrAdd(E.Group).Add(&E);
	}

	for (int32 Indice = 0; Indice < Orden.Num(); ++Indice)
	{
		TSharedRef<SHorizontalBox> Fila = SNew(SHorizontalBox);
		for (const FJamExample* E : PorGrupo[Orden[Indice]])
		{
			const FString Archivo = E->File;
			const FString Mensaje = E->Message;
			Fila->AddSlot().AutoWidth().Padding(2.0f, 0.0f)
			[
				SNew(SButton)
				.ToolTipText(FText::FromString(FString::Printf(
					TEXT("%s\n\n%s"), *E->Title, *E->Doc)))
				.ContentPadding(FMargin(3.0f))
				.OnClicked_Lambda([this, Archivo, Mensaje]()
				{
					LoadBundledExample(Archivo, FText::FromString(Mensaje));
					return FReply::Handled();
				})
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
					[ MakeBadge(CategoryColor(JamLearnTab), TEXT("EJ"), 42.0f, JamIconPath(E->Icon)) ]
					+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 2.0f, 0.0f, 0.0f)
					[
						SNew(STextBlock)
						.Text(FText::FromString(E->Title))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					]
				]
			];
		}

		TabContentBox->AddSlot().AutoWidth().Padding(3.0f, 0.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ Fila ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f).HAlign(HAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Orden[Indice]))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.62f, 0.62f, 0.66f, 1.0f)))
			]
		];

		if (Indice + 1 < Orden.Num())
		{
			TabContentBox->AddSlot().AutoWidth().Padding(2.0f, 2.0f)
			[
				SNew(SSeparator).Orientation(Orient_Vertical).Thickness(1.0f)
			];
		}
	}
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
	AddNode(Op->Verb, &Modelo);
	return FReply::Handled();
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
			TEXT("A"), DataColor(TEXT("A")));
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
		for (const TSharedPtr<FString>& O : P.Options)
		{
			if (O.IsValid()) { Opts.Add(*O); }
		}
		const FString DataType = P.DataType.IsEmpty() ? JamParamDataType(P.Name, P.Type) : P.DataType;
		Params.Add(FJamNodeParam(P.Name, Value, P.Type, Opts, DataType, DataColor(DataType)));
		Node.PinNames.Add(P.Name);
	}

	const FString Id = Node.Id;
	// Nodos FUENTE (producen el dato, no lo reciben): sin pin de entrada, convención de Grasshopper.
	// El flag viene del spec (data-driven): asset/pick/create_spline y las fuentes de flow.
	const bool bHasInput = !T->bSource && !bFilaEsLaEntrada;

	TSharedRef<SJamGraphNode> Widget = SNew(SJamGraphNode)
		.Verb(Verb)
		.IconPath(IconPathForVerb(Verb))
		.IconColor(CategoryColor(T->Cat))
		.OutName(T->OutName)
		.InputColor(DataColor(T->InName))
		.OutputColor(DataColor(T->OutName))
		.InputLabel(DataName(T->InName))
		.OutputLabel(DataName(T->OutName))
		.Params(Params)
		.HasInput(bHasInput)
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
		.OnOutputClicked_Lambda([this, Id]() { OnPinClicked(Id, TEXT("out"), true); })
		.OnInputClicked_Lambda([this, Id](const FString& Pin) { OnPinClicked(Id, Pin, false); })
		.OnClicked_Lambda([this, Id](bool bShift, bool bCtrl) { ClickNode(Id, bShift, bCtrl); })
		.OnDragEnd_Lambda([this]() { Marcar(); })
		.OnParamChanged_Lambda([this]() { Marcar(); })
		.OnDeleteSelection_Lambda([this, Id]()
		{
			// `Supr` sobre un nodo de un grupo borra el grupo; sobre uno suelto, ese nodo.
			if (SelectedNodeIds.Contains(Id)) { DeleteSelection(); } else { DeleteNode(Id); }
		})
		.OnDeleteClicked_Lambda([this, Id]() { DeleteNode(Id); });

	Node.Widget = Widget;

	const float Height = SJamGraphNode::NodeHeight(Params.Num());
	Node.Height = Height;
	Canvas->AddSlot()
		.Position(TAttribute<FVector2D>::CreateLambda([this, Id]()
		{
			const FGNode* N = Nodes.FindByPredicate([&Id](const FGNode& X) { return X.Id == Id; });
			return N ? N->Pos + PanOffset : FVector2D::ZeroVector;   // el modelo no se mueve: se mueve la vista
		}))
		.Size(FVector2D(NodeWidth, Height))
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
	if (LoadGraphJson(Json))
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

// ---- portapapeles ----

void SJamGraphEditor::Copiar(bool bCortar)
{
	if (SelectedNodeIds.Num() == 0)
	{
		return;
	}
	// Al portapapeles DEL SISTEMA y no a un buffer interno: así se pega entre dos ventanas de Graph,
	// y el fragmento se puede pegar en un chat o en el vault — es el mismo JSON de un .jamgraph.
	const FString Recorte = BuildJson(&SelectedNodeIds);
	FPlatformApplicationMisc::ClipboardCopy(*Recorte);
	const int32 Cuantos = SelectedNodeIds.Num();
	if (bCortar)
	{
		DeleteSelection();
	}
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(
			TEXT("%s: %d nodo%s"), bCortar ? TEXT("cortado") : TEXT("copiado"),
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
	if (SelectedNodeIds.Num() == 0)
	{
		return;
	}
	// Sin tocar el portapapeles: duplicar no puede pisar lo que tenías copiado.
	if (PegarJson(BuildJson(&SelectedNodeIds), /*bDesplazar*/ true)) { Marcar(); }
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
	for (const TPair<FString, TSharedPtr<FJsonValue>>& KV : (*NodesObj)->Values)
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
				for (const TPair<FString, TSharedPtr<FJsonValue>>& PV : (*PO)->Values)
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
		}
	}
	if (Pegados.Num() == 0)
	{
		if (Output.IsValid())
		{
			Output->SetText(LOCTEXT("PasteNothing", "no había nada pegable en el portapapeles."));
		}
		return false;
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
	// Lo pegado queda elegido: es lo que uno quiere mover o volver a pegar enseguida.
	SelectedNodeIds = Pegados;
	if (Output.IsValid())
	{
		Output->SetText(FText::FromString(FString::Printf(TEXT("pegado: %d nodos"), Pegados.Num())));
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
		Max.X = FMath::Max(Max.X, N.Pos.X + NodeWidth);
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
	// Copia: `DeleteNode` toca `SelectedNodeIds`, y recorrer un TSet mientras se modifica es UB.
	TArray<FString> Ids = SelectedNodeIds.Array();
	if (Ids.Num() == 0)
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
	}
	SelectedNodeIds.Reset();
	Marcar();
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

void SJamGraphEditor::AcomodarSeleccion(const FString& Accion)
{
	if (SelectedNodeIds.Num() < 2 || !OnLayout.IsBound())
	{
		return;
	}
	// Rectángulos en coordenadas de MODELO: lo que `jam.layout` sabe leer. El ancho es fijo; el
	// alto NO (depende de cuántos params tiene el verbo), y es justo el que hace que alinear
	// «abajo» sea distinto de alinear por `y`.
	TArray<FString> Filas;
	for (const FGNode& N : Nodes)
	{
		if (!SelectedNodeIds.Contains(N.Id)) { continue; }
		Filas.Add(FString::Printf(
			TEXT("{\"id\":\"%s\",\"x\":%.3f,\"y\":%.3f,\"w\":%.3f,\"h\":%.3f}"),
			*N.Id, N.Pos.X, N.Pos.Y, NodeWidth, N.Height));
	}
	const FString Json = FString::Printf(TEXT("[%s]"), *FString::Join(Filas, TEXT(",")));

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
	for (const TPair<FString, TSharedPtr<FJsonValue>>& KV : (*Pos)->Values)
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

FString SJamGraphEditor::OutputDataTypeFor(const FString& NodeId, const FString& Pin) const
{
	if (Pin != TEXT("out"))
	{
		return FString();
	}
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	return T ? T->OutName : FString();
}

FString SJamGraphEditor::InputDataTypeFor(const FString& NodeId, const FString& Pin) const
{
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	if (N == nullptr || T == nullptr)
	{
		return FString();
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
static bool JamTiposCompatibles(const FString& OutType, const FString& InType)
{
	if (OutType.IsEmpty() || InType.IsEmpty())
	{
		return false;
	}
	return InType == TEXT("*") || OutType == InType;
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
	if (!JamTiposCompatibles(OutType, InType))
	{
		OutError = FString::Printf(TEXT("tipo incompatible: %s.%s entrega %s; %s.%s espera %s"),
			*From, *FromPin, *OutType, *To, *ToPin, *InType);
		return false;
	}
	return true;
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
	// · MT=grafo de material (el shader que se está armando, todavía sin hornear).
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
	if (OutName == TEXT("M")) { return FLinearColor(0.08f, 0.58f, 0.62f, 1.0f); }   // cian (DynamicMesh)
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

FLinearColor SJamGraphEditor::WireColorFor(const FString& NodeId) const
{
	const FGNode* N = Nodes.FindByPredicate([&NodeId](const FGNode& X) { return X.Id == NodeId; });
	const FJamTool* T = N ? FindTool(N->Verb) : nullptr;
	return DataColor(T ? T->OutName : FString());
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
			const float AY = SJamGraphNode::PinLocalY(-1);
			const float BY = SJamGraphNode::PinLocalY(PinIndex(E.To, E.ToPin));
			FJamWire W;
			W.A = (FVector2D(A->Pos.X + NodeWidth - Half, A->Pos.Y + AY) + PanOffset) * Zoom;
			W.B = (FVector2D(B->Pos.X + Half, B->Pos.Y + BY) + PanOffset) * Zoom;
			W.Color = WireColorFor(E.From);   // color = tipo del dato que SALE del origen
			Out.Add(W);
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
	const float AY = SJamGraphNode::PinLocalY(-1);
	OutFrom = (FVector2D(A->Pos.X + NodeWidth - Half, A->Pos.Y + AY) + PanOffset) * Zoom;
	OutTo = LastMousePos;
	OutColor = WireColorFor(PendingSource);
	return true;
}

FString SJamGraphEditor::BuildJson(const TSet<FString>* Solo) const
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
	if (Tecla == EKeys::F && !InKeyEvent.IsControlDown())
	{
		Encuadrar(/*bSoloSeleccion*/ true);
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
		ClearSelection();
		return FReply::Handled();
	}
	if (Tecla == EKeys::Delete && SelectedNodeIds.Num() > 0)
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
		if (Min.X < Max.X && Min.Y < Max.Y)
		{
			for (const FGNode& N : Nodes)
			{
				if (N.Pos.X < Max.X && N.Pos.X + NodeWidth > Min.X
					&& N.Pos.Y < Max.Y && N.Pos.Y + N.Height > Min.Y)
				{
					SelectedNodeIds.Add(N.Id);
				}
			}
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
	MB.AddMenuEntry(LOCTEXT("Save", "Guardar"), LOCTEXT("SaveTip", "Guardar en el archivo actual"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::SaveDiagram, false)));
	MB.AddMenuEntry(LOCTEXT("SaveAs", "Guardar como…"), LOCTEXT("SaveAsTip", "Elegir archivo"), FSlateIcon(),
		FUIAction(FExecuteAction::CreateSP(this, &SJamGraphEditor::SaveDiagram, true)));
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
		// Todas piden 2+… no: piden AL MENOS UNO elegido. Pegar es la excepción, siempre se puede
		// intentar (el portapapeles puede venir de otra ventana de Graph).
		const FCanExecuteAction HayAlgo = FCanExecuteAction::CreateLambda(
			[this]() { return SelectedNodeIds.Num() > 0; });
		MB.AddMenuEntry(LOCTEXT("Copy", "Copiar\tCtrl+C"),
			LOCTEXT("CopyTip", "Copia los nodos elegidos como JSON al portapapeles del sistema"),
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
	}
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
	MB.EndSection();

	// Alinear y distribuir: las posiciones las decide `jam.layout` (puro y testeado). Requieren 2+
	// nodos elegidos; con menos, la acción no hace nada porque no hay contra qué alinear.
	MB.BeginSection(TEXT("Acomodar"), LOCTEXT("SectionAlign", "Alinear y distribuir"));
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
	Nodes.Reset();
	Edges.Reset();
	SelectedNodeIds.Reset();
	PendingSource.Empty();
	PendingSourcePin.Empty();
	NextId = 1;
	// `New` inicia un DOCUMENTO nuevo. Conservar esta ruta hacía que el Save siguiente sobrescribiera
	// silenciosamente el .jamgraph anterior.
	CurrentPath.Empty();
	if (Output.IsValid())
	{
		Output->SetText(LOCTEXT("NewDone", "grafo vacío."));
	}
	Marcar();   // vaciar el grafo también se deshace (queda callado cuando lo llama LoadGraphJson)
}

bool SJamGraphEditor::LoadGraphJson(const FString& Json)
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
	for (const TPair<FString, TSharedPtr<FJsonValue>>& KV : (*NodesObj)->Values)
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
		const TSharedPtr<FJsonObject>* ParamsObj = nullptr;
		if (NO->HasField(TEXT("params"))
			&& (!NO->TryGetObjectField(TEXT("params"), ParamsObj) || ParamsObj == nullptr))
		{
			return Fail(FString::Printf(TEXT("params de '%s' debe ser un objeto."), *KV.Key));
		}
		if (ParamsObj != nullptr)
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& PV : (*ParamsObj)->Values)
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
			const FString OutType = (FromPin == TEXT("out") && FromTool) ? FromTool->OutName : FString();
			FString InType;
			if (ToPin == TEXT("in") && ToTool && !ToTool->bSource && ToTool->Arity != 0)
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
			if (!JamTiposCompatibles(OutType, InType))
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

	// Fase 2: el modelo completo es válido; recién ahora reemplazar el documento visible.
	// El silencio va en un BLOQUE propio: vaciar + crear N nodos + N wires es UN paso deshacible y no
	// 2N+1, pero el `Marcar()` tiene que quedar afuera. Con `TGuardValue` y no con un bool a mano,
	// porque acá adentro hay `return Fail(...)`: dejar la bandera prendida mataría el historial en
	// silencio para el resto de la sesión.
	{
		TGuardValue<bool> Callado(bSinHistorial, true);
		NewGraph();
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
			}
		}
		for (const FLoadedEdge& Loaded : LoadedEdges)
		{
			Edges.Add(FGEdge{IdMap[Loaded.From], Loaded.FromPin, IdMap[Loaded.To], Loaded.ToPin});
		}
		RefreshCabledPins();   // reflejar en los inputs los cables recién cargados
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

void SJamGraphEditor::SaveDiagram(bool bForceDialog)
{
	FString Path = CurrentPath;
	if (Path.IsEmpty() || bForceDialog)
	{
		IDesktopPlatform* DP = FDesktopPlatformModule::Get();
		if (DP == nullptr) { return; }
		const FString Dir = FPaths::ProjectSavedDir() / TEXT("JamGraphs");
		IFileManager::Get().MakeDirectory(*Dir, true);
		TArray<FString> Files;
		const bool bOk = DP->SaveFileDialog(nullptr, TEXT("Guardar diagrama Jam"), Dir,
			TEXT("diagrama.jamgraph"), TEXT("Jam Graph (*.jamgraph)|*.jamgraph|JSON (*.json)|*.json"),
			EFileDialogFlags::None, Files);
		if (!bOk || Files.Num() == 0) { return; }
		Path = Files[0];
	}
	const FString TempPath = Path + TEXT(".tmp");
	IFileManager::Get().Delete(*TempPath, false, true, true);
	const bool bWroteTemp = FFileHelper::SaveStringToFile(BuildJson(), *TempPath);
	const bool bPromoted = bWroteTemp
		&& IFileManager::Get().Move(*Path, *TempPath, true, true, false, true);
	if (bPromoted)
	{
		CurrentPath = Path;
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
