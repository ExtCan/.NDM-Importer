# NDM Importer for Blender

A Blender addon for importing NDM model files and DTX textures from Nintendo games.

## Features

- **NDM Model Import**: Full support for NDM 3D model files
  - Mesh geometry (vertices, faces)
  - UV coordinates
  - Materials/textures
  - Node hierarchy
  - Vertex colors
  - Armature/rigging support
  - Shape keys/blend shapes
  - Axis orientation options
  - Scale factor control

- **DTX Texture Loading**: 
  - Automatic loading when importing NDM files
  - Standalone DTX texture import
  - RGB565 format decoding

## Installation

### Method 1: Install from ZIP
1. Download the repository as a ZIP file
2. In Blender, go to `Edit > Preferences > Add-ons`
3. Click `Install...` and select the ZIP file
4. Enable the "NDM Importer" addon

### Method 2: Manual Installation
1. Copy the `ndm_importer` folder to your Blender addons directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
   - macOS: `~/Library/Application Support/Blender/<version>/scripts/addons/`
   - Linux: `~/.config/blender/<version>/scripts/addons/`
2. Restart Blender and enable the addon in Preferences

## Usage

### Importing NDM Models
1. Go to `File > Import > NDM Model (.ndm)`
2. Select one or more NDM files
3. Configure import options:
   - **Import Textures**: Load DTX textures as materials
   - **Import Vertex Colors**: Import vertex color data
   - **Import Normals**: Import custom normals
   - **Import Armature**: Import bone/rigging data if present
   - **Import Shape Keys**: Import blend shapes/morph targets if present
   - **Scale**: Scale factor for imported geometry (default 0.01)
   - **Forward/Up Axis**: Axis orientation options
4. Click Import

### Importing DTX Textures
1. Go to `File > Import > DTX Texture (.dtx)`
2. Select one or more DTX files
3. Textures will be added to Blender's image data

## File Formats

### NDM Format
NDM files contain 3D model data including:
- Header with material count and node count
- Material/texture names (references to DTX files)
- Node hierarchy data
- Per-node mesh data:
  - Vertices (int16 x, y, z coordinates)
  - UVs (indexed texture coordinates)
  - Faces (GX display lists with tristrip/trilist/quad primitives)

### DTX Format
DTX files are texture files with:
- 32-byte header with dimensions (as powers of 2)
- Pixel data in RGB565 format (2 bytes per pixel)

## Technical Details

### GX Display List Format
The NDM files use Nintendo's GX graphics library format for face data:
- `0x80`: Triangle Strip primitive
- `0x90`: Triangle List primitive  
- `0x98`: Quad List primitive

Each vertex in the display list contains:
- Position index (1 byte)
- UV/attribute index (1 byte)

### Statistics
Tested with sample files:
- 16 NDM files: 532,767 vertices, 808,160 faces
- 278 DTX files: All loaded successfully

## Requirements

- Blender 2.80 or later

## License

This project is for educational and preservation purposes.