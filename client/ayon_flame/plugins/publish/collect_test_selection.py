import os
import pyblish.api
import tempfile
import ayon_flame.api as ayfapi
from ayon_flame.otio import flame_export as otio_export
import opentimelineio as otio
from pprint import pformat


class CollectTestSelection(pyblish.api.ContextPlugin):
    """testing selection sharing
    """

    order = pyblish.api.CollectorOrder
    label = "test selection"
    hosts = ["flame"]
    active = False

    def process(self, context):
        self.log.info(
            "Active Selection: {}".format(ayfapi.CTX.selection))

        sequence = ayfapi.get_current_sequence(ayfapi.CTX.selection)

        self.test_print_attributes(sequence)
        self.test_otio_export(sequence)

    def test_otio_export(self, sequence):
        test_dir = os.path.normpath(
            tempfile.mkdtemp(prefix="test_pyblish_tmp_")
        )
        export_path = os.path.normpath(
            os.path.join(
                test_dir, "otio_timeline_export.otio"
            )
        )
        self.log.debug(export_path)
        validation_aggregator = ayfapi.ValidationAggregator()
        otio_timeline = otio_export.create_otio_timeline(
            sequence, validation_aggregator=validation_aggregator)

        failed_segments = validation_aggregator.failed_segments
        self.log.info(failed_segments)
        for segment in failed_segments:
            self.log.error(f"Failed segment: {segment.name}")

        otio_export.write_to_file(
            otio_timeline, export_path
        )
        read_timeline_otio = otio.adapters.read_from_file(export_path)

        if len(str(otio_timeline)) != len(str(read_timeline_otio)):
            raise Exception("Exported timeline is different from original")

        self.log.info(pformat(otio_timeline))
        self.log.info("Otio exported to: {}".format(export_path))

    def test_print_attributes(self, sequence):
        with ayfapi.maintained_segment_selection(sequence) as sel_segments:
            for segment in sel_segments:
                self.log.debug("Segment with AYONData: {}".format(
                    segment.name))

                self.print_segment_properties(segment)

    def print_segment_properties(self, segment):
        """Loop through a PySegment object's attributes and printproperties.

        Args:
            segment: A flame.PySegment object
        """
        # Get all attributes
        attributes = dir(segment)

        self.log.debug("Properties of the PySegment object:")
        self.log.debug("-" * 40)
        for attr in attributes:
            if (
                not attr.startswith("__")
                and not callable(getattr(segment, attr))
            ):
                self.log.debug(f"{attr}: {getattr(segment, attr)}")
