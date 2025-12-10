#!/usr/bin/env python3
"""
Test script to validate NDM parser without Blender.
Tests parsing of vertices, faces, UVs, and vertex colors.
"""

import os
import sys

# Add io_import_ndm to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'io_import_ndm'))

from ndm_parser import NDMParser

def test_ndm_file(filepath):
    """Test parsing an NDM file"""
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(filepath)}")
    print('='*60)
    
    try:
        parser = NDMParser(filepath)
        parser.read()
        
        print(f"✓ Successfully parsed header")
        print(f"  Textures: {len(parser.textures)}")
        print(f"  Nodes: {len(parser.nodes)}")
        
        if parser.textures:
            print(f"  Texture names: {', '.join(parser.textures[:5])}")
            if len(parser.textures) > 5:
                print(f"  ... and {len(parser.textures) - 5} more")
        
        # Test each node
        total_vertices = 0
        total_faces = 0
        total_uvs = 0
        nodes_with_mesh = 0
        
        for node in parser.nodes:
            if node.has_mesh:
                nodes_with_mesh += 1
                vertices = parser.get_mesh_vertices(node)
                faces, uv_faces = parser.get_mesh_faces_and_uvs(node, len(vertices))
                uvs = parser.get_mesh_uvs(node)
                
                total_vertices += len(vertices)
                total_faces += len(faces)
                total_uvs += len(uvs)
                
                print(f"\n  Node: {node.name}")
                print(f"    Vertices: {len(vertices)}")
                print(f"    Faces: {len(faces)}")
                print(f"    UVs: {len(uvs)}")
                print(f"    UV faces: {len(uv_faces)}")
                if node.color1 != (1.0, 1.0, 1.0, 1.0):
                    print(f"    Color1: {node.color1}")
                
                # Validate data
                if len(vertices) > 0:
                    if len(faces) == 0:
                        print(f"    ⚠ Warning: Has vertices but no faces")
                    else:
                        # Check if all face indices are valid
                        max_idx = max(max(f) for f in faces)
                        if max_idx >= len(vertices):
                            print(f"    ✗ Error: Face index {max_idx} >= vertex count {len(vertices)}")
                        else:
                            print(f"    ✓ All face indices valid")
                    
                    # Check UV data
                    if len(uvs) > 0 and len(uv_faces) > 0:
                        max_uv_idx = max(max(f) for f in uv_faces)
                        if max_uv_idx >= len(uvs):
                            print(f"    ✗ Error: UV index {max_uv_idx} >= UV count {len(uvs)}")
                        else:
                            print(f"    ✓ All UV indices valid")
                    elif len(faces) > 0:
                        print(f"    ⚠ Warning: Has faces but no UVs")
        
        print(f"\n{'='*60}")
        print(f"Summary for {os.path.basename(filepath)}:")
        print(f"  Mesh nodes: {nodes_with_mesh}")
        print(f"  Total vertices: {total_vertices}")
        print(f"  Total faces: {total_faces}")
        print(f"  Total UVs: {total_uvs}")
        print('='*60)
        
        return True
        
    except Exception as e:
        print(f"✗ Error parsing file: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test all NDM files in current directory"""
    ndm_files = []
    for f in os.listdir('.'):
        if f.lower().endswith('.ndm'):
            ndm_files.append(f)
    
    if not ndm_files:
        print("No NDM files found in current directory")
        return
    
    print(f"Found {len(ndm_files)} NDM files to test")
    
    success_count = 0
    for ndm_file in sorted(ndm_files):
        if test_ndm_file(ndm_file):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Test Results: {success_count}/{len(ndm_files)} files parsed successfully")
    print('='*60)


if __name__ == '__main__':
    main()
