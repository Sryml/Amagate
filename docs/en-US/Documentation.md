# Amagate Documentation

## 📖 Installation

Blender version: 4.3.0 or above

From the menu bar, select `Edit -> Preferences -> Get Extensions`,  
then click `Install from Disk` in the top-right corner and choose the downloaded extension zip file.

Entity creation and animation setup require a model pack to be used. After [downloading](https://github.com/Sryml/Amagate/releases/tag/1.4.0), import it in the model pack panel.  
Upon first installation, the required Python packages (approximately 41MB) will be automatically installed.

## 🌠 Features

- [Level Editor (L3D)](#level-editor-l3d)
- [L3D Entity Panel](#l3d-entity-panel)
- Entity Placement and Export
- Animation Settings
- Mirror Animation
- \*.BOD Import/Export and convenience features
- \*.BMV Import/Export
- \*.CAM Import/Export
- Blade Space Conversion
- Cubemap conversion
- PAK conversion

## Level Editor (L3D)

### ✨ Advantages

- Uses a custom binary protocol to communicate with the game client (e.g., synchronizing camera movement, loading maps, etc.)
- Freely editable surfaces (e.g., creating arched walls)
- Moving sectors does not lose slope states like in LED
- Can divide sub-textures of any shape on any plane of a sector (LED can only be divided vertically on walls)
- Texture dropdown with filtering and preview functionality
- Individual texture scaling for X/Y axes
- Real-time sky texture switching
- Real-time 3D preview and editing

### HUD Information

1. Selected sector
2. Whether it is homeomorphic to a 2D sphere  
   If mixed types exist in the selected sector, it displays as `*`
3. Whether it is a convex polyhedron  
   If mixed types exist in the selected sector, it displays as `*`

### 🌟 L3D Features

- Scene
  - Atmosphere management
  - External light management
  - Texture management
  - Sky texture settings and downloading
  - Default sector attribute settings
  - Frustum Culling
- Sector
  - Steepness check and settings
  - Atmosphere assignment
  - Preset texture assignment
  - Individual texture scaling for X/Y axes
  - External light assignment
  - Ambient light settings
  - Flat light settings
  - Bulb light management
  - Group assignment
  -
  - Automatic limited dissolve
  - Copy handling
  - Split handling
  - Merge handling
  - Delete handling
- Tools
  - Polyline path creation
  - Ghost sector creation and export
  - Select connected sectors
  - Select concave sectors
  - Select sectors by group
  - Convert to sector
  - Separate convex parts
  - Connect sectors
  - Disconnect sectors
  - Set selected sector as default
  - Compile map
  - Import map
- Server
  - Load any level
  - Reload current level
  - Align camera to client
  - Real-time Blender-to-client camera synchronization
  - Move client player to camera position
  - Toggle client HUD display

### ⚠️ Notes

- **Volumetric Fog**  
  Black fog cannot display lights
- **Concave Polyhedrons**  
  Do not create complex concave sectors at once; instead, create multiple convex sectors and then connect them
- **Non-uniform scaling issues**  
  If sector connection or other sector operations fail, try applying scale transformation `(Ctrl+A -> Scale)`
- **Light simulation deviation**  
  Occurs in bulb light ranges or multi-light brightness/color
- **Sky textures**  
  Sky texture must occupy a sector plane exclusively
- **Preventing automatic dissolve**  
  To set different positions/scaling/angles for the same texture on a flat surface, mark the edges as sharp
- **Copy handling**  
  Use `Shift+D/Alt+D` for sector duplication instead of `Ctrl+C`
- **Sector connection**  
  If sector connection fails, try repositioning to ensure surfaces are tightly aligned
- **Separating convex parts**  
  Complex concave polyhedrons cannot be separated automatically and must be separated manually.  
  Perform `Split Concave Faces` first before separation, otherwise the resulting sectors may contain concave polyhedrons.  
  Cross-surface splitting is unreliable; recommend disabling auto-connect and manually adjusting split sectors before perform the connection

## L3D Entity Panel

### 🌟 Features

- Entity preview list (searchable)
- Create entity
- Append/open selected entity file
- Set as prefab
- Remove prefab
-
- Name editing and reset
- Object type setting
- Character hiding settings
- Character equipment inventory management
- Character item inventory management
- Settable entity properties
  - Kind
  - Alpha
  - SelfIlum
  - Static
  - CastShadows
  - Character skin
  - Life
  - Level
  - Angle
  - SetOnFloor
  - Freeze
  - Blind
  - Deaf
  - FiresIntensity
  - Intensity
  - Color
  - Flick
  - Visible
-
- Burnable setting
- Breakable setting
- Internal item management for breakable containers
- Torch Usable setting

## 📝 Todo

- Sector Prefabs (doors, windows, houses, stairs, etc.)
