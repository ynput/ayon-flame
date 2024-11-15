import os
import subprocess
import appdirs

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
            settings = self.data["project_settings"][self.host_name]
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

        # secondly if OpenTimelineIO is installed in our custom site-packages
        custom_site_path = self.get_custom_site_path()

        # make sure the custom site-packages exists
        os.makedirs(custom_site_path, exist_ok=True)

        # add custom site-packages to PYTHONPATH
        env["PYTHONPATH"] += f"{os.pathsep}{custom_site_path}"
        result = subprocess.run(
            [flame_py_exe, "-c", "import opentimelineio"], env=env
        )
        if result.returncode == 0:
            self.log.info(
                "OpenTimelineIO is installed within AYON Flame env.")
            return

        # lastly install OpenTimelineIO into our custom site-packages
        result = subprocess.run(
            [
                flame_py_exe,
                "-m",
                "pip",
                "install",
                "opentimelineio",
                "-t",
                custom_site_path,
            ]
        )
        if result.returncode == 0:
            self.log.info(
                "OpenTimelineIO is installed now within AYON Flame "
                "env and ready to be used."
            )
            return

        raise ApplicationLaunchFailed("Failed to install OpenTimelineIO")

    def get_custom_site_path(self):
        return appdirs.user_data_dir("ayon_flame", "Ynput")
