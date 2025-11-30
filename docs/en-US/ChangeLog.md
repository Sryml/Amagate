# Amagate ChangeLog

## 1.4.3

- Adapted for Blender 5
- Added \*.PAK unpack/pack functionality
- Fixed built-in textures were not converted to relative paths when saving maps
- Fixed external libraries wouldn't reload after updating the library paths

## 1.4.2

- Model packages are now manually imported for lightweight purposes
- Added switch wound textures functionality
- Optimized the logic for setting sector textures
- Material names are now used as texture names for .BOD exports
-
- Fixed callback execution errors in L3D edit mode
- Fixed Spike and Trail issues in .BOD import/export
- Fixed geometric center issues in .BOD import/export
- Fixed missing skeletons and anchors when duplicating entities
- Fixed an error when creating a new map without a model package

## 1.4.0

- Adapted for Blender 4.5.1
- Added entity placement functionality
- Added entity export functionality
- Added entity animation set functionality
- Added entity property editing functionality
- Added \*.BOD import/export and convenience features
- Added \*.BMV import/export functionality
- Added \*.CAM import/export functionality
- Added mirror animation functionality
- Added reset roll angle functionality
- Added world baking functionality
- Added select sectors by group functionality
- Added select concave sectors functionality
- Added toggle for client HUD display
- Added spatial transformation for orientation, direction, and camera
- Added visibility buttons for atmosphere and external light panels
-
- Fixed Python package installation issues
- Fixed L3D scene node loading errors
- Fixed relative path issues when setting sky textures
- Fixed texture icon preview issues

## 1.2.0

- Added map import functionality
- Added visible-only sector compilation option
- Added volume toggle
- Added frustum culling toggle
- Added display connected faces toggle
- Added the ability to select connected sectors
- Added face attribute copy/paste functionality
- Copying sectors now preserves connections and bulb lights
- Added undo functionality for adding/removing bulb lights
- Automatically desubdivide after connecting sectors
-
- Optimized sector connection error handling
- Sector conversion can now fix sectors with duplicate IDs
- Check for runtime files before loading the current level
- Adjusted the progress bar behavior when installing Python packages
- Face attribute texture UI no longer shares presets with sector floor textures
- Adjusted default scene properties
- Removed inefficient material volumes and replaced them with world volume for fog simulation
- Moving the active camera now automatically switches the sector's atmosphere and external lighting
-
- Fixed sector connection issues
- Fixed BW compilation not desubdividing faces
- Fixed BW compilation handling tangent issues for single-connected faces
- Fixed BW compilation handling multi-connected faces
- Fixed BW compilation handling sub-textures
- Fixed bulb light rendering issues
- Fixed incorrect texture mapping
- Fixed file browser crash issue
- Fixed callback functions not registering correctly when launching Blender via .blend files

## 1.0.0

- Level Editor (L3D)
- Blade coordinate conversion
- Cubemap conversion
