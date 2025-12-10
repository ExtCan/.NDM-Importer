#!/usr/bin/env python3
"""
Debug script to export detailed mesh information for troubleshooting.
Usage: python3 debug_mesh.py <filename.ndm> <mesh_name>
"""
import sys
import struct

sys.path.insert(0, 'io_import_ndm')
from ndm_parser import NDMParser

def debug_mesh(filename, mesh_name):
    parser = NDMParser(filename)
    parser.read()
    
    # Find the mesh
    node = None
    for n in parser.nodes:
        if n.name == mesh_name:
            node = n
            break
    
    if not node:
        print(f"ERROR: Mesh '{mesh_name}' not found in {filename}")
        print(f"Available meshes: {[n.name for n in parser.nodes if n.has_mesh][:20]}")
        return
    
    print(f"="*80)
    print(f"Debug info for mesh: {mesh_name} in {filename}")
    print(f"="*80)
    
    # Node info
    print(f"\nNode properties:")
    print(f"  has_mesh: {node.has_mesh}")
    print(f"  position: {node.position}")
    print(f"  scale: {node.scale}")
    print(f"  mesh_data_offset: 0x{node.mesh_data_offset:X}")
    print(f"  vertex_data_size: {node.vertex_data_size} bytes")
    print(f"  display_list_size: {node.display_list_size} bytes")
    print(f"  dl_header_size: {node.dl_header_size} bytes")
    
    # Extract geometry
    vertices = parser.get_mesh_vertices(node)
    faces, uv_faces = parser.get_mesh_faces_and_uvs(node, len(vertices))
    uvs = parser.get_mesh_uvs(node)
    
    print(f"\nGeometry:")
    print(f"  Vertices: {len(vertices)}")
    print(f"  Faces: {len(faces)}")
    print(f"  UVs: {len(uvs)}")
    
    # Detect format
    dl_offset = node.mesh_data_offset + node.vertex_data_size
    dl_end = dl_offset + node.display_list_size
    detected_format = parser._detect_vertex_ref_format(dl_offset, dl_end, len(vertices))
    print(f"  Detected format: {detected_format}-byte")
    
    # Check for issues
    degenerate = sum(1 for f in faces if len(set(f)) != len(f))
    invalid_idx = sum(1 for f in faces if any(idx >= len(vertices) or idx < 0 for idx in f))
    print(f"\n  Degenerate faces: {degenerate}")
    print(f"  Invalid face indices: {invalid_idx}")
    
    # Vertex bounds
    if vertices:
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        zs = [v[2] for v in vertices]
        print(f"\nVertex bounds:")
        print(f"  X: {min(xs):.2f} to {max(xs):.2f} (range: {max(xs)-min(xs):.2f})")
        print(f"  Y: {min(ys):.2f} to {max(ys):.2f} (range: {max(ys)-min(ys):.2f})")
        print(f"  Z: {min(zs):.2f} to {max(zs):.2f} (range: {max(zs)-min(zs):.2f})")
    
    # Sample vertices
    print(f"\nFirst 10 vertices:")
    for i, v in enumerate(vertices[:10]):
        print(f"  {i}: ({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})")
    
    # Sample faces
    print(f"\nFirst 10 faces:")
    for i, f in enumerate(faces[:10]):
        print(f"  {i}: {f}")
    
    # Draw commands
    print(f"\nDraw commands:")
    dl_offset_with_header = node.mesh_data_offset + node.vertex_data_size + node.dl_header_size
    offset = dl_offset_with_header
    cmd_count = 0
    
    while offset < dl_end and cmd_count < 10:
        cmd = parser.data[offset]
        if cmd in [0x80, 0x90, 0x98, 0xA0]:
            count = struct.unpack_from('>H', parser.data, offset + 1)[0]
            cmd_names = {0x80: 'QUADS', 0x90: 'TRIS', 0x98: 'TRISTRIP', 0xA0: 'TRIFAN'}
            cmd_count += 1
            print(f"  {cmd_count}. Offset 0x{offset:X}: {cmd_names.get(cmd, 'UNKNOWN')} count={count}")
            offset += 3 + count * detected_format
        else:
            offset += 1
    
    if cmd_count >= 10:
        print(f"  ... (showing first 10 commands only)")
    
    print(f"\n" + "="*80)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 debug_mesh.py <filename.ndm> <mesh_name>")
        print("Example: python3 debug_mesh.py STG_ENTR.NDM obj111")
        sys.exit(1)
    
    debug_mesh(sys.argv[1], sys.argv[2])
