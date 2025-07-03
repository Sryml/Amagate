# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import sys
import os
import math
import pickle
import struct
import contextlib
import shutil
import threading
import time
from pprint import pprint
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

import bpy
import bmesh
from bpy.app.translations import pgettext
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
from mathutils import *  # type: ignore

from . import data
from . import ag_utils


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


############################
logger = data.logger


############################
############################ 编辑操作
############################


# 创建集合
class OT_CreateColl(bpy.types.Operator):
    bl_idname = "amagate.ent_create_coll"
    bl_label = "Add Collection"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        coll_name = data.get_coll_name("Blade_Object_")
        coll = bpy.data.collections.new(coll_name)
        context.scene.collection.children.link(coll)
        return {"FINISHED"}


# 添加锚点
class OT_AddAnchor(bpy.types.Operator):
    bl_idname = "amagate.ent_add_anchor"
    bl_label = "Add Anchor"
    bl_options = {"INTERNAL"}

    action: EnumProperty(
        name="",
        description="",
        translation_context="EntAnchor",
        items=[
            ("", "Object", ""),
            ("1", "1H_R", "Blade_Anchor_1H_R"),
            ("2", "1H_L", "Blade_Anchor_1H_L"),
            ("3", "2H", "Blade_Anchor_2H"),
            ("4", "Inv", "Blade_Anchor_Inv"),
            ("5", "Back", "Blade_Anchor_Back"),
            ("6", "Shield", "Blade_Anchor_Shield"),
            ("7", "Crush", "Blade_Anchor_Crush"),
            ("", "Person", ""),
            ("8", "R_Hand", "Blade_Anchor_R_Hand"),
            ("9", "L_Hand", "Blade_Anchor_L_Hand"),
            ("10", "2O", "Blade_Anchor_2O"),
            ("11", "ViewPoint", "Blade_Anchor_ViewPoint"),
        ],
    )  # type: ignore

    def execute(self, context: Context):
        # print(f"action: {self.action}")
        key = bpy.types.UILayout.enum_item_description(self, "action", self.action)
        anchor = bpy.data.objects.new(key, None)
        anchor.empty_display_size = 0.1
        anchor.empty_display_type = "ARROWS"
        data.link2coll(anchor, context.collection)
        return {"FINISHED"}


# 添加组件
class OT_AddComponent(bpy.types.Operator):
    bl_idname = "amagate.ent_add_component"
    bl_label = "Add Component"
    bl_options = {"INTERNAL"}

    action: EnumProperty(
        name="",
        description="",
        translation_context="EntComponent",
        items=[
            ("1", "Edge", "Blade_Edge_1"),
            ("2", "Spike", "Blade_Spike_1"),
            ("3", "Trail", "Blade_Trail_1"),
            ("4", "Fire", "B_Fire_Fuego_1"),
            ("5", "Light", "Blade_Light_1"),
        ],
    )  # type: ignore

    def execute(self, context: Context):
        # print(f"action: {self.action}")
        key = bpy.types.UILayout.enum_item_description(self, "action", self.action)
        obj_name = data.get_object_name(key[:-1])
        if key == "Blade_Light_1":
            anchor = bpy.data.objects.new(obj_name, None)
            anchor.empty_display_size = 0.1
            anchor.empty_display_type = "ARROWS"
            data.link2coll(anchor, context.collection)
        else:
            filepath = os.path.join(data.ADDON_PATH, "bin/ent_component.dat")
            mesh_dict = pickle.load(open(filepath, "rb"))
            mesh_data = mesh_dict[key]
            #
            bm = bmesh.new()
            verts = []
            for co in mesh_data["vertices"]:
                verts.append(bm.verts.new(co))
            for idx in mesh_data["edges"]:
                bm.edges.new([verts[i] for i in idx])
            for idx in mesh_data["faces"]:
                bm.faces.new([verts[i] for i in idx])
            #
            mesh = bpy.data.meshes.new(obj_name)
            bm.to_mesh(mesh)
            bm.free()
            obj = bpy.data.objects.new(obj_name, mesh)  # type: Object # type: ignore
            obj_data = obj.amagate_data
            obj_data.ent_comp_type = int(self.action)
            data.link2coll(obj, context.collection)
        return {"FINISHED"}


# 预设
class OT_Presets(bpy.types.Operator):
    bl_idname = "amagate.ent_presets"
    bl_label = "Presets"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        # print(f"action: {self.action}")
        return {"FINISHED"}


############################
############################ 导入操作
############################


############################
############################ 导出操作
############################


class OT_ExportBOD(bpy.types.Operator):
    bl_idname = "amagate.export_bod"
    bl_label = "Export BOD"
    bl_options = {"INTERNAL"}

    main: BoolProperty(default=False)  # type: ignore
    action: EnumProperty(
        name="",
        description="",
        items=[
            # ("1", "Export BOD", ""),
            ("2", "Export BOD (Visible Only)", ""),
        ],
    )  # type: ignore

    def execute(self, context: Context):
        # print(f"main: {self.main}, action: {self.action}")
        coll_list = []
        for coll in bpy.data.collections:
            # 判断名称前缀
            if not coll.name.lower().startswith("blade_object_"):
                continue
            # 判断是否有引用
            if coll.users - coll.use_fake_user == 0:
                continue
            # 判断是否有物体
            if len(coll.objects) == 0:
                continue

            if not self.main:
                # 仅可见
                if self.action == "2":
                    if not coll.objects[0].visible_get():
                        continue
            coll_list.append(coll)
            break
        #
        if not coll_list:
            self.report(
                {"INFO"}, "No collection with the prefix `Blade_Object_` was found"
            )
            return {"CANCELLED"}
        #
        for coll in coll_list:
            # 导出BOD
            objects = []

        return {"FINISHED"}


############################
############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.Operator)
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
