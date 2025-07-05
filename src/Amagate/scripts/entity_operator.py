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
        data.import_nodes(mat, nodes_data["EXPORT.Entity"])
        mat.use_fake_user = True
        mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
        mat.use_backface_culling = True

    return mat


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


class OT_ImportBOD(bpy.types.Operator):
    bl_idname = "amagate.import_bod"
    bl_label = "Import BOD"
    bl_description = "Import BOD"
    bl_options = {"INTERNAL"}

    filter_glob: StringProperty(default="*.bod", options={"HIDDEN"})  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context: Context):
        if os.path.splitext(self.filepath)[1].lower() != ".bod":
            self.report({"ERROR"}, "Not a bod file")
            return {"CANCELLED"}
        #
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        with open(self.filepath, "rb") as f:
            bm = bmesh.new()
            uv_layer = bm.loops.layers.uv.verify()  # 获取或创建UV图层
            bm_verts = []  # type: list[bmesh.types.BMVert]
            # 内部名称
            length = unpack("I", f)[0]
            inter_name = unpack(f"{length}s", f)
            #
            mesh = bpy.data.meshes.new(inter_name)
            entity = bpy.data.objects.new(inter_name, mesh)
            #
            ent_coll = bpy.data.collections.new(f"Blade_Object_{inter_name}")
            context.scene.collection.children.link(ent_coll)
            data.link2coll(entity, ent_coll)
            # 顶点
            verts_num = unpack("I", f)[0]
            for i in range(verts_num):
                co = Vector(unpack("ddd", f)) / 1000
                co.yz = co.z, -co.y
                bm_verts.append(bm.verts.new(co))
                # 跳过法线
                f.seek(24, 1)
            # 面
            faces_num = unpack("I", f)[0]
            for i in range(faces_num):
                vert_idx = unpack("III", f)
                try:
                    face = bm.faces.new([bm_verts[i] for i in vert_idx])
                except:
                    face = None
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
                    slot_index = mesh.materials.find(img_name)
                    if slot_index == -1:
                        mesh.materials.append(mat)
                        slot_index = len(mesh.materials) - 1
                    face.material_index = slot_index
                # 跳过0
                f.seek(4, 1)
            # 骨架
            bones_num = unpack("I", f)[0]
            bones_name = []
            bones_vert_idx = []
            # pose_matrix_list = []  # type: list[Matrix]
            armature = None
            if bones_num != 1:
                bmesh.ops.transform(
                    bm, matrix=Matrix.Rotation(math.pi / 2, 4, "X"), verts=bm_verts
                )
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
                # 构造交换矩阵
                swap_matrix = Matrix(
                    (
                        (1, 0, 0, 0),
                        (0, 0, 1, 0),  # y → z
                        (0, -1, 0, 0),  # z → -y
                        (0, 0, 0, 1),
                    )
                )
                # 转换坐标轴
                # matrix = swap_matrix @ matrix @ swap_matrix.transposed()
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
                        parent_matrix = parent_bone.matrix
                        matrix = (
                            parent_matrix.to_quaternion().to_matrix().to_4x4() @ matrix
                        )
                        matrix.translation += parent_matrix.translation
                        dir = (parent_bone.tail - parent_bone.head).normalized()
                        dot = dir.dot(matrix.translation - parent_bone.head)
                        if dot > 0:
                            parent_bone.length = dot
                    # 设置骨骼矩阵
                    bone.matrix = matrix
                    verts = bm_verts[vert_start : vert_start + numverts]
                    bmesh.ops.transform(
                        bm,
                        matrix=matrix,
                        verts=verts,
                    )
                    # 保存顶点索引
                    bones_vert_idx.append((vert_start, vert_start + numverts))
                #
                num = unpack("I", f)[0]
                for j in range(num):
                    pos = Vector(unpack("ddd", f)) / 1000
                    pos = (matrix @ Matrix.Translation(pos)).to_translation()
                    # pos.yz = pos.z, -pos.y
                    dist = unpack("d", f)[0] / 1000
                    #
                    # empty = bpy.data.objects.new(name, None)
                    # empty.location = pos
                    # empty.empty_display_size = dist
                    # data.link2coll(empty, context.collection)
                    #
                    numverts = unpack("I", f)[0]
                    vert_start = unpack("I", f)[0]
            # 中心
            center = Vector(unpack("ddd", f)) / 1000
            center.yz = center.z, -center.y
            dist = unpack("d", f)[0] / 1000
            #
            # empty = bpy.data.objects.new("t.center", None)
            # empty.location = center
            # empty.empty_display_size = dist
            # data.link2coll(empty, context.scene.collection)
            #
            #
            bm.to_mesh(mesh)
            bm.free()
            # mesh.shade_smooth()  # 平滑着色
            if armature is not None:
                # 添加顶点组
                for idx, name in enumerate(bones_name):
                    group = entity.vertex_groups.new(name=name)
                    start, end = bones_vert_idx[idx]
                    group.add(list(range(start, end)), 1.0, "REPLACE")
                # 添加骨架修改器
                modifier = entity.modifiers.new("Armature", "ARMATURE")
                modifier.object = armature_obj  # type: ignore
            #
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.view3d.view_all(center=True)
        #
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        self.filepath = f"//"
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
        has_skin = False
        buffer = BytesIO()
        if ent_dict["skin"] is not None:
            has_skin = True
            entity = ent_dict["skin"]  # type: Object
            ag_utils.select_active(context, entity)
            for obj in entity.children_recursive:
                obj.select_set(True)
            # 如果有子物体
            if len(context.selected_objects) > 1:
                bpy.ops.object.duplicate()
                bpy.ops.object.join()
                entity = context.object  # type: ignore
            else:
                bpy.ops.object.duplicate()
                entity = context.object  # type: ignore
        elif len(ent_dict["objects"]) > 1:
            ag_utils.select_active(context, ent_dict["objects"][0])
            for obj in ent_dict["objects"]:
                obj.select_set(True)
                bpy.ops.object.duplicate()
                bpy.ops.object.join()
                entity = context.object  # type: ignore
        else:
            ag_utils.select_active(context, ent_dict["objects"][0])
            bpy.ops.object.duplicate()
            entity = context.object  # type: ignore

        bpy.ops.object.mode_set(mode="EDIT")
        # 合并顶点
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles()
        # 三角化
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
        #
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        #
        mesh = entity.data  # type: bpy.types.Mesh # type: ignore
        matrix = entity.matrix_world.copy()
        quat = matrix.to_quaternion()
        uv_layer = mesh.uv_layers.active.data

        # 导出BOD
        # 写入内部名称
        inter_name = ent_dict["kind"].encode("utf-8")
        buffer.write(struct.pack("I", len(inter_name)))
        buffer.write(inter_name)
        # 写入顶点数据
        verts_num = len(mesh.vertices)
        buffer.write(struct.pack("I", verts_num))
        for vert in mesh.vertices:
            normal = quat @ vert.normal
            normal.yz = -normal.z, normal.y
            co = (matrix @ vert.co) * 1000
            co.yz = -co.z, co.y
            co = co.to_tuple(1)
            buffer.write(struct.pack("ddd", *co))
            buffer.write(struct.pack("ddd", *normal))
        # 写入面数据
        faces_num = len(mesh.polygons)
        buffer.write(struct.pack("I", faces_num))
        for poly in mesh.polygons:
            # 写顶点索引
            buffer.write(struct.pack("III", *poly.vertices))
            # 写材质
            mat = entity.material_slots[poly.material_index].material
            img_node = mat.node_tree.nodes.get("Image Texture")
            img_name = ""
            if img_node:
                img = img_node.image  # type: Image # type: ignore
                if img:
                    img_name = img.name
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

        # 如果有蒙皮和骨架
        skeleton = [ent_dict["skeleton"]]  # type: list[Object]
        if has_skin and skeleton is not None:
            ag_utils.select_active(context, skeleton[0])
            for obj in skeleton[0].children_recursive:
                obj.select_set(True)
                skeleton.append(obj)  # type: ignore
            # 原点到几何中心
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
            #
            buffer.write(struct.pack("I", len(skeleton)))
            for obj in skeleton:
                name = obj.name.encode("utf-8")
                buffer.write(struct.pack("I", len(name)))
                buffer.write(name)
                # 父节点索引
                if obj.parent is None:
                    buffer.write(struct.pack("i", -1))
                else:
                    parent_idx = skeleton.index(obj.parent)  # type: ignore
                    buffer.write(struct.pack("I", parent_idx))
                # 矩阵

        else:
            buffer.write(struct.pack("Ii", 1, -1))
            for row in Matrix():
                buffer.write(struct.pack("dddd", *row))
            buffer.write(struct.pack("I", verts_num))
            buffer.write(struct.pack("II", 0, 1))
            center = entity.location.copy() * 1000
            center.yz = -center.z, center.y
            buffer.write(struct.pack("dddd", *center, 1000))
            buffer.write(struct.pack("II", 0, verts_num))
        #
        with open(self.filepath, "wb") as f:
            f.write(buffer.getvalue())
        buffer.close()
        #
        bpy.data.meshes.remove(mesh)
        if lack_texture:
            self.report({"WARNING"}, "The object lacks texture")
        else:
            self.report(
                {"INFO"},
                f"{os.path.basename(self.filepath)}: {pgettext('Export successfully')}",
            )
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        ent_coll = None
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

            # if not self.main:
            #     # 仅可见
            #     if self.action == "2":
            #         if not coll.objects[0].visible_get():
            #             continue
            ent_coll = coll
            break
        if ent_coll is None:
            self.report(
                {"WARNING"}, "No collection with the prefix `Blade_Object_` was found"
            )
            return {"CANCELLED"}

        # 找到实体集合
        ent_dict = {
            "kind": ent_coll.name[13:],
            "objects": [],
            "skin": None,
            "skeleton": None,
            "anchors": [],
            "edges": [],
            "spikes": [],
            "trails": [],
            "fires": [],
            "lights": [],
        }

        for obj in ent_coll.objects:
            if not obj.visible_get():
                continue
            #
            if obj.name.lower().startswith("blade_skin"):
                ent_dict["skin"] = obj
            elif obj.name.lower().startswith("blade_skeleton"):
                ent_dict["skeleton"] = obj
            elif obj.name.lower().startswith("blade_anchor_"):
                ent_dict["anchors"].append(obj)
            elif (
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
            elif obj.name.lower().startswith("blade_light_"):
                ent_dict["lights"].append(obj)
            else:
                ent_dict["objects"].append(obj)
        #
        if not ent_dict["objects"]:
            self.report({"WARNING"}, "There are no visible entities objects")
            return {"CANCELLED"}
        # 找到实体对象
        self.ent_dict = ent_dict

        if not bpy.data.filepath or (not self.main and self.action == "2"):
            self.filepath = f"//{ent_dict['kind']}.bod"
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
