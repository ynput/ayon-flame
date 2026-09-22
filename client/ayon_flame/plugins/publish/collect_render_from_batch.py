"""Collect render instances from batch Write File nodes."""
import pyblish.api

from ayon_core.pipeline import PublishError

import ayon_flame.api as flapi


class CollectRenderFromBatch(pyblish.api.InstancePlugin):
    """Collect batch render instances and handle the review attribute."""

    order = pyblish.api.CollectorOrder + 0.48
    label = "Collect Render from Batch"
    hosts = ["flame"]
    families = ["render"]

    def process(self, instance):
        if (
            instance.data.get("flame_context") != "FlameMenuBatch"
            or not instance.data.get("write_node_name")
        ):
            self.log.warning("No valid batch render instance, skipping.")
            return

        batch_name = instance.data["batch_name"]
        write_node_name = instance.data["write_node_name"]

        batch = flapi.get_batch_from_workspace(batch_name)
        if batch is None:
            raise PublishError(
                f"Batch group not found in workspace: '{batch_name}'."
            )

        write_node = flapi.get_write_node_from_batch(batch, write_node_name)
        if write_node is None:
            raise PublishError(
                f"Write File node '{write_node_name}' not found "
                f"in batch '{batch_name}'."
            )

        if instance.data.get("creator_attributes", {}).get("review"):
            instance.data["families"].append("review")
            self.log.debug(
                f"Review enabled for render instance '{instance.name}'."
            )

        handle_start = instance.context.data["handleStart"]
        handle_end = instance.context.data["handleEnd"]

        frame_start_handle = write_node.range_start.get_value()
        frame_end_handle = write_node.range_end.get_value()

        fps = flapi.parse_frame_rate(write_node.frame_rate.get_value())
        context_fps = instance.context.data["fps"]
        if fps != context_fps:
            self.log.warning(
                f"Write File node '{write_node_name}' renders at {fps} fps "
                f"but the folder is set to {context_fps} fps."
            )

        instance.data.update({
            "frameStart": frame_start_handle + handle_start,
            "frameEnd": frame_end_handle - handle_end,
            "frameStartHandle": frame_start_handle,
            "frameEndHandle": frame_end_handle,
            "handleStart": handle_start,
            "handleEnd": handle_end,
            "fps": fps,
        })

        self.log.debug(
            f"Collected render instance '{instance.name}' "
            f"from Write File node '{write_node_name}' "
            f"({frame_start_handle}-{frame_end_handle}, "
            f"handles {handle_start}/{handle_end}, {fps} fps). "
            f"Families: {instance.data['families']}"
        )
