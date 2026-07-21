from ayon_server.settings import BaseSettingsModel, SettingsField


class ScriptsmenuSubmodel(BaseSettingsModel):
    """Item Definition"""
    _isGroup = True

    title: str = SettingsField("", title="Title")
    command: str = SettingsField("", title="Command")
    flame_context: str = SettingsField(
        default_factory=str,
        title="Flame Context",
        enum_resolver=lambda: [
            "FlameMenuUniversal",
            "FlameMenuTimeline",
            "FlameMenuBatch",
        ]
    )


class ScriptsmenuSettings(BaseSettingsModel):
    """Flame script menu project settings."""
    _isGroup = True

    name: str = SettingsField("Custom Tools", title="Script Menu Name")
    enabled: bool = SettingsField(title="enabled", default=False)
    definitions: list[ScriptsmenuSubmodel] = SettingsField(
        default_factory=list,
        title="Definitions",
        description="Script Menu Definition"
    )


DEFAULT_SCRIPTSMENU_SETTINGS = {
    "name": "Custom Tools",
    "enabled": False,
    "definitions": [
        {
            "title": "Ayon Flame Docs",
            "flame_context": "FlameMenuUniversal",
            "command": "import webbrowser;webbrowser.open(url='https://docs.ayon.dev/features?addons=flame')",  # noqa
        }
    ]
}
