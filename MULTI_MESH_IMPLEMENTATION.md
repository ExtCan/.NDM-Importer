# Multi-Mesh NDM Import - Implementation Notes

## Overview

The NDM importer correctly handles files with multiple meshes. This document clarifies how multi-mesh detection and import works.

## How It Works

### 1. File Structure Detection

When an NDM file is loaded, the parser:
1. Reads all nodes from the file
2. Identifies which nodes have mesh data (`node.has_mesh = True`)
3. Identifies which nodes are transform/empty nodes

Example breakdown:
- **BIPLANE.NDM**: 57 total nodes → 49 mesh nodes, 8 empty nodes
- **STG_ENTR.NDM**: 222 total nodes → 196 mesh nodes, 26 empty nodes
- **ARROW.NDM**: 768 total nodes → 751 mesh nodes, 17 empty nodes

### 2. Per-Mesh Processing

For EACH mesh node, the importer:

```python
for node in parser.nodes:
    if node.has_mesh:
        # Step 1: Detect format for THIS specific mesh
        detected_format = parser._detect_vertex_ref_format(...)
        # Format can be 3-byte, 4-byte, or 6-byte
        
        # Step 2: Extract geometry for THIS mesh
        vertices = parser.get_mesh_vertices(node)
        faces, uv_faces = parser.get_mesh_faces_and_uvs(node, len(vertices))
        uvs = parser.get_mesh_uvs(node)
        
        # Step 3: Create separate Blender mesh object
        mesh = bpy.data.meshes.new(node.name)
        mesh.from_pydata(vertices, [], faces)
        obj = bpy.data.objects.new(node.name, mesh)
```

### 3. Individual Format Detection

**Important**: Format detection is done PER-MESH, not per-file!

Example from BIPLANE.NDM:
- `BODY` mesh: 100 vertices → **3-byte format** detected
- `pit_cover` mesh: 206 vertices → **4-byte format** detected
- `pit_coverB` mesh: 57 vertices → **3-byte format** detected
- `tessenL` mesh: 144 vertices → **3-byte format** detected

This is correct because each mesh has its own display list with its own vertex reference format.

## Console Output

The enhanced logging provides clear feedback:

```
============================================================
Importing NDM: BIPLANE.NDM
============================================================
Total nodes: 57
  - Mesh nodes: 49
  - Transform/Empty nodes: 8
Texture references: 29

⚠ MULTI-MESH FILE DETECTED
  This file contains 49 separate mesh objects.
  Each mesh will be imported as a separate Blender object.

  Processing mesh 'BODY': 100 verts, 156 faces, 74 UVs (3-byte format)
  Processing mesh 'pit_cover': 206 verts, 338 faces, 123 UVs (4-byte format)
  Processing mesh 'pit_coverB': 57 verts, 60 faces, 18 UVs (3-byte format)
  Processing mesh 'tire': 288 verts, 230 faces, 88 UVs (3-byte format)
  Processing mesh 'tessenL': 144 verts, 168 faces, 40 UVs (3-byte format)

============================================================
Import Complete!
  Created 49 mesh objects
  Created 8 empty/transform objects
  Total objects: 57
  Texture references: 1_bi_bod, 1_bi_ba, 1_bi_li
    ... and 26 more
============================================================
```

## Why This Matters

### Before Enhancement
- Silent processing - users couldn't see what was happening
- No indication that multi-mesh files were being handled
- No visibility into per-mesh format detection

### After Enhancement
- Clear multi-mesh detection warning
- Shows first 5 meshes being processed with their formats
- Comprehensive summary of what was imported
- Users can verify all meshes were imported

## Test Results

| File | Total Nodes | Mesh Nodes | Empty Nodes | Status |
|------|-------------|------------|-------------|---------|
| KURIBO.NDM | 1 | 1 | 0 | ✓ Single mesh |
| BIPLANE.NDM | 57 | 49 | 8 | ✓ Multi-mesh |
| STG_ENTR.NDM | 222 | 196 | 26 | ✓ Multi-mesh |
| ARROW.NDM | 768 | 751 | 17 | ✓ Huge multi-mesh |

**All files import correctly with individual format detection per mesh.**

## Common Misconceptions

### ❌ "Multi-mesh files aren't detected"
**Reality**: They are detected. Each mesh node is processed individually.

### ❌ "Format detection is global per file"
**Reality**: Format detection is per-mesh. Different meshes in the same file can use different formats (3-byte, 4-byte, or 6-byte).

### ❌ "All meshes should use the same format"
**Reality**: Format depends on each mesh's display list data, not the file as a whole.

## Implementation Details

### Format Detection Algorithm (Per-Mesh)

For each mesh:
1. Locate the mesh's display list
2. Find the first draw command (0x80, 0x90, 0x98, or 0xA0)
3. Sample first 8 vertex references
4. Try interpreting as 3-byte, 4-byte, and 6-byte
5. Check validity (indices < vertex_count)
6. Check variety (not all same value)
7. Check sequentiality (differences ≤ 10)
8. Select best format based on these heuristics

### Edge Cases Handled

1. **Meshes with no faces**: Created as point clouds
2. **Empty nodes**: Created as Blender empties with transform
3. **Duplicate names**: Auto-incremented with `_{count}` suffix
4. **Out-of-range UV indices**: Use default UV (0,0)

## Conclusion

The NDM importer fully supports multi-mesh files. Each mesh is:
- Detected individually
- Analyzed with its own format detection
- Imported as a separate Blender object

The enhanced logging makes this process visible and verifiable.
