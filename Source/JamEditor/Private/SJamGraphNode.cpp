#include "SJamGraphNode.h"

#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/AppStyle.h"

#define LOCTEXT_NAMESPACE "JamGraphNode"

void SJamGraphNode::Construct(const FArguments& InArgs)
{
	Verb = InArgs._Verb;
	OnDragDelta = InArgs._OnDragDelta;

	TSharedRef<SVerticalBox> Params = SNew(SVerticalBox);
	for (const FJamNodeParam& P : InArgs._Params)
	{
		const FString Key = P.Key;
		TSharedPtr<SEditableTextBox> Field;
		Params->AddSlot()
			.AutoHeight()
			.Padding(2.0f, 1.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(0.45f).VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::FromString(Key))
				]
				+ SHorizontalBox::Slot().FillWidth(0.55f)
				[
					SAssignNew(Field, SEditableTextBox).Text(FText::FromString(P.Value))
				]
			];
		Fields.Add(Key, Field);
	}

	ChildSlot
	[
		SNew(SBorder)
		.BorderImage(FAppStyle::GetBrush("Menu.Background"))
		.Padding(0.0f)
		[
			SNew(SVerticalBox)

			// Header: pin entrada · verbo (zona de arrastre) · borrar · pin salida
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SBorder)
				.BorderImage(FAppStyle::GetBrush("Brushes.Header"))
				.Padding(2.0f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					[
						SNew(SButton)
						.ToolTipText(LOCTEXT("InPin", "entrada (clic para conectar)"))
						.ContentPadding(FMargin(2.0f, 0.0f))
						.OnClicked_Lambda([this]() { OnInputClickedDelegate.ExecuteIfBound(); return FReply::Handled(); })
						[ SNew(STextBlock).Text(FText::FromString(TEXT("○"))) ]
					]
					+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(4.0f, 0.0f)
					[
						SNew(STextBlock).Text(FText::FromString(Verb))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					[
						SNew(SButton)
						.ToolTipText(LOCTEXT("Del", "borrar nodo"))
						.ContentPadding(FMargin(2.0f, 0.0f))
						.OnClicked_Lambda([this]() { OnDeleteClickedDelegate.ExecuteIfBound(); return FReply::Handled(); })
						[ SNew(STextBlock).Text(FText::FromString(TEXT("×"))) ]
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					[
						SNew(SButton)
						.ToolTipText(LOCTEXT("OutPin", "salida (clic para conectar)"))
						.ContentPadding(FMargin(2.0f, 0.0f))
						.OnClicked_Lambda([this]() { OnOutputClickedDelegate.ExecuteIfBound(); return FReply::Handled(); })
						[ SNew(STextBlock).Text(FText::FromString(TEXT("○"))) ]
					]
				]
			]

			// Cuerpo: params
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(2.0f)
			[
				Params
			]
		]
	];

	OnInputClickedDelegate = InArgs._OnInputClicked;
	OnOutputClickedDelegate = InArgs._OnOutputClicked;
	OnDeleteClickedDelegate = InArgs._OnDeleteClicked;
}

TMap<FString, FString> SJamGraphNode::GetParamValues() const
{
	TMap<FString, FString> Out;
	for (const TPair<FString, TSharedPtr<SEditableTextBox>>& F : Fields)
	{
		if (F.Value.IsValid())
		{
			Out.Add(F.Key, F.Value->GetText().ToString());
		}
	}
	return Out;
}

FReply SJamGraphNode::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bDragging = true;
		return FReply::Handled().CaptureMouse(SharedThis(this));
	}
	return FReply::Unhandled();
}

FReply SJamGraphNode::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	if (bDragging && HasMouseCapture())
	{
		// El delta del cursor viene en píxeles de pantalla; el modelo está en unidades locales del
		// canvas → dividir por la escala de layout (DPI) para que el nodo siga al mouse 1:1.
		const float S = MyGeometry.GetAccumulatedLayoutTransform().GetScale();
		const FVector2D Delta = MouseEvent.GetCursorDelta() / (S > 0.0f ? S : 1.0f);
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
		return FReply::Handled().ReleaseMouseCapture();
	}
	return FReply::Unhandled();
}

#undef LOCTEXT_NAMESPACE
