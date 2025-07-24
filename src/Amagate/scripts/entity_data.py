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
############################ 模板列表
############################


############################
############################ Collection Props
############################


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
                    "Static",
                    "Arrow",
                    "Actor",
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
        get=lambda self: self.get_value("Static", False),
        set=lambda self, value: self.set_value(value, "Static"),
    )  # type: ignore
    CastShadows: BoolProperty(default=True, get=lambda self: self.get_value("CastShadows", True), set=lambda self, value: self.set_value(value, "CastShadows"))  # type: ignore

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
                ent_data[key] = value
        else:
            self[key] = value

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
                ent_data[key] = value
                if key == "CastShadows":
                    ent.visible_shadow = value
        else:
            self[key] = value


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
