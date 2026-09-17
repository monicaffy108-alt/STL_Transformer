# STL Transformer

A Blender addon for batch converting STL files to GLB and OBJ formats with automatic PBR material assignment.

![Blender](https://img.shields.io/badge/Blender-4.0%2B-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-yellow) ![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Batch Processing** — Recursively scan directories and convert all STL files in one click
- **Dual Format Export** — Simultaneously export to GLB (glTF 2.0 Binary) and OBJ (Wavefront)
- **Automatic Color Schemes** — 5 built-in PBR material presets with smart part-type detection
- **Directory Structure Preservation** — Maintains source folder hierarchy in output
- **Blender UI Integration** — Clean panel in the N-sidebar for easy access

## Color Schemes

| Scheme | Description | Use Case |
|--------|-------------|----------|
| None | No material applied | Raw geometry export |
| Light Blue | Blue body + dark metal joints | Consumer robotics |
| White | White body + dark metal joints | Medical/clean design |
| Beige | Warm beige body + dark joints | Prosthetics |
| Robotic Gray | Dark metallic style | Industrial robotics |

The addon automatically detects part types from filenames (body, joint, metal, grip) and applies appropriate roughness and metallic values for each.

## Installation

1. Download `stl_transformer.py`
2. Open Blender > **Edit > Preferences > Add-ons**
3. Click **Install...** (top-right dropdown)
4. Select `stl_transformer.py`
5. Enable the checkbox next to **STL Transformer**

## Usage

1. Open Blender (any project)
2. Press **N** in the 3D viewport to open the sidebar
3. Click the **STL Transformer** tab
4. Set **Input Directory** — folder containing STL files
5. Set **Output Directory** — where converted files will be saved
6. Check **Recursive** to scan subdirectories
7. Select export formats (GLB and/or OBJ)
8. Choose a color scheme
9. Click **Start Conversion**

## Requirements

- Blender 4.0 or later (tested on Blender 5.1)
- No external Python dependencies required

## File Structure

```
STL_Transformer/
├── stl_transformer.py    # Main addon script
├── README.md             # This file
├── LICENSE               # MIT License
└── .gitignore
```

## How It Works

1. Scans the input directory (recursively if enabled) for `.stl` files
2. For each STL file:
   - Clears the scene
   - Imports the STL mesh
   - Detects part type from filename (body/joint/metal/grip)
   - Applies PBR material based on selected color scheme
   - Exports to GLB and/or OBJ
3. Preserves the source directory structure in the output folder
4. Reports success/failure count upon completion

## Use Case: Robotic Hand Models

This addon was originally developed for converting robotic hand CAD models (STL from SolidWorks) into web-viewable formats. The color schemes are tuned for robotic/prosthetic hand presentations:

- Palm base → body color
- Finger proximal joints → joint color (metallic)
- Finger distal tips → body color
- Metacarpal connections → metal color (high metallic)
- Grip pads → grip color (high roughness, low metallic)

## License

MIT License — feel free to use this in your projects.
