import pyblish.api

from ayon_core.pipeline import PublishError


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

        # Only interested in flame batchgroup.
        if creator_identifier != "io.ayon.creators.flame.batchgroup":
            self.log.debug("Not a batchgroup workfile, ignore.")
            return

        # Validate attach_to_task settings.
        missing_keys = [
            key for key in ("task_name", "task_type")
            if key not in self.attach_to_task
        ]
        if missing_keys:
            raise ValueError(
                "Invalid batchgroup workfile instance. "
                "CollectBatchgroup.attach_to_task is missing "
                f"required keys: {missing_keys}. "
                "Please ensure settings are properly configured."
            )

        # Ensure parent shot instance will
        # create expected batchgroup task
        self._update_parent_shot_instance_tasks(instance)

        # update shot related shared attributes
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]
        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        instance.data.update({
            "families": ["batchgroup"],
            "attachToTask": self.attach_to_task,
            "outputNodeProperties": self.output_node_properties,
        })
        self.log.info(
            "Collected batchgroup workfile products for shot %s",
            instance,
        )

    def _update_parent_shot_instance_tasks(self, instance):
        """ Update parent instance shot tasks with expected batchgroup task.
        """
        parent_instance_id = instance.data["parent_instance_id"]
        shot_tasks = parent_instance = None

        # Find parent instance from context
        for inst in instance.context:
            if inst.data["instance_id"] == parent_instance_id:
                parent_instance = inst
                shot_tasks = inst.data.get("tasks", {})
                break

        else:
            raise PublishError(
                f"Cannot find parent shot instance: {parent_instance_id} "
                f'for batchgroup instance: {instance.data["instance_id"]}'
            )

        # Batchgroup product get published under a specific task
        # type that get created by the shot product. If expected batchgroup
        # task is missing, warn and add it to the shot parent instance.
        bg_task_name = self.attach_to_task["task_name"]
        bg_task_type = self.attach_to_task["task_type"]
        bg_task_data = {"type": bg_task_type}

        if bg_task_name not in shot_tasks:
            self.log.warning(
                "Batchgroup settings expect a %s "
                "(%s)task at shot level. Adding it "
                "in the shot parent instance.",
                bg_task_name, bg_task_type,
            )
            shot_tasks[bg_task_name] = bg_task_data
        else:
            shot_tasks[bg_task_name].update(bg_task_data)

        parent_instance.data["tasks"] = shot_tasks
