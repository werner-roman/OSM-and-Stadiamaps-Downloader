import mercantile
import requests
from PIL import Image, ImageFile
import os
from io import BytesIO
import time
import hashlib
import sys

# Disable the decompression bomb protection for large images
Image.MAX_IMAGE_PIXELS = None  # Remove limit
ImageFile.LOAD_TRUNCATED_IMAGES = True  # Add this to handle potentially truncated images

# Create cache directory if it doesn't exist
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tile_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Panel 18 bounds
lat_min, lon_min = 47.381, 8.3795  # bottom-left
lat_max, lon_max = 48.926, 10.6920  # top-right

# Zoom level (adjust depending on desired detail)
zoom = 8

# Define available tile servers
TILE_SERVERS = {
    "osm": {
        "name": "OpenStreetMap Standard",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "© OpenStreetMap contributors",
        "user_agent": "OSM_Downloader/1.0 (Personal non-commercial project; caching enabled; contact: example@example.com)",
        "format": "png",
        "requires_key": False
    },
    "stamen-toner-lite": {
        "name": "Stamen Toner Lite (via Stadia)",
        "url": "https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}.png",
        "attribution": "Map tiles by Stamen Design, under CC BY 4.0. Data by OpenStreetMap, under ODbL.",
        "user_agent": "OSM_Downloader/1.0 (Personal non-commercial project; caching enabled; contact: example@example.com)",
        "format": "png",
        "requires_key": True  # Stadia Maps requires API key
    },
    "stamen-terrain": {
        "name": "Stamen Terrain (via Stadia)",
        "url": "https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png",
        "attribution": "Map tiles by Stamen Design, under CC BY 4.0. Data by OpenStreetMap, under ODbL.",
        "user_agent": "OSM_Downloader/1.0 (Personal non-commercial project; caching enabled; contact: example@example.com)",
        "format": "png",
        "requires_key": True  # Stadia Maps requires API key
    },
    "stamen-watercolor": {
        "name": "Stamen Watercolor (via Stadia)",
        "url": "https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg",
        "attribution": "Map tiles by Stamen Design, under CC BY 4.0. Data by OpenStreetMap, under CC BY SA.",
        "user_agent": "OSM_Downloader/1.0 (Personal non-commercial project; caching enabled; contact: example@example.com)",
        "format": "jpg",
        "requires_key": True  # Stadia Maps requires API key
    },
    "alidade-smooth": {
        "name": "Alidade Smooth (via Stadia)",
        "url": "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png",
        "attribution": "© Stadia Maps, © OpenMapTiles, © OpenStreetMap contributors",
        "user_agent": "OSM_Downloader/1.0 (Personal non-commercial project; caching enabled; contact: example@example.com)",
        "format": "png",
        "requires_key": True  # Stadia Maps requires API key
    },
    "alidade-smooth-dark": {
        "name": "Alidade Smooth Dark (via Stadia)",
        "url": "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png",
        "attribution": "© Stadia Maps, © OpenMapTiles, © OpenStreetMap contributors",
        "user_agent": "OSM_Downloader/1.0 (Personal non-commercial project; caching enabled; contact: example@example.com)",
        "format": "png",
        "requires_key": True  # Stadia Maps requires API key
    }
}

# Let user choose the tile server using numbers
print("Available tile servers:")
server_keys = list(TILE_SERVERS.keys())
for i, key in enumerate(server_keys):
    server = TILE_SERVERS[key]
    key_requirement = "(API key required)" if server["requires_key"] else ""
    print(f"{i+1}. {server['name']} {key_requirement}")

# Get user selection by number
while True:
    try:
        selection = input(f"Choose a tile server (1-{len(server_keys)}, default: 1): ").strip()
        if selection == "":
            selected_index = 0  # Default to first option (OSM)
            break
        selected_index = int(selection) - 1
        if 0 <= selected_index < len(server_keys):
            break
        else:
            print(f"Please enter a number between 1 and {len(server_keys)}")
    except ValueError:
        print("Please enter a valid number")

# Get the key for the selected server
tile_server_choice = server_keys[selected_index]
print(f"Using: {TILE_SERVERS[tile_server_choice]['name']}")

# Handle API key for Stadia Maps services
api_key = None
if TILE_SERVERS[tile_server_choice]['requires_key']:
    print("\n⚠️ This tile server requires a Stadia Maps API key.")
    print("- Register for a free account at https://client.stadiamaps.com/signup/")
    print("- Create an API key in your dashboard")
    print("- Free tier includes 2,500 map views/day (~100,000 tiles/month)")
    
    api_key_input = input("Enter your Stadia Maps API key: ").strip()
    if not api_key_input:
        print("Error: An API key is required for this tile server.")
        sys.exit(1)
    api_key = api_key_input
    print("API key provided. Using authenticated access.")

# Display usage policy notice
print("\n⚠️ IMPORTANT: Tile Usage Policy Notice ⚠️")
print(f"- You're downloading tiles from {TILE_SERVERS[tile_server_choice]['name']}")

# Add source-specific notices
if "stamen" in tile_server_choice or "alidade" in tile_server_choice:
    print("- These tiles are hosted by Stadia Maps and require an API key")
elif tile_server_choice == "osm":
    print("- OpenStreetMap tile usage policy: https://operations.osmfoundation.org/policies/tiles/")

print("- Please ensure your usage complies with the tile server's policy")
print("- This script implements caching and rate limiting to reduce server load")
print(f"- Required attribution: {TILE_SERVERS[tile_server_choice]['attribution']}")
print("")

user_confirmation = input("Continue with download? (y/n): ")
if user_confirmation.lower() != 'y':
    print("Download cancelled.")
    sys.exit(0)

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
cached_tiles = 0

# Define rate limiting parameters - compliant with tile server policy
REQUEST_DELAY = 0.3  # seconds between requests to avoid overloading the server

start_time = time.time()
for i, tile in enumerate(tiles):
    # Create a cache filename for this tile that includes the tile server choice
    # Add API key info to cache filename if used (as a hash)
    api_key_suffix = f"_k{hashlib.md5(api_key.encode()).hexdigest()[:8]}" if api_key else ""
    cache_file = os.path.join(CACHE_DIR, f"{tile_server_choice}{api_key_suffix}_{tile.z}_{tile.x}_{tile.y}.{TILE_SERVERS[tile_server_choice]['format']}")
    
    # Progress update
    progress = (i + 1) / total_tiles * 100
    elapsed = time.time() - start_time
    tiles_per_sec = (i + 1) / elapsed if elapsed > 0 else 0
    
    print(f"Processing tile {i+1}/{total_tiles} ({progress:.1f}%) - {tiles_per_sec:.1f} tiles/sec", end="\r")
    
    # Check if tile is already cached
    if os.path.exists(cache_file):
        try:
            tile_img = Image.open(cache_file)
            px = (tile.x - x_offset) * tile_size
            py = (tile.y - y_offset) * tile_size
            image.paste(tile_img, (px, py))
            cached_tiles += 1
            continue
        except Exception as e:
            print(f"\nError reading cached tile {cache_file}: {str(e)}")
            # If cache read fails, continue to download
    
    # If not cached, download with rate limiting
    url = TILE_SERVERS[tile_server_choice]['url'].format(z=tile.z, x=tile.x, y=tile.y, r="")
        
    # Set up headers with User-Agent and API key if needed
    headers = {
        "User-Agent": TILE_SERVERS[tile_server_choice]['user_agent']
    }
    
    # Add Authorization header for Stadia Maps services
    if api_key and TILE_SERVERS[tile_server_choice]['requires_key']:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        # Rate limiting
        time.sleep(REQUEST_DELAY)
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Save to cache
            with open(cache_file, 'wb') as f:
                f.write(response.content)
            
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

print(f"\nTiles used: {successful_downloads + cached_tiles} total")
print(f"- {cached_tiles} from cache")
print(f"- {successful_downloads} newly downloaded")
print(f"- {failed_downloads} failed")

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

# Save cropped image with appropriate name based on tile service
api_key_indicator = "_auth" if api_key else ""
output_filename = f"{tile_server_choice}{api_key_indicator}_map_z{zoom}.{TILE_SERVERS[tile_server_choice]['format']}"
cropped_image.save(output_filename)
print(f"✅ Saved as {output_filename}")
print(f"Final image size: {cropped_image.width}x{cropped_image.height} pixels")
print(f"Attribution: {TILE_SERVERS[tile_server_choice]['attribution']}")
