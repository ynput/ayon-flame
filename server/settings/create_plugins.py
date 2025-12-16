from ayon_server.settings import BaseSettingsModel, SettingsField


def create_shot_clip_overrides_enum() -> list[dict[str, str]]:
    return [
        {"value": "hierarchy", "label": "Shot parent hierarchy"},
        {"value": "useShotName", "label": "Use Shot Name"},
        {"value": "clipRename", "label": "Rename Clips"},
        {"value": "clipName", "label": "Clip name template"},
        {"value": "segmentIndex", "label": "Accept segment order"},
        {"value": "countFrom", "label": "Count sequence from"},
        {"value": "countSteps", "label": "Stepping number"},
        {"value": "folder", "label": "{folder}"},
        {"value": "episode", "label": "{episode}"},
        {"value": "sequence", "label": "{sequence}"},
        {"value": "track", "label": "{track}"},
        {"value": "shot", "label": "{shot}"},
        {"value": "vSyncOn", "label": "Enable Vertical Sync"},
        {"value": "export_audio", "label": "Include audio"},
        {"value": "sourceResolution", "label": "Source resolution"},
        {"value": "workfileFrameStart", "label": "Workfiles Start Frame"},
        {"value": "handleStart", "label": "Handle start (head)"},
        {"value": "handleEnd", "label": "Handle end (tail)"},
        {"value": "includeHandles", "label": "Enable handles including"},
        {"value": "retimedHandles", "label": "Enable retimed handles"},
        {"value": "retimedFramerange", "label": "Enable retimed shot frameranges"},
    ]


class CreateShotClipModel(BaseSettingsModel):
    hierarchy: str = SettingsField(
        "shot",
        title="Shot parent hierarchy",
        section="Shot Hierarchy And Rename Settings"
    )
    useShotName: bool = SettingsField(
        True,
        title="Use Shot Name",
    )
    clipRename: bool = SettingsField(
        False,
        title="Rename clips",
    )
    clipName: str = SettingsField(
        "{sequence}{shot}",
        title="Clip name template"
    )
    segmentIndex: bool = SettingsField(
        True,
        title="Accept segment order"
    )
    countFrom: int = SettingsField(
        10,
        title="Count sequence from"
    )
    countSteps: int = SettingsField(
        10,
        title="Stepping number"
    )

    folder: str = SettingsField(
        "shots",
        title="{folder}",
        section="Shot Template Keywords"
    )
    episode: str = SettingsField(
        "ep01",
        title="{episode}"
    )
    sequence: str = SettingsField(
        "a",
        title="{sequence}"
    )
    track: str = SettingsField(
        "{_track_}",
        title="{track}"
    )
    shot: str = SettingsField(
        "####",
        title="{shot}"
    )

    vSyncOn: bool = SettingsField(
        False,
        title="Enable Vertical Sync",
        section="Vertical Synchronization Of Attributes"
    )

    export_audio: bool = SettingsField(
        False,
        title="Include audio",
    )

    sourceResolution: bool = SettingsField(
        False,
        title="Source resolution",
    )

    workfileFrameStart: int = SettingsField(
        1001,
        title="Workfiles Start Frame",
        section="Shot Attributes"
    )
    handleStart: int = SettingsField(
        10,
        title="Handle start (head)"
    )
    handleEnd: int = SettingsField(
        10,
        title="Handle end (tail)"
    )
    includeHandles: bool = SettingsField(
        False,
        title="Enable handles including"
    )
    retimedHandles: bool = SettingsField(
        True,
        title="Enable retimed handles"
    )
    retimedFramerange: bool = SettingsField(
        True,
        title="Enable retimed shot frameranges"
    )
    overrides: list[str] = SettingsField(
        section="Exposed overrides",
        title="Exposed Overrides",
        description=(
            "Expose the attribute in this list to the user when publishing."
        ),
        enum_resolver=create_shot_clip_overrides_enum,
        default_factory=list,
    )

class CollectShotClipInstancesModels(BaseSettingsModel):
    collectSelectedInstance: bool = SettingsField(
        False,
        title="Collect only instances from selected clips.",
        description=(
            "This feature allows to restrict instance "
            "collection to selected timeline clips "
            "in the active sequence."
        )
    )

class CreatePluginsModel(BaseSettingsModel):
    CreateShotClip: CreateShotClipModel = SettingsField(
        default_factory=CreateShotClipModel,
        title="Create Shot Clip"
    )
    CollectShotClip: CollectShotClipInstancesModels = SettingsField(
        default_factory=CollectShotClipInstancesModels,
        title="Collect Shot Clip instances"
    )


DEFAULT_CREATE_SETTINGS = {
    "CreateShotClip": {
        "hierarchy": "{folder}/{sequence}",
        "useShotName": True,
        "clipRename": False,
        "clipName": "{sequence}{shot}",
        "segmentIndex": True,
        "countFrom": 10,
        "countSteps": 10,
        "folder": "shots",
        "episode": "ep01",
        "sequence": "a",
        "track": "{_track_}",
        "shot": "####",
        "vSyncOn": False,
        "workfileFrameStart": 1001,
        "handleStart": 5,
        "handleEnd": 5,
        "includeHandles": False,
        "retimedHandles": True,
        "retimedFramerange": True,
        "overrides": [
            # Expose all by default
            "hierarchy",
            "useShotName",
            "clipRename",
            "clipName",
            "segmentIndex",
            "countFrom",
            "countSteps",
            "folder",
            "episode",
            "sequence",
            "track",
            "shot",
            "vSyncOn",
            "export_audio",
            "sourceResolution",
            "workfileFrameStart",
            "handleStart",
            "handleEnd",
            "includeHandles",
            "retimedHandles",
            "retimedFramerange",
        ],
    },
    "CollectShotClip": {
        "collectSelectedInstance": False,
    }
}
