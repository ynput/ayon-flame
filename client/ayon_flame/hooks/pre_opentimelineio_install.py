import subprocess

from ayon_applications import (
    PreLaunchHook, LaunchTypes, ApplicationLaunchFailed)


class InstallOpenTimelineIOToFlame(PreLaunchHook):
    """Automatically install OpenTimelineIO to Flame python environment."""

    app_groups = {"flame"}
    order = 2
    launch_types = {LaunchTypes.local}

    def execute(self):
        # Prelaunch hook is not crucial
        try:
            settings = self.data["project_settings"]["flame"]
            hook_settings = settings["hooks"]["InstallOpenTimelineIOToFlame"]
            if not hook_settings["enabled"]:
                return
            self.inner_execute()
        except Exception:
            self.log.warning(
                f"Processing of '{self.__class__.__name__}' crashed.",
                exc_info=True
            )

    def inner_execute(self):
        self.log.debug("Check for OpenTimelineIO installation.")

        flame_py_exe = self.data.get("flame_python_executable")
        if not flame_py_exe:
            self.log.warning("Flame python executable not found.")
            return

        env = self.launch_context.env
        # first try if OpenTimeline is installed into Flame python environment
        result = subprocess.run(
            [flame_py_exe, "-c", "import opentimelineio"], env=env
        )
        if result.returncode == 0:
            self.log.info("OpenTimelineIO is installed within Flame env.")
            return

        # Install it otherwise.
        result = subprocess.run(
            [
                flame_py_exe,
                "-m",
                "pip",
                "install",
                "opentimelineio",
            ]
        )
        if result.returncode == 0:
            self.log.info(
                "OpenTimelineIO is installed now within AYON Flame "
                "env and ready to be used."
            )
            return

        raise ApplicationLaunchFailed("Failed to install OpenTimelineIO")
