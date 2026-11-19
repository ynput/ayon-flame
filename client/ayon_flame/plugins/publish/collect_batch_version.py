import os

import pyblish.api
from ayon_core.lib import get_version_from_path

import ayon_flame.api as flapi


class CollectBatchVersion(pyblish.api.ContextPlugin):
    """ Collect "version" from the Batch workfile of the publish.

    Like core 'CollectSceneVersion', which Flame does not run by default.
    Core uses it when 'follow_workfile_version' is on, else the next version.
    """

    order = pyblish.api.CollectorOrder
    label = "Collect Batch Version"
    hosts = ["flame"]

    def process(self, context):
        # No need to collect current batch version as "workfile"
        # version if no instance related to batch is found in context.
        for instance in context:
            if instance.data.get("flame_context") == "FlameMenuBatch":
                break
        else:
            self.log.debug("No instances related to batch found in context.")
            return

        # Flame iteration numbers jump and get reused, so they cannot be
        # versions.
        current_file = context.data.get("currentFile", "")
        if not current_file.endswith(flapi.BATCH_WORKFILE_EXTENSION):
            self.log.debug("No Batch workfile saved, no context version.")
            return

        version = get_version_from_path(os.path.basename(current_file))
        if version is None:
            self.log.debug(f"No version in '{current_file}'.")
            return

        context.data["version"] = int(version)
        self.log.debug(
            f"Collected context version: {context.data['version']} "
            f"from '{current_file}'"
        )
