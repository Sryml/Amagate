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
    selected_entities = SELECTED_ENTITIES
    if not selected_entities:
        return True
    #
    active_entity = selected_entities[0]
    ent_data = active_entity.amagate_data.get_entity_data()
    active_value = eval(f"ent_data.{attr}")
    for i in range(1, len(selected_entities)):
        entity = selected_entities[i]
        ent_data = entity.amagate_data.get_entity_data()
        if active_value != eval(f"ent_data.{attr}"):
            return False
    return True


def get_equipment(this, context):
    return EQUIPMENT_ENUM


def get_equipment_search(this, context):
    ent_enum = EQUIPMENT_ENUM.copy()
    for i in range(len(ent_enum) - 1, -1, -1):
        if ent_enum[i][0] == "":
            ent_enum.pop(i)
        else:
            ent_enum[i] = (
                ent_enum[i][0],
                f"{ent_enum[i][1]} - {ent_enum[i][2]}",
                ent_enum[i][2],
                ent_enum[i][3],
                ent_enum[i][4],
            )
    return ent_enum


def add_equipment(this, context: Context):
    ag_utils.simulate_keypress(27)
    bpy.app.timers.register(add_equipment_timer, first_interval=0.03)


def add_equipment_timer():
    from . import L3D_operator as OP_L3D

    context = bpy.context
    wm_data = context.window_manager.amagate_data
    inter_name = bpy.types.UILayout.enum_item_description(
        wm_data, "equipment_enum", wm_data.equipment_enum
    )
    _, inv_ent = OP_L3D.OT_EntityAddToScene.add(None, context, inter_name)

    ent = SELECTED_ENTITIES[0]
    ent_data = ent.amagate_data.get_entity_data()
    item = ent_data.equipment_inv.add()
    item.obj = inv_ent
    wm_data.active_equipment = len(ent_data.equipment_inv) - 1

    inv_ent.visible_camera = False
    inv_ent.visible_shadow = False
    inv_ent.location = ent.location + Vector((0, 0, 1.2))


def gen_equipment():
    global EQUIPMENT_ENUM
    EQUIPMENT_ENUM = []
    count = 0

    for cat in (
        "Characters",
        "Props",
        "1H Weapons",
        "2H Weapons",
        "Shields & Bows",
        "Others",
        "Pieces",
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
        # enum.insert(0, ("", cat, ""))
        EQUIPMENT_ENUM.extend(enum)


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
            icon_id = next(i[3] for i in data.ENT_ENUM if i[2] == ent_data.Kind)
            row = layout.row()
            row.label(text=ent_data.Name, icon_value=icon_id)
            row.operator(OP_Entity.OT_Equipment_Select.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False).obj_name = ent.name  # type: ignore


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
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return default
            #
            active_entity = selected_entities[0]
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data.light_prop, key)
        else:
            return self.get(key, default)

    def set_value(self, value, key):
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
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

    Kind: StringProperty(description="Read Only", get=lambda self: self.get_kind(), set=lambda self, value: self.set_kind(value))  # type: ignore
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

    Animation: StringProperty(
        default="",
        get=lambda self: self.get_value("Animation", ""),
        set=lambda self, value: self.set_value(value, "Animation"),
        description="Name of the animation created by Bladex.LoadSampledAnimation; the game will crash if it does not exist or if the skeleton does not match",
    )  # type: ignore

    Life: IntProperty(
        min=0,
        description=pgettext("Life", "Property"),
        get=lambda self: self.get_value("Life", 0),
        set=lambda self, value: self.set_value(value, "Life"),
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
        default=True,
        get=lambda self: self.get_value("Hide", True),
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
    #
    ambient_color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0, 0, 0),
    )  # type: ignore

    ############################
    def get_kind(self):
        key = "Kind"
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return ""
            #
            active_entity = selected_entities[0]
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data, key)
        else:
            return self.get(key, "")

    def set_kind(self, value):
        key = "Kind"
        if self.target == "UI":
            pass
        else:
            self[key] = value

    ############################
    def get_name(self):
        key = "Name"
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return ""
            #
            active_entity = selected_entities[0]
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data, key)
        else:
            return self.get(key, "")

    def set_name(self, value):
        key = "Name"
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return
            if value == "":
                return
            #
            if len(selected_entities) != 1:
                start = 1
                for ent in selected_entities:
                    ent_data = ent.amagate_data.get_entity_data()
                    new_value = f"{value}_{start}"
                    start += 1
                    curr_value = ent_data[key]
                    if new_value == curr_value:
                        continue
                    #
                    ent2 = scene_data["EntityManage"].get(new_value)
                    if ent2 is not None:
                        ent_data2 = ent2.amagate_data.get_entity_data()
                        scene_data["EntityManage"][curr_value] = ent2
                        setattr(ent_data2, key, curr_value)
                    else:
                        scene_data["EntityManage"].pop(curr_value)
                    scene_data["EntityManage"][new_value] = ent
                    setattr(ent_data, key, new_value)
            else:
                ent = selected_entities[0]
                ent_data = ent.amagate_data.get_entity_data()
                curr_value = ent_data[key]
                if value == curr_value:
                    return
                #
                ent2 = scene_data["EntityManage"].get(value)
                if ent2 is not None:
                    ent_data2 = ent2.amagate_data.get_entity_data()
                    scene_data["EntityManage"][curr_value] = ent2
                    setattr(ent_data2, key, curr_value)
                else:
                    scene_data["EntityManage"].pop(curr_value)
                scene_data["EntityManage"][value] = ent
                setattr(ent_data, key, value)
            #
            data.area_redraw("OUTLINER")
        else:
            self[key] = value
            ent = self.id_data  # type: Object
            ent.rename(value, mode="ALWAYS")

    ############################
    def get_objtype(self):
        key = "ObjType"
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return -1
            #
            active_entity = selected_entities[0]
            ent_data = active_entity.amagate_data.get_entity_data()
            return int(getattr(ent_data, key))
        else:
            return self.get(key, -1)

    def set_objtype(self, value):
        key = "ObjType"
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return
            #
            for ent in selected_entities:
                ent_data = ent.amagate_data.get_entity_data()
                if ent_data[key] == value:
                    continue
                #
                enum_items_static_ui = self.bl_rna.properties[key].enum_items_static_ui  # type: ignore
                curr_type = enum_items_static_ui[ent_data[key]].name
                if enum_items_static_ui[value].name == "Person":
                    quat = self.set_angle(ent_data.Angle)
                    ent.rotation_euler = quat.to_euler("XYZ")
                elif curr_type == "Person":
                    ent.rotation_euler = 0, 0, 0
                #
                ent_data[key] = value
        else:
            ent = self.id_data  # type: Object
            ent_data = ent.amagate_data.get_entity_data()
            if ent_data.get(key):
                enum_items_static_ui = self.bl_rna.properties[key].enum_items_static_ui  # type: ignore
                curr_type = enum_items_static_ui[ent_data[key]].name
                if enum_items_static_ui[value].name == "Person":
                    quat = self.set_angle(ent_data.Angle)
                    ent.rotation_euler = quat.to_euler("XYZ")
                elif curr_type == "Person":
                    ent.rotation_euler = 0, 0, 0
            #
            self[key] = value

    ############################
    @staticmethod
    def set_angle(angle):
        return Quaternion((0, 0, 1), angle) @ Quaternion((0, 0, 1), math.pi) @ Quaternion((1, 0, 0), math.pi * 0.5)  # type: ignore

    ############################
    def get_value(self, key, default):
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return default
            #
            active_entity = selected_entities[0]
            ent_data = active_entity.amagate_data.get_entity_data()
            return getattr(ent_data, key)
        else:
            return self.get(key, default)

    def set_value(self, value, key):
        context = bpy.context
        scene_data = context.scene.amagate_data
        if self.target == "UI":
            selected_entities = SELECTED_ENTITIES
            if not selected_entities:
                return
            #
            for ent in selected_entities:
                ent_data = ent.amagate_data.get_entity_data()
                setattr(ent_data, key, value)
        else:
            self[key] = value
            #
            ent = self.id_data  # type: Object
            ent_data = ent.amagate_data.get_entity_data()
            if key == "Angle":
                quat = self.set_angle(value)
                ent.rotation_euler = quat.to_euler("XYZ")
            elif key == "CastShadows":
                ent.visible_shadow = value


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
