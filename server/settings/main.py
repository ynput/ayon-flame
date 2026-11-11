from ayon_server.settings import BaseSettingsModel, SettingsField

from .bookmarks import BookmarksModel, DEFAULT_BOOKMARK_SETTINGS
from .imageio import FlameImageIOModel, DEFAULT_IMAGEIO_SETTINGS
from .create_plugins import CreatePluginsModel, DEFAULT_CREATE_SETTINGS
from .publish_plugins import PublishPluginsModel, DEFAULT_PUBLISH_SETTINGS
from .loader_plugins import LoaderPluginsModel, DEFAULT_LOADER_SETTINGS
from .custom_menu import CustomMenuSettings, DEFAULT_CUSTOM_MENU_SETTINGS


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


class UpdateBatchWorkfileModel(BaseSettingsModel):
    """Rewrite the Batch workfile on each Flame project save."""
    enabled: bool = SettingsField(default=True, title="Enabled")


class FlameSettings(BaseSettingsModel):
    bookmarks: BookmarksModel = SettingsField(
        default_factory=BookmarksModel,
        title="Project Bookmarks",
    )
    imageio: FlameImageIOModel = SettingsField(
        default_factory=FlameImageIOModel,
        title="Color Management (ImageIO)"
    )
    hooks: FlameHooksModel = SettingsField(
        default_factory=FlameHooksModel,
        title="Hooks"
    )
    update_batch_workfile: UpdateBatchWorkfileModel = SettingsField(
        default_factory=UpdateBatchWorkfileModel,
        title="Update Batch Workfile on Project Save"
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
    custom_menu: CustomMenuSettings = SettingsField(
        default_factory=CustomMenuSettings,
        title="Custom Menu"
    )


DEFAULT_VALUES = {
    "bookmarks": DEFAULT_BOOKMARK_SETTINGS,
    "imageio": DEFAULT_IMAGEIO_SETTINGS,
    "create": DEFAULT_CREATE_SETTINGS,
    "publish": DEFAULT_PUBLISH_SETTINGS,
    "load": DEFAULT_LOADER_SETTINGS,
    "custom_menu": DEFAULT_CUSTOM_MENU_SETTINGS
}
