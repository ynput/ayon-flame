import os
import json
from typing import Dict, List

from ayon_applications import PostLaunchHook, LaunchTypes
from ayon_core.pipeline import Anatomy
from ayon_core.pipeline.anatomy import AnatomyStringTemplate
from ayon_core.pipeline.template_data import get_project_template_data


# Paths of the default bookmarks Flame adds to every project
FLAME_DEFAULT_BOOKMARK_PATHS = {"<project home>", "<project setups>"}


class FlamePostLaunch(PostLaunchHook):

    app_groups = {"flame"}
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
            setups_dir (str): Flame project setups directory, read
                from Wiretap by the prelaunch hook.
            bookmark_paths (dict[str, str]): Bookmark paths
            remove_default_bookmarks (bool): Remove the bookmarks Flame
                adds to every project, e.g. Project Home.
        """
        if not os.path.isdir(setups_dir):
            self.log.error(
                f"Unable to create bookmarks, Flame project setups folder "
                f"'{setups_dir}' does not exist"
            )
            return
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

        Will not run if bookmarks are disabled, the Flame project setups
        folder was not found from Wiretap, or no bookmarks defined in
        the settings.
        """
        project_settings = self.data["project_settings"]

        bookmark_settings = project_settings["flame"]["bookmarks"]

        if not bookmark_settings["enabled"]:
            self.log.info("Bookmarks disabled")
            return

        setups_dir = self.data.get("flame_project_setups_dir")
        if not setups_dir:
            self.log.error(
                "Unable to create bookmarks, Flame project setups folder "
                "was not found from Wiretap"
            )
            return

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
