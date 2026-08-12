#include "SJamGraphNode.h"

#include "SJamKnob.h"
#include "SJamScrub.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
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
	OnParamLiveDelegate = InArgs._OnParamLive;
	OnDebugChangedDelegate = InArgs._OnDebugChanged;
	OnBypassChangedDelegate = InArgs._OnBypassChanged;
	OnThumbnailOpenDelegate = InArgs._OnThumbnailOpen;
	OnPedirVariablesDelegate = InArgs._OnPedirVariables;
	OnCompactoCambiadoDelegate = InArgs._OnCompactoCambiado;
	bCompacto = InArgs._Compacto;
	bCanBypass = InArgs._CanBypass;
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
				// El NOMBRE del tipo, que es lo que hace que un pin no se identifique sólo por su
				// color. Estaba en 0.30/0.31/0.33 = 2.28:1 sobre el cuerpo — o sea que el texto que
				// reemplaza al color era el que no se leía. Ahora 4.58:1 (ver `ContrasteDelNodoTests`).
				.Text(FText::FromString(InArgs._HasInput ? InArgs._InputLabel : FString()))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.12f, 0.13f, 0.14f, 1.0f)))
			]
			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(InArgs._OutputLabel))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.12f, 0.13f, 0.14f, 1.0f)))
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
				// Changed avisa POR FRAME y sólo lo escucha el live view; el historial se entera al
				// soltar, abajo. Son dos avisos porque son dos preguntas distintas: «¿esto es un paso
				// que se puede deshacer?» y «¿esto cambió lo que hay que mostrar?».
				.OnValueChanged_Lambda([this, Val](float V)
					{ *Val = V; OnParamLiveDelegate.ExecuteIfBound(); })
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
				.OnValueChanged_Lambda([this, H](float V)
					{ *H = V; OnParamLiveDelegate.ExecuteIfBound(); })
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

			// Desplegable de variables, sólo en `expr`. La lista se pide al DESPLEGAR y no al
			// construir el nodo: los nombres cambian con cada tecla que se tipea en un `number`,
			// así que una lista congelada al nacer el nodo mentiría casi siempre.
			//
			// Es un botón AL LADO y no un dropdown que reemplace el campo: `expr` acepta
			// expresiones enteras (`radio * 2`), y cambiarlo por una lista cerrada sacaría eso.
			// PERILLA para los ángulos (el «Control Knob» de Grasshopper). Jam tiene ~50
			// parámetros que son rotaciones —yaw/pitch/roll, ángulos de rama, `start_angle`— y
			// todos se editaban tipeando. Un ángulo es una DIRECCIÓN, no una cantidad: la aguja
			// dice hacia dónde apunta de un vistazo y «137.5» hay que imaginárselo.
			//
			// Va AL LADO del campo y no en su lugar, por el mismo motivo por el que el desplegable
			// de variables no reemplaza a `expr`: una perilla sola sacaría la capacidad de escribir
			// 137,5 exacto y dejaría al usuario peleando con el mouse por medio grado. Es además la
			// postura de riesgo correcta para un widget dibujado a mano — si la aguja pinta mal, el
			// número sigue funcionando.
			//
			// El campo es la ÚNICA fuente de verdad: la perilla lo lee para pintarse y lo escribe
			// al arrastrar. Sin eso habría dos estados del mismo valor y uno se desincronizaría.
			// TIRADOR para arrastrar un número (el «Digit Scroller» de Grasshopper). Jam tiene
			// 505 params numéricos y todos se tipeaban: el campo es un cuadro de texto pelado. Eso
			// no fue un descuido —cualquier param numérico puede llevar una expresión (`=radio * 2`)
			// y un spinbox no puede contenerla— pero deja al usuario tecleando para probar un
			// valor, que es lo contrario de tantear.
			//
			// Va AL LADO, como la perilla y como el desplegable de `expr`: el campo sigue aceptando
			// expresiones y valores exactos, y el tirador agrega lo único que faltaba. No aparece
			// donde ya hay perilla —un ángulo no necesita dos controles— ni donde el spec no dijo
			// que el valor es un número.
			const bool bNumerico = P.Type == TEXT("float") || P.Type == TEXT("int");
			if (bNumerico && P.Unidad != TEXT("grados"))
			{
				Input = SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[ Field ]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					  .Padding(2.0f, 0.0f, 0.0f, 0.0f)
					[
						SNew(SJamScrub)
						.Entero(P.Type == TEXT("int"))
						.ToolTipText(LOCTEXT("TiradorTip",
							"arrastrá para tantear · Shift acomoda a enteros · el campo sigue "
							"aceptando expresiones («=radio * 2») y valores exactos"))
						.TextoActual_Lambda([Field]() { return Field->GetText().ToString(); })
						.OnValueChanged_Lambda([this, Field](float Valor)
						{
							Field->SetText(FText::FromString(
								FString::SanitizeFloat(Valor, /*MinFractionalDigits*/ 0)));
							OnParamLiveDelegate.ExecuteIfBound();
						})
						.OnValueCommitted_Lambda([this](float)
							{ OnParamChangedDelegate.ExecuteIfBound(); })
					];
			}

			if (P.Unidad == TEXT("grados"))
			{
				Input = SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[ Field ]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					  .Padding(3.0f, 0.0f, 0.0f, 0.0f)
					[
						SNew(SJamKnob)
						.Diameter(24.0f)
						.ToolTipText(LOCTEXT("PerillaTip",
							"arrastrá para girar · Shift acomoda de a 5° · el campo sigue "
							"aceptando un valor exacto"))
						.Angle_Lambda([Field]()
							{ return FCString::Atof(*Field->GetText().ToString()); })
						.OnAngleChanged_Lambda([this, Field](float Grados)
						{
							Field->SetText(FText::FromString(
								FString::Printf(TEXT("%.1f"), Grados)));
							// Por frame: el live view recocina mientras se gira.
							OnParamLiveDelegate.ExecuteIfBound();
						})
						// Al soltar: UN paso de historial por arrastre, como los sliders.
						.OnAngleCommitted_Lambda([this](float)
							{ OnParamChangedDelegate.ExecuteIfBound(); })
					];
			}

			if (Key == TEXT("expr"))
			{
				Input = SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[ Field ]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					[
						SNew(SComboButton)
						.ComboButtonStyle(&FAppStyle::Get().GetWidgetStyle<FComboButtonStyle>("SimpleComboButton"))
						.HasDownArrow(true)
						.ToolTipText(LOCTEXT("VariablesTip", "variables del grafo: elegir una la inserta"))
						.OnGetMenuContent_Lambda([this, Field]()
						{
							FMenuBuilder MB(/*bCloseAfterSelection*/ true, nullptr);
							TArray<FString> Nombres;
							if (OnPedirVariablesDelegate.IsBound())
							{
								Nombres = OnPedirVariablesDelegate.Execute();
							}
							if (Nombres.Num() == 0)
							{
								// Un menú vacío no dice nada; esto dice qué hacer para llenarlo.
								MB.AddMenuEntry(
									LOCTEXT("SinVariables", "todavía no hay variables"),
									LOCTEXT("SinVariablesTip",
										"agregá un nodo «number» o «text» y ponele un nombre"),
									FSlateIcon(), FUIAction(), NAME_None, EUserInterfaceActionType::Button);
								return MB.MakeWidget();
							}
							for (const FString& Nombre : Nombres)
							{
								MB.AddMenuEntry(FText::FromString(Nombre), FText::GetEmpty(), FSlateIcon(),
									FUIAction(FExecuteAction::CreateLambda([this, Field, Nombre]()
									{
										// Reemplaza lo que no aporta («0» es el default, y vacío no
										// es nada); si ya hay una expresión, AGREGA en vez de
										// pisarla — perder lo tipeado por elegir del menú sería
										// exactamente lo contrario de una comodidad.
										const FString Actual = Field->GetText().ToString().TrimStartAndEnd();
										const bool bPisar = Actual.IsEmpty() || Actual == TEXT("0");
										Field->SetText(FText::FromString(
											bPisar ? Nombre : Actual + TEXT(" ") + Nombre));
										OnParamChangedDelegate.ExecuteIfBound();
									})));
							}
							return MB.MakeWidget();
						})
					];
			}
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

	// Columna COMPRIMIDA: una letra por fila, en el mismo lugar y con la misma altura que la fila
	// de parámetro que reemplaza. Así los pines siguen alineados y los cables anclan igual.
	TSharedRef<SVerticalBox> LetrasCol = SNew(SVerticalBox);
	LetrasCol->AddSlot().AutoHeight()[ Spacer(PadTop) ];
	LetrasCol->AddSlot().AutoHeight()[ Cell(HeaderH, SNew(SSpacer)) ];
	auto FilaLetra = [&](const FString& Texto, const FString& Tip)
	{
		LetrasCol->AddSlot().AutoHeight()
		[
			Cell(RowH,
				SNew(STextBlock)
				.Text(FText::FromString(Texto))
				.ToolTipText(FText::FromString(Tip))
				.ColorAndOpacity(JamInk)
				.Justification(ETextJustify::Center)
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 8)))
		];
	};
	for (const FJamNodeParam& P : InArgs._Params)
	{
		// El tooltip conserva el nombre COMPLETO: la letra ahorra espacio, no información.
		FilaLetra(P.Letra.IsEmpty() ? P.Name.Left(1).ToUpper() : P.Letra,
			P.Label.IsEmpty() ? P.Name : P.Label);
	}
	for (const FJamNodePin& P : InArgs._InputPins)
	{
		FilaLetra(P.Name.Left(1).ToUpper(), FString::Printf(TEXT("%s (%s)"), *P.Name, *P.TypeLabel));
	}

	// UN solo layout, y lo único que cambia es la columna del medio. Las columnas de NUBS quedan
	// compartidas —un widget Slate no puede tener dos padres, y duplicar los pines habría dejado dos
	// conjuntos que se desincronizan— así que comprimir no puede hacer que un pin deje de conectarse.
	TSharedRef<SHorizontalBox> MainContent = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ LeftCol ] ]
		+ SHorizontalBox::Slot().AutoWidth()
		[
			SNew(SBox)
			.WidthOverride(TAttribute<FOptionalSize>::CreateLambda(
				[this]() { return FOptionalSize(AnchoColumnaCentral()); }))
			[
				// Acá había un `SWidgetSwitcher` que elegía la columna por índice. El editor moría
				// en `DrawPrepass` con «Array index out of bounds: 254 into an array of size 2»
				// dentro de un `TOneDynamicChildBase<…, TSlateAttribute<int>>`, que es su firma.
				//
				// Se intentó dos veces arreglar el índice —diferir la creación del nodo, y cambiar
				// el `[this]` crudo del lambda por un puntero débil con clamp— y el crash volvió
				// igual las dos veces. En vez de seguir afinando el índice se saca el índice: dos
				// hijos con `Visibility` hacen lo mismo y no hay entero que pueda quedar fuera de
				// rango. Si el crash SIGUE después de esto, el switcher que revienta no es de Jam
				// —es el único que había— y hay que buscarlo en el editor.
				SNew(SOverlay)
				+ SOverlay::Slot()
				[
					SAssignNew(ColumnaParams, SBox)
					.Visibility(bCompacto ? EVisibility::Collapsed : EVisibility::Visible)
					[ ParamCol ]
				]
				+ SOverlay::Slot()
				[
					SAssignNew(ColumnaLetras, SBox)
					.Visibility(bCompacto ? EVisibility::Visible : EVisibility::Collapsed)
					[ LetrasCol ]
				]
			]
		]
		+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]   // centro: icono (OnPaint)
		+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(PinColW)[ RightCol ] ];

	ChildSlot
	[
		SNew(SOverlay)
		+ SOverlay::Slot()[ MainContent ]
		// Veredicto del oráculo, EN EL CANVAS y no sólo en el color: `✓ ⚠ ✗ !`. Es la regla de
		// accesibilidad del proyecto —ningún estado se distingue sólo por color—; hasta acá el
		// veredicto vivía en el color del cuerpo y en un tooltip que había que hoverear.
		// Va a la izquierda porque la derecha ya la ocupan bypass, debug y la ×.
		+ SOverlay::Slot()
		.HAlign(HAlign_Left)
		.VAlign(VAlign_Top)
		.Padding(3.0f, 1.0f, 0.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(16.0f).HeightOverride(16.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([this]() { return FText::FromString(StateGlyph()); })
				.ToolTipText_Lambda([this]()
				{
					// El nombre del estado en palabras: el glifo dice CUÁL, esto dice QUÉ significa.
					if (ResultState == TEXT("ok"))    { return LOCTEXT("VeredictoOk", "el oráculo dice OK"); }
					if (ResultState == TEXT("aviso")) { return LOCTEXT("VeredictoAviso", "corrió, pero algo hay que mirar"); }
					if (ResultState == TEXT("warn"))  { return LOCTEXT("VeredictoWarn", "el oráculo dice REVISAR: el resultado no sirve"); }
					if (ResultState == TEXT("error")) { return LOCTEXT("VeredictoError", "reventó: no hay resultado"); }
					if (ResultState == TEXT("omitido")) { return LOCTEXT("VeredictoOmitido",
						"no corrió: se está viendo otro nodo (apagá su ◉ para correr todo)"); }
					return LOCTEXT("VeredictoNada", "todavía no corrió");
				})
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
				.ColorAndOpacity_Lambda([this]() { return FSlateColor(StateColor()); })
			]
		]
		// Los tres botones de vista comparten criterio de color: PRENDIDO su tono, APAGADO la
		// tinta del nodo — y los dos a opacidad plena. Antes el apagado iba al 45% y el prendido
		// usaba tonos claros; medidos contra el cuerpo daban entre 1.15:1 y 1.40:1, o sea
		// invisibles. Los tonos de ahora son oscuros y pasan WCAG AA (ver `ContrasteDelNodoTests`).
		// Desvanecer el apagado no hacía falta: la forma ya es hueca contra llena.
		// Comprimir: el nodo se reduce a una letra por pin y su icono. NO cambia el grafo, sólo
		// cómo se lo ve — por eso es un botón de vista y no toca el historial de otra forma.
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(0.0f, 1.0f, 68.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(20.0f).HeightOverride(18.0f)
			[
				SNew(SButton)
				.ButtonStyle(&FAppStyle::Get(), "NoBorder")
				.ToolTipText(LOCTEXT("CompactoFlag",
					"comprimir el nodo: una letra por pin y el icono, sin campos"))
				.ContentPadding(FMargin(0.0f))
				.HAlign(HAlign_Center).VAlign(VAlign_Center)
				.OnClicked_Lambda([this]()
				{
					SetCompacto(!bCompacto);
					OnCompactoCambiadoDelegate.ExecuteIfBound();
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					// Triángulos: cerrar/abrir. La FORMA cambia, no sólo el color — y los dos están
					// en DroidSansFallback (ver `GlifosQueLaFuenteTieneTests`).
					.Text_Lambda([this]() { return FText::FromString(bCompacto ? TEXT("▲") : TEXT("△")); })
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
					.ColorAndOpacity_Lambda([this]()
					{
						return bCompacto ? FSlateColor(FLinearColor(0.03f, 0.16f, 0.07f))
						                 : FSlateColor(JamInk);
					})
				]
			]
		]
		// Bypass: apaga el nodo sin sacarlo del grafo. Sólo aparece donde es LEGAL (mismo tipo de
		// entrada y salida); en el resto ni se dibuja, porque una opción que no se puede usar
		// confunde más que ayuda.
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(0.0f, 1.0f, 46.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(20.0f).HeightOverride(18.0f)
			.Visibility(bCanBypass ? EVisibility::Visible : EVisibility::Collapsed)
			[
				SNew(SButton)
				.ButtonStyle(&FAppStyle::Get(), "NoBorder")
				.ToolTipText(LOCTEXT("BypassFlag",
					"apagar este nodo (D): sigue cableado, pero no corre — el stream lo atraviesa"))
				.ContentPadding(FMargin(0.0f))
				.HAlign(HAlign_Center).VAlign(VAlign_Center)
				.OnClicked_Lambda([this]()
				{
					SetBypassed(!bBypassed);
					// A diferencia del debug, esto cambia lo que el grafo HACE: es un paso de undo.
					OnBypassChangedDelegate.ExecuteIfBound();
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					// La FORMA cambia, no sólo el color: es la regla de accesibilidad del roadmap
					// —ningún estado se distingue únicamente por color— y acá sale gratis.
					//
					// CUADRADOS y no círculos: el botón de al lado (debug) usa ◉/○, y dos pares de
					// círculos serían dos botones idénticos a un metro de distancia. Lleno = el
					// flag está PRENDIDO, igual que en debug.
					//
					// Los glifos salen de DroidSansFallback, que es la fuente de respaldo que Slate
					// sí tiene en la cadena. El par anterior (⏻/⊘) no lo cubría NINGUNA fuente del
					// motor y se dibujaba como el rombo con «?» de LastResort.
					.Text_Lambda([this]() { return FText::FromString(bBypassed ? TEXT("■") : TEXT("□")); })
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
					.ColorAndOpacity_Lambda([this]()
					{
						return bBypassed ? FSlateColor(FLinearColor(0.04f, 0.10f, 0.34f))
						                 : FSlateColor(JamInk);
					})
				]
			]
		]
		// Flag de debug: se prende el nodo que YA está, sin agregar ni cablear nada. Es el display
		// flag de Houdini / la tecla D de PCG, y no el nodo de debug aparte que había antes.
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(0.0f, 1.0f, 24.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(20.0f).HeightOverride(18.0f)
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
					// Pero ahora marcar RECORTA lo que corre, así que el editor tiene que enterarse:
					// es él quien apaga los otros —el display flag de Houdini se MUEVE, no se
					// acumula— y quien vuelve a cocinar si el live view está prendido.
					OnDebugChangedDelegate.ExecuteIfBound();
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					.Text_Lambda([this]() { return FText::FromString(bDebugEnabled ? TEXT("◉") : TEXT("○")); })
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 12))
					.ColorAndOpacity_Lambda([this]()
					{
						return bDebugEnabled ? FSlateColor(FLinearColor(0.22f, 0.10f, 0.01f))
						                     : FSlateColor(JamInk);
					})
				]
			]
		]
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(0.0f, 1.0f, 2.0f, 0.0f)
		[
			SNew(SBox).WidthOverride(20.0f).HeightOverride(18.0f)
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

FSlateRect SJamGraphNode::ThumbnailRect(const FVector2D& LocalSize) const
{
	if (ThumbnailBrush == nullptr)
	{
		return FSlateRect(0.0f, 0.0f, 0.0f, 0.0f);
	}
	const float BodyH = FMath::Max(0.0f, (float)LocalSize.Y - TitleH - 1.0f);
	const float BodyY = TitleH;
	const float FreeLeft = PinColW + AnchoColumnaCentral();
	const float FreeRight = (float)LocalSize.X - PinColW;
	const float Cx = (FreeLeft + FreeRight) * 0.5f;
	// Se estira a lo que entre: los nodos de Jam no miden todos igual y un tamaño fijo se saldría
	// del cuerpo en los más chatos.
	const float Lado = FMath::Min(FreeRight - FreeLeft - 6.0f, BodyH - 8.0f);
	if (Lado < 12.0f)
	{
		return FSlateRect(0.0f, 0.0f, 0.0f, 0.0f);
	}
	const float X = Cx - Lado * 0.5f;
	const float Y = BodyY + BodyH * 0.5f - Lado * 0.5f;
	return FSlateRect(X, Y, X + Lado, Y + Lado);
}

FReply SJamGraphNode::OnMouseButtonDoubleClick(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	// Doble clic SOBRE LA MINIATURA abre el visor grande; en el resto del nodo no hace nada y el
	// gesto sigue siendo el de siempre (arrastrar desde cualquier zona libre).
	const FSlateRect Rect = ThumbnailRect(MyGeometry.GetLocalSize());
	const FVector2D Local = MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
	if (Rect.GetArea() > 0.0f && Rect.ContainsPoint(Local))
	{
		OnThumbnailOpenDelegate.ExecuteIfBound();
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

void SJamGraphNode::SetCompacto(bool bEnabled)
{
	if (bEnabled == bCompacto)
	{
		return;
	}
	bCompacto = bEnabled;
	// La visibilidad se cambia A MANO y no por atributo. Con un lambda de `Visibility` el nodo
	// quedaba mostrando la columna compacta con el TAMAÑO de la normal, y después el botón ya no
	// lo devolvía: invalidar no alcanza para que Slate reevalúe una visibilidad cacheada. Los
	// campos de valor siguen VIVOS detrás, con lo que hubieras tipeado.
	if (ColumnaParams.IsValid())
	{
		ColumnaParams->SetVisibility(bCompacto ? EVisibility::Collapsed : EVisibility::Visible);
	}
	if (ColumnaLetras.IsValid())
	{
		ColumnaLetras->SetVisibility(bCompacto ? EVisibility::Visible : EVisibility::Collapsed);
	}
	Invalidate(EInvalidateWidgetReason::LayoutAndVolatility);
}

void SJamGraphNode::SetBypassed(bool bEnabled)
{
	// Se ignora en un verbo que no lo admite: cargar un `.jamgraph` con el flag mal puesto no debe
	// dejar el canvas mostrando un apagado que Compile va a rechazar igual.
	const bool bNuevo = bEnabled && bCanBypass;
	if (bNuevo == bBypassed)
	{
		return;
	}
	bBypassed = bNuevo;
	RebuildBodyBrush();
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
		// Naranja GH, ACLARADO hasta pasar WCAG AA con la tinta oscura: el original daba 4.44 y el
		// mínimo es 4.5. Justo los estados que avisan de un problema eran los menos legibles.
		Fill = FLinearColor(1.0f, 0.64f, 0.24f, 1.0f);
	}
	else if (ResultState == TEXT("error"))
	{
		// Un rojo saturado no llega a AA con NINGUNA tinta: el original daba 2.62 con la oscura y
		// 2.66 con blanca. Tenía que aclararse. El significado no se pierde — lo llevan además el
		// borde (`StateColor`) y el símbolo `!` del veredicto.
		Fill = FLinearColor(1.0f, 0.58f, 0.54f, 1.0f);
	}
	if (bBypassed)
	{
		// Apagado: el cuerpo se desatura y se aclara, como un componente deshabilitado. Pisa al
		// veredicto a propósito — un nodo que no corrió no tiene veredicto que mostrar, y dejar el
		// verde de la corrida anterior diría que hizo algo.
		const float Gris = Fill.R * 0.30f + Fill.G * 0.59f + Fill.B * 0.11f;
		Fill = FMath::Lerp(FLinearColor(Gris, Gris, Gris, 1.0f),
			FLinearColor(0.88f, 0.88f, 0.87f, 1.0f), 0.55f);
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
		// Ya NO hay que reservar la esquina derecha: la cartela subió y los botones tienen su
		// propia fila, así que un nombre largo puede usar casi todo el ancho.
		const float LabelW = FMath::Min(BodyW - 10.0f, TS.X + 14.0f);
		const float LabelH = TitleH - 4.0f;
		const float LabelX = (Size.X - LabelW) * 0.5f;
		// Negativo: la cartela flota POR ENCIMA del nodo. No entra en `NodeHeight`, así que ningún
		// pin se movió y los cables siguen anclando donde estaban.
		const float LabelY = 1.0f - TitleFloatUp;
		FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 4,
			AllottedGeometry.ToPaintGeometry(
				FVector2D(LabelW, LabelH), FSlateLayoutTransform(FVector2D(LabelX, LabelY))),
			&TitleBrush, ESlateDrawEffect::None,
			TitleBrush.TintColor.GetSpecifiedColor());

		const float Cx = Size.X * 0.5f;
		// Guía de la cartela al cuerpo: sin ella el nombre quedaría flotando suelto y, con nodos
		// cerca, no se sabría de cuál es.
		TArray<FVector2D> Guia;
		Guia.Add(FVector2D(Cx, LabelY + LabelH));
		Guia.Add(FVector2D(Cx, TitleH - 5.0f));
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 4,
			AllottedGeometry.ToPaintGeometry(), Guia, ESlateDrawEffect::None,
			FLinearColor(0.12f, 0.12f, 0.12f, 0.55f), true, 1.2f);

		TArray<FVector2D> Pointer;
		Pointer.Add(FVector2D(Cx - 4.0f, TitleH - 5.0f));
		Pointer.Add(FVector2D(Cx, TitleH - 1.0f));
		Pointer.Add(FVector2D(Cx + 4.0f, TitleH - 5.0f));
		FSlateDrawElement::MakeLines(OutDrawElements, LayerId + 4,
			AllottedGeometry.ToPaintGeometry(), Pointer, ESlateDrawEffect::None,
			FLinearColor(0.12f, 0.12f, 0.12f, 1.0f), false, 2.0f);

		const FVector2D TopLeft(Cx - TS.X * 0.5f, LabelY + (LabelH - TS.Y) * 0.5f);
		FSlateDrawElement::MakeText(OutDrawElements, LayerId + 5,
			AllottedGeometry.ToPaintGeometry(TS, FSlateLayoutTransform(TopLeft)), Title, Font,
			ESlateDrawEffect::None, JamInk);
	}

	// Pictograma central del verbo. Si falta el asset o el mapping, conserva el nombre vertical como
	// fallback legible: un error al editar icon-map.json nunca deja un nodo anónimo.
	{
		const float FreeLeft = PinColW + AnchoColumnaCentral();
		const float FreeRight = Size.X - PinColW;
		const float Cx = (FreeLeft + FreeRight) * 0.5f;
		// Miniatura de lo que el nodo PRODUJO, como en Substance Designer: cuando existe, el nodo
		// deja de mostrar un glifo genérico y muestra su resultado. Ocupa la misma zona libre que el
		// icono —no cambia la geometría del nodo— y se estira a lo que entre: los nodos de Jam no
		// miden todos igual, así que un tamaño fijo se saldría del cuerpo en los más chatos.
		if (const FSlateRect Thumb = ThumbnailRect(Size); Thumb.GetArea() > 0.0f)
		{
			FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 5,
				AllottedGeometry.ToPaintGeometry(
					FVector2D(Thumb.GetSize().X, Thumb.GetSize().Y),
					FSlateLayoutTransform(FVector2D(Thumb.Left, Thumb.Top))),
				ThumbnailBrush, ESlateDrawEffect::None,
				InWidgetStyle.GetColorAndOpacityTint());
		}
		else if (IconBrush.IsValid())
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

FString SJamGraphNode::StateGlyph() const
{
	// Un símbolo POR ESTADO, y los cuatro distintos entre sí: si dos compartieran glifo, el color
	// volvería a ser el único canal para separarlos y no habríamos ganado nada.
	// Son los mismos que `jam.graph` ya emite en el texto del reporte.
	if (ResultState == TEXT("ok"))    { return TEXT("✓"); }
	// Triángulo y no ⚠: el de advertencia sólo lo cubre la fuente de EMOJI, así que salía a color
	// o como rombo vacío. Éste está en DroidSansFallback, que es la que Slate tiene en la cadena.
	if (ResultState == TEXT("aviso")) { return TEXT("▲"); }
	if (ResultState == TEXT("warn"))  { return TEXT("✗"); }   // el oráculo dice REVISAR
	if (ResultState == TEXT("error")) { return TEXT("!"); }   // reventó: no hay resultado
	// Omitido: no corrió porque se está viendo OTRO nodo. Necesita glifo propio y no quedar como
	// «sin veredicto»: son dos cosas distintas —uno nunca corrió, el otro fue excluido a propósito—
	// y sin distinguirlas el usuario no puede saber si su nodo está roto o simplemente apagado.
	if (ResultState == TEXT("omitido")) { return TEXT("–"); }
	return FString();   // todavía no corrió: no hay veredicto que mostrar
}

FLinearColor SJamGraphNode::StateColor() const
{
	if (bBypassed)                    { return FLinearColor(0.35f, 0.55f, 0.95f, 1.0f); }   // azul: apagado
	if (ResultState == TEXT("ok"))    { return FLinearColor(0.13f, 0.55f, 0.22f, 1.0f); }
	if (ResultState == TEXT("aviso")) { return FLinearColor(0.80f, 0.68f, 0.10f, 1.0f); }
	if (ResultState == TEXT("warn"))  { return FLinearColor(0.85f, 0.48f, 0.03f, 1.0f); }
	if (ResultState == TEXT("error")) { return FLinearColor(0.80f, 0.12f, 0.12f, 1.0f); }
	if (ResultState == TEXT("omitido")) { return FLinearColor(0.45f, 0.44f, 0.42f, 1.0f); }   // gris: fuera del recorte
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
