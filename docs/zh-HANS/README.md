<h1 align="center">
  <a href="#"><img src="https://raw.githubusercontent.com/Sryml/Amagate/refs/heads/main/preview/logo.png" width="150" height="150" alt="banner" /></a>
</h1>
  <p align="center"><a href="https://github.com/Sryml/Amagate/blob/main/README.md">English</a> | 简体中文</p>

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

Amagate 是一个 Blender 扩展，可以将 Blender 转变为一个专门用于构建 3D 地图、管理资产并导出到专有的 Blade 引擎格式的环境。  
最终目标是与 Blade 无缝交互并成为一站式的开发工具。

已实现和计划实现的功能包含：地图创建和导出，与游戏实时交互，模型导出，动画导出，MMP 文件可视化编辑等。。。

该项目的目标很大，任重而道远。  
我希望这个工具能够帮助那些有兴趣的人们踏入 3D 世界的大门，这就是阿门。

<!-- ## Introduction -->

## 🔗 Amagate 客户端

https://github.com/Sryml/AmagateClient/releases

## 📃 文档

## 📖 安装

Blender 版本：4.3.0 或以上

从菜单栏中选择`编辑 -> 偏好设置 -> 获取扩展`，  
然后点击右上角`从磁盘安装`并选择下载好的扩展 zip 文件。

初次安装会自动安装所需的 Python 包，大约 41MB。

## 🌠 功能

- [关卡编辑器 (L3D)](#关卡编辑器-l3d)
- Blade 坐标转换
- 立方体贴图转换

## 关卡编辑器 (L3D)

### ✨ 优势

- 使用自定义二进制协议与游戏客户端进行通信（例如同步摄像机移动，加载地图等）
- 可自由编辑的面（例如制作拱形的墙壁）
- 移动扇区不会像 LED 那样丢失斜坡状态
- 可在扇区任意平面上分割任意形状的子纹理（LED 只能在墙壁上垂直分割）
- 纹理下拉列表有筛选和预览功能
- 单独设置纹理的 X/Y 轴缩放
- 实时切换天空纹理
- 实时的 3D 预览与编辑

### 🎯 标记对象

- `Player`表示导出地图时的玩家位置

### HUD 信息

1. 选中的扇区
2. 是否同胚于二维球面  
   如果选中的扇区中存在混合类型，则显示为`*`
3. 是否为凸多面体  
   如果选中的扇区中存在混合类型，则显示为`*`

### 🌟 L3D 功能

- 场景
  - 大气管理
  - 外部光管理
  - 纹理管理
  - 天空纹理的设置与下载
  - 默认扇区属性设置
  - 视锥裁剪
- 扇区
  - 陡峭检查与设置
  - 大气分配
  - 预设纹理分配
  - 单独设置纹理的 X/Y 轴缩放
  - 外部光分配
  - 环境光设置
  - 平面光设置
  - 灯泡光管理
  - 组分配
  -
  - 自动有限融并
  - 复制处理
  - 分离处理
  - 合并处理
  - 删除处理
- 工具
  - 多线段路径创建
  - 虚拟扇区创建与导出
  - 转换为扇区
  - 分离凸部分
  - 连接扇区
  - 断开连接扇区
  - 将选中扇区设为默认
  - 编译地图
  - 导入地图
- 服务器
  - 加载任意关卡
  - 重载当前关卡
  - 对齐摄像机到客户端
  - 实时同步 blender 摄像机到客户端
  - 移动客户端玩家到摄像机位置
- 其它
  - 编译地图只会编译可见的凸扇区

更多参阅 [Documentation.md](https://github.com/Sryml/Amagate/blob/main/docs/zh-HANS/Documentation.md)

## 📃 变更日志

参阅 [ChangeLog.md](https://github.com/Sryml/Amagate/blob/main/docs/zh-HANS/ChangeLog.md)

## 💡 集思广益

目前 Amagate 的工作流尚不完善，还有一些 Blade 引擎的功能没有实现，例如粒子系统，物理系统，光环效果，动画过渡等。  
如果有人可以提供更高效的地图建造工作流或者在 Blender 中模拟 Blade 功能的建议，我将非常感谢。

任何建议或问题，欢迎在 GitHub 上提交 [Issues](https://github.com/Sryml/Amagate/issues) 或在 [Discord](https://discord.gg/ZWdfcx2KW2) 上讨论。

## 💗 参考与致谢

- Rebel Act Studios 制作了出色的游戏
- SNEG, Fire Falcom, General Arcade 重新发行了游戏
- Blender 基金会开发了出色的软件
- LLM DeepSeek 提供了许多帮助
- 重铸纹理来自 sfb 的 [Blade of Darkness Reforged](https://www.moddb.com/mods/blade-of-darkness-reforged)
- 感谢 Ubaid 的测试

## License

Amagate is licensed under [GPLv3 License](https://github.com/Sryml/Amagate/blob/main/LICENSE).
