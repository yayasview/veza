#!/usr/bin/env python3
"""
Create simple placeholder icons for the Chrome extension.
These are minimal valid PNG files with a red circle (record icon).
"""

import zlib
import struct
import os

def create_png(width, height, filename):
    """Create a simple PNG with a red circle on white background."""

    def make_pixel(x, y, w, h):
        """Return RGB for pixel at x,y."""
        # Center of the image
        cx, cy = w / 2, h / 2
        # Radius of the circle (80% of half the smaller dimension)
        radius = min(w, h) * 0.4

        # Distance from center
        dx = x - cx
        dy = y - cy
        dist = (dx * dx + dy * dy) ** 0.5

        if dist <= radius:
            # Red circle
            return (234, 67, 53)  # Google red
        else:
            # White background
            return (255, 255, 255)

    # Create raw image data
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # Filter byte for each row
        for x in range(width):
            r, g, b = make_pixel(x, y, width, height)
            raw_data += bytes([r, g, b])

    # Compress the data
    compressed = zlib.compress(raw_data, 9)

    def png_chunk(chunk_type, data):
        """Create a PNG chunk."""
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    # PNG signature
    png_signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk
    idat_chunk = png_chunk(b'IDAT', compressed)

    # IEND chunk
    iend_chunk = png_chunk(b'IEND', b'')

    # Combine all chunks
    png_data = png_signature + ihdr_chunk + idat_chunk + iend_chunk

    # Write to file
    with open(filename, 'wb') as f:
        f.write(png_data)

    print(f'Created {filename} ({width}x{height})')

if __name__ == '__main__':
    # Create icons directory if it doesn't exist
    icons_dir = os.path.dirname(os.path.abspath(__file__)) + '/icons'
    os.makedirs(icons_dir, exist_ok=True)

    # Create icons of different sizes
    create_png(16, 16, f'{icons_dir}/icon16.png')
    create_png(48, 48, f'{icons_dir}/icon48.png')
    create_png(128, 128, f'{icons_dir}/icon128.png')

    print('All icons created successfully!')
