import pyblish.api

from ayon_flame.otio import utils


class CollectBatchgroup(pyblish.api.InstancePlugin):
    """Collect Shot related batchgroup workfile products."""

    order = pyblish.api.CollectorOrder - 0.47
    label = "Collect Batchgroup"
    hosts = ["flame"]
    families = ["workfile"]

    output_node_properties = {}
    attach_to_task = {}

    def process(self, instance):
        creator_identifier = instance.data["creator_identifier"]

        if creator_identifier != "io.ayon.creators.flame.batchgroup":
            # only interested in flame batchgroup
            return

        # Validate that attach_to_task has required keys
        required_keys = ["task_name", "task_type"]
        missing_keys = [
            k for k in required_keys if k not in self.attach_to_task]
        if missing_keys:
            raise ValueError(str(
                "CollectBatchgroup.attach_to_task is missing "
                f"required keys: {missing_keys}. "
                "Please ensure settings are properly configured."
            ))

        # Update parent instance tasks with attach_to_task
        self._update_parent_instance_tasks(instance)

        # update shot related shared attributes
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]
        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError(
                f"Could not retrieve otioClip for shot {instance}")

        instance.data["otioClip"] = otio_clip

        clip_src = instance.data["otioClip"].source_range
        clip_src_in = clip_src.start_time.to_frames()
        clip_src_out = clip_src_in + clip_src.duration.to_frames()
        instance.data.update({
            "clipInH": clip_src_in,
            "clipOutH": clip_src_out,
            "families": ["batchgroup", "clip"],
            "taskName": self.attach_to_task["task_name"],
            "attachToTask": self.attach_to_task,
            "outputNodeProperties": self.output_node_properties,
        })
        self.log.info(
            f"Collected batchgroup workfile products for shot {instance}")

    def _update_parent_instance_tasks(self, instance):
        """Update parent instance tasks with attach_to_task if not present."""
        parent_instance_id = instance.data["parent_instance_id"]
        context = instance.context
        for parent_instance in context:
            if parent_instance.data["instance_id"] == parent_instance_id:
                tasks = parent_instance.data.get("tasks", {})
                attach_task_name = self.attach_to_task["task_name"]
                new_task_data = {"type": self.attach_to_task["task_type"]}
                if attach_task_name not in tasks:
                    tasks[attach_task_name] = new_task_data
                else:
                    tasks[attach_task_name].update(new_task_data)

                parent_instance.data["tasks"] = tasks
                break
