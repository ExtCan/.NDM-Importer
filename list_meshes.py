#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/runner/work/.NDM-Importer/.NDM-Importer/io_import_ndm')
from ndm_parser import NDMParser

if len(sys.argv) < 2:
    print("Usage: python3 list_meshes.py <filename.ndm>")
    sys.exit(1)

filename = sys.argv[1]
parser = NDMParser(filename)

print(f"File: {filename}")
print(f"Total nodes: {len(parser.nodes)}")
print(f"\nMesh nodes:")

for i, node in enumerate(parser.nodes):
    if node.has_mesh:
        verts = len(parser.get_mesh_vertices(node))
        print(f"  {i}: '{node.name}' ({verts} vertices)")
