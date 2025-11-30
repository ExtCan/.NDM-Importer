"""
NDM file format parser.

NDM file structure (big-endian):
- Header (16 bytes):
  - uint32: Number of textures/materials
  - uint32: Texture table end offset (from start of file)
  - uint32: Node flags (high word = node count)
  - uint32: Node data size info
- Texture names (16 bytes each, null-terminated, starting at offset 0x20)
- Hierarchy data (3 bytes per node: type, parent_low, parent_high)
- Node blocks (128 bytes header + geometry data each)

Node block structure (128 bytes header):
- +0x00: Name (32 bytes, null-terminated)
- +0x20: Transform floats (position, rotation, scale - 12 floats = 48 bytes)
- +0x50: Geometry descriptor (48 bytes):
  - +0x00: Vertex data size in bytes
  - +0x04: UV data offset (relative to vertex data start)
  - +0x08: Face data offset (relative to vertex data start)
  - +0x0C: Flags
  - +0x10: Total geometry size
  - +0x14+: Additional info (colors, etc.)
- +0x80: Geometry data starts (vertices, then UVs, then faces)

Vertex format: int16 x, int16 y, int16 z (6 bytes each)
UV format: uint8 u, uint8 v (2 bytes each)
Face format: (vertex_index, flags) pairs in triangle strips
"""

import struct
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class NDMMaterial:
    """Material/texture reference"""
    name: str
    index: int


@dataclass
class NDMVertex:
    """Vertex with position, UV, normal, and color"""
    position: Tuple[float, float, float]
    uv: Optional[Tuple[float, float]] = None
    normal: Optional[Tuple[float, float, float]] = None
    color: Optional[Tuple[int, int, int, int]] = None


@dataclass
class NDMFace:
    """Triangle face with vertex indices"""
    indices: Tuple[int, int, int]
    material_index: int = 0


@dataclass
class NDMNode:
    """Node/mesh in the model hierarchy"""
    name: str
    parent_index: int = -1
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    material_index: int = 0
    vertices: List[NDMVertex] = field(default_factory=list)
    faces: List[NDMFace] = field(default_factory=list)
    vertex_colors: List[Tuple[int, int, int, int]] = field(default_factory=list)
    # For armature/rigging
    bone_weights: List[List[Tuple[int, float]]] = field(default_factory=list)
    # For blend shapes
    shape_keys: dict = field(default_factory=dict)


@dataclass
class NDMData:
    """Complete NDM file data"""
    materials: List[NDMMaterial]
    nodes: List[NDMNode]
    hierarchy: List[Tuple[int, int, int]]  # (type, parent, child) relationships


def read_string(data: bytes, offset: int, max_length: int = 16) -> str:
    """Read a null-terminated string from bytes."""
    end = offset
    while end < offset + max_length and end < len(data) and data[end] != 0:
        end += 1
    try:
        return data[offset:end].decode('ascii', errors='replace').strip()
    except Exception:
        return ""


def read_uint32_be(data: bytes, offset: int) -> int:
    """Read a big-endian uint32."""
    return struct.unpack('>I', data[offset:offset+4])[0]


def read_uint16_be(data: bytes, offset: int) -> int:
    """Read a big-endian uint16."""
    return struct.unpack('>H', data[offset:offset+2])[0]


def read_int16_be(data: bytes, offset: int) -> int:
    """Read a big-endian int16."""
    return struct.unpack('>h', data[offset:offset+2])[0]


def read_float_be(data: bytes, offset: int) -> float:
    """Read a big-endian float."""
    return struct.unpack('>f', data[offset:offset+4])[0]


def read_uint8(data: bytes, offset: int) -> int:
    """Read a uint8."""
    return data[offset]


def parse_ndm(filepath: str) -> Optional[NDMData]:
    """
    Parse an NDM file and return the model data.
    
    The NDM format appears to be from a Nintendo game (possibly Mario related
    based on the texture names). The format uses big-endian byte ordering.
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except IOError as e:
        print(f"Error reading file: {e}")
        return None

    if len(data) < 16:
        print("File too small to be a valid NDM file")
        return None

    # Parse header
    num_textures = read_uint32_be(data, 0)
    texture_table_end = read_uint32_be(data, 4)  # End offset of texture table
    node_flags = read_uint32_be(data, 8)
    node_data_size = read_uint32_be(data, 12)

    # Extract number of nodes from flags (high word)
    num_nodes = (node_flags >> 16) & 0xFFFF
    if num_nodes == 0:
        # Try alternate interpretation
        num_nodes = node_flags & 0xFFFF

    # Validate header
    if num_textures > 1000:
        print(f"Invalid header values: textures={num_textures}")
        return None

    materials = []
    nodes = []
    hierarchy = []

    # Read texture/material names (16 bytes each, starting at offset 0x20)
    tex_offset = 0x20
    for i in range(num_textures):
        if tex_offset + 16 > len(data):
            break
        name = read_string(data, tex_offset, 16)
        materials.append(NDMMaterial(name=name, index=i))
        tex_offset += 16

    # Read node hierarchy data (3 bytes per entry)
    # Starts after texture names
    hier_offset = 0x20 + num_textures * 16
    for i in range(num_nodes):
        if hier_offset + 3 > len(data):
            break
        type_flag = read_uint8(data, hier_offset)
        parent_low = read_uint8(data, hier_offset + 1)
        parent_high = read_uint8(data, hier_offset + 2)
        parent = (parent_high << 8) | parent_low
        if parent == 0xFFFF:
            parent = -1
        hierarchy.append((type_flag, parent, i))
        hier_offset += 3

    # Parse node/mesh data blocks
    # Nodes start after header + texture table (at texture_table_end + 16)
    # But we need to find actual node blocks which start with a name
    node_block_start = texture_table_end + 16
    
    parsed_nodes = parse_mesh_blocks(data, node_block_start, num_nodes, hierarchy, materials)
    nodes.extend(parsed_nodes)

    return NDMData(
        materials=materials,
        nodes=nodes,
        hierarchy=hierarchy,
    )


def parse_mesh_blocks(data: bytes, start_offset: int, expected_nodes: int, 
                      hierarchy: List[Tuple[int, int, int]],
                      materials: List[NDMMaterial]) -> List[NDMNode]:
    """Parse mesh data blocks from the NDM file."""
    nodes = []
    
    # Find all node blocks by scanning for valid names
    offset = start_offset
    
    while offset < len(data) - 128 and len(nodes) < max(expected_nodes, 100):
        # Try to find a valid node block (starts with a name)
        name = read_string(data, offset, 32)
        
        # Check if this looks like a valid node name
        if name and len(name) >= 1 and is_valid_name(name):
            node = parse_single_node(data, offset, materials)
            if node and (len(node.vertices) > 0 or len(node.faces) > 0):
                nodes.append(node)
            
            # Move to next potential node block
            # Node blocks are 128 bytes header + variable geometry
            # Try to find the next node by looking for the next valid name
            offset = find_next_node_offset(data, offset + 128)
        else:
            offset += 4  # Try next alignment

    return nodes


def is_valid_name(name: str) -> bool:
    """Check if a string looks like a valid node name."""
    if not name:
        return False
    # Must have at least some alphanumeric characters
    has_alpha = any(c.isalpha() for c in name)
    # All characters must be printable and reasonable
    all_valid = all(c.isalnum() or c in '_.-' for c in name)
    return has_alpha and all_valid


def find_next_node_offset(data: bytes, start: int) -> int:
    """Find the offset of the next node block."""
    offset = start
    
    while offset < len(data) - 32:
        # Look for a valid name at this offset
        name = read_string(data, offset, 32)
        if name and len(name) >= 1 and is_valid_name(name):
            return offset
        offset += 4  # Check every 4 bytes for alignment
    
    return len(data)


def parse_single_node(data: bytes, node_offset: int, 
                      materials: List[NDMMaterial]) -> Optional[NDMNode]:
    """Parse a single node block starting at the given offset."""
    if node_offset + 128 > len(data):
        return None

    # Read node name (32 bytes)
    name = read_string(data, node_offset, 32)
    if not name:
        return None

    node = NDMNode(name=name)

    # Read transform data at +32
    # The layout seems to be:
    # +32: position x, y, z (3 floats or 6 bytes as int16s)
    # +44: scale x, y, z (3 floats) - actually at +40, +44, +48
    transform_offset = node_offset + 32
    
    try:
        # Check if we have valid float values for scale
        scale_x = read_float_be(data, transform_offset + 8)
        scale_y = read_float_be(data, transform_offset + 12)
        scale_z = read_float_be(data, transform_offset + 16)
        
        # Validate scale values (should be reasonable, not NaN or extremely large)
        if (not (scale_x != scale_x) and not (scale_y != scale_y) and not (scale_z != scale_z) and
            abs(scale_x) < 1000 and abs(scale_y) < 1000 and abs(scale_z) < 1000 and
            abs(scale_x) > 0.0001 and abs(scale_y) > 0.0001 and abs(scale_z) > 0.0001):
            node.scale = (scale_x, scale_y, scale_z)
        else:
            node.scale = (1.0, 1.0, 1.0)
    except Exception:
        node.scale = (1.0, 1.0, 1.0)

    # Geometry descriptor at +80
    geom_desc_offset = node_offset + 80
    
    # Read geometry sizes from descriptor
    vertex_data_size = read_uint32_be(data, geom_desc_offset)
    uv_rel_offset = read_uint32_be(data, geom_desc_offset + 4)
    face_rel_offset = read_uint32_be(data, geom_desc_offset + 8)
    
    # Validate sizes
    if vertex_data_size == 0 or vertex_data_size > 0x100000:
        # Try alternate offset
        return parse_node_geometry_fallback(data, node_offset, node)

    # Geometry data starts at +128
    geom_data_offset = node_offset + 128
    
    # Calculate vertex count (6 bytes per vertex: int16 x, y, z)
    num_vertices = vertex_data_size // 6
    
    if num_vertices < 3 or num_vertices > 100000:
        return parse_node_geometry_fallback(data, node_offset, node)

    # Read vertices
    vertices = []
    for i in range(num_vertices):
        vert_offset = geom_data_offset + i * 6
        if vert_offset + 6 > len(data):
            break
        x = read_int16_be(data, vert_offset)
        y = read_int16_be(data, vert_offset + 2)
        z = read_int16_be(data, vert_offset + 4)
        vertices.append((float(x), float(y), float(z)))

    if len(vertices) < 3:
        return node

    # Read UVs (at vertex_data_offset + vertex_data_size, or use relative offset)
    uv_offset = geom_data_offset + vertex_data_size
    uvs = []
    for i in range(len(vertices)):
        uv_pos = uv_offset + i * 2  # UVs are 2 bytes each (u8, u8)
        if uv_pos + 2 > len(data):
            break
        u = data[uv_pos] / 255.0
        v = data[uv_pos + 1] / 255.0
        uvs.append((u, v))

    # Read faces
    # Face data starts after UVs
    face_offset = uv_offset + len(vertices) * 2
    
    # Skip to face data if we have a relative offset
    # The offset can be larger than 0x10000 for big models
    if face_rel_offset > 0 and face_rel_offset < len(data):
        face_offset = geom_data_offset + face_rel_offset

    faces = parse_face_data(data, face_offset, len(vertices))

    # Create vertex list with UVs
    scale = 1.0 / 256.0  # Scale factor for vertex positions
    for i, (x, y, z) in enumerate(vertices):
        uv = uvs[i] if i < len(uvs) else None
        node.vertices.append(NDMVertex(
            position=(x * scale, y * scale, z * scale),
            uv=uv,
        ))

    # Add faces
    for face_indices in faces:
        if len(face_indices) >= 3:
            idx0, idx1, idx2 = face_indices[0], face_indices[1], face_indices[2]
            if idx0 < len(vertices) and idx1 < len(vertices) and idx2 < len(vertices):
                node.faces.append(NDMFace(indices=(idx0, idx1, idx2)))

    return node


def parse_face_data(data: bytes, offset: int, num_vertices: int) -> List[Tuple[int, int, int]]:
    """Parse face/triangle data from the given offset.
    
    The face data uses GX display list format:
    - Command byte (0x80 = tristrip, 0x90 = trilist, 0x98 = quads)
    - Vertex count (16-bit big-endian)
    - Vertex data (2 bytes per vertex: position index + attribute)
    """
    faces = []
    max_faces = num_vertices * 4  # Reasonable upper limit
    
    pos = offset
    
    # Search for GX display list commands
    while pos < len(data) - 4 and len(faces) < max_faces:
        cmd = data[pos]
        
        # GX primitive commands: 0x80=tristrip, 0x90=trilist, 0x98=quads, 0xA0=lines, 0xB0=linestrip, 0xB8=points
        if cmd in [0x80, 0x90, 0x98, 0xA0, 0xA8, 0xB0, 0xB8]:
            if pos + 3 > len(data):
                break
                
            vert_count = read_uint16_be(data, pos + 1)
            
            # Sanity check
            if vert_count == 0 or vert_count > 10000:
                pos += 1
                continue
            
            # Read vertex indices (2 bytes per vertex: index + attribute)
            vertex_data_start = pos + 3
            vertex_indices = []
            
            for i in range(vert_count):
                idx_pos = vertex_data_start + i * 2
                if idx_pos + 2 > len(data):
                    break
                vertex_idx = data[idx_pos]
                if vertex_idx < num_vertices:
                    vertex_indices.append(vertex_idx)
                else:
                    # If we hit invalid indices, the format might be different
                    break
            
            if len(vertex_indices) < 3:
                pos += 1
                continue
            
            # Convert primitives to triangles
            if cmd == 0x80:  # Triangle strip
                for i in range(len(vertex_indices) - 2):
                    v0, v1, v2 = vertex_indices[i], vertex_indices[i+1], vertex_indices[i+2]
                    # Skip degenerate triangles
                    if v0 != v1 and v1 != v2 and v0 != v2:
                        if i % 2 == 0:
                            faces.append((v0, v1, v2))
                        else:
                            faces.append((v0, v2, v1))  # Flip winding for odd triangles
                            
            elif cmd == 0x90:  # Triangle list
                for i in range(0, len(vertex_indices) - 2, 3):
                    v0, v1, v2 = vertex_indices[i], vertex_indices[i+1], vertex_indices[i+2]
                    if v0 != v1 and v1 != v2 and v0 != v2:
                        faces.append((v0, v1, v2))
                        
            elif cmd == 0x98:  # Quad list
                for i in range(0, len(vertex_indices) - 3, 4):
                    v0, v1, v2, v3 = vertex_indices[i], vertex_indices[i+1], vertex_indices[i+2], vertex_indices[i+3]
                    # Split quad into two triangles
                    if v0 != v1 and v1 != v2 and v0 != v2:
                        faces.append((v0, v1, v2))
                    if v0 != v2 and v2 != v3 and v0 != v3:
                        faces.append((v0, v2, v3))
            
            # Move past this command
            pos = vertex_data_start + vert_count * 2
        else:
            pos += 1
    
    # If no GX commands found, try the old simple format
    if len(faces) == 0:
        faces = parse_face_data_simple(data, offset, num_vertices)
    
    return faces


def parse_face_data_simple(data: bytes, offset: int, num_vertices: int) -> List[Tuple[int, int, int]]:
    """Parse face data in simple (index, flags) pair format."""
    faces = []
    max_faces = num_vertices * 2
    
    pos = offset
    while pos + 6 <= len(data) and len(faces) < max_faces:
        # Face format is (vertex_index, flags) pairs
        idx0 = data[pos]
        flg0 = data[pos + 1]
        idx1 = data[pos + 2]
        flg1 = data[pos + 3]
        idx2 = data[pos + 4]
        flg2 = data[pos + 5]
        
        # Check for end markers
        if idx0 == 0 and flg0 == 0 and idx1 == 0 and flg1 == 0 and idx2 == 0 and flg2 == 0:
            pos += 6
            continue
        
        # Validate indices
        if idx0 < num_vertices and idx1 < num_vertices and idx2 < num_vertices:
            if not (idx0 == idx1 or idx1 == idx2 or idx0 == idx2):
                faces.append((idx0, idx1, idx2))
        else:
            break
        
        pos += 6
    
    return faces


def parse_node_geometry_fallback(data: bytes, node_offset: int, 
                                  node: NDMNode) -> NDMNode:
    """Fallback geometry parser for non-standard node layouts."""
    # Try to find vertex data by scanning for patterns
    offset = node_offset + 128
    
    while offset < min(len(data) - 32, node_offset + 512):
        # Look for vertex data patterns (reasonable int16 coordinates)
        vertices, uvs, faces = try_parse_geometry_at(data, offset)
        
        if len(vertices) >= 3:
            scale = 1.0 / 256.0
            for i, (x, y, z) in enumerate(vertices):
                uv = uvs[i] if i < len(uvs) else None
                node.vertices.append(NDMVertex(
                    position=(x * scale, y * scale, z * scale),
                    uv=uv,
                ))
            for face_indices in faces:
                if len(face_indices) >= 3:
                    node.faces.append(NDMFace(indices=(face_indices[0], face_indices[1], face_indices[2])))
            break
        
        offset += 4
    
    return node


def try_parse_geometry_at(data: bytes, offset: int) -> Tuple[
    List[Tuple[float, float, float]], 
    List[Tuple[float, float]], 
    List[Tuple[int, int, int]]
]:
    """Try to parse geometry starting at the given offset."""
    vertices = []
    uvs = []
    faces = []
    
    # Try to read vertices (int16 x, y, z)
    vert_offset = offset
    max_vertices = 1000
    
    for i in range(max_vertices):
        if vert_offset + 6 > len(data):
            break
        
        x = read_int16_be(data, vert_offset)
        y = read_int16_be(data, vert_offset + 2)
        z = read_int16_be(data, vert_offset + 4)
        
        # Check for reasonable values (not too large, not all zeros after first)
        if abs(x) < 16000 and abs(y) < 16000 and abs(z) < 16000:
            vertices.append((float(x), float(y), float(z)))
            vert_offset += 6
        else:
            break
    
    if len(vertices) < 3:
        return [], [], []
    
    # Try to read UVs after vertices
    uv_offset = vert_offset
    for i in range(len(vertices)):
        if uv_offset + 2 > len(data):
            break
        u = data[uv_offset] / 255.0
        v = data[uv_offset + 1] / 255.0
        uvs.append((u, v))
        uv_offset += 2
    
    # Try to read faces after UVs
    face_offset = uv_offset
    faces = parse_face_data(data, face_offset, len(vertices))
    
    return vertices, uvs, faces
