# Amagate ChangeLog

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
