# NDM File Format Documentation
Generated from analysis of ind-nddemo (Peach's Castle Demo) files

## File Summary

| File | Textures | Nodes | Meshes | Vertices | Faces | Notes |
|------|----------|-------|--------|----------|-------|-------|
| ARROW.NDM | 4 | 751 | 751 | 151,962 | 300,920 | Direction arrows (many small meshes) |
| BIPLANE.NDM | 29 | 57 | 49 | 4,142 | 3,567 | Mario's biplane |
| COIN.NDM | 8 | 10 | 8 | 496 | 960 | Collectible coins |
| KURIBO.NDM | 1 | 1 | 1 | 4,221 | 8,254 | Goomba enemy (uses 16-bit indices) |
| STG_CAVE.NDM | 57 | 57 | 48 | 21,010 | 4,943 | Cave area |
| STG_CINE.NDM | 47 | 53 | 51 | 9,171 | 3,055 | Cinema room |
| STG_COIN.NDM | 5 | 1 | 1 | 60 | 116 | Coin stage element |
| STG_DOME.NDM | 21 | 22 | 19 | 9,466 | 5,628 | Dome room |
| STG_ENTR.NDM | 64 | 201 | 196 | 34,877 | 15,207 | Castle entrance (large) |
| STG_ENVE.NDM | 21 | 28 | 26 | 3,249 | 1,232 | Envelope/letter? |
| STG_HANG.NDM | 36 | 46 | 44 | 18,374 | 6,649 | Hanging area |
| STG_MPOL.NDM | 4 | 8 | 6 | 414 | 135 | Pole stage |
| STG_OPEN.NDM | 8 | 13 | 12 | 694 | 807 | Opening area |
| STG_SPIL.NDM | 74 | 78 | 76 | 17,737 | 26,543 | Spillway area |
| TITLE.NDM | 1 | 1 | 1 | 15 | 0 | Title screen |
| TOUEI.NDM | 78 | 79 | 78 | 702 | 0 | Logo/projection |

## Format Details

### Header (0x00-0x20, 32 bytes)
- `0x00-0x03`: Texture count (uint32 BE)
- `0x04-0x07`: Offset to node definitions (uint32 BE)
- `0x08-0x09`: Node count (uint16 BE)
- `0x0A-0x1F`: Flags and padding

### Texture Table (0x20 onwards)
- 16 bytes per entry
- Null-terminated texture name (references .DTX files)

### Node Hierarchy
- 3 bytes per node after texture table
- Format: (parent_high, parent_low, flags)
- 0xFF = no parent (root node)

### Node Definition (128 bytes each)
| Offset | Size | Description |
|--------|------|-------------|
| 0x00 | 16 | Node name (null-terminated) |
| 0x10 | 12 | Position (3x float32 BE) |
| 0x1C | 4 | Unknown |
| 0x20 | 8 | Rotation? (often zeros) |
| 0x28 | 12 | Scale (3x float32 BE) |
| 0x34 | 4 | Flags |
| 0x38 | 4 | Color1 (RGBA) |
| 0x3C | 4 | Color2 (RGBA) |
| 0x40 | 8 | Texture indices (4x uint16, 0xFFFF=none) |
| 0x48 | 8 | More texture/material info |
| 0x50 | 4 | Vertex data size (total: positions + UVs + normals) |
| 0x54 | 4 | Additional header size |
| 0x58 | 4 | Display list size |
| 0x5C | 4 | Vertex counts |
| 0x60 | 32 | Additional mesh offsets |
| 0x74 | 4 | Position data size (just vertex positions) |

### Vertex Data
- Immediately follows 128-byte node header
- Format: signed int16 triplets (x, y, z) - Big Endian
- Scale: divide by 256.0 for world units
- 6 bytes per vertex

### Display List
- Follows vertex data
- Contains GX draw commands and vertex references

#### Draw Commands
| Command | Type |
|---------|------|
| 0x80 | Quads |
| 0x90 | Triangles |
| 0x98 | Triangle Strip |
| 0xA0 | Triangle Fan |

Command format: `[cmd:u8] [count:u16BE] [vertex_refs...]`

#### Vertex Reference Format
The format depends on vertex count:

**Small models (≤255 vertices)**: 3 bytes per ref
- Byte 0: Position index (uint8)
- Byte 1: Attribute (uint8, often matches position or is 0)
- Byte 2: UV index (uint8)

**Large models (>255 vertices)**: 6 bytes per ref
- Bytes 0-1: Position index (uint16 BE)
- Bytes 2-3: Normal index (uint16 BE)  
- Bytes 4-5: UV index (uint16 BE)

Note: In many cases, all three indices are the same value.

## Model Categories

### Character Models
- **KURIBO.NDM**: Goomba enemy
  - Single mesh with 4,221 vertices
  - Uses 16-bit indices due to vertex count
  - 8,254 triangles

### Vehicle Models
- **BIPLANE.NDM**: Mario's biplane
  - 49 meshes for parts (body, wings, tires, etc.)
  - 4,142 total vertices

### Environment/Stage Models
- **STG_ENTR.NDM**: Castle entrance (largest stage file)
  - 196 meshes, 34,877 vertices
- **STG_CAVE.NDM**: Cave area
  - 48 meshes, 21,010 vertices
- **STG_HANG.NDM**: Hanging area
  - 44 meshes, 18,374 vertices
- **STG_SPIL.NDM**: Spillway area
  - 76 meshes, 17,737 vertices

### UI/Effects
- **ARROW.NDM**: Direction arrows (many small meshes)
- **COIN.NDM**: Collectible coins (8 identical coins)
- **TITLE.NDM**: Title screen element
- **TOUEI.NDM**: Logo/projection

## Key Findings

1. **Index Format Detection**: Models with >255 vertices use 6-byte vertex references (16-bit indices), while smaller models use 3-byte references (8-bit indices).

2. **Position Data Size**: The field at offset 0x74 in the node header contains the actual position data size, which is more reliable than the general vertex data size at 0x50.

3. **Display List Structure**: Some display lists (especially for larger models) have setup/header data before the actual draw commands. The parser scans for valid 0x80/0x90/0x98/0xA0 commands.

4. **Quad to Triangle Conversion**: GX uses quads (0x80 command) extensively. These are converted to triangles for Blender import: quad [v0,v1,v2,v3] → triangles [v0,v1,v2] + [v0,v2,v3].

5. **Coordinate Scale**: All vertex positions are stored as signed int16 values and need to be divided by 256.0 for proper world-space coordinates.
