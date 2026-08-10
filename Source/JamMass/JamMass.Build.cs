// Puente runtime mínimo entre las recetas puras de Jam y MassEntity.
using UnrealBuildTool;

public class JamMass : ModuleRules
{
	public JamMass(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Json",
			"MassCore",
			"MassEntity",
			"MassActors",
			"MassLOD",
			"MassRepresentation",
			"MassSpawner",
		});
	}
}
