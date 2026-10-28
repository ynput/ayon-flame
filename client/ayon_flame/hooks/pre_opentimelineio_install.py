from ayon_applications import PreLaunchHook, LaunchTypes

from ayon_editorial.lib.otio_install import OTIOInstallHookMixin


class InstallOpenTimelineIOToFlame(OTIOInstallHookMixin, PreLaunchHook):
    """Automatically install OpenTimelineIO to Flame python environment."""

    app_groups = {"flame"}
    order = 2
    launch_types = {LaunchTypes.local}

    settings_category = "flame"
    # Keeps the existing per-interpreter install folders of ayon_flame.
    resources_addon_name = "ayon_flame"

    def get_python_executable(self):
        return self.data.get("flame_python_executable")
