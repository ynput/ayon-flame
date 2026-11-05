from ayon_server.settings import BaseSettingsModel, SettingsField


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


class BatchWriteFileModel(BaseSettingsModel):
    node_name: str = SettingsField(
        "node_name",
        title="Node name",
    )
    media_path: str = SettingsField(
        "media_path",
        title="Media path",
    )
    frame_padding: int = SettingsField(
        "frame_padding",
        title="Frame padding",
    )
    compress_mode: str = SettingsField(
        "compress_mode",
        title="Compress mode",
    )
    include_setup: bool = SettingsField(
        "include_setup",
        title="Include setup",
    )
    include_setup_path: str = SettingsField(
        "include_setup_path",
        title="Include setup path",
    )
    create_clip: bool = SettingsField(
        "create_clip",
        title="Create clip",
    )
    shot_name: str = SettingsField(
        "shot_name",
        title="Shot name",
    )
    media_path_pattern: str = SettingsField(
        "media_path_pattern",
        title="Media path pattern",
    )


class CreatePluginsModel(BaseSettingsModel):
    CollectShotClip: CollectShotClipInstancesModels = SettingsField(
        default_factory=CollectShotClipInstancesModels,
        title="Collect Shot Clip instances"
    )
    CreateBatchRender: BatchWriteFileModel = SettingsField(
        default_factory=BatchWriteFileModel,
        title="Create Batch Render"
    )


DEFAULT_CREATE_SETTINGS = {
    "CollectShotClip": {
        "collectSelectedInstance": False,
    },
    "CreateBatchRender": {
        "node_name": "RenderFlame",
        "media_path": "",
        "frame_padding": 4,
        "compress_mode": "DWAA",
        "include_setup": True,
        "include_setup_path": "<batch name>_flame_v<iteration###>",
        "create_clip": False,
        "shot_name": "<batch name>",
        "media_path_pattern": (
            "renders/flame/<name>/v<iteration###>/"
            "<batch name><name>_v<iteration###>"
        ),
    },
}
