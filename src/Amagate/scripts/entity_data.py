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

# 武器库存
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
    Intensity: FloatProperty(default=2.5)  # type: ignore
    Precision: FloatProperty(default=0.03125)  # type: ignore
    Color: FloatVectorProperty(subtype="COLOR", default=((255 / 255, 196 / 255, 128 / 255)))  # type: ignore
    Flick: BoolProperty()  # type: ignore
    Visible: BoolProperty()  # type: ignore
    CastShadows: BoolProperty(default=True)  # type: ignore


# 实体属性
class EntityProperty(bpy.types.PropertyGroup):
    target: StringProperty(default="UI")  # type: ignore
    Name: StringProperty(
        name="Name",
        description="Entity Name",
        default="",
    )  # type: ignore
    Kind: StringProperty()  # type: ignore
    # Position: FloatVectorProperty(
    #     name="Position",
    #     description="Entity Position",
    #     subtype="XYZ",
    #     default=(0.0, 0.0, 0.0),
    # )  # type: ignore
    EntType: EnumProperty(
        translation_context="EntType",
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
    )  # type: ignore
    #
    Static: BoolProperty()  # type: ignore
    Alpha: FloatProperty(default=1.0)  # type: ignore
    CastShadows: BoolProperty(default=True)  # type: ignore
    SelfIlum: FloatProperty(default=0.0)  # type: ignore
    Blind: BoolProperty(default=False)  # type: ignore
    Deaf: BoolProperty(default=False)  # type: ignore
    Freeze: BoolProperty(default=False)  # type: ignore

    #
    Level: IntProperty()  # type: ignore
    Angle: FloatProperty()  # type: ignore
    Scale: FloatProperty(default=1.0)  # type: ignore
    # Orientation: FloatVectorProperty(subtype="QUATERNION")  # type: ignore
    SetOnFloor: BoolProperty()  # type: ignore
    #
    FiresIntensity: IntProperty(default=5)  # type: ignore
    #
    light_prop: PointerProperty(type=LightProperty)  # type: ignore
    ambient_color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0, 0, 0),
    )  # type: ignore


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
