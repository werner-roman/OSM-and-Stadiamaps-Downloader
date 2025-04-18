# OSM Map Downloader

A Python script for downloading and stitching together OpenStreetMap tiles for a specific geographic region (Panel 18).

## Features

- Downloads map tiles from OpenStreetMap based on geographical coordinates
- Stitches tiles together into a seamless map image
- Crops the image to exact geographical boundaries
- Displays progress information during download

## Requirements

- Python 3.6+
- Required packages:
  - mercantile
  - requests
  - Pillow (PIL)

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install mercantile requests Pillow