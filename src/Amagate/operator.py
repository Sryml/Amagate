import sys

import bpy
from bpy.app.translations import pgettext

from . import data


# 定义添加和删除大气的操作
class OT_AddAtmosphere(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_add"
    bl_label = "Add Atmosphere"

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


class OT_RemoveAtmosphere(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_remove"
    bl_label = "Remove Atmosphere"

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        scene_data.atmospheres.remove(scene_data.active_atmosphere)
        if scene_data.active_atmosphere >= len(scene_data.atmospheres):
            scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        data.AtmosphereProperty.check_duplicate_name(context)
        return {"FINISHED"}


################################


class OT_NewScene(bpy.types.Operator):
    bl_idname = "amagate.newscene"
    bl_label = "New Scene"
    bl_description = "Create a new Blade Scene"

    def execute(self, context):
        name = "Blade Scene"
        num = 0
        names = set(s.name for s in bpy.data.scenes)
        while name in names:
            num += 1
            name = f"Blade Scene {num}"

        bpy.ops.scene.new()
        scene = context.scene
        scene.name = name
        scene.amagate_data.is_blade = True  # type: ignore
        bpy.ops.amagate.scene_atmo_add()  # type: ignore
        return {"FINISHED"}


# 重载插件
class OT_ReloadAddon(bpy.types.Operator):
    bl_idname = "amagate.reloadaddon"
    bl_label = ""
    bl_description = "Reload Addon"

    def execute(self, context):
        base_package = sys.modules[__package__]  # type: ignore

        # bpy.ops.preferences.addon_disable(module=__package__)  # type: ignore
        base_package.unregister()
        # bpy.ops.preferences.addon_enable(module=__package__)  # type: ignore
        base_package.register(reload=True)
        print("插件已热更新！")
        return {"FINISHED"}


class OT_ExportMap(bpy.types.Operator):
    bl_idname = "amagate.exportmap"
    bl_label = "Export Map"
    bl_description = "Export Blade Map"

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
