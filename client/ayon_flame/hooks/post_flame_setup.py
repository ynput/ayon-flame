import os
import json
import platform
from typing import Dict, List, Union

from ayon_applications import PostLaunchHook, LaunchTypes
from ayon_core.lib import filter_profiles
from ayon_core.pipeline import Anatomy
from ayon_core.pipeline.anatomy import AnatomyStringTemplate
from ayon_core.pipeline.template_data import get_project_template_data


class BaseProjectRootException(Exception):
    """Base exception for this module"""


class NoProjectRootFoldersFound(BaseProjectRootException):
    """Raised when no project folders are found on disk"""


class NoProjectRootSettingsFound(BaseProjectRootException):
    """Raised when there are no project root folders specified in the
    settings or when the settings do not contain the required system paths.
    """


class FlamePostLaunch(PostLaunchHook):

    app_groups = {"flame"}
    order = 1
    launch_types = {LaunchTypes.local}

    def _create_bookmarks(
        self,
        project_name: str,
        projects_root: str,
        bookmark_paths: Dict[str, str]
    ) -> None:
        """Create bookmarks for project.

        As multiple roots can be defined, this will create a bookmark for each
        root respectively.

        This will respect previously set up bookmarks, only removing duplicate
        bookmarked paths in favour of the new ones.

        Args:
            project_name (str): Name of the project
            projects_root (str): Path to flame projects' location on disk.
            bookmark_paths (dict[str, str]): Bookmark paths
        """
        bookmarks_path = os.path.join(
            projects_root,
            project_name,
            "status",
            "cf_bookmarks.json"
        )
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
        for label, path in bookmark_paths.items():
            bookmarks.append(
                {
                    "Bookmark": label,
                    "Path": path,
                    "Visibility": "Global"
                }
            )

        for section in data["DlBookmark"]["Sections"]:
            if section["Section"] == "Project":
                filtered_bookmarks = [
                    bookmark
                    for bookmark in section["Bookmarks"]
                    if bookmark["Path"] not in bookmark_paths
                ]
                # insert directly after the default "Project Home" bookmark
                section["Bookmarks"] = (
                    filtered_bookmarks[:1]   # default Project Home bookmark
                    + bookmarks               # project root bookmarks
                    + filtered_bookmarks[1:]  # remaining preexisting bookmarks
                )

        os.makedirs(os.path.dirname(bookmarks_path), exist_ok=True)
        with open(bookmarks_path, "w") as bookmark_file:
            json.dump(data, bookmark_file, ensure_ascii=True, indent=4)

    def _get_projects_root(
        self,
        variants: List[Dict[str, Union[List[str], str]]]
    ) -> str:
        flame_app_name = os.getenv("AYON_APP_NAME", "")
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

    def _get_bookmark_paths(
        self, bookmark_settings: List[Dict[str, str]]
    ) -> Dict[str, str]:
        if not bookmark_settings:
            return {}

        project_entity = self.data["project_entity"]
        project_name = project_entity["name"]
        anatomy = Anatomy(project_name, project_entity=project_entity)
        template_data = get_project_template_data(project_entity)

        paths = {}
        for item in bookmark_settings:
            self.log.debug(item["name"])
            template = AnatomyStringTemplate(
                anatomy.templates_obj, item["path_template"]
            )
            path = template.format(template_data)
            # we need to add a "/" at the end if not already there
            # to keep in line with how flame likes to store the paths
            if not path.endswith(os.path.sep):
                path += os.path.sep
            label_template = AnatomyStringTemplate(
                anatomy.templates_obj, item["bookmark_label"]
            )
            label = label_template.format(template_data)
            paths[label] = path
        return paths

    def execute(self) -> None:
        """Collects the bookmark path templates defined in the flame settings
        and sets up the bookmarks file for flame to point to them.

        Will not run if bookmarks are disabled, there are no valid project
        roots defined, or no bookmarks defined in the settings.
        """
        project_settings = self.data["project_settings"]

        bookmark_settings = project_settings["flame"]["bookmarks"]

        if not bookmark_settings["enabled"]:
            self.log.info("Bookmarks disabled")
            return

        try:
            project_root = self._get_projects_root(
                bookmark_settings["flame_projects_root"]
            )
        except BaseProjectRootException as error:
            self.log.error("Unable to create bookmarks")
            self.log.exception(error)
            return

        bookmark_paths = self._get_bookmark_paths(
            bookmark_settings["bookmark_paths"]
        )
        if not bookmark_paths:
            self.log.info("No bookmarks to create.")
            return

        self._create_bookmarks(
            self.data["project_entity"]["name"],
            project_root,
            bookmark_paths,
        )
