import os

import pyblish.api

from ayon_core.lib import get_version_from_path
from ayon_core.pipeline import registered_host


class CollectBatchVersion(pyblish.api.ContextPlugin):
    """ Collect "version" from the current batch workfile, if any.
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

        # AYON workfile name carries the version. Flame's own iteration
        # index cannot: it is re-usable and re-indexable, so publishing from
        # it can overwrite an existing published version
        filepath = registered_host().get_current_workfile()
        if not filepath:
            self.log.debug("No AYON workfile for the current task.")
            return

        version = get_version_from_path(os.path.basename(filepath))
        if version is None:
            self.log.debug(f"No version in workfile name: {filepath}")
            return

        context.data["version"] = int(version)
        self.log.debug(
            f"Collected context version: {context.data['version']} "
            f"from {filepath}"
        )
