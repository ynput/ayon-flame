import pyblish

from ayon_core.pipeline.load import (
    get_representation_context,
    discover_loader_plugins,
    load_with_repre_context,
    IncompatibleLoaderError
)


class IntegrateBatchgroup(pyblish.api.InstancePlugin):
    """Extract + Integrate Batchgroup Product data."""

    label = "Integrate Batchgroup"
    hosts = ["flame"]
    families = ["batchgroup"]

    default_loader = "LoadClip"

    def process(self, instance):
        # Gather new published plate representation to
        # be associated with the current batchgroup.
        plate_repres = self._find_plate_representations(
            instance,
        )
        if not plate_repres:
            self.log.info(
                "Ignore batchgroup post-upgrade. "
                "No relevant plate representation found."
            )
            return

        # Load/Update plate representation(s) in the bgroup.
        bgroup = instance.data["extracted_batchgroup"]
        self.log.debug("Batchgroup: %s.", bgroup.name)
        self._load_clip_to_context(instance, bgroup, plate_repres)

        # Override batchgroup publish.

    def _find_plate_representations(self, instance):
        """ Gather representations to load/update in the
            batchgroup from sibling plate instance if any.
        """
        parent_instance_id = instance.data["parent_instance_id"]
        plate_instance = None

        # Find parent instance from context
        for inst in instance.context:
            creator_identifier = inst.data["creator_identifier"]
            inst_parent_instance_id = inst.data.get("parent_instance_id")

            if (
                inst_parent_instance_id == parent_instance_id
                and creator_identifier != "io.ayon.creators.flame.plate"
            ):
                plate_instance = inst
                break
        else:
            return []

        return [
            repr_data
            for repr_data in plate_instance.data["representations"]
            if repr_data.get("load_to_batch_group")
        ]


    def _load_clip_to_context(self, instance, bgroup, plate_repres):
        """ Load/Update the representation(s) in the batchgroup.
        """
        # get all loaders for host
        loaders_by_name = {
            loader.__name__: loader
            for loader in discover_loader_plugins()
        }

        # loop all returned repres from repre_context dict
        for repre in plate_repres:
            loader_name = (
                repre.get("batch_group_loader_name")
                or self.default_loader
            )

            loader_plugin = loaders_by_name.get(loader_name)
            if not loader_plugin:
                self.log.warning(
                    "Unsupported loader for representation: %r ."
                    "Loader %s is unknown.",
                    repre,
                    loader_name,
                )
                continue

            repre_context = get_representation_context(
                instance.data["projectEntity"]["name"],
                repre,
            )

            try:
                load_with_repre_context(
                    loader_plugin,
                    repre_context,
                    data={
                        "workdir": self.task_workdir,
                        "batch": bgroup
                    }
                )
            except IncompatibleLoaderError as error:
                self.log.error(
                    "Failed to load representaton %r with loader %s: %r",
                    repre,
                    loader_name,
                    error
                )
                raise
