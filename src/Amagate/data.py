from __future__ import annotations

import os
from typing import Any

# from collections import Counter

import bpy
from bpy.props import (
    PointerProperty,
    CollectionProperty,
    EnumProperty,
    BoolProperty,
    BoolVectorProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    IntVectorProperty,
    StringProperty,
)

############################
ICONS: Any = None
############################


def region_redraw(target):
    for region in bpy.context.area.regions:  # type: ignore
        if region.type == target:
            region.tag_redraw()  # 刷新该区域


def get_atmo_by_id(scene_data, atmo_id) -> tuple[int, AtmosphereProperty]:
    if atmo_id != 0:
        for i, atmo in enumerate(scene_data.atmospheres):
            if atmo.id == atmo_id:
                return (i, atmo)
    return (0, None)  # type: ignore


def get_texture_by_id(texture_id) -> tuple[int, bpy.types.Image]:
    if texture_id != 0:
        for i, texture in enumerate(bpy.data.images):
            if texture.amagate_data.id == texture_id:  # type: ignore
                return (i, texture)
    return (0, None)  # type: ignore


# 确保NULL纹理存在
def ensure_null_texture():
    images = bpy.data.images
    img = images.get("NULL")
    if not img:
        img = images.new("NULL", width=256, height=256)
        img.amagate_data.id = -1  # type: ignore
    elif not img.amagate_data.id:  # type: ignore
        img.amagate_data.id = -1  # type: ignore


############################
############################
############################


class AMAGATE_UI_UL_StrList(bpy.types.UIList):
    # def draw_filter(self, context, layout):
    #     pass

    def draw_item(
        self,
        context,
        layout: bpy.types.UILayout,
        data,
        item,
        icon,
        active_data,
        active_prop,
    ):
        row = layout.row()
        row.label(text=item.name)


class AMAGATE_UI_UL_AtmoList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        scene_data = context.scene.amagate_data  # type: ignore
        atmosphere = item  # 获取大气数据
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        # row.alignment = "LEFT"
        split = row.split(factor=0.6)
        row = split.row()
        # split = row

        # col = split.column()
        # col.enabled = False
        # col.label(text=f"ID: {atmosphere.id}")
        i = ICONS["star"].icon_id if atmosphere.id == scene_data.defaults.atmo_id else 0
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)  # icon="CHECKMARK"

        col = row.column()
        if enabled:
            col.prop(atmosphere, "name", text="", emboss=False)
        else:
            col.label(text=atmosphere.name)

        row = split.row()
        row.enabled = enabled
        row.prop(atmosphere, "color", text="")


class AMAGATE_UI_UL_TextureList(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = [0] * len(items)
        flt_neworder = []

        for idx, item in enumerate(items):
            if item.amagate_data.id != 0:
                flt_flags[idx] = self.bitflag_filter_item

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context,
        layout,
        data,
        item: bpy.types.Image,
        icon,
        active_data,
        active_prop,
    ):
        scene_data = context.scene.amagate_data  # type: ignore
        tex = item
        tex_data = tex.amagate_data  # type: ignore
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()

        i = tex.preview.icon_id if tex.preview else 0
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)

        col = row.column()
        if enabled:
            col.prop(tex, "name", text="", emboss=False)
        else:
            col.label(text=tex.name)

        col = row.column()
        col.alignment = "RIGHT"
        default_id = [
            i["id"] for i in scene_data.defaults["Textures"].values() if i["id"] != 0
        ]
        i = ICONS["star"].icon_id if tex_data.id in default_id else 0
        col.label(text="", icon_value=i)

        col = row.column()
        col.alignment = "RIGHT"
        i = "UGLYPACKAGE" if tex.packed_file else "NONE"
        col.label(text="", icon=i)


############################
############################ Operator Props
############################


class StringCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore


# 选择大气
class Atmo_Select(bpy.types.PropertyGroup):
    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        self["_index"] = value

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        if self.target == "Sector":
            pass
        elif self.target == "Scene":
            scene_data.defaults.atmo_id = scene_data.atmospheres[value].id
        region_redraw("UI")

    ############################
    index: IntProperty(name="", default=0, get=get_index, set=set_index)  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore


# 选择纹理
class Texture_Select(bpy.types.PropertyGroup):
    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        self["_index"] = value

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        if self.target != "Sector":
            scene_data.defaults["Textures"][self.target]["id"] = bpy.data.images[
                value
            ].amagate_data.id
        region_redraw("UI")

    ############################
    index: IntProperty(name="", default=0, get=get_index, set=set_index)  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore


############################
############################ Object Props
############################


# 大气属性
class AtmosphereProperty(bpy.types.PropertyGroup):
    def get_name(self):
        return self.get("_name", "")

    def set_name(self, value):
        if value == "":
            return

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        atmos = scene_data.atmospheres
        for atmo in atmos:
            if atmo.name == value and atmo != self:
                atmo["_name"] = self.get("_name", "")
                break
        self["_name"] = value

    ############################
    name: StringProperty(name="Atmosphere Name", default="", get=get_name, set=set_name)  # type: ignore
    atmo_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
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


# 纹理属性
class TextureProperty(bpy.types.PropertyGroup):
    # id: IntProperty(name="ID", default=0)  # type: ignore
    # x: FloatProperty(name="X", default=0.0)  # type: ignore
    # y: FloatProperty(name="Y", default=0.0)  # type: ignore
    def get_pos(self):
        if self.target != "Sector":
            scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
            return scene_data.defaults["Textures"][self.target]["pos"]
        else:
            return self.get("_pos", (0.0, 0.0))

    def set_pos(self, value):
        if self.target != "Sector":
            scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
            scene_data.defaults["Textures"][self.target]["pos"] = value
        else:
            self["_pos"] = value

    ############################
    def get_zoom(self):
        if self.target != "Sector":
            scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
            return scene_data.defaults["Textures"][self.target]["zoom"]
        else:
            return self.get("_zoom", 10.0)

    def set_zoom(self, value):
        if self.target != "Sector":
            scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
            scene_data.defaults["Textures"][self.target]["zoom"] = value
        else:
            self["_zoom"] = value

    ############################
    def get_angle(self):
        if self.target != "Sector":
            scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
            return scene_data.defaults["Textures"][self.target]["angle"]
        else:
            return self.get("_angle", 0.0)

    def set_angle(self, value):
        if self.target != "Sector":
            scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
            scene_data.defaults["Textures"][self.target]["angle"] = value
        else:
            self["_angle"] = value

    ############################
    target: StringProperty(default="Sector")  # type: ignore
    pos: FloatVectorProperty(
        name="Position",
        subtype="XYZ",
        size=2,
        step=10,
        set=set_pos,
        get=get_pos,
        # min=-1.0,
        # max=1.0,
    )  # type: ignore
    zoom: FloatProperty(name="Zoom", default=10.0, set=set_zoom, get=get_zoom)  # type: ignore
    angle: FloatProperty(name="Angle", default=0.0, set=set_angle, get=get_angle)  # type: ignore


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
    is_sector: BoolProperty(default=False)  # type: ignore
    atmo_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    atmo_id: IntProperty(name="Atmosphere", description="", default=1)  # type: ignore
    # floor_texture: CollectionProperty(type=TextureProperty)  # type: ignore
    # ceiling_texture: CollectionProperty(type=TextureProperty)  # type: ignore
    # wall_texture: CollectionProperty(type=TextureProperty)  # type: ignore

    flat_light: PointerProperty(type=SectorLightProperty)  # type: ignore # 平面光
    external_light: PointerProperty(type=SectorLightProperty)  # type: ignore # 外部光
    ambient_light: PointerProperty(type=SectorLightProperty)  # type: ignore # 环境光
    spot_light: CollectionProperty(type=SectorFocoLightProperty)  # type: ignore # 聚光灯

    group: IntProperty(
        name="Group",
        description="",
        default=0,  # 默认值为0
    )  # type: ignore
    comment: StringProperty(name="Comment", description="", default="")  # type: ignore


# 图像属性
class ImageProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore


# 场景属性
class SceneProperty(bpy.types.PropertyGroup):
    def get_active_texture(self):
        value = self.get("_active_texture", 0)

        if value >= len(bpy.data.images):
            return 0

        active_id = self.get("_active_texture_id", 0)
        curr_id = bpy.data.images[value].amagate_data.id
        if active_id and curr_id:
            if curr_id != active_id:
                for i, img in enumerate(bpy.data.images):
                    if img.amagate_data.id == active_id:  # type: ignore
                        value = i
                        break
                else:
                    self["_active_texture_id"] = curr_id
        return value

    def set_active_texture(self, value):
        self["_active_texture"] = value
        self["_active_texture_id"] = bpy.data.images[value].amagate_data.id

    ############################
    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore

    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(name="Atmosphere", default=0)  # type: ignore

    active_texture: IntProperty(name="Texture", default=0, set=set_active_texture, get=get_active_texture)  # type: ignore

    defaults: PointerProperty(type=SectorProperty)  # type: ignore # 扇区默认属性

    # 布局属性
    default_tex: CollectionProperty(type=TextureProperty)  # type: ignore
    sector_tex: PointerProperty(type=TextureProperty)  # type: ignore
    ############################

    def init(self):
        defaults = self.defaults

        defaults.atmo_id = 1
        defaults["Textures"] = {
            "Floor": {"id": 0, "pos": (0.0, 0.0), "zoom": 10.0, "angle": 0.0},
            "Ceiling": {"id": 0, "pos": (0.0, 0.0), "zoom": 10.0, "angle": 0.0},
            "Wall": {"id": 0, "pos": (0.0, 0.0), "zoom": 10.0, "angle": -90.0},
        }

        ############################
        for i in ("Floor", "Ceiling", "Wall"):
            prop = self.default_tex.add()
            prop.target = i


############################
############################
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
    bpy.types.Image.amagate_data = PointerProperty(type=ImageProperty)  # type: ignore


def unregister():
    global ICONS
    del bpy.types.Object.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    del bpy.types.Image.amagate_data  # type: ignore
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.utils.previews.remove(ICONS)
    ICONS = None
