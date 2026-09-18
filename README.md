# STL Transformer

A Blender addon for batch converting STL files to GLB and OBJ formats with automatic PBR material assignment. Supports URDF-based assembly to export complete models with correct part positioning.

![Blender](https://img.shields.io/badge/Blender-4.0%2B-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-yellow) ![License](https://img.shields.io/badge/License-MIT-green) ![Version](https://img.shields.io/badge/Version-2.0.0-orange)

## Features

### Individual File Conversion
- **Batch Processing** — Recursively scan directories and convert all STL files in one click
- **Dual Format Export** — Simultaneously export to GLB (glTF 2.0 Binary) and OBJ (Wavefront)
- **Directory Structure Preservation** — Maintains source folder hierarchy in output

### URDF Assembly (v2.0 New)
- **URDF Parsing** — Reads joint origins and link transforms from URDF XML
- **Kinematic Tree Traversal** — Accumulates transforms from root to each link for correct world positioning
- **Complete Model Export** — Assembles all STL parts into a single GLB/OBJ with proper spatial arrangement
- **Join Meshes Option** — Merge all parts into one mesh for OBJ export (single object output)
- **Works with SW2URDF output** — Compatible with SolidWorks URDF exporter format

### Shared Features
- **Automatic Color Schemes** — 5 built-in PBR material presets with smart part-type detection
- **Blender UI Integration** — Clean panel in the N-sidebar with mode switching

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

### Mode 1: Individual File Conversion

1. Open Blender, press **N** in the 3D viewport
2. Click the **STL Transformer** tab
3. Set **Mode** to **Individual Files**
4. Set **Input Directory** — folder containing STL files
5. Set **Output Directory** — where converted files will be saved
6. Check **Recursive** to scan subdirectories
7. Select export formats (GLB and/or OBJ)
8. Choose a color scheme
9. Click **Start Conversion**

### Mode 2: URDF Assembly

1. Set **Mode** to **URDF Assembly**
2. Set **URDF File** — path to your `.urdf` file
3. Set **Output Directory**
4. Select export formats
5. Choose a color scheme
6. (Optional) Check **Join Meshes** to merge all parts into one mesh for OBJ export
7. Click **Assemble & Export**

The addon will:
1. Parse the URDF to extract all link mesh paths and joint transforms
2. Build a kinematic tree from root link to each child link
3. Accumulate 4x4 transformation matrices (translation + RPY rotation)
4. Import each STL and position it at its correct world coordinate
5. Export the complete assembled model as GLB and/or OBJ

## Requirements

- Blender 4.0 or later (tested on Blender 5.1)
- No external Python dependencies required (uses Blender's built-in `xml.etree`)

## How It Works

### Individual Mode
1. Scans the input directory (recursively if enabled) for `.stl` files
2. For each STL file:
   - Clears the scene
   - Imports the STL mesh
   - Detects part type from filename (body/joint/metal/grip)
   - Applies PBR material based on selected color scheme
   - Exports to GLB and/or OBJ
3. Preserves the source directory structure in the output folder

### URDF Assembly Mode
1. Parses URDF XML to extract:
   - Link definitions (mesh filename, visual origin xyz/rpy)
   - Joint definitions (parent-child relationships, joint origin xyz/rpy)
2. Builds a parent-child map and finds root links
3. BFS traversal from root, accumulating 4x4 transform matrices:
   - `world[child] = world[parent] @ Translation(joint.xyz) @ RPY(joint.rpy) @ Translation(link.xyz) @ RPY(link.rpy)`
4. Imports each STL and sets `obj.matrix_world` to the computed transform
5. Exports all objects as a single assembled GLB/OBJ file

## Use Case: Robotic Hand Models

This addon was originally developed for converting robotic hand CAD models (STL from SolidWorks) into web-viewable formats. The color schemes are tuned for robotic/prosthetic hand presentations:

- Palm base → body color
- Finger proximal joints → joint color (metallic)
- Finger distal tips → body color
- Metacarpal connections → metal color (high metallic)
- Grip pads → grip color (high roughness, low metallic)

The URDF assembly mode was added to solve the problem of exporting a complete robotic hand as a single model, where all finger parts are correctly positioned according to the CAD-defined kinematic tree.

## File Structure

```
STL_Transformer/
├── stl_transformer.py    # Main addon script (v2.0)
├── README.md             # This file
├── LICENSE               # MIT License
└── .gitignore
```

## Changelog

### v2.0.0
- Added URDF Assembly mode with kinematic tree parsing
- Added URDF file browser
- Added Join Meshes option for OBJ export
- Added mode switcher (Individual / URDF Assembly)
- Updated UI to adapt based on selected mode

### v1.0.0
- Initial release
- Batch STL to GLB + OBJ conversion
- 5 color schemes with automatic part-type detection
- Recursive directory scanning
- Overwrite control

## License

MIT License — feel free to use this in your projects.
