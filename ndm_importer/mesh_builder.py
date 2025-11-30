"""
Mesh builder module for creating Blender meshes from NDM data.

This module handles:
- Creating mesh geometry (vertices, faces, UVs)
- Creating and assigning materials/textures
- Setting up vertex colors
- Creating armature/bones for rigging
- Creating shape keys for blend shapes
"""

import bpy
import bmesh
from mathutils import Vector, Matrix
import os
from typing import List, Optional

from . import dtx_loader
from .ndm_parser import NDMData, NDMNode, NDMMaterial


def build_meshes(
    context,
    ndm_data: NDMData,
    base_name: str,
    directory: str,
    import_textures: bool = True,
    import_vertex_colors: bool = True,
    import_normals: bool = True,
    import_armature: bool = True,
    import_shape_keys: bool = True,
    scale_factor: float = 0.01,
):
    """
    Build Blender meshes from NDM data.
    """
    # Create materials first
    materials = []
    if import_textures:
        materials = create_materials(ndm_data.materials, directory)

    # Create a collection for this import
    collection = bpy.data.collections.new(base_name)
    context.scene.collection.children.link(collection)

    # Create armature if rigging data exists
    armature_obj = None
    if import_armature and has_rigging_data(ndm_data):
        armature_obj = create_armature(ndm_data, base_name, collection, scale_factor)

    # Create meshes for each node
    created_objects = []
    for node in ndm_data.nodes:
        if len(node.vertices) == 0:
            continue

        obj = create_mesh_object(
            node,
            base_name,
            materials,
            scale_factor,
            import_vertex_colors,
            import_normals,
        )

        if obj:
            collection.objects.link(obj)
            created_objects.append(obj)

            # Parent to armature if available
            if armature_obj and import_armature:
                setup_armature_modifier(obj, armature_obj, node)

            # Add shape keys if available
            if import_shape_keys and node.shape_keys:
                setup_shape_keys(obj, node, scale_factor)

    # Select all created objects
    for obj in created_objects:
        obj.select_set(True)

    if created_objects:
        context.view_layer.objects.active = created_objects[0]

    return created_objects


def create_materials(
    ndm_materials: List[NDMMaterial],
    directory: str,
) -> List[bpy.types.Material]:
    """
    Create Blender materials from NDM material data.
    """
    materials = []

    for ndm_mat in ndm_materials:
        mat_name = ndm_mat.name if ndm_mat.name else f"Material_{ndm_mat.index}"

        # Check if material already exists
        if mat_name in bpy.data.materials:
            materials.append(bpy.data.materials[mat_name])
            continue

        # Create new material
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True

        # Get the principled BSDF node
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        principled = nodes.get('Principled BSDF')
        if not principled:
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')

        # Try to load the texture
        dtx_path = dtx_loader.find_dtx_file(directory, ndm_mat.name)
        if dtx_path:
            dtx_data = dtx_loader.load_dtx(dtx_path)
            if dtx_data:
                image = dtx_loader.create_blender_image(dtx_data, ndm_mat.name)
                if image:
                    # Create texture node
                    tex_node = nodes.new(type='ShaderNodeTexImage')
                    tex_node.image = image
                    tex_node.location = (-300, 300)

                    # Connect to principled BSDF
                    links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
                    links.new(tex_node.outputs['Alpha'], principled.inputs['Alpha'])

                    # Enable alpha blending
                    mat.blend_method = 'BLEND'

        # Set some default material properties
        try:
            principled.inputs['Roughness'].default_value = 0.5
        except KeyError:
            pass
        # Handle different Blender versions for Specular
        try:
            principled.inputs['Specular IOR Level'].default_value = 0.3
        except KeyError:
            try:
                principled.inputs['Specular'].default_value = 0.3
            except KeyError:
                pass

        materials.append(mat)

    return materials


def create_mesh_object(
    node: NDMNode,
    base_name: str,
    materials: List[bpy.types.Material],
    scale_factor: float,
    import_vertex_colors: bool,
    import_normals: bool,
) -> Optional[bpy.types.Object]:
    """
    Create a Blender mesh object from NDM node data.
    """
    if len(node.vertices) == 0:
        return None

    mesh_name = f"{base_name}_{node.name}" if node.name else base_name
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(mesh_name, mesh)

    # Create BMesh for mesh construction
    bm = bmesh.new()

    # Add vertices
    vert_map = []
    for i, vert in enumerate(node.vertices):
        pos = Vector(vert.position) * scale_factor
        bm_vert = bm.verts.new(pos)
        vert_map.append(bm_vert)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    # Add faces
    for face in node.faces:
        try:
            idx0, idx1, idx2 = face.indices
            if idx0 < len(vert_map) and idx1 < len(vert_map) and idx2 < len(vert_map):
                verts = [vert_map[idx0], vert_map[idx1], vert_map[idx2]]
                try:
                    bm_face = bm.faces.new(verts)
                    bm_face.smooth = True
                except ValueError:
                    # Face already exists or is degenerate
                    pass
        except (IndexError, ValueError):
            continue

    bm.faces.ensure_lookup_table()

    # Create UV layer
    if any(v.uv is not None for v in node.vertices):
        uv_layer = bm.loops.layers.uv.new("UVMap")
        for face in bm.faces:
            for loop in face.loops:
                vert_idx = loop.vert.index
                if vert_idx < len(node.vertices):
                    vert = node.vertices[vert_idx]
                    if vert.uv:
                        loop[uv_layer].uv = vert.uv

    # Create vertex colors
    if import_vertex_colors and (node.vertex_colors or any(v.color for v in node.vertices)):
        color_layer = bm.loops.layers.color.new("Col")
        for face in bm.faces:
            for loop in face.loops:
                vert_idx = loop.vert.index
                if vert_idx < len(node.vertices):
                    vert = node.vertices[vert_idx]
                    if vert.color:
                        r, g, b, a = vert.color
                        loop[color_layer] = (r/255.0, g/255.0, b/255.0, a/255.0)
                    elif vert_idx < len(node.vertex_colors):
                        r, g, b, a = node.vertex_colors[vert_idx]
                        loop[color_layer] = (r/255.0, g/255.0, b/255.0, a/255.0)

    # Convert BMesh to mesh
    bm.to_mesh(mesh)
    bm.free()

    # Import custom normals if available
    if import_normals:
        normals = []
        for vert in node.vertices:
            if vert.normal:
                normals.append(Vector(vert.normal))
            else:
                normals.append(Vector((0, 0, 1)))

        if normals and len(normals) == len(mesh.vertices):
            # use_auto_smooth was deprecated in Blender 4.0
            try:
                mesh.use_auto_smooth = True
            except AttributeError:
                pass  # Blender 4.0+
            try:
                mesh.normals_split_custom_set_from_vertices(normals)
            except Exception:
                pass  # In case normals can't be set

    # Assign materials
    if materials:
        mat_idx = node.material_index if node.material_index < len(materials) else 0
        if mat_idx < len(materials):
            mesh.materials.append(materials[mat_idx])

    # Update mesh
    mesh.update()

    # Set object transform
    if node.position:
        obj.location = Vector(node.position) * scale_factor

    if node.scale and node.scale != (1.0, 1.0, 1.0):
        obj.scale = Vector(node.scale)

    return obj


def has_rigging_data(ndm_data: NDMData) -> bool:
    """Check if the NDM data contains rigging/bone information."""
    for node in ndm_data.nodes:
        if node.bone_weights:
            return True
    return False


def create_armature(
    ndm_data: NDMData,
    base_name: str,
    collection: bpy.types.Collection,
    scale_factor: float,
) -> Optional[bpy.types.Object]:
    """
    Create an armature from NDM node hierarchy.
    """
    armature = bpy.data.armatures.new(f"{base_name}_Armature")
    armature_obj = bpy.data.objects.new(f"{base_name}_Armature", armature)
    collection.objects.link(armature_obj)

    # Enter edit mode to create bones
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')

    bone_map = {}

    # Create bones from hierarchy
    for type_flag, parent_idx, node_idx in ndm_data.hierarchy:
        if node_idx < len(ndm_data.nodes):
            node = ndm_data.nodes[node_idx]
            bone = armature.edit_bones.new(node.name or f"Bone_{node_idx}")
            bone.head = Vector(node.position) * scale_factor
            bone.tail = bone.head + Vector((0, 0.1, 0))

            if parent_idx >= 0 and parent_idx in bone_map:
                bone.parent = bone_map[parent_idx]

            bone_map[node_idx] = bone

    bpy.ops.object.mode_set(mode='OBJECT')

    return armature_obj


def setup_armature_modifier(
    obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    node: NDMNode,
):
    """
    Set up armature modifier and vertex groups for mesh.
    """
    if not node.bone_weights:
        return

    # Add armature modifier
    mod = obj.modifiers.new(name='Armature', type='ARMATURE')
    mod.object = armature_obj

    # Create vertex groups and assign weights
    for vert_idx, weights in enumerate(node.bone_weights):
        for bone_idx, weight in weights:
            bone_name = f"Bone_{bone_idx}"
            if bone_name not in obj.vertex_groups:
                obj.vertex_groups.new(name=bone_name)
            vg = obj.vertex_groups[bone_name]
            vg.add([vert_idx], weight, 'REPLACE')


def setup_shape_keys(
    obj: bpy.types.Object,
    node: NDMNode,
    scale_factor: float,
):
    """
    Set up shape keys (blend shapes) for mesh.
    """
    if not node.shape_keys:
        return

    # Create basis shape key
    obj.shape_key_add(name='Basis')

    for shape_name, shape_verts in node.shape_keys.items():
        sk = obj.shape_key_add(name=shape_name)
        
        for i, (x, y, z) in enumerate(shape_verts):
            if i < len(sk.data):
                sk.data[i].co = Vector((x, y, z)) * scale_factor
