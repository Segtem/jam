// Módulo de editor del plugin Jam: tab Slate nativo (consola DSL) que llama al Python de Jam.
using UnrealBuildTool;

public class JamEditor : ModuleRules
{
	public JamEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"CoreUObject",
			"Engine",
			"Slate",
			"SlateCore",
			"UnrealEd",
			"ToolMenus",
			"InputCore",
			"Projects",
			"Json",
			"AssetRegistry",
			"PythonScriptPlugin",
			"DesktopPlatform",   // diálogos Abrir/Guardar diagrama
			"ApplicationCore",       // portapapeles del sistema (copiar/pegar nodos)
			"WorkspaceMenuStructure", // categoría de los paneles en Window ▸ Tools
			"AppFramework",          // OpenColorPicker (color por caja de comentario/grupo)
		});
	}
}
