"""Flame sequence to an OTIO timeline.

Flame is only read here: segments, media info, markers, time effects and
the colour policy. They are turned into the plain specs of
`ayon_editorial.otio.builder`, which builds the OTIO objects. The Flame
timewarp XML baker (`tw_bake`) stays in this addon and feeds the lookup of
`TimeWarpEffectSpec`.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pprint import pformat

import flame
import opentimelineio as otio
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS
from ayon_editorial.otio import builder, effects, paths
from ayon_editorial.otio.time import create_time_range, timecode_to_frames

from ayon_flame.api import (
    MediaInfoFile,
    TimeEffectMetadata,
    lib,
)

from . import tw_bake

log = logging.getLogger(__name__)


MARKERS_COLOR_MAP = {
    (1.0, 0.0, 0.0): otio.schema.MarkerColor.RED,
    (1.0, 0.5, 0.0): otio.schema.MarkerColor.ORANGE,
    (1.0, 1.0, 0.0): otio.schema.MarkerColor.YELLOW,
    (1.0, 0.5, 1.0): otio.schema.MarkerColor.PINK,
    (1.0, 1.0, 1.0): otio.schema.MarkerColor.WHITE,
    (0.0, 1.0, 0.0): otio.schema.MarkerColor.GREEN,
    (0.0, 1.0, 1.0): otio.schema.MarkerColor.CYAN,
    (0.0, 0.0, 1.0): otio.schema.MarkerColor.BLUE,
    (0.5, 0.0, 0.5): otio.schema.MarkerColor.PURPLE,
    (0.5, 0.0, 1.0): otio.schema.MarkerColor.MAGENTA,
    (0.0, 0.0, 0.0): otio.schema.MarkerColor.BLACK
}
MARKERS_INCLUDE = True


class OtioExportCTX:
    _fps = None
    _tl_start_frame = None
    project = None
    clips = None

    @classmethod
    def set_fps(cls, new_fps):
        if not isinstance(new_fps, float):
            raise TypeError(f"Invalid fps type {type(new_fps)}")
        if cls._fps != new_fps:
            cls._fps = new_fps

    @classmethod
    def get_fps(cls):
        return cls._fps

    @classmethod
    def set_tl_start_frame(cls, number):
        if not isinstance(number, int):
            raise TypeError(
                f"Invalid timeline start frame type {type(number)}")
        if cls._tl_start_frame != number:
            cls._tl_start_frame = number

    @classmethod
    def get_tl_start_frame(cls):
        return cls._tl_start_frame


def get_current_flame_project():
    project = flame.project.current_project
    return project


def create_otio_time_range(start_frame, frame_duration, fps):
    return create_time_range(start_frame, frame_duration, fps)


def _get_metadata(item):
    if hasattr(item, "metadata"):
        return dict(item.metadata) if item.metadata else {}
    return {}


def _get_marker_color(flame_colour):
    # clamp colors to closes half numbers
    _flame_colour = [round(c * 2) / 2 for c in flame_colour]

    for color, otio_color_type in MARKERS_COLOR_MAP.items():
        if _flame_colour == list(color):
            return otio_color_type

    return otio.schema.MarkerColor.RED


def _get_marker_specs(item):
    """Read the markers of a Flame segment into marker specs."""
    if not MARKERS_INCLUDE:
        return []

    time_in = item.record_in.relative_frame
    specs = []
    for marker in item.markers:
        log.debug(marker)
        comment = marker.comment.get_value()

        # to identify this as json, at least 3 items in the list should
        # be present ["{", ":", "}"]
        metadata = {}
        if len(re.findall(r"[{:}]", comment)) >= 3:
            try:
                metadata.update(json.loads(comment))
            except ValueError as msg:
                log.error(f"Marker json conversion: {msg}")
        else:
            metadata["comment"] = comment

        location = marker.location.get_value().relative_frame
        specs.append(builder.MarkerSpec(
            name=marker.name.get_value(),
            start=(location - time_in) + 1,
            duration=marker.duration.get_value().relative_frame,
            color=_get_marker_color(marker.colour.get_value()),
            metadata=metadata,
        ))
    return specs


def _get_media_spec(clip_data, media_info, source_duration, fps):
    """Read the probed media of a segment into a media spec."""
    path = clip_data["fpath"]
    metadata = {}

    # Add image-based metadata if not a pure audio media
    if hasattr(media_info, "width"):
        metadata.update({
            "ayon.source.width": media_info.width,
            "ayon.source.height": media_info.height,
            "ayon.source.pixelAspect": media_info.pixel_aspect,
        })

    sequence = None
    # match range pattern e.g. "foo_[1001-1010].ext"
    sequence_match = re.match(
        r".*\[(?P<start_frame>\d*)-(?P<end_frame>\d*)\].?",
        media_info.file_pattern
    )
    if sequence_match:
        file_name = os.path.basename(path)
        frame_number = sequence_match.group("start_frame")
        sequence = builder.SequenceSpec(
            target_url_base=os.path.dirname(path) + os.sep,
            name_prefix=file_name.split(frame_number)[0],
            name_suffix=os.path.splitext(file_name)[1],
            start_frame=int(frame_number),
            padding=len(frame_number),
        )

    return builder.MediaSpec(
        target_url=path,
        available_start=media_info.start_frame or 0,
        available_duration=source_duration,
        rate=fps or media_info.fps or OtioExportCTX.get_fps(),
        metadata=metadata,
        sequence=sequence,
    )


def _get_time_effect_spec(clip_data, time_effect, media, speed):
    """Get the retime effect spec of a segment.

    Flame writes a time warp OR a speed effect, never both.
    """
    if not time_effect.is_empty:
        data = time_effect.data

        # Check if constant speed retiming
        if data["type"] == "speed" and data.get("numKeys") == 1:
            speed = data["speed"]

        else:
            # Interpolate curves and retrieve interpolated value per frame.
            iframes = tw_bake.Timewarp().bake_flame_tw_setup(
                time_effect.setup_data
            )

            # Flame TWs defines its timing offsets from available range
            # (relative). Map interpolated frames to available_range
            # (absolute).
            av_start = int(media.available_start)
            mapped_frames = [
                (av_start + iframe - 1)
                for iframe in iframes.values()
            ]

            # Lookup values are offsets from src_range (relative).
            frame_src_offset = min(
                int(clip_data["source_in"]),
                int(clip_data["source_out"])
            )
            return builder.TimeWarpEffectSpec(
                lookup=effects.lookup_from_frames(
                    mapped_frames, frame_src_offset
                )
            )

    return builder.SpeedEffectSpec(speed)


def _get_clip_spec(clip_data):
    """Read a segment's attributes, media and effects into a clip spec."""
    segment = clip_data["PySegment"]
    fps = OtioExportCTX.get_fps()  # fallback from timeline

    media_info = None
    file_first_frame = None
    media_timecode_start = None
    tw_data = None
    media_fps = fps
    if clip_data.get("fpath"):
        file_path = clip_data["fpath"]

        # calculate source in
        media_info = MediaInfoFile(file_path, logger=log)
        media_timecode_start = media_info.start_frame
        media_fps = media_info.fps

        # define first frame
        file_first_frame = paths.get_frame(file_path, IMAGE_EXTENSIONS)
        if file_first_frame:
            file_first_frame = int(file_first_frame)

        # Timewarp metadata
        tw_data = TimeEffectMetadata(segment, logger=log)
        log.debug(f"__ tw_data: {tw_data.data}")
    # fallback for clips with missing file path
    # they will be added as missing reference clips
    elif clip_data.get("start_frame"):
        file_first_frame = int(clip_data["start_frame"])
        media_timecode_start = file_first_frame
    elif clip_data.get("source_frame_rate"):
        # it returns `23.976 fps`
        media_fps = float(
            clip_data["source_frame_rate"].replace(" fps", "")
        )

    first_frame = int(media_timecode_start or file_first_frame or 0)

    clip_source_in = int(clip_data["source_in"])
    clip_source_out = int(clip_data["source_out"])
    clip_record_duration = int(clip_data["record_duration"])

    # first solve if the reverse timing
    speed = 1
    if clip_data["source_in"] > clip_data["source_out"]:
        source_in = clip_source_out - first_frame
        source_out = clip_source_in - first_frame
        speed = -1
    else:
        source_in = clip_source_in - first_frame
        source_out = clip_source_out - first_frame

    source_duration = (source_out - source_in + 1)

    if "source_duration" not in clip_data:
        clip_data["source_duration"] = source_duration

    # secondly check if any change of speed
    if source_duration != clip_record_duration:
        speed *= float(source_duration) / float(clip_record_duration)

    log.debug(
        f"_ source_in: {source_in}, source_out: {source_out}, "
        f"speed: {speed}, source_duration: {source_duration}, "
        f"record_duration: {clip_record_duration}"
    )

    media = None
    if media_info:
        media = _get_media_spec(
            clip_data, media_info, int(clip_data["source_duration"]),
            media_fps
        )

    clip_effects = []
    if tw_data and media:
        clip_effects.append(
            _get_time_effect_spec(clip_data, tw_data, media, speed)
        )

    return builder.ClipSpec(
        name=clip_data["segment_name"],
        source_offset=source_in,
        duration=clip_record_duration,
        media=media,
        record_in=clip_data["record_in"],
        record_out=clip_data["record_out"],
        markers=_get_marker_specs(segment),
        effects=clip_effects,
    )


def create_otio_clip(clip_data):
    """Create an OTIO clip from the attributes of a Flame segment.

    Needs `OtioExportCTX.set_fps` set to the timeline rate.
    """
    return builder.create_clip(
        _get_clip_spec(clip_data), OtioExportCTX.get_fps()
    )


def _get_colourspace_policy():

    output = {}
    # get policies project path
    policy_dir = (
        f"/opt/Autodesk/project/{OtioExportCTX.project.name}/synColor/policy")

    policy_fp = os.path.join(policy_dir, "policy.cfg")

    if not os.path.exists(policy_fp):
        return output

    with open(policy_fp) as file:
        dict_conf = dict(line.strip().split(" = ", 1) for line in file)
        output.update(
            {f"ayon.flame.{k}": v for k, v in dict_conf.items()}
        )
    return output


def _get_timeline_metadata(sequence):
    metadata = _get_metadata(sequence)

    # find colour policy files and add them to metadata
    metadata.update(_get_colourspace_policy())

    metadata.update({
        "ayon.timeline.width": int(sequence.width),
        "ayon.timeline.height": int(sequence.height),
        "ayon.timeline.pixelAspect": float(1)
    })
    return metadata


def _get_segments_from_track(
    flame_track,
    validation_aggregator: lib.ValidationAggregator = None
):
    """Gather segment(s) from a flame track.

    Args:
        flame_track (flame.PyTrack): The Flame track.
        validation_aggregator (lib.ValidationAggregator, optional):
                Output object to store attributes for passing into
                publishing validation. Defaults to None.

    Returns:
        List[flame.PySegment]. The gathered segments.
    """
    if not validation_aggregator:
        validation_aggregator = lib.ValidationAggregator()

    all_segments = []
    for segment in flame_track.segments:
        clip_data = lib.get_segment_attributes(segment, validation_aggregator)
        if clip_data:
            all_segments.append(clip_data)

    return all_segments


def _fill_track(track_builder, flame_track, validation_aggregator):
    """Append the clips of a Flame track; gaps come from record times."""
    segments = _get_segments_from_track(
        flame_track, validation_aggregator=validation_aggregator)
    log.debug(f"_ segments: {pformat(segments)}")
    for segment_data in segments:
        track_builder.append_clip(_get_clip_spec(segment_data))


def create_otio_timeline(
        sequence, validation_aggregator: lib.ValidationAggregator = None):
    if validation_aggregator is None:
        validation_aggregator = lib.ValidationAggregator()

    log.info(dir(sequence))
    log.info(sequence.attributes)

    OtioExportCTX.project = get_current_flame_project()

    # get current timeline
    OtioExportCTX.set_fps(
        float(str(sequence.frame_rate)[:-4]))

    tl_start_frame = timecode_to_frames(
        str(sequence.start_time).replace("+", ":"),
        OtioExportCTX.get_fps()
    )
    OtioExportCTX.set_tl_start_frame(tl_start_frame)

    timeline_builder = builder.TimelineBuilder(
        str(sequence.name)[1:-1],
        OtioExportCTX.get_fps(),
        start_frame=OtioExportCTX.get_tl_start_frame(),
        metadata=_get_timeline_metadata(sequence),
        gap_mode=builder.GAP_RECORD,
        sequence_fallback_padded=False,
    )

    # create otio video tracks with clips
    for ver in sequence.versions:
        for track in ver.tracks:
            # avoid all empty tracks
            # or hidden tracks
            if (
                len(track.segments) == 0
                or track.hidden.get_value()
            ):
                continue

            track_builder = timeline_builder.add_track(
                str(track.name)[1:-1], "Video")
            _fill_track(track_builder, track, validation_aggregator)

    # create otio audio tracks with clips
    for audio_track in sequence.audio_tracks:

        if (
            len(audio_track.channels) == 0
            and audio_track.stereo and len(audio_track.channels) < 2
        ):
            # Unsupported audio_track do not export.
            log.debug(f"Unsupported audio track: {audio_track!r}")
            continue

        # only the first channel is exported
        audio_channel = audio_track.channels[0]

        # avoid all empty tracks
        # or hidden tracks
        if (
            len(audio_channel.segments) == 0
            or audio_channel.hidden.get_value()
        ):
            log.debug(f"Hidden or empty channel: {audio_channel!r}")
            continue

        track_builder = timeline_builder.add_track(
            audio_track.name or "unnamed", "Audio")
        _fill_track(track_builder, audio_channel, validation_aggregator)

    return timeline_builder.build()


def write_to_file(otio_timeline, path):
    builder.write_to_file(otio_timeline, path)
