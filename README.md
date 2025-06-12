<h1 align="center">
  <a href="#"><img src="https://raw.githubusercontent.com/Sryml/Amagate/refs/heads/main/preview/logo.png" width="150" height="150" alt="banner" /></a>
</h1>
  <p align="center">English | <a href="https://github.com/Sryml/Amagate/blob/main/docs/zh-HANS/README.md">简体中文</a></p>

<div align="center">
  <a href="https://discord.gg/ZWdfcx2KW2" target="_blank"><img alt="discord"
src="https://img.shields.io/badge/Discord-gray?style=flat&logo=discord"></a>
  <a href="https://www.moddb.com/mods/amagate" target="_blank"><img alt="moddb"
src="https://img.shields.io/badge/ModDB-gray?style=flat&logo=data:image/png;base64,UklGRuwCAABXRUJQVlA4WAoAAAAQAAAAEwAAFAAAVlA4THgCAAAvEwAFEE2ISVOM3ovof8BkEaGgbRvGGn+cfyD6H+0zAHKrbVvz5tInO8zMzExVTgZIncoDhEdwFYYFsgBvQT0zlWbmnyS94Rmk2Na2bMu57ud3d//T3wR3zyRvFlmkfxjYOEgMwZp7I7q7w6vPFWxi245ysleISZ0KGThACCJwsxlATHpmAk7fS6vStZjOQiADhEAIVAECVcgQUkvfMOtCvQuzSaskASqE5N2KrGy19ShaRSaElBKygC4d8z3GMGZ5EgikpOjT9dva1sJOP0pzh61rNAoJVSgthWV5THu2x5JLoAqsGjJ81bErfpw0vsnxc6Z6vFuzPqnVIAsl2vKsWyZCWIb2Ue9vuHLYyac6zhqYdeG+szedOWHqtKU/tGVtkhCoSQYISdJIljzSsSx++/JEecuGZNGSEzPu7bRxXDRYhQg1CWmzFGphoLQttHcy4r5VheIM3Zb91dUpH6YFIWF1JNTCOOpY3G/IijcO45RshZr/XmyT/zX1jk4QAlMYxozMlaXZoj/K4y5f0lMAqHB31tPTlvaZ6ZQlwKAHkzL7l3lSSVGYverVXy8LpY1J8c2TA2xRb9V6EACYFI3MCgDxhxErkkxmYVavxSab7jHThwGACoQAgBbklqQUSZYpRCMaAAAK8FedygDzwNQUFBT+UPqLTBIBcghh/lNS+h8mSQIgpEzhL0SN/QFsTgNApxJqSioAACrwp4o5Ny/pDND3zL41o6dosD80GAMABbulWzov2/nBrYO+HmKR/wgACNrKtICATCJxn+9sZ5I/BGCgA6qfzQQJY0A0QD8d/KVGAAjR8qV5t3l7WoyEwd8ZECDM69/8DlBTQUlOAAAAOEJJTQPtAAAAAAAQAEgAAAABAAIASAAAAAEAAjhCSU0EKAAAAAAADAAAAAI/8AAAAAAAADhCSU0EQwAAAAAADVBiZVcBEAAFAQAAAAAA"></a>
  <a href="https://www.youtube.com/playlist?list=PL9zGzVy6W7ukUfFvCNjOMfpLU9ceeYYBC" target="_blank"><img alt="youtube"
src="https://img.shields.io/badge/YouTube-gray?style=flat&logo=youtube"></a>

  <!-- <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/sryml/Amagate?style=flat"> -->

<p>
  <a href="https://github.com/Sryml/Amagate/releases" target="_blank"><img alt="GitHub release (latest by date)"
src="https://img.shields.io/github/v/release/sryml/Amagate?style=flat"></a>
  <a href="https://deepwiki.com/Sryml/Amagate"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

</div>

# Amagate

Amagate is a Blender extension that transforms Blender into a specialized environment for building 3D maps, managing assets, and exporting to Blade Engine's proprietary format.  
The ultimate goal is to seamlessly interact with Blade and become an all-in-one development tool.

Features already implemented and planned include: map creation and export, real-time interaction with the game, model export, animation export, MMP file visual editing, and more...

The project has ambitious goals and a long road ahead.  
I hope this tool can help those interested step into the gateway of the 3D world. This is Amagate.

## 🔗 Amagate Client

https://github.com/Sryml/AmagateClient/releases

## 📃 Documentation

## 📖 Installation

From the menu bar, select `Edit -> Preferences -> Get Extensions`,  
then click `Install from Disk` in the top-right corner and choose the downloaded extension zip file (or search for Amagate directly for online installation).

Upon first installation, the required Python packages (approximately 41MB) will be automatically installed.

## 🌠 Features

- [Level Editor (L3D)](#level-editor-l3d)
- Blade coordinate conversion
- Cubemap conversion

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

### 🎯 Marker Objects

- `Player` indicates the player's position when exporting the map

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
  - Convert to sector
  - Separate convex parts
  - Connect sectors
  - Disconnect sectors
  - Set selected sector as default
  - Compile map
- Server
  - Load any level
  - Reload current level
  - Align camera to client
  - Real-time Blender-to-client camera synchronization
  - Move client player to camera position
- Others
  - Map compilation only compiles visible convex sectors

See [Documentation.md](https://github.com/Sryml/Amagate/blob/main/docs/en-US/Documentation.md) for details

## 📃 Change log

See [ChangeLog.md](https://github.com/Sryml/Amagate/blob/main/docs/en-US/ChangeLog.md)

## 💡 Pooling Ideas

The current workflow of Amagate is not yet perfect, and some features of the Blade engine have not been implemented, such as the particle system, physics system, halo effects, animation transitions, etc.  
If anyone can provide suggestions for a more efficient map-building workflow or ideas for simulating Blade functions in Blender, I would be very grateful.

Any suggestions or questions are welcome. Feel free to submit [Issues](https://github.com/Sryml/Amagate/issues) on GitHub or discuss them on [Discord](https://discord.gg/ZWdfcx2KW2).

## 💗 References and Thanks

- Rebel Act Studios for creating an excellent game
- SNEG, Fire Falcom, General Arcade for re-releasing the game
- The Blender Foundation for developing excellent software
- LLM DeepSeek for providing much assistance
- The reforged textures are from sfb's [Blade of Darkness Reforged](https://www.moddb.com/mods/blade-of-darkness-reforged)

## License

Amagate is licensed under [GPLv3 License](https://github.com/Sryml/Amagate/blob/main/LICENSE).
