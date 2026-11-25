import pyblish.api

from ayon_core.pipeline.anatomy import AnatomyStringTemplate
from ayon_core.pipeline.template_data import get_project_template_data


class CollectExportPresetsDir(pyblish.api.ContextPlugin):
    """Collect the central export presets folder from settings, if enabled.

    Its presets are copied into each Flame project on launch. Publishing
    also searches it for export presets set by file name only.
    """

    label = "Collect Export Presets Folder"
    # after the anatomy and project entity are collected
    order = pyblish.api.CollectorOrder
    hosts = ["flame"]

    def process(self, context):
        presets_settings = (
            context.data["project_settings"]["flame"]["export_presets"])
        if (
            not presets_settings["enabled"]
            or not presets_settings["source_dir"]
        ):
            self.log.debug("Central export presets folder not enabled.")
            return

        template = AnatomyStringTemplate(
            context.data["anatomy"].templates_obj,
            presets_settings["source_dir"]
        )
        template_data = get_project_template_data(
            context.data["projectEntity"])
        presets_dir = template.format(template_data)

        self.log.debug(f"Central export presets folder: {presets_dir}")
        context.data["flameExportPresetsDir"] = presets_dir
