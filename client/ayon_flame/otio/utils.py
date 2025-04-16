import os
import re
import opentimelineio as otio
import logging

from ayon_core.lib.transcoding import IMAGE_EXTENSIONS


log = logging.getLogger(__name__)

FRAME_PATTERN = r"[\._](\d+)"


def timecode_to_frames(timecode, framerate):
    rt = otio.opentime.from_timecode(timecode, framerate)
    return int(otio.opentime.to_frames(rt))


def frames_to_timecode(frames, framerate):
    rt = otio.opentime.from_frames(frames, framerate)
    return otio.opentime.to_timecode(rt)


def frames_to_seconds(frames, framerate):
    rt = otio.opentime.from_frames(frames, framerate)
    return otio.opentime.to_seconds(rt)


def get_reformatted_filename(filename, padded=True):
    """
    Return fixed python expression path

    Args:
        filename (str): file name

    Returns:
        type: string with reformatted path

    Example:
        get_reformatted_filename("plate.1001.exr") > plate.%04d.exr

    """
    found = FRAME_PATTERN.search(filename)

    if not found:
        log.info("File name is not sequence: {}".format(filename))
        return filename

    padding = get_padding_from_filename(filename)

    replacement = "%0{}d".format(padding) if padded else "%d"
    start_idx, end_idx = found.span(1)

    return replacement.join(
        [filename[:start_idx], filename[end_idx:]]
    )


def get_padding_from_filename(filename):
    """
    Return padding number from Flame path style

    Args:
        filename (str): file name

    Returns:
        int: padding number

    Example:
        get_padding_from_filename("plate.0001.exr") > 4

    """
    found = get_frame_from_filename(filename)

    return len(found) if found else None


def get_frame_from_filename(filename):
    """
    Return sequence number from Flame path style

    Args:
        filename (str): file name

    Returns:
        Optional[str]: sequence frame number if found or None

    Example:
        def get_frame_from_filename(path):
            ("plate.0001.exr") > "0001"

    """
    _, ext = os.path.splitext(filename)

    if ext.lower() not in IMAGE_EXTENSIONS:
        return None

    pattern = re.compile(FRAME_PATTERN + ext)
    found = re.findall(pattern, filename)

    return found.pop() if found else None


def get_marker_from_clip_index(otio_timeline, clip_index):
    """
    Return the clip and marker data from clip index.

    Args:
        otio_timeline (dict): otio timeline
        clip_index (str): The clip index.

    Returns:
        dict: otio clip object

    """
    import ayon_flame.api as ayfapi

    for otio_clip in otio_timeline.find_clips():

        # Retrieve otioClip from parent context otioTimeline
        # See collect_current_project
        for marker in otio_clip.markers:

            if ayfapi.MARKER_NAME not in marker.name:
                continue

            if marker.metadata.get("clip_index") == clip_index:
                return otio_clip, marker

    return None, None
