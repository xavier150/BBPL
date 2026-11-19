import bpy
from typing import List

class SkinWeightMeshUpdater:
    """
    A class to update mesh skin weights by renaming vertex groups.
    """
    def __init__(self):
        self.update_weights: int = 0
        self.remove_weights: int = 0
        self.print_log: bool = False

    def update_mesh_skin_weight(self, obj: bpy.types.Object, old_names: List[str], new_name: str):
        """
        Updates the skin weights of a mesh by renaming one or more old vertex groups to a new name.

        Args:
            obj (bpy.types.Object): The object whose skin weights need to be updated.
            old_names (list of str): A list of names of old vertex groups to rename.
            new_name (str): The new name for the specified vertex groups.

        Returns:
            None

        :param obj: The object whose skin weights need to be updated.
        :param old_names: A list of names of old vertex groups to rename.
        :param new_name: The new name for the specified vertex groups.
        """

        if not isinstance(obj.data, bpy.types.Mesh):
            print("The object is not a mesh.")
            return

        # Check if the object has vertex groups
        if not obj.vertex_groups:
            print("The object does not contain any vertex groups.")
            return

        for old_name in old_names:
            vg_old = obj.vertex_groups.get(old_name)
            if not vg_old:
                if self.print_log:
                    print(f"The vertex group '{old_name}' does not exist in the object: '{obj.name}'.")
                continue
            
            # Check if the new vertex group already exists, if not, create it
            vg_new = obj.vertex_groups.get(new_name)
            if not vg_new:
                vg_new = obj.vertex_groups.new(name=new_name)

            # Copy vertex weights from the old group to the new group
            for vert in obj.data.vertices:
                for group in vert.groups:
                    if group.group == vg_old.index:
                        vg_new.add([vert.index], group.weight, 'REPLACE')

            # Remove the old vertex group
            obj.vertex_groups.remove(vg_old)
            if self.print_log:
                print(f"The vertex group '{old_name}' has been renamed to '{new_name}'.")
            self.update_weights += 1

    def print_update_log(self):
        """
        Print a log of the number of data variables updated and removed.

        Args:
            None

        Returns:
            None
        """
        print(f'{self.update_weights} vertex groups have been updated.')
        print(f'{self.remove_weights} vertex groups have been removed.')