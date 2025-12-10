# Alternative Import Methods for Multi-Mesh NDM Files

## Overview

The NDM importer now provides two methods for importing multi-mesh NDM files, allowing users to choose the approach that best fits their workflow.

## Import Modes

### Mode 1: Separate Objects (Default)

Each mesh node in the NDM file creates its own Blender object.

**Advantages:**
- Individual meshes can be edited separately
- Preserves original file structure
- Easy to work with individual parts
- Each object has its own transforms (position, scale)

**Best for:**
- Files where you need to edit individual parts
- Models with meaningful mesh separation (e.g., BIPLANE with body, wings, wheels)
- Animation where parts move independently

**Example:**
```
BIPLANE.NDM:
  49 separate objects created:
    - BODY (100 verts, 156 faces)
    - pit_cover (206 verts, 338 faces)
    - tire (288 verts, 230 faces)
    ... and 46 more
```

### Mode 2: Merged Meshes (Optional)

All mesh nodes are combined into a single Blender object.

**Advantages:**
- Simplified scene hierarchy (1 object instead of 100+)
- Better performance for files with many small meshes
- Easier to manage in outliner
- Single object for export/manipulation

**Best for:**
- Files with many small meshes (e.g., ARROW with 751 meshes)
- Static models that don't need part separation
- Reducing scene complexity
- Game engine export where single mesh is preferred

**Example:**
```
ARROW.NDM (merged):
  1 single object created:
    - Total: 151,962 verts, 300,920 faces, 211,385 UVs
    - All 751 original meshes combined
```

## How to Use

### In Blender UI

1. File > Import > NDM (.ndm)
2. Select your NDM file
3. In the import options (right panel):
   - **Uncheck "Merge Meshes"**: Separate objects mode
   - **Check "Merge Meshes"**: Merged mode
4. Adjust scale if needed (default: 0.01)
5. Click Import

### Example Results

**BIPLANE.NDM:**
- Separate: 49 objects (good for editing)
- Merged: 1 object with 4,142 vertices

**STG_ENTR.NDM:**
- Separate: 196 objects
- Merged: 1 object with 34,877 vertices

**ARROW.NDM:**
- Separate: 751 objects (many small parts)
- Merged: 1 object with 151,962 vertices (much simpler!)

## Technical Details

### Transform Application

**Separate Mode:**
Each object gets transforms from its node data:
```python
obj.location = (node.position[0] * scale_factor,
              node.position[1] * scale_factor,
              node.position[2] * scale_factor)
obj.scale = node.scale
```

**Merged Mode:**
Vertices are pre-transformed during merge, creating a single object at the origin.

### UV and Vertex Color Handling

Both modes preserve UVs and vertex colors:

**Separate Mode:**
- Each object has its own UV map
- Vertex colors applied per-object from node color data

**Merged Mode:**
- Single UV map with all UVs combined
- UV indices are offset correctly when merging
- Vertex colors are merged (dominant color wins)

### Index Offsetting in Merged Mode

When combining meshes, indices must be offset:

```python
vertex_offset = 0
uv_offset = 0

for each mesh:
    # Add vertices
    all_vertices.extend(vertices)
    
    # Offset face indices
    offset_face = tuple(idx + vertex_offset for idx in face)
    all_faces.append(offset_face)
    
    # Offset UV indices
    offset_uv_face = tuple(idx + uv_offset for idx in uv_face)
    all_uv_faces.append(offset_uv_face)
    
    # Update offsets
    vertex_offset += len(vertices)
    uv_offset += len(uvs)
```

## Performance Comparison

| File | Mode | Objects | Vertices | Faces | Scene Complexity |
|------|------|---------|----------|-------|------------------|
| BIPLANE | Separate | 49 | 4,142 | 9,187 | Medium |
| BIPLANE | Merged | 1 | 4,142 | 9,187 | Low |
| ARROW | Separate | 751 | 151,962 | 300,920 | Very High |
| ARROW | Merged | 1 | 151,962 | 300,920 | Low |

**Key Insight:** Merged mode doesn't reduce vertex/face count, but dramatically simplifies scene hierarchy.

## When to Use Which Mode

### Use Separate Objects When:
- You need to edit/animate individual parts
- The model has meaningful part separation
- File has < 50 meshes
- You're rigging the model for animation

### Use Merged Mode When:
- File has 100+ separate meshes
- You need a static model
- Exporting to game engine
- Scene hierarchy is getting cluttered
- Performance is a concern (many objects = slower viewport)

## Troubleshooting

### "Too many objects in my scene!"
→ Use merged mode

### "I need to edit individual parts"
→ Use separate objects mode

### "UVs look wrong"
→ Check if UV indices are out of range (logged in console)

### "Model appears at wrong location"
→ Separate mode applies transforms; merged mode doesn't

## Future Enhancements

Potential improvements:
- Option to merge by material/texture
- Selective merge (merge only similar meshes)
- Preserve hierarchy in merged mode with vertex groups
- Auto-detect best mode based on mesh count

## Conclusion

Both import modes are fully functional and handle UVs, vertex colors, and geometry correctly. Choose based on your workflow needs:
- **Many small parts to edit?** → Separate objects
- **Simple static model?** → Merged mode
