"""
DTX texture file loader.

DTX format appears to be a Nintendo-specific texture format with:
- Header containing dimensions and format info
- Pixel data in various formats (RGB565, RGBA8, etc.)

This module loads DTX files and converts them to images for use in Blender materials.
"""

import struct
import os
from typing import Optional, Tuple


def read_uint16_be(data: bytes, offset: int) -> int:
    """Read a big-endian uint16."""
    return struct.unpack('>H', data[offset:offset+2])[0]


def read_uint32_be(data: bytes, offset: int) -> int:
    """Read a big-endian uint32."""
    return struct.unpack('>I', data[offset:offset+4])[0]


def rgb565_to_rgba(value: int) -> Tuple[int, int, int, int]:
    """Convert RGB565 to RGBA8888."""
    r = ((value >> 11) & 0x1F) << 3
    g = ((value >> 5) & 0x3F) << 2
    b = (value & 0x1F) << 3
    return (r, g, b, 255)


def rgba5551_to_rgba(value: int) -> Tuple[int, int, int, int]:
    """Convert RGBA5551 to RGBA8888."""
    r = ((value >> 11) & 0x1F) << 3
    g = ((value >> 6) & 0x1F) << 3
    b = ((value >> 1) & 0x1F) << 3
    a = (value & 0x01) * 255
    return (r, g, b, a)


def parse_dtx_header(data: bytes) -> Optional[dict]:
    """
    Parse DTX header and return format information.
    
    DTX Header format (8 bytes):
    - byte 0-1: Format flags (e.g., 0x0004 = RGBA8, 0x0808 = indexed)
    - byte 2-3: Additional flags
    - byte 4-5: Width/format info
    - byte 6-7: Height/format info
    """
    if len(data) < 8:
        return None

    # Parse header bytes
    format_flags = read_uint16_be(data, 0)
    flags2 = read_uint16_be(data, 2)
    width_info = read_uint16_be(data, 4)
    height_info = read_uint16_be(data, 6)

    # Determine texture dimensions
    # Common dimensions are powers of 2: 32, 64, 128, 256
    
    # Try to extract dimensions from header
    # The format varies, so we'll try multiple interpretations
    
    width = 0
    height = 0
    format_type = 'unknown'
    
    # Format 0x0004 0x0808 appears to be common
    if format_flags == 0x0004:
        # Likely 8x8 blocks or similar
        format_type = 'block'
        # Dimensions may be encoded in other fields
        width = 64  # Default fallback
        height = 64
    elif format_flags == 0x0808:
        format_type = 'rgb565'
        width = 32
        height = 32
    
    # Try to compute dimensions from file size
    pixel_data_start = 32  # Assume 32-byte header
    data_size = len(data) - pixel_data_start
    
    # For RGB565, each pixel is 2 bytes
    pixel_count = data_size // 2
    
    # Common texture sizes
    common_sizes = [
        (256, 256), (256, 128), (128, 256),
        (128, 128), (128, 64), (64, 128),
        (64, 64), (64, 32), (32, 64),
        (32, 32), (32, 16), (16, 32),
        (16, 16), (8, 8),
    ]
    
    for w, h in common_sizes:
        if w * h == pixel_count:
            width = w
            height = h
            break
    
    if width == 0 or height == 0:
        # Try to guess from file size
        import math
        side = int(math.sqrt(pixel_count))
        if side * side == pixel_count:
            width = height = side
        else:
            # Non-square texture
            for factor in range(1, 512):
                if pixel_count % factor == 0:
                    other = pixel_count // factor
                    if other <= 512 and factor <= 512:
                        width = other
                        height = factor
                        break

    return {
        'format_flags': format_flags,
        'flags2': flags2,
        'width_info': width_info,
        'height_info': height_info,
        'width': width,
        'height': height,
        'format_type': format_type,
        'data_offset': 32,  # Typical header size
    }


def decode_dtx_pixels(data: bytes, header: dict) -> list:
    """
    Decode pixel data from DTX format to RGBA.
    
    Returns a flat list of [R, G, B, A, R, G, B, A, ...] values.
    """
    width = header['width']
    height = header['height']
    offset = header['data_offset']
    
    if width == 0 or height == 0:
        return []
    
    pixels = []
    
    # Try RGB565 decoding (most common)
    for y in range(height):
        for x in range(width):
            pixel_offset = offset + (y * width + x) * 2
            if pixel_offset + 2 > len(data):
                pixels.extend([128, 128, 128, 255])  # Gray fallback
                continue
            
            value = read_uint16_be(data, pixel_offset)
            r, g, b, a = rgb565_to_rgba(value)
            pixels.extend([r, g, b, a])
    
    return pixels


def load_dtx(filepath: str) -> Optional[dict]:
    """
    Load a DTX texture file.
    
    Returns a dict with:
    - 'width': texture width
    - 'height': texture height
    - 'pixels': list of RGBA pixel values
    - 'name': texture name from filename
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except IOError as e:
        print(f"Error reading DTX file: {e}")
        return None

    if len(data) < 32:
        print(f"DTX file too small: {filepath}")
        return None

    header = parse_dtx_header(data)
    if header is None:
        return None

    # If we couldn't determine dimensions, try to infer from file size
    if header['width'] == 0 or header['height'] == 0:
        # Assume RGB565 and common sizes
        data_size = len(data) - 32
        pixel_count = data_size // 2
        
        import math
        side = int(math.sqrt(pixel_count))
        if side > 0 and side * side == pixel_count:
            header['width'] = side
            header['height'] = side
        else:
            # Default to 64x64
            header['width'] = 64
            header['height'] = 64

    pixels = decode_dtx_pixels(data, header)

    name = os.path.splitext(os.path.basename(filepath))[0]

    return {
        'width': header['width'],
        'height': header['height'],
        'pixels': pixels,
        'name': name,
    }


def create_blender_image(dtx_data: dict, name: str = None):
    """
    Create a Blender image from DTX data.
    
    This function should be called from within Blender context.
    """
    try:
        import bpy
    except ImportError:
        print("Cannot create Blender image outside of Blender")
        return None

    if dtx_data is None:
        return None

    image_name = name or dtx_data.get('name', 'DTX_Texture')
    width = dtx_data['width']
    height = dtx_data['height']
    pixels = dtx_data['pixels']

    if width == 0 or height == 0 or not pixels:
        return None

    # Create new image
    image = bpy.data.images.new(
        name=image_name,
        width=width,
        height=height,
        alpha=True,
    )

    # Convert pixel values to float (0.0 - 1.0)
    float_pixels = [p / 255.0 for p in pixels]

    # Blender expects pixels in bottom-to-top order, but DTX is top-to-bottom
    # Flip the image vertically
    flipped_pixels = []
    for y in range(height - 1, -1, -1):
        row_start = y * width * 4
        row_end = row_start + width * 4
        flipped_pixels.extend(float_pixels[row_start:row_end])

    image.pixels[:] = flipped_pixels
    image.pack()

    return image


def find_dtx_file(directory: str, texture_name: str) -> Optional[str]:
    """
    Find a DTX file matching the given texture name in the directory.
    
    Tries various naming conventions and case variations.
    """
    if not texture_name:
        return None

    # Clean up the texture name
    name = texture_name.strip().upper()
    
    # Remove any extension if present
    if name.endswith('.DTX'):
        name = name[:-4]

    # Try different file name patterns
    patterns = [
        f"{name}.DTX",
        f"{name}.dtx",
        f"{name.lower()}.DTX",
        f"{name.lower()}.dtx",
        name + ".DTX",
        name + ".dtx",
    ]

    for pattern in patterns:
        filepath = os.path.join(directory, pattern)
        if os.path.exists(filepath):
            return filepath

    # Try case-insensitive search
    try:
        for filename in os.listdir(directory):
            if filename.upper().endswith('.DTX'):
                file_base = os.path.splitext(filename)[0].upper()
                if file_base == name:
                    return os.path.join(directory, filename)
    except OSError:
        pass

    return None
