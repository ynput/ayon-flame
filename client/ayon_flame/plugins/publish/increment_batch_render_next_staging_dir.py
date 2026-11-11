import copy
import os

import pyblish.api
from ayon_core.pipeline import get_staging_dir_info
from ayon_core.pipeline.publish import OptionalPyblishPluginMixin

import ayon_flame.api as flapi


class IncrementBatchRenderNextStagingDir(
    pyblish.api.InstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Point Write File node to the next version custom staging dir.

    Keeps the output path shown in the node in sync with what
    the next publish will expect.
    """

    label = "Increment Batch Render Custom Staging Dir"
    order = pyblish.api.IntegratorOrder + 0.6
    families = ["render"]
    hosts = ["flame"]
    settings_category = "flame"

    optional = True
    active = True

    @staticmethod
    def _follows_workfile_version(instance):
        """Whether render version follows the batch iteration.
        """
        if "followWorkfileVersion" in instance.data:
            return instance.data["followWorkfileVersion"]

        project_settings = instance.context.data["project_settings"]
        return (
            project_settings["core"]["publish"]
            ["CollectAnatomyInstanceData"]["follow_workfile_version"]
        )

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if not instance.data.get("stagingDir_is_custom"):
            self.log.debug(
                "Current batch render instance does not "
                "use custom staging directory."
            )
            return

        write_node = instance.data["transientData"].get("writeNode")
        if write_node is None:
            self.log.warning("Could not find write node from instance.")
            return

        context = instance.context
        template_data = copy.deepcopy(instance.data["anatomyData"])

        # Sync with the actual batch iteration (incremented or not
        # by 'IntegrateBatchIteration'), like Nuke 'IncrementWriteNodePath'.
        if self._follows_workfile_version(instance):
            batch_name = instance.data["batch_name"]
            batch = flapi.get_batch_from_workspace(batch_name)
            if batch is None:
                self.log.warning(f"Batch group not found: {batch_name}")
                return
            template_data["version"] = batch.current_iteration_number

        else:
            template_data["version"] += 1

        current_file = context.data.get("currentFile")
        if current_file:
            template_data["workfile_name"] = os.path.splitext(
                os.path.basename(current_file)
            )[0]

        staging_dir_info = get_staging_dir_info(
            context.data["projectEntity"],
            instance.data.get("folderEntity"),
            instance.data.get("taskEntity"),
            product_base_type=instance.data.get("productBaseType"),
            product_type=instance.data["productType"],
            product_name=instance.data["productName"],
            host_name=context.data["hostName"],
            anatomy=context.data["anatomy"],
            project_settings=context.data["project_settings"],
            template_data=template_data,
            always_return_path=False,
            username=context.data["user"],
        )
        if staging_dir_info is None:
            return

        flapi.set_write_node_output_dir(write_node, staging_dir_info.directory)
        self.log.info(
            f"Write File node '{write_node.name.get_value()}' now renders "
            f"to '{staging_dir_info.directory}'."
        )
