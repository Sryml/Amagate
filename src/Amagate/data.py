from collections import Counter

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    IntVectorProperty,
    PointerProperty,
    StringProperty,
)

atmo_duplicate_name_ids = []


# 自定义的列表项模板
class AMAGATE_UI_UL_AtmosphereList(bpy.types.UIList):
    # bl_idname = "AMAGATE_UI_UL_AtmosphereList"

    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        atmosphere = item  # 获取大气数据

        row = layout.row()
        split = row.split(factor=0.2)

        col = split.column()
        col.enabled = False
        col.label(text=f"ID: {atmosphere.id}")

        if atmosphere.id in atmo_duplicate_name_ids:
            split.alert = True

        split.prop(atmosphere, "name", text="", emboss=False)
        split.prop(atmosphere, "color", text="")


class AtmosphereProperty(bpy.types.PropertyGroup):
    name: StringProperty(name="Atmosphere Name", default="", update=lambda self, context: self.check_duplicate_name(context))  # type: ignore
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=4,  # RGBA
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0, 0.02),
    )  # type: ignore
    id: IntProperty(name="ID", default=1)  # type: ignore
    # intensity: FloatProperty(name="Intensity", default=0.02)  # type: ignore

    @staticmethod
    def check_duplicate_name(context):
        global atmo_duplicate_name_ids
        scene_data = context.scene.amagate_data  # type: ignore
        items = scene_data.atmospheres
        if not items:
            return

        name_counter = Counter(item.name for item in items)
        # 检查是否有重复名称
        duplicate_name_ids = [item.id for item in items if name_counter[item.name] > 1]
        atmo_duplicate_name_ids = duplicate_name_ids
        # print(f"Duplicate Name IDs: {duplicate_name_ids}")
        if duplicate_name_ids:
            bpy.context.window_manager.popup_menu(
                lambda self, context: self.layout.label(text="Duplicate Name"),
                title="Error",
                icon="ERROR",
            )


class SceneProperty(bpy.types.PropertyGroup):
    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore
    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(default=0)  # type: ignore


class SectorProperty(bpy.types.PropertyGroup):
    atom_id: IntProperty(name="Atmosphere", description="", default=0)  # type: ignore
    group: IntProperty(
        name="Group",
        description="",
        default=0,  # 默认值为0
    )  # type: ignore
    comment: StringProperty(name="Comment", description="", default="")  # type: ignore


##############################
##############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and any(issubclass(cls, parent) for parent in class_tuple)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.amagate_data = PointerProperty(type=SectorProperty)  # type: ignore
    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty)  # type: ignore


def unregister():
    del bpy.types.Object.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
