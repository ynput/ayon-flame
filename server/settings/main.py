from ayon_server.settings import BaseSettingsModel, SettingsField

from .imageio import FlameImageIOModel, DEFAULT_IMAGEIO_SETTINGS
from .create_plugins import CreatePluginsModel, DEFAULT_CREATE_SETTINGS
from .publish_plugins import PublishPluginsModel, DEFAULT_PUBLISH_SETTINGS
from .loader_plugins import LoaderPluginsModel, DEFAULT_LOADER_SETTINGS


class InstallOpenTimelineIOToFlameModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        default=True,
        title="Enable"
    )


# hooks configurations
class FlameHooksModel(BaseSettingsModel):
    _layout = "expanded"
    InstallOpenTimelineIOToFlame: InstallOpenTimelineIOToFlameModel = \
        SettingsField(
            default_factory=InstallOpenTimelineIOToFlameModel,
            title="Install OpenTimelineIO to Flame"
        )


class FlameSettings(BaseSettingsModel):
    imageio: FlameImageIOModel = SettingsField(
        default_factory=FlameImageIOModel,
        title="Color Management (ImageIO)"
    )
    hooks: FlameHooksModel = SettingsField(
        default_factory=FlameHooksModel,
        title="Hooks"
    )
    create: CreatePluginsModel = SettingsField(
        default_factory=CreatePluginsModel,
        title="Create plugins"
    )
    publish: PublishPluginsModel = SettingsField(
        default_factory=PublishPluginsModel,
        title="Publish plugins"
    )
    load: LoaderPluginsModel = SettingsField(
        default_factory=LoaderPluginsModel,
        title="Loader plugins"
    )


DEFAULT_VALUES = {
    "imageio": DEFAULT_IMAGEIO_SETTINGS,
    "create": DEFAULT_CREATE_SETTINGS,
    "publish": DEFAULT_PUBLISH_SETTINGS,
    "load": DEFAULT_LOADER_SETTINGS
}
