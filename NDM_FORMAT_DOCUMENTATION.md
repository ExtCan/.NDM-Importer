# NDM File Format Documentation
Generated from analysis of ind-nddemo (Peach's Castle Demo) files

## File Summary

| File | Textures | Nodes | Meshes | Vertices | Faces | Notes |
|------|----------|-------|--------|----------|-------|-------|
| ARROW.NDM | 4 | 768 | 768 | 151,962 | 300,920 | Direction arrows (many small meshes) |
| BIPLANE.NDM | 29 | 57 | 49 | 4,142 | 4,800 | Mario's biplane |
| COIN.NDM | 8 | 10 | 8 | 496 | 960 | Collectible coins |
| KURIBO.NDM | 1 | 1 | 1 | 4,221 | 16,969 | Goomba enemy |
| STG_CAVE.NDM | 57 | 58 | 48 | 21,010 | 40,424 | Cave area |
| STG_CINE.NDM | 47 | 69 | 51 | 9,171 | 14,743 | Cinema room |
| STG_COIN.NDM | 1 | 1 | 1 | 60 | 116 | Coin stage element |
| STG_DOME.NDM | 21 | 23 | 19 | 9,466 | 17,400 | Dome room |
| STG_ENTR.NDM | 38 | 222 | 192 | 34,877 | 64,486 | Castle entrance (largest) |
| STG_ENVE.NDM | 21 | 31 | 26 | 3,249 | 12,581 | Envelope room |
| STG_HANG.NDM | 36 | 60 | 44 | 18,374 | 29,362 | Hanging area |
| STG_MPOL.NDM | 4 | 8 | 6 | 414 | 553 | Pole stage |
| STG_OPEN.NDM | 8 | 15 | 12 | 694 | 893 | Opening area |
| STG_SPIL.NDM | 74 | 111 | 76 | 17,737 | 45,220 | Spillway area |
| TITLE.NDM | 1 | 1 | 1 | 15 | 16 | Title screen grid |
| TOUEI.NDM | 78 | 79 | 78 | 702 | 624 | Logo/projection |

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
- May have header/setup bytes before draw commands (typically 0x20-0x40 bytes)
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
Two formats are used based on file structure:

**3-byte format** (most files): 
- Byte 0: Position index (uint8)
- Byte 1: Attribute/normal index (uint8)
- Byte 2: UV index (uint8)

**4-byte format** (some files like TITLE.NDM):
- Byte 0: Position index (uint8)
- Byte 1: 0x00 (padding)
- Byte 2: 0x00 (padding)
- Byte 3: UV index (uint8)

Detection: If bytes 1 and 2 are consistently 0x00 across vertex refs, the 4-byte format is used.

Note: All indices are 8-bit (0-255). Models with >256 vertices use multiple draw commands, each addressing a subset of vertices.

## Model Categories

### Character Models
- **KURIBO.NDM**: Goomba enemy
  - Single mesh with 4,221 vertices
  - Multiple draw commands to handle >256 vertex limit
  - 16,969 triangles

### Vehicle Models
- **BIPLANE.NDM**: Mario's biplane
  - 49 meshes for parts (body, wings, tires, etc.)
  - 4,142 total vertices, 4,800 faces

### Environment/Stage Models
- **STG_ENTR.NDM**: Castle entrance (largest stage file)
  - 192 meshes, 34,877 vertices, 64,486 faces
- **STG_SPIL.NDM**: Spillway area
  - 76 meshes, 17,737 vertices, 45,220 faces
- **STG_CAVE.NDM**: Cave area
  - 48 meshes, 21,010 vertices, 40,424 faces
- **STG_HANG.NDM**: Hanging area
  - 44 meshes, 18,374 vertices, 29,362 faces

### UI/Effects
- **ARROW.NDM**: Direction arrows (768 small meshes, 300K+ faces)
- **COIN.NDM**: Collectible coins (8 identical coins)
- **TITLE.NDM**: Title screen grid (4-byte vertex format)
- **TOUEI.NDM**: Logo/projection (78 meshes)

## Key Findings

1. **Index Format Detection**: All models use 8-bit vertex indices. The difference is in the number of bytes per vertex reference (3 or 4). Format is auto-detected by checking if bytes 1-2 are always zero.

2. **Position Data Size**: The field at offset 0x74 in the node header contains the actual position data size, which is more reliable than the general vertex data size at 0x50.

3. **Display List Header**: Many display lists have setup commands (GX Load BP/CP/XF) before draw commands. The parser skips the first ~0x20-0x40 bytes when searching for 0x80/0x90 draw commands.

4. **Quad to Triangle Conversion**: GX uses quads (0x80 command) extensively. These are converted to triangles for Blender import: quad [v0,v1,v2,v3] → triangles [v0,v1,v2] + [v0,v2,v3].

5. **Coordinate Scale**: All vertex positions are stored as signed int16 values and need to be divided by 256.0 for proper world-space coordinates.
