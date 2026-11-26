import os
import json
import stat
import shutil
import filecmp
import platform
from functools import cached_property
from typing import Dict, List, Optional, Union

from ayon_applications import PostLaunchHook, LaunchTypes
from ayon_core.lib import filter_profiles
from ayon_core.pipeline import Anatomy
from ayon_core.pipeline.anatomy import AnatomyStringTemplate
from ayon_core.pipeline.template_data import get_project_template_data


# Paths of the default bookmarks Flame adds to every project
FLAME_DEFAULT_BOOKMARK_PATHS = {"<project home>", "<project setups>"}

# Lists the export presets installed from the central folder, so presets
# removed from it can be removed from the project too
EXPORT_PRESETS_MANIFEST = ".ayon_export_presets.json"


class BaseProjectRootException(Exception):
    """Base exception for this module"""


class NoProjectRootFoldersFound(BaseProjectRootException):
    """Raised when no project folders are found on disk"""


class NoProjectRootSettingsFound(BaseProjectRootException):
    """Raised when there are no project root folders specified in the
    settings or when the settings do not contain the required system paths.
    """


class FlamePostLaunch(PostLaunchHook):

    app_groups = {"flame", "flameassist", "flare"}
    order = 1
    launch_types = {LaunchTypes.local}

    def _create_bookmarks(
        self,
        setups_dir: str,
        bookmark_paths: Dict[str, str],
        remove_default_bookmarks: bool = False
    ) -> None:
        """Create bookmarks for project.

        As multiple roots can be defined, this will create a bookmark for each
        root respectively.

        This will respect previously set up bookmarks, only removing those
        with the same label or path in favour of the new ones.

        Args:
            setups_dir (str): The Flame project's setups folder.
            bookmark_paths (dict[str, str]): Bookmark paths
            remove_default_bookmarks (bool): Remove the bookmarks Flame
                adds to every project, e.g. Project Home.
        """
        bookmarks_path = os.path.join(
            setups_dir,
            "status",
            "cf_bookmarks.json"
        )
        self.log.info(f"Creating bookmarks at '{bookmarks_path}'")
        if os.path.exists(bookmarks_path):
            with open(bookmarks_path, "r") as bookmark_file:
                data = json.load(bookmark_file)
        else:
            # this is the default bookmark data
            data = {
                "DlBookmark": {
                    "Version": 1,
                    "Sections": [
                        {
                            "Section": "Project",
                            "Bookmarks": [
                                {
                                    "Bookmark": "Project Home",
                                    "Path": "<project home>",
                                    "Visibility": "Global"
                                }
                            ]
                        }
                    ]
                }
            }

        bookmarks = []
        all_bookmark_paths = set()
        for label, path in bookmark_paths.items():
            bookmarks.append(
                {
                    "Bookmark": label,
                    "Path": path,
                    "Visibility": "Global"
                }
            )
            all_bookmark_paths.add(path)
        if remove_default_bookmarks:
            all_bookmark_paths.update(FLAME_DEFAULT_BOOKMARK_PATHS)

        sections = data["DlBookmark"]["Sections"]
        if not any(section["Section"] == "Project" for section in sections):
            sections.append({"Section": "Project", "Bookmarks": []})

        for section in sections:
            if section["Section"] == "Project":
                filtered_bookmarks = [
                    bookmark
                    for bookmark in section.get("Bookmarks", [])
                    if bookmark["Path"] not in all_bookmark_paths
                    and bookmark["Bookmark"] not in bookmark_paths
                ]
                # insert after Flame's own bookmarks, e.g. "<project home>"
                index = next(
                    (
                        index
                        for index, bookmark in enumerate(filtered_bookmarks)
                        if not bookmark["Path"].startswith("<")
                    ),
                    len(filtered_bookmarks)
                )
                section["Bookmarks"] = (
                    filtered_bookmarks[:index]   # Flame's own bookmarks
                    + bookmarks                   # project root bookmarks
                    + filtered_bookmarks[index:]  # remaining bookmarks
                )

        is_new_file = not os.path.exists(bookmarks_path)
        os.makedirs(os.path.dirname(bookmarks_path), exist_ok=True)
        with open(bookmarks_path, "w") as bookmark_file:
            json.dump(data, bookmark_file, ensure_ascii=True, indent=4)
        if is_new_file:
            # let other users update it too, like Flame's own files
            os.chmod(bookmarks_path, 0o666)

    def _sync_export_presets(self, source_dir: str, presets_dir: str) -> None:
        """Mirror export presets from a central folder into the project.

        Presets installed by a previous launch but no longer in the central
        folder are removed. Presets made in the project are left alone,
        unless the central folder has one with the same name.

        Args:
            source_dir (str): Central folder with one subfolder per export
                type, e.g. 'movie_file'.
            presets_dir (str): The Flame project's export presets folder.
        """
        self.log.info(
            f"Syncing export presets from '{source_dir}' to '{presets_dir}'"
        )
        manifest_path = os.path.join(presets_dir, EXPORT_PRESETS_MANIFEST)
        previous_presets = set()
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as manifest_file:
                    previous_presets = set(json.load(manifest_file))
            except ValueError:
                self.log.warning(
                    f"Unable to read '{manifest_path}', "
                    "no presets will be removed"
                )

        presets = []
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            for filename in files:
                if filename.startswith(".") or not filename.endswith(".xml"):
                    continue
                source_path = os.path.join(root, filename)
                preset = os.path.relpath(source_path, source_dir)
                presets.append(preset)

                target_path = os.path.join(presets_dir, preset)
                is_new_file = not os.path.exists(target_path)
                if not is_new_file and filecmp.cmp(
                    source_path, target_path, shallow=False
                ):
                    continue
                self._makedirs(os.path.dirname(target_path))
                shutil.copyfile(source_path, target_path)
                if is_new_file:
                    self._make_writable(target_path)

        removed_count = 0
        for preset in previous_presets - set(presets):
            preset_path = os.path.join(presets_dir, preset)
            # only remove presets inside the project's presets folder
            if (
                preset.endswith(".xml")
                and self._is_inside(preset_path, presets_dir)
                and os.path.isfile(preset_path)
            ):
                os.remove(preset_path)
                removed_count += 1

        is_new_file = not os.path.exists(manifest_path)
        self._makedirs(presets_dir)
        with open(manifest_path, "w") as manifest_file:
            json.dump(sorted(presets), manifest_file, indent=4)
        if is_new_file:
            self._make_writable(manifest_path)

        self.log.info(
            f"Synced {len(presets)} export presets, "
            f"removed {removed_count}"
        )

    def _makedirs(self, path: str) -> None:
        """Create missing folders, writable by all users like Flame's own."""
        missing = []
        while path and not os.path.isdir(path):
            missing.append(path)
            path = os.path.dirname(path)
        for folder in reversed(missing):
            os.mkdir(folder)
            self._make_writable(folder)

    @staticmethod
    def _make_writable(path: str) -> None:
        """Let other users update a file or folder this hook created."""
        mode = 0o777 if os.path.isdir(path) else 0o666
        os.chmod(path, stat.S_IMODE(os.stat(path).st_mode) | mode)

    @staticmethod
    def _is_inside(path: str, folder: str) -> bool:
        path = os.path.realpath(path)
        folder = os.path.realpath(folder)
        return os.path.commonpath([path, folder]) == folder

    def _get_projects_root(
        self,
        variants: List[Dict[str, Union[List[str], str]]]
    ) -> str:
        # AYON_APP_NAME is only set in the launch environment, not in the
        # launcher process running this hook
        flame_app_name = self.app_name or ""
        flame_variant = flame_app_name.split("/", 1)[-1]
        filter_profile = {"name": flame_variant}

        root_profile = filter_profiles(
            variants, filter_profile, logger=self.log
        )

        if not root_profile:
            raise NoProjectRootSettingsFound(
                f"No project roots for `{flame_app_name}` found in settings"
            )
        system_name = platform.system().lower()
        project_paths = root_profile["project_path"][system_name]
        if not project_paths:
            raise NoProjectRootSettingsFound(
                f"No project roots for `{flame_app_name}` ({system_name}) "
                "found in settings"
            )
        for project_path in project_paths:
            if os.path.isdir(project_path):
                return project_path
            self.log.debug(f"{project_path} does not exist, skipped")

        raise NoProjectRootFoldersFound(
            "Could not find a project root folder on disk."
        )

    def _get_project_setups_dir(self, projects_root: str) -> Optional[str]:
        """Get the launched Flame project's setups folder.

        Flame 2026+ keeps it in the project's 'setups' folder, older
        versions use the project folder itself.
        """
        project_dir = os.path.join(
            projects_root, self.data["project_entity"]["name"]
        )
        if not os.path.isdir(project_dir):
            self.log.error(
                f"Flame project folder '{project_dir}' does not exist"
            )
            return None

        setups_dir = os.path.join(project_dir, "setups")
        if os.path.isdir(setups_dir):
            return setups_dir
        return project_dir

    @cached_property
    def _anatomy(self) -> Anatomy:
        project_entity = self.data["project_entity"]
        return Anatomy(project_entity["name"], project_entity=project_entity)

    def _format_template(self, template: str) -> str:
        """Format a template with the project's 'root' and 'project' data."""
        template_data = get_project_template_data(self.data["project_entity"])
        return AnatomyStringTemplate(
            self._anatomy.templates_obj, template
        ).format(template_data)

    def _get_bookmark_paths(
        self, bookmark_settings: List[Dict[str, str]]
    ) -> Dict[str, str]:
        if not bookmark_settings:
            return {}

        paths = {}
        for item in bookmark_settings:
            self.log.debug(item["name"])
            path = self._format_template(item["path_template"])
            # we need to add a "/" at the end if not already there
            # to keep in line with how flame likes to store the paths
            if not path.endswith(os.path.sep):
                path += os.path.sep
            label = self._format_template(item["bookmark_label"])
            paths[label] = path
        return paths

    def _setup_bookmarks(
        self, setups_dir: str, bookmark_settings: Dict
    ) -> None:
        bookmark_paths = self._get_bookmark_paths(
            bookmark_settings["bookmark_paths"]
        )
        remove_default_bookmarks = (
            bookmark_settings["remove_default_bookmarks"]
        )
        if not bookmark_paths and not remove_default_bookmarks:
            self.log.info("No bookmarks to create.")
            return

        try:
            self._create_bookmarks(
                setups_dir,
                bookmark_paths,
                remove_default_bookmarks,
            )
        except (OSError, ValueError) as error:
            self.log.error("Unable to update bookmarks file")
            self.log.exception(error)

    def _setup_export_presets(
        self, setups_dir: str, presets_settings: Dict
    ) -> None:
        if not presets_settings["source_dir"]:
            self.log.warning("No central export presets folder set.")
            return

        source_dir = self._format_template(presets_settings["source_dir"])
        if not os.path.isdir(source_dir):
            self.log.error(
                f"Central export presets folder '{source_dir}' "
                "does not exist"
            )
            return

        # Flame keeps the project's export presets in an extra 'flame'
        # folder, unlike shared presets: export/presets/flame/<type>
        presets_dir = os.path.join(setups_dir, "export", "presets", "flame")
        try:
            self._sync_export_presets(source_dir, presets_dir)
        except OSError as error:
            self.log.error("Unable to sync export presets")
            self.log.exception(error)

    def execute(self) -> None:
        """Sets up the launched Flame project's bookmarks and export presets
        from the flame settings.

        Will not run if both are disabled or there are no valid project
        roots defined.
        """
        flame_settings = self.data["project_settings"]["flame"]
        bookmark_settings = flame_settings["bookmarks"]
        presets_settings = flame_settings["export_presets"]

        if not bookmark_settings["enabled"]:
            self.log.info("Bookmarks disabled")
        if not presets_settings["enabled"]:
            self.log.info("Export presets disabled")
        if not (bookmark_settings["enabled"] or presets_settings["enabled"]):
            return

        try:
            projects_root = self._get_projects_root(
                flame_settings["flame_projects_root"]["variants"]
            )
        except BaseProjectRootException as error:
            self.log.error("Unable to find the Flame projects folder")
            self.log.exception(error)
            return

        setups_dir = self._get_project_setups_dir(projects_root)
        if not setups_dir:
            return

        if bookmark_settings["enabled"]:
            self._setup_bookmarks(setups_dir, bookmark_settings)
        if presets_settings["enabled"]:
            self._setup_export_presets(setups_dir, presets_settings)
