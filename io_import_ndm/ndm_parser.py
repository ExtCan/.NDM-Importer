"""
NDM File Parser for Blender

Parses .NDM model files from Nintendo GameCube's ind-nddemo (Peach's Castle Demo)
and creates Blender meshes from the data.

NDM File Format:
================

Header (0x00-0x20, 32 bytes):
- 0x00-0x03: Number of texture references (uint32 BE)
- 0x04-0x07: End offset of texture section / node definitions start (uint32 BE)  
- 0x08-0x09: Number of nodes (uint16 BE)
- 0x0A-0x1F: Reserved/flags (22 bytes, typically zeros)

Texture References (starting at 0x20, 16 bytes each):
- Null-terminated texture name strings

Node Hierarchy (after textures, variable location):
- 3 bytes per node: parent_high, parent_low, flags

Node Definitions (128 bytes each):
- 0x00-0x0F: Node name (16 bytes, null-terminated)
- 0x10-0x1B: Position (3x float32 BE)
- 0x1C-0x1F: Unknown/padding
- 0x20-0x27: Rotation? (8 bytes, often zeros)
- 0x28-0x33: Scale (3x float32 BE, typically 1.0 = 0x3f800000)
- 0x34-0x37: Flags
- 0x38-0x3B: Color1 (RGBA)
- 0x3C-0x3F: Color2 (RGBA)
- 0x40-0x4F: Texture indices (4x uint16, 0xFFFF = no texture)
- 0x50-0x53: Vertex data size (total bytes for positions + UVs + normals)
- 0x54-0x57: Additional header size (padding before display list)
- 0x58-0x5B: Display list size  
- 0x5C-0x5F: Vertex counts
- 0x60-0x7F: Additional mesh info

Display List Format:
- Small models (<=255 vertices): 3 bytes per vertex ref (pos_idx:u8, attr:u8, uv_idx:u8)
- Large models (>255 vertices): 6 bytes per vertex ref (pos_idx:u16, norm_idx:u16, uv_idx:u16)

GX Draw Commands:
- 0x80: Quads
- 0x90: Triangles
- 0x98: Triangle Strip
- 0xA0: Triangle Fan
"""

import struct
import os
import math

# Minimum ratio of valid indices required when parsing vertex references.
# 80% allows for some padding or invalid data at the end of display lists.
MIN_VALID_INDEX_RATIO = 0.8

# Maximum vertex count per draw command (sanity check)
MAX_DRAW_COMMAND_VERTICES = 20000

# Display list header constants
DL_HEADER_BASE_OFFSET = 0x20  # Base offset that indicates no GX setup commands
MAX_DL_HEADER_SIZE = 0x1000  # Maximum valid display list header size

# Format detection constants  
MAX_HEADER_SCAN_BYTES = 200  # Maximum bytes to scan for first draw command
MIN_DRAW_COUNT = 4  # Minimum vertex count for valid draw command
MAX_DRAW_COUNT = 2000  # Maximum vertex count for format detection sampling
SAMPLE_REFS_COUNT = 6  # Number of vertex references to sample for format detection
MIN_BOTH_ZERO_4BYTE = 5  # Minimum refs with bytes 1,2 both zero to detect 4-byte format

# Blender imports - only available when running in Blender
try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


class NDMNode:
    """Represents a node in the NDM file"""
    def __init__(self):
        self.name = ""
        self.offset = 0
        self.parent_index = -1
        self.node_type = 0
        self.position = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.flags = 0
        self.color1 = (1.0, 1.0, 1.0, 1.0)
        self.color2 = (1.0, 1.0, 1.0, 1.0)
        self.texture_indices = []
        self.has_mesh = False
        self.mesh_data_offset = 0
        self.vertex_data_size = 0  # Total mesh data size (positions + UVs + etc)
        self.position_data_size = 0  # Size of just the vertex positions
        self.display_list_size = 0
        self.dl_header_size = 0  # Bytes of GX setup commands before draw commands
        self.vertex_count = 0


class NDMParser:
    """Parser for NDM files"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = None
        self.num_textures = 0
        self.texture_section_end = 0
        self.num_nodes = 0
        self.textures = []
        self.nodes = []
        
    def read(self):
        """Read and parse the NDM file"""
        with open(self.filepath, 'rb') as f:
            self.data = f.read()
        
        self._parse_header()
        self._parse_textures()
        self._find_and_parse_nodes()
        
    def _parse_header(self):
        """Parse the NDM file header"""
        self.num_textures = struct.unpack_from('>I', self.data, 0x00)[0]
        self.texture_section_end = struct.unpack_from('>I', self.data, 0x04)[0]
        word2 = struct.unpack_from('>I', self.data, 0x08)[0]
        
        # Number of nodes is in the upper byte of word2
        self.num_nodes = (word2 >> 16) & 0xFF
        if self.num_nodes == 0:
            self.num_nodes = (word2 >> 16) & 0xFFFF
            
    def _parse_textures(self):
        """Parse texture references"""
        self.textures = []
        for i in range(self.num_textures):
            offset = 0x20 + i * 16
            if offset + 16 > len(self.data):
                break
            name = self.data[offset:offset+16].rstrip(b'\x00').decode('ascii', errors='ignore')
            self.textures.append(name)
    
    def _is_valid_node_at(self, offset):
        """Check if there's a valid node at the given offset"""
        if offset + 128 > len(self.data):
            return False
            
        # Check for valid ASCII name in first 16 bytes
        name_bytes = self.data[offset:offset + 16].rstrip(b'\x00')
        if len(name_bytes) == 0:
            return False
        if not all(32 <= b < 127 for b in name_bytes):
            return False
            
        # Check for valid scale values at offset + 0x20
        # Scale of 1.0 = 0x3f800000, or small values like 3.0 = 0x40400000
        scale_val = struct.unpack_from('>I', self.data, offset + 0x20)[0]
        
        # Check for characteristic patterns:
        # - Scale 1.0 at offset 0x28 (third scale component)
        scale_z = struct.unpack_from('>f', self.data, offset + 0x28)[0]
        if not (0.001 < abs(scale_z) < 10000 or math.isnan(scale_z)):
            return False
            
        # Check for flags pattern at 0x2C (often 0x5498xxxx or 0x1400xxxx or 0xd480xxxx)
        flags = struct.unpack_from('>I', self.data, offset + 0x2C)[0]
        flags_upper = (flags >> 24) & 0xFF
        if flags_upper not in [0x00, 0x14, 0x54, 0xD4, 0x3F, 0x40]:
            # Also allow 0x3f800000 (1.0 float) as it might be part of scale
            pass
            
        return True
    
    def _find_and_parse_nodes(self):
        """Find all nodes by searching for valid node patterns"""
        self.nodes = []
        
        # Start searching after texture section
        search_start = 0x20 + self.num_textures * 16
        
        # Search for nodes by looking for valid node patterns
        # Nodes are 128-byte aligned and have recognizable structure
        offset = search_start
        
        while offset < len(self.data) - 128:
            # Skip non-node data (look for ASCII name start)
            if not self._is_valid_node_at(offset):
                offset += 16  # Try next 16-byte aligned position
                continue
                
            # Found a valid node
            node = self._parse_node_at(offset)
            if node:
                self.nodes.append(node)
                
                # Calculate next node position
                # If this node has mesh data, skip past it
                if node.has_mesh:
                    mesh_size = node.vertex_data_size + node.display_list_size
                    next_offset = offset + 128 + mesh_size
                    # Align to 16 bytes
                    next_offset = (next_offset + 0xF) & ~0xF
                    offset = next_offset
                else:
                    offset += 128
            else:
                offset += 16
                
    def _parse_node_at(self, offset):
        """Parse a node at the given offset"""
        if offset + 128 > len(self.data):
            return None
            
        node = NDMNode()
        node.offset = offset
        
        # Parse name (first 16 bytes)
        name_bytes = self.data[offset:offset + 16].rstrip(b'\x00')
        if len(name_bytes) == 0:
            return None
        if not all(32 <= b < 127 for b in name_bytes):
            return None
        node.name = name_bytes.decode('ascii', errors='ignore')
        
        # Parse position at offset 0x10
        # Could be floats or zeros
        fpx, fpy, fpz = struct.unpack_from('>3f', self.data, offset + 0x10)
        if all(abs(f) < 100000 for f in [fpx, fpy, fpz] if not math.isnan(f)):
            node.position = (fpx, fpy, fpz)
        else:
            node.position = (0.0, 0.0, 0.0)
        
        # Parse scale at offset 0x20
        sx, sy, sz = struct.unpack_from('>3f', self.data, offset + 0x20)
        if all(0.0001 < abs(s) < 10000 for s in [sx, sy, sz] if not math.isnan(s)):
            node.scale = (sx, sy, sz)
        else:
            node.scale = (1.0, 1.0, 1.0)
        
        # Parse flags at 0x2C
        node.flags = struct.unpack_from('>I', self.data, offset + 0x2C)[0]
        
        # Parse colors at 0x30 and 0x34
        c1 = struct.unpack_from('>4B', self.data, offset + 0x30)
        c2 = struct.unpack_from('>4B', self.data, offset + 0x34)
        node.color1 = tuple(c / 255.0 for c in c1)
        node.color2 = tuple(c / 255.0 for c in c2)
        
        # Parse texture indices at 0x40
        tex_data = struct.unpack_from('>4H', self.data, offset + 0x40)
        node.texture_indices = [t for t in tex_data if t != 0xFFFF and t < len(self.textures)]
        
        # Parse mesh info at 0x50
        # 0x50: total vertex attribute data size (positions + UVs + etc)
        # 0x54: display list header size (GX setup commands before draw commands)
        # 0x58: display list size
        node.vertex_data_size = struct.unpack_from('>I', self.data, offset + 0x50)[0]
        dl_header_field = struct.unpack_from('>I', self.data, offset + 0x54)[0]
        node.display_list_size = struct.unpack_from('>I', self.data, offset + 0x58)[0]
        
        # The dl_header_field indicates where to start looking for draw commands
        # Draw commands start at (dl_header_field - DL_HEADER_BASE_OFFSET) bytes into the display list
        # When dl_header_field equals DL_HEADER_BASE_OFFSET, draw commands start immediately
        if dl_header_field >= DL_HEADER_BASE_OFFSET and dl_header_field < MAX_DL_HEADER_SIZE:
            node.dl_header_size = dl_header_field - DL_HEADER_BASE_OFFSET
        else:
            node.dl_header_size = 0
        
        # The actual position data size is at offset 0x74
        # This is the byte size of just vertex positions (num_vertices * 6)
        node.position_data_size = struct.unpack_from('>I', self.data, offset + 0x74)[0]
        
        # Calculate actual vertex count from position data size
        if node.position_data_size > 0 and node.position_data_size % 6 == 0:
            node.vertex_count = node.position_data_size // 6
        else:
            # Fallback: use total vertex data size 
            node.vertex_count = node.vertex_data_size // 6
        
        # Check if this node has mesh data
        # Valid mesh nodes have reasonable vertex data sizes and counts
        if (node.vertex_data_size > 0 and 
            node.vertex_data_size < 0x100000 and  # Less than 1MB
            node.display_list_size > 0 and
            node.display_list_size < 0x100000):
            node.has_mesh = True
            node.mesh_data_offset = offset + 128  # Mesh data follows node header
        else:
            node.has_mesh = False
            
        return node
                
    def get_mesh_vertices(self, node):
        """Extract vertex positions from a node's mesh data"""
        if not node.has_mesh or node.mesh_data_offset == 0:
            return []
            
        vertices = []
        offset = node.mesh_data_offset
        
        # Use position_data_size if available, otherwise fall back to vertex_data_size
        if node.position_data_size > 0:
            num_verts = node.position_data_size // 6
        else:
            num_verts = node.vertex_count if node.vertex_count > 0 else node.vertex_data_size // 6
            
        if num_verts == 0 or num_verts > 100000:
            return []
            
        for i in range(num_verts):
            vert_offset = offset + i * 6
            if vert_offset + 6 > len(self.data):
                break
            x, y, z = struct.unpack_from('>3h', self.data, vert_offset)
            # Values are in 1/256 units
            vertices.append((x / 256.0, y / 256.0, z / 256.0))
            
        return vertices
    
    def get_mesh_uvs(self, node):
        """Extract UV coordinates from a node's mesh data.
        
        UV data follows position data in the vertex_data section.
        Format: signed int16 pairs (u, v), scaled by 1/256.0
        """
        if not node.has_mesh or node.mesh_data_offset == 0:
            return []
        
        # Calculate offset to UV data (after positions)
        uv_offset = node.mesh_data_offset + node.position_data_size
        
        # Calculate remaining vertex data size
        remaining_data = node.vertex_data_size - node.position_data_size
        
        # UV data is likely 4 bytes per UV (2x int16)
        if remaining_data <= 0 or remaining_data % 4 != 0:
            return []
        
        num_uvs = remaining_data // 4
        
        if num_uvs == 0 or num_uvs > 100000:
            return []
        
        uvs = []
        for i in range(num_uvs):
            uv_data_offset = uv_offset + i * 4
            if uv_data_offset + 4 > len(self.data):
                break
            u, v = struct.unpack_from('>2h', self.data, uv_data_offset)
            # Values are likely in 1/256 units, normalized to 0-1 range
            uvs.append((u / 256.0, v / 256.0))
        
        return uvs
        
    def _detect_vertex_ref_format(self, dl_offset, dl_end, num_vertices):
        """Detect vertex reference format (3-byte or 4-byte) from display list data.
        
        Returns bytes_per_vertex (3, 4, or 6 for 16-bit indices).
        
        Format detection strategies:
        - 6-byte: Used when >255 vertices (16-bit indices required)
        - 4-byte: pos:u8, norm:u8, color:u8, uv:u8 
          - Both bytes 1 AND 2 are often 0 for all refs
          - Or positions at 4-byte intervals are sequential (0,1,2,3...)
        - 3-byte: pos:u8, attr:u8, uv:u8
          - Byte 1 is often 0 (attr=0 or same as pos)
          - Positions at 3-byte intervals are valid and varied
        """
        if num_vertices > 255:
            return 6  # Must use 16-bit indices
        
        # Find first draw command
        offset = dl_offset
        while offset < min(dl_end, dl_offset + MAX_HEADER_SCAN_BYTES) and offset < len(self.data) - 3:
            cmd = self.data[offset]
            if cmd == 0x80 and offset + 30 < len(self.data):
                count = struct.unpack_from('>H', self.data, offset + 1)[0]
                if MIN_DRAW_COUNT <= count <= MAX_DRAW_COUNT:
                    # Read first 24 bytes of vertex refs
                    refs = self.data[offset + 3:offset + 3 + 24]
                    
                    # Strategy 1: Check if bytes 1,2 in 4-byte groups are both 0
                    both_zero_4byte = sum(1 for j in range(SAMPLE_REFS_COUNT) if j*4+2 < len(refs) and 
                                         refs[j*4+1] == 0 and refs[j*4+2] == 0)
                    
                    if both_zero_4byte >= MIN_BOTH_ZERO_4BYTE:
                        return 4  # Clearly 4-byte format
                    
                    # Strategy 2: Check if 4-byte positions form a sequential quad
                    pos_4byte = [refs[j * 4] for j in range(min(4, len(refs) // 4))]
                    is_sequential_quad_4byte = (
                        len(pos_4byte) >= 4 and
                        all(p < num_vertices for p in pos_4byte) and
                        (pos_4byte == [0, 1, 2, 3] or 
                         pos_4byte == [pos_4byte[0], pos_4byte[0]+1, pos_4byte[0]+2, pos_4byte[0]+3])
                    )
                    
                    pos_3byte = [refs[j * 3] for j in range(min(4, len(refs) // 3))]
                    is_sequential_quad_3byte = (
                        len(pos_3byte) >= 4 and
                        all(p < num_vertices for p in pos_3byte) and
                        (pos_3byte == [0, 1, 2, 3] or 
                         pos_3byte == [pos_3byte[0], pos_3byte[0]+1, pos_3byte[0]+2, pos_3byte[0]+3])
                    )
                    
                    # If 4-byte gives sequential and 3-byte doesn't, use 4-byte
                    if is_sequential_quad_4byte and not is_sequential_quad_3byte:
                        return 4
                    
                    # If 3-byte gives sequential and 4-byte doesn't, use 3-byte
                    if is_sequential_quad_3byte and not is_sequential_quad_4byte:
                        return 3
                    
                    # If both or neither are sequential, check byte patterns
                    # In 3-byte format, byte 1 is often 0
                    zeros_3byte = sum(1 for j in range(8) if j*3+1 < len(refs) and refs[j*3+1] == 0)
                    
                    if zeros_3byte >= 6:
                        return 3  # High zero count in 3-byte format
                    
                    # Default to 3-byte
                    return 3
            offset += 1
        
        return 3  # Default
    
    def get_mesh_faces(self, node, num_vertices):
        """Extract face indices from a node's display list
        
        GameCube GX display lists contain setup commands followed by draw commands.
        Draw commands (0x80-0xBF) reference vertex indices.
        
        Vertex reference formats:
        - 3 bytes: pos:u8, attr:u8, uv:u8 (most common for small meshes)
        - 4 bytes: pos:u8, norm:u8, color:u8, uv:u8 (some files like TITLE, STG_*)
        - 6 bytes: pos:u16, norm:u16, uv:u16 (when >255 vertices)
        """
        if not node.has_mesh or node.display_list_size == 0:
            return []
            
        # Display list immediately follows vertex data in the mesh data block.
        # Skip past GX setup commands using dl_header_size.
        dl_offset = node.mesh_data_offset + node.vertex_data_size + node.dl_header_size
        dl_end = node.mesh_data_offset + node.vertex_data_size + node.display_list_size
        
        if dl_offset >= len(self.data):
            return []
        
        # Detect vertex reference format (use full dl range for detection)
        full_dl_offset = node.mesh_data_offset + node.vertex_data_size
        bytes_per_vertex = self._detect_vertex_ref_format(full_dl_offset, dl_end, num_vertices)
        use_16bit = bytes_per_vertex == 6
            
        faces = []
        offset = dl_offset
        
        while offset < dl_end and offset < len(self.data) - 3:
            cmd = self.data[offset]
            
            # Only process draw commands: 0x80 (quads), 0x90 (triangles), 0x98 (strip), 0xA0 (fan)
            if cmd in [0x80, 0x90, 0x98, 0xA0]:
                if offset + 3 > len(self.data):
                    break
                    
                count = struct.unpack_from('>H', self.data, offset + 1)[0]
                
                # Sanity check count - must be reasonable for a draw command
                if count == 0 or count > MAX_DRAW_COMMAND_VERTICES:
                    offset += 1
                    continue
                
                # Validate first few vertex indices
                vert_start = offset + 3
                valid_count = 0
                check_count = min(4, count)
                
                for i in range(check_count):
                    idx_offset = vert_start + i * bytes_per_vertex
                    if idx_offset + bytes_per_vertex > len(self.data):
                        break
                    
                    if use_16bit:
                        idx = struct.unpack_from('>H', self.data, idx_offset)[0]
                    else:
                        idx = self.data[idx_offset]
                    
                    if idx < num_vertices:
                        valid_count += 1
                
                # Need at least 75% of checked indices to be valid
                if valid_count < check_count * 0.75:
                    offset += 1
                    continue
                
                # This is a valid draw command - process it
                offset += 3  # Skip command header
                
                # Parse all vertex indices
                indices = []
                for i in range(count):
                    idx_offset = offset + i * bytes_per_vertex
                    if idx_offset + bytes_per_vertex > len(self.data):
                        break
                    
                    if use_16bit:
                        idx = struct.unpack_from('>H', self.data, idx_offset)[0]
                    else:
                        idx = self.data[idx_offset]
                    
                    if idx < num_vertices:
                        indices.append(idx)
                    else:
                        # Stop on invalid index
                        break
                
                # Advance offset past vertex data
                offset += count * bytes_per_vertex
                
                if len(indices) >= 3:
                    # Determine primitive type from command
                    prim_type = cmd & 0xF8  # Upper 5 bits
                    
                    if prim_type == 0x80:  # Quads
                        # Convert quads to triangles
                        for i in range(0, len(indices) - 3, 4):
                            i0, i1, i2, i3 = indices[i], indices[i+1], indices[i+2], indices[i+3]
                            if i0 != i1 and i1 != i2 and i2 != i3:
                                faces.append((i0, i1, i2))
                                faces.append((i0, i2, i3))
                                
                    elif prim_type == 0x90:  # Triangles
                        for i in range(0, len(indices) - 2, 3):
                            i0, i1, i2 = indices[i], indices[i+1], indices[i+2]
                            if i0 != i1 and i1 != i2 and i0 != i2:
                                faces.append((i0, i1, i2))
                                
                    elif prim_type == 0x98:  # Triangle strip
                        for i in range(len(indices) - 2):
                            i0, i1, i2 = indices[i], indices[i+1], indices[i+2]
                            if i0 != i1 and i1 != i2 and i0 != i2:
                                if i % 2 == 0:
                                    faces.append((i0, i1, i2))
                                else:
                                    faces.append((i1, i0, i2))
                                    
                    elif prim_type == 0xA0:  # Triangle fan
                        if len(indices) >= 3:
                            for i in range(1, len(indices) - 1):
                                i0, i1, i2 = indices[0], indices[i], indices[i+1]
                                if i0 != i1 and i1 != i2 and i0 != i2:
                                    faces.append((i0, i1, i2))
            else:
                # Not a draw command we recognize - skip one byte
                offset += 1
        
        return faces
    
    def get_mesh_faces_and_uvs(self, node, num_vertices):
        """Extract face indices and UV indices from a node's display list.
        
        Returns: (faces, uv_faces) where:
        - faces: list of (v0, v1, v2) vertex index tuples
        - uv_faces: list of (uv0, uv1, uv2) UV index tuples corresponding to faces
        
        Vertex reference formats:
        - 3 bytes: pos:u8, attr:u8, uv:u8
        - 4 bytes: pos:u8, norm:u8, color:u8, uv:u8  
        - 6 bytes: pos:u16, norm:u16, uv:u16
        """
        if not node.has_mesh or node.display_list_size == 0:
            return [], []
            
        # Display list immediately follows vertex data in the mesh data block.
        # Skip past GX setup commands using dl_header_size.
        dl_offset = node.mesh_data_offset + node.vertex_data_size + node.dl_header_size
        dl_end = node.mesh_data_offset + node.vertex_data_size + node.display_list_size
        
        if dl_offset >= len(self.data):
            return [], []
        
        # Detect vertex reference format
        full_dl_offset = node.mesh_data_offset + node.vertex_data_size
        bytes_per_vertex = self._detect_vertex_ref_format(full_dl_offset, dl_end, num_vertices)
        use_16bit = bytes_per_vertex == 6
        uv_byte_offset = bytes_per_vertex - 1 if bytes_per_vertex == 3 else (bytes_per_vertex - 1)
        # For 3-byte: UV at byte 2 (index 2)
        # For 4-byte: UV at byte 3 (index 3)
        # For 6-byte: UV at bytes 4-5 (indices 4-5)
            
        faces = []
        uv_faces = []
        offset = dl_offset
        
        while offset < dl_end and offset < len(self.data) - 3:
            cmd = self.data[offset]
            
            # Only process draw commands: 0x80 (quads), 0x90 (triangles), 0x98 (strip), 0xA0 (fan)
            if cmd in [0x80, 0x90, 0x98, 0xA0]:
                if offset + 3 > len(self.data):
                    break
                    
                count = struct.unpack_from('>H', self.data, offset + 1)[0]
                
                # Sanity check count
                if count == 0 or count > MAX_DRAW_COMMAND_VERTICES:
                    offset += 1
                    continue
                
                # Validate first few vertex indices
                vert_start = offset + 3
                valid_count = 0
                check_count = min(4, count)
                
                for i in range(check_count):
                    idx_offset = vert_start + i * bytes_per_vertex
                    if idx_offset + bytes_per_vertex > len(self.data):
                        break
                    
                    if use_16bit:
                        idx = struct.unpack_from('>H', self.data, idx_offset)[0]
                    else:
                        idx = self.data[idx_offset]
                    
                    if idx < num_vertices:
                        valid_count += 1
                
                # Need at least 75% of checked indices to be valid
                if valid_count < check_count * 0.75:
                    offset += 1
                    continue
                
                # This is a valid draw command - process it
                offset += 3  # Skip command header
                
                # Parse all vertex and UV indices
                indices = []
                uv_indices = []
                for i in range(count):
                    idx_offset = offset + i * bytes_per_vertex
                    if idx_offset + bytes_per_vertex > len(self.data):
                        break
                    
                    # Extract position index
                    if use_16bit:
                        pos_idx = struct.unpack_from('>H', self.data, idx_offset)[0]
                        uv_idx = struct.unpack_from('>H', self.data, idx_offset + 4)[0]
                    else:
                        pos_idx = self.data[idx_offset]
                        uv_idx = self.data[idx_offset + uv_byte_offset]
                    
                    if pos_idx < num_vertices:
                        indices.append(pos_idx)
                        uv_indices.append(uv_idx)
                    else:
                        # Stop on invalid index
                        break
                
                # Advance offset past vertex data
                offset += count * bytes_per_vertex
                
                if len(indices) >= 3:
                    # Determine primitive type from command
                    prim_type = cmd & 0xF8  # Upper 5 bits
                    
                    if prim_type == 0x80:  # Quads
                        # Convert quads to triangles
                        for i in range(0, len(indices) - 3, 4):
                            i0, i1, i2, i3 = indices[i], indices[i+1], indices[i+2], indices[i+3]
                            uv0, uv1, uv2, uv3 = uv_indices[i], uv_indices[i+1], uv_indices[i+2], uv_indices[i+3]
                            if i0 != i1 and i1 != i2 and i2 != i3:
                                faces.append((i0, i1, i2))
                                faces.append((i0, i2, i3))
                                uv_faces.append((uv0, uv1, uv2))
                                uv_faces.append((uv0, uv2, uv3))
                                
                    elif prim_type == 0x90:  # Triangles
                        for i in range(0, len(indices) - 2, 3):
                            i0, i1, i2 = indices[i], indices[i+1], indices[i+2]
                            uv0, uv1, uv2 = uv_indices[i], uv_indices[i+1], uv_indices[i+2]
                            if i0 != i1 and i1 != i2 and i0 != i2:
                                faces.append((i0, i1, i2))
                                uv_faces.append((uv0, uv1, uv2))
                                
                    elif prim_type == 0x98:  # Triangle strip
                        for i in range(len(indices) - 2):
                            i0, i1, i2 = indices[i], indices[i+1], indices[i+2]
                            uv0, uv1, uv2 = uv_indices[i], uv_indices[i+1], uv_indices[i+2]
                            if i0 != i1 and i1 != i2 and i0 != i2:
                                if i % 2 == 0:
                                    faces.append((i0, i1, i2))
                                    uv_faces.append((uv0, uv1, uv2))
                                else:
                                    faces.append((i1, i0, i2))
                                    uv_faces.append((uv1, uv0, uv2))
                                    
                    elif prim_type == 0xA0:  # Triangle fan
                        if len(indices) >= 3:
                            for i in range(1, len(indices) - 1):
                                i0, i1, i2 = indices[0], indices[i], indices[i+1]
                                uv0, uv1, uv2 = uv_indices[0], uv_indices[i], uv_indices[i+1]
                                if i0 != i1 and i1 != i2 and i0 != i2:
                                    faces.append((i0, i1, i2))
                                    uv_faces.append((uv0, uv1, uv2))
            else:
                # Not a draw command we recognize - skip one byte
                offset += 1
        
        return faces, uv_faces


def import_ndm(context, filepath, import_textures=True, scale_factor=0.01):
    """Import an NDM file and create Blender objects"""
    
    if not HAS_BLENDER:
        print("Error: Blender modules not available")
        return {'CANCELLED'}
    
    try:
        parser = NDMParser(filepath)
        parser.read()
    except Exception as e:
        print(f"Error reading NDM file: {e}")
        import traceback
        traceback.print_exc()
        return {'CANCELLED'}
    
    if len(parser.nodes) == 0:
        print("No nodes found in NDM file")
        return {'CANCELLED'}
        
    # Create a collection for the imported model
    model_name = os.path.splitext(os.path.basename(filepath))[0]
    collection = bpy.data.collections.new(model_name)
    context.scene.collection.children.link(collection)
    
    # Create objects for each node
    created_objects = {}
    mesh_count = 0
    used_names = set()  # Track used names for O(1) duplicate checking
    
    for node in parser.nodes:
        if not node.name:
            continue
            
        # Create mesh if node has mesh data
        if node.has_mesh:
            vertices = parser.get_mesh_vertices(node)
            if len(vertices) == 0:
                print(f"Warning: Node '{node.name}' has no vertices")
                continue
                
            # Get faces and UV indices
            faces, uv_faces = parser.get_mesh_faces_and_uvs(node, len(vertices))
            
            # Get UV coordinates if available
            uvs = parser.get_mesh_uvs(node)
            
            # Create mesh with unique name
            if node.name in used_names:
                mesh_name = f"{node.name}_{mesh_count}"
            else:
                mesh_name = node.name
            used_names.add(mesh_name)
            mesh = bpy.data.meshes.new(mesh_name)
            
            # Scale vertices
            scaled_verts = [(v[0] * scale_factor, v[1] * scale_factor, v[2] * scale_factor) 
                           for v in vertices]
            
            # Create mesh from data
            try:
                if len(faces) > 0:
                    mesh.from_pydata(scaled_verts, [], faces)
                else:
                    # No faces - just create vertices as a point cloud
                    mesh.from_pydata(scaled_verts, [], [])
                
                mesh.update()
                mesh.validate()
            except Exception as e:
                print(f"Warning: Error creating mesh for '{node.name}': {e}")
                # Try with just vertices
                mesh.from_pydata(scaled_verts, [], [])
                mesh.update()
            
            # Create object
            obj = bpy.data.objects.new(mesh_name, mesh)
            
            # Apply UV coordinates if available
            if len(uvs) > 0 and len(uv_faces) > 0:
                try:
                    # Create UV layer
                    uv_layer = mesh.uv_layers.new(name="UVMap")
                    
                    # Apply UVs per face loop
                    for face_idx, face in enumerate(mesh.polygons):
                        if face_idx < len(uv_faces):
                            uv_indices = uv_faces[face_idx]
                            for loop_idx, loop in enumerate(face.loop_indices):
                                if loop_idx < len(uv_indices):
                                    uv_idx = uv_indices[loop_idx]
                                    if uv_idx < len(uvs):
                                        uv_layer.data[loop].uv = uvs[uv_idx]
                    
                    print(f"Applied {len(uvs)} UVs to '{node.name}'")
                except Exception as e:
                    print(f"Warning: Error applying UVs to '{node.name}': {e}")
            
            # Apply vertex colors from node color
            if node.color1 != (1.0, 1.0, 1.0, 1.0):
                try:
                    # Create vertex color layer
                    color_layer = mesh.vertex_colors.new(name="Color")
                    
                    # Apply color to all vertices
                    for poly in mesh.polygons:
                        for loop_idx in poly.loop_indices:
                            color_layer.data[loop_idx].color = node.color1
                    
                    print(f"Applied vertex color {node.color1} to '{node.name}'")
                except Exception as e:
                    print(f"Warning: Error applying vertex colors to '{node.name}': {e}")
            
            collection.objects.link(obj)
            created_objects[node.name] = obj
            mesh_count += 1
            
        else:
            # Create empty for non-mesh nodes (transform nodes, etc.)
            empty = bpy.data.objects.new(node.name, None)
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 0.1
            empty.location = (node.position[0] * scale_factor,
                            node.position[1] * scale_factor,
                            node.position[2] * scale_factor)
            collection.objects.link(empty)
            created_objects[node.name] = empty
    
    # Select the imported objects
    for obj in created_objects.values():
        obj.select_set(True)
    
    if created_objects:
        context.view_layer.objects.active = list(created_objects.values())[0]
    
    print(f"Imported {mesh_count} meshes and {len(created_objects) - mesh_count} empties from {filepath}")
    print(f"Textures referenced: {parser.textures}")
    
    return {'FINISHED'}
