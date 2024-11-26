from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

# from collections import Counter

import bpy
from bpy.app.translations import pgettext

# from bpy.types import Context
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
import rna_keymap_ui

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image

############################
ICONS: Any = None

AG_COLL = "Amagate Auto Generated"
S_COLL = "Sector Collection"
GS_COLL = "Ghost Sector Collection"
E_COLL = "Entity Collection"

DEBUG = False
############################


def region_redraw(target):
    for region in bpy.context.area.regions:  # type: ignore
        if region.type == target:
            region.tag_redraw()  # 刷新该区域


def get_scene_suffix(scene: bpy.types.Scene = None) -> str:  # type: ignore
    if not scene:
        scene = bpy.context.scene
    scene_data = scene.amagate_data  # type: ignore
    suffix = ""
    if scene_data.id != 1:
        suffix = f" (BS{scene_data.id})"
    return suffix


#
def get_id(used_ids, start_id=1) -> int:
    id_ = start_id
    while id_ in used_ids:
        id_ += 1
    return id_


def get_name(used_names, f, id_) -> str:
    name = f.format(id_)
    while name in used_names:
        id_ += 1
        name = f.format(id_)
    return name


#
def get_atmo_by_id(scene_data, atmo_id) -> tuple[int, AtmosphereProperty]:
    if atmo_id != 0:
        for i, atmo in enumerate(scene_data.atmospheres):
            if atmo.id == atmo_id:
                return (i, atmo)
    return (0, None)  # type: ignore


def get_external_by_id(scene_data, external_id) -> tuple[int, ExternalLightProperty]:
    if external_id != 0:
        for i, external in enumerate(scene_data.externals):
            if external.id == external_id:
                return (i, external)
    return (0, None)  # type: ignore


def get_texture_by_id(texture_id) -> tuple[int, bpy.types.Image]:
    if texture_id != 0:
        for i, texture in enumerate(bpy.data.images):
            if texture.amagate_data.id == texture_id:  # type: ignore
                return (i, texture)
    return (-1, None)  # type: ignore


# 确保NULL纹理存在
def ensure_null_texture():
    images = bpy.data.images
    img = images.get("NULL")
    if not img:
        img = images.new("NULL", width=256, height=256)
        img.amagate_data.id = -1  # type: ignore
    elif not img.amagate_data.id:  # type: ignore
        img.amagate_data.id = -1  # type: ignore


# 确保NULL物体存在
def ensure_null_object() -> bpy.types.Object:
    null_obj = bpy.data.objects.get("NULL")
    if not null_obj:
        null_obj = bpy.data.objects.new("NULL", None)
    return null_obj


# 确保集合
def ensure_collection(name, scene=None, hide_select=False) -> bpy.types.Collection:
    if not scene:
        scene = bpy.context.scene
    collections = bpy.data.collections
    name = f"{pgettext(name)}{get_scene_suffix(scene)}"
    coll = collections.get(name)
    if not coll:
        coll = collections.new(name)
        scene.collection.children.link(coll)
        coll.hide_select = hide_select
    return coll


def link2coll(obj, coll):
    if coll.objects.get(obj.name) is None:
        coll.objects.link(obj)


############################
############################ 偏好设置
############################

addon_keymaps = []


class AmagatePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__  # type: ignore

    # 用于保存面板的展开状态
    fold_state: BoolProperty(name="Fold State", default=True)  # type: ignore
    is_user_modified: BoolProperty(default=False)  # type: ignore

    def __init__(self):
        super().__init__()
        # self.fold_state = False

    def draw(self, context: Context):
        self.is_user_modified = False
        layout = self.layout
        wm = context.window_manager
        kc = wm.keyconfigs.user
        km = kc.keymaps["3D View"]
        keymap_items = [
            kmi for kmi in km.keymap_items if kmi.idname.startswith("amagate.")
        ]
        if len(keymap_items) < 1:
            self.is_user_modified = True
        else:
            for kmi in keymap_items:
                if kmi.is_user_modified:
                    self.is_user_modified = True

        row = layout.row()
        col = row.column()
        col.alignment = "LEFT"
        col.prop(
            self,
            "fold_state",
            text="",
            icon="TRIA_DOWN" if self.fold_state else "TRIA_RIGHT",
            emboss=False,
        )
        row.label(text="Keymap")
        # if self.is_user_modified:
        #     col = row.column()
        #     col.alignment = "RIGHT"
        #     col.operator("preferences.keymap_restore", text="Restore")

        if self.fold_state and keymap_items:
            box = layout.box()
            split = box.split()
            col = split.column()
            for kmi in keymap_items:
                col.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)


def register_shortcuts():
    global addon_keymaps
    # preferences = bpy.context.preferences.addons[__package__].preferences  # type: ignore

    wm = bpy.context.window_manager  # type: ignore
    kc = wm.keyconfigs.addon

    if kc:
        # shortcut_key = preferences.shortcut_key

        km = kc.keymaps.get("3D View")
        if km is None:
            km = kc.keymaps.new(
                name="3D View", space_type="VIEW_3D", region_type="WINDOW"
            )
        kmi = km.keymap_items.new(
            idname="amagate.sector_convert",
            type="ONE",
            value="PRESS",
            ctrl=True,
            alt=True,
        )
        # kmi.properties.name = "test"
        kmi.active = True
        addon_keymaps.append((km, kmi))


def unregister_shortcuts():
    global addon_keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


############################
############################ 保存前回调
############################


# 定义检查函数
def check_before_save(scene: bpy.types.Scene):
    img = bpy.data.images.get("NULL")
    if img:
        img.use_fake_user = True


############################
############################ 模板列表
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
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        # row.alignment = "LEFT"
        split = row.split(factor=0.6)
        row = split.row()
        # split = row

        # col = split.column()
        # col.enabled = False
        # col.label(text=f"ID: {item.id}")
        i = ICONS["star"].icon_id if item.id == scene_data.defaults.atmo_id else 0
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)  # icon="CHECKMARK"

        col = row.column()
        if enabled:
            col.prop(item, "name", text="", emboss=False)
        else:
            col.label(text=item.name)

        row = split.row()
        row.enabled = enabled
        row.prop(item, "color", text="")


class AMAGATE_UI_UL_ExternalLight(bpy.types.UIList):
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
        scene_data = context.scene.amagate_data  # type: ignore
        light = item  # 获取大气数据
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        split = row.split(factor=0.6)
        row = split.row()

        i = ICONS["star"].icon_id if light.id == scene_data.defaults.external_id else 0
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)

        col = row.column()
        if enabled:
            col.prop(light, "name", text="", emboss=False)
        else:
            col.label(text=light.name)

        if enabled:
            split = split.split(factor=0.5)
            row = split.row()
            row.alignment = "RIGHT"
            row.operator(
                "amagate.scene_external_set", text="", icon="LIGHT_SUN", emboss=False
            ).id = light.id  # type: ignore

        row = split.row()
        color = "color" if enabled else "color_readonly"
        row.prop(light, color, text="")


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
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        if self.target == "Sector":
            sectors = [obj for obj in bpy.context.selected_objects if obj.amagate_data.get_sector_data()]  # type: ignore
            for s in sectors:
                sector_data = s.amagate_data.get_sector_data()  # type: ignore
                sector_data.atmo_id = scene_data.atmospheres[value].id
        elif self.target == "Scene":
            scene_data.defaults.atmo_id = scene_data.atmospheres[value].id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select Atmosphere")


# 选择外部光
class External_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        if self.target == "Sector":
            sectors = [obj for obj in bpy.context.selected_objects if obj.amagate_data.get_sector_data()]  # type: ignore
            for s in sectors:
                sector_data = s.amagate_data.get_sector_data()  # type: ignore
                sector_data.external_id = scene_data.externals[value].id
        elif self.target == "Scene":
            scene_data.defaults.external_id = scene_data.externals[value].id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select External Light")


# 选择纹理
class Texture_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        if self.target != "Sector":
            scene_data.defaults["Textures"][self.target]["id"] = bpy.data.images[
                value
            ].amagate_data.id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select Texture")


############################
############################ Object Props
############################


class ObjectCollection(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)  # type: ignore


# 大气属性
class AtmosphereProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    name: StringProperty(name="Atmosphere Name", default="", get=lambda self: self.get_name(), set=lambda self, value: self.set_name(value))  # type: ignore
    users_obj: CollectionProperty(type=ObjectCollection)  # type: ignore
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=4,  # RGBA
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0, 0.02),
    )  # type: ignore
    # intensity: FloatProperty(name="Intensity", default=0.02)  # type: ignore

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

    # 确保引用对象存在
    # def ensure_obj(self, scene: bpy.types.Scene, fix_link=False):
    #     if not self.obj:
    #         name = f"AG.atmo{self.id}{get_scene_suffix(scene)}"
    #         obj = bpy.data.objects.get(name)
    #         if not (obj and obj.type == "EMPTY"):
    #             obj = bpy.data.objects.new(name, None)
    #         obj["id"] = self.id
    #         self.obj = obj

    #         # 引用对象被意外删除，进行自动修复
    #         if fix_link:
    #             for i in bpy.context.scene.objects:
    #                 sec_data = i.amagate_data.get_sector_data() # type: ignore
    #                 if sec_data and sec_data.atmo_id == self.id:
    #                     sec_data.atmo_obj = obj
    #             print("Fixed atmo reference link")

    #     return self.obj


# 纹理属性
class TextureProperty(bpy.types.PropertyGroup):
    # id: IntProperty(name="ID", default=0)  # type: ignore
    # x: FloatProperty(name="X", default=0.0)  # type: ignore
    # y: FloatProperty(name="Y", default=0.0)  # type: ignore

    target: StringProperty(default="Sector")  # type: ignore
    pos: FloatVectorProperty(
        name="Position",
        subtype="XYZ",
        size=2,
        step=10,
        set=lambda self, value: self.set_pos(value),
        get=lambda self: self.get_pos(),
        # min=-1.0,
        # max=1.0,
    )  # type: ignore
    zoom: FloatProperty(name="Zoom", default=10.0, set=lambda self, value: self.set_zoom(value), get=lambda self: self.get_zoom())  # type: ignore
    angle: FloatProperty(name="Angle", default=0.0, set=lambda self, value: self.set_angle(value), get=lambda self: self.get_angle())  # type: ignore
    ############################

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


# 外部光属性
class ExternalLightProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    name: StringProperty(name="Light Name", default="", get=lambda self: self.get_name(), set=lambda self, value: self.set_name(value))  # type: ignore
    obj: PointerProperty(type=bpy.types.Light)  # type: ignore
    users_obj: CollectionProperty(type=ObjectCollection)  # type: ignore

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
        get=lambda self: self.get("_color", (0.784, 0.784, 0.784)),
        set=lambda self, value: self.set_dict("_color", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    color_readonly: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        get=lambda self: self.get("_color", (0.784, 0.784, 0.784)),
        set=lambda self, value: None,
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Direction",
        subtype="XYZ",
        default=(0.0, 0.0, -1.0),  # 默认向量值
        size=3,  # 必须是 3 维向量
        min=-1.0,
        max=1.0,
        get=lambda self: self.get("_vector", (0.0, 0.0, -1.0)),
        set=lambda self, value: self.set_dict("_vector", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    vector2: FloatVectorProperty(
        name="Direction",
        subtype="DIRECTION",
        default=(0.0, 0.0, -1.0),  # 默认向量值
        size=3,  # 必须是 3 维向量
        min=-1.0,
        max=1.0,
        get=lambda self: self.get("_vector", (0.0, 0.0, -1.0)),
        set=lambda self, value: self.set_dict("_vector", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore

    def set_dict(self, key, value):
        self[key] = value

    def get_name(self):
        return self.get("_name", "")

    def set_name(self, value):
        if value == "":
            return

        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore
        lights = scene_data.externals
        for l in lights:
            if l.name == value and l != self:
                l["_name"] = self.get("_name", "")
                break
        self["_name"] = value

    # TODO 每删除10个扇区触发一次clean
    def clean(self, lst=None):
        if not lst:
            lst = [i for i, item in enumerate(self.users_obj) if not item.obj]
        for i in reversed(lst):
            self.users_obj.remove(i)

    def ensure_obj(self):
        if not self.obj:
            name = f"AG.Sun{self.id}"
            light_data = bpy.data.lights.get(name)
            if not (light_data and light_data.type == "SUN"):
                light_data = bpy.data.lights.new("", type="SUN")
                light_data.rename(name, mode="ALWAYS")
            self.obj = light_data

        return self.obj

    def sync_users(self, rotation_euler):
        items_to_remove = []
        for i, d in enumerate(self.users_obj):
            sec = d.obj
            if not sec:
                items_to_remove.append(i)
            else:
                sec.amagate_data.get_sector_data().ensure_external_obj(
                    self, rotation_euler
                )

        if items_to_remove:
            self.clean(items_to_remove)

    def update_obj(self, context=None):
        self.ensure_obj()
        self.obj.color = self.color  # 设置颜色
        rotation_euler = self.vector.to_track_quat("-Z", "Z").to_euler()
        self.sync_users(rotation_euler)
        # light_data.energy = self.energy  # 设置能量


# 环境光属性
class AmbientLightProperty(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
    )  # type: ignore


# 平面光属性
class FlatLightProperty(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Direction",
        subtype="XYZ",
        default=(0.0, 0.0, 0.0),
        size=3,
        min=-1.0,
        max=1.0,
    )  # type: ignore


class SectorFocoLightProperty(bpy.types.PropertyGroup):
    # 可添加多个，保存数据块名称
    name: StringProperty(name="Name", default="")  # type: ignore
    # TODO


# 扇区属性
class SectorProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    # is_sector: BoolProperty(default=False)  # type: ignore
    atmo_id: IntProperty(name="Atmosphere", description="", default=1)  # type: ignore
    # atmo_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    # floor_texture: CollectionProperty(type=TextureProperty)  # type: ignore
    # ceiling_texture: CollectionProperty(type=TextureProperty)  # type: ignore
    # wall_texture: CollectionProperty(type=TextureProperty)  # type: ignore

    ambient_light: PointerProperty(type=AmbientLightProperty)  # type: ignore # 环境光
    external_id: IntProperty(name="External Light", description="", default=1)  # type: ignore
    external_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    flat_light: PointerProperty(type=FlatLightProperty)  # type: ignore # 平面光

    spot_light: CollectionProperty(type=SectorFocoLightProperty)  # type: ignore # 聚光灯

    group: IntProperty(
        name="Group",
        description="",
        default=0,  # 默认值为0
    )  # type: ignore
    comment: StringProperty(name="Comment", description="", default="")  # type: ignore

    def ensure_external_obj(self, external=None, rotation_euler=None):
        scene_data = bpy.context.scene.amagate_data  # type: ignore
        if not external:
            external = get_external_by_id(scene_data, self.external_id)[1]
        if not external:
            # 不存在的external_id
            print("Error: external_id {self.external_id} does not exist")
            return
        light_data = external.obj
        if not light_data:
            return

        if not self.external_obj:
            name = f"AG - Sector{self.id}.Sun{self.external_id}"
            light = bpy.data.objects.new(name, object_data=light_data)
            self.external_obj = light

            light.hide_select = True
            # self.id_data.users_collection[0].objects.link(light)
            # light.parent = self.id_data
            link2coll(light, ensure_collection(AG_COLL, hide_select=True))
            # 创建灯光链接集合
            collections = bpy.data.collections
            name = f"{name}.Linking"
            lightlink_coll = collections.get(name)
            if lightlink_coll:
                collections.remove(lightlink_coll)
            lightlink_coll = collections.new(name)
            light.light_linking.receiver_collection = lightlink_coll
            light.light_linking.blocker_collection = lightlink_coll
            link2coll(ensure_null_object(), lightlink_coll)

            if not rotation_euler:
                rotation_euler = external.vector.to_track_quat("-Z", "Z").to_euler()

        if rotation_euler:
            self.external_obj.rotation_euler = rotation_euler

        return self.external_obj

    def init(self):
        scene_data: SceneProperty = bpy.context.scene.amagate_data  # type: ignore

        used_ids = tuple(a.amagate_data.get_sector_data().id for a in bpy.context.scene.objects if a.amagate_data.get_sector_data())  # type: ignore
        id_ = get_id(used_ids)
        self.id = id_

        self["Textures"] = {}
        obj = self.id_data
        mesh = obj.data

        # 遍历网格的面
        for face in mesh.polygons:  # polygons 代表面
            face_index = face.index  # 面的索引
            face_normal = face.normal  # 面的法线方向（Vector）

            # 判断是否朝上或朝下
            if face_normal.z > 0:  # z 方向为正，面朝上，地板
                self["Textures"][str(face_index)] = scene_data.defaults["Textures"][
                    "Floor"
                ]
            elif face_normal.z < 0:  # z 方向为负，面朝下，天花板
                self["Textures"][str(face_index)] = scene_data.defaults["Textures"][
                    "Ceiling"
                ]
            else:
                self["Textures"][str(face_index)] = scene_data.defaults["Textures"][
                    "Wall"
                ]

        self.atmo_id = scene_data.defaults.atmo_id
        get_atmo_by_id(scene_data, self.atmo_id)[1].users_obj.add().obj = obj

        # self.ambient_light.color = scene_data.defaults.ambient_light.color
        # self.ambient_light.vector = scene_data.defaults.ambient_light.vector

        self.external_id = scene_data.defaults.external_id
        self.ensure_external_obj()
        get_external_by_id(scene_data, self.external_id)[1].users_obj.add().obj = obj
        # self.external_light.color = scene_data.defaults.external_light.color
        # self.external_light.vector = scene_data.defaults.external_light.vector

        # self.flat_light.color = scene_data.defaults.flat_light.color


# 图像属性
class ImageProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore


# 场景属性
class SceneProperty(bpy.types.PropertyGroup):
    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore

    # amagate_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore
    sector_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore
    ghostsector_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore
    entity_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore

    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(name="Atmosphere", default=0)  # type: ignore

    # 外部光
    externals: CollectionProperty(type=ExternalLightProperty)  # type: ignore
    active_external: IntProperty(name="External Light", default=0)  # type: ignore

    active_texture: IntProperty(name="Texture", default=0, set=lambda self, value: self.set_active_texture(value), get=lambda self: self.get_active_texture())  # type: ignore

    defaults: PointerProperty(type=SectorProperty)  # type: ignore # 扇区默认属性

    # 布局属性
    default_tex: CollectionProperty(type=TextureProperty)  # type: ignore
    sector_tex: PointerProperty(type=TextureProperty)  # type: ignore
    ############################

    def get_active_texture(self):
        value = self.get("_active_texture", 0)

        if value >= len(bpy.data.images) or bpy.data.images[value].amagate_data.id == 0:
            value = next((i for i, img in enumerate(bpy.data.images) if img.amagate_data.id != 0), 0)  # type: ignore

        return value

    def set_active_texture(self, value):
        self["_active_texture"] = value

    ############################
    def init(self):
        defaults = self.defaults

        defaults.atmo_id = 1
        defaults.external_id = 1
        defaults["Textures"] = {
            "Floor": {"id": 0, "pos": (0.0, 0.0), "zoom": 10.0, "angle": 0.0},
            "Ceiling": {"id": 0, "pos": (0.0, 0.0), "zoom": 10.0, "angle": 0.0},
            "Wall": {"id": 0, "pos": (0.0, 0.0), "zoom": 10.0, "angle": -90.0},
        }

        ############################
        for i in ("Floor", "Ceiling", "Wall"):
            prop = self.default_tex.add()
            prop.target = i


# 物体属性
class ObjectProperty(bpy.types.PropertyGroup):
    SectorData: CollectionProperty(type=SectorProperty)  # type: ignore

    def get_sector_data(self):
        if len(self.SectorData) == 0:
            return None
        return self.SectorData[0]

    def set_sector_data(self):
        if not self.SectorData:
            self.SectorData.add()
            # return self.SectorData[0]


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
    ICONS.load("blade", os.path.join(icons_dir, "blade.png"), "IMAGE")

    bpy.utils.register_class(AmagatePreferences)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.amagate_data = PointerProperty(type=ObjectProperty, name="Amagate Data")  # type: ignore
    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty, name="Amagate Data")  # type: ignore
    bpy.types.Image.amagate_data = PointerProperty(type=ImageProperty, name="Amagate Data")  # type: ignore

    # 注册保存前回调函数
    # bpy.app.handlers.save_pre.append(check_before_save)


def unregister():
    global ICONS
    del bpy.types.Object.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    del bpy.types.Image.amagate_data  # type: ignore

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.utils.unregister_class(AmagatePreferences)

    bpy.utils.previews.remove(ICONS)
    ICONS = None

    # bpy.app.handlers.save_pre.remove(check_before_save)
