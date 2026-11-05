"""Helpers to find the AYON marker of a clip in an OTIO timeline.

Frame, timecode and path helpers live in `ayon_editorial.otio` (time,
paths) and `ayon_flame.api` (`get_frame_from_filename` and friends).
"""


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
