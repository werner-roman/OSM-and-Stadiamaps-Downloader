import mercantile
import requests
from PIL import Image
import os
from io import BytesIO
import time

# Panel 18 bounds
lat_min, lon_min = 47.381, 8.3795  # bottom-left
lat_max, lon_max = 48.926, 10.6920  # top-right

# Zoom level (adjust depending on desired detail)
zoom = 10

# Get all tiles intersecting bounding box
print("Calculating required tiles...")
tiles = list(mercantile.tiles(lon_min, lat_min, lon_max, lat_max, zoom))
total_tiles = len(tiles)
print(f"Need to download {total_tiles} tiles")

# Create output image grid
tile_size = 256
cols = max(t.x for t in tiles) - min(t.x for t in tiles) + 1
rows = max(t.y for t in tiles) - min(t.y for t in tiles) + 1
image = Image.new('RGB', (cols * tile_size, rows * tile_size))

# Offset for placement
x_offset = min(t.x for t in tiles)
y_offset = min(t.y for t in tiles)

# Download and paste tiles
successful_downloads = 0
failed_downloads = 0

start_time = time.time()
for i, tile in enumerate(tiles):
    url = f"https://tile.openstreetmap.org/{tile.z}/{tile.x}/{tile.y}.png"
    headers = {
        "User-Agent": "RomanWerner-Panel18/1.0 (https://bytetools.org contact: roman@example.com)"
    }
    
    # Progress update
    progress = (i + 1) / total_tiles * 100
    elapsed = time.time() - start_time
    tiles_per_sec = (i + 1) / elapsed if elapsed > 0 else 0
    
    print(f"Downloading tile {i+1}/{total_tiles} ({progress:.1f}%) - {tiles_per_sec:.1f} tiles/sec", end="\r")
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            tile_img = Image.open(BytesIO(response.content))
            px = (tile.x - x_offset) * tile_size
            py = (tile.y - y_offset) * tile_size
            image.paste(tile_img, (px, py))
            successful_downloads += 1
        else:
            print(f"\nFailed to fetch {url} (Status: {response.status_code})")
            failed_downloads += 1
    except Exception as e:
        print(f"\nError downloading {url}: {str(e)}")
        failed_downloads += 1

print(f"\nDownloaded {successful_downloads} tiles successfully, {failed_downloads} failed")

# Calculate pixel positions for exact coordinates
def lat_lon_to_pixel(lat, lon):
    tile = mercantile.tile(lon, lat, zoom)
    tile_nw = mercantile.ul(tile.x, tile.y, tile.z)
    
    # Calculate position within the tile
    x_ratio = (lon - tile_nw[0]) / (mercantile.ul(tile.x + 1, tile.y, tile.z)[0] - tile_nw[0])
    y_ratio = (tile_nw[1] - lat) / (tile_nw[1] - mercantile.ul(tile.x, tile.y + 1, tile.z)[1])
    
    # Translate to pixel position in our image
    x = (tile.x - x_offset) * tile_size + x_ratio * tile_size
    y = (tile.y - y_offset) * tile_size + y_ratio * tile_size
    
    return int(x), int(y)

# Calculate pixel coordinates for cropping
print("Calculating exact crop boundaries...")
left, bottom = lat_lon_to_pixel(lat_min, lon_min)
right, top = lat_lon_to_pixel(lat_max, lon_max)

# Crop to exact coordinates
print("Cropping image to exact coordinates...")
cropped_image = image.crop((left, top, right, bottom))

# Save cropped image
cropped_image.save("panel18_map.png")
print("✅ Saved as panel18_map.png")
print(f"Final image size: {cropped_image.width}x{cropped_image.height} pixels")
