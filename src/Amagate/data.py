import os
from typing import Any

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

############################
atmo_duplicate_name_ids = []
ICONS: Any = None
############################


# 自定义的列表项模板
class AMAGATE_UI_UL_AtmosphereList(bpy.types.UIList):
    # bl_idname = "AMAGATE_UI_UL_AtmosphereList"

    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        scene_data = context.scene.amagate_data  # type: ignore
        atmosphere = item  # 获取大气数据

        row = layout.row(align=True)
        row.alignment = "LEFT"
        # split = row.split(factor=0.2)
        # split = row

        # col = split.column()
        # col.enabled = False
        # col.label(text=f"ID: {atmosphere.id}")
        icon = (
            ICONS["star"].icon_id
            if atmosphere.id == scene_data.get_default().atom_id
            else 0
        )
        row.label(text="", icon_value=icon)  # icon="CHECKMARK"

        if atmosphere.id in atmo_duplicate_name_ids:
            row.alert = True

        row.prop(atmosphere, "name", text="", emboss=False)
        row.prop(atmosphere, "color", text="")


# 大气属性
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


# 扇区纹理属性
class SectorTextureProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    x: FloatProperty(name="X", default=0.0)  # type: ignore
    y: FloatProperty(name="Y", default=0.0)  # type: ignore
    zoom: FloatProperty(name="Zoom", default=1.0)  # type: ignore
    angle: FloatProperty(name="Angle", default=0.0)  # type: ignore


# 扇区灯光属性
class SectorLightProperty(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Vector",
        subtype="XYZ",
        size=3,
        min=-1.0,
        max=1.0,
    )  # type: ignore


class SectorFocoLightProperty(bpy.types.PropertyGroup):
    # 可添加多个，保存数据块名称
    name: StringProperty(name="Name", default="")  # type: ignore


# 扇区属性
class SectorProperty(bpy.types.PropertyGroup):
    atom_id: IntProperty(name="Atmosphere", description="", default=1)  # type: ignore
    floor_texture: CollectionProperty(type=SectorTextureProperty)  # type: ignore
    ceiling_texture: CollectionProperty(type=SectorTextureProperty)  # type: ignore
    wall_texture: CollectionProperty(type=SectorTextureProperty)  # type: ignore

    flat_light: CollectionProperty(type=SectorLightProperty)  # type: ignore # 平面光
    external_light: CollectionProperty(type=SectorLightProperty)  # type: ignore # 外部光
    ambient_light: CollectionProperty(type=SectorLightProperty)  # type: ignore # 环境光
    spot_light: CollectionProperty(type=SectorFocoLightProperty)  # type: ignore # 聚光灯

    group: IntProperty(
        name="Group",
        description="",
        default=0,  # 默认值为0
    )  # type: ignore
    comment: StringProperty(name="Comment", description="", default="")  # type: ignore


# 场景属性
class SceneProperty(bpy.types.PropertyGroup):
    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore
    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(name="Atmosphere", default=0)  # type: ignore
    defaults: CollectionProperty(type=SectorProperty)  # type: ignore # 扇区默认属性

    def get_default(self):
        return self.defaults[0]

    def set_defaults(self):
        self.defaults.add()
        default = self.defaults[0]

        default.atom_id = 1


##############################
##############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and any(issubclass(cls, parent) for parent in class_tuple)
]


def register():
    global ICONS
    addon_directory = os.path.dirname(__file__)

    import bpy.utils.previews

    ICONS = bpy.utils.previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    ICONS.load("star", os.path.join(icons_dir, "star.png"), "IMAGE")

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.amagate_data = PointerProperty(type=SectorProperty)  # type: ignore
    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty)  # type: ignore


def unregister():
    global ICONS
    del bpy.types.Object.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.utils.previews.remove(ICONS)
    ICONS = None
