from ayon_server.settings import BaseSettingsModel, SettingsField


def item_type_enum_resolver():
    return [
        {"value": "action", "label": "Action"},
        {"value": "menu", "label": "Menu"},
    ]


def menu_item_type_enum_resolver():
    return [
        {"value": "action", "label": "Action"},
    ]


def source_type_enum_resolver():
    return [
        {"value": "python", "label": "Python"},
        {"value": "file", "label": "Python file (set filepath as command)"},
    ]


class ActionModel(BaseSettingsModel):
    """Action Definition"""
    title: str = SettingsField("", title="Title")
    flame_context: str = SettingsField(
        "FlameMenuUniversal",
        title="Flame Context",
        enum_resolver=lambda: [
            "ALL",
            "FlameMenuUniversal",
            "FlameMenuTimeline",
            "FlameMenuBatch",
        ]
    )
    source_type: str = SettingsField(
        "file",
        title="Source Type",
        enum_resolver=source_type_enum_resolver,
        conditional_enum=True,
    )
    python: str = SettingsField(
        "",
        title="Python",
        widget="textarea",
        syntax="python",
    )
    file: str = SettingsField("", title="Filepath")


class MenuItemDefinition(BaseSettingsModel):
    """Item Definition"""
    _layout = "expanded"

    item_type: str = SettingsField(
        "action",
        title="Type",
        enum_resolver=menu_item_type_enum_resolver,
        conditional_enum=True,
    )
    action: ActionModel = ActionModel(
        default_factory=ActionModel,
    )


class MenuItemModel(BaseSettingsModel):
    _layout = "expanded"
    title: str = SettingsField("", title="Title")
    items: list[MenuItemDefinition] = SettingsField(
        default_factory=list,
    )


class CustomMenuItemDefinition(BaseSettingsModel):
    """Custom item Definition"""
    _layout = "expanded"

    item_type: str = SettingsField(
        "action",
        title="Type",
        enum_resolver=item_type_enum_resolver,
        conditional_enum=True,
    )
    action: ActionModel = ActionModel(
        default_factory=ActionModel,
    )
    menu: MenuItemModel = SettingsField(
        default_factory=MenuItemModel,
    )



class CustomMenuSettings(BaseSettingsModel):
    """Flame script menu project settings."""
    _isGroup = True

    name: str = SettingsField(title="Menu name")
    enabled: bool = SettingsField(title="enabled", default=False)
    definition: list[CustomMenuItemDefinition] = SettingsField(
        default_factory=list,
        title="Definition",
        description="Custom Menu Items Definition"
    )


DEFAULT_CUSTOM_MENU_SETTINGS = {
    "name": "Custom Tools",
    "definition": [
        {
            "item_type": "action",
            "action": {
                "title": "AYON Flame Docs",
                "flame_context": "ALL",
                "source_type": "python",
                "python": "import webbrowser\n\nwebbrowser.open(url='https://docs.ayon.dev/features?addons=flame')",
                "file": "",
            }
        }
    ]
}
