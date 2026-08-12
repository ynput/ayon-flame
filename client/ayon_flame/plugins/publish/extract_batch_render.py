""" Extract render output from Flame batch Write File nodes. """
import os

from pathlib import Path

import pyblish.api

from ayon_core.pipeline import publish, PublishError

import ayon_flame.api as flapi


class ExtractBatchRender(publish.Extractor):
    """Render the batch then collect Write File outputs as representations.
    """

    label = "Extract Batch Render"
    order = pyblish.api.ExtractorOrder
    families = ["render"]
    hosts = ["flame"]

    # Context key used to ensure render is triggered only once per publish.
    # Could be multiple batch renders per publish context.
    _RENDER_DONE_KEY = "_batch_render_done"

    def process(self, instance):
        write_node_name = instance.data.get("write_node_name")
        if not write_node_name:
            self.log.debug("No valid batch render instance, skipping.")
            return

        batch_name = instance.data["batch_name"]
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

        # Render once per publish context across all render instances.
        render_context = instance.context.data.setdefault(
            self._RENDER_DONE_KEY, {}
        )
        if not render_context.get(batch_name):
            self.log.info(f"Rendering batch '{batch_name}'.")
            success = batch.render()  # render_option='Foreground' (blocking)
            if not success:
                raise PublishError(
                    f"Flame batch render failed for '{batch_name}'."
                )

            render_context[batch_name] = True
            self.log.info(f"Batch '{batch_name}' rendered successfully.")

        else:
            self.log.debug("Batch already rendered, no need to re-render.")

        # get_resolved_media_path() returns either:
        # - a sequence pattern: /path/file.[0001001-0001050].exr
        # - a single file:      /path/output.mov
        resolved_path = write_node.get_resolved_media_path()
        output_dir = os.path.dirname(resolved_path)
        resolved_name = os.path.basename(resolved_path)

        bracket_pos = resolved_name.find("[")
        is_sequence = bracket_pos != -1
        _, ext = os.path.splitext(resolved_name)
        ext = ext.lstrip(".")

        # Single file output, check the exact file exists.
        if not is_sequence:
            single_file = Path(output_dir) / resolved_name
            if not single_file.exists():
                raise PublishError(
                    f"Output file not found after render: {single_file}"
                )
            written_files = [resolved_name]

        else:
            output_path = Path(output_dir)
            if not output_path.exists():
                raise PublishError(
                    f"Output directory not found after render: {output_dir}"
                )

            name_prefix = resolved_name[:bracket_pos]

            # Scan output directory for written files.
            # NOTE: Pre-existing files matching the extension will be included.
            # If the Write File node is configured to overwrite the same output
            # path across multiple publishes, older files are picked up too.
            written_files = sorted(
                f.name for f in output_path.iterdir()
                if f.is_file()
                and f.suffix.lstrip(".").lower() == ext.lower()
                and f.name.startswith(name_prefix)
            )
        if not written_files:
            raise PublishError(
                f"Expected {resolved_path} files is not found "
                "in output directory."
            )

        if "representations" not in instance.data:
            instance.data["representations"] = []

        review = "review" in instance.data["families"]

        representation = {
            "name": ext,
            "ext": ext,
            "outputName": ext,
            "files": (
                written_files if len(written_files) > 1 else written_files[0]
            ),
            "stagingDir": output_dir,
            "tags": ["review"] if review else [],
        }
        instance.data["representations"].append(representation)
        self.log.info(
            f"Collected render representation from '{write_node_name}': "
            f"{output_dir} ({len(written_files)} file(s))."
        )
