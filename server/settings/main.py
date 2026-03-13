from ayon_server.settings import BaseSettingsModel, SettingsField

from .bookmarks import BookmarksModel, DEFAULT_BOOKMARK_SETTINGS
from .imageio import FlameImageIOModel, DEFAULT_IMAGEIO_SETTINGS
from .create_plugins import CreatePluginsModel, DEFAULT_CREATE_SETTINGS
from .publish_plugins import PublishPluginsModel, DEFAULT_PUBLISH_SETTINGS
from .loader_plugins import LoaderPluginsModel, DEFAULT_LOADER_SETTINGS


class ProjectNicknameModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        default=False, title="Enable"
    )
    regex: str = SettingsField("", title="Regex Pattern")
    replacement: str = SettingsField(
        "",
        title="Replacement Pattern",
        description=(
            "'\\U': Uppercase\n"
            "'\\u': Uppercase first letter\n"
            "'\\L': Lowercase\n"
            "'\\l': Lowercase first letter\n"
            "'\\E': Prevent further case change"
        )
    )


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
    nickname: ProjectNicknameModel = SettingsField(
        default_factory=ProjectNicknameModel,
        title="Custom Project Nickname",
        description=(
            "Use this feature to enable custom project nicknames "
            "based off the project name.\n"
            "Use regexes and perl-style replacement patterns to generate a "
            "new nickname.\nFor example, transforming 'project_12345' "
            "into 'PROJECT' would use a regex of '([a-z]+)_\\d+' and a "
            "replacement pattern of '\\U\\1'. "
        )
    )
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
    "bookmarks": DEFAULT_BOOKMARK_SETTINGS,
    "imageio": DEFAULT_IMAGEIO_SETTINGS,
    "create": DEFAULT_CREATE_SETTINGS,
    "publish": DEFAULT_PUBLISH_SETTINGS,
    "load": DEFAULT_LOADER_SETTINGS
}
