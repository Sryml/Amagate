import sys
import os
from typing import Any

import bpy
from bpy.app.translations import pgettext
from bpy.props import PointerProperty

from . import data

"""
import ctypes
import time

# 定义 Windows API 中的 keybd_event 函数
def simulate_keypress():
    # 0x1B 是 Esc 键的虚拟键码
    ESC_KEY_CODE = 0x1B

    # 定义 keybd_event 参数
    # 需要按下 ESC 键
    ctypes.windll.user32.keybd_event(ESC_KEY_CODE, 0, 0, 0)
    time.sleep(0.01)  # 按键按下后等待一段时间

    # 释放 ESC 键
    ctypes.windll.user32.keybd_event(ESC_KEY_CODE, 0, 2, 0)
"""


# 场景面板 -> 大气面板
class OT_Scene_Atmo_Add(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_add"
    bl_label = "Add Atmosphere"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore

        # 已经使用的ID
        used_ids = set(a.id for a in scene_data.atmospheres)

        new_atmo = scene_data.atmospheres.add()
        id_ = 1
        while id_ in used_ids:
            id_ += 1
        new_atmo.id = id_

        # 给大气命名
        name = f"atmo{id_}"
        names = set(a.name for a in scene_data.atmospheres)
        while name in names:
            id_ += 1
            name = f"atmo{id_}"
        new_atmo.name = name

        scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        return {"FINISHED"}


class OT_Scene_Atmo_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_remove"
    bl_label = "Remove Atmosphere"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        active_atmo = scene_data.active_atmosphere
        if scene_data.atmospheres[active_atmo].id == scene_data.defaults.atmo_id:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Cannot remove default atmosphere')}",
            )
            return {"CANCELLED"}

        scene_data.atmospheres.remove(active_atmo)

        if active_atmo >= len(scene_data.atmospheres):
            scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        return {"FINISHED"}

    def invoke(self, context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Scene_Atmo_Default(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_default"
    bl_label = "Set as default atmosphere"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        scene_data.defaults.atmo_id = scene_data.atmospheres[
            scene_data.active_atmosphere
        ].id
        return {"FINISHED"}


# 纹理面板
class OT_Scene_Texture_Add(bpy.types.Operator):
    bl_idname = "amagate.scene_texture_add"
    bl_label = "Add Texture"
    bl_description = "Hold shift to enable overlay"
    bl_options = {"INTERNAL"}

    # 过滤文件
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_image: bpy.props.BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    # filter_glob: bpy.props.StringProperty(default="*.jpg;*.png;*.jpeg;*.bmp;*.tga", options={"HIDDEN"})  # type: ignore

    # 相对路径
    relative_path: bpy.props.BoolProperty(name="Relative Path", default=True)  # type: ignore
    # 覆盖模式
    override: bpy.props.BoolProperty(name="Override Mode", default=False)  # type: ignore
    # filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: bpy.props.StringProperty()  # type: ignore
    directory: bpy.props.StringProperty()  # type: ignore
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    def get_id(self):
        # 已经使用的ID
        used_ids = set(i.amagate_data.id for i in bpy.data.images)  # type: ignore
        id_ = 1
        while id_ in used_ids:
            id_ += 1
        return id_

    def load_image(self, context, filepath, name=""):
        scene_data = context.scene.amagate_data  # type: ignore
        img = bpy.data.images.load(filepath)
        img_data = img.amagate_data  # type: ignore
        if name:
            img.name = name

        img_data.id = self.get_id()

    def execute(self, context):
        curr_dir = bpy.path.abspath("//")
        # 相同驱动器
        same_drive = (
            os.path.splitdrive(self.directory)[0] == os.path.splitdrive(curr_dir)[0]
        )
        files = [
            f.name
            for f in self.files
            if f.name and os.path.exists(os.path.join(self.directory, f.name))
        ]
        if not files:
            files = [
                f
                for f in os.listdir(self.directory)
                if f.endswith((".jpg", ".png", ".jpeg", ".bmp", ".tga"))
            ]

        for file in files:
            name = os.path.splitext(file)[0]
            filepath = os.path.join(self.directory, file)
            if same_drive and self.relative_path:
                filepath = f"//{os.path.relpath(filepath, curr_dir)}"

            img = bpy.data.images.get(name)
            if img:
                if self.override:
                    img.filepath = filepath
                    img.reload()
                    if not img.amagate_data.id:  # type: ignore
                        img.amagate_data.id = self.get_id()  # type: ignore
            else:
                self.load_image(context, filepath, name)
        return {"FINISHED"}

    def invoke(self, context, event):
        self.override = event.shift
        # 这里通过文件选择器来选择文件或文件夹
        context.window_manager.fileselect_add(self)  # type: ignore
        return {"RUNNING_MODAL"}


class OT_Scene_Texture_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_texture_remove"
    bl_label = "Remove Texture"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        print(f"{self.__class__.bl_idname}")
        return {"FINISHED"}

    def invoke(self, context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Scene_Texture_Reload(bpy.types.Operator):
    bl_idname = "amagate.scene_texture_reload"
    bl_label = "Reload Texture"
    bl_description = "Hold shift to reload all texture"
    bl_options = {"INTERNAL"}

    reload_all: bpy.props.BoolProperty(name="Reload All", default=False)  # type: ignore

    def execute(self, context):
        print(f"{self.__class__.bl_idname}")
        return {"FINISHED"}

    def invoke(self, context, event):
        self.reload_all = event.shift
        self.execute(context)
        return {"FINISHED"}


class OT_Scene_Texture_Package(bpy.types.Operator):
    bl_idname = "amagate.scene_texture_package"
    bl_label = "Package Texture"
    bl_description = "Hold shift to pack all textures"
    bl_options = {"INTERNAL"}

    # 打包所有
    pack_all: bpy.props.BoolProperty(name="Pack All", default=False)  # type: ignore

    def execute(self, context):
        print(f"{self.__class__.bl_idname}")
        return {"FINISHED"}

    def invoke(self, context, event):
        self.pack_all = event.shift
        self.execute(context)
        return {"FINISHED"}


# 场景面板 -> 默认属性面板
class OT_Scene_Default_Atmo(bpy.types.Operator):
    bl_idname = "amagate.scene_default_atmo"
    bl_label = "Select Atmosphere"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=data.Scene_Default_Atmo)  # type: ignore

    def draw(self, context):
        self.prop.active = True

        scene_data = context.scene.amagate_data  # type: ignore
        layout = self.layout
        col = layout.column()

        col.template_list(
            "AMAGATE_UI_UL_AtmoList",
            "atmosphere_list",
            scene_data,
            "atmospheres",
            self.prop,
            "index",
            maxrows=14,
        )

    def execute(self, context):
        # print(f"{self.__class__.__name__}.execute")
        # self.report({"INFO"}, "execute")
        # simulate_keypress()
        # bpy.context.window.cursor_warp(10,10)

        # move_back = lambda: bpy.context.window.cursor_warp(self.mouse[0], self.mouse[1])
        # bpy.app.timers.register(move_back, first_interval=0.01)
        return {"FINISHED"}

    def invoke(self, context, event):
        # self.mouse = event.mouse_x, event.mouse_y
        # print(self.mouse)
        return context.window_manager.invoke_popup(self, width=200)  # type: ignore


# 场景面板 -> 新建场景
class OT_NewScene(bpy.types.Operator):
    bl_idname = "amagate.newscene"
    bl_label = "New Scene"
    bl_description = "Create a new Blade Scene"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        name = "Blade Scene"
        num = 0
        names = set(s.name for s in bpy.data.scenes)
        while name in names:
            num += 1
            name = f"Blade Scene {num}"

        bpy.ops.scene.new()
        scene = context.scene  # type: ignore
        scene.name = name
        scene.amagate_data.is_blade = True  # type: ignore

        scene.amagate_data.set_defaults()  # type: ignore

        bpy.ops.amagate.scene_atmo_add()  # type: ignore

        # TODO 添加默认摄像机 添加默认扇区 划分界面布局 调整视角
        return {"FINISHED"}


# 重载插件
class OT_ReloadAddon(bpy.types.Operator):
    bl_idname = "amagate.reloadaddon"
    bl_label = ""
    bl_description = "Reload Addon"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        base_package = sys.modules[__package__]  # type: ignore

        bpy.ops.preferences.addon_disable(module=__package__)  # type: ignore
        # base_package.unregister()
        bpy.ops.preferences.addon_enable(module=__package__)  # type: ignore
        # base_package.register(reload=True)
        print("插件已热更新！")
        return {"FINISHED"}


#  -> 导出地图
class OT_ExportMap(bpy.types.Operator):
    bl_idname = "amagate.exportmap"
    bl_label = "Export Map"
    bl_description = "Export Blade Map"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        # self.report({'WARNING'}, "Export Failed")
        self.report({"INFO"}, "Export Success")
        return {"FINISHED"}


classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and issubclass(cls, bpy.types.Operator)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
