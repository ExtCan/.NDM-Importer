"""
NDM Importer - Blender addon for importing NDM model files and DTX textures.
"""

bl_info = {
    "name": "NDM Importer",
    "author": "NDM Importer Team",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > NDM (.ndm)",
    "description": "Import NDM model files with materials, textures, vertex colors, rigging, and blend shapes",
    "category": "Import-Export",
}

import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, OperatorFileListElement

# Import our modules
from . import ndm_parser
from . import dtx_loader
from . import mesh_builder


class ImportNDM(Operator, ImportHelper):
    """Import an NDM model file"""
    bl_idname = "import_scene.ndm"
    bl_label = "Import NDM"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".ndm"

    filter_glob: StringProperty(
        default="*.ndm;*.NDM",
        options={'HIDDEN'},
        maxlen=255,
    )

    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
    )

    directory: StringProperty(subtype='DIR_PATH')

    import_textures: BoolProperty(
        name="Import Textures",
        description="Load DTX textures as materials",
        default=True,
    )

    import_vertex_colors: BoolProperty(
        name="Import Vertex Colors",
        description="Import vertex color data",
        default=True,
    )

    import_normals: BoolProperty(
        name="Import Normals",
        description="Import custom normals",
        default=True,
    )

    import_armature: BoolProperty(
        name="Import Armature",
        description="Import bone/rigging data if present",
        default=True,
    )

    import_shape_keys: BoolProperty(
        name="Import Shape Keys",
        description="Import blend shapes/morph targets if present",
        default=True,
    )

    scale_factor: bpy.props.FloatProperty(
        name="Scale",
        description="Scale factor for imported geometry",
        default=0.01,
        min=0.0001,
        max=1000.0,
    )

    def execute(self, context):
        import os

        if not self.files:
            # Single file import
            return self.import_ndm_file(context, self.filepath)

        # Multiple file import
        for file_elem in self.files:
            filepath = os.path.join(self.directory, file_elem.name)
            result = self.import_ndm_file(context, filepath)
            if result != {'FINISHED'}:
                return result

        return {'FINISHED'}

    def import_ndm_file(self, context, filepath):
        import os

        try:
            # Parse the NDM file
            ndm_data = ndm_parser.parse_ndm(filepath)

            if ndm_data is None:
                self.report({'ERROR'}, f"Failed to parse NDM file: {filepath}")
                return {'CANCELLED'}

            # Get the directory for texture lookup
            directory = os.path.dirname(filepath)
            base_name = os.path.splitext(os.path.basename(filepath))[0]

            # Build the mesh(es) in Blender
            mesh_builder.build_meshes(
                context,
                ndm_data,
                base_name,
                directory,
                import_textures=self.import_textures,
                import_vertex_colors=self.import_vertex_colors,
                import_normals=self.import_normals,
                import_armature=self.import_armature,
                import_shape_keys=self.import_shape_keys,
                scale_factor=self.scale_factor,
            )

            self.report({'INFO'}, f"Successfully imported: {filepath}")
            return {'FINISHED'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error importing NDM: {str(e)}")
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "import_textures")
        layout.prop(self, "import_vertex_colors")
        layout.prop(self, "import_normals")
        layout.prop(self, "import_armature")
        layout.prop(self, "import_shape_keys")
        layout.prop(self, "scale_factor")


def menu_func_import(self, context):
    self.layout.operator(ImportNDM.bl_idname, text="NDM (.ndm)")


def register():
    bpy.utils.register_class(ImportNDM)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportNDM)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
