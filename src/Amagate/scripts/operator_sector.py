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
                ray_origin = matrix_world @ f.calc_center_bounds()  # 位于面内部的中心点
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
            if obj.type == "MESH" and (not obj.amagate_data.is_sector)
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
            data.SELECTED_SECTORS, data.ACTIVE_SECTOR = ag_utils.get_selected_sectors()
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
        if context.mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
            data.geometry_modify_post(selected_sectors)

        selected_sectors = data.SELECTED_SECTORS.copy()
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
        success = set()
        bm_simplify = {}  # type: dict[int, bmesh.types.BMesh] # 简化后的网格

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
                sec_bm_1 = bm_simplify.get(sec_idx_1)
                if sec_bm_1 is None:
                    bm = bmesh.new()
                    bm.from_mesh(mesh_1)
                    # 融并面及反细分边，删除连接面
                    ag_utils.dissolve_unsubdivide(bm, del_connected=True)
                    sec_bm_1 = bm_simplify.setdefault(sec_idx_1, bm)

                sec_bm_2 = bm_simplify.get(sec_idx_2)
                if sec_bm_2 is None:
                    bm = bmesh.new()
                    bm.from_mesh(mesh_2)
                    # 融并面及反细分边，删除连接面
                    ag_utils.dissolve_unsubdivide(bm, del_connected=True)
                    sec_bm_2 = bm_simplify.setdefault(sec_idx_2, bm)
                #
                has_connect = False  # 是否有连接
                for face_1 in sec_bm_1.faces:
                    normal_1 = matrix_1.to_quaternion() @ face_1.normal
                    for face_2 in sec_bm_2.faces:
                        normal_2 = matrix_2.to_quaternion() @ face_2.normal

                        # 如果法向不是完全相反，跳过
                        if normal_1.dot(normal_2) > -epsilon2:
                            continue

                        # 获取面的顶点坐标
                        co1 = matrix_1 @ face_1.verts[0].co
                        co2 = matrix_2 @ face_2.verts[0].co
                        dir = (co2 - co1).normalized()
                        # 如果顶点不是在同一平面，跳过
                        if abs(dir.dot(normal_1)) > epsilon:
                            continue

                        sec_info = [
                            {
                                "sec": sec_1,
                                "bm_face": face_1,
                                "flat_info": (),
                                "is_sky": False,
                            },
                            {
                                "sec": sec_2,
                                "bm_face": face_2,
                                "flat_info": (),
                                "is_sky": False,
                            },
                        ]

                        # 获取刀具
                        knife, knife_bm = self.get_knife(context, sec_info)
                        if knife is None:
                            continue

                        # 交集(切割)
                        for i, face in enumerate((face_1, face_2)):
                            normal = face.normal.copy()
                            dist = face.verts[0].co.dot(normal)
                            sec_info[i]["flat_info"] = (dist, normal)
                        self.intersect(context, sec_info, knife)
                        # 比较连接面
                        has_connect, connect_face_idx = self.compare_face(
                            context, sec_info, knife_bm
                        )
                        if has_connect:
                            if connect_face_idx[0] != -1:
                                mesh_1.attributes["amagate_connected"].data[connect_face_idx[0]].value = sec_data_2.id  # type: ignore
                                success.add(sec_1)
                                sec_data_1.connect_num += 1
                            if connect_face_idx[1] != -1:
                                mesh_2.attributes["amagate_connected"].data[connect_face_idx[1]].value = sec_data_1.id  # type: ignore
                                success.add(sec_2)
                                sec_data_2.connect_num += 1
                        # if has_connect:
                        #     mesh_1.attributes["amagate_connected"].data[connect_face_idx[0]].value = sec_data_2.id  # type: ignore
                        #     mesh_2.attributes["amagate_connected"].data[connect_face_idx[1]].value = sec_data_1.id  # type: ignore
                        #     success.update({sec_1, sec_2})

                        #
                        knife_bm.free()

                        bmesh.ops.delete(sec_bm_1, geom=[face_1], context="FACES")
                        bmesh.ops.delete(sec_bm_2, geom=[face_2], context="FACES")

                        break

                    if has_connect:
                        break

        # 清理
        for bm in bm_simplify.values():
            bm.free()

        self.failed_lst = [sec.name for sec in sectors if sec not in success]

    # 获取刀具
    def get_knife(self, context: Context, sec_info) -> tuple[Object, bmesh.types.BMesh]:
        """获取刀具"""
        sec_1 = sec_info[0]["sec"]  # type: Object
        face_1 = sec_info[0]["bm_face"]  # type: bmesh.types.BMFace
        sec_2 = sec_info[1]["sec"]  # type: Object
        face_2 = sec_info[1]["bm_face"]  # type: bmesh.types.BMFace

        matrix_1 = sec_1.matrix_world
        matrix_2 = sec_2.matrix_world

        proj_normal = matrix_1.to_quaternion() @ face_1.normal

        knife_bm = bmesh.new()
        for v in face_1.verts:
            knife_bm.verts.new(matrix_1 @ v.co)
        knife_bm.faces.new(knife_bm.verts[: len(face_1.verts)])
        for v in face_2.verts:
            knife_bm.verts.new(matrix_2 @ v.co)
        knife_bm.faces.new(knife_bm.verts[len(face_1.verts) :])
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
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格

        bm_edit = bmesh.from_edit_mesh(knife_mesh)
        bm_edit.faces.ensure_lookup_table()

        bm_face_1, bm_face_2 = bm_edit.faces

        bm_face_1.select_set(True)
        bmesh.update_edit_mesh(
            knife_mesh, loop_triangles=False, destructive=False
        )  # 更新网格
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": proj_normal * 0.1}
        )  # 往投影法向挤出并移动10厘米

        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        bm_face_2.select_set(True)
        bmesh.update_edit_mesh(knife_mesh, loop_triangles=False, destructive=False)
        bpy.ops.transform.translate(value=proj_normal * 0.05)  # 往投影法向移动5厘米
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": -proj_normal * 0.1}
        )  # 往反方向挤出并移动10厘米

        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.normals_make_consistent(inside=False)  # 重新计算法向（外侧）

        # 开始布尔交集
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        bm_edit.faces.ensure_lookup_table()
        bm_face_1.select_set(True)
        bmesh.update_edit_mesh(knife_mesh, loop_triangles=False, destructive=False)
        bpy.ops.mesh.select_linked()  # 选择关联项

        with contextlib.redirect_stdout(StringIO()):
            bpy.ops.mesh.intersect_boolean(
                operation="INTERSECT", solver="EXACT"
            )  # 布尔交集，准确模式
        # 如果没有交集
        if len(bm_edit.verts) == 0:
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
            bpy.data.meshes.remove(knife_mesh)  # 删除网格
            return None, None  # type: ignore

        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.normals_make_consistent(inside=True)  # 重新计算法向（内侧）
        # 选择与投影法向相同的面
        bpy.ops.mesh.select_mode(type="FACE")  # 切换面模式
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        for f in bm_edit.faces:
            dot = f.normal.dot(proj_normal)
            # ag_utils.debugprint(f"dot: {dot}")
            if dot > 0.999:
                f.select_set(True)
                break
        bmesh.update_edit_mesh(knife_mesh, loop_triangles=False, destructive=False)
        bpy.ops.mesh.faces_select_linked_flat(sharpness=0.005)  # 选中相连的平展面

        bpy.ops.mesh.select_all(action="INVERT")  # 反选
        bpy.ops.mesh.delete(type="FACE")  # 删除面

        # 简并融并，两次
        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        with contextlib.redirect_stdout(StringIO()):
            bpy.ops.mesh.dissolve_degenerate()
            bpy.ops.mesh.dissolve_degenerate()
        # 融并面
        # bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
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

    # 交集(切割)
    def intersect(
        self,
        context: Context,
        sec_info,
        knife: Object,
    ):
        sec_1 = sec_info[0]["sec"]  # type: Object
        face_1 = sec_info[0]["bm_face"]  # type: bmesh.types.BMFace
        sec_2 = sec_info[1]["sec"]  # type: Object
        face_2 = sec_info[1]["bm_face"]  # type: bmesh.types.BMFace

        matrix_1 = sec_1.matrix_world
        matrix_2 = sec_2.matrix_world
        mesh_1 = sec_1.data  # type: bpy.types.Mesh # type: ignore
        mesh_2 = sec_2.data  # type: bpy.types.Mesh # type: ignore
        #
        proj_normal = matrix_1.to_quaternion() @ face_1.normal
        knife_mesh = knife.data  # type: bpy.types.Mesh # type: ignore
        knife_pool = [knife]
        #
        knife_verts_set = {v.co.to_tuple(3) for v in knife_mesh.vertices}
        verts_set_1 = {(matrix_1 @ v.co).to_tuple(3) for v in face_1.verts}
        verts_set_2 = {(matrix_2 @ v.co).to_tuple(3) for v in face_2.verts}
        #
        cut_1 = cut_2 = True
        if verts_set_1 == knife_verts_set:
            cut_1 = False
        if verts_set_2 == knife_verts_set:
            cut_2 = False
        # 如果两个都需要切割
        if cut_1 and cut_2:
            knife_copy = knife.copy()
            data.link2coll(knife_copy, context.scene.collection)
            knife_pool.append(knife_copy)
        # 如果两个都不需要切割
        if not (cut_1 or cut_2):
            bpy.data.meshes.remove(knife_mesh)  # 删除网格

        #
        def join_knife(knife_obj, sec, flat_info):
            # type: (Object, Object, tuple[float, Vector]) -> bmesh.types.BMesh
            """合并刀具"""
            matrix = sec.matrix_world
            align_dist, align_normal = flat_info
            # 确保刀具法线是相反的
            # fmt: off
            normal2 = knife_obj.data.polygons[0].normal  # type: Vector # type: ignore
            # fmt: on
            if normal2.dot(matrix.to_quaternion() @ align_normal) > 0:
                ag_utils.select_active(context, knife_obj)  # 单选并设为活动
                bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
                bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                bpy.ops.mesh.flip_normals()  # 反转法向
                bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

            ag_utils.select_active(context, sec)  # 单选并设为活动
            knife_obj.select_set(True)  # 选择刀具
            bpy.ops.object.join()  # 合并对象

            # 调整刀具面位置
            bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            bm_edit = bmesh.from_edit_mesh(mesh)
            bm_edit.faces.ensure_lookup_table()
            knife_face = bm_edit.faces[-1]
            for v in knife_face.verts:
                dist_2 = v.co.dot(align_normal)
                offset = align_dist - dist_2
                if offset != 0:
                    bmesh.ops.translate(
                        bm_edit,
                        vec=align_normal * offset,
                        verts=[v],
                    )
                # bpy.ops.transform.translate(value=align_normal * offset)  # 移动刀具面
            bmesh.update_edit_mesh(
                mesh, loop_triangles=False, destructive=False
            )  # 更新网格
            return bm_edit

        # 切割
        for index, cut in enumerate((cut_1, cut_2)):
            if not cut:
                continue

            sec = sec_info[index]["sec"]  # type: Object
            matrix = sec.matrix_world
            quat = matrix.to_quaternion()
            flat_info = sec_info[index]["flat_info"]  # type: tuple[float, Vector]
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            bm_edit = join_knife(knife_pool.pop(), sec, flat_info)

            # 如果存在天空纹理，跳过
            layer = bm_edit.faces.layers.int.get("amagate_tex_id")
            for f in bm_edit.faces:
                if f[layer] == -1:  # type: ignore
                    sec_info[index]["is_sky"] = True
                    bmesh.ops.delete(bm_edit, geom=[bm_edit.faces[-1]], context="FACES")
                    bmesh.update_edit_mesh(mesh)  # 更新网格
                    break
            if sec_info[index]["is_sky"]:
                # ag_utils.debugprint(f"sec {sec.name} is sky")
                continue

            # 挤出刀具
            direction = quat @ flat_info[1]
            knife_start_idx = len(bm_edit.faces) - 1
            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            bm_edit.faces[-1].select_set(True)  # 选择刀具面
            bmesh.update_edit_mesh(
                mesh, loop_triangles=False, destructive=False
            )  # 更新网格
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={"value": -direction * 0.1}
            )  # 往反方向挤出并移动10厘米
            bpy.ops.mesh.select_linked()  # 选择关联项
            bpy.ops.mesh.normals_make_consistent(inside=True)  # 重新计算法向（内侧）
            bm_edit.faces.ensure_lookup_table()
            knife_face = next(
                (
                    bm_edit.faces[i]
                    for i in range(knife_start_idx, len(bm_edit.faces))
                    if (quat @ bm_edit.faces[i].normal).dot(direction) > epsilon2
                ),
                None,
            )
            if knife_face is None:
                ag_utils.debugprint(f"knife face not found in {sec.name}")
                bpy.ops.mesh.delete(type="FACE")
                continue

            bpy.ops.mesh.select_all(action="INVERT")  # 反选
            # 交集(切割)，剪切模式
            bpy.ops.mesh.intersect(mode="SELECT_UNSELECT", separate_mode="CUT")

            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            bm_edit.faces.ensure_lookup_table()
            knife_face.select_set(True)  # 选择刀具面
            bmesh.update_edit_mesh(
                mesh, loop_triangles=False, destructive=False
            )  # 更新网格
            bpy.ops.mesh.select_linked()  # 选择关联项
            # 删除刀具面
            # bpy.ops.mesh.select_all(action="INVERT")  # 反选
            bpy.ops.mesh.delete(type="FACE")  # 删除面

            bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
            with contextlib.redirect_stdout(StringIO()):
                # 简并融并，两次
                bpy.ops.mesh.dissolve_degenerate()
                bpy.ops.mesh.dissolve_degenerate()
            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            bpy.ops.mesh.select_mode(type="EDGE")  # 边模式
            bpy.ops.mesh.select_non_manifold()  # 选择非流形
            bpy.ops.mesh.delete(type="EDGE")  # 删除边

            bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
            # 重新计算法向（内侧）
            bpy.ops.mesh.normals_make_consistent(inside=True)
            ag_utils.unsubdivide(bm_edit)  # 反细分边
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

    # 比较连接面
    def compare_face(self, context, sec_info, knife_bm):
        # type: (Context, list , bmesh.types.BMesh) -> tuple[bool, list[int]]
        """比较连接面"""
        sec_1 = sec_info[0]["sec"]  # type: Object
        face_1 = sec_info[0]["bm_face"]  # type: bmesh.types.BMFace
        sec_2 = sec_info[1]["sec"]  # type: Object
        face_2 = sec_info[1]["bm_face"]  # type: bmesh.types.BMFace

        matrix_1 = sec_1.matrix_world
        matrix_2 = sec_2.matrix_world

        proj_normal = matrix_1.to_quaternion() @ face_1.normal
        #
        ag_utils.select_active(context, sec_1)  # 单选并设为活动
        sec_2.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
        sec_lst = (sec_1, sec_2)

        connect_face_idx = [-1, -1]
        bm_cmp = bmesh.new()

        has_connect = False

        bvh = bvhtree.BVHTree.FromBMesh(knife_bm)
        for index in range(2):
            if sec_info[index]["is_sky"]:
                continue

            sec = sec_lst[index]
            sec_matrix = sec.matrix_world
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            bm_edit = bmesh.from_edit_mesh(mesh)
            dist = sec_info[index]["flat_info"][0]  # type: float
            normal = sec_info[index]["flat_info"][1]  # type:  Vector
            for f in bm_edit.faces:
                # 如果法线不一致，跳过
                if f.normal.dot(normal) < epsilon2:
                    continue
                # 如果不在同一平面，跳过
                if abs(f.verts[0].co.dot(normal) - dist) > epsilon:
                    continue

                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                f.select_set(True)  # 选择面
                bmesh.update_edit_mesh(
                    mesh, loop_triangles=False, destructive=False
                )  # 更新网格
                bpy.ops.mesh.faces_select_linked_flat(
                    sharpness=0.005
                )  # 选中相连的平展面
                select_num = 0
                for f in bm_edit.faces:
                    if f.select:
                        select_num += 1
                    if select_num > 1:
                        bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
                        break
                connect_faces = [f for f in bm_edit.faces if f.select]

                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                hit = False
                for f in connect_faces:
                    # 定义射线起点、方向和距离
                    ray_origin = sec_matrix @ f.calc_center_bounds()
                    ray_direction = proj_normal
                    # 执行射线检测
                    hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                        bvh, ray_origin, ray_direction
                    )
                    if hit_index is not None:
                        if not hit:
                            hit = True
                        f.select_set(True)
                if hit:
                    bmesh.update_edit_mesh(
                        mesh, loop_triangles=False, destructive=False
                    )  # 更新网格
                    bpy.ops.mesh.dissolve_faces(use_verts=True)  # 融并面
                    selected_faces = [f for f in bm_edit.faces if f.select]
                    connect_face = selected_faces[0]

                    for v in connect_face.verts:
                        bm_cmp.verts.new(sec_matrix @ v.co)
                    bm_cmp.faces.new(bm_cmp.verts[-len(connect_face.verts) :])
                    connect_face_idx[index] = connect_face.index
                else:
                    ag_utils.debugprint(f"No hit for {sec.name}")
                break

        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

        if -1 not in connect_face_idx:
            bm_cmp = ag_utils.ensure_lookup_table(bm_cmp)
            ag_utils.unsubdivide(bm_cmp)  # 反细分边

            # bm_cmp_mesh = bpy.data.meshes.new("AG.Compare")
            # bm_cmp.to_mesh(bm_cmp_mesh)
            # bm_cmp_obj = bpy.data.objects.new("AG.Compare", bm_cmp_mesh)
            # data.link2coll(bm_cmp_obj, context.scene.collection)

            bm_cmp.faces.ensure_lookup_table()
            verts_set_1 = {v.co.to_tuple(3) for v in bm_cmp.faces[0].verts}
            verts_set_2 = {v.co.to_tuple(3) for v in bm_cmp.faces[1].verts}
            # if verts_set_1.issubset(verts_set_2) or verts_set_2.issubset(verts_set_1):
            if verts_set_1 == verts_set_2:
                has_connect = True
            else:
                ag_utils.debugprint(f"No match for {sec_1.name} and {sec_2.name}")
        # 单连接的情况，只有一个项是-1
        elif connect_face_idx[0] != connect_face_idx[1]:
            has_connect = True

        bm_cmp.free()
        return has_connect, connect_face_idx


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
                data.SELECTED_SECTORS, data.ACTIVE_SECTOR = (
                    ag_utils.get_selected_sectors()
                )
            self.is_button = False  # 重置，因为从F3执行时会使用缓存值

            # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
            if context.mode == "EDIT_MESH":
                bpy.ops.object.mode_set(mode="OBJECT")
                data.geometry_modify_post(selected_sectors)

            selected_sectors = data.SELECTED_SECTORS.copy()

            # 排除拓扑类型是二维球面的扇区
            for i in range(len(selected_sectors) - 1, -1, -1):
                sec = selected_sectors[i]
                sec_data = sec.amagate_data.get_sector_data()
                if sec_data.is_2d_sphere:
                    selected_sectors.remove(sec)

            if len(selected_sectors) < 2:
                self.report({"WARNING"}, "Select at least two non-2d-sphere sectors")
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
                        bmesh.update_edit_mesh(
                            mesh_1, loop_triangles=False, destructive=False
                        )  # 更新网格
                        bmesh.update_edit_mesh(
                            mesh_2, loop_triangles=False, destructive=False
                        )  # 更新网格
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
        # 重新计算法向（内侧）
        bpy.ops.mesh.normals_make_consistent(inside=True)
        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
        data.geometry_modify_post(sectors, undo=False)

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
            data.SELECTED_SECTORS, data.ACTIVE_SECTOR = ag_utils.get_selected_sectors()
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
        if context.mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
            data.geometry_modify_post(selected_sectors)

        selected_sectors = data.SELECTED_SECTORS.copy()

        if len(selected_sectors) == 0:
            self.report({"WARNING"}, "Select at least one sector")
            return {"CANCELLED"}

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

        ag_utils.disconnect(self, context, selected_sectors)

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
            data.SELECTED_SECTORS, data.ACTIVE_SECTOR = ag_utils.get_selected_sectors()
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        selected_sectors = data.SELECTED_SECTORS
        if len(selected_sectors) == 0:
            self.report({"WARNING"}, "Select at least one sector")
            return {"CANCELLED"}

        # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
        if context.mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
            data.geometry_modify_post(selected_sectors)

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
        # if not complex_list:
        self.report({"INFO"}, "No need to separate")
        if self.undo:
            bpy.ops.ed.undo_push(message="Separate Convex")
        return ret


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
