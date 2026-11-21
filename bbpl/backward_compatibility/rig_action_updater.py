# SPDX-FileCopyrightText: Xavier Loux (BleuRaven)
#
# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------
#  BBPL -> BleuRaven Blender Python Library
#  https://github.com/xavier150/BBPL
# ----------------------------------------------

from typing import TYPE_CHECKING, Callable, Iterator, List, Optional, Set, Tuple, cast

import bpy

CONFLIT_RESOLUTIONS: Tuple[str, ...] = ("keep_both", "remove_old", "remove_new")

if TYPE_CHECKING:
    from typing import Protocol

    class _FCurveCollection(Protocol):
        def __iter__(self) -> Iterator[bpy.types.FCurve]: ...

        def find(self, data_path: str, *, index: int = 0) -> Optional[bpy.types.FCurve]: ...

        def remove(self, fcurve: bpy.types.FCurve) -> None: ...


class RigActionUpdater:
    """
    A class to update FCurves in Blender actions by modifying their data paths.

    Uses legacy action FCurves before Blender 4.4 and per-slot channelbags
    in Blender 4.4 and newer.
    """
    def __init__(self) -> None:
        self.update_fcurve: int = 0
        self.remove_fcurve: int = 0
        self.print_log: bool = False

    def _fcurve_collections(self, action: bpy.types.Action) -> Iterator["_FCurveCollection"]:
        if bpy.app.version >= (4, 4, 0):
            for layer in action.layers:
                for strip in layer.strips:
                    if strip.type == 'KEYFRAME':
                        for slot in action.slots:
                            channelbag = strip.channelbag(slot)
                            if channelbag is not None:
                                yield cast("_FCurveCollection", channelbag.fcurves)
        else:
            # Modern bpy stubs no longer declare the legacy Action.fcurves API.
            yield cast("_FCurveCollection", getattr(action, "fcurves"))

    def update_action_curve_data_path(
        self, action: bpy.types.Action, old_data_paths: List[str], new_data_path: str,
        remove_if_already_exists: bool = False, show_debug: bool = False, *,
        conflit_resolution: Optional[str] = None, exact_match: bool = False,
    ) -> None:
        """
        Update the data paths of FCurves in a given action by replacing old data paths with a new one.

        Args:
            action (bpy.types.Action): The Blender action containing FCurves to be updated.
            old_data_paths (list of str): A list of old data paths to search for and replace.
            new_data_path (str): The new data path to replace the old ones with.
            remove_if_already_exists (bool, optional): Legacy collision handling when
                conflit_resolution is not specified.
            conflit_resolution (str, optional): One of CONFLIT_RESOLUTIONS.
            exact_match (bool, optional): Match the entire data path instead of a substring.

        Returns:
            None
        """
        if conflit_resolution is None:
            conflit_resolution = "remove_old" if remove_if_already_exists else "keep_both"
        if conflit_resolution not in CONFLIT_RESOLUTIONS:
            raise ValueError(f"Unknown conflict resolution: {conflit_resolution!r}.")
        for fcurves in self._fcurve_collections(action):
            self._update_fcurve_collection(
                action, fcurves, old_data_paths, new_data_path, conflit_resolution, show_debug, exact_match,
            )

    def _update_fcurve_collection(
        self,
        action: bpy.types.Action,
        fcurves: "_FCurveCollection",
        old_data_paths: List[str],
        new_data_path: str,
        conflit_resolution: str,
        show_debug: bool,
        exact_match: bool,
    ) -> None:
        cache_action_fcurves = [(fcurve, fcurve.as_pointer()) for fcurve in fcurves]
        # A conflicting destination can also be present later in the snapshot.
        removed_pointers: Set[int] = set()

        for action_fcurve, pointer in cache_action_fcurves:
            if pointer in removed_pointers:
                continue
            for old_data_path in old_data_paths:
                current_target = action_fcurve.data_path

                if (current_target == old_data_path if exact_match else old_data_path in current_target):
                    # ---
                    if show_debug: 
                        print(f"{old_data_path} found in {current_target} for action {action.name}.")

                    new_target = current_target.replace(old_data_path, new_data_path)
                    if new_target == current_target:
                        continue
                    existing = fcurves.find(new_target, index=action_fcurve.array_index)
                    if existing is not None and conflit_resolution == "remove_old":
                        fcurves.remove(action_fcurve)
                        self.remove_fcurve += 1
                        if self.print_log or show_debug:
                            print(f'"{current_target}" removed in {action.name} action; keeping "{new_target}".')
                        break
                    if existing is not None and conflit_resolution == "keep_both":
                        if self.print_log or show_debug:
                            print(f'"{current_target}" can not be updated to "{new_target}" in {action.name} action. (Already exists!)')
                        continue
                    if existing is not None:
                        removed_pointers.add(existing.as_pointer())
                        fcurves.remove(existing)
                        self.remove_fcurve += 1
                    action_fcurve.data_path = new_target
                    if self.print_log or show_debug:
                        print(f'"{current_target}" updated to "{new_target}" in {action.name} action.')
                    self.update_fcurve += 1
                else:
                    if show_debug: 
                        print(f"{old_data_path} not found in {current_target} for action {action.name}.")

    def remove_action_curve_by_data_path(
        self, action: bpy.types.Action, data_paths: List[str], *,
        exact_match: bool = False, starts_with: bool = False,
    ) -> None:
        """
        Remove FCurves from a given action based on specified data paths.

        Args:
            action (bpy.types.Action): The Blender action containing FCurves to be checked and removed.
            data_paths (list of str): A list of data paths to identify FCurves for removal.
            exact_match (bool, optional): Match the entire data path instead of a substring.
            starts_with (bool, optional): Match a prefix instead of a substring.

        Returns:
            None
        """
        if exact_match and starts_with:
            raise ValueError("exact_match and starts_with cannot both be enabled.")
        for fcurves in self._fcurve_collections(action):
            self._remove_from_fcurve_collection(action, fcurves, data_paths, exact_match, starts_with)

    def _remove_from_fcurve_collection(
        self, action: bpy.types.Action, fcurves: "_FCurveCollection", data_paths: List[str],
        exact_match: bool, starts_with: bool,
    ) -> None:
        cache_action_fcurves: List[bpy.types.FCurve] = []
        for fcurve in fcurves:
            cache_action_fcurves.append(fcurve)

        for action_fcurve in cache_action_fcurves:
            for data_path in data_paths:
                current_target = action_fcurve.data_path
                if (
                    current_target == data_path if exact_match
                    else current_target.startswith(data_path) if starts_with
                    else data_path in current_target
                ):

                    # ---

                    fcurves.remove(action_fcurve)
                    if self.print_log:
                        print(f'"{current_target}" removed in {action.name} action.')
                    self.remove_fcurve += 1
                    break #FCurve removed so no need to test the other old_var_names

    def edit_action_curve(self, action: bpy.types.Action, data_paths: List[str], callback: Optional[Callable[[bpy.types.Action, bpy.types.FCurve, str], None]] = None) -> None:
        """
        Edit FCurves in a given action based on specified data paths using a custom callback function.

        Args:
            action (bpy.types.Action): The Blender action containing FCurves to be edited.
            data_paths (list of str): A list of data paths to identify FCurves for editing.
            callback (function, optional): A custom callback function that will be called for each matching FCurve.
                The callback function should accept three parameters: `action` (the action containing the FCurve),
                `fcurve` (the FCurve to be edited), and `data_path` (the matching data path). If callback is None,
                no editing is performed.

        Returns:
            None
        """
        for fcurves in self._fcurve_collections(action):
            self._edit_fcurve_collection(action, fcurves, data_paths, callback)

    def _edit_fcurve_collection(
        self,
        action: bpy.types.Action,
        fcurves: "_FCurveCollection",
        data_paths: List[str],
        callback: Optional[Callable[[bpy.types.Action, bpy.types.FCurve, str], None]],
    ) -> None:
        cache_action_fcurves: List[bpy.types.FCurve] = []
        for fcurve in fcurves:
            cache_action_fcurves.append(fcurve)


        for action_fcurve in cache_action_fcurves:
            for data_path in data_paths:
                current_target = action_fcurve.data_path
                if data_path in current_target:

                    # ---

                    if callback:
                        callback(action, action_fcurve, data_path)


    def print_update_log(self) -> None:
        """
        Print a log of the number of FCurves updated and removed.

        Args:
            None

        Returns:
            None
        """
        print(f'{self.update_fcurve} fcurve data_paths have been updated.')
        print(f'{self.remove_fcurve} fcurve data_paths have been removed.')
