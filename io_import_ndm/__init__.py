"""
NDM Importer for Blender
Imports .NDM model files from Nintendo GameCube's ind-nddemo (Peach's Castle Demo)

Author: Generated for NDM-Importer project
"""

bl_info = {
    "name": "NDM Model Importer",
    "author": "NDM-Importer Project",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > NDM (.ndm)",
    "description": "Import NDM model files from GameCube's Peach's Castle Demo",
    "category": "Import-Export",
}

import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty

from . import ndm_parser


class ImportNDM(bpy.types.Operator):
    """Import an NDM file from the GameCube Peach's Castle Demo"""
    bl_idname = "import_scene.ndm"
    bl_label = "Import NDM"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="File Path",
        description="Filepath used for importing the NDM file",
        maxlen=1024,
        subtype='FILE_PATH',
    )

    filter_glob: StringProperty(
        default="*.ndm;*.NDM",
        options={'HIDDEN'},
    )

    import_textures: BoolProperty(
        name="Import Textures",
        description="Attempt to import referenced textures (DTX files)",
        default=True,
    )

    scale_factor: FloatProperty(
        name="Scale",
        description="Scale factor for imported model",
        default=0.01,
        min=0.0001,
        max=100.0,
    )
    
    merge_meshes: BoolProperty(
        name="Merge Meshes",
        description="Merge all meshes into a single object (alternative import method)",
        default=False,
    )

    def execute(self, context):
        return ndm_parser.import_ndm(context, self.filepath, self.import_textures, 
                                     self.scale_factor, self.merge_meshes)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "import_textures")
        layout.prop(self, "scale_factor")
        layout.prop(self, "merge_meshes")


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
