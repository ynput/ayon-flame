"""Host API required Work Files tool"""
import os

exported_project_ext = ".otoc"


def file_extensions():
    return [exported_project_ext]


def has_unsaved_changes():
    raise NotImplementedError("Flame use native workfile management")


def save_file(filepath):
    raise NotImplementedError("Flame use native workfile management")


def open_file(filepath):
    raise NotImplementedError("Flame use native workfile management")


def current_file():
    raise NotImplementedError("Flame use native workfile management")


def work_root(session):
    return os.path.normpath(session["AYON_WORKDIR"])
