import sys
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

        new_atmosphere = scene_data.atmospheres.add()
        id_ = 1
        while id_ in used_ids:
            id_ += 1
        new_atmosphere.id = id_

        # 给大气命名
        name = f"atmo{id_}"
        names = set(a.name for a in scene_data.atmospheres)
        while name in names:
            id_ += 1
            name = f"atmo{id_}"
        new_atmosphere.name = name

        scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        return {"FINISHED"}


class OT_Scene_Atmo_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_remove"
    bl_label = "Remove Atmosphere"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        if (
            scene_data.atmospheres[scene_data.active_atmosphere].id
            == scene_data.defaults.atmo_id
        ):
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Cannot remove default atmosphere')}",
            )
            return {"CANCELLED"}

        scene_data.atmospheres.remove(scene_data.active_atmosphere)
        if scene_data.active_atmosphere >= len(scene_data.atmospheres):
            scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        data.AtmosphereProperty.check_duplicate_name(context)
        return {"FINISHED"}


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
        print(f"{self.__class__.__name__}.execute")
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

        # bpy.ops.preferences.addon_disable(module=__package__)  # type: ignore
        base_package.unregister()
        # bpy.ops.preferences.addon_enable(module=__package__)  # type: ignore
        base_package.register(reload=True)
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
