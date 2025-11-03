from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    task_types_enum,
)


class XMLPresetAttrsFromCommentsModel(BaseSettingsModel):
    _layout = "expanded"
    name: str = SettingsField("", title="Attribute name")
    type: str = SettingsField(
        default_factory=str,
        title="Attribute type",
        enum_resolver=lambda: ["number", "float", "string"]
    )


class AddTasksModel(BaseSettingsModel):
    _layout = "expanded"
    name: str = SettingsField("", title="Task name")
    type: str = SettingsField(
        default_factory=str,
        title="Task type",
        enum_resolver=task_types_enum
    )
    create_batch_group: bool = SettingsField(
        True,
        title="Create batch group"
    )


class CollectShotsModel(BaseSettingsModel):
    _isGroup = True

    xml_preset_attrs_from_comments: list[XMLPresetAttrsFromCommentsModel] = (
        SettingsField(
            default_factory=list,
            title="XML presets attributes parsable from segment comments"
        )
    )
    add_tasks: list[AddTasksModel] = SettingsField(
        default_factory=list,
        title="Add tasks"
    )


class OutputNodePropertiesModel(BaseSettingsModel):
    _layout = "compact"
    name: str = SettingsField(
        default_factory=str,
        title="Attribute name"
    )
    value: str = SettingsField(
        default_factory=str,
        title="Attribute value"
    )


class AttachToTaskModel(BaseSettingsModel):
    task_name: str = SettingsField(
        default_factory=str,
        title="Task name"
    )
    task_type: str = SettingsField(
        default_factory=str,
        title="Task type",
        enum_resolver=task_types_enum
    )


class CollectBatchgroupModel(BaseSettingsModel):
    _isGroup = True
    output_node_properties: list[OutputNodePropertiesModel] = SettingsField(
        default_factory=list,
        title="Output node properties"
    )
    attach_to_task: AttachToTaskModel = SettingsField(
        default_factory=AttachToTaskModel,
        title="Attach to task"
    )

class ExportPresetsMappingModel(BaseSettingsModel):
    _layout = "expanded"

    name: str = SettingsField(
        ...,
        title="Name",
        description=(
            "Used to identify the preset. It can also be part of the "
            "output file name via the `outputName` anatomy template token. "
            "It serves as a unique representation name."
        ),
    )
    active: bool = SettingsField(
        True,
        title="Is active",
        section="Filtering properties",
        description=(
            "If the preset is active, it will be used during the export "
            "process."
        ),
    )
    filter_path_regex: str = SettingsField(
        ".*",
        title="Activate by search pattern",
        description=(
            "If the clip's media resource path matches the input regex "
            "pattern, the preset will be used."
        ),
    )
    ext: str = SettingsField(
        "exr",
        title="Output extension",
        section="Output file properties",
        description=(
            "The output file extension for the published "
            "representation."
        ),
    )
    colorspace_out: str = SettingsField(
        "ACES - ACEScg",
        title="Output color (imageio)",
        description=(
            "Specifies the colorspace data to be stored in the "
            "representation. This is used downstream in the publishing "
            "process or by loading plugins."
        ),
    )
    export_type: str = SettingsField(
        "File Sequence",
        title="Export clip type",
        enum_resolver=lambda: ["Movie", "File Sequence", "Sequence Publish"],
        description="The type of XML preset to be used for export.",
        section="XML preset properties",
    )
    xml_preset_dir: str = SettingsField(
        "",
        title="XML preset directory",
        description=(
            "The absolute directory path where the XML preset is stored. "
            "If left empty, built-in directories are used, either shared "
            "or installed presets folder."
        ),
    )
    xml_preset_file: str = SettingsField(
        "OpenEXR (16-bit fp DWAA).xml",
        title="XML preset file (with ext)",
        description="The name of the XML preset file with its extension.",
    )
    parsed_comment_attrs: bool = SettingsField(
        True,
        title="Distribute parsed comment attributes to XML preset",
        description=(
            "If enabled, previously collected clip comment attributes "
            "will be distributed to the XML preset. This can affect the "
            "resulting resolution of the exported media."
        ),
    )
    representation_add_range: bool = SettingsField(
        True,
        title="Add range to representation name",
        description=(
            "Adds frame range-related attributes to the publishing "
            "representation data for downstream use in the publishing process."
        ),
        section="Representation properties",
    )
    representation_tags: list[str] = SettingsField(
        default_factory=list,
        title="Representation tags",
        description=(
            "Adds tags to the representation data for downstream use in "
            "the publishing process. For example, marking the representation "
            "as reviewable."
        ),
    )
    load_to_batch_group: bool = SettingsField(
        True,
        title="Load to batch group reel",
        description=(
            "If enabled, the representation will be loaded to the batch "
            "group reel after publishing (connected to IntegrateBatchGroup)."
        ),
        section="Batch group properties",
    )
    batch_group_loader_name: str = SettingsField(
        "LoadClipBatch",
        title="Use loader name",
        description=(
            "Defines which loader plugin should be used for loading the "
            "representation after publishing (connected to "
            "IntegrateBatchGroup)."
        ),
    )


class ExtractProductResourcesModel(BaseSettingsModel):
    _isGroup = True

    keep_original_representation: bool = SettingsField(
        False,
        title="Publish clip's original media"
    )
    export_presets_mapping: list[ExportPresetsMappingModel] = SettingsField(
        default_factory=list,
        title="Export presets mapping"
    )


class IntegrateBatchGroupModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        False,
        title="Enabled"
    )


class PublishPluginsModel(BaseSettingsModel):
    CollectShot: CollectShotsModel = SettingsField(
        default_factory=CollectShotsModel,
        title="Collect Shot instances"
    )
    CollectBatchgroup: CollectBatchgroupModel = SettingsField(
        default_factory=CollectBatchgroupModel,
        title="Collect Batchgroup instances"
    )

    ExtractProductResources: ExtractProductResourcesModel = SettingsField(
        default_factory=ExtractProductResourcesModel,
        title="Extract Product Resources"
    )

    IntegrateBatchGroup: IntegrateBatchGroupModel = SettingsField(
        default_factory=IntegrateBatchGroupModel,
        title="IntegrateBatchGroup"
    )


DEFAULT_PUBLISH_SETTINGS = {
    "CollectShot": {
        "xml_preset_attrs_from_comments": [
            {
                "name": "width",
                "type": "number"
            },
            {
                "name": "height",
                "type": "number"
            },
            {
                "name": "pixelRatio",
                "type": "float"
            },
            {
                "name": "resizeType",
                "type": "string"
            },
            {
                "name": "resizeFilter",
                "type": "string"
            }
        ],
        "add_tasks": [
            {
                "name": "compositing",
                "type": "Compositing",
                "create_batch_group": True
            }
        ]
    },
    "CollectBatchgroup": {
        "output_node_properties": [
            {
                "name": "file_type",
                "value": "OpenEXR",
            },
            {
                "name": "format_extension",
                "value": "exr",
            },
            {
                "name": "bit_depth",
                "value": "16",
            },
            {
                "name": "include_setup_path",
                "value": "./<name>_v<iteration###>",
            }
        ],
        "attach_to_task": {
            "task_name": "compositing",
            "task_type": "Compositing",
        }
    },
    "ExtractProductResources": {
        "keep_original_representation": False,
        "export_presets_mapping": [
            {
                "name": "exr16fpdwaa",
                "active": True,
                "export_type": "File Sequence",
                "ext": "exr",
                "xml_preset_file": "OpenEXR (16-bit fp DWAA).xml",
                "colorspace_out": "ACES - ACEScg",
                "xml_preset_dir": "",
                "parsed_comment_attrs": True,
                "representation_add_range": True,
                "representation_tags": [],
                "load_to_batch_group": True,
                "batch_group_loader_name": "LoadClipBatch",
                "filter_path_regex": ".*"
            }
        ]
    },
    "IntegrateBatchGroup": {
        "enabled": False
    }
}
