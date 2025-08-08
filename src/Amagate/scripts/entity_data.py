# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import re
import os
import math
import shutil
import pickle
import threading
import contextlib
from pathlib import Path
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

# from collections import Counter
#
import bpy

import bmesh
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
import blf
from mathutils import *  # type: ignore

#
from . import ag_utils, data

#

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection

############################
logger = data.logger
SELECTED_ENTITIES = []  # type: list[Object]
ACTIVE_ENTITY = None  # type: Object | None

# 装备库存
W_FLAG_1H = 0
W_FLAG_2W = 1
W_FLAG_AXE = 2
W_FLAG_SP = 3
OBJ_STANDARD = 4
OBJ_SHIELD = 5
OBJ_QUIVER = 6
OBJ_BOW = 7
# 道具库存
OBJ_ITEM = 8
OBJ_USEME = 9
OBJ_KEY = 10
#
OBJ_ARROW = 11
OBJ_ARMOUR = 12
OBJ_SPECIALKEY = 13
OBJ_TABLET = 14

# 角色
OBJ_CHARACTER = 20

#
OBJ_NONE = 99


############################
############################
############################


def get_name(context: Context, prefix: str, start_id=1):
    scene_data = context.scene.amagate_data
    while scene_data["EntityManage"].get(f"{prefix}{start_id}"):
        start_id += 1
    return f"{prefix}{start_id}"


def is_uniform(attr: str):
    selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
    if not active_entity:
        return True
    #
    ent_data = active_entity.amagate_data.get_entity_data()
    active_value = eval(f"ent_data.{attr}")
    for entity in selected_entities:
        if entity == active_entity:
            continue

        ent_data = entity.amagate_data.get_entity_data()
        if active_value != eval(f"ent_data.{attr}"):
            return False
    return True


def load_ent_preview():
    preview_dir = os.path.join(data.ADDON_PATH, "Models", "Preview")
    data.ENT_PREVIEWS = bpy.utils.previews.new()
    for file in os.listdir(preview_dir):
        if file.lower().endswith(".jpg"):
            data.ENT_PREVIEWS.load(
                file[:-4], os.path.join(preview_dir, file), "IMAGE"
            )  # force_reload=True
    # 生成实体枚举
    gen_ent_enum()
    gen_equipment()
    gen_prop()
    gen_character()


############################


def get_ent_enum(this, context):
    return ENT_ENUM


def get_ent_enum_search(this, context):
    return ENT_ENUM_SEARCH

    # ent_enum = ENT_ENUM.copy()
    # for i in range(len(ent_enum) - 1, -1, -1):
    #     if ent_enum[i][0] == "":
    #         ent_enum.pop(i)
    #     else:
    #         ent_enum[i] = (
    #             ent_enum[i][0],
    #             f"{ent_enum[i][1]} - {ent_enum[i][2]}",
    #             ent_enum[i][2],
    #             ent_enum[i][3],
    #             ent_enum[i][4],
    #         )
    # get_ent_enum_search.items = ent_enum
    # return ent_enum


def get_ent_preview(this, context) -> Any:
    wm_data = context.window_manager.amagate_data
    name = bpy.types.UILayout.enum_item_name(wm_data, "ent_enum", wm_data.ent_enum)
    description = bpy.types.UILayout.enum_item_description(
        wm_data, "ent_enum", wm_data.ent_enum
    )
    icon = bpy.types.UILayout.enum_item_icon(wm_data, "ent_enum", wm_data.ent_enum)
    get_ent_preview.items = [("0", name, description, icon, 0)]
    return get_ent_preview.items


def gen_ent_enum():
    global ENT_ENUM, ENT_ENUM_SEARCH
    ENT_ENUM = []
    ENT_ENUM_SEARCH = []
    count = 0

    for cat in (
        "Characters",
        "Props",
        "1H Weapons",
        "2H Weapons",
        "Shields & Bows",
        # "Special Entities",
        "Others",
        "Custom",
        "Pieces",
    ):
        enum = []
        for k, v in data.E_MANIFEST["Entities"][cat].items():
            filename = Path(v[1])
            enum.append(
                [
                    str(count),
                    v[0],
                    k,
                    (
                        data.ENT_PREVIEWS[filename.stem].icon_id
                        if data.ENT_PREVIEWS.get(filename.stem)
                        else data.BLANK1
                    ),
                    count,
                    v[2],
                ]
            )
            count += 1
        enum.sort(key=lambda x: x[1])
        enum.sort(key=lambda x: x[5])
        for i in range(len(enum)):
            enum[i] = tuple(enum[i][:-1])
        #
        enum_search = enum.copy()
        for i in range(len(enum_search)):
            item = enum_search[i]
            enum_search[i] = (
                item[0],
                f"{item[1]} - {item[2]}",
                item[2],
                item[3],
                item[4],
            )
        ENT_ENUM_SEARCH.extend(enum_search)
        #
        enum.insert(0, ("", cat, ""))
        ENT_ENUM.extend(enum)


############################
def get_equipment(this, context):
    return EQUIPMENT_ENUM


def get_equipment_search(this, context):
    return EQUIPMENT_ENUM_SEARCH


def add_equipment_pre(this, context: Context):
    ag_utils.simulate_keypress(27)
    bpy.app.timers.register(
        lambda: (add_equipment(undo=True), None)[1], first_interval=0.03
    )


def add_equipment(inter_name="", entity=None, undo=False):
    from . import L3D_operator as OP_L3D

    context = bpy.context
    wm_data = context.window_manager.amagate_data
    if inter_name == "":
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "equipment_enum", wm_data.equipment_enum
        )
    if entity is None:
        entity = ACTIVE_ENTITY
    ent_data = entity.amagate_data.get_entity_data()

    obj_name = get_name(context, f"{ent_data.Name}_Equip_")
    _, inv_ent = OP_L3D.OT_EntityCreate.add(
        None, context, inter_name, obj_name=obj_name
    )
    if not inv_ent:
        return

    item = ent_data.equipment_inv.add()
    item.obj = inv_ent
    wm_data.active_equipment = len(ent_data.equipment_inv) - 1

    inv_ent.visible_camera = False
    inv_ent.visible_shadow = False
    # inv_ent.location = entity.location + Vector((0, 0, 1.2))

    if undo:
        bpy.ops.ed.undo_push(message="Add Inventory")

    return inv_ent


def gen_equipment():
    global EQUIPMENT_ENUM, EQUIPMENT_ENUM_SEARCH
    EQUIPMENT_ENUM = []
    EQUIPMENT_ENUM_SEARCH = []
    count = 0

    for cat in (
        # "Characters",
        # "Props",
        "1H Weapons",
        "2H Weapons",
        "Shields & Bows",
        # "Others",
        # "Pieces",
        "Custom",
    ):
        enum = []
        for k, v in data.E_MANIFEST["Entities"][cat].items():
            filename = Path(v[1])
            ItemType = v[2]
            if 0 <= ItemType <= 7:
                enum.append(
                    [
                        str(count),
                        v[0],
                        k,
                        (
                            data.ENT_PREVIEWS[filename.stem].icon_id
                            if data.ENT_PREVIEWS.get(filename.stem)
                            else data.BLANK1
                        ),
                        count,
                        ItemType,
                    ]
                )
                count += 1
        enum.sort(key=lambda x: x[1])
        enum.sort(key=lambda x: x[5])
        for i in range(len(enum)):
            enum[i] = tuple(enum[i][:-1])
        #
        enum_search = enum.copy()
        for i in range(len(enum_search)):
            item = enum_search[i]
            enum_search[i] = (
                item[0],
                f"{item[1]} - {item[2]}",
                item[2],
                item[3],
                item[4],
            )
        EQUIPMENT_ENUM_SEARCH.extend(enum_search)
        #
        # enum.insert(0, ("", cat, ""))
        EQUIPMENT_ENUM.extend(enum)


############################
def get_prop(this, context):
    return PROP_ENUM


def get_prop_search(this, context):
    return PROP_ENUM_SEARCH


def add_prop_pre(this, context: Context):
    ag_utils.simulate_keypress(27)
    bpy.app.timers.register(lambda: (add_prop(undo=True), None)[1], first_interval=0.03)


def add_prop(inter_name="", entity=None, undo=False):
    from . import L3D_operator as OP_L3D

    context = bpy.context
    wm_data = context.window_manager.amagate_data
    if inter_name == "":
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "prop_enum", wm_data.prop_enum
        )
    if entity is None:
        entity = ACTIVE_ENTITY
    ent_data = entity.amagate_data.get_entity_data()

    obj_name = get_name(context, f"{ent_data.Name}_Prop_")
    _, inv_ent = OP_L3D.OT_EntityCreate.add(
        None, context, inter_name, obj_name=obj_name
    )
    if not inv_ent:
        return

    item = ent_data.prop_inv.add()
    item.obj = inv_ent
    wm_data.active_prop = len(ent_data.prop_inv) - 1

    inv_ent.visible_camera = False
    inv_ent.visible_shadow = False
    # inv_ent.location = entity.location + Vector((0, 0, 1.2))

    if undo:
        bpy.ops.ed.undo_push(message="Add Inventory")

    return inv_ent


def gen_prop():
    global PROP_ENUM, PROP_ENUM_SEARCH
    PROP_ENUM = []
    PROP_ENUM_SEARCH = []
    count = 0

    for cat in (
        # "Characters",
        "Props",
        # "1H Weapons",
        # "2H Weapons",
        # "Shields & Bows",
        # "Others",
        # "Pieces",
        "Custom",
    ):
        enum = []
        for k, v in data.E_MANIFEST["Entities"][cat].items():
            filename = Path(v[1])
            ItemType = v[2]
            if 8 <= ItemType <= 10:
                enum.append(
                    [
                        str(count),
                        v[0],
                        k,
                        (
                            data.ENT_PREVIEWS[filename.stem].icon_id
                            if data.ENT_PREVIEWS.get(filename.stem)
                            else data.BLANK1
                        ),
                        count,
                        ItemType,
                    ]
                )
                count += 1
        enum.sort(key=lambda x: x[1])
        enum.sort(key=lambda x: x[5])
        for i in range(len(enum)):
            enum[i] = tuple(enum[i][:-1])
        #
        enum_search = enum.copy()
        for i in range(len(enum_search)):
            item = enum_search[i]
            enum_search[i] = (
                item[0],
                f"{item[1]} - {item[2]}",
                item[2],
                item[3],
                item[4],
            )
        PROP_ENUM_SEARCH.extend(enum_search)
        #
        # enum.insert(0, ("", cat, ""))
        PROP_ENUM.extend(enum)


############################


def get_character_enum(this, context):
    return CHARACTER_ENUM


def get_character_enum_search(this, context):
    return CHARACTER_ENUM_SEARCH


def gen_character():
    global CHARACTER_ENUM, CHARACTER_ENUM_SEARCH
    CHARACTER_ENUM = []
    CHARACTER_ENUM_SEARCH = []
    count = 0

    for cat in (
        "Characters",
        # "Props",
        # "1H Weapons",
        # "2H Weapons",
        # "Shields & Bows",
        # "Others",
        # "Pieces",
        "Custom",
    ):
        enum = []
        for k, v in data.E_MANIFEST["Entities"][cat].items():
            filename = Path(v[1])
            ItemType = v[2]
            if ItemType == 20:
                enum.append(
                    [
                        str(count),
                        v[0],
                        k,
                        (
                            data.ENT_PREVIEWS[filename.stem].icon_id
                            if data.ENT_PREVIEWS.get(filename.stem)
                            else data.BLANK1
                        ),
                        count,
                    ]
                )
                count += 1
        enum.sort(key=lambda x: x[1])
        #
        enum_search = enum.copy()
        for i in range(len(enum_search)):
            item = enum_search[i]
            enum_search[i] = (
                item[0],
                f"{item[1]} - {item[2]}",
                item[2],
                item[3],
                item[4],
            )
        CHARACTER_ENUM_SEARCH.extend(enum_search)
        #
        CHARACTER_ENUM.extend(enum)


############################
def add_contained_item_pre(this, context: Context):
    ag_utils.simulate_keypress(27)
    bpy.app.timers.register(lambda: add_contained_item(undo=True), first_interval=0.03)


def add_contained_item(inter_name="", entity=None, undo=False):
    from . import L3D_operator as OP_L3D

    context = bpy.context
    wm_data = context.window_manager.amagate_data
    if inter_name == "":
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "contained_item_enum", wm_data.contained_item_enum
        )
    if entity is None:
        entity = ACTIVE_ENTITY
    ent_data = entity.amagate_data.get_entity_data()

    obj_name = get_name(context, f"{inter_name}_")
    _, inv_ent = OP_L3D.OT_EntityCreate.add(
        None, context, inter_name, obj_name=obj_name
    )
    if not inv_ent:
        return

    item = ent_data.contained_item.add()
    item.obj = inv_ent
    wm_data.active_contained_item = len(ent_data.contained_item) - 1

    inv_ent.visible_camera = False
    inv_ent.visible_shadow = False
    # inv_ent.location = entity.location + Vector((0, 0, 1.2))

    if undo:
        bpy.ops.ed.undo_push(message="Add Item")


############################
############################ 模板列表
############################


# 库存
class AMAGATE_UI_UL_Inventory(bpy.types.UIList):
    def draw_filter(self, context, layout):
        row = layout.row()
        row.prop(self, "filter_name", text="", icon="VIEWZOOM")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        #
        flt_neworder = []
        # 按A-Z排序
        # if self.use_filter_sort_alpha:
        #     flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(items, "item_name")
        # else:
        #     flt_neworder = []
        # 按名称过滤
        if self.filter_name:
            flt_flags = [self.bitflag_filter_item] * len(items)  # 默认全部显示
            regex_pattern = re.escape(self.filter_name).replace(r"\*", ".*")
            regex = re.compile(f"{regex_pattern}", re.IGNORECASE)  # 全匹配忽略大小写
            for idx, item in enumerate(items):
                if item.obj is None or not regex.search(item.obj.name):
                    flt_flags[idx] = 0
        elif self.use_filter_invert:
            flt_flags = [0] * len(items)
        else:
            flt_flags = [self.bitflag_filter_item] * len(items)

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context: Context,
        layout: bpy.types.UILayout,
        data_,
        item,
        icon,
        active_data,
        active_prop,
    ):
        from . import entity_operator as OP_Entity

        scene_data = context.scene.amagate_data
        ent = item.obj
        if ent is None:
            layout.alert = True
            layout.label(text="Deleted Object", icon="ERROR")
        else:
            layout.alert = False
            ent_data = ent.amagate_data.get_entity_data()
            icon_id = next(i[3] for i in ENT_ENUM if i[2] == ent_data.Kind)
            row = layout.row(align=True)
            op = row.operator(
                OP_Entity.OT_Inventory_Preview.bl_idname,
                text="",
                icon_value=icon_id,
                emboss=False,
            )
            op.icon_id = icon_id  # type: ignore
            op.Kind = ent_data.Kind  # type: ignore

            row.label(text=ent_data.Name)
            row.operator(OP_Entity.OT_Inventory_Select.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False).obj_name = ent.name  # type: ignore


############################
############################ Collection Props
############################


class EntityCollection(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    # index: IntProperty(default=0)  # type: ignore


############################
############################ Object Props
############################


# 实体灯光属性
class LightProperty(bpy.types.PropertyGroup):
    target: StringProperty(default="UI")  # type: ignore

    Intensity: FloatProperty(
        description="Intensity of the light",
        default=10,
        min=0,
        get=lambda self: self.get_value("Intensity", 10),
        set=lambda self, value: self.set_value(value, "Intensity"),
    )  # type: ignore
    Precision: FloatProperty(
        description="Precision of the light",
        default=0.03125,
        min=0.00001,
        get=lambda self: self.get_value("Precision", 0.03125),
        set=lambda self, value: self.set_value(value, "Precision"),
    )  # type: ignore
    Color: FloatVectorProperty(
        subtype="COLOR",
        default=(1.0, 0.768, 0.501),  # (255, 196, 128)
        min=0,
        max=1,
        get=lambda self: self.get_value("Color", (1.0, 0.768, 0.501)),
        set=lambda self, value: self.set_value(value, "Color"),
    )  # type: ignore
    Flick: BoolProperty(
        default=True,
        description="Flicker",
        get=lambda self: self.get_value("Flick", True),
        set=lambda self, value: self.set_value(value, "Flick"),
    )  # type: ignore
    Visible: BoolProperty(
        default=True,
        description="Visible",
        get=lambda self: self.get_value("Visible", True),
        set=lambda self, value: self.set_value(value, "Visible"),
    )  # type: ignore
    CastShadows: BoolProperty(
        default=True,
        description="CastShadows",
        get=lambda self: self.get_value("CastShadows", True),
        set=lambda self, value: self.set_value(value, "CastShadows"),
    )  # type: ignore

    ############################
    def get_value(self, key, default):
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return default
            #
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data.light_prop, key)
        else:
            return self.get(key, default)

    def set_value(self, value, key):
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return
            #
            for ent in selected_entities:
                ent_data = ent.amagate_data.get_entity_data()
                ent_data.light_prop[key] = value
        else:
            self[key] = value


# 实体属性
class EntityProperty(bpy.types.PropertyGroup):
    target: StringProperty(default="UI")  # type: ignore
    has_fire: BoolProperty(default=False)  # type: ignore
    has_light: BoolProperty(default=False)  # type: ignore
    # 装备库存
    equipment_inv: CollectionProperty(type=EntityCollection)  # type: ignore
    # 道具库存
    prop_inv: CollectionProperty(type=EntityCollection)  # type: ignore

    Kind: StringProperty(get=lambda self: self.get_kind("Kind", ""), set=lambda self, value: self.set_kind(value, "Kind"))  # type: ignore
    Name: StringProperty(
        name="Name",
        description="Entity Name",
        default="",
        get=lambda self: self.get_name(),
        set=lambda self, value: self.set_name(value),
    )  # type: ignore
    # Position: FloatVectorProperty(
    #     name="Position",
    #     description="Entity Position",
    #     subtype="XYZ",
    #     default=(0.0, 0.0, 0.0),
    # )  # type: ignore
    ObjType: EnumProperty(
        translation_context="ObjType",
        items=[
            (str(i), v, "")
            for i, v in enumerate(
                (
                    "Person",
                    "Weapon",
                    "Physic",
                    "Arrow",
                    "Actor",
                    "None",
                    "Assigned By Script",
                )
            )
        ],
        get=lambda self: self.get_objtype(),
        set=lambda self, value: self.set_objtype(value),
    )  # type: ignore
    #
    Alpha: FloatProperty(
        default=1.0,
        min=0,
        max=1,
        description="Opacity",
        get=lambda self: self.get_value("Alpha", 1),
        set=lambda self, value: self.set_value(value, "Alpha"),
    )  # type: ignore
    # Scale: FloatProperty(default=1.0, min=0.01, soft_max=10)  # type: ignore
    SelfIlum: FloatProperty(
        default=0.0,
        min=-1,
        max=1,
        description="Self Illumination",
        get=lambda self: self.get_value("SelfIlum", 0),
        set=lambda self, value: self.set_value(value, "SelfIlum"),
    )  # type: ignore
    # 仅物理类型可用该属性
    Static: BoolProperty(
        default=False,
        description="Static",
        get=lambda self: self.get_value("Static", False),
        set=lambda self, value: self.set_value(value, "Static"),
    )  # type: ignore
    CastShadows: BoolProperty(
        default=True,
        description="CastShadows",
        get=lambda self: self.get_value("CastShadows", True),
        set=lambda self, value: self.set_value(value, "CastShadows"),
    )  # type: ignore
    # 实例化数据
    instance_data: BoolProperty(
        default=True,
        get=lambda self: self.get_value("instance_data", True),
        set=lambda self, value: self.set_value(value, "instance_data"),
    )  # type: ignore

    Animation: StringProperty(
        default="",
        get=lambda self: self.get_value("Animation", ""),
        set=lambda self, value: self.set_value(value, "Animation"),
        description="Name of the animation created by Bladex.LoadSampledAnimation; the game will crash if it does not exist or if the skeleton does not match",
    )  # type: ignore

    #
    skin: StringProperty(
        get=lambda self: self.get_kind("skin", ""),
        set=lambda self, value: self.set_kind(value, "skin"),
    )  # type: ignore
    Life: IntProperty(
        min=0,
        description=pgettext("Life", "Property"),
        get=lambda self: self.get_value("Life", 0),
        set=lambda self, value: self.set_value(value, "Life"),
    )  # type: ignore
    Life_Enabled: BoolProperty(
        get=lambda self: self.get_value("Life_Enabled", False),
        set=lambda self, value: self.set_value(value, "Life_Enabled"),
    )  # type: ignore
    Level: IntProperty(
        default=0,
        min=0,
        get=lambda self: self.get_value("Level", 0),
        set=lambda self, value: self.set_value(value, "Level"),
    )  # type: ignore
    Angle: FloatProperty(
        default=0.0,
        subtype="ANGLE",
        precision=2,
        step=100,
        get=lambda self: self.get_value("Angle", 0),
        set=lambda self, value: self.set_value(value, "Angle"),
    )  # type: ignore
    SetOnFloor: BoolProperty(
        default=True,
        description="Set on Floor",
        get=lambda self: self.get_value("SetOnFloor", True),
        set=lambda self, value: self.set_value(value, "SetOnFloor"),
    )  # type: ignore
    Hide: BoolProperty(
        description="Hide",
        default=False,
        get=lambda self: self.get_value("Hide", False),
        set=lambda self, value: self.set_value(value, "Hide"),
    )  # type: ignore
    Blind: BoolProperty(
        description="Blind",
        default=False,
        get=lambda self: self.get_value("Blind", False),
        set=lambda self, value: self.set_value(value, "Blind"),
    )  # type: ignore
    Deaf: BoolProperty(
        description="Deaf",
        default=False,
        get=lambda self: self.get_value("Deaf", False),
        set=lambda self, value: self.set_value(value, "Deaf"),
    )  # type: ignore
    Freeze: BoolProperty(
        description="Freeze",
        default=False,
        get=lambda self: self.get_value("Freeze", False),
        set=lambda self, value: self.set_value(value, "Freeze"),
    )  # type: ignore

    #
    # Orientation: FloatVectorProperty(subtype="QUATERNION")  # type: ignore
    #
    FiresIntensity: IntProperty(
        default=5,
        min=0,
        soft_max=45,
        name="Fires Intensity",
        get=lambda self: self.get_value("FiresIntensity", 5),
        set=lambda self, value: self.set_value(value, "FiresIntensity"),
    )  # type: ignore
    #
    light_prop: PointerProperty(type=LightProperty)  # type: ignore
    # 可燃的
    Burnable: BoolProperty(
        default=False,
        get=lambda self: self.get_value("Burnable", False),
        set=lambda self, value: self.set_value(value, "Burnable"),
    )  # type: ignore
    BurnTime: FloatProperty(
        default=6,
        min=0,
        get=lambda self: self.get_value("BurnTime", 6),
        set=lambda self, value: self.set_value(value, "BurnTime"),
        description="Explodes after burning for a specified duration; if set to 0, it will continue burning indefinitely",
    )  # type: ignore
    DestroyTimeAfterBurn: FloatProperty(
        default=12,
        min=0,
        get=lambda self: self.get_value("DestroyTimeAfterBurn", 12),
        set=lambda self, value: self.set_value(value, "DestroyTimeAfterBurn"),
        description="Destruction time (counted after exploding); if set to 0, it will not be destroyed",
    )  # type: ignore

    # 可破坏的
    Breakable: BoolProperty(
        default=False,
        get=lambda self: self.get_value("Breakable", False),
        set=lambda self, value: self.set_value(value, "Breakable"),
    )  # type: ignore
    PiecesDestroyTime: FloatProperty(
        default=12,
        min=0,
        get=lambda self: self.get_value("PiecesDestroyTime", 12),
        set=lambda self, value: self.set_value(value, "PiecesDestroyTime"),
        description="Destruction time for pieces (timed after physical stillness), if set to 0, it will not be destroyed",
    )  # type: ignore
    DestroyTime: FloatProperty(
        default=100,
        min=0,
        get=lambda self: self.get_value("DestroyTime", 100),
        set=lambda self, value: self.set_value(value, "DestroyTime"),
        description="Main body destruction time; if set to 0, it will not be destroyed",
    )  # type: ignore
    contained_item: CollectionProperty(type=EntityCollection)  # type: ignore
    active_entity_note: BoolProperty(name="", description="This feature is only used for active entity", get=lambda self: False, set=lambda self, value: None)  # type: ignore

    # 火炬可用
    torch_usable: BoolProperty(
        default=False,
        get=lambda self: self.get_value("torch_usable", False),
        set=lambda self, value: self.set_value(value, "torch_usable"),
    )  # type: ignore
    torch_light_int: FloatProperty(
        default=3.0,
        get=lambda self: self.get_value("torch_light_int", 3.0),
        set=lambda self, value: self.set_value(value, "torch_light_int"),
        description="Light intensity after ignition",
    )  # type: ignore
    torch_fire_int: FloatProperty(
        default=3.0,
        get=lambda self: self.get_value("torch_fire_int", 3.0),
        set=lambda self, value: self.set_value(value, "torch_fire_int"),
        description="Flame intensity after ignition",
    )  # type: ignore
    torch_life: FloatProperty(
        default=-1,
        get=lambda self: self.get_value("torch_life", -1),
        set=lambda self, value: self.set_value(value, "torch_life"),
        description="Lifetime after ignition",
    )  # type: ignore

    ############################
    # 清空库存
    def clear_inv(self):
        scene_data = bpy.context.scene.amagate_data
        ent_data = self
        for inv in (ent_data.equipment_inv, ent_data.prop_inv):
            for item in inv:
                ag_utils.delete_entity(ent=item.obj)
            inv.clear()

    # 清空内含物
    def clear_contained(self):
        scene_data = bpy.context.scene.amagate_data
        ent_data = self
        for item in ent_data.contained_item:
            ag_utils.delete_entity(ent=item.obj)
        ent_data.contained_item.clear()

    # 清理已删除子物体
    def clear_deleted_children(self):
        ent_data = self
        for coll_prop in (
            ent_data.equipment_inv,
            ent_data.prop_inv,
            ent_data.contained_item,
        ):
            for item_idx in range(len(coll_prop) - 1, -1, -1):
                item = coll_prop[item_idx]
                obj = item.obj  # type: Object
                if not obj:
                    coll_prop.remove(item_idx)

    ############################
    def get_kind(self, key, default):
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return ""
            #
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data, key)
        else:
            return self.get(key, "")

    def set_kind(self, value, key):
        if self.target == "UI":
            pass
        else:
            self[key] = value

    ############################
    def get_name(self):
        key = "Name"
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return ""
            #
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data, key)
        else:
            return self.get(key, "")

    def set_name(self, value):
        key = "Name"
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return
            if value == "":
                return
            #
            if len(selected_entities) != 1:
                start = 1
                for ent in selected_entities:
                    ent_data = ent.amagate_data.get_entity_data()
                    new_value = f"{value}_{start}"
                    setattr(ent_data, key, new_value)
                    start += 1
            else:
                ent = active_entity
                ent_data = ent.amagate_data.get_entity_data()
                setattr(ent_data, key, value)
            #
            data.area_redraw("OUTLINER")
            # bpy.ops.ed.undo_push(message="Change Name")
        else:
            if value == "":
                return
            curr_value = self.get(key)
            if curr_value == value:
                return

            ent2 = scene_data["EntityManage"].get(value)  # type: Object

            self[key] = value
            ent = self.id_data  # type: Object
            ent.rename(value, mode="ALWAYS")
            scene_data["EntityManage"][value] = ent

            if ent2 is not None:
                ent_data2 = ent2.amagate_data.get_entity_data()
                if not curr_value:
                    curr_value = get_name(context, f"{ent_data2.Kind}_")
                scene_data["EntityManage"][curr_value] = ent2
                ent_data2[key] = curr_value
                ent2.rename(curr_value, mode="ALWAYS")
            elif curr_value and scene_data["EntityManage"].get(curr_value) == ent:
                scene_data["EntityManage"].pop(curr_value)

            # 同步库存物体名称
            inventories = (self.equipment_inv, self.prop_inv)
            suffix = ("_Equip_", "_Prop_")
            for idx in (0, 1):
                inv = inventories[idx]
                for item in inv:
                    obj = item.obj  # type: Object
                    if not obj:
                        continue

                    obj_name = get_name(context, f"{self.Name}{suffix[idx]}")
                    obj.amagate_data.get_entity_data().Name = obj_name

    ############################
    def get_objtype(self):
        key = "ObjType"
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return -1
            #
            ent_data = active_entity.amagate_data.get_entity_data()
            return int(getattr(ent_data, key))
        else:
            return self.get(key, -1)

    def set_objtype(self, value):
        key = "ObjType"
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return
            #
            enum_items_static_ui = self.bl_rna.properties[key].enum_items_static_ui  # type: ignore
            identifier = enum_items_static_ui[value].identifier
            for ent in selected_entities:
                ent_data = ent.amagate_data.get_entity_data()
                setattr(ent_data, key, identifier)
            # bpy.ops.ed.undo_push(message="Change Object Type")
        else:
            if self.get(key) == value:
                return

            ent = self.id_data  # type: Object
            ent_data = self
            if ent_data.get(key) is not None:
                enum_items_static_ui = self.bl_rna.properties[key].enum_items_static_ui  # type: ignore
                curr_type = enum_items_static_ui[ent_data[key]].name
                # 切换到Person
                if enum_items_static_ui[value].name == "Person":
                    quat = self.set_angle(ent_data.Angle)
                    ent.rotation_euler = quat.to_euler("XYZ")
                    # 清空内含物
                    self.clear_contained()
                    self.Burnable = False
                    self.Breakable = False
                    self.torch_usable = False
                # 从Person切换到其他
                elif curr_type == "Person":
                    ent.rotation_euler = 0, 0, 0
                    # 清空库存
                    self.clear_inv()
                # 从Physic切换到其它
                if curr_type == "Physic":
                    self.Static = False
            #
            self[key] = value

    ############################
    @staticmethod
    def set_angle(angle):
        return Quaternion((0, 0, 1), angle) @ Quaternion((0, 0, 1), math.pi) @ Quaternion((1, 0, 0), math.pi * 0.5)  # type: ignore

    ############################
    def get_value(self, key, default):
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return default
            #
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data, key)
        else:
            return self.get(key, default)

    def set_value(self, value, key):
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities, active_entity = SELECTED_ENTITIES, ACTIVE_ENTITY
            if not active_entity:
                return
            #
            for ent in selected_entities:
                ent_data = ent.amagate_data.get_entity_data()
                setattr(ent_data, key, value)
            # bpy.ops.ed.undo_push(message="Change Property")
        else:
            self[key] = value
            #
            ent = self.id_data  # type: Object
            if key == "Angle":
                quat = self.set_angle(value)
                ent.rotation_euler = quat.to_euler("XYZ")
            elif key == "CastShadows":
                ent.visible_shadow = value
            elif key == "Breakable":
                if not value:
                    self.clear_contained()


############################
############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and any(issubclass(cls, parent) for parent in class_tuple)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
