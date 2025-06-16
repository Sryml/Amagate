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
import typing
import numpy as np
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

from . import data, L3D_data
from . import ag_utils


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


############################
epsilon: float = ag_utils.epsilon
epsilon2: float = ag_utils.epsilon2

REGION_DATA = {}
# 分离后的所有扇区
SECTORS_LIST = []  # type: list[list[Object]]
SEPARATE_DATA = {}  # type: Any

# CONNECT_DATA = {}  # type: Any

############################
############################ Separate Convex
############################


def pre_knife_project():
    """投影切割预处理"""
    context = bpy.context
    separate = SEPARATE_DATA["separate_list"][
        SEPARATE_DATA["index"]
    ]  # type: tuple[Object, set[int], set[int], list[int], list[Object], bmesh.types.BMesh, Vector]
    (
        sec,
        faces_int_idx,  # 内部面
        faces_int_idx_prime,  # 内部面 (排除垂直面)
        faces_exterior_idx,  # 与内部面共边的外部面
        knife_project,  # 投影切割刀具
        knife_bm,  # 投影切割刀具BMesh
        proj_normal_prime,  # 投影法向
    ) = separate
    region = REGION_DATA["region"]  # type: bpy.types.Region
    # sec, faces_index, knifes, proj_normal_prime = knife_project.pop()

    # 确保网格数据为单用户的
    sec_data = sec.amagate_data.get_sector_data()
    sec_data.mesh_unique()

    bpy.ops.object.select_all(action="DESELECT")  # 取消选择
    context.view_layer.objects.active = sec  # 设置活动物体
    bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
    bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
    for knife in knife_project:
        knife.select_set(True)
    ag_utils.set_view_rotation(region, proj_normal_prime)
    region.data.view_perspective = "ORTHO"

    bpy.app.timers.register(knife_project_timer, first_interval=0.05)


def knife_project_timer():
    """投影切割定时器"""
    context = bpy.context
    separate = SEPARATE_DATA["separate_list"][
        SEPARATE_DATA["index"]
    ]  # type: tuple[Object, set[int], set[int], list[int], list[Object], bmesh.types.BMesh, Vector]
    (
        sec,
        faces_int_idx,  # 内部面
        faces_int_idx_prime,  # 内部面 (排除垂直面)
        faces_exterior_idx,  # 与内部面共边的外部面
        knife_project,  # 投影切割刀具
        knife_bm,  # 投影切割刀具BMesh
        proj_normal_prime,  # 投影法向
    ) = separate
    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    # 隐藏内部面
    for i in faces_int_idx:
        bm.faces[i].hide = True
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

    # 保存面
    faces_int = [bm.faces[i] for i in faces_int_idx]
    faces_int_prime = [bm.faces[i] for i in faces_int_idx_prime]

    # 覆盖上下文
    with context.temp_override(
        area=REGION_DATA["area"],
        region=REGION_DATA["region"],
    ):
        bpy.ops.mesh.knife_project(cut_through=False)  # 投影切割

        matrix_world = sec.matrix_world
        # 检查切割出来的面是否与刀具面一一对应
        # 从bmesh构建BVHTree
        # verts = [v.co for v in knife_bm.verts]
        # faces = [[v.index for v in f.verts] for f in knife_bm.faces]
        # bvh = bvhtree.BVHTree.FromPolygons(verts, faces)
        bvh = bvhtree.BVHTree.FromBMesh(knife_bm)
        face_lst = {
            i: [] for i in range(len(knife_bm.faces))
        }  # type: dict[int, list[bmesh.types.BMFace]]
        for f in bm.faces:
            # 访问选中的面
            if f.select:
                # 定义射线起点、方向和距离
                ray_origin = matrix_world @ f.calc_center_bounds()
                ray_direction = proj_normal_prime
                # 执行射线检测
                hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                    bvh, ray_origin, ray_direction
                )
                if hit_index is not None:
                    face_lst[hit_index].append(f)
        #
        for faces in face_lst.values():
            if len(faces) > 1:
                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                for f in faces:
                    f.select_set(True)
                    bmesh.update_edit_mesh(
                        mesh, loop_triangles=False, destructive=False
                    )
                # 尝试融并面
                bpy.ops.mesh.dissolve_faces()

    # 恢复面索引
    separate[1] = {f.index for f in faces_int}  # type: ignore
    separate[2] = {f.index for f in faces_int_prime}  # type: ignore

    # 删除刀具BMesh
    knife_bm.free()
    # 删除刀具
    for obj in knife_project:
        bpy.data.meshes.remove(obj.data)  # type: ignore
    # 显示内部面
    bm.faces.ensure_lookup_table()
    for f in faces_int:
        f.hide = False
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    SEPARATE_DATA["index"] += 1
    if SEPARATE_DATA["index"] < len(SEPARATE_DATA["separate_list"]):
        pre_knife_project()
    else:
        knife_project_done()


def knife_project_done():
    """投影切割完成，开始分离"""
    global SECTORS_LIST, REGION_DATA

    SECTORS_LIST = []  # 初始化
    context = bpy.context
    separate_list = SEPARATE_DATA[
        "separate_list"
    ]  # type: list[tuple[Object, set[int], set[int], list[int], list[Object], bmesh.types.BMesh, Vector]]
    for (
        sec,
        faces_int_idx,  # 内部面
        faces_int_idx_prime,  # 内部面 (排除垂直面)
        faces_exterior_idx,  # 与内部面共边的外部面
        knife_project,  # 投影切割刀具
        knife_bm,  # 投影切割刀具BMesh
        proj_normal_prime,  # 投影法向
    ) in separate_list:
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        matrix_world = sec.matrix_world
        proj_normal_prime = matrix_world.to_quaternion().inverted() @ proj_normal_prime
        proj_normal_prime.normalize()
        # proj_normal_prime = Vector(proj_normal_prime.normalized().to_tuple(4))
        bpy.ops.object.select_all(action="DESELECT")  # 取消选择
        context.view_layer.objects.active = sec  # 设置活动物体
        sec.select_set(True)  # 选择物体
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")  # 选择面模式
        sec_bm = bmesh.from_edit_mesh(mesh)  # type: ignore
        sec_bm.faces.ensure_lookup_table()

        # 投影切割后的分离操作
        knife_project_separate(mesh, sec_bm, faces_int_idx_prime, proj_normal_prime)

        bpy.ops.object.mode_set(mode="OBJECT")

        # 分离后的处理
        selected_objects = knife_project_separate_post(sec)
        SECTORS_LIST.append(selected_objects)

    bpy.ops.object.select_all(action="DESELECT")  # 取消选择
    for lst in SECTORS_LIST:
        for sec in lst:
            sec.select_set(True)
    if context.selected_objects:
        context.view_layer.objects.active = context.selected_objects[0]

    area = REGION_DATA["area"]  # type: bpy.types.Area
    region = REGION_DATA["region"]  # type: bpy.types.Region
    region.data.view_rotation = REGION_DATA["view_rotation"]
    region.data.view_perspective = REGION_DATA["view_perspective"]
    area.spaces[0].shading.type = REGION_DATA["shading_type"]  # type: ignore

    with context.temp_override(
        area=REGION_DATA["area"],
        region=REGION_DATA["region"],
    ):
        bpy.ops.amagate.report_message(message="Separate Done")  # type: ignore

    if SEPARATE_DATA["undo"]:
        bpy.ops.ed.undo_push(message="Separate Convex")

    scene_data = context.scene.amagate_data
    auto_connect = scene_data.operator_props.sec_separate_connect
    if auto_connect:
        with context.temp_override(
            area=REGION_DATA["area"],
            region=REGION_DATA["region"],
        ):
            bpy.ops.amagate.sector_connect_vm(undo=True, from_separate=True)  # type: ignore

    REGION_DATA = {}  # 清空区域数据


# 投影切割后的分离操作
def knife_project_separate(mesh, sec_bm, faces_int_idx_prime, proj_normal_prime):
    # type: (bpy.types.Mesh,bmesh.types.BMesh, set[int], Vector) -> Any
    """投影切割后的分离操作"""
    faces_int_prime = [sec_bm.faces[i] for i in faces_int_idx_prime]
    for face in faces_int_prime:
        sec_bm.verts.ensure_lookup_table()
        v1 = face.verts[0]
        # coords_set = set(v.co.to_tuple(4) for v in face.verts)
        verts_index = set()
        normal = face.normal.copy()
        dot = proj_normal_prime.dot(normal)
        if dot < 0:
            normal = -normal
            dot = -dot
        if dot > epsilon2:
            dot = 1
        # 转为2D多边形
        u = normal.cross(Vector((1, 0, 0)))  # type: Vector
        if u.length < epsilon:  # 防止法向量平行于 x 轴
            u = normal.cross(Vector((0, 1, 0)))
        u.normalize()
        v = normal.cross(u).normalized()  # type: Vector
        polygon = [(u.dot(vert.co), v.dot(vert.co)) for vert in face.verts]
        # 刀具面顶点字典
        verts_dict = {v.index: [] for v in face.verts}  # type: dict[int, list[int]]
        # print(f"polygon: {polygon}")
        # 获取投影在刀具面中的所有顶点
        for v2 in sec_bm.verts:
            if v2 in face.verts:
                continue
            t = (v1.co - v2.co).dot(normal) / dot
            # 点在刀具面外部，跳过
            if t < 0:
                continue

            proj_point = v2.co + proj_normal_prime * t

            # key = proj_point.to_tuple(4)
            # if key in coords_set:
            #     verts_index.add(v2.index)
            for f_vert in face.verts:
                # 投影到顶点的情况
                if (proj_point - f_vert.co).length < 1e-3:
                    verts_index.add(v2.index)
                    verts_dict[f_vert.index].append(v2.index)
                    break
            # 没有投影到顶点，也许在边上或者在面的内部
            else:
                proj_point_2d = u.dot(proj_point), v.dot(proj_point)
                if ag_utils.is_point_in_polygon(proj_point_2d, polygon):
                    verts_index.add(v2.index)

        # 新增边
        for f_vert_idx, verts_idx in verts_dict.items():
            if verts_idx == []:
                continue
            co = sec_bm.verts[f_vert_idx].co
            # 按距离排序v
            verts_idx.sort(key=lambda x: (sec_bm.verts[x].co - co).length)
            verts_idx.insert(0, f_vert_idx)
            # 头部顶点的相连面集合
            head_faces = {f.index for f in sec_bm.verts[verts_idx[0]].link_faces}
            for i in range(len(verts_idx) - 1):
                v1 = sec_bm.verts[verts_idx[i]]
                v2 = sec_bm.verts[verts_idx[i + 1]]
                tail_faces = {f.index for f in v2.link_faces}
                # 如果与头部顶点没有共同面，跳过
                if not head_faces.intersection(tail_faces):
                    break

                head_faces = tail_faces

                for e in v1.link_edges:
                    # 找到v1与v2的边，跳过
                    if e.other_vert(v1) == v2:
                        break
                # v1与v2不存在边，添加边
                else:
                    # ag_utils.debugprint(f"add edge: {v1.index} {v2.index}")
                    bmesh.ops.connect_vert_pair(sec_bm, verts=[v1, v2])
                    bmesh.update_edit_mesh(mesh)

        # 按照顶点选中面并分离
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        verts_index.update(v.index for v in face.verts)
        for f in sec_bm.faces:
            v_index = set(v.index for v in f.verts)
            if v_index.issubset(verts_index):
                f.select_set(True)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        #### test
        # print(f"vert: {[i.index for i in sec_bm.verts]}")
        # print(f"verts_index: {verts_index}")
        # bpy.ops.mesh.select_mode(type="VERT")
        # sec_bm.verts.ensure_lookup_table()
        # for i in verts_index:
        #     sec_bm.verts[i].select_set(True)
        # if faces.index(f) == 1:
        #     break
        #### test
        bpy.ops.mesh.separate(type="SELECTED")  # 按选中项分离


# 投影切割分离后的处理
def knife_project_separate_post(main_sec):
    # type: (Object) -> list[Object]
    """投影切割分离后的处理"""
    sec_data = main_sec.amagate_data.get_sector_data()
    context = bpy.context
    selected_objects = (
        context.selected_objects.copy()
    )  # type: list[Object] # type: ignore
    selected_objects.remove(main_sec)
    # 删除空网格
    if len(main_sec.data.vertices) == 0:  # type: ignore
        ag_utils.delete_sector(main_sec)
        main_sec = None  # type: ignore
    else:
        sec_data.is_2d_sphere = ag_utils.is_2d_sphere(main_sec)
        sec_data.is_convex = ag_utils.is_convex(main_sec)

    # 对分离出的新对象执行复制后初始化
    for sec in selected_objects.copy():
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        # 按距离合并顶点
        bpy.ops.object.select_all(action="DESELECT")  # 取消选择
        context.view_layer.objects.active = sec  # 设置活动物体
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="VERT")  # 选择顶点模式
        bpy.ops.mesh.select_all(action="SELECT")  # 全选
        with contextlib.redirect_stdout(StringIO()):
            bpy.ops.mesh.remove_doubles(threshold=0.0001)  # 合并顶点
        bpy.ops.object.mode_set(mode="OBJECT")
        # 删除平面物体
        visited_verts = list(mesh.polygons[0].vertices)
        base_point = mesh.vertices[visited_verts[0]].co
        normal = mesh.polygons[0].normal.copy()
        vector1 = base_point + normal
        for f in mesh.polygons[1:]:
            # 存在法向不平行的面，跳过
            if abs(f.normal.dot(normal)) < epsilon2:
                break
            # 法向平行，判断是否在同一平面
            is_solid = False  # 是否为立体的
            for f_vert_idx in f.vertices:
                if f_vert_idx not in visited_verts:
                    visited_verts.append(f_vert_idx)
                    vector2 = mesh.vertices[f_vert_idx].co - base_point
                    # 点不在同一平面，跳过
                    if abs(vector1.dot(vector2)) > epsilon:
                        is_solid = True
                        break
            # 点不在同一平面，跳过
            if is_solid:
                break
        else:
            selected_objects.remove(sec)
            bpy.data.meshes.remove(mesh)
            continue
        #
        sec_data = sec.amagate_data.get_sector_data()
        sec_data.init(post_copy=True)

    if main_sec:
        selected_objects.append(main_sec)
    return selected_objects


############################
############################ 扇区操作
############################


# 转换为扇区
class OT_Sector_Convert(bpy.types.Operator):
    bl_idname = "amagate.sector_convert"
    bl_label = "Convert to Sector"
    bl_description = "Convert selected objects to sector"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        original_selection = (
            context.selected_objects
        )  # type: list[Object] # type: ignore
        if not original_selection:
            self.report({"INFO"}, "No objects selected")
            return {"CANCELLED"}

        # 非扇区的网格对象
        mesh_objects = [
            obj
            for obj in original_selection
            if obj.type == "MESH"
            and not (obj.amagate_data.is_sector or obj.amagate_data.is_gho_sector)
        ]  # type: list[Object] # type: ignore
        if not mesh_objects:
            self.report({"INFO"}, "No mesh objects selected")
            return {"CANCELLED"}

        # 如果缺少活跃对象，则指定选中列表的第一个为活跃对象
        if not context.active_object:
            context.view_layer.objects.active = mesh_objects[0]

        # 选择所有 MESH 对象
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)  # 选择 MESH 对象

        # bpy.ops.object.mode_set(mode="EDIT")
        # # 全选所有面
        # bpy.ops.mesh.select_all(action="SELECT")
        # # 重新计算法向（内侧）
        # bpy.ops.mesh.normals_make_consistent(inside=True)
        # bpy.ops.object.mode_set(mode="OBJECT")

        # 恢复选择
        # bpy.ops.object.select_all(action="DESELECT")
        # for obj in original_selection:
        #     obj.select_set(True)

        for obj in mesh_objects:
            if not obj.amagate_data.get_sector_data():
                obj.amagate_data.set_sector_data()
                sector_data = obj.amagate_data.get_sector_data()
                sector_data.init()
        # data.area_redraw("VIEW_3D")
        L3D_data.update_scene_edit_mode()
        return {"FINISHED"}


# 创建虚拟扇区
class OT_GhostSector_Create(bpy.types.Operator):
    bl_idname = "amagate.ghost_sector_create"
    bl_label = "Create Ghost Sector"
    bl_description = ""
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        if "EDIT" in context.mode:
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

        bpy.ops.mesh.primitive_plane_add()
        gsec = context.active_object
        mesh = gsec.data  # type: bpy.types.Mesh # type: ignore
        # 确保法线向下
        if mesh.polygons[0].normal.dot(Vector((0, 0, 1))) > 0:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.reverse_faces(bm, faces=bm.faces)  # type: ignore
            bm.to_mesh(mesh)
            bm.free()

        # 移动到当前视图焦点
        rv3d = context.region_data
        gsec.location = rv3d.view_location.to_tuple(0)

        # 设置视图属性
        gsec.color = (1.0, 0.3, 0, 1)
        gsec.hide_render = True
        gsec.visible_camera = False
        gsec.visible_shadow = False
        gsec.display.show_shadows = False
        gsec.display_type = "WIRE"
        # 重命名
        name = f"SectorGhost"
        gsec.rename(name, mode="SAME_ROOT")
        gsec.data.rename(name, mode="SAME_ROOT")
        coll = L3D_data.ensure_collection(L3D_data.GS_COLL)
        # 链接到集合
        if coll not in gsec.users_collection:
            # 清除集合
            gsec.users_collection[0].objects.unlink(gsec)
            # 链接到集合
            data.link2coll(gsec, coll)
        #
        gsec.amagate_data.set_ghost_sector_data()
        gsec_data = gsec.amagate_data.get_ghost_sector_data()
        # 添加修改器
        modifier = gsec.modifiers.new("", type="SOLIDIFY")
        modifier.thickness = gsec_data.height  # type: ignore

        L3D_data.update_scene_edit_mode()
        return {"FINISHED"}


# 连接扇区
class OT_Sector_Connect(bpy.types.Operator):
    bl_idname = "amagate.sector_connect"
    bl_label = "Connect Sectors"
    bl_description = "Connect selected sectors"
    # bl_options = {"UNDO"}

    undo: BoolProperty(default=True)  # type: ignore
    is_button: BoolProperty(default=False)  # type: ignore
    # 自动分离，仅用于内部传参，如果为-1，则使用UI开关值
    # auto_separate: IntProperty(default=-1)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        # 如果是从F3执行，获取当前选中的扇区
        if not self.is_button:
            L3D_data.SELECTED_SECTORS, L3D_data.ACTIVE_SECTOR = (
                ag_utils.get_selected_sectors()
            )
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        selected_sectors = L3D_data.SELECTED_SECTORS.copy()

        # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
        if "EDIT" in context.mode:
            bpy.ops.object.mode_set(mode="OBJECT")
            L3D_data.geometry_modify_post(selected_sectors)
            L3D_data.update_scene_edit_mode()

        # if len(selected_sectors) < 2:
        #     self.report({"WARNING"}, "Select at least two sectors")
        #     return {"CANCELLED"}

        for i in range(len(selected_sectors) - 1, -1, -1):
            sec = selected_sectors[i]
            sec_data = sec.amagate_data.get_sector_data()
            # 如果选中扇区存在非凸，排除
            if not sec_data.is_convex:
                selected_sectors.remove(sec)

        if len(selected_sectors) < 2:
            self.report({"WARNING"}, "Select at least two convex sectors")
            return {"CANCELLED"}

        self.failed_lst = []  # type: list[str] # 失败列表

        active_object = context.active_object

        # 确保网格数据为单用户的
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            sec_data.mesh_unique()
            # 应用不均匀缩放
            scale = sec.scale
            if scale.x != scale.y or scale.x != scale.z:
                ag_utils.select_active(context, sec)
                bpy.ops.object.transform_apply(
                    location=False, rotation=False, scale=True
                )

        self.connect(context, selected_sectors)

        # 恢复选择
        ag_utils.select_active(context, selected_sectors[0])
        for obj in selected_sectors:
            obj.select_set(True)
        context.view_layer.objects.active = active_object

        # 如果有连接失败的扇区，提示
        if self.failed_lst:
            if len(self.failed_lst) == len(selected_sectors):
                self.report({"WARNING"}, "All sectors are unconnectable")
            else:
                self.report(
                    {"WARNING"},
                    f"{pgettext('Unconnectable sectors')}: {self.failed_lst}",
                )
        else:
            self.report({"INFO"}, "Sectors connected successfully")

        if self.undo:
            bpy.ops.ed.undo_push(message="Connect Sectors")
        return {"FINISHED"}

    def connect(self, context: Context, sectors: list[Object]):
        success = self.success = set()

        for sec_idx_1, sec_1 in enumerate(sectors):
            sec_data_1 = sec_1.amagate_data.get_sector_data()
            matrix_1 = sec_1.matrix_world
            mesh_1 = sec_1.data  # type: bpy.types.Mesh # type: ignore
            #
            for sec_idx_2, sec_2 in enumerate(sectors):
                if sec_idx_2 <= sec_idx_1:
                    continue

                sec_data_2 = sec_2.amagate_data.get_sector_data()
                matrix_2 = sec_2.matrix_world
                mesh_2 = sec_2.data  # type: bpy.types.Mesh # type: ignore
                #
                sec_bm_1 = bmesh.new()
                sec_bm_1.from_mesh(mesh_1)
                conn_layer_1 = sec_bm_1.faces.layers.int.get("amagate_connected")
                tex_id_layer_1 = sec_bm_1.faces.layers.int.get("amagate_tex_id")
                # for face in sec_bm_1.faces:
                #     if face[layer] != 0:  # type: ignore
                #         bmesh.ops.delete(sec_bm_1, geom=[face], context="FACES")
                #
                sec_bm_2 = bmesh.new()
                sec_bm_2.from_mesh(mesh_2)
                conn_layer_2 = sec_bm_2.faces.layers.int.get("amagate_connected")
                tex_id_layer_2 = sec_bm_2.faces.layers.int.get("amagate_tex_id")
                # for face in sec_bm_2.faces:
                #     if face[layer] != 0:  # type: ignore
                #         bmesh.ops.delete(sec_bm_2, geom=[face], context="FACES")

                #
                has_coplane = False  # 是否找到共平面
                for face_1 in sec_bm_1.faces:
                    if face_1[conn_layer_1] != 0 or face_1[tex_id_layer_1] == -1:  # type: ignore
                        continue
                    normal_1 = matrix_1.to_quaternion() @ face_1.normal
                    for face_2 in sec_bm_2.faces:
                        if face_2[conn_layer_2] != 0 or face_2[tex_id_layer_2] == -1:  # type: ignore
                            continue
                        normal_2 = matrix_2.to_quaternion() @ face_2.normal

                        # 如果法向不是完全相反，跳过
                        if normal_1.dot(normal_2) > -epsilon2:
                            continue

                        # 获取面的顶点坐标
                        co1 = matrix_1 @ face_1.verts[0].co
                        co2 = matrix_2 @ face_2.verts[0].co
                        dir = (co2 - co1).normalized()
                        # 如果顶点不是在同一平面，跳过
                        dot = abs(dir.dot(normal_1))
                        # ag_utils.debugprint("dot", dot)
                        if dot > epsilon:
                            continue

                        has_coplane = True
                        # 获取平展面并排除连接面
                        sec_bm_1.faces.ensure_lookup_table()
                        sec_bm_2.faces.ensure_lookup_table()

                        flat_face_1 = ag_utils.get_linked_flat(face_1)
                        flat_face_1 = [f for f in flat_face_1 if f[conn_layer_1] == 0 and f[tex_id_layer_1] != -1]  # type: ignore

                        flat_face_2 = ag_utils.get_linked_flat(face_2)
                        flat_face_2 = [f for f in flat_face_2 if f[conn_layer_2] == 0 and f[tex_id_layer_2] != -1]  # type: ignore

                        sec_info = [
                            {
                                "sec": sec_1,
                                "bm": sec_bm_1,
                                "bm_face": flat_face_1,
                                # "flat_info": (),
                                # "is_sky": False,
                            },
                            {
                                "sec": sec_2,
                                "bm": sec_bm_2,
                                "bm_face": flat_face_2,
                                # "flat_info": (),
                                # "is_sky": False,
                            },
                        ]
                        # ag_utils.debugprint("get_knife")
                        # 获取刀具
                        knife, knife_bm = self.get_knife(context, sec_info)
                        # return
                        if knife is None:
                            ag_utils.debugprint("knife is None")
                            continue
                        self.cut_plane(context, sec_info, knife, knife_bm)
                        knife_bm.free()
                        break

                    if has_coplane:
                        break

                sec_bm_1.free()
                sec_bm_2.free()

        self.failed_lst = [sec.name for sec in sectors if sec not in success]

    # 获取刀具
    def get_knife(self, context: Context, sec_info) -> tuple[Object, bmesh.types.BMesh]:
        """获取刀具"""
        sec_1 = sec_info[0]["sec"]  # type: Object
        flat_face_1 = sec_info[0]["bm_face"]  # type: list[bmesh.types.BMFace]
        sec_2 = sec_info[1]["sec"]  # type: Object
        flat_face_2 = sec_info[1]["bm_face"]  # type: list[bmesh.types.BMFace]

        matrix_1 = sec_1.matrix_world
        matrix_2 = sec_2.matrix_world

        proj_normal = matrix_1.to_quaternion() @ flat_face_1[0].normal

        #
        knife_bm = bmesh.new()
        mark_layer = knife_bm.faces.layers.int.new("mark")
        verts_map = {}
        for f in flat_face_1:
            for v in f.verts:
                if v.index not in verts_map:
                    verts_map[v.index] = knife_bm.verts.new(matrix_1 @ v.co)
            new_f = knife_bm.faces.new([verts_map[v.index] for v in f.verts])
            new_f[mark_layer] = 1
        # 往投影法向挤出10厘米
        result = bmesh.ops.extrude_face_region(knife_bm, geom=knife_bm.faces)  # type: ignore
        matrix = Matrix.Translation(proj_normal * 0.1)
        bmesh.ops.transform(
            knife_bm,
            matrix=matrix,
            verts=[g for g in result["geom"] if isinstance(g, bmesh.types.BMVert)],
        )
        #
        verts_map = {}
        knife_faces = []  # type: list[bmesh.types.BMFace]
        for f in flat_face_2:
            for v in f.verts:
                if v.index not in verts_map:
                    verts_map[v.index] = knife_bm.verts.new(matrix_2 @ v.co)
            new_f = knife_bm.faces.new([verts_map[v.index] for v in f.verts])
            knife_faces.append(new_f)
        # 往投影法向移动5厘米, 再往反方向挤出10厘米
        matrix = Matrix.Translation(proj_normal * 0.05)
        bmesh.ops.transform(knife_bm, matrix=matrix, verts=[v for f in knife_faces for v in f.verts])  # type: ignore
        result = bmesh.ops.extrude_face_region(knife_bm, geom=knife_faces)  # type: ignore
        matrix = Matrix.Translation(-proj_normal * 0.1)
        bmesh.ops.transform(
            knife_bm,
            matrix=matrix,
            verts=[g for g in result["geom"] if isinstance(g, bmesh.types.BMVert)],
        )
        #
        knife_mesh = bpy.data.meshes.new("AG.knife")
        knife_bm.to_mesh(knife_mesh)
        knife_bm.free()
        #
        knife = bpy.data.objects.new(
            "AG.knife", knife_mesh
        )  # type: Object #type: ignore
        data.link2coll(knife, context.scene.collection)
        #
        ag_utils.select_active(context, knife)  # 单选并设为活动
        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
        bpy.ops.mesh.select_mode(type="FACE")  # 切换面模式

        bm_edit = bmesh.from_edit_mesh(knife_mesh)
        # bm_edit.faces.ensure_lookup_table()
        mark_layer = bm_edit.faces.layers.int.get("mark")

        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.normals_make_consistent(inside=False)  # 重新计算法向（外侧）
        # 开始布尔交集
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        for face in bm_edit.faces:
            if face[mark_layer] == 1:  # type: ignore
                face.select_set(True)
        bm_edit.select_flush_mode()  # 刷新选择
        # return None, None  # type: ignore
        with contextlib.redirect_stdout(StringIO()):
            bpy.ops.mesh.intersect_boolean(
                operation="INTERSECT", solver="EXACT"
            )  # 布尔交集，准确模式
        # 如果没有交集
        if len(bm_edit.faces) == 0:
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
            bpy.data.meshes.remove(knife_mesh)  # 删除网格
            return None, None  # type: ignore

        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.normals_make_consistent(inside=True)  # 重新计算法向（内侧）
        # 选择与投影法向相同的面
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        for f in bm_edit.faces:
            dot = f.normal.dot(proj_normal)
            # ag_utils.debugprint(f"dot: {dot}")
            if dot > 0.999:
                f.select_set(True)
                break
        bm_edit.select_flush_mode()  # 刷新选择
        bpy.ops.mesh.faces_select_linked_flat(sharpness=0.002)  # 选中相连的平展面

        bpy.ops.mesh.select_all(action="INVERT")  # 反选
        bpy.ops.mesh.delete(type="FACE")  # 删除面

        # 简并融并，两次
        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        with contextlib.redirect_stdout(StringIO()):
            bpy.ops.mesh.dissolve_degenerate()
            bpy.ops.mesh.dissolve_degenerate()
        # 再次判断是否有刀具
        if len(bm_edit.faces) == 0:
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
            bpy.data.meshes.remove(knife_mesh)  # 删除网格
            # ag_utils.debugprint("no knife")
            return None, None  # type: ignore
        bmesh.ops.dissolve_faces(
            bm_edit, faces=list(bm_edit.faces), use_verts=False
        )  # 融并面
        ag_utils.unsubdivide(bm_edit)  # 反细分边
        bmesh.update_edit_mesh(knife_mesh)

        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

        knife_bm = bmesh.new()
        knife_bm.from_mesh(knife_mesh)
        # 放大，再往投影法向移动1米
        matrix = Matrix.Translation(proj_normal)
        # matrix = Matrix.Scale(1.0001, 4)
        # matrix.translation = proj_normal
        bmesh.ops.transform(
            knife_bm, matrix=matrix, verts=knife_bm.verts  # type: ignore
        )

        return knife, knife_bm

    def cut_plane(
        self,
        context: Context,
        sec_info,
        knife: Object,
        knife_bm: bmesh.types.BMesh,
    ):
        success = self.success
        #
        knife_mesh = knife.data  # type: bpy.types.Mesh # type: ignore
        #
        knife_verts_set = {v.co.to_tuple(3) for v in knife_mesh.vertices}
        bvh = bvhtree.BVHTree.FromBMesh(knife_bm)
        for index in range(2):
            sec = sec_info[index]["sec"]  # type: Object
            sec_bm = sec_info[index]["bm"]  # type: bmesh.types.BMesh
            flat_face = sec_info[index]["bm_face"]  # type: list[bmesh.types.BMFace]
            # tex_id_layer = sec_bm.faces.layers.int.get("amagate_tex_id")
            conn_layer = sec_bm.faces.layers.int.get("amagate_connected")
            sec_data = sec.amagate_data.get_sector_data()
            matrix = sec.matrix_world
            matrix_inv = matrix.inverted()  # type: Matrix
            matrix_quat = matrix.to_quaternion()
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            if index == 0:
                proj_normal = matrix_quat @ flat_face[0].normal
            #
            hit_bm = bmesh.new()
            hit_faces = []
            verts_map = {}
            for f in flat_face:
                # 定义射线起点、方向和距离
                ray_origin = matrix @ f.calc_center_median()
                ray_direction = proj_normal
                # 执行射线检测
                hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                    bvh, ray_origin, ray_direction
                )
                if hit_index is None:  # type: ignore
                    continue

                hit_faces.append(f)
                for v in f.verts:
                    if v.index not in verts_map:
                        verts_map[v.index] = hit_bm.verts.new(matrix @ v.co)
                hit_bm.faces.new([verts_map[v.index] for v in f.verts])
            #
            hit_bm = ag_utils.ensure_lookup_table(hit_bm)
            face_num = len(hit_faces)
            if face_num != 0:
                if face_num != 1:
                    bmesh.ops.dissolve_faces(
                        hit_bm, faces=hit_bm.faces, use_verts=False  # type: ignore
                    )  # 融并面
                ag_utils.unsubdivide(hit_bm)  # 反细分边
                # 如果找到与刀具匹配的面，无需切割
                verts_set = {v.co.to_tuple(3) for v in hit_bm.verts}
                if verts_set == knife_verts_set:
                    # ag_utils.debugprint("found match")
                    if face_num != 1:
                        result = bmesh.ops.dissolve_faces(
                            sec_bm, faces=hit_faces, use_verts=False
                        )  # 融并面 # type: ignore
                        conn_face = result["region"][0]
                    else:
                        conn_face = hit_faces[0]
                    sec_data_2 = sec_info[1 - index][
                        "sec"
                    ].amagate_data.get_sector_data()
                    conn_face[conn_layer] = sec_data_2.id  # type: ignore
                    success.add(sec)
                    sec_data.connect_num += 1
                    # 有限融并普通面
                    faces = self.get_linked_flat(conn_face)
                    # 重置标记
                    for f in faces:
                        for e in f.edges:
                            e.seam = False
                    for f in faces:
                        if f[conn_layer] != 0:  # type: ignore
                            for e in f.edges:
                                e.seam = True
                    faces = [f for f in faces if f[conn_layer] == 0]  # type: ignore
                    edges = {e for f in faces for e in f.edges}
                    bmesh.ops.dissolve_limit(
                        sec_bm,
                        angle_limit=0.002,
                        edges=list(edges),
                        delimit={"SEAM", "MATERIAL"},
                    )  # NORMAL
                    sec_bm.to_mesh(mesh)
                    #
                    hit_bm.free()
                    continue
            hit_bm.free()
            # 没有找到与刀具匹配的面，切割
            cut_layer = sec_bm.edges.layers.int.new("amagate_cut")
            # 获取边界
            boundary = []
            visited = set()
            for f in flat_face:
                for e in f.edges:
                    if e.index in visited:
                        continue
                    visited.add(e.index)
                    for f2 in e.link_faces:
                        if f2 in flat_face:
                            continue
                        if abs(f2.normal.dot(f.normal)) > epsilon2:
                            continue
                        # 找到边界边
                        co1 = e.verts[0].co
                        co2 = e.verts[1].co
                        # key = (co2 - co1).normalized().to_tuple(5)
                        # if key not in boundary:
                        boundary.append(((co2 - co1).normalized(), co1))
            #
            # ag_utils.debugprint(f"boundary: {boundary}")
            normal = matrix_inv.to_quaternion() @ knife_mesh.polygons[0].normal
            verts_idx = knife_mesh.polygons[0].vertices
            v_num = len(verts_idx)
            geom = {e for f in flat_face for e in f.edges} | {
                v for f in flat_face for v in f.verts
            }
            geom = list(geom) + flat_face
            for i in range(v_num):
                is_boundary = False
                j = (i + 1) % v_num
                co1 = matrix_inv @ knife_mesh.vertices[verts_idx[i]].co
                co2 = matrix_inv @ knife_mesh.vertices[verts_idx[j]].co
                dir2 = (co2 - co1).normalized()
                for dir1, co in boundary:
                    if abs(dir2.dot(dir1)) > epsilon2:
                        if (co1 - co).length < epsilon:
                            is_boundary = True
                            break
                        if abs((co1 - co).normalized().dot(dir1)) > epsilon2:
                            is_boundary = True
                            break
                if is_boundary:
                    # ag_utils.debugprint("is_boundary")
                    continue
                #
                cross = dir2.cross(normal)  # type: Vector
                plane_no = cross.normalized()
                #
                result = bmesh.ops.bisect_plane(
                    sec_bm,
                    geom=geom,  # type: ignore
                    dist=1e-4,
                    plane_no=plane_no,
                    plane_co=co1,
                    clear_inner=False,
                    clear_outer=False,
                )
                # ag_utils.debugprint(f"{sec.name}: plane_no: {plane_no}, plane_co: {co1}")
                sec_bm.faces.ensure_lookup_table()
                # 获取内部面
                med_point = (co1 + co2) / 2.0
                min_len = np.inf
                for g in result["geom_cut"]:
                    if isinstance(g, bmesh.types.BMEdge):
                        g[cut_layer] = 1  # type: ignore
                        med_point2 = (g.verts[0].co + g.verts[1].co) / 2.0
                        length = (med_point - med_point2).length
                        if length < min_len:
                            min_len = length
                            edge = g
                #
                cut_verts = [
                    g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMVert)
                ]
                face1, face2 = edge.link_faces
                co = next(v.co for v in face1.verts if v not in cut_verts)
                dir = (co - edge.verts[0].co).normalized()
                if plane_no.dot(dir) < 0:
                    inner_face = face1
                else:
                    inner_face = face2
                inner_faces = self.get_linked_flat(inner_face, cut_layer, conn_layer)
                # ag_utils.debugprint(f"inner_faces_idx: {inner_faces_idx}")
                geom = (
                    list(
                        {e for f in inner_faces for e in f.edges}
                        | {v for f in inner_faces for v in f.verts}
                    )
                    + inner_faces
                )
                # ag_utils.debugprint(f"inner_faces: {[f.index for f in inner_faces]}")
            #
            sec_bm.edges.layers.int.remove(cut_layer)
            # sec_bm.to_mesh(mesh)
            # return
            if len(inner_faces) != 1:
                result = bmesh.ops.dissolve_faces(
                    sec_bm, faces=inner_faces, use_verts=False
                )  # 融并面 # type: ignore
                conn_face = result["region"][0]
                # ag_utils.debugprint("dissolve_faces")
            else:
                conn_face = inner_faces[0]
            # ag_utils.debugprint(f"conn_face_idx: {conn_face.index}")
            sec_data_2 = sec_info[1 - index]["sec"].amagate_data.get_sector_data()
            conn_face[conn_layer] = sec_data_2.id  # type: ignore
            success.add(sec)
            sec_data.connect_num += 1
            # 有限融并普通面
            faces = self.get_linked_flat(conn_face)
            # 重置标记
            for f in faces:
                for e in f.edges:
                    e.seam = False
            for f in faces:
                if f[conn_layer] != 0:  # type: ignore
                    for e in f.edges:
                        e.seam = True
            faces = [f for f in faces if f[conn_layer] == 0]  # type: ignore
            edges = {e for f in faces for e in f.edges}
            bmesh.ops.dissolve_limit(
                sec_bm,
                angle_limit=0.002,
                edges=list(edges),
                delimit={"SEAM", "MATERIAL"},
            )  # NORMAL
            ag_utils.unsubdivide(sec_bm)  # 反细分边
            sec_bm.to_mesh(mesh)
        #
        bpy.data.meshes.remove(knife_mesh)  # 删除网格

    def get_linked_flat(self, face, cut_layer=None, conn_layer=None):
        # type: (bmesh.types.BMFace, Any,Any) -> list[bmesh.types.BMFace]
        visited = []
        stack = [face]  # type: list[bmesh.types.BMFace]
        normal = face.normal.copy()

        while stack:
            f = stack.pop()
            if f not in visited:
                visited.append(f)

                for e in f.edges:
                    if cut_layer is not None and e[cut_layer] == 1:  # type: ignore
                        continue
                    for f2 in e.link_faces:
                        if conn_layer is not None and f2[conn_layer] != 0:  # type: ignore
                            continue
                        if f2 not in visited:  # 避免重复访问
                            if (
                                f2.normal.dot(normal) > epsilon2
                            ):  # 使用阈值来判断法线是否相同
                                stack.append(f2)
        return visited


class OT_Sector_Connect_More(bpy.types.Operator):
    bl_idname = "amagate.sector_connect_more"
    bl_label = "More Connect"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        op = col.operator(OT_Sector_Connect_VM.bl_idname)
        op.is_button = True  # type: ignore

    def execute(self, context: Context):
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        return context.window_manager.invoke_popup(self, width=130)  # type: ignore


# 连接扇区 (顶点匹配)
class OT_Sector_Connect_VM(bpy.types.Operator):
    bl_idname = "amagate.sector_connect_vm"
    bl_label = "Vertex Matching"
    bl_description = "Connect selected sectors using vertex matching"
    # bl_options = {"UNDO"}

    undo: BoolProperty(default=True)  # type: ignore
    is_button: BoolProperty(default=False)  # type: ignore
    from_separate: BoolProperty(default=False)  # type: ignore

    def execute(self, context: Context):
        global SECTORS_LIST

        if self.from_separate:
            for sectors in SECTORS_LIST:
                self.connect(context, sectors)
            SECTORS_LIST = []  # 清空
        else:
            # 如果是从F3执行，获取当前选中的扇区
            if not self.is_button:
                L3D_data.SELECTED_SECTORS, L3D_data.ACTIVE_SECTOR = (
                    ag_utils.get_selected_sectors()
                )
            self.is_button = False  # 重置，因为从F3执行时会使用缓存值

            selected_sectors = L3D_data.SELECTED_SECTORS.copy()

            # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
            if "EDIT" in context.mode:
                bpy.ops.object.mode_set(mode="OBJECT")
                L3D_data.geometry_modify_post(selected_sectors)
                L3D_data.update_scene_edit_mode()

            # 排除拓扑类型是二维球面的扇区
            for i in range(len(selected_sectors) - 1, -1, -1):
                sec = selected_sectors[i]
                sec_data = sec.amagate_data.get_sector_data()
                if sec_data.is_2d_sphere:
                    selected_sectors.remove(sec)

            if len(selected_sectors) < 2:
                self.report(
                    {"WARNING"},
                    "Select at least two non-2d-sphere sectors, and the vertex matching portion should be a hole (without faces)",
                )
                return {"CANCELLED"}

            # 如果没有活跃对象或者活跃对象未选中
            if context.active_object not in selected_sectors:
                context.view_layer.objects.active = selected_sectors[0]

            self.failed_lst = []  # type: list[str] # 失败列表

            # 确保网格数据为单用户的
            for sec in selected_sectors:
                sec_data = sec.amagate_data.get_sector_data()
                sec_data.mesh_unique()
            self.connect(context, selected_sectors)

            # 如果有连接失败的扇区，提示
            if self.failed_lst:
                if len(self.failed_lst) == len(selected_sectors):
                    self.report({"WARNING"}, "All sectors are unconnectable")
                else:
                    self.report(
                        {"WARNING"},
                        f"{pgettext('Unconnectable sectors')}: {self.failed_lst}",
                    )
            else:
                self.report({"INFO"}, "Sectors connected successfully")

        if self.undo:
            bpy.ops.ed.undo_push(message="Connect Sectors (Vertex Matching)")

        return {"FINISHED"}

    def connect(self, context: Context, sectors: list[Object]):
        """顶点匹配连接"""
        success = set()

        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
        bpy.ops.mesh.select_mode(type="EDGE")  # 边模式
        verts_map = {}
        for i, sec_1 in enumerate(sectors):
            sec_data_1 = sec_1.amagate_data.get_sector_data()
            matrix_1 = sec_1.matrix_world
            mesh_1 = sec_1.data  # type: bpy.types.Mesh # type: ignore
            bm_edit_1 = bmesh.from_edit_mesh(mesh_1)
            bm_edit_1.verts.ensure_lookup_table()

            for j, sec_2 in enumerate(sectors):
                if j > i:
                    sec_data_2 = sec_2.amagate_data.get_sector_data()
                    matrix_2 = sec_2.matrix_world
                    mesh_2 = sec_2.data  # type: bpy.types.Mesh # type: ignore
                    bm_edit_2 = bmesh.from_edit_mesh(mesh_2)
                    bm_edit_2.verts.ensure_lookup_table()

                    verts_dict_1 = verts_map.setdefault(
                        i,
                        {
                            (matrix_1 @ v.co).to_tuple(3): v.index
                            for v in bm_edit_1.verts
                        },
                    )
                    verts_dict_2 = verts_map.setdefault(
                        j,
                        {
                            (matrix_2 @ v.co).to_tuple(3): v.index
                            for v in bm_edit_2.verts
                        },
                    )
                    intersection = set(verts_dict_1.keys()).intersection(
                        set(verts_dict_2.keys())
                    )

                    # 如果有对应顶点
                    if intersection:
                        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                        verts_idx_1 = set(verts_dict_1[k] for k in intersection)
                        verts_idx_2 = set(verts_dict_2[k] for k in intersection)
                        for e in bm_edit_1.edges:
                            if len(e.link_faces) > 1:
                                continue
                            if {v.index for v in e.verts}.issubset(verts_idx_1):
                                e.select_set(True)
                        for e in bm_edit_2.edges:
                            if len(e.link_faces) > 1:
                                continue
                            if {v.index for v in e.verts}.issubset(verts_idx_2):
                                e.select_set(True)
                        bm_edit_1.select_flush_mode()
                        bm_edit_2.select_flush_mode()
                        # bmesh.update_edit_mesh(
                        #     mesh_1, loop_triangles=False, destructive=False
                        # )  # 更新网格
                        # bmesh.update_edit_mesh(
                        #     mesh_2, loop_triangles=False, destructive=False
                        # )  # 更新网格
                        bpy.ops.mesh.edge_face_add()  # 从顶点创建边/面

                        # 设置属性
                        face = next((f for f in bm_edit_1.faces if f.select), None)
                        if face is not None:
                            layer = bm_edit_1.faces.layers.int.get("amagate_connected")
                            face[layer] = sec_data_2.id  # type: ignore
                            success.add(sec_1)
                            sec_data_1.connect_num += 1

                        face = next((f for f in bm_edit_2.faces if f.select), None)
                        if face is not None:
                            layer = bm_edit_2.faces.layers.int.get("amagate_connected")
                            face[layer] = sec_data_1.id  # type: ignore
                            success.add(sec_2)
                            sec_data_2.connect_num += 1

        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        # # 重新计算法向（内侧）
        bpy.ops.mesh.normals_make_consistent(inside=True)
        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
        L3D_data.geometry_modify_post(sectors, undo=False, check_connect=False)

        self.failed_lst = [sec.name for sec in sectors if sec not in success]


# 断开连接
class OT_Sector_Disconnect(bpy.types.Operator):
    bl_idname = "amagate.sector_disconnect"
    bl_label = "Disconnect"
    bl_description = "Disconnect selected sectors"

    undo: BoolProperty(default=True)  # type: ignore
    is_button: BoolProperty(default=False)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        # 如果是从F3执行，获取当前选中的扇区
        if not self.is_button:
            L3D_data.SELECTED_SECTORS, L3D_data.ACTIVE_SECTOR = (
                ag_utils.get_selected_sectors()
            )
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        selected_sectors = L3D_data.SELECTED_SECTORS.copy()
        if len(selected_sectors) == 0:
            self.report({"WARNING"}, "Select at least one sector")
            return {"CANCELLED"}

        # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
        if "EDIT" in context.mode:
            edit_mode = True
            bpy.ops.object.mode_set(mode="OBJECT")
            L3D_data.geometry_modify_post(selected_sectors)
            L3D_data.update_scene_edit_mode()
        else:
            edit_mode = False

        Connectionless = []
        # # 排除无连接扇区
        # for i in range(len(selected_sectors) - 1, -1, -1):
        #     sec = selected_sectors[i]
        #     sec_data = sec.amagate_data.get_sector_data()
        #     if sec_data.connect_num == 0:
        #         selected_sectors.remove(sec)
        #         Connectionless.append(sec.name)

        # if len(selected_sectors) == 0:
        #     # 扇区没有连接
        #     self.report({"WARNING"}, "No connection found")
        #     return {"CANCELLED"}

        ag_utils.disconnect(self, context, selected_sectors, edit_mode=edit_mode)

        if Connectionless:
            self.report(
                {"INFO"}, f"{pgettext('No connection found')}: {Connectionless}"
            )
        else:
            self.report({"INFO"}, pgettext("Disconnect", "Operator"))

        if self.undo:
            bpy.ops.ed.undo_push(message="Disconnect")

        return {"FINISHED"}


# 分离凸多面体
class OT_Sector_SeparateConvex(bpy.types.Operator):
    bl_idname = "amagate.sector_separate_convex"
    bl_label = "Separate Convex"
    bl_description = "Separate selected sectors into convex parts"
    # bl_options = {"UNDO"}

    undo: BoolProperty(default=True)  # type: ignore
    is_button: BoolProperty(default=False)  # type: ignore
    # 自动连接，仅用于内部传参，如果为-1，则使用UI开关值
    # auto_connect: IntProperty(default=-1)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    # def separate_simple(self, context: Context, sec: Object):
    #     """分割（简单）"""
    #     sec_data = sec.amagate_data.get_sector_data()

    def pre_separate(self, context: Context, sec: Object):
        """预分割"""
        sec_data = sec.amagate_data.get_sector_data()
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        matrix_world = sec.matrix_world

        separate = ()  # 分割数据
        is_complex = False
        # 内部面索引
        faces_int_idx = set(sec_data["ConcaveData"]["faces_int_idx"])

        sec_bm = bmesh.new()
        sec_bm.from_mesh(mesh)
        sec_bm.verts.ensure_lookup_table()
        sec_bm.faces.ensure_lookup_table()

        # XXX 弃用 # 对内部面进行拆分凹面（平面）
        """
        bpy.ops.object.select_all(action="DESELECT")  # 取消选择
        context.view_layer.objects.active = sec  # 设置活动物体
        bpy.ops.object.mode_set(mode="EDIT")  # 进入编辑模式
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        bm_edit = bmesh.from_edit_mesh(mesh)
        bm_edit.faces.ensure_lookup_table()
        for i in faces_int_idx:
            bm_edit.faces[i].select_set(True)  # 选择面
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        face_num = len(bm_edit.faces)
        bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
        if len(bm_edit.faces) != face_num:
            # 更新内部面索引
            faces_int_idx = set(f.index for f in bm_edit.faces if f.select)
            print(f"faces_int_idx: {faces_int_idx}")
            # 更新sec_bm数据
            sec_bm.free()
            sec_bm = bm_edit.copy()
            sec_bm.verts.ensure_lookup_table()
            sec_bm.faces.ensure_lookup_table()
        bpy.ops.object.mode_set(mode="OBJECT")
        """

        # 外部面索引
        # faces_ext_idx = set(range(len(sec_bm.faces))) - faces_int_idx

        # 获取内部面法向
        internal_v = [sec_bm.faces[i].normal for i in faces_int_idx]
        # 获取外部平面法向
        external_v = list(sec_data["ConcaveData"]["flat_ext"])
        # 获取投影法线
        proj_normal = ag_utils.get_project_normal(internal_v, external_v)

        # 如果不存在有效的投影法线，则为复杂凹面
        if proj_normal is None:
            ag_utils.debugprint("not in same hemisphere")
            sec_bm.free()
            sec_data["ConcaveData"]["concave_type"] = ag_utils.CONCAVE_T_COMPLEX
            is_complex = True
            return {"is_complex": is_complex, "separate": separate}

        proj_normal = Vector(proj_normal)
        # 投影法线应用物体变换
        proj_normal_prime = (matrix_world.to_quaternion() @ proj_normal).normalized()
        # proj_normal_prime = Vector(proj_normal_prime.to_tuple(4))
        # ag_utils.debugprint(f"proj_normal_prime: {proj_normal_prime}")

        # 与内部面共边的外部面
        faces_exterior_idx = []  # type: list[int]
        knife_edges = set(e for i in faces_int_idx for e in sec_bm.faces[i].edges)
        faces_exterior = set(f for f in sec_bm.faces if f.index not in faces_int_idx)
        for f in faces_exterior:
            for e in f.edges:
                if e in knife_edges:
                    faces_exterior_idx.append(f.index)
                    break

        # 内部面 (排除垂直面)
        faces_int_idx_prime = faces_int_idx.copy()
        # 创建刀具BMesh
        knife_bm = bmesh.new()
        exist_verts = {}
        distance = 0
        for face_idx in faces_int_idx:
            f = sec_bm.faces[face_idx]  # type: bmesh.types.BMFace
            # 跳过垂直面
            if abs(f.normal.dot(proj_normal)) < epsilon:
                faces_int_idx_prime.remove(face_idx)
                continue
            verts = []
            # 重复顶点
            is_dup_vert = False
            for i in f.verts:
                # co = Vector((matrix_world @ i.co).to_tuple(4))
                co = matrix_world @ i.co
                dist = (co).dot(proj_normal_prime)
                # 往投影方向延伸10米
                if distance == 0:
                    distance = dist + 10
                co += proj_normal_prime * (distance - dist)
                # print(f"co: {co}")
                key = co.to_tuple(3)
                v = exist_verts.get(key)
                if not v:
                    v = knife_bm.verts.new(co)
                    exist_verts[key] = v
                if v in verts:
                    is_dup_vert = True
                    break
                verts.append(v)
            # 跳过重复顶点的面
            if is_dup_vert:
                faces_int_idx_prime.remove(face_idx)
                continue
            knife_bm.faces.new(verts)

        # 刀具BMesh转Mesh
        knife_mesh = bpy.data.meshes.new(f"AG.{sec.name}_knife")
        knife_bm.to_mesh(knife_mesh)
        knife_obj = bpy.data.objects.new(f"AG.{sec.name}_knife", knife_mesh)
        data.link2coll(knife_obj, context.scene.collection)
        bpy.ops.object.select_all(action="DESELECT")  # 取消选择
        context.view_layer.objects.active = knife_obj  # 设置活动物体
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        # 弃用 #交集判断
        """
        bm_edit = bmesh.from_edit_mesh(knife_obj.data)  # type: ignore
        face_num = len(bm_edit.faces)
        with contextlib.redirect_stdout(StringIO()):
            # 交集(切割)
            bpy.ops.mesh.intersect(mode="SELECT")
        # 如果存在交集
        if len(bm_edit.faces) != face_num:
            ag_utils.debugprint(f"{knife_obj.name} has intersect")
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.data.meshes.remove(knife_mesh)
            is_complex = True
        # 不存在交集
        """
        # bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.edge_split(type="EDGE")  # 按边拆分
        bpy.ops.mesh.separate(type="LOOSE")  # 分离松散块
        bpy.ops.object.mode_set(mode="OBJECT")
        context.active_object.select_set(True)  # 刀具本体也需选择

        # 添加到投影切割列表
        knife_project = context.selected_objects
        separate = [
            sec,
            faces_int_idx,  # 内部面
            faces_int_idx_prime,  # 内部面 (排除垂直面)
            faces_exterior_idx,  # 与内部面共边的外部面
            knife_project,  # 投影切割刀具
            knife_bm,  # 投影切割刀具BMesh
            proj_normal_prime,  # 投影法向
        ]

        sec_bm.free()

        return {"is_complex": is_complex, "separate": separate}

    def execute(self, context: Context):
        global SEPARATE_DATA, REGION_DATA
        # 如果是从F3执行，获取当前选中的扇区
        if not self.is_button:
            L3D_data.SELECTED_SECTORS, L3D_data.ACTIVE_SECTOR = (
                ag_utils.get_selected_sectors()
            )
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        selected_sectors = L3D_data.SELECTED_SECTORS.copy()
        if len(selected_sectors) == 0:
            self.report({"WARNING"}, "Select at least one sector")
            return {"CANCELLED"}

        # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
        if "EDIT" in context.mode:
            bpy.ops.object.mode_set(mode="OBJECT")
            L3D_data.geometry_modify_post(selected_sectors)
            L3D_data.update_scene_edit_mode()

        # knife_project = []
        separate_list = []
        complex_list = []
        non_2d_sphere_list = []
        # has_separate_simple = False

        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            # 跳过非二维球面
            if not sec_data.is_2d_sphere:
                non_2d_sphere_list.append(sec)
                continue
            # 跳过凸多面体
            if sec_data.is_convex:
                continue

            concave_type = sec_data["ConcaveData"]["concave_type"]
            # 跳过复杂凹多面体
            if concave_type == ag_utils.CONCAVE_T_COMPLEX:
                complex_list.append(sec)
                continue

            # 断开凹扇区的连接
            if sec_data.connect_num > 0:
                ag_utils.disconnect(None, context, [sec])
            sec_data.is_convex = ag_utils.is_convex(sec)

            # 简单凹面的情况
            # if concave_type == ag_utils.CONCAVE_T_SIMPLE:
            #     self.separate_simple(context, sec)
            #     has_separate_simple = True
            # else:

            # 预分割判断是复杂还是普通凹面
            ret = self.pre_separate(context, sec)
            if ret["is_complex"]:
                complex_list.append(sec)
            else:
                separate_list.append(ret["separate"])
        #
        if complex_list:
            self.report(
                {"WARNING"},
                f'{pgettext("Cannot separate complex polyhedron")}: {", ".join(s.name for s in complex_list)}',
            )
        area = context.area
        region = next(r for r in area.regions if r.type == "WINDOW")
        # 如果切割列表不为空
        if separate_list:
            SEPARATE_DATA = {
                "index": 0,
                "separate_list": separate_list,
                "undo": self.undo,
            }
            REGION_DATA = {
                "area": area,
                "region": region,
                "view_rotation": region.data.view_rotation.copy(),
                "view_perspective": region.data.view_perspective,
                "shading_type": area.spaces[0].shading.type,  # type: ignore
            }
            area.spaces[0].shading.type = "WIREFRAME"  # type: ignore
            pre_knife_project()
            return {"FINISHED"}

        #
        ret = {"FINISHED"}
        # 没有切割凹面，且不存在复杂凹面
        if not complex_list:
            self.report({"INFO"}, "No need to separate")
        if self.undo:
            bpy.ops.ed.undo_push(message="Separate Convex")
        return ret


# 导出虚拟扇区
class OT_GhostSectorExport(bpy.types.Operator):
    bl_idname = "amagate.ghost_sector_export"
    bl_label = "Export Ghost Sector"
    bl_description = ""
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        # 检查是否为无标题文件
        if not bpy.data.filepath:
            self.report({"WARNING"}, "Please save the file first")
            return {"CANCELLED"}

        coll = L3D_data.ensure_collection(L3D_data.GS_COLL)
        gho_sectors = [
            obj
            for obj in coll.all_objects
            if obj.amagate_data.is_gho_sector
            and len(obj.data.polygons) == 1  # type: ignore
            and abs((obj.matrix_world.to_quaternion() @ obj.data.polygons[0].normal).dot(Vector((0, 0, 1)))) > epsilon2  # type: ignore
        ]
        if not gho_sectors:
            self.report(
                {"INFO"},
                "No export, ensure that the mesh of the Ghost sector has only one face with its normal parallel to the Z-axis",
            )
            return {"CANCELLED"}

        sf_file = os.path.join(os.path.dirname(bpy.data.filepath), "AG_GhostSector.sf")
        z_axis = Vector((0, 0, 1))
        buff = StringIO()
        count = 0
        for gsec in gho_sectors:
            depsgraph = context.evaluated_depsgraph_get()
            evaluated_obj = gsec.evaluated_get(depsgraph)
            mesh = evaluated_obj.data  # type: bpy.types.Mesh # type: ignore
            bm = bmesh.new()
            bm.from_mesh(mesh)
            #
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # type: ignore
            roof = next((f for f in bm.faces if f.normal.dot(z_axis) > epsilon2), None)
            floor = next(
                (f for f in bm.faces if f.normal.dot(-z_axis) > epsilon2), None
            )
            if not roof or not floor:
                bm.free()
                continue
            #
            matrix = gsec.matrix_world.copy()
            #
            buff.write("BeginGhostSector\n")
            buff.write(f"  Name => {gsec.name}\n")
            buff.write(f"  FloorHeight => {(matrix @ floor.verts[0].co).z:.2f}\n")
            buff.write(f"  RoofHeight => {(matrix @ roof.verts[0].co).z:.2f}\n")
            for v in roof.verts:
                co = (matrix @ v.co).to_tuple(2)
                buff.write(f"  Vertex => {co[0]} {-co[1]}\n")
            buff.write("  Grupo => Grupo1\n")
            buff.write("  Sonido => Sonido1\n")
            buff.write("  Volumen => 1.0\n")
            buff.write("  VolumenBase => 1.0\n")
            buff.write("  DistanciaMinima => 1000\n")
            buff.write("  DistanciaMaxima => 20000\n")
            buff.write("  DistMaximaVertical => 20000\n")
            buff.write("  Escala => 1.0\n")
            buff.write("EndGhostSector\n\n")
            #
            count += 1
            bm.free()
        #
        if count != 0:
            with open(sf_file, "w", encoding="utf-8") as f:
                f.write(f"NumGhostSectors => {count}\n\n")
                f.write(buff.getvalue())

            self.report(
                {"INFO"}, f"{pgettext('The number of Ghost sector exports')}: {count}"
            )
            return {"FINISHED"}
        else:
            self.report(
                {"INFO"},
                "No export, ensure that the mesh of the Ghost sector has only one face with its normal parallel to the Z-axis",
            )
            return {"CANCELLED"}


# 设为默认扇区
class OT_SectorSetDefault(bpy.types.Operator):
    bl_idname = "amagate.sector_set_default"
    bl_label = "Set as Default"
    bl_description = ""
    # bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore
    is_button: BoolProperty(default=False)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        # 如果是从F3执行，获取当前选中的扇区
        if not self.is_button:
            L3D_data.SELECTED_SECTORS, L3D_data.ACTIVE_SECTOR = (
                ag_utils.get_selected_sectors()
            )
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        active_sector = L3D_data.ACTIVE_SECTOR
        if not active_sector:
            self.report({"WARNING"}, "Select at least one sector")
            return {"CANCELLED"}
        #
        sec_data = active_sector.amagate_data.get_sector_data()
        scene_data = context.scene.amagate_data
        defaults = scene_data.defaults
        #
        defaults.atmo_id = sec_data.atmo_id
        defaults.external_id = sec_data.external_id
        defaults.ambient_color = sec_data.ambient_color.copy()
        defaults.flat_light.color = sec_data.flat_light.color.copy()
        for i in ("Floor", "Ceiling", "Wall"):
            tex_prop = sec_data.textures.get(i)
            def_prop = defaults.textures.get(i)
            #
            def_prop.id = tex_prop.id
            def_prop.xpos = tex_prop.xpos
            def_prop.ypos = tex_prop.ypos
            def_prop.xzoom = tex_prop.xzoom
            def_prop.yzoom = tex_prop.yzoom
            def_prop.angle = tex_prop.angle

        return {"FINISHED"}


# 扇区灯泡
class OT_Bulb_Add(bpy.types.Operator):
    bl_idname = "amagate.sector_bulb_add"
    bl_label = "Add Bulb"
    bl_description = ""
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        selected_sectors = L3D_data.SELECTED_SECTORS
        active_sector = L3D_data.ACTIVE_SECTOR
        if len(selected_sectors) != 1:
            return {"CANCELLED"}

        self.add(context, active_sector, self.undo)
        return {"FINISHED"}

    @staticmethod
    def add(context: Context, sec: Object, undo=False):
        scene_data = context.scene.amagate_data
        sec_data = sec.amagate_data.get_sector_data()
        item = sec_data.bulb_light.add()
        item.set_id()
        # 创建灯泡
        light_name = f"AG.{sec_data.id}.Light"
        light_data = bpy.data.lights.new("", "POINT")
        # light_data.energy = 2  # type: ignore
        light_data.color = (0.784, 0.784, 0.392)
        light_data.shadow_maximum_resolution = 0.03125  # type: ignore
        light_data.volume_factor = 0

        light = bpy.data.objects.new("", light_data)
        light.rename(light_name, mode="SAME_ROOT")
        light_data.rename(light.name, mode="ALWAYS")
        #
        data.link2coll(light, L3D_data.ensure_collection(L3D_data.S_COLL))
        light.parent = sec
        #
        item.light_obj = light
        item.update_strength(context)

        # 调整活动索引
        scene_data.bulb_operator.active = len(sec_data.bulb_light) - 1

        if undo:
            bpy.ops.ed.undo_push(message="Add Bulb")

        return item


class OT_Bulb_Del(bpy.types.Operator):
    bl_idname = "amagate.sector_bulb_del"
    bl_label = "Delete Bulb"
    bl_description = ""
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        selected_sectors = L3D_data.SELECTED_SECTORS
        active_sector = L3D_data.ACTIVE_SECTOR
        if len(selected_sectors) != 1:
            return {"CANCELLED"}

        scene_data = context.scene.amagate_data
        sec_data = active_sector.amagate_data.get_sector_data()
        index = scene_data.bulb_operator.active
        if index != -1 and index < len(sec_data.bulb_light):
            item = sec_data.bulb_light[index]
            light = item.light_obj
            if light:
                bpy.data.lights.remove(light.data)

            #
            light_link_manager = scene_data.light_link_manager
            key = item.name
            if key in light_link_manager:
                light_link_manager.remove(light_link_manager.find(key))

            id_manager = scene_data.bulb_operator.id_manager
            id_manager.remove(id_manager.find(key))
            #
            sec_data.bulb_light.remove(index)
            # 调整活动索引
            if index != 0 and index >= len(sec_data.bulb_light):
                scene_data.bulb_operator.active = len(sec_data.bulb_light) - 1

        if self.undo:
            bpy.ops.ed.undo_push(message="Delete Bulb")

        return {"FINISHED"}


class OT_Bulb_Set(bpy.types.Operator):
    bl_idname = "amagate.sector_bulb_set"
    bl_label = ""  # "Bulb Settings"
    bl_description = ""
    bl_options = {"INTERNAL"}

    key: StringProperty()  # type: ignore

    @classmethod
    def description(cls, context, properties):
        active_sector = L3D_data.ACTIVE_SECTOR
        sec_data = active_sector.amagate_data.get_sector_data()
        item = sec_data.bulb_light[properties.key]  # type: ignore
        light = item.light_obj  # type: Object
        if light:
            return light.name
        return ""

    def execute(self, context: Context):
        return {"FINISHED"}

    def draw(self, context: Context):
        active_sector = L3D_data.ACTIVE_SECTOR
        sec_data = active_sector.amagate_data.get_sector_data()
        item = sec_data.bulb_light[self.key]

        layout = self.layout

        col = layout.column()
        col.prop(item, "vector", text="")
        col.prop(item, "distance", text="Distance")
        col.prop(item, "precision")
        op = col.operator(OT_Bulb_Render.bl_idname, text="Render")
        op.key = self.key  # type: ignore

    def invoke(self, context, event):
        active_sector = L3D_data.ACTIVE_SECTOR
        sec_data = active_sector.amagate_data.get_sector_data()
        item = sec_data.bulb_light[self.key]
        light = item.light_obj  # type: Object

        bbox_corners = [
            active_sector.matrix_world @ Vector(corner)
            for corner in active_sector.bound_box
        ]
        center = sec_data.center = sum(bbox_corners, Vector()) / 8
        vector = center - light.matrix_world.translation
        if vector.length > epsilon:
            item["vector"] = vector.normalized()
            item.update_location(context)

        return context.window_manager.invoke_popup(self, width=110)  # type: ignore


class OT_Bulb_Render(bpy.types.Operator):
    bl_idname = "amagate.sector_bulb_render"
    bl_label = "Bulb Render"
    bl_description = ""
    bl_options = {"INTERNAL"}

    key: StringProperty()  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        active_sector = L3D_data.ACTIVE_SECTOR
        sec_data = active_sector.amagate_data.get_sector_data()
        item = sec_data.bulb_light[self.key]
        light = item.light_obj  # type: Object
        light_data = light.data  # type: bpy.types.Light # type: ignore

        if light_data.type != "SUN":
            return {"CANCELLED"}

        light_link_manager = scene_data.light_link_manager
        if len(light_link_manager) >= 60:
            light2 = light_link_manager[0].obj
            light_link_manager.remove(0)
            if light2:
                light2.light_linking.receiver_collection = None
                light2.light_linking.blocker_collection = None

        light_link = sec_data.bulb_light_link
        if not light_link:
            light_link = bpy.data.collections.new(
                f"AG.{sec_data.id}.Bulb  Light Linking"
            )
            sec_data.bulb_light_link = light_link
        shadow_link = sec_data.bulb_shadow_link
        if not shadow_link:
            shadow_link = bpy.data.collections.new(
                f"AG.{sec_data.id}.Bulb  Shadow Linking"
            )
            sec_data.bulb_shadow_link = shadow_link
        #
        for coll in (light_link, shadow_link):
            while coll.objects:
                coll.objects.unlink(coll.objects[-1])
        data.link2coll(active_sector, light_link)
        data.link2coll(active_sector, shadow_link)
        shadow_link.collection_objects[0].light_linking.link_state = "EXCLUDE"
        #
        light_pos = light.matrix_world.translation
        co_list = [active_sector.matrix_world @ v.co for v in active_sector.data.vertices]  # type: ignore
        co_list.sort(key=lambda v: (v - light_pos).length)
        origin = co_list[0]
        direction = item.vector
        sectors = {active_sector}
        depth = 0
        while sectors and depth < 3:
            sec = sectors.pop()
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            for attr in mesh.attributes["amagate_connected"].data:  # type: ignore
                conn_sid = attr.value
                # 如果没有连接，跳过
                if conn_sid == 0:
                    continue

                conn_sec = L3D_data.get_sector_by_id(scene_data, conn_sid)
                has_sky = next((1 for i in conn_sec.data.attributes["amagate_tex_id"].data if i.value == -1), 0)  # type: ignore
                # 如果是天空扇区，跳过
                if has_sky:
                    continue

                for v in conn_sec.data.vertices:  # type: ignore
                    co = conn_sec.matrix_world @ v.co
                    # 只要有1个顶点在光源的正方向，添加
                    if (co - origin).normalized().dot(direction) > epsilon:
                        sectors.add(conn_sec)
                        break

            depth += 1
        for sec in sectors:
            data.link2coll(sec, light_link)
            data.link2coll(sec, shadow_link)
        #
        light.light_linking.receiver_collection = light_link
        light.light_linking.blocker_collection = shadow_link
        light.hide_viewport = False
        #
        if item.name not in light_link_manager:
            light_link_mgr = light_link_manager.add()
            light_link_mgr.name = item.name
            light_link_mgr.obj = light

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
