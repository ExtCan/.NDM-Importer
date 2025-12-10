# NDM Importer for Blender

A Blender addon for importing .NDM model files from the Nintendo GameCube tech demo "ind-nddemo" (also known as the "Peach's Castle Demo").

## Installation

1. Download the `io_import_ndm` folder
2. In Blender, go to Edit > Preferences > Add-ons
3. Click "Install..." and navigate to the `io_import_ndm` folder (or zip it first)
4. Enable the "NDM Model Importer" addon

## Usage

1. Go to File > Import > NDM (.ndm)
2. Select an NDM file to import
3. Adjust import settings as needed:
   - **Scale**: Scale factor for the imported model (default: 0.01)
   - **Import Textures**: Attempt to import referenced textures (not yet implemented)

## Supported Files

The addon supports .NDM files from the Peach's Castle Demo, including:
- Character models (e.g., KURIBO.NDM - Goomba)
- Environment models (e.g., STG_ENTR.NDM - stage entrance)
- Props (e.g., COIN.NDM, BIPLANE.NDM)

## File Format

NDM files contain:
- Texture references (names only, textures stored separately)
- Node hierarchy (transforms and bones)
- Mesh data (vertices as signed int16 triplets, scaled by 1/256)
- Display lists (GameCube GX commands for face definitions)

## Limitations

- Textures are not imported (only referenced by name, requires DTX file parsing)
- Animations are not supported
- Normal vectors are not yet extracted from display lists

## Recent Improvements

- ✅ UV coordinates are now imported and applied to meshes
- ✅ Vertex colors from node colors are now applied to meshes
- ✅ Improved display list parsing for better compatibility

## License

This addon is provided for educational and preservation purposes.