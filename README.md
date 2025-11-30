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

- **DTX Texture Loading**: Automatic loading of DTX texture files as materials

## Installation

1. Download the `ndm_importer` folder
2. In Blender, go to `Edit > Preferences > Add-ons`
3. Click `Install...` and select the `ndm_importer` folder (as a zip file)
4. Enable the "NDM Importer" addon

Or manually:
1. Copy the `ndm_importer` folder to your Blender addons directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
   - macOS: `~/Library/Application Support/Blender/<version>/scripts/addons/`
   - Linux: `~/.config/blender/<version>/scripts/addons/`
2. Restart Blender and enable the addon in Preferences

## Usage

1. Go to `File > Import > NDM (.ndm)`
2. Select one or more NDM files
3. Configure import options:
   - **Import Textures**: Load DTX textures as materials
   - **Import Vertex Colors**: Import vertex color data
   - **Import Normals**: Import custom normals
   - **Import Armature**: Import bone/rigging data if present
   - **Import Shape Keys**: Import blend shapes/morph targets if present
   - **Scale**: Scale factor for imported geometry (default 0.01)
4. Click Import

## File Formats

### NDM Format
NDM files contain 3D model data including:
- Header with material count and node count
- Material/texture names (references to DTX files)
- Node hierarchy data
- Per-node mesh data (vertices, UVs, faces using GX display lists)

### DTX Format
DTX files are texture files in RGB565 format. They are automatically loaded when importing NDM files if present in the same directory.

## Supported Games

This importer is designed for NDM files from Nintendo games, particularly those using the GX graphics library (GameCube/Wii era).

## License

This project is for educational and preservation purposes.