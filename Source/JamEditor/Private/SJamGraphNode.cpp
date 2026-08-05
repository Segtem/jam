#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SSpinBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Styling/AppStyle.h"
#include "Styling/CoreStyle.h"
#include "Rendering/DrawElements.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Math/TransformCalculus2D.h"

#define LOCTEXT_NAMESPACE "JamGraphNode"

namespace
{
	// Texto oscuro sobre el cuerpo gris claro del componente (como GH).
	const FLinearColor JamInk(0.10f, 0.10f, 0.11f, 1.0f);

	// Grip en dos discos: el exterior recibe el color semántico del dato y el interior claro conserva
	// contraste sobre cualquier cuerpo. Su centro cae justo sobre el borde, como en Grasshopper.
	const FSlateRoundedBoxBrush GGripOuterBrush(FLinearColor::White, 5.0f);
	const FSlateRoundedBoxBrush GGripInnerBrush(FLinearColor(0.90f, 0.90f, 0.87f, 1.0f), 4.0f);

	FString FriendlyVerbName(const FString& Verb)
	{
		FString Name = Verb;
		Name.ReplaceInline(TEXT("_"), TEXT(" "));
		if (!Name.IsEmpty())
		{
			Name[0] = FChar::ToUpper(Name[0]);
		}
		return Name;
	}

	// Nub = botón sin borde con el grip circular clicable.
	TSharedRef<SWidget> MakeNub(const FString& Tip, const FLinearColor& BorderColor, TFunction<void()> OnClick)
	{
		return SNew(SButton)
			.ButtonStyle(&FAppStyle::Get(), "NoBorder")
			.ToolTipText(FText::FromString(Tip + TEXT("\nAlt+clic: eliminar conexiones del pin")))
			.ContentPadding(FMargin(0.0f))
			.HAlign(HAlign_Center).VAlign(VAlign_Center)
			.OnClicked_Lambda([OnClick]() { OnClick(); return FReply::Handled(); })
			[
				SNew(SBox).WidthOverride(10.0f).HeightOverride(10.0f)
				[
					SNew(SOverlay)
					+ SOverlay::Slot()
					[ SNew(SImage).Image(&GGripOuterBrush).ColorAndOpacity(BorderColor) ]
					+ SOverlay::Slot().Padding(2.0f)
					[ SNew(SImage).Image(&GGripInnerBrush) ]
				]
			];
	}
}

void SJamGraphNode::Construct(const FArguments& InArgs)
{
	Verb = InArgs._Verb;
	DisplayName = InArgs._DisplayName;
	IconPath = InArgs._IconPath;
	IconColor = InArgs._IconColor;
	OnDragDelta = InArgs._OnDragDelta;
	OnInputClickedDelegate = InArgs._OnInputClicked;
	OnOutputClickedDelegate = InArgs._OnOutputClicked;
	OnDeleteClickedDelegate = InArgs._OnDeleteClicked;
	OnClickedDelegate = InArgs._OnClicked;
	OnDeleteSelectionDelegate = InArgs._OnDeleteSelection;
	OnDragEndDelegate = InArgs._OnDragEnd;
	OnParamChangedDelegate = InArgs._OnParamChanged;
	IsSelectedAttr = InArgs._IsSelected;
	RebuildBodyBrush();
	if (!IconPath.IsEmpty())
	{
		IconBrush = MakeShared<FSlateVectorImageBrush>(IconPath, FVector2D(24.0f), JamInk);
	}

	// Controles CLAROS y compactos, como los parámetros auxiliares de GH, en vez de heredar los
	// inputs oscuros del editor de Unreal.
	FieldStyle = FAppStyle::Get().GetWidgetStyle<FEditableTextBoxStyle>("NormalEditableTextBox");
	const FSlateRoundedBoxBrush FieldBg(FLinearColor(0.96f, 0.96f, 0.93f, 1.0f), 2.0f,
		FLinearColor(0.34f, 0.34f, 0.32f, 1.0f), 1.0f);
	const FSlateRoundedBoxBrush FieldFocus(FLinearColor(1.0f, 1.0f, 0.98f, 1.0f), 2.0f,
		IconColor, 1.4f);
	FieldStyle.SetBackgroundImageNormal(FieldBg);
	FieldStyle.SetBackgroundImageHovered(FieldFocus);
	FieldStyle.SetBackgroundImageFocused(FieldFocus);
	FieldStyle.SetBackgroundImageReadOnly(FieldBg);
	FieldStyle.SetForegroundColor(FLinearColor::Black);
	FieldStyle.SetFocusedForegroundColor(FLinearColor::Black);
	FieldStyle.SetReadOnlyForegroundColor(FLinearColor(0.15f, 0.15f, 0.15f, 1.0f));
	FieldStyle.SetPadding(FMargin(4.0f, 1.0f));
	// SELECCIÓN de texto: el TextStyle heredado es del tema OSCURO (texto blanco + resalte claro) →
	// al seleccionar quedaba blanco sobre blanco. Texto negro + resalte AZUL para que se lea.
	FTextBlockStyle TextStyle = FieldStyle.TextStyle;
	TextStyle.SetFont(FCoreStyle::GetDefaultFontStyle("Regular", 7));
	TextStyle.SetColorAndOpacity(FLinearColor::Black);
	TextStyle.SetSelectedBackgroundColor(FLinearColor(0.20f, 0.45f, 0.85f, 1.0f));
	TextStyle.SetHighlightColor(FLinearColor::Black);
	FieldStyle.SetTextStyle(TextStyle);

	SpinStyle = FAppStyle::Get().GetWidgetStyle<FSpinBoxStyle>("SpinBox");
	const FSlateRoundedBoxBrush SpinFill(IconColor.CopyWithNewOpacity(0.55f), 2.0f);
	SpinStyle.SetBackgroundBrush(FieldBg)
		.SetHoveredBackgroundBrush(FieldFocus)
		.SetActiveBackgroundBrush(FieldFocus)
		.SetActiveFillBrush(SpinFill)
		.SetHoveredFillBrush(SpinFill)
		.SetInactiveFillBrush(*FAppStyle::GetBrush("NoBrush"))
		.SetArrowsImage(*FAppStyle::GetBrush("NoBrush"))
		.SetForegroundColor(JamInk)
		.SetTextPadding(FMargin(4.0f, 1.0f))
		.SetInsetPadding(FMargin(1.0f));

	// El Checkbox estándar toma FStyleColors::Input del tema del editor (negro en el tema oscuro).
	// Conservamos su glyph nativo y reemplazamos sólo la caja por el mismo lenguaje claro de los
	// campos numéricos/textuales. El tamaño explícito evita que el brush altere la altura de la fila.
	CheckStyle = FAppStyle::Get().GetWidgetStyle<FCheckBoxStyle>("Checkbox");
	const FVector2f CheckSize(18.0f, 18.0f);
	const FSlateRoundedBoxBrush CheckBg(FLinearColor(0.96f, 0.96f, 0.93f, 1.0f), 3.0f,
		FLinearColor(0.34f, 0.34f, 0.32f, 1.0f), 1.0f, CheckSize);
	const FSlateRoundedBoxBrush CheckHover(FLinearColor(1.0f, 1.0f, 0.98f, 1.0f), 3.0f,
		IconColor, 1.4f, CheckSize);
	CheckStyle.SetBackgroundImage(CheckBg)
		.SetBackgroundHoveredImage(CheckHover)
		.SetBackgroundPressedImage(CheckHover)
		.SetPadding(FMargin(0.0f));

	// Celda de alto FIJO (los pines se alinean a las filas por construcción; la métrica la comparte el
	// editor para anclar los wires exactamente en cada pin — como los grips por parámetro de GH).
	auto Cell = [](float H, TSharedRef<SWidget> W)
	{
		return SNew(SBox).HeightOverride(H).VAlign(VAlign_Center)[ W ];
	};
	auto Spacer = [](float H) { return SNew(SBox).HeightOverride(H); };
	const FString OutputPinName = InArgs._OutputPinName.IsEmpty()
		? FString(TEXT("out")) : InArgs._OutputPinName;

	// Anatomía de componente de Grasshopper: cartela flotante arriba (la pinta OnPaint), parámetros en
	// filas a la izquierda [grip][nombre][valor], nombre vertical en el centro (futuro icono) y salida a
	// la derecha. Sin Execution Pins: Jam es dataflow como GH.
	//   col pines-in (izq) · col params (nombre+valor) · centro libre · col pin-out (der)
	TSharedRef<SVerticalBox> LeftCol  = SNew(SVerticalBox);
	TSharedRef<SVerticalBox> ParamCol = SNew(SVerticalBox);
	TSharedRef<SVerticalBox> RightCol = SNew(SVerticalBox);

	LeftCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	ParamCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	RightCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];

	// Fila header: nub de stream «in» (izq) · zona libre de arrastre · nub «out» (der). Cerrar vive en
	// una capa independiente, arriba a la derecha del componente.
	LeftCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH, InArgs._HasInput
			? MakeNub(TEXT("entrada de stream (clic para conectar)"),
				InArgs._InputColor,
				[this]() { OnInputClickedDelegate.ExecuteIfBound(TEXT("in")); })
			: StaticCastSharedRef<SWidget>(SNullWidget::NullWidget))
	];
	// La fila del header lleva los NOMBRES de lo que entra y de lo que sale. Antes acá había un
	// espaciador y los dos pines eran puntos de color sin más: para saber qué recibía un nodo había
	// que acordarse de la paleta. Los colores siguen (ayudan a seguir un cable de un vistazo), pero
	// la que dice qué es cada cosa es la palabra.
	ParamCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH,
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(InArgs._HasInput ? InArgs._InputLabel : FString()))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.30f, 0.31f, 0.33f, 1.0f)))
			]
			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(InArgs._OutputLabel))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.30f, 0.31f, 0.33f, 1.0f)))
			])
	];
	RightCol->AddSlot().AutoHeight()
	[
		Cell(HeaderH, InArgs._OutputPins.Num() == 0 && !InArgs._OutputDataType.IsEmpty()
			? MakeNub(FString::Printf(TEXT("salida «%s» · tipo %s"),
				*OutputPinName, *InArgs._OutputDataType), InArgs._OutputColor,
				[this, OutputPinName]() { OnOutputClickedDelegate.ExecuteIfBound(OutputPinName); })
			: StaticCastSharedRef<SWidget>(SNullWidget::NullWidget))
	];

	// Slider del nodo `number`: el `value` se arrastra dentro de [min, max] (el Number Slider de GH). El
	// rango vive en holders compartidos que los campos `min`/`max` actualizan en vivo → mover el rango
	// re-clampa el slider al toque. Se leen de los defaults antes del loop (pueden llegar en cualquier orden).
	TSharedRef<float> NumMin = MakeShared<float>(0.0f);
	TSharedRef<float> NumMax = MakeShared<float>(100.0f);
	if (Verb == TEXT("number"))
	{
		for (const FJamNodeParam& Q : InArgs._Params)
		{
			if (Q.Name == TEXT("min")) { *NumMin = FCString::Atof(*Q.Value); }
			else if (Q.Name == TEXT("max")) { *NumMax = FCString::Atof(*Q.Value); }
		}
	}

	// una fila por parámetro: [nub] · [nombre][input] · (sin salida). El INPUT depende del tipo del
	// param (como los widgets de Grasshopper): bool → toggle · enum (`opciones`) → dropdown · resto →
	// campo de texto. Los numéricos siguen siendo texto A PROPÓSITO: en el grafo un param puede ser una
	// EXPRESIÓN «=count*2» (el cerebro paramétrico) que un spinbox no dejaría tipear — el slider de GH
	// se logra cableando un nodo `number` al pin del param.
	for (const FJamNodeParam& P : InArgs._Params)
	{
		const FString Key = P.Name;
		const FString Label = P.Label.IsEmpty() ? Key : P.Label;

		TSharedRef<SWidget> Input = SNullWidget::NullWidget;
		if (Verb == TEXT("number") && Key == TEXT("value"))
		{
			// SLIDER VISUAL (el Number Slider de GH): el `value` del nodo `number` es SIEMPRE un literal
			// (la fuente de la variable; el `math` es el que lleva la expresión) → se arrastra en vez de
			// tipear, ACOTADO a [min, max] como GH.
			TSharedRef<float> Val = MakeShared<float>(FCString::Atof(*P.Value));
			Input = SNew(SSpinBox<float>)
				.Style(&SpinStyle)
				.Value_Lambda([Val]() { return *Val; })
				.OnValueChanged_Lambda([Val](float V) { *Val = V; })
				// Commit y no Changed: UN paso del historial por arrastre del slider, no por frame.
				.OnValueCommitted_Lambda([this](float, ETextCommit::Type)
					{ OnParamChangedDelegate.ExecuteIfBound(); })
				.MinValue_Lambda([NumMin]() { return *NumMin; })
				.MaxValue_Lambda([NumMax]() { return *NumMax; })
				.MinSliderValue_Lambda([NumMin]() { return *NumMin; })
				.MaxSliderValue_Lambda([NumMax]() { return *NumMax; })
				.Delta(0.0f)
				.MinDesiredWidth(60.0f);
			ParamGetters.Add(Key, [Val]() { return FString::SanitizeFloat(*Val); });
			ParamSetters.Add(Key, [Val](const FString& V) { *Val = FCString::Atof(*V); });
		}
		else if (Verb == TEXT("number") && (Key == TEXT("min") || Key == TEXT("max")))
		{
			// Los EXTREMOS del rango del slider: spinbox libre (sin tope) que escribe el holder → el
			// slider de arriba se re-acota al instante.
			TSharedRef<float> H = (Key == TEXT("min")) ? NumMin : NumMax;
			Input = SNew(SSpinBox<float>)
				.Style(&SpinStyle)
				.Value_Lambda([H]() { return *H; })
				.OnValueChanged_Lambda([H](float V) { *H = V; })
				.OnValueCommitted_Lambda([this](float, ETextCommit::Type)
					{ OnParamChangedDelegate.ExecuteIfBound(); })
				.MinValue(TOptional<float>()).MaxValue(TOptional<float>())
				.MinSliderValue(-1000.0f).MaxSliderValue(1000.0f)
				.MinDesiredWidth(50.0f);
			ParamGetters.Add(Key, [H]() { return FString::SanitizeFloat(*H); });
			ParamSetters.Add(Key, [H](const FString& V) { *H = FCString::Atof(*V); });
		}
		else if (P.Type == TEXT("bool"))
		{
			// TOGGLE (como el Boolean Toggle de GH): no obliga a tipear «true».
			const bool bOn = P.Value.Equals(TEXT("true"), ESearchCase::IgnoreCase);
			TSharedRef<SCheckBox> Check = SNew(SCheckBox)
				.Style(&CheckStyle)
				.IsChecked(bOn ? ECheckBoxState::Checked : ECheckBoxState::Unchecked)
				.OnCheckStateChanged_Lambda([this](ECheckBoxState)
					{ OnParamChangedDelegate.ExecuteIfBound(); });
			Input = Check;
			ParamGetters.Add(Key, [Check]()
			{
				return Check->IsChecked() ? FString(TEXT("true")) : FString(TEXT("false"));
			});
			ParamSetters.Add(Key, [Check](const FString& V)
			{
				Check->SetIsChecked(V.Equals(TEXT("true"), ESearchCase::IgnoreCase)
					? ECheckBoxState::Checked : ECheckBoxState::Unchecked);
			});
		}
		else if (P.Options.Num() > 0)
		{
			// DROPDOWN (Value List de GH): dominio cerrado → se elige, no se escribe (ni se escribe mal).
			TSharedRef<FString> Choice = MakeShared<FString>(P.Value);
			const TArray<FString> Opts = P.Options;
			const TArray<FString> OptionLabels = P.OptionLabels;
			Input = SNew(SComboButton)
				.ComboButtonStyle(&FAppStyle::Get().GetWidgetStyle<FComboButtonStyle>("SimpleComboButton"))
				// `this` también en la lambda de AFUERA: la de adentro avisa del cambio, y una lambda
				// anidada no puede capturar lo que la que la contiene no capturó.
				.OnGetMenuContent_Lambda([this, Choice, Opts, OptionLabels]()
				{
					FMenuBuilder MB(true, nullptr);
					for (int32 Index = 0; Index < Opts.Num(); ++Index)
					{
						const FString O = Opts[Index];
						const FString Label = OptionLabels.IsValidIndex(Index) ? OptionLabels[Index] : O;
						MB.AddMenuEntry(FText::FromString(Label.IsEmpty() ? TEXT("(—)") : Label),
							FText::GetEmpty(), FSlateIcon(),
							FUIAction(FExecuteAction::CreateLambda([this, Choice, O]()
							{
								*Choice = O;
								OnParamChangedDelegate.ExecuteIfBound();
							})));
					}
					return MB.MakeWidget();
				})
				.ButtonContent()
				[
					SNew(STextBlock)
					.ColorAndOpacity(JamInk)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
					.Text_Lambda([Choice, Opts, OptionLabels]()
					{
						const int32 Index = Opts.Find(*Choice);
						const FString Label = OptionLabels.IsValidIndex(Index) ? OptionLabels[Index] : *Choice;
						return FText::FromString(Label.IsEmpty() ? TEXT("(—)") : Label);
					})
				];
			ParamGetters.Add(Key, [Choice]() { return *Choice; });
			ParamSetters.Add(Key, [Choice](const FString& V) { *Choice = V; });
		}
		else
		{
			// TEXTO claro (número, semilla, expresión «=…», nombre de asset).
			TSharedRef<SEditableTextBox> Field = SNew(SEditableTextBox)
				.Style(&FieldStyle).Text(FText::FromString(P.Value))
				// Al confirmar (Enter o perder el foco), no en cada tecla: si no, tipear «24» serían
				// dos pasos del historial y Ctrl+Z devolvería «2».
				.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type)
					{ OnParamChangedDelegate.ExecuteIfBound(); });
			Input = Field;
			ParamGetters.Add(Key, [Field]() { return Field->GetText().ToString(); });
			ParamSetters.Add(Key, [Field](const FString& V) { Field->SetText(FText::FromString(V)); });
		}

		// Si el pin de este parámetro tiene un CABLE, el input se deshabilita (grisea): el valor lo manda
		// el cable, no el campo — como GH cuando un input está wired. IsEnabled se lee por atributo.
		const FString PinParaGrisear = P.PinName.IsEmpty() ? Key : P.PinName;
		Input->SetEnabled(TAttribute<bool>::CreateLambda(
			[this, PinParaGrisear]() { return !CabledPins.Contains(PinParaGrisear); }));

		const FString PinDeLaFila = P.PinName.IsEmpty() ? Key : P.PinName;
		LeftCol->AddSlot().AutoHeight()
		[
			Cell(RowH, MakeNub(FString::Printf(TEXT("pin «%s» · tipo %s"), *Key, *P.DataType),
				P.PinColor,
				[this, PinDeLaFila]() { OnInputClickedDelegate.ExecuteIfBound(PinDeLaFila); }))
		];
		ParamCol->AddSlot().AutoHeight()
		[
			Cell(RowH,
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(1.0f, 0.0f, 3.0f, 0.0f)
				[
					SNew(STextBlock).Text(FText::FromString(Label))
					.ColorAndOpacity(JamInk)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
				[
					Input
				])
		];
		RightCol->AddSlot().AutoHeight()[ Cell(RowH, StaticCastSharedRef<SWidget>(SNullWidget::NullWidget)) ];
	}

	// Una función puede tener N entradas y M salidas. Van en filas enfrentadas y NOMBRADAS: el
	// nombre es parte del contrato, no una etiqueta cosmética. Las filas empiezan después de los
	// parámetros comunes para que el editor pueda calcular su Y con la misma métrica fija.
	const int32 SignatureRows = FMath::Max(InArgs._InputPins.Num(), InArgs._OutputPins.Num());
	for (int32 Row = 0; Row < SignatureRows; ++Row)
	{
		const bool bHasIn = InArgs._InputPins.IsValidIndex(Row);
		const bool bHasOut = InArgs._OutputPins.IsValidIndex(Row);
		const FJamNodePin InPin = bHasIn ? InArgs._InputPins[Row] : FJamNodePin();
		const FJamNodePin OutPin = bHasOut ? InArgs._OutputPins[Row] : FJamNodePin();
		LeftCol->AddSlot().AutoHeight()
		[
			Cell(RowH, bHasIn
				? MakeNub(FString::Printf(TEXT("entrada «%s» · tipo %s"), *InPin.Name, *InPin.DataType),
					InPin.Color, [this, Nombre = InPin.Name]()
					{ OnInputClickedDelegate.ExecuteIfBound(Nombre); })
				: StaticCastSharedRef<SWidget>(SNullWidget::NullWidget))
		];
		ParamCol->AddSlot().AutoHeight()
		[
			Cell(RowH,
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::FromString(bHasIn
						? FString::Printf(TEXT("%s (%s)"), *InPin.Name, *InPin.TypeLabel) : FString()))
					.ColorAndOpacity(JamInk).Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::FromString(bHasOut
						? FString::Printf(TEXT("%s (%s)"), *OutPin.Name, *OutPin.TypeLabel) : FString()))
					.ColorAndOpacity(JamInk).Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				])
		];
		RightCol->AddSlot().AutoHeight()
		[
			Cell(RowH, bHasOut
				? MakeNub(FString::Printf(TEXT("salida «%s» · tipo %s"), *OutPin.Name, *OutPin.DataType),
					OutPin.Color, [this, Nombre = OutPin.Name]()
					{ OnOutputClickedDelegate.ExecuteIfBound(Nombre); })
				: StaticCastSharedRef<SWidget>(SNullWidget::NullWidget))
		];
	}

	TSharedRef<SHorizontalBox> MainContent = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ LeftCol ] ]
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(ParamColW)[ ParamCol ] ]
		+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]   // centro: nombre/icono (OnPaint)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ RightCol ] ];

	ChildSlot
	[
		SNew(SOverlay)
		+ SOverlay::Slot()[ MainContent ]
		// Flag de debug: se prende el nodo que YA está, sin agregar ni cablear nada. Es el display
		// flag de Houdini / la tecla D de PCG, y no el nodo de debug aparte que había antes.
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(0.0f, 1.0f, 22.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(18.0f).HeightOverride(16.0f)
			[
				SNew(SButton)
				.ButtonStyle(&FAppStyle::Get(), "NoBorder")
				.ToolTipText(LOCTEXT("DebugFlag", "ver este nodo: dibuja su salida y vuelca sus datos al reporte"))
				.ContentPadding(FMargin(0.0f))
				.HAlign(HAlign_Center).VAlign(VAlign_Center)
				.OnClicked_Lambda([this]()
				{
					// El flag lo lee `BuildJson` al serializar, así que alcanza con guardarlo acá.
					bDebugEnabled = !bDebugEnabled;
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					.Text_Lambda([this]() { return FText::FromString(bDebugEnabled ? TEXT("◉") : TEXT("○")); })
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
					.ColorAndOpacity_Lambda([this]()
					{
						return bDebugEnabled ? FSlateColor(FLinearColor(1.0f, 0.62f, 0.11f))
						                     : FSlateColor(JamInk.CopyWithNewOpacity(0.45f));
					})
				]
			]
		]
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(0.0f, 1.0f, 2.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(18.0f).HeightOverride(16.0f)
			[
				SNew(SButton)
				.ButtonStyle(&FAppStyle::Get(), "NoBorder")
				.ToolTipText(LOCTEXT("Del", "borrar nodo"))
				.ContentPadding(FMargin(0.0f))
				.HAlign(HAlign_Center).VAlign(VAlign_Center)
				.OnClicked_Lambda([this]()
				{
					OnDeleteClickedDelegate.ExecuteIfBound();
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					.Text(FText::FromString(TEXT("×")))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
					.ColorAndOpacity(JamInk)
				]
			]
		]
	];
}

void SJamGraphNode::RebuildBodyBrush()
{
	// En GH el cuerpo normal es gris; naranja y rojo comunican warning/error, no categorías. Jam mantiene
	// una huella mínima de la categoría en el neutro y reserva los colores fuertes para el oráculo.
	FLinearColor Fill = FMath::Lerp(
		FLinearColor(0.76f, 0.77f, 0.78f, 1.0f), IconColor, 0.10f);
	if (ResultState == TEXT("aviso"))
	{
		// AMARILLO: pasó algo que no es un error pero que hay que saber — «12 pisados contra lo que
		// ya estaba». El nodo corrió y su resultado sirve; lo que cambia es que no salió gratis.
		// Es un escalón distinto del naranja, que significa «el oráculo dice REVISAR».
		Fill = FLinearColor(0.95f, 0.82f, 0.16f, 1.0f);
	}
	else if (ResultState == TEXT("warn"))
	{
		Fill = FLinearColor(1.0f, 0.56f, 0.08f, 1.0f);   // naranja GH
	}
	else if (ResultState == TEXT("error"))
	{
		Fill = FLinearColor(0.90f, 0.20f, 0.14f, 1.0f);
	}
	BodyBrush = FSlateRoundedBoxBrush(Fill, 5.0f, StateColor(), 1.4f);
}

int32 SJamGraphNode::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements, int32 LayerId,
	const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	// Componente redondeado detrás de los hijos, insetado para que los grips queden sobre el borde. La
	// franja superior queda libre para la cartela flotante con el nombre (como en las referencias GH).
	const FVector2D Size = AllottedGeometry.GetLocalSize();
	const float BodyW = FMath::Max(0.0f, (float)Size.X - 14.0f);
	const float BodyH = FMath::Max(0.0f, (float)Size.Y - TitleH - 1.0f);
	const float BodyY = TitleH;

	// El RELLENO de un brush sale del `InTint` de MakeBox, NO de `Brush.TintColor`:
	// `FSlateBoxPayload::SetBrush` copia margen/UV/tiling/recurso y nunca mira el tint del brush. El
	// BORDE sí se lee del brush. Omitir el tint pintaba TODOS estos rellenos de blanco opaco: la
	// sombra y el lavanda de la selección no se dibujaron nunca, y el cuerpo salía blanco en vez del
	// gris de `BodyBrush`. Por eso cada relleno pasa su tint explícito.
	//
	// Selección/hover lavanda alrededor del componente, equivalente al rectángulo violeta de GH. El
	// foco propio o de uno de sus controles mantiene visible qué nodo recibirá la tecla Supr.
	if (IsHovered() || bDragging || HasKeyboardFocus() || HasFocusedDescendants()
		|| IsSelectedAttr.Get(false))
	{
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId,
			AllottedGeometry.ToPaintGeometry(
				FVector2D(Size.X - 6.0f, BodyH + 6.0f),
				FSlateLayoutTransform(FVector2D(3.0f, BodyY - 3.0f))),
			&SelectionBrush, ESlateDrawEffect::None,
			SelectionBrush.TintColor.GetSpecifiedColor());
	}

	// Sombra corta inferior: el relieve discreto visible en los componentes clásicos.
	FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 1,
		AllottedGeometry.ToPaintGeometry(
			FVector2D(BodyW, BodyH), FSlateLayoutTransform(FVector2D(8.0f, BodyY + 2.0f))),
		&ShadowBrush, ESlateDrawEffect::None,
		ShadowBrush.TintColor.GetSpecifiedColor());

	const FPaintGeometry PG = AllottedGeometry.ToPaintGeometry(
		FVector2D(BodyW, BodyH), FSlateLayoutTransform(FVector2D(7.0f, BodyY)));
	FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 2, PG, &BodyBrush,
		ESlateDrawEffect::None, BodyBrush.TintColor.GetSpecifiedColor());

	// Bevel suave estilo GH: luz arriba y una sombra corta abajo, insetadas para respetar las esquinas.
	const float R = 5.0f;
	if (BodyW > 2.0f * R && BodyH > 2.0f * R)
	{
		const FVector2D GSize(BodyW - 2.0f * R, BodyH - 2.0f * R);
		const FPaintGeometry GPG = AllottedGeometry.ToPaintGeometry(
			GSize, FSlateLayoutTransform(FVector2D(7.0f + R, BodyY + R)));
		TArray<FSlateGradientStop> Stops;
		Stops.Add(FSlateGradientStop(FVector2D(0.0f, 0.0f), FLinearColor(1.0f, 1.0f, 1.0f, 0.18f)));
		Stops.Add(FSlateGradientStop(FVector2D(0.0f, GSize.Y), FLinearColor(0.0f, 0.0f, 0.0f, 0.10f)));
		FSlateDrawElement::MakeGradient(OutDrawElements, LayerId + 3, GPG, Stops, Orient_Vertical);

		TArray<FVector2D> Hi;
		Hi.Add(FVector2D(7.0f + R, BodyY + 1.5f));
		Hi.Add(FVector2D(7.0f + BodyW - R, BodyY + 1.5f));
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 3, AllottedGeometry.ToPaintGeometry(),
			Hi, ESlateDrawEffect::None, FLinearColor(1.0f, 1.0f, 1.0f, 0.35f), true, 1.0f);
	}

	// Cartela superior: nombre humano del verbo y pequeño pico hacia el cuerpo.
	{
		const FString Title = DisplayName.IsEmpty() ? FriendlyVerbName(Verb) : DisplayName;
		const FSlateFontInfo Font = FCoreStyle::GetDefaultFontStyle("Regular", 8);
		const TSharedRef<FSlateFontMeasure> FM =
			FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
		const FVector2D TS = FM->Measure(Title, Font);
		// Reservar la esquina superior derecha para la × independiente.
		const float LabelW = FMath::Min(BodyW - 42.0f, TS.X + 14.0f);
		const float LabelH = TitleH - 4.0f;
		const float LabelX = (Size.X - LabelW) * 0.5f;
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 4,
			AllottedGeometry.ToPaintGeometry(
				FVector2D(LabelW, LabelH), FSlateLayoutTransform(FVector2D(LabelX, 1.0f))),
			&TitleBrush, ESlateDrawEffect::None,
			TitleBrush.TintColor.GetSpecifiedColor());

		const float Cx = Size.X * 0.5f;
		TArray<FVector2D> Pointer;
		Pointer.Add(FVector2D(Cx - 4.0f, LabelH));
		Pointer.Add(FVector2D(Cx, LabelH + 4.0f));
		Pointer.Add(FVector2D(Cx + 4.0f, LabelH));
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 4,
			AllottedGeometry.ToPaintGeometry(), Pointer, ESlateDrawEffect::None,
			FLinearColor(0.12f, 0.12f, 0.12f, 1.0f), false, 2.0f);

		const FVector2D TopLeft(Cx - TS.X * 0.5f, 1.0f + (LabelH - TS.Y) * 0.5f);
		FSlateDrawElement::MakeText(OutDrawElements, LayerId + 5,
			AllottedGeometry.ToPaintGeometry(TS, FSlateLayoutTransform(TopLeft)), Title, Font,
			ESlateDrawEffect::None, JamInk);
	}

	// Pictograma central del verbo. Si falta el asset o el mapping, conserva el nombre vertical como
	// fallback legible: un error al editar icon-map.json nunca deja un nodo anónimo.
	{
		const float FreeLeft = PinColW + ParamColW;
		const float FreeRight = Size.X - PinColW;
		const float Cx = (FreeLeft + FreeRight) * 0.5f;
		if (IconBrush.IsValid())
		{
			const FVector2D IconSize(24.0f, 24.0f);
			const FVector2D IconAt(Cx - IconSize.X * 0.5f,
				BodyY + BodyH * 0.5f - IconSize.Y * 0.5f);
			FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 5,
				AllottedGeometry.ToPaintGeometry(IconSize, FSlateLayoutTransform(IconAt)),
				IconBrush.Get(), ESlateDrawEffect::None,
				IconBrush->GetTint(InWidgetStyle) * InWidgetStyle.GetColorAndOpacityTint());
		}
		else
		{
			const FString CenterName = DisplayName.IsEmpty() ? FriendlyVerbName(Verb) : DisplayName;
			const FSlateFontInfo CenterFont = FCoreStyle::GetDefaultFontStyle("Bold", 8);
			const TSharedRef<FSlateFontMeasure> FM =
				FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
			const FVector2D NS = FM->Measure(CenterName, CenterFont);
			const FVector2D NameAt(Cx - NS.X * 0.5f, BodyY + BodyH * 0.5f - NS.Y * 0.5f);
			const FPaintGeometry NamePG = AllottedGeometry.ToPaintGeometry(
				NS, FSlateLayoutTransform(NameAt),
				FSlateRenderTransform(FQuat2D(FMath::DegreesToRadians(-90.0f))), FVector2D(0.5f, 0.5f));
			FSlateDrawElement::MakeText(OutDrawElements, LayerId + 5,
				NamePG, CenterName, CenterFont, ESlateDrawEffect::None, JamInk);
		}
	}

	return SCompoundWidget::OnPaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements,
		LayerId + 6, InWidgetStyle, bParentEnabled);
}

void SJamGraphNode::SetResult(const FString& State, const FString& Text)
{
	ResultState = State;
	RebuildBodyBrush();
	SetToolTipText(Text.IsEmpty()
		? FText::FromString(Verb)
		: FText::FromString(FString::Printf(TEXT("%s\n%s"), *Verb, *Text)));
}

FLinearColor SJamGraphNode::StateColor() const
{
	if (ResultState == TEXT("ok"))    { return FLinearColor(0.13f, 0.55f, 0.22f, 1.0f); }
	if (ResultState == TEXT("aviso")) { return FLinearColor(0.80f, 0.68f, 0.10f, 1.0f); }
	if (ResultState == TEXT("warn"))  { return FLinearColor(0.85f, 0.48f, 0.03f, 1.0f); }
	if (ResultState == TEXT("error")) { return FLinearColor(0.80f, 0.12f, 0.12f, 1.0f); }
	return FLinearColor(0.24f, 0.24f, 0.23f, 1.0f);   // neutro: contorno oscuro del componente
}

TMap<FString, FString> SJamGraphNode::GetParamValues() const
{
	TMap<FString, FString> Out;
	for (const TPair<FString, TFunction<FString()>>& G : ParamGetters)
	{
		Out.Add(G.Key, G.Value());
	}
	return Out;
}

void SJamGraphNode::SetParamValues(const TMap<FString, FString>& Values)
{
	for (const TPair<FString, FString>& KV : Values)
	{
		if (const TFunction<void(const FString&)>* S = ParamSetters.Find(KV.Key))
		{
			(*S)(KV.Value);
		}
	}
}

FReply SJamGraphNode::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		// Primero la selección, después el arrastre: así arrastrar un nodo que YA estaba elegido
		// mueve todo el grupo, y arrastrar uno suelto lo convierte antes en la selección.
		OnClickedDelegate.ExecuteIfBound(MouseEvent.IsShiftDown(), MouseEvent.IsControlDown());
		bDragging = true;
		bMovioAlgo = false;
		return FReply::Handled()
			.CaptureMouse(SharedThis(this))
			.SetUserFocus(SharedThis(this), EFocusCause::Mouse);
	}
	return FReply::Unhandled();
}

FReply SJamGraphNode::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
	if (InKeyEvent.GetKey() == EKeys::Delete)
	{
		// Va al editor, que es el único que sabe si hay UNO o VARIOS elegidos: `Supr` sobre un nodo
		// de un grupo tiene que borrar el grupo. La × en cambio siempre borra ESE nodo, que es lo
		// que dice el botón. Un text box enfocado consume Supr antes de que llegue acá.
		if (OnDeleteSelectionDelegate.IsBound())
		{
			OnDeleteSelectionDelegate.Execute();
		}
		else
		{
			OnDeleteClickedDelegate.ExecuteIfBound();
		}
		return FReply::Handled();
	}
	return SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
}

FReply SJamGraphNode::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bDragging && HasMouseCapture())
	{
		// El delta del cursor viene en píxeles de pantalla; el modelo está en unidades locales del
		// canvas → dividir por la escala de layout (DPI) para que el nodo siga al mouse 1:1.
		const float S = MyGeometry.GetAccumulatedLayoutTransform().GetScale();
		const FVector2D Delta = MouseEvent.GetCursorDelta() / (S > 0.0f ? S : 1.0f);
		if (!Delta.IsNearlyZero())
		{
			bMovioAlgo = true;
		}
		OnDragDelta.ExecuteIfBound(Delta);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SJamGraphNode::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bDragging && MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bDragging = false;
		if (bMovioAlgo)
		{
			// UN paso por arrastre, al soltar. Marcarlo por frame llenaría el historial con los
			// cientos de posiciones intermedias de un solo gesto.
			bMovioAlgo = false;
			OnDragEndDelegate.ExecuteIfBound();
		}
		return FReply::Handled().ReleaseMouseCapture();
	}
	return FReply::Unhandled();
}

#undef LOCTEXT_NAMESPACE
