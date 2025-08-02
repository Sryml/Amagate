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
from pathlib import Path
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

from . import data, entity_data
from . import ag_utils


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection


############################
logger = data.logger

unpack = ag_utils.unpack

############################


# 确保材质
def ensure_material(tex: Image) -> bpy.types.Material:
    name = tex.name
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new("")
        mat.rename(name, mode="ALWAYS")
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))
        data.import_nodes(mat, nodes_data["Export.EntityTex"])
        mat.use_fake_user = True
        mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
        mat.use_backface_culling = True

    return mat


# 获取实体集合和主体
def get_ent_data(
    ent_coll=None, check_visible=True
) -> tuple[Collection | None, Object | None, bool, bool]:
    entity = None
    has_fire = False
    has_light = False
    if ent_coll is None:
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

            ent_coll = coll
            break
    #
    if ent_coll is None:
        return ent_coll, entity, has_fire, has_light
    #
    prefixes = (
        "blade_edge_",
        "blade_spike_",
        "blade_trail_",
        "b_fire_fuego_",
    )
    for obj in ent_coll.all_objects:
        if check_visible and not obj.visible_get():
            continue
        #
        if obj.type == "MESH":
            if entity is None and not obj.name.lower().startswith(prefixes):
                entity = obj
            elif obj.name.lower().startswith("b_fire_fuego_"):
                has_fire = True
        elif obj.type == "EMPTY":
            if obj.name.lower().startswith("blade_light_"):
                has_light = True
    #
    return ent_coll, entity, has_fire, has_light


############################
############################ 预制体面板
############################


# 库存选择
class OT_Inventory_Select(bpy.types.Operator):
    bl_idname = "amagate.inventory_select"
    bl_label = "Select Item"
    bl_description = ""
    bl_options = {"INTERNAL"}

    obj_name: StringProperty(default="")  # type: ignore

    # @classmethod
    # def poll(cls, context: Context):
    #     if entity_data.SELECTED_ENTITIES:
    #         return True
    #     return False

    def execute(self, context: Context):
        if context.view_layer.objects.get(self.obj_name) is not None:
            ag_utils.select_active(context, bpy.data.objects[self.obj_name])
            bpy.ops.ed.undo_push(message="Select Item")
        return {"FINISHED"}


# Kind搜索
class OT_Entity_Kind_Search(bpy.types.Operator):
    bl_idname = "amagate.entity_kind_search"
    bl_label = "Search"
    bl_description = ""
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    @classmethod
    def poll(cls, context: Context):
        if entity_data.SELECTED_ENTITIES:
            return True
        return False

    enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_ent_enum_search,
    )  # type: ignore

    def execute(self, context: Context):
        from . import L3D_operator as OP_L3D

        selected_entities = entity_data.SELECTED_ENTITIES
        if not selected_entities:
            return
        #
        inter_name = bpy.types.UILayout.enum_item_description(self, "enum", self.enum)
        for ent in selected_entities:
            OP_L3D.OT_EntityCreate.add(None, context, inter_name, entity=ent)

        data.region_redraw("UI")
        bpy.ops.ed.undo_push(message="Change Kind")
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        context.window_manager.invoke_search_popup(self)
        return {"FINISHED"}


############################ 装备库存


class Inventory:
    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if (
                bpy.types.UILayout.enum_item_name(ent_data, "ObjType", ent_data.ObjType)
                == "Person"
            ):
                return True
        return False


# 添加装备
class OT_Equipment_Add(bpy.types.Operator, Inventory):
    bl_idname = "amagate.equipment_add"
    bl_label = "Add Inventory"
    bl_description = "Hold down shift to search"
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    row_number: IntProperty(default=40)  # type: ignore

    enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_equipment_search,
    )  # type: ignore

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        wm_data.equipment_enum = self.enum
        # data.region_redraw("UI")
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        if event.shift:
            context.window_manager.invoke_search_popup(self)
            return {"FINISHED"}
        ent_enum = entity_data.get_equipment(None, None)
        return context.window_manager.invoke_popup(
            self, width=(len(ent_enum) // self.row_number + 1) * 180
        )

    def draw(self, context: Context):
        layout = self.layout
        wm_data = context.window_manager.amagate_data
        scene_data = context.scene.amagate_data
        ent_enum = entity_data.get_equipment(None, None)
        row = layout.row(align=False)
        row_number = self.row_number
        for idx, item in enumerate(ent_enum):
            if idx % row_number == 0:
                col = row.column(align=True, heading_ctxt="Entity")
            col.prop_enum(wm_data, "equipment_enum", item[0])


# 移除装备
class OT_Equipment_Remove(bpy.types.Operator):
    bl_idname = "amagate.equipment_remove"
    bl_label = "Remove Inventory"
    bl_description = "Remove selected equipment"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if len(ent_data.equipment_inv) != 0:
                return True
        return False

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        wm_data = context.window_manager.amagate_data
        selected_entities = entity_data.SELECTED_ENTITIES
        ent = entity_data.ACTIVE_ENTITY
        ent_data = ent.amagate_data.get_entity_data()
        index = wm_data.active_equipment
        if index < 0 or index >= len(ent_data.equipment_inv):
            return {"FINISHED"}

        item = ent_data.equipment_inv[index]
        ag_utils.delete_entity(ent=item.obj)
        ent_data.equipment_inv.remove(index)
        if index >= len(ent_data.equipment_inv):
            new_index = max(len(ent_data.equipment_inv) - 1, 0)
        else:
            new_index = index
        wm_data.active_equipment = new_index

        bpy.ops.ed.undo_push(message="Remove Inventory")
        return {"FINISHED"}


# 移动装备
class OT_Equipment_Move(bpy.types.Operator):
    bl_idname = "amagate.equipment_move"
    bl_label = "Move Inventory"
    bl_description = "Move selected equipment"
    bl_options = {"INTERNAL"}

    direction: EnumProperty(
        items=[
            ("UP", "Up", ""),
            ("DOWN", "Down", ""),
        ],
    )  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if len(ent_data.equipment_inv) > 1:
                return True
        return False

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        selected_entities = entity_data.SELECTED_ENTITIES
        ent = entity_data.ACTIVE_ENTITY
        ent_data = ent.amagate_data.get_entity_data()
        index = wm_data.active_equipment
        if index < 0 or index >= len(ent_data.equipment_inv):
            return {"FINISHED"}

        inv_list = ent_data.equipment_inv
        length = len(inv_list)

        if self.direction == "UP":
            new_index = (index - 1) % length
            inv_list.move(index, new_index)
        else:
            new_index = (index + 1) % length
            inv_list.move(index, new_index)

        wm_data.active_equipment = new_index
        bpy.ops.ed.undo_push(message="Move Inventory")
        return {"FINISHED"}


############################ 道具库存


# 添加道具
class OT_Prop_Add(bpy.types.Operator, Inventory):
    bl_idname = "amagate.prop_add"
    bl_label = "Add Inventory"
    bl_description = "Hold down shift to search"
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    row_number: IntProperty(default=25)  # type: ignore

    enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_prop_search,
    )  # type: ignore

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        wm_data.prop_enum = self.enum
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        if event.shift:
            context.window_manager.invoke_search_popup(self)
            return {"FINISHED"}
        ent_enum = entity_data.get_prop(None, None)
        return context.window_manager.invoke_popup(
            self, width=(len(ent_enum) // self.row_number + 1) * 180
        )

    def draw(self, context: Context):
        layout = self.layout
        wm_data = context.window_manager.amagate_data
        scene_data = context.scene.amagate_data
        ent_enum = entity_data.get_prop(None, None)
        row = layout.row(align=False)
        row_number = self.row_number
        for idx, item in enumerate(ent_enum):
            if idx % row_number == 0:
                col = row.column(align=True, heading_ctxt="Entity")
            col.prop_enum(wm_data, "prop_enum", item[0])


# 移除道具
class OT_Prop_Remove(bpy.types.Operator):
    bl_idname = "amagate.prop_remove"
    bl_label = "Remove Inventory"
    bl_description = "Remove selected prop"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if len(ent_data.prop_inv) != 0:
                return True
        return False

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        wm_data = context.window_manager.amagate_data
        selected_entities = entity_data.SELECTED_ENTITIES
        ent = entity_data.ACTIVE_ENTITY
        ent_data = ent.amagate_data.get_entity_data()
        index = wm_data.active_prop
        if index < 0 or index >= len(ent_data.prop_inv):
            return {"FINISHED"}

        item = ent_data.prop_inv[index]
        ag_utils.delete_entity(ent=item.obj)
        ent_data.prop_inv.remove(index)
        if index >= len(ent_data.prop_inv):
            new_index = max(len(ent_data.prop_inv) - 1, 0)
        else:
            new_index = index
        wm_data.active_prop = new_index

        bpy.ops.ed.undo_push(message="Remove Inventory")
        return {"FINISHED"}


# 移动道具
class OT_Prop_Move(bpy.types.Operator):
    bl_idname = "amagate.prop_move"
    bl_label = "Move Inventory"
    bl_description = "Move selected prop"
    bl_options = {"INTERNAL"}

    direction: EnumProperty(
        items=[
            ("UP", "Up", ""),
            ("DOWN", "Down", ""),
        ],
    )  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if len(ent_data.prop_inv) > 1:
                return True
        return False

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        selected_entities = entity_data.SELECTED_ENTITIES
        ent = entity_data.ACTIVE_ENTITY
        ent_data = ent.amagate_data.get_entity_data()
        index = wm_data.active_prop
        if index < 0 or index >= len(ent_data.prop_inv):
            return {"FINISHED"}

        inv_list = ent_data.prop_inv
        length = len(inv_list)

        if self.direction == "UP":
            new_index = (index - 1) % length
            inv_list.move(index, new_index)
        else:
            new_index = (index + 1) % length
            inv_list.move(index, new_index)

        wm_data.active_prop = new_index
        bpy.ops.ed.undo_push(message="Move Inventory")
        return {"FINISHED"}


############################ 容器内物品


# 添加物品
class OT_ContainedItem_Add(bpy.types.Operator, Inventory):
    bl_idname = "amagate.contained_item_add"
    bl_label = "Add Item"
    bl_description = "Hold down shift to search"
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_ent_enum_search,
    )  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if len(ent_data.contained_item) == 0:
                return True
        return False

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        wm_data.contained_item_enum = self.enum
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        if event.shift:
            context.window_manager.invoke_search_popup(self)
            return {"FINISHED"}
        col_number = 7 + (1 if data.E_MANIFEST["Entities"]["Custom"] != {} else 0)
        return context.window_manager.invoke_popup(self, width=col_number * 145)

    def draw(self, context: Context):
        layout = self.layout
        wm_data = context.window_manager.amagate_data
        scene_data = context.scene.amagate_data
        ent_enum = entity_data.get_ent_enum(None, None)
        row = layout.row(align=False)
        for item in ent_enum:
            if item[0] == "":
                col = row.column(align=True, heading=item[1], heading_ctxt="Entity")
            else:
                col.prop_enum(wm_data, "contained_item_enum", item[0])


# 移除物品
class OT_ContainedItem_Remove(bpy.types.Operator):
    bl_idname = "amagate.contained_item_remove"
    bl_label = "Remove Item"
    bl_description = "Remove selected item"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        ent = entity_data.ACTIVE_ENTITY
        if ent is not None:
            ent_data = ent.amagate_data.get_entity_data()
            if len(ent_data.contained_item) != 0:
                return True
        return False

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        wm_data = context.window_manager.amagate_data
        selected_entities = entity_data.SELECTED_ENTITIES
        ent = entity_data.ACTIVE_ENTITY
        ent_data = ent.amagate_data.get_entity_data()
        index = wm_data.active_contained_item
        if index < 0 or index >= len(ent_data.contained_item):
            return {"FINISHED"}

        item = ent_data.contained_item[index]
        ag_utils.delete_entity(ent=item.obj)
        ent_data.contained_item.remove(index)
        if index >= len(ent_data.contained_item):
            new_index = max(len(ent_data.contained_item) - 1, 0)
        else:
            new_index = index
        wm_data.active_contained_item = new_index

        bpy.ops.ed.undo_push(message="Remove Item")
        return {"FINISHED"}


############################


# 库存预览图
class OT_Inventory_Preview(bpy.types.Operator):
    bl_idname = "amagate.inventory_preview"
    bl_label = "Preview"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def get_items(self, context: Context):
        return [("0", "0", "", self.icon_id, 0)]

    Kind: StringProperty(default="")  # type: ignore
    icon_id: IntProperty(default=0)  # type: ignore
    preview: EnumProperty(items=get_items)  # type: ignore

    def execute(self, context: Context):
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        return context.window_manager.invoke_popup(self, width=180)

    def draw(self, context: Context):
        layout = self.layout
        # layout.enabled = False
        layout.prop(self, "Kind", text="Kind")
        layout.template_icon_view(
            self, "preview", show_labels=False, scale=10, scale_popup=1
        )


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
        bpy.ops.ed.undo_push(message="New Collection")
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
        anchor.show_in_front = True
        data.link2coll(anchor, context.collection)
        bpy.ops.ed.undo_push(message="Add Anchor")
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
            obj = bpy.data.objects.new(obj_name, None)  # type: Object # type: ignore
            obj.empty_display_size = 0.1
            obj.empty_display_type = "ARROWS"
            obj.show_in_front = True
            data.link2coll(obj, context.collection)
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
            obj.show_in_front = True
            data.link2coll(obj, context.collection)
        bpy.ops.ed.undo_push(message="Add Component")
        return {"FINISHED"}


# 预设
# class OT_Presets(bpy.types.Operator):
#     bl_idname = "amagate.ent_presets"
#     bl_label = "Presets"
#     bl_options = {"INTERNAL"}

#     def execute(self, context: Context):
#         # print(f"action: {self.action}")
#         return {"FINISHED"}


# 按组选择
class OT_SelectByGroup(bpy.types.Operator):
    bl_idname = "amagate.select_by_group"
    bl_label = "Select By Group"
    bl_options = {"INTERNAL"}

    @staticmethod
    def get_items():
        items = [(str(i), str(i + 1), "") for i in range(32)]
        items.insert(16, ("", "Group", ""))
        items.insert(0, ("", "Group", ""))
        return items

    action: EnumProperty(items=get_items())  # type: ignore

    def execute(self, context: Context):
        index = int(self.action)
        obj = context.object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        edit_bm = bmesh.from_edit_mesh(mesh)
        layer = edit_bm.faces.layers.int.get("amagate_group")
        for face in edit_bm.faces:
            if (face[layer] >> index) & 1:  # type: ignore
                face.select_set(True)

        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

        return {"FINISHED"}


# 按肢解组选择
class OT_SelectByMutilateGroup(bpy.types.Operator):
    bl_idname = "amagate.select_by_mutilate_group"
    bl_label = "Select By Group"
    bl_options = {"INTERNAL"}

    @staticmethod
    def get_items():
        items = [(str(i), str(i + 1), "") for i in range(32)]
        items.insert(16, ("", "Group", ""))
        items.insert(0, ("", "Group", ""))
        return items

    action: EnumProperty(items=get_items())  # type: ignore

    def execute(self, context: Context):
        index = int(self.action)
        obj = context.object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        edit_bm = bmesh.from_edit_mesh(mesh)
        layer = edit_bm.faces.layers.int.get("amagate_mutilation_group")
        # edit_bm.verts.ensure_lookup_table()
        # 取消选择
        # bpy.ops.object.select_all(action="DESELECT")
        for face in edit_bm.faces:
            if (face[layer] >> index) & 1:  # type: ignore
                face.select_set(True)
        # edit_bm.select_flush_mode()
        # edit_bm.select_flush(True)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

        return {"FINISHED"}


# 实体说明
class OT_EntityNote(bpy.types.Operator):
    bl_idname = "amagate.ent_note"
    bl_label = "Entity Note"
    bl_description = "Entity Note"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        wm = context.window_manager
        wm.popup_menu(
            self.draw_menu, title=pgettext("Entity Note", "Operator"), icon="INFO"
        )
        return {"FINISHED"}

    @staticmethod
    def draw_menu(this, context: Context):
        layout = this.layout  # type: bpy.types.UILayout
        column = layout.column()
        column.label(
            text=f"1. {pgettext('All vertices must be assigned to bone vertex groups and can only belong to one bone vertex group')}"
        )
        column.label(
            text=f"2. {pgettext('Do not link lights or flames to bone, as the BOD engine does not support it')}"
        )
        column.separator(factor=1, type="SPACE")


############################
############################ 导入操作
############################


class OT_ImportBOD(bpy.types.Operator):
    bl_idname = "amagate.import_bod"
    bl_label = "Import BOD"
    bl_description = "Import BOD"
    bl_options = {"INTERNAL"}

    # 转换坐标空间
    # from_old_exporter: BoolProperty(name="From Old Exporter", default=True)  # type: ignore
    filter_glob: StringProperty(default="*.bod", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context: Context):
        filepath = self.filepath
        if os.path.splitext(filepath)[1].lower() != ".bod":
            self.report({"ERROR"}, "Not a bod file")
            return {"CANCELLED"}

        self.import_bod(context, filepath)
        return {"FINISHED"}

    @staticmethod
    def import_bod(context: Context, filepath):
        def final():
            ag_utils.select_active(context, entity)  # type: ignore
            for obj in ent_coll.objects:
                if not obj.parent:
                    obj.select_set(True)
            # 调整实体中心
            for obj in context.selected_objects:
                obj.matrix_world.translation += center
            # 纠正方向
            if not transform_space:
                for obj in context.selected_objects:
                    obj.matrix_world = (
                        Matrix.Rotation(-math.pi / 2, 4, "X") @ obj.matrix_world
                    )

            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.object.select_all(action="DESELECT")
            #
            bpy.ops.view3d.view_all(center=True)
            return entity, lack_texture, dup_face

        #
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.space_data.shading.type = "WIREFRAME"  # type: ignore
        #
        lack_texture = False
        dup_face = False
        # 局部空间
        local_space = Matrix.Rotation(-math.pi / 2, 4, "X")
        # local_space_inv = local_space.inverted()
        transform_space = False  # not self.from_old_exporter # XXX 不再需要
        path = os.path.join(data.ADDON_PATH, "bin/ent_component.dat")
        mesh_dict = pickle.load(open(path, "rb"))

        ent_bm = bmesh.new()
        uv_layer = ent_bm.loops.layers.uv.verify()  # 获取或创建UV图层
        bm_verts = []  # type: list[bmesh.types.BMVert]
        bm_verts_dup = {}
        verts_dup_count = 0
        with open(filepath, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size
            # 内部名称
            length = unpack("I", f)[0]
            inter_name = unpack(f"{length}s", f)
            #
            ent_mesh = bpy.data.meshes.new(inter_name)
            entity = bpy.data.objects.new(inter_name, ent_mesh)
            #
            ent_coll = bpy.data.collections.new(
                f"Blade_Object_{inter_name}"
            )  # type: Collection # type: ignore
            context.scene.collection.children.link(ent_coll)
            data.link2coll(entity, ent_coll)
            entity["AG.ambient_color"] = (1.0, 1.0, 1.0)
            # entity.id_properties_ensure()  # 确保属性存在
            entity.id_properties_ui("AG.ambient_color").update(
                subtype="COLOR", min=0.0, max=1.0, default=(1, 1, 1), step=0.1
            )
            # 顶点
            verts_num = unpack("I", f)[0]
            for i in range(verts_num):
                co = Vector(unpack("ddd", f)) / 1000
                # if transform_space:
                #     co.yz = co.z, -co.y
                bm_verts.append(ent_bm.verts.new(co))
                # 跳过法线
                f.seek(24, 1)
            # 面
            faces_num = unpack("I", f)[0]
            for i in range(faces_num):
                vert_idx = unpack("III", f)
                try:
                    face = ent_bm.faces.new([bm_verts[i] for i in vert_idx])
                except:
                    dup_face = True
                    verts = []
                    for i in vert_idx:
                        vert = ent_bm.verts.new(bm_verts[i].co)
                        verts.append(vert)
                        bm_verts_dup.setdefault(i, []).append(
                            verts_num + verts_dup_count
                        )
                        verts_dup_count += 1
                    face = ent_bm.faces.new(verts)
                    bm_verts.extend(verts)
                length = unpack("I", f)[0]
                img_name = unpack(f"{length}s", f)
                uv_list = unpack("ffffff", f)
                if face is not None:
                    uv_list = [
                        (uv_list[0], uv_list[3]),
                        (uv_list[1], uv_list[4]),
                        (uv_list[2], uv_list[5]),
                    ]
                    for idx, loop in enumerate(face.loops):
                        loop[uv_layer].uv = uv_list[idx]
                    #
                    img = bpy.data.images.get(img_name)  # type: Image # type: ignore
                    if img is None:
                        img = bpy.data.images.new(img_name, 256, 256)
                        img.source = "FILE"
                        img.filepath = f"//textures/{img_name}.bmp"
                    mat = ensure_material(img)
                    #
                    slot_index = ent_mesh.materials.find(img_name)
                    if slot_index == -1:
                        ent_mesh.materials.append(mat)
                        slot_index = len(ent_mesh.materials) - 1
                    face.material_index = slot_index
                    # 调试代码
                    # if not os.path.exists(
                    #     bpy.path.abspath(f"//textures/{img_name}.bmp")
                    # ):
                    #     if not Path("D:/tmp/temp").joinpath(f"{img_name}.bmp").exists():
                    #         lack_texture = True
                # 跳过0
                f.seek(4, 1)
            # 骨架
            bones_num = unpack("I", f)[0]
            bones_name = []
            bones_vert_idx = []
            bone_matrix = {}  # type: dict[str, Matrix]
            armature = None
            if bones_num != 1:
                # bmesh.ops.transform(
                #     ent_bm, matrix=Matrix.Rotation(math.pi / 2, 4, "X"), verts=bm_verts
                # )
                # 创建骨架
                armature = bpy.data.armatures.new("Blade_Skeleton")
                armature.show_names = True
                armature.show_axes = True
                # armature.display_type = "STICK"
                armature_obj = bpy.data.objects.new("Blade_Skeleton", armature)
                armature_obj.show_in_front = True
                data.link2coll(armature_obj, ent_coll)
                ag_utils.select_active(context, armature_obj)  # type: ignore
                bpy.ops.object.mode_set(mode="EDIT")
            elif transform_space:
                bmesh.ops.transform(
                    ent_bm,
                    matrix=local_space,
                    verts=ent_bm.verts,  # type: ignore
                )

            for i in range(bones_num):
                if bones_num != 1:
                    length = unpack("I", f)[0]
                    name = unpack(f"{length}s", f)
                else:
                    name = "None"
                #
                parent_idx = unpack("i", f)[0]  # type: int
                lst = unpack("dddd" * 4, f)
                lst = [lst[i * 4 : (i + 1) * 4] for i in range(4)]
                matrix = Matrix(lst)
                matrix.transpose()  # 转置
                matrix.translation /= 1000  # 转换位置单位

                numverts = unpack("I", f)[0]
                vert_start = unpack("I", f)[0]
                # 添加骨骼
                if armature is not None:
                    # pose_matrix_list.append(matrix)
                    bone = armature.edit_bones.new(name)
                    bones_name.append(name)
                    bone.length = 0.1
                    if parent_idx != -1:
                        parent_bone = armature.edit_bones[
                            bones_name[parent_idx]
                        ]  # type: bpy.types.EditBone
                        bone.parent = parent_bone
                        # bone.use_connect = True
                        # if transform_space:
                        # matrix = bone_matrix[parent_bone.name] @ matrix
                        # bone_matrix[name] = matrix
                        matrix = bone_matrix[parent_bone.name] @ matrix
                        # else:
                        #     matrix = parent_bone.matrix @ matrix
                        # matrix = (
                        #     parent_matrix.to_quaternion().to_matrix().to_4x4() @ matrix
                        # )
                        # matrix.translation += parent_matrix.translation
                        dir = (parent_bone.tail - parent_bone.head).normalized()
                        dot = dir.dot(matrix.translation - parent_bone.head)
                        if dot > 0:
                            parent_bone.length = max(0.001, dot)
                    elif transform_space:
                        matrix = local_space @ matrix
                    bone_matrix[name] = matrix
                    # if transform_space:
                    #     bone_matrix[name][0] = local_space @ matrix

                    # if transform_space:
                    #     bm_matrix = local_space @ bone_matrix[name]
                    # else:
                    #     bm_matrix = matrix
                    # 设置骨骼矩阵
                    bone.matrix = matrix
                    vert_end = vert_start + numverts
                    verts = bm_verts[vert_start:vert_end]
                    verts_dup_idx = []
                    for k, v in bm_verts_dup.items():
                        if vert_start <= k < vert_end:
                            verts_dup_idx.extend(v)
                    verts.extend([bm_verts[i] for i in verts_dup_idx])
                    bmesh.ops.transform(
                        ent_bm,
                        matrix=matrix,
                        verts=verts,
                    )
                    # 保存顶点索引
                    bones_vert_idx.append((vert_start, vert_end, verts_dup_idx))
                #
                num = unpack("I", f)[0]
                for j in range(num):
                    pos = Vector(unpack("ddd", f)) / 1000
                    pos = matrix @ pos
                    dist = unpack("d", f)[0] / 1000
                    #
                    # empty = bpy.data.objects.new(name, None)
                    # empty.location = pos
                    # empty.empty_display_size = dist
                    # data.link2coll(empty, context.collection)
                    #
                    vert_start = unpack("I", f)[0]
                    numverts = unpack("I", f)[0]
            #
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            #
            ent_bm.to_mesh(ent_mesh)
            ent_bm.free()
            ent_mesh.shade_smooth()  # 平滑着色
            # 中心
            center = Vector(unpack("ddd", f)) / 1000
            if transform_space:
                center.yz = center.z, -center.y
            dist = unpack("d", f)[0] / 1000

            #
            # empty = bpy.data.objects.new("t.center", None)
            # empty.location = center
            # empty.empty_display_size = dist
            # data.link2coll(empty, context.scene.collection)
            #

            # 添加顶点组
            if armature is not None:
                for idx, name in enumerate(bones_name):
                    group = entity.vertex_groups.new(name=name)
                    start, end, verts_dup_idx = bones_vert_idx[idx]
                    group.add(list(range(start, end)), 1.0, "REPLACE")
                    group.add(verts_dup_idx, 1.0, "ADD")
                # 添加骨架修改器
                modifier = entity.modifiers.new("Armature", "ARMATURE")
                modifier.object = armature_obj  # type: ignore
                # 检查没有顶点组或者顶点组大于1的顶点
                verts_no_group = []
                verts_multi_group = []
                for v in ent_mesh.vertices:
                    if len(v.groups) == 0:
                        verts_no_group.append(v.index)
                    elif len(v.groups) > 1:
                        verts_multi_group.append(v.index)
                if verts_no_group:
                    logger.debug(f"verts_no_group: {verts_no_group}")
                if verts_multi_group:
                    logger.debug(f"verts_multi_group: {verts_multi_group}")
                #

            # 火焰
            num = unpack("I", f)[0]
            for idx in range(num):
                verts_num = unpack("I", f)[0]
                bm = bmesh.new()
                prev_vert = None
                for i in range(verts_num):
                    co = Vector(unpack("ddd", f)) / 1000
                    if transform_space:
                        co.yz = co.z, -co.y
                    vert = bm.verts.new(co)
                    if prev_vert is not None:
                        bm.edges.new([prev_vert, vert])
                    prev_vert = vert
                    #
                    mark = unpack("I", f)[0]
                    if mark != 3:
                        logger.debug(f"Fire - mark not 3: {mark}")
                #
                obj_name = data.get_object_name("B_Fire_Fuego_")
                mesh = bpy.data.meshes.new(obj_name)
                obj = bpy.data.objects.new(
                    obj_name, mesh
                )  # type: Object # type: ignore
                # fire_obj.amagate_data.ent_comp_type = 4
                obj.show_in_front = True
                data.link2coll(obj, ent_coll)

                parent_idx = unpack("i", f)[0]  # type: int
                if parent_idx != -1:
                    if armature is not None:
                        bone_name = bones_name[parent_idx]
                        bmesh.ops.transform(bm, matrix=bone_matrix[bone_name], verts=bm.verts)  # type: ignore
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = bone_name
                        obj.matrix_world = Matrix()
                    else:
                        logger.debug(f"Fire - parent_idx not -1: {parent_idx}")

                bm.to_mesh(mesh)
                bm.free()

                #
                idx_mark = unpack("I", f)[0]
                if idx_mark != idx:
                    logger.debug(f"Fire - idx_mark not idx: {idx_mark} {idx}")

            # 灯光
            num = unpack("I", f)[0]
            for idx in range(num):
                strength = unpack("f", f)[0]
                precision = unpack("f", f)[0]
                co = Vector(unpack("ddd", f)) / 1000
                if transform_space:
                    co.yz = co.z, -co.y
                #
                obj_name = data.get_object_name("Blade_Light_")
                obj = bpy.data.objects.new(
                    obj_name, None
                )  # type: Object # type: ignore
                obj.empty_display_size = 0.1
                obj.empty_display_type = "ARROWS"
                obj.show_in_front = True
                data.link2coll(obj, ent_coll)
                #
                parent_idx = unpack("i", f)[0]  # type: int
                if parent_idx != -1:
                    if armature is not None:
                        bone_name = bones_name[parent_idx]
                        co = bone_matrix[bone_name] @ co
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = bone_name
                    else:
                        logger.debug(f"Light - parent_idx not -1: {parent_idx}")
                #
                obj.matrix_world = Matrix.Translation(co)

            # 锚点
            num = unpack("I", f)[0]
            for idx in range(num):
                length = unpack("I", f)[0]
                name = unpack(f"{length}s", f)
                lst = unpack("dddd" * 4, f)
                lst = [lst[i * 4 : (i + 1) * 4] for i in range(4)]
                matrix = Matrix(lst)
                matrix.transpose()  # 转置
                matrix.translation /= 1000  # 转换位置单位
                #
                obj_name = f"Blade_Anchor_{name}"
                obj = bpy.data.objects.new(
                    obj_name, None
                )  # type: Object # type: ignore
                obj.empty_display_size = 0.1
                obj.empty_display_type = "ARROWS"
                obj.show_in_front = True
                data.link2coll(obj, ent_coll)
                #
                parent_matrix = local_space if transform_space else None
                parent_idx = unpack("i", f)[0]  # type: int
                if parent_idx != -1:
                    if armature is not None:
                        bone_name = bones_name[parent_idx]
                        parent_matrix = bone_matrix[bone_name]
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = bone_name
                    else:
                        obj.parent = entity  # type: ignore
                #
                if parent_matrix:
                    matrix = parent_matrix @ matrix
                # XXX 有BUG，没有父对象时，矩阵设置不生效
                if not obj.parent:
                    obj.parent = entity  # type: ignore
                    obj.matrix_world = matrix
                    bpy.app.timers.register(
                        lambda obj=obj: setattr(obj, "parent", None), first_interval=0.2
                    )
                else:
                    obj.matrix_world = matrix

            # 剩余数据种类
            data_num = unpack("I", f)[0]
            if data_num == 0:
                return final()

            # 边缘
            num = unpack("I", f)[0]
            for idx in range(num):
                mark = unpack("I", f)[0]  # 默认0
                if mark != 0:
                    logger.debug(f"Edge - mark not 0: {mark}")
                #
                parent_idx = unpack("i", f)[0]  # type: int
                pt1 = Vector(unpack("ddd", f)) / 1000
                pt2 = Vector(unpack("ddd", f)) / 1000
                pt3 = Vector(unpack("ddd", f)) / 1000
                #
                obj_name = data.get_object_name("Blade_Edge_")
                mesh = bpy.data.meshes.new(obj_name)
                obj = bpy.data.objects.new(
                    obj_name, mesh
                )  # type: Object # type: ignore
                obj.show_in_front = True
                obj.amagate_data.ent_comp_type = 1
                data.link2coll(obj, ent_coll)
                #
                parent_matrix = local_space if transform_space else None
                if parent_idx != -1:
                    if armature is not None:
                        bone_name = bones_name[parent_idx]
                        parent_matrix = bone_matrix[bone_name]
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = bone_name
                    else:
                        obj.parent = entity  # type: ignore
                #
                if parent_matrix:
                    quat = parent_matrix.to_quaternion()
                    pt1 = parent_matrix @ pt1
                    pt2 = quat @ pt2
                    pt3 = quat @ pt3
                #
                mesh_data = mesh_dict["Blade_Edge_1"]
                bm = bmesh.new()
                verts = []
                for co in mesh_data["vertices"]:
                    verts.append(bm.verts.new(co))
                for idx in mesh_data["edges"]:
                    bm.edges.new([verts[i] for i in idx])
                # 调整大小
                scale_y = pt2.length * 2 / 0.8
                bmesh.ops.scale(bm, vec=(1, scale_y, 1), verts=bm.verts)  # type: ignore
                move_x = pt3.length - 0.3
                bmesh.ops.translate(bm, vec=(move_x, 0, 0), verts=[verts[i] for i in range(2, 8)])  # type: ignore
                # 调整朝向
                x_axis = pt3.normalized()
                y_axis = pt2.normalized()
                z_axis = x_axis.cross(y_axis).normalized()
                bm_matrix = Matrix((x_axis, y_axis, z_axis)).transposed()
                # quat = pt2.normalized().to_track_quat("Y", "Z")
                # quat = pt3.normalized().to_track_quat("X", "Z") @ quat
                bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=bm_matrix, verts=bm.verts)  # type: ignore

                bm.to_mesh(mesh)
                bm.free()
                #
                obj.matrix_world.translation = pt1

            #
            data_num -= 1
            if data_num == 0:
                return final()

            # 尖刺
            num = unpack("I", f)[0]
            for idx in range(num):
                mark = unpack("I", f)[0]  # 默认0
                if mark != 0:
                    logger.debug(f"Spike - mark not 0: {mark}")
                #
                parent_idx = unpack("i", f)[0]  # type: int
                pt1 = Vector(unpack("ddd", f)) / 1000
                pt2 = Vector(unpack("ddd", f)) / 1000
                #
                obj_name = data.get_object_name("Blade_Spike_")
                mesh = bpy.data.meshes.new(obj_name)
                obj = bpy.data.objects.new(
                    obj_name, mesh
                )  # type: Object # type: ignore
                obj.show_in_front = True
                obj.amagate_data.ent_comp_type = 2
                data.link2coll(obj, ent_coll)
                #
                parent_matrix = local_space if transform_space else None
                if parent_idx != -1:
                    if armature is not None:
                        bone_name = bones_name[parent_idx]
                        parent_matrix = bone_matrix[bone_name]
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = bone_name
                    else:
                        obj.parent = entity  # type: ignore
                #
                if parent_matrix:
                    pt1 = parent_matrix @ pt1
                    pt2 = parent_matrix @ pt2
                #
                mesh_data = mesh_dict["Blade_Spike_1"]
                bm = bmesh.new()
                verts = []
                for co in mesh_data["vertices"]:
                    verts.append(bm.verts.new(co))
                for idx in mesh_data["edges"]:
                    bm.edges.new([verts[i] for i in idx])
                # 调整大小
                move_y = (pt2 - pt1).length - 0.1
                bmesh.ops.translate(bm, vec=(0, move_y, 0), verts=[verts[i] for i in range(1, 6)])  # type: ignore
                # 调整朝向
                quat = (pt2 - pt1).normalized().to_track_quat("Y", "Z")
                bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=quat.to_matrix(), verts=bm.verts)  # type: ignore

                bm.to_mesh(mesh)
                bm.free()
                #
                obj.matrix_world = Matrix.Translation(pt1)

            ent_mesh.attributes.new(name="amagate_group", type="INT", domain="FACE")
            ent_mesh.attributes.new(
                name="amagate_mutilation_group", type="INT", domain="FACE"
            )

            #
            data_num -= 1
            if data_num == 0:
                return final()

            # 组
            num = unpack("I", f)[0]
            for idx in range(num):
                group = unpack("B", f)[0]
                if idx >= len(ent_mesh.polygons):
                    continue
                ent_mesh.attributes["amagate_group"].data[idx].value = 0 if group == 0 else ag_utils.uint_to_int(1 << (group - 1))  # type: ignore

            # 肢解组
            num = unpack("I", f)[0]
            for idx in range(num):
                group = unpack("i", f)[0]
                if idx >= len(ent_mesh.polygons):
                    continue
                ent_mesh.attributes["amagate_mutilation_group"].data[idx].value = group  # type: ignore

            #
            data_num -= 1
            if data_num == 0:
                return final()

            # 轨迹
            num = unpack("I", f)[0]
            for idx in range(num):
                mark = unpack("I", f)[0]  # 默认0
                if mark != 0:
                    logger.debug(f"Track - mark not 0: {mark}")
                parent_idx = unpack("i", f)[0]  # type: int
                pt1 = Vector(unpack("ddd", f)) / 1000
                pt2 = Vector(unpack("ddd", f)) / 1000
                #
                obj_name = data.get_object_name("Blade_Trail_")
                mesh = bpy.data.meshes.new(obj_name)
                obj = bpy.data.objects.new(
                    obj_name, mesh
                )  # type: Object # type: ignore
                obj.show_in_front = True
                obj.amagate_data.ent_comp_type = 3
                data.link2coll(obj, ent_coll)
                #
                parent_matrix = local_space if transform_space else None
                if parent_idx != -1:
                    if armature is not None:
                        bone_name = bones_name[parent_idx]
                        parent_matrix = bone_matrix[bone_name]
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = bone_name
                    else:
                        obj.parent = entity  # type: ignore
                #
                if parent_matrix:
                    pt1 = parent_matrix @ pt1
                    pt2 = parent_matrix @ pt2
                #
                obj.matrix_world = Matrix()
                bm = bmesh.new()
                bm.verts.new(pt1)
                bm.verts.new(pt2)
                bm.edges.new(bm.verts)

                bm.to_mesh(mesh)
                bm.free()

            #
            return final()

    def invoke(self, context: Context, event):
        # 设为上次选择目录，文件名为空
        self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


############################
############################ 导出操作
############################


class OT_ExportBOD(bpy.types.Operator):
    bl_idname = "amagate.export_bod"
    bl_label = "Export BOD"
    bl_description = "Export BOD"
    bl_options = {"INTERNAL"}

    main: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    action: EnumProperty(
        name="",
        description="",
        items=[
            # ("1", "Export BOD", ""),
            ("2", "Export BOD as ...", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore
    filter_glob: StringProperty(default="*.bod", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context: Context):
        # print(f"main: {self.main}, action: {self.action}")
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        #
        self.filepath = bpy.path.ensure_ext(self.filepath, ".bod")
        # logger.debug(f"filepath: {self.filepath}")
        ent_dict = self.ent_dict
        lack_texture = False

        # 获取主实体
        # if ent_dict["skin"] is not None:
        #     entity = ent_dict["skin"]  # type: Object
        #     ag_utils.select_active(context, entity)
        #     for obj in entity.children_recursive:  # type: ignore
        #         obj.select_set(True)
        #     # 如果有子物体
        #     if len(context.selected_objects) > 1:
        #         bpy.ops.object.duplicate()
        #         bpy.ops.object.join()
        #         entity = context.object  # type: ignore
        #     else:
        #         bpy.ops.object.duplicate()
        #         entity = context.object  # type: ignore
        if len(ent_dict["objects"]) > 1:
            ag_utils.select_active(context, ent_dict["objects"][0])
            for obj in ent_dict["objects"]:
                obj.select_set(True)
            bpy.ops.object.duplicate()
            bpy.ops.object.join()
            entity = context.object  # type: Object # type: ignore
        else:
            ag_utils.select_active(context, ent_dict["objects"][0])
            bpy.ops.object.duplicate()
            entity = context.object  # type: Object # type: ignore

        ent_mesh = entity.data  # type: bpy.types.Mesh # type: ignore
        if not ent_mesh.attributes.get("amagate_group"):
            ent_mesh.attributes.new(name="amagate_group", type="INT", domain="FACE")
        if not ent_mesh.attributes.get("amagate_mutilation_group"):
            ent_mesh.attributes.new(
                name="amagate_mutilation_group", type="INT", domain="FACE"
            )

        bpy.ops.object.mode_set(mode="EDIT")
        # 合并顶点
        # bpy.ops.mesh.select_mode(type="VERT")
        # bpy.ops.mesh.select_all(action="SELECT")
        # with contextlib.redirect_stdout(StringIO()):
        #     bpy.ops.mesh.remove_doubles()
        # 三角化
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
        #
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        # bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        #
        depsgraph = context.evaluated_depsgraph_get()
        # 目标坐标系
        target_space_inv = Matrix.Rotation(
            -math.pi / 2, 4, "X"
        ).inverted()  # type: Matrix

        ent_mesh = entity.to_mesh(
            preserve_all_data_layers=True, depsgraph=depsgraph
        )  # type: bpy.types.Mesh # type: ignore
        entity_eval = entity.evaluated_get(depsgraph)
        matrix = entity_eval.matrix_world.copy()
        origin = matrix.to_translation()
        bounds_length = [
            ((matrix @ Vector(corner)) - origin).length
            for corner in entity_eval.bound_box
        ]
        bounds_length.sort(reverse=True)
        bound_max_length = bounds_length[0] * 1000
        # matrix = entity.matrix_world.copy()
        # quat = matrix.to_quaternion()
        uv_layer = ent_mesh.uv_layers.active.data
        #
        cursor = context.scene.cursor
        armature_obj = next((m.object for m in entity.modifiers if m.type == "ARMATURE"), None)  # type: ignore
        if armature_obj is not None:
            # 判断顶点组是否包含所有骨骼
            names = set(i.name for i in entity.vertex_groups)
            bone_names = set(i.name for i in armature_obj.data.bones)
            if not names.issuperset(bone_names):
                self.report({"ERROR"}, "Missing bone vertex group")
                entity.to_mesh_clear()
                bpy.data.meshes.remove(entity.data)  # type: ignore
                return {"CANCELLED"}
            groups_idx = [entity.vertex_groups[name].index for name in bone_names]
            for v in ent_mesh.vertices:
                # has_vg = next((1 for g in v.groups if g.group in groups_idx), 0)
                vert_groups = [1 for g in v.groups if g.group in groups_idx]
                if len(vert_groups) != 1:
                    self.report(
                        {"ERROR"},
                        "All vertices must be assigned to bone vertex groups and can only belong to one bone vertex group",
                    )
                    entity.to_mesh_clear()
                    bpy.data.meshes.remove(entity.data)  # type: ignore
                    return {"CANCELLED"}

            #
            prev_cursor = cursor.location.copy()
            cursor.location = origin
            ag_utils.select_active(context, armature_obj)
            bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
            bpy.ops.object.select_all(action="DESELECT")
            cursor.location = prev_cursor
            armature_matrix = armature_obj.matrix_world.copy()
            armature_matrix.translation = Vector()
            armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        else:
            armature = None  # type: ignore
            armature_matrix = Matrix()

        # 导出BOD
        buffer = BytesIO()
        global_verts_map = {}
        global_verts_count = 0
        # 写入内部名称
        inter_name = ent_dict["kind"].encode("utf-8")
        buffer.write(struct.pack("I", len(inter_name)))
        buffer.write(inter_name)

        # 写入顶点数据
        verts_num = len(ent_mesh.vertices)
        buffer.write(struct.pack("I", verts_num))
        bones_name = []  # type: list[str]
        bones_list = []
        bones_matrix = {}  # type: dict[str, tuple[Matrix, Matrix]]
        # 如果有骨架
        if armature is not None:
            bone_verts_start = 0
            for bone in armature_obj.pose.bones:
                name = bone.name
                matrix = armature_matrix @ bone.matrix
                # 应用缩放
                loc, rot, scale = matrix.decompose()
                matrix = Matrix.LocRotScale(loc, rot, (1, 1, 1))
                bone_matrix = bones_matrix.setdefault(
                    name,
                    (
                        target_space_inv @ matrix,
                        (target_space_inv @ matrix).inverted(),
                    ),
                )[1]
                # bone_matrix = bone.matrix.inverted()  # type: Matrix
                vertex_indices = ag_utils.get_vertex_in_group(
                    entity, name
                )  # type: set[int]
                co_list = []
                max_length = 0
                if len(vertex_indices) > 512:
                    logger.warning(f"Bone [{name}] has more than 512 vertices!")
                for idx in vertex_indices:
                    if idx in global_verts_map:
                        continue

                    global_verts_map[idx] = global_verts_count
                    global_verts_count += 1
                    #
                    vert = ent_mesh.vertices[idx]
                    normal = vert.normal.copy()
                    normal.yz = -normal.z, normal.y
                    normal = bone_matrix.to_quaternion() @ normal

                    co = vert.co.copy()
                    co.yz = -co.z, co.y
                    co = bone_matrix @ co
                    co *= 1000
                    # if vert.index == 0:
                    #     print(f"co: {co}")
                    co_list.append(co)
                    length = co.length
                    if length > max_length:
                        max_length = length
                    #
                    buffer.write(struct.pack("ddd", *co))
                    buffer.write(struct.pack("ddd", *normal))
                #
                bone_verts_num = len(co_list)
                if bone_verts_num == 0:
                    bone_center = Vector()
                else:
                    bone_center = sum(co_list, Vector()) / bone_verts_num
                bones_name.append(name)
                bones_list.append(
                    (bone_verts_num, bone_verts_start, bone_center, max_length)
                )
                bone_verts_start += bone_verts_num
        else:
            for vert in ent_mesh.vertices:
                normal = vert.normal.copy()
                normal.yz = -normal.z, normal.y
                co = vert.co * 1000
                co.yz = -co.z, co.y
                # co = co.to_tuple(1)
                buffer.write(struct.pack("ddd", *co))
                buffer.write(struct.pack("ddd", *normal))

        # 写入面数据
        faces_num = len(ent_mesh.polygons)
        buffer.write(struct.pack("I", faces_num))
        for poly in ent_mesh.polygons:
            # 写顶点索引
            if armature is not None:
                buffer.write(
                    struct.pack("III", *[global_verts_map[i] for i in poly.vertices])
                )
            else:
                buffer.write(struct.pack("III", *poly.vertices))
            # 写材质
            img_name = ""
            if poly.material_index < len(entity.material_slots):
                mat = entity.material_slots[poly.material_index].material
                if mat:
                    img_name = mat.name
                    img_node = mat.node_tree.nodes.get(
                        "Image Texture"
                    )  # type: bpy.types.ShaderNodeTexImage # type: ignore
                    if img_node and img_node.image:
                        img_name = img_node.image.name

            if not img_name:
                img_name = "NULL"
                if not lack_texture:
                    lack_texture = True
            img_name = img_name.encode("utf-8")
            buffer.write(struct.pack("I", len(img_name)))
            buffer.write(img_name)
            # 写UV
            uv_list = []
            for loop_idx in poly.loop_indices:
                uv_list.append(uv_layer[loop_idx].uv.to_tuple())
            uv_list = tuple(zip(*uv_list))
            buffer.write(struct.pack("ffffff", *uv_list[0], *uv_list[1]))
            #
            buffer.write(struct.pack("f", 0))

        # 如果有骨架
        if armature is not None:
            # ag_utils.select_active(context, skeleton[0])
            # for obj in skeleton[0].children_recursive:
            #     obj.select_set(True)
            #     skeleton.append(obj)  # type: ignore
            # # 原点到几何中心
            # bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
            #
            buffer.write(struct.pack("I", len(bones_name)))
            for index, bone_name in enumerate(bones_name):
                bone = armature_obj.pose.bones[bone_name]
                name = bone_name.encode("utf-8")
                buffer.write(struct.pack("I", len(name)))
                buffer.write(name)
                # 父节点索引
                parent_bone = bone.parent
                matrix = bones_matrix[bone_name][0]
                if parent_bone is None:
                    parent_idx = -1
                else:
                    parent_idx = bones_name.index(parent_bone.name)  # type: ignore
                    # matrix.translation = matrix.translation - bones_matrix[parent_bone.name][0].translation
                    # matrix = bones_matrix[parent_bone.name][1].to_quaternion().to_matrix().to_4x4() @ matrix
                    matrix = bones_matrix[parent_bone.name][1] @ matrix

                matrix.translation *= 1000  # 转换位置单位
                matrix.transpose()  # 转置
                buffer.write(struct.pack("i", parent_idx))
                for row in matrix:
                    buffer.write(struct.pack("dddd", *row))
                bone_verts_num, bone_verts_start, bone_center, max_length = bones_list[
                    index
                ]
                # 写入顶点数量
                buffer.write(struct.pack("I", bone_verts_num))
                # 写入顶点起始位置
                buffer.write(struct.pack("I", bone_verts_start))
                #
                buffer.write(struct.pack("I", 1))
                buffer.write(struct.pack("ddd", *bone_center))
                buffer.write(struct.pack("d", max_length))
                buffer.write(struct.pack("I", bone_verts_start))
                buffer.write(struct.pack("I", bone_verts_num))
        else:
            buffer.write(struct.pack("I", 1))  # 骨骼为1
            parent_idx = -1
            buffer.write(struct.pack("i", parent_idx))
            for row in Matrix():
                buffer.write(struct.pack("dddd", *row))
            buffer.write(struct.pack("I", verts_num))  # 顶点数量
            buffer.write(struct.pack("I", 0))  # 顶点起始位置
            #
            buffer.write(struct.pack("I", 1))
            center = origin * 1000
            center.yz = -center.z, center.y
            buffer.write(struct.pack("dddd", *center, bound_max_length))
            buffer.write(struct.pack("II", 0, verts_num))

        # 中心
        center = origin * 1000
        center.yz = -center.z, center.y
        buffer.write(struct.pack("dddd", *center, bound_max_length))

        obj: Object
        # 火焰
        buffer.write(struct.pack("I", len(ent_dict["fires"])))
        for index, obj in enumerate(ent_dict["fires"]):
            obj = obj.evaluated_get(depsgraph)
            matrix_world = obj.matrix_world.copy()
            matrix_world.translation -= origin
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            buffer.write(struct.pack("I", len(mesh.vertices)))
            #
            # parent_matrix = None
            parent_idx = -1
            # if obj.parent:
            #     if obj.parent_bone in bones_name:
            #         parent_matrix = bones_matrix[obj.parent_bone][1]
            #         parent_idx = bones_name.index(obj.parent_bone)
            #     else:
            #         parent_idx = 0

            for vert in mesh.vertices:
                co = matrix_world @ vert.co
                co.yz = -co.z, co.y
                # if parent_matrix:
                #     co = parent_matrix @ co
                #
                co *= 1000
                buffer.write(struct.pack("ddd", *co))
                buffer.write(struct.pack("I", 3))  # 固定3
            buffer.write(struct.pack("i", parent_idx))
            buffer.write(struct.pack("I", index))

        # 灯光
        buffer.write(struct.pack("I", len(ent_dict["lights"])))
        for obj in ent_dict["lights"]:
            obj = obj.evaluated_get(depsgraph)
            strength = 1  # 创建实体时灯光强度默认为10，不会被该值影响
            precision = bytes.fromhex("0000003D")  # 0.03125
            buffer.write(struct.pack("f", strength))
            buffer.write(precision)

            co = obj.matrix_world.translation - origin
            co.yz = -co.z, co.y
            #
            # parent_matrix = None
            parent_idx = -1
            # if obj.parent:
            #     if obj.parent_bone in bones_name:
            #         parent_matrix = bones_matrix[obj.parent_bone][1]
            #         parent_idx = bones_name.index(obj.parent_bone)
            #     else:
            #         parent_idx = 0

            # if parent_matrix:
            #     co = parent_matrix @ co
            #
            co *= 1000
            buffer.write(struct.pack("ddd", *co))
            buffer.write(struct.pack("i", parent_idx))

        # 锚点
        buffer.write(struct.pack("I", len(ent_dict["anchors"])))
        for obj in ent_dict["anchors"]:
            obj = obj.evaluated_get(depsgraph)
            name = obj.name[13:].encode("utf-8")
            buffer.write(struct.pack("I", len(name)))
            buffer.write(name)
            #
            parent_matrix = None
            parent_idx = -1
            if obj.parent:
                if obj.parent_bone in bones_name:
                    parent_matrix = bones_matrix[obj.parent_bone][1]
                    parent_idx = bones_name.index(obj.parent_bone)
                else:
                    parent_idx = 0

            matrix = obj.matrix_world.copy()
            matrix.translation -= origin
            matrix = target_space_inv @ matrix
            if parent_matrix:
                matrix = parent_matrix @ matrix
            #
            matrix.translation *= 1000  # 转换位置单位
            matrix.transpose()  # 转置
            for row in matrix:
                buffer.write(struct.pack("dddd", *row))
            buffer.write(struct.pack("i", parent_idx))

        #
        buffer.write(struct.pack("I", 4))  # 写4种数据：边缘，尖刺，组，轨迹

        # 边缘
        buffer.write(struct.pack("I", len(ent_dict["edges"])))
        for obj in ent_dict["edges"]:
            obj = obj.evaluated_get(depsgraph)
            matrix_world = obj.matrix_world.copy()
            matrix_world.translation -= origin
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            #
            pt1 = (
                matrix_world @ mesh.vertices[0].co + matrix_world @ mesh.vertices[1].co
            ) / 2
            pt2 = matrix_world @ mesh.vertices[1].co - pt1
            pt3 = (
                matrix_world @ mesh.vertices[2].co + matrix_world @ mesh.vertices[3].co
            ) / 2 - pt1
            pt1.yz = -pt1.z, pt1.y
            pt2.yz = -pt2.z, pt2.y
            pt3.yz = -pt3.z, pt3.y
            #
            parent_matrix = None
            parent_idx = -1
            if obj.parent:
                if obj.parent_bone in bones_name:
                    parent_matrix = bones_matrix[obj.parent_bone][1]
                    parent_idx = bones_name.index(obj.parent_bone)
                else:
                    parent_idx = 0

            if parent_matrix:
                quat = parent_matrix.to_quaternion()
                pt1 = parent_matrix @ pt1
                pt2 = quat @ pt2
                pt3 = quat @ pt3
            #
            pt1 *= 1000
            pt2 *= 1000
            pt3 *= 1000
            buffer.write(struct.pack("I", 0))  # 固定0
            buffer.write(struct.pack("i", parent_idx))
            buffer.write(struct.pack("ddd", *pt1))
            buffer.write(struct.pack("ddd", *pt2))
            buffer.write(struct.pack("ddd", *pt3))

        # 尖刺
        buffer.write(struct.pack("I", len(ent_dict["spikes"])))
        for obj in ent_dict["spikes"]:
            obj = obj.evaluated_get(depsgraph)
            matrix_world = obj.matrix_world.copy()
            matrix_world.translation -= origin
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            #
            pt1 = matrix_world @ mesh.vertices[0].co
            pt2 = matrix_world @ mesh.vertices[1].co
            pt1.yz = -pt1.z, pt1.y
            pt2.yz = -pt2.z, pt2.y
            #
            parent_matrix = None
            parent_idx = -1
            if obj.parent:
                if obj.parent_bone in bones_name:
                    parent_matrix = bones_matrix[obj.parent_bone][1]
                    parent_idx = bones_name.index(obj.parent_bone)
                else:
                    parent_idx = 0

            if parent_matrix:
                pt1 = parent_matrix @ pt1
                pt2 = parent_matrix @ pt2
            #
            pt1 *= 1000
            pt2 *= 1000
            buffer.write(struct.pack("I", 0))  # 固定0
            buffer.write(struct.pack("i", parent_idx))
            buffer.write(struct.pack("ddd", *pt1))
            buffer.write(struct.pack("ddd", *pt2))

        # 组
        buffer.write(struct.pack("I", faces_num))
        for i in range(faces_num):
            group = ent_mesh.attributes["amagate_group"].data[i].value  # type: ignore
            group = next((i + 1 for i in range(32) if (1 << i) & group), 0)
            buffer.write(struct.pack("B", group))

        # 肢解组
        if armature is not None:
            buffer.write(struct.pack("I", faces_num))
            for i in range(faces_num):
                group = ent_mesh.attributes["amagate_mutilation_group"].data[i].value  # type: ignore
                buffer.write(struct.pack("i", group))
        else:
            buffer.write(struct.pack("I", 0))

        # 轨迹
        buffer.write(struct.pack("I", len(ent_dict["trails"])))
        for obj in ent_dict["trails"]:
            obj = obj.evaluated_get(depsgraph)
            matrix_world = obj.matrix_world.copy()
            matrix_world.translation -= origin
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            #
            pt1 = matrix_world @ mesh.vertices[0].co
            pt2 = matrix_world @ mesh.vertices[1].co
            pt1.yz = -pt1.z, pt1.y
            pt2.yz = -pt2.z, pt2.y
            #
            parent_matrix = None
            parent_idx = -1
            if obj.parent:
                if obj.parent_bone in bones_name:
                    parent_matrix = bones_matrix[obj.parent_bone][1]
                    parent_idx = bones_name.index(obj.parent_bone)
                else:
                    parent_idx = 0

            if parent_matrix:
                pt1 = parent_matrix @ pt1
                pt2 = parent_matrix @ pt2
            #
            pt1 *= 1000
            pt2 *= 1000
            buffer.write(struct.pack("I", 0))  # 固定0
            buffer.write(struct.pack("i", parent_idx))
            buffer.write(struct.pack("ddd", *pt1))
            buffer.write(struct.pack("ddd", *pt2))

        # 写入文件
        with open(self.filepath, "wb") as f:
            f.write(buffer.getvalue())
        buffer.close()
        #
        entity.to_mesh_clear()
        bpy.data.meshes.remove(entity.data)  # type: ignore
        if lack_texture:
            self.report({"WARNING"}, "The object lacks texture")
        else:
            self.report(
                {"INFO"},
                f"{pgettext('Export successfully')}: {os.path.basename(self.filepath)}",
            )
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        ent_coll = None
        for coll in bpy.data.collections:
            if len(coll.name) < 14:
                continue
            # 判断名称前缀
            if not coll.name.lower().startswith("blade_object_"):
                continue
            # 判断是否有引用
            if coll.users - coll.use_fake_user == 0:
                continue
            # 判断是否有物体
            if len(coll.objects) == 0:
                continue

            # if not self.main:
            #     # 仅可见
            #     if self.action == "2":
            #         if not coll.objects[0].visible_get():
            #             continue
            ent_coll = coll
            break
        if ent_coll is None:
            self.report(
                {"ERROR"}, "No collection with the prefix `Blade_Object_` was found"
            )
            return {"CANCELLED"}

        # 找到实体集合
        ent_dict = {
            "kind": ent_coll.name[13:],
            "objects": [],
            # "skin": None,
            # "skeleton": None,
            "anchors": [],
            "edges": [],
            "spikes": [],
            "trails": [],
            "fires": [],
            "lights": [],
        }

        for obj in ent_coll.all_objects:
            if not obj.visible_get():
                continue
            #
            if obj.type == "MESH":
                # if obj.name.lower().startswith("blade_skin"):
                #     ent_dict["skin"] = obj
                if (
                    obj.name.lower().startswith("blade_edge_")
                    and obj.amagate_data.ent_comp_type == 1
                ):
                    ent_dict["edges"].append(obj)
                elif (
                    obj.name.lower().startswith("blade_spike_")
                    and obj.amagate_data.ent_comp_type == 2
                ):
                    ent_dict["spikes"].append(obj)
                elif (
                    obj.name.lower().startswith("blade_trail_")
                    and obj.amagate_data.ent_comp_type == 3
                ):
                    ent_dict["trails"].append(obj)
                elif obj.name.lower().startswith("b_fire_fuego_"):
                    ent_dict["fires"].append(obj)
                else:
                    ent_dict["objects"].append(obj)

            # elif obj.type == "ARMATURE" and obj.name.lower().startswith(
            #     "blade_skeleton"
            # ):
            #     ent_dict["skeleton"] = obj

            elif obj.type == "EMPTY":
                if len(obj.name) > 13 and obj.name.lower().startswith("blade_anchor_"):
                    ent_dict["anchors"].append(obj)
                elif obj.name.lower().startswith("blade_light_"):
                    ent_dict["lights"].append(obj)

        #
        if not ent_dict["objects"]:
            self.report({"ERROR"}, "No visible entity Mesh")
            return {"CANCELLED"}
        if next(
            (True for obj in ent_dict["objects"] if len(obj.data.uv_layers) == 0), False
        ):
            self.report({"ERROR"}, "The entity is missing UV map")
            return {"CANCELLED"}
        # print([i.name for i in ent_dict["objects"]])
        # return {"CANCELLED"}
        # 找到实体对象
        self.ent_dict = ent_dict

        if not bpy.data.filepath or (not self.main and self.action == "2"):
            if not self.filepath:
                self.filepath = f"{ent_dict['kind']}.bod"
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = f"{os.path.splitext(bpy.data.filepath)[0]}.bod"
            return self.execute(context)


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
