#include "JamMassLibrary.h"

#include "Engine/World.h"
#include "Modules/ModuleManager.h"

class FJamMassModule final : public IModuleInterface
{
public:
	virtual void StartupModule() override
	{
		WorldCleanupHandle = FWorldDelegates::OnWorldCleanup.AddRaw(
			this, &FJamMassModule::OnWorldCleanup);
	}

	virtual void ShutdownModule() override
	{
		FWorldDelegates::OnWorldCleanup.Remove(WorldCleanupHandle);
		UJamMassLibrary::ClearAllPopulations();
	}

private:
	void OnWorldCleanup(UWorld* World, bool, bool)
	{
		UJamMassLibrary::ClearAllPopulations(World);
	}

	FDelegateHandle WorldCleanupHandle;
};

IMPLEMENT_MODULE(FJamMassModule, JamMass)
