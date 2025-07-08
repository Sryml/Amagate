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
        anchor.show_in_front = True
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

    # 转换坐标空间
    from_old_exporter: BoolProperty(name="From Old Exporter", default=True)  # type: ignore
    filter_glob: StringProperty(default="*.bod", options={"HIDDEN"})  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context: Context):
        if os.path.splitext(self.filepath)[1].lower() != ".bod":
            self.report({"ERROR"}, "Not a bod file")
            return {"CANCELLED"}
        #
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        # 交换矩阵
        swap_matrix = Matrix(
            (
                (1, 0, 0, 0),
                (0, 0, 1, 0),  # y → z
                (0, -1, 0, 0),  # z → -y
                (0, 0, 0, 1),
            )
        )
        transform_space = not self.from_old_exporter
        filepath = os.path.join(data.ADDON_PATH, "bin/ent_component.dat")
        mesh_dict = pickle.load(open(filepath, "rb"))

        with open(self.filepath, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size
            ent_bm = bmesh.new()
            uv_layer = ent_bm.loops.layers.uv.verify()  # 获取或创建UV图层
            bm_verts = []  # type: list[bmesh.types.BMVert]
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
            # 顶点
            verts_num = unpack("I", f)[0]
            for i in range(verts_num):
                co = Vector(unpack("ddd", f)) / 1000
                if transform_space:
                    co.yz = co.z, -co.y
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
                    slot_index = ent_mesh.materials.find(img_name)
                    if slot_index == -1:
                        ent_mesh.materials.append(mat)
                        slot_index = len(ent_mesh.materials) - 1
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
                        ent_bm,
                        matrix=matrix,
                        verts=verts,
                    )
                    # 保存顶点索引
                    bones_vert_idx.append((vert_start, vert_start + numverts))
                #
                num = unpack("I", f)[0]
                for j in range(num):
                    pos = Vector(unpack("ddd", f)) / 1000
                    pos = matrix @ pos
                    if transform_space:
                        pos.yz = pos.z, -pos.y
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
            # if transform_space:
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
                    start, end = bones_vert_idx[idx]
                    group.add(list(range(start, end)), 1.0, "REPLACE")
                # 添加骨架修改器
                modifier = entity.modifiers.new("Armature", "ARMATURE")
                modifier.object = armature_obj  # type: ignore

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
                if parent_idx != -1 and armature is not None:
                    parent_bone = armature_obj.pose.bones[bones_name[parent_idx]]
                    bmesh.ops.transform(bm, matrix=parent_bone.matrix, verts=bm.verts)  # type: ignore
                    obj.parent = armature_obj  # type: ignore
                    obj.parent_type = "BONE"
                    obj.parent_bone = parent_bone.name
                obj.matrix_world = Matrix()

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
                if parent_idx != -1 and armature is not None:
                    parent_bone = armature_obj.pose.bones[bones_name[parent_idx]]
                    co = parent_bone.matrix @ co
                    obj.parent = armature_obj  # type: ignore
                    obj.parent_type = "BONE"
                    obj.parent_bone = parent_bone.name
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
                # 转换坐标轴
                if transform_space:
                    matrix = swap_matrix @ matrix @ swap_matrix.transposed()
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
                parent_idx = unpack("i", f)[0]  # type: int
                if parent_idx != -1:
                    if armature is not None:
                        parent_bone = armature_obj.pose.bones[bones_name[parent_idx]]
                        parent_matrix = parent_bone.matrix
                        matrix = parent_matrix @ matrix
                        # matrix = (
                        #     parent_matrix.to_quaternion().to_matrix().to_4x4() @ matrix
                        # )
                        # matrix.translation += parent_matrix.translation
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = parent_bone.name
                    else:
                        obj.parent = entity  # type: ignore
                #
                obj.matrix_world = matrix

            # 跳过 0x04
            f.seek(4, 1)

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
                if transform_space:
                    pt1.yz = pt1.z, -pt1.y
                    pt2.yz = pt2.z, -pt2.y
                    pt3.yz = pt3.z, -pt3.y
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
                if parent_idx != -1:
                    if armature is not None:
                        parent_bone = armature_obj.pose.bones[bones_name[parent_idx]]
                        parent_matrix = parent_bone.matrix
                        quat = parent_matrix.to_quaternion()
                        pt1 = parent_matrix @ pt1
                        pt2 = quat @ pt2
                        pt3 = quat @ pt3
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = parent_bone.name
                    else:
                        obj.parent = entity  # type: ignore
                #
                mesh_data = mesh_dict["Blade_Edge_1"]
                #
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
                matrix = Matrix((x_axis, y_axis, z_axis)).transposed()
                # quat = pt2.normalized().to_track_quat("Y", "Z")
                # quat = pt3.normalized().to_track_quat("X", "Z") @ quat
                bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=matrix, verts=bm.verts)  # type: ignore

                bm.to_mesh(mesh)
                bm.free()
                #
                obj.matrix_world = Matrix.Translation(pt1)

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
                if transform_space:
                    pt1.yz = pt1.z, -pt1.y
                    pt2.yz = pt2.z, -pt2.y
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
                if parent_idx != -1:
                    if armature is not None:
                        parent_bone = armature_obj.pose.bones[bones_name[parent_idx]]
                        parent_matrix = parent_bone.matrix
                        pt1 = parent_matrix @ pt1
                        pt2 = parent_matrix @ pt2
                        obj.parent = armature_obj  # type: ignore
                        obj.parent_type = "BONE"
                        obj.parent_bone = parent_bone.name
                    else:
                        obj.parent = entity  # type: ignore
                #
                mesh_data = mesh_dict["Blade_Spike_1"]
                #
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
            # 组
            num = unpack("I", f)[0]
            for idx in range(num):
                group = unpack("B", f)[0]
                if idx >= len(ent_mesh.polygons):
                    continue
                ent_mesh.attributes["amagate_group"].data[idx].value = 0 if group == 0 else ag_utils.uint_to_int(1 << (group - 1))  # type: ignore

            # 如果不是文件尾
            if f.tell() != file_size:
                # 肢解组
                num = unpack("I", f)[0]
                for idx in range(num):
                    group = unpack("i", f)[0]
                    if idx >= len(ent_mesh.polygons):
                        continue
                    ent_mesh.attributes["amagate_mutilation_group"].data[idx].value = group  # type: ignore

                # 轨迹
                num = unpack("I", f)[0]
                for idx in range(num):
                    mark = unpack("I", f)[0]  # 默认0
                    if mark != 0:
                        logger.debug(f"Track - mark not 0: {mark}")
                    parent_idx = unpack("i", f)[0]  # type: int
                    pt1 = Vector(unpack("ddd", f)) / 1000
                    pt2 = Vector(unpack("ddd", f)) / 1000
                    if transform_space:
                        pt1.yz = pt1.z, -pt1.y
                        pt2.yz = pt2.z, -pt2.y
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
                    if parent_idx != -1:
                        if armature is not None:
                            parent_bone = armature_obj.pose.bones[
                                bones_name[parent_idx]
                            ]
                            parent_matrix = parent_bone.matrix
                            pt1 = parent_matrix @ pt1
                            pt2 = parent_matrix @ pt2
                            obj.parent = armature_obj  # type: ignore
                            obj.parent_type = "BONE"
                            obj.parent_bone = parent_bone.name
                        else:
                            obj.parent = entity  # type: ignore
                    #
                    obj.matrix_world = Matrix()
                    bm = bmesh.new()
                    bm.verts.new(pt1)
                    bm.verts.new(pt2)
                    bm.edges.new(bm.verts)

                    bm.to_mesh(mesh)
                    bm.free()

        ag_utils.select_active(context, entity)  # type: ignore
        for obj in ent_coll.objects:
            if not obj.parent:
                obj.select_set(True)
        # if armature is not None:
        #     armature_obj.select_set(True)
        # 纠正方向
        if not transform_space:
            for obj in context.selected_objects:
                obj.matrix_world = (
                    Matrix.Rotation(-math.pi / 2, 4, "X") @ obj.matrix_world
                )
            # entity.rotation_euler = Euler((-math.pi / 2, 0, 0))
            # if armature is not None:
            #     armature_obj.rotation_euler = Euler((-math.pi / 2, 0, 0))
        # 调整实体中心
        for obj in context.selected_objects:
            obj.location += center
        # entity.location = center
        # if armature is not None:
        #     armature_obj.location = center

        # bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.select_all(action="DESELECT")
        #
        bpy.ops.view3d.view_all(center=True)
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
        #
        armature_obj = ent_dict["skeleton"]  # type: Object
        if armature_obj is not None:
            armature_matrix = armature_obj.matrix_world.copy()
            armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        else:
            armature = None  # type: ignore
            armature_matrix = Matrix()
        # 获取主实体
        buffer = BytesIO()
        if ent_dict["skin"] is not None:
            entity = ent_dict["skin"]  # type: Object
            ag_utils.select_active(context, entity)
            for obj in entity.children_recursive:  # type: ignore
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
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        # bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        #
        depsgraph = context.evaluated_depsgraph_get()
        # 交换矩阵
        swap_matrix = Matrix(
            (
                (1, 0, 0, 0),
                (0, 0, -1, 0),  # y → -z
                (0, 1, 0, 0),  # z → y
                (0, 0, 0, 1),
            )
        )

        entity = entity.evaluated_get(depsgraph)
        ent_mesh = entity.data  # type: bpy.types.Mesh # type: ignore
        # matrix = entity.matrix_world.copy()
        # quat = matrix.to_quaternion()
        uv_layer = ent_mesh.uv_layers.active.data

        # 导出BOD
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
        if armature is not None:
            bone_verts_start = 0
            for bone in armature_obj.pose.bones:
                bone_matrix = bones_matrix.setdefault(
                    bone.name,
                    (
                        armature_matrix @ bone.matrix,
                        (armature_matrix @ bone.matrix).inverted(),
                    ),
                )[1]
                # bone_matrix = bone.matrix.inverted()  # type: Matrix
                name = bone.name
                vertex_indices = ag_utils.get_vertex_in_group(
                    entity, name
                )  # type: set[int]
                co_list = []
                max_length = 0
                for idx in vertex_indices:
                    global_verts_map[idx] = global_verts_count
                    global_verts_count += 1
                    #
                    vert = ent_mesh.vertices[idx]

                    normal = bone_matrix.to_quaternion() @ vert.normal
                    normal.yz = -normal.z, normal.y
                    co = bone_matrix @ vert.co
                    co *= 1000
                    co.yz = -co.z, co.y
                    co_list.append(co)
                    length = co.length
                    if length > max_length:
                        max_length = length
                    #
                    buffer.write(struct.pack("ddd", *co))
                    buffer.write(struct.pack("ddd", *normal))
                #
                bone_verts_num = len(co_list)
                bone_center = sum(co_list, Vector()) / len(co_list)
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
                img_node = mat.node_tree.nodes.get("Image Texture")
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
                    matrix = bones_matrix[parent_bone.name][1] @ matrix
                    # matrix = (
                    #     armature_matrix @ parent_bone.matrix.inverted() @ bone.matrix
                    # )

                matrix = swap_matrix @ matrix @ swap_matrix.transposed()
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
            buffer.write(struct.pack("Ii", 1, -1))
            for row in Matrix():
                buffer.write(struct.pack("dddd", *row))
            buffer.write(struct.pack("I", verts_num))
            buffer.write(struct.pack("I", 0))
            #
            buffer.write(struct.pack("I", 1))
            center = entity.location * 1000
            center.yz = -center.z, center.y
            buffer.write(struct.pack("dddd", *center, 500))
            buffer.write(struct.pack("II", 0, verts_num))

        # 中心
        buffer.write(
            struct.pack("dddd", 0, 0, 0, 500)
        )  # XXX 是否需要正确的中心到边界框最长距离

        obj: Object
        # 火焰
        buffer.write(struct.pack("I", len(ent_dict["fires"])))
        for index, obj in enumerate(ent_dict["fires"]):
            obj = obj.evaluated_get(depsgraph)
            matrix_world = obj.matrix_world.copy()
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            buffer.write(struct.pack("I", len(mesh.vertices)))
            #
            if obj.parent_bone in bones_name:
                # parent_matrix = armature_obj.pose.bones[obj.parent_bone].matrix
                parent_matrix = bones_matrix[obj.parent_bone][1]
                parent_idx = bones_name.index(obj.parent_bone)
            else:
                parent_matrix = None
                parent_idx = -1
            for vert in mesh.vertices:
                if parent_matrix:
                    co = parent_matrix @ matrix_world @ vert.co
                else:
                    co = matrix_world @ vert.co
                co *= 1000
                co.yz = -co.z, co.y
                #
                buffer.write(struct.pack("ddd", *co))
                buffer.write(struct.pack("I", 3))  # 固定3
                buffer.write(struct.pack("i", parent_idx))
                buffer.write(struct.pack("I", index))

        # 灯光
        buffer.write(struct.pack("I", len(ent_dict["lights"])))
        for obj in ent_dict["lights"]:
            obj = obj.evaluated_get(depsgraph)
            strength = 0.1
            precision = 0.01
            buffer.write(struct.pack("f", strength))
            buffer.write(struct.pack("f", precision))
            #
            if obj.parent_bone in bones_name:
                parent_matrix = bones_matrix[obj.parent_bone][1]
                parent_idx = bones_name.index(obj.parent_bone)
            else:
                parent_matrix = None
                parent_idx = -1
            if parent_matrix:
                co = parent_matrix @ obj.matrix_world.translation
            else:
                co = obj.matrix_world.to_translation()
            co *= 1000
            co.yz = -co.z, co.y
            #
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
            if obj.parent_bone in bones_name:
                parent_matrix = bones_matrix[obj.parent_bone][1]
                parent_idx = bones_name.index(obj.parent_bone)
            else:
                parent_matrix = None
                if obj.parent:
                    parent_idx = 0
                else:
                    parent_idx = -1
            if parent_matrix:
                matrix = parent_matrix @ obj.matrix_world
            else:
                matrix = obj.matrix_world.copy()
            #
            matrix = swap_matrix @ matrix @ swap_matrix.transposed()
            matrix.translation *= 1000  # 转换位置单位
            matrix.transpose()  # 转置
            for row in matrix:
                buffer.write(struct.pack("dddd", *row))
            buffer.write(struct.pack("i", parent_idx))

        #
        buffer.write(struct.pack("I", 4))  # 固定4

        # 边缘
        buffer.write(struct.pack("I", len(ent_dict["edges"])))
        for obj in ent_dict["edges"]:
            obj = obj.evaluated_get(depsgraph)
            matrix_world = obj.matrix_world.copy()
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            #
            pt1 = (
                matrix_world @ mesh.vertices[0].co + matrix_world @ mesh.vertices[1].co
            ) / 2
            pt2 = matrix_world @ mesh.vertices[1].co - pt1
            pt3 = (
                matrix_world @ mesh.vertices[2].co + matrix_world @ mesh.vertices[3].co
            ) / 2 - pt1
            #
            if obj.parent_bone in bones_name:
                parent_matrix = bones_matrix[obj.parent_bone][1]
                parent_idx = bones_name.index(obj.parent_bone)
            else:
                parent_matrix = None
                if obj.parent:
                    parent_idx = 0
                else:
                    parent_idx = -1
            if parent_matrix:
                pt1 = parent_matrix @ pt1
                pt2 = parent_matrix @ pt2
                pt3 = parent_matrix @ pt3
            pt1 *= 1000
            pt2 *= 1000
            pt3 *= 1000
            pt1.yz = -pt1.z, pt1.y
            pt2.yz = -pt2.z, pt2.y
            pt3.yz = -pt3.z, pt3.y
            #
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
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            #
            pt1 = matrix_world @ mesh.vertices[0].co
            pt2 = matrix_world @ mesh.vertices[1].co
            #
            if obj.parent_bone in bones_name:
                parent_matrix = bones_matrix[obj.parent_bone][1]
                parent_idx = bones_name.index(obj.parent_bone)
            else:
                parent_matrix = None
                if obj.parent:
                    parent_idx = 0
                else:
                    parent_idx = -1
            if parent_matrix:
                pt1 = parent_matrix @ pt1
                pt2 = parent_matrix @ pt2
            pt1 *= 1000
            pt2 *= 1000
            pt1.yz = -pt1.z, pt1.y
            pt2.yz = -pt2.z, pt2.y
            #
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
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            #
            pt1 = matrix_world @ mesh.vertices[0].co
            pt2 = matrix_world @ mesh.vertices[1].co
            #
            if obj.parent_bone in bones_name:
                parent_matrix = bones_matrix[obj.parent_bone][1]
                parent_idx = bones_name.index(obj.parent_bone)
            else:
                parent_matrix = None
                if obj.parent:
                    parent_idx = 0
                else:
                    parent_idx = -1
            if parent_matrix:
                pt1 = parent_matrix @ pt1
                pt2 = parent_matrix @ pt2
            pt1 *= 1000
            pt2 *= 1000
            pt1.yz = -pt1.z, pt1.y
            pt2.yz = -pt2.z, pt2.y
            #
            buffer.write(struct.pack("I", 0))  # 固定0
            buffer.write(struct.pack("i", parent_idx))
            buffer.write(struct.pack("ddd", *pt1))
            buffer.write(struct.pack("ddd", *pt2))

        # 写入文件
        with open(self.filepath, "wb") as f:
            f.write(buffer.getvalue())
        buffer.close()
        #
        bpy.data.meshes.remove(bpy.data.meshes[ent_mesh.name])
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
        if not ent_dict["objects"] and not ent_dict["skin"]:
            self.report({"WARNING"}, "There are no visible entities objects")
            return {"CANCELLED"}
        # print([i.name for i in ent_dict["objects"]])
        # return {"CANCELLED"}
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
