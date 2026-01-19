import pyblish.api
from pprint import pformat

import opentimelineio as otio

import ayon_flame.api as ayfapi
from ayon_flame.otio import flame_export


class CollecTimelineOTIO(pyblish.api.ContextPlugin):
    """Inject the current sequence data into publish context"""

    label = "Collect Timeline OTIO"
    order = pyblish.api.CollectorOrder - 0.491

    def process(self, context):

        # update context with current sequence/timeline attributes
        sequence = ayfapi.get_current_sequence(ayfapi.CTX.selection)
        if sequence is None:
            # No sequence currently opened in Flame.
            # This means all publish instances comes from reel/media panel.
            context.data["otioTimeline"] = otio.schema.Timeline()
            self.log.debug("No current Flame sequence found.")
            return

        # validate segment from current sequence
        segments = ayfapi.get_sequence_segments(sequence)
        validation_aggregator = ayfapi.ValidationAggregator()
        with ayfapi.maintained_segment_selection(sequence):
            otio_timeline = flame_export.create_otio_timeline(
                sequence, validation_aggregator=validation_aggregator)

        failed_segments = validation_aggregator.failed_segments

        # update context with timeline attributes
        project = context.data["flameProject"]
        timeline_data = {
            "flameSequence": sequence,
            "failedSegments": failed_segments,
            "otioTimeline": otio_timeline,
            "currentFile": "Flame/{}/{}".format(
                project.name, sequence.name.get_value()
            ),
            "flameSegments": segments,
            "fps": float(str(sequence.frame_rate)[:-4])
        }
        self.log.debug(f">>> Timeline data: {pformat(timeline_data)}")
        context.data.update(timeline_data)
