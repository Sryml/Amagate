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

CONNECT_DATA = {}  # type: Any

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
    global SECTORS_LIST

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

    scene_data = context.scene.amagate_data
    auto_connect = SEPARATE_DATA["auto_connect"]
    # 如果是来自连接扇区的调用
    if auto_connect != -1:
        return
    else:
        auto_connect = scene_data.operator_props.sec_separate_connect

    area = REGION_DATA["area"]  # type: bpy.types.Area
    region = REGION_DATA["region"]  # type: bpy.types.Region
    region.data.view_rotation = REGION_DATA["view_rotation"]
    region.data.view_perspective = REGION_DATA["view_perspective"]
    area.spaces[0].shading.type = REGION_DATA["shading_type"]  # type: ignore

    if SEPARATE_DATA["undo"]:
        bpy.ops.ed.undo_push(message="Separate Convex")


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
        normal = face.normal
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
        normal = mesh.polygons[0].normal
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
############################ Sector Connect
############################


def connect_timer():
    """连接扇区定时器"""
    context = bpy.context
    group_info = CONNECT_DATA["connect_list"][
        CONNECT_DATA["index"]
    ]  # type: dict[str, Any]
    active_sector = CONNECT_DATA["active_sector"]  # type: Object
    active_mesh = active_sector.data  # type: bpy.types.Mesh # type: ignore
    proj_normal = group_info["proj_normal"]  # type: Vector
    matrix_world = active_sector.matrix_world

    # 切割活动扇区
    bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
    # 隐藏未选项
    bpy.ops.mesh.hide(unselected=True)
    # 只显示组面
    for f in group_info["faces"]:
        f.hide = False
    bmesh.update_edit_mesh(active_mesh, loop_triangles=False, destructive=False)

    active_bm = CONNECT_DATA["active_bm"]  # type: bmesh.types.BMesh
    # 选择刀具物体
    for connect_info in group_info["connect_info"]:
        for knife_obj in connect_info["knife_objs"]:
            knife_obj.select_set(True)

    # 覆盖上下文
    with context.temp_override(
        area=REGION_DATA["area"],
        region=REGION_DATA["region"],
    ):
        bpy.ops.mesh.knife_project(cut_through=False)  # 投影切割
        # 如果切割了新面，反选其它面并拆分凹面
        has_new_face = False
        for f in active_bm.faces:
            if f.select:
                bpy.ops.mesh.select_all(action="INVERT")  # 反选
                # 如果反选后有选择项
                for f in active_bm.faces:
                    if f.select:
                        bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
                        bpy.ops.mesh.faces_select_linked_flat(
                            sharpness=0.005
                        )  # 选中相连的平展面
                        group_faces = [f for f in active_bm.faces if f.select]
                        has_new_face = True
                        break
                break
        # 没有切割出新面或刚好被完全切割
        if not has_new_face:
            group_faces = group_info["faces"].copy()

    # 切割连接扇区
    for connect_info in group_info["connect_info"]:
        connect_faces = []  # type: list[bmesh.types.BMFace]
        # 取消选择
        for sec in context.selected_objects:
            sec.select_set(False)
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        # 隐藏未选项
        bpy.ops.mesh.hide(unselected=True)
        sec = connect_info["sector"]  # type: Object
        matrix_world2 = sec.matrix_world
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        bm_edit = bmesh.from_edit_mesh(mesh)
        bm_edit.faces.ensure_lookup_table()
        # 显示连接面
        for i in connect_info["faces_idx"]:
            bm_edit.faces[i].hide = False
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        # 选择刀具物体
        for knife_obj in connect_info["knife_objs"]:
            knife_obj.select_set(True)
        # 覆盖上下文
        with context.temp_override(
            area=REGION_DATA["area"],
            region=REGION_DATA["region"],
        ):
            bpy.ops.mesh.knife_project(cut_through=False)  # 投影切割

        bm_edit.faces.ensure_lookup_table()
        # 保存连接面
        connect_faces = [f for f in bm_edit.faces if f.select]
        # 如果切割了新面，反选其它面并拆分凹面
        if connect_faces:
            bpy.ops.mesh.select_all(action="INVERT")  # 反选
            # 如果反选后有选择项
            for f in bm_edit.faces:
                if f.select:
                    bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
                    break
        else:
            connect_faces = [bm_edit.faces[i] for i in connect_info["faces_idx"]]

        # 检查切割出来的面是否与刀具面一一对应
        knife_bm = connect_info["knife_bm"]  # type: bmesh.types.BMesh
        bvh = bvhtree.BVHTree.FromBMesh(knife_bm)
        face_dict = {
            i: {"group_faces": [], "connect_faces": []}
            for i in range(len(knife_bm.faces))
        }  # type: dict[int, dict[str, list[bmesh.types.BMFace]]]
        bm_edit.faces.ensure_lookup_table()
        for f in connect_faces:
            # 定义射线起点、方向和距离
            ray_origin = matrix_world2 @ f.calc_center_bounds()  # 位于面内部的中心点
            ray_direction = proj_normal
            # 执行射线检测
            hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                bvh, ray_origin, ray_direction
            )
            if hit_index is not None:
                face_dict[hit_index]["connect_faces"].append(f)
        # 倒序遍历，避免删除元素导致索引变化
        for index in range(len(group_faces) - 1, -1, -1):
            f = group_faces[index]  # type: bmesh.types.BMFace
            # 定义射线起点、方向和距离
            ray_origin = matrix_world @ f.calc_center_bounds()  # 位于面内部的中心点
            ray_direction = proj_normal
            # 执行射线检测
            hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                bvh, ray_origin, ray_direction
            )
            if hit_index is not None:
                face_dict[hit_index]["group_faces"].append(f)
                del group_faces[index]

        # 删除刀具物体
        for knife_obj in connect_info["knife_objs"]:
            bpy.data.meshes.remove(knife_obj.data)  # type: ignore
        # 删除刀具bm
        connect_info["knife_bm"] = None
        knife_bm.free()

        # 显示所有面
        bpy.ops.mesh.reveal(select=False)
        # 融并多余三角面
        for dict_ in face_dict.values():
            face_list = []  # type: list[bmesh.types.BMFace]
            bm_lst = (active_bm, bm_edit)
            mesh_lst = (active_mesh, mesh)
            key = ("group_faces", "connect_faces")
            for i in range(2):
                faces = dict_[key[i]]
                if len(faces) > 1:
                    bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                    for f in faces:
                        f.select_set(True)
                        bmesh.update_edit_mesh(
                            mesh_lst[i], loop_triangles=False, destructive=False
                        )
                    # 尝试融并面
                    bpy.ops.mesh.dissolve_faces()
                    selected_faces = [f for f in bm_lst[i].faces if f.select]
                    face_list.append(selected_faces[0])
                elif len(faces) == 1:
                    face_list.append(faces[0])
                else:
                    break
            else:
                # 如果面积一致，符合连接条件，记录
                area_diff = abs(face_list[0].calc_area() - face_list[1].calc_area())
                if area_diff < 0.001:
                    ag_utils.debugprint(
                        f"connect {face_list[0].index} {face_list[1].index}"
                    )
    ##########
    CONNECT_DATA["index"] += 1
    if CONNECT_DATA["index"] < len(CONNECT_DATA["connect_list"]):
        region = REGION_DATA["region"]  # type: bpy.types.Region
        group_info = CONNECT_DATA["connect_list"][
            CONNECT_DATA["index"]
        ]  # type: dict[str, Any]
        ag_utils.set_view_rotation(region, group_info["proj_normal"])
        return 0.05
    else:
        if CONNECT_DATA["undo"]:
            bpy.ops.ed.undo_push(message="Connect Sectors")


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

        bpy.ops.object.mode_set(mode="EDIT")
        # 全选所有面
        bpy.ops.mesh.select_all(action="SELECT")
        # 重新计算法向（内侧）
        bpy.ops.mesh.normals_make_consistent(inside=True)
        bpy.ops.object.mode_set(mode="OBJECT")

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
    from_separate: BoolProperty(default=False)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context: Context):
        global CONNECT_DATA, REGION_DATA
        # 如果是从F3执行，获取当前选中的扇区
        if not self.is_button:
            data.SELECTED_SECTORS, data.ACTIVE_SECTOR = ag_utils.get_selected_sectors()
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        active_sector = context.active_object
        # 如果缺少活跃对象，直接返回
        if not active_sector:
            self.report({"WARNING"}, "No active object")
            return {"CANCELLED"}
            # context.view_layer.objects.active = selected_sectors[0]

        # 如果活跃对象不是扇区，直接返回
        if not active_sector.amagate_data.is_sector:
            self.report({"WARNING"}, "Active object is not a sector")
            return {"CANCELLED"}

        selected_sectors = data.SELECTED_SECTORS
        if active_sector not in selected_sectors:
            active_sector.select_set(True)
            selected_sectors.append(active_sector)
        if len(selected_sectors) < 2:
            self.report({"WARNING"}, "Select at least two sectors")
            return {"CANCELLED"}

        sectors = selected_sectors.copy()
        sectors.remove(active_sector)

        # 重置连接管理器
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            sec_data["ConnectManager"] = {"sec_ids": [], "faces": {}, "new_verts": []}
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            attributes = mesh.attributes.get("amagate_connected")
            if attributes:
                mesh.attributes.remove(attributes)
            mesh.attributes.new(
                name="amagate_connected", type="INT", domain="FACE"
            )  # BOOLEAN

        scene_data = context.scene.amagate_data

        # 如果启用了自动分离
        # if scene_data.operator_props.sec_connect_sep_convex:
        #     bpy.ops.amagate.sector_separate_convex(undo=False, is_button=True, auto_connect=0)  # type: ignore
        # selected_sectors = SECTORS_LIST

        connect_list = self.get_connect_list(context, sectors, active_sector)
        self.gen_knife(context, sectors, active_sector, connect_list)
        connect_list = list(connect_list.values())

        if connect_list != []:
            self.intersect(context, connect_list, active_sector)
            # self.connect(context, connect_list, active_sector)

        # for sec in selected_sectors:
        #     mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        #     sec_data = sec.amagate_data.get_sector_data()
        #     for i, sid in sec_data["ConnectManager"]["faces"].items():
        #         mesh.attributes["amagate_connected"].data[int(i)].value = sid  # type: ignore

        if self.undo:
            bpy.ops.ed.undo_push(message="Connect Sectors")
        return {"FINISHED"}

        # area = context.area
        # region = next(r for r in area.regions if r.type == "WINDOW")

        # 保存活动扇区的面数据
        bm_edit = bmesh.from_edit_mesh(active_sector.data)  # type: ignore
        bm_edit.faces.ensure_lookup_table()
        for group_info in connect_list:
            faces = [bm_edit.faces[i] for i in group_info["faces_idx"]]
            group_info["faces"] = faces

        CONNECT_DATA = {
            "index": 0,
            "active_sector": active_sector,
            "active_bm": bm_edit,
            "connect_list": connect_list,
            "undo": self.undo,
        }
        # REGION_DATA = {
        #     "area": area,
        #     "region": region,
        #     "view_rotation": region.data.view_rotation.copy(),
        #     "view_perspective": region.data.view_perspective,
        #     "shading_type": area.spaces[0].shading.type,  # type: ignore
        # }
        # region.data.view_perspective = "ORTHO"  # 正交视角
        # area.spaces[0].shading.type = "WIREFRAME"  # type: ignore

        # group_info = CONNECT_DATA["connect_list"][
        #     CONNECT_DATA["index"]
        # ]  # type: dict[str, Any]
        # ag_utils.set_view_rotation(region, group_info["proj_normal"])

        # bpy.app.timers.register(connect_timer, first_interval=0.05)

        # self.report({"INFO"}, "Sectors connected successfully")
        return {"FINISHED"}

        bpy.ops.object.mode_set(mode="OBJECT")
        for i, sec1 in enumerate(selected_sectors):
            for j, sec2 in enumerate(selected_sectors):
                if j > i:
                    self.connect(sec1, sec2)

        success = False
        for sec in selected_sectors:
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data["ConnectManager"]["sec_ids"] and not success:
                success = True
            for i, sid in sec_data["ConnectManager"]["faces"].items():
                mesh.attributes["amagate_connected"].data[int(i)].value = sid  # type: ignore

        if success:
            self.report({"INFO"}, "Sectors connected successfully")
            return {"FINISHED"}
        else:
            self.report({"INFO"}, "No sectors to connect")
            return {"CANCELLED"}

    # 获取连接列表
    def get_connect_list(
        self, context: Context, sectors: list[Object], active_sector: Object
    ):
        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式

        active_mesh = active_sector.data  # type: bpy.types.Mesh # type: ignore
        active_matrix = active_sector.matrix_world
        active_bm_edit = bmesh.from_edit_mesh(active_sector.data)  # type: ignore
        active_bm_edit.faces.ensure_lookup_table()
        active_sec_data = active_sector.amagate_data.get_sector_data()
        active_sec_ids = active_sec_data["ConnectManager"]["sec_ids"].to_list()

        # 连接列表
        connect_list = {}
        # 可连接扇区
        connect_sectors = []
        # 活动扇区已访问的面
        visited_faces = []
        for face1_idx, face1 in enumerate(active_bm_edit.faces):
            # 跳过已访问的面
            if face1_idx in visited_faces:
                continue

            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            active_bm_edit.faces[face1_idx].select_set(True)  # 选择面
            # 选中相连的平展面
            bpy.ops.mesh.faces_select_linked_flat(sharpness=0.005)
            group_faces_idx = [f.index for f in active_bm_edit.faces if f.select]
            # 更新已访问的面
            visited_faces.extend(group_faces_idx)

            # group_verts_dict = {(active_matrix @ v.co).to_tuple(4): v.index for i in group_faces_idx for v in active_bm_edit.faces[i].verts}

            normal1 = active_matrix.to_quaternion() @ face1.normal
            for sec in sectors:
                # 跳过可连接的扇区
                if sec in connect_sectors:
                    continue

                mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                sec_matrix = sec.matrix_world
                bm_edit = bmesh.from_edit_mesh(sec.data)  # type: ignore
                bm_edit.faces.ensure_lookup_table()
                for face2_idx, face2 in enumerate(bm_edit.faces):
                    normal2 = sec_matrix.to_quaternion() @ face2.normal
                    # 如果法向不是完全相反，跳过
                    if normal1.dot(normal2) > -epsilon2:
                        continue

                    # 获取面的顶点坐标
                    co1 = active_matrix @ face1.verts[0].co
                    co2 = sec_matrix @ face2.verts[0].co
                    # 如果顶点不是在同一平面，跳过
                    if abs((co2 - co1).dot(normal1)) > epsilon:
                        continue

                    # 添加到可连接列表，相当于已访问
                    connect_sectors.append(sec)

                    # 如果所有顶点一一对应，则直接连接
                    # 保留小数为毫米单位后一位
                    # verts1 = {(matrix1 @ v.co).to_tuple(4) for v in face1.verts}
                    # verts2 = {(matrix2 @ v.co).to_tuple(4) for v in face2.verts}
                    # if verts1.issubset(verts2) or verts2.issubset(verts1):
                    #     sec2_data = sec.amagate_data.get_sector_data()
                    #     sec2_ids = sec2_data["ConnectManager"]["sec_ids"].to_list()
                    #     if sec2_data.id not in sec1_ids:
                    #         sec1_ids.append(sec2_data.id)
                    #     if sec1_data.id not in sec2_ids:
                    #         sec2_ids.append(sec1_data.id)
                    #     sec1_data["ConnectManager"]["faces"][
                    #         str(face1_idx)
                    #     ] = sec2_data.id
                    #     sec2_data["ConnectManager"]["faces"][
                    #         str(face2_idx)
                    #     ] = sec1_data.id
                    #     # print(
                    #     #     f"connect: {sec1.name} {face1_idx} <-> {sec2.name} {face2_idx}"
                    #     # )
                    #     sec2_data["ConnectManager"]["sec_ids"] = sec2_ids
                    #     continue

                    bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                    bm_edit.faces[face2_idx].select_set(True)  # 选择面
                    # 选中相连的平展面
                    bpy.ops.mesh.faces_select_linked_flat(sharpness=0.005)
                    faces_idx = [f.index for f in bm_edit.faces if f.select]

                    # verts_dict = {(sec_matrix @ v.co).to_tuple(4): v.index for i in faces_idx for v in bm_edit.faces[i].verts}
                    # print(verts_dict.keys(), group_verts_dict.keys())
                    # # 如果顶点是组面的子集，直接连接
                    # if set(verts_dict.keys()).issubset(set(group_verts_dict.keys())):
                    #     bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
                    #     sec_data = sec.amagate_data.get_sector_data()
                    #     # sec_ids = sec_data["ConnectManager"]["sec_ids"].to_list()
                    #     for face_idx in faces_idx:
                    #         mesh.attributes["amagate_connected"].data[face_idx].value = active_sec_data.id  # type: ignore
                    #     for key in verts_dict.keys():
                    #         face_idx = group_verts_dict[key]
                    #         active_mesh.attributes["amagate_connected"].data[face_idx].value = sec_data.id  # type: ignore
                    #     bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
                    #     ag_utils.debugprint(f"connect")
                    #     break

                    group_info = connect_list.setdefault(
                        face1_idx,
                        {
                            "faces_idx": group_faces_idx,
                            "connect_info": [],
                            "proj_normal": active_matrix.to_quaternion() @ face1.normal,
                            "enable_cut": True,
                        },
                    )
                    group_info["connect_info"].append(
                        {
                            "sector": sec,
                            "faces_idx": faces_idx,
                            "knife_obj": None,
                            "knife_bm": None,
                            "enable_cut": True,
                        }
                    )
                    # 一个扇区只有一个平面相连
                    break

        active_sec_data["ConnectManager"]["sec_ids"] = active_sec_ids
        return connect_list

    # 生成刀具
    def gen_knife(
        self,
        context: Context,
        sectors: list[Object],
        active_sector: Object,
        connect_list,
    ):
        active_matrix = active_sector.matrix_world
        active_bm_edit = bmesh.from_edit_mesh(active_sector.data)  # type: ignore

        def duplicate_faces(info, sec, bm_edit, edge_split=True):
            """复制面"""
            selected_objects = context.selected_objects.copy()
            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            # 选中面
            for i in info["faces_idx"]:
                bm_edit.faces[i].select_set(True)
            bmesh.update_edit_mesh(sec.data, loop_triangles=False, destructive=False)  # type: ignore # 更新网格
            bpy.ops.mesh.duplicate()  # 复制
            if edge_split:
                bpy.ops.mesh.edge_split(type="EDGE")  # 按边拆分
                bpy.ops.mesh.separate(type="LOOSE")  # 分离松散块
            else:
                bpy.ops.mesh.separate(type="SELECTED")  # 按选中项分离
            info["sep_obj"] = next(
                o for o in context.selected_objects if o not in selected_objects
            )

        # 复制面
        for group_info in connect_list.values():
            duplicate_faces(group_info, active_sector, active_bm_edit, edge_split=False)
            for connect_info in group_info["connect_info"]:
                sec = connect_info["sector"]
                bm_edit = bmesh.from_edit_mesh(sec.data)  # type: ignore
                bm_edit.faces.ensure_lookup_table()
                active_bm_edit.faces.ensure_lookup_table()
                duplicate_faces(connect_info, sec, bm_edit, edge_split=False)

        # 融并复制出来的面
        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
        # 取消选择扇区，只保留分离出的物体
        active_sector.select_set(False)
        for sec in sectors:
            sec.select_set(False)
        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.dissolve_faces(use_verts=True)  # 融并面

        # 布尔交集处理

        for key, group_info in connect_list.items():
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
            # 投影法向
            proj_normal = group_info["proj_normal"]
            connect_num = len(group_info["connect_info"])
            group_sep_obj = group_info["sep_obj"]  # type: Object
            group_sep_obj_mesh = (
                group_sep_obj.data
            )  # type: bpy.types.Mesh # type: ignore

            if len(group_sep_obj_mesh.polygons) != 1:
                ag_utils.debugprint(f"group_sep_obj_mesh: polygon not 1")
                continue

            group_verts_dict = {}
            for v in group_sep_obj_mesh.vertices:
                co = active_matrix @ v.co
                group_verts_dict[co.to_tuple(3)] = co

            disable_cut = 0
            # 倒序处理，避免删除元素导致索引变化
            for index in range(connect_num - 1, -1, -1):
                # for index, connect_info in enumerate(group_info["connect_info"]):
                connect_info = group_info["connect_info"][index]
                sec = connect_info["sector"]  # type: Object
                sec_matrix = sec.matrix_world
                # bm_edit = bmesh.from_edit_mesh(sec.data)  # type: ignore
                # bm_edit.faces.ensure_lookup_table()
                sep_obj = connect_info["sep_obj"]  # type: Object
                sep_obj_mesh = sep_obj.data  # type: bpy.types.Mesh # type: ignore

                if len(sep_obj_mesh.polygons) != 1:
                    ag_utils.debugprint(f"sep_obj_mesh: polygon not 1")
                    continue

                verts_dict = {}
                for v in sep_obj_mesh.vertices:
                    co = sec_matrix @ v.co
                    verts_dict[co.to_tuple(3)] = co

                # ag_utils.select_active(context, sep_obj)  # 单选并设为活动
                # bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式

                # bpy.ops.mesh.select_all(action="SELECT")  # 全选网格

                # # 挤出并移动10厘米
                # bpy.ops.mesh.extrude_region_move(
                #     TRANSFORM_OT_translate={"value": proj_normal * 0.1}
                # )
                # bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                # bpy.ops.mesh.normals_make_consistent(
                #     inside=False
                # )  # 重新计算法向（外侧）
                # bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
                # # 将整体反向移动5厘米
                # bpy.ops.transform.translate(value=-proj_normal * 0.05)

                # 重新获取组分割面，因为它是上一次循环的刀具结果
                group_sep_obj = group_info["sep_obj"]  # type: Object
                # 合并处理
                ag_utils.select_active(context, group_sep_obj)  # 单选并设为活动
                # 如果不是最后一个元素，则复制
                if index != 0:
                    bpy.ops.object.duplicate()
                    group_sep_obj = context.active_object  # 获取最新的物体
                else:
                    group_info["sep_obj"] = None

                knife_matrix = group_sep_obj.matrix_world
                group_sep_obj_mesh = (
                    group_sep_obj.data
                )  # type: bpy.types.Mesh # type: ignore

                sep_obj.select_set(True)
                bpy.ops.object.join()  # 合并对象
                bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式

                bm_edit = bmesh.from_edit_mesh(group_sep_obj_mesh)
                bm_edit.faces.ensure_lookup_table()
                group_sep_face = bm_edit.faces[0]
                sep_face = bm_edit.faces[1]

                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                group_sep_face.select_set(True)
                bmesh.update_edit_mesh(
                    group_sep_obj_mesh, loop_triangles=False, destructive=False
                )
                bpy.ops.mesh.extrude_region_move(
                    TRANSFORM_OT_translate={"value": proj_normal * 0.1}
                )  # 往投影法向挤出并移动10厘米

                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                sep_face.select_set(True)
                bmesh.update_edit_mesh(
                    group_sep_obj_mesh, loop_triangles=False, destructive=False
                )
                bpy.ops.transform.translate(
                    value=proj_normal * 0.05
                )  # 往投影法向移动5厘米
                bpy.ops.mesh.extrude_region_move(
                    TRANSFORM_OT_translate={"value": -proj_normal * 0.1}
                )  # 往反方向挤出并移动10厘米

                bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                bpy.ops.mesh.normals_make_consistent(
                    inside=False
                )  # 重新计算法向（外侧）

                # 开始布尔交集
                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                bm_edit.faces.ensure_lookup_table()
                # 选择属于活动扇区的面
                group_sep_face.select_set(True)
                # 更新网格
                bmesh.update_edit_mesh(
                    group_sep_obj_mesh, loop_triangles=False, destructive=False
                )
                bpy.ops.mesh.select_linked()  # 选择关联项

                with contextlib.redirect_stdout(StringIO()):
                    bpy.ops.mesh.intersect_boolean(
                        operation="INTERSECT", solver="EXACT"
                    )  # 布尔交集，准确模式
                    # 如果没有交集
                    if len(bm_edit.verts) == 0:
                        # 删除元素
                        del group_info["connect_info"][index]
                        # ag_utils.debugprint(f"No intersect")
                        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
                        continue

                    bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                    bpy.ops.mesh.normals_make_consistent(
                        inside=True
                    )  # 重新计算法向（内侧）
                    # 选择与投影法向相同的面
                    bpy.ops.mesh.select_mode(type="FACE")  # 切换面模式
                    bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                    for f in bm_edit.faces:
                        dot = (knife_matrix @ f.normal).dot(proj_normal)
                        ag_utils.debugprint(f"dot: {dot}")
                        if dot > 0.999:
                            f.select_set(True)
                            break
                    bmesh.update_edit_mesh(
                        group_sep_obj_mesh, loop_triangles=False, destructive=False
                    )
                    bpy.ops.mesh.faces_select_linked_flat(
                        sharpness=0.005
                    )  # 选中相连的平展面

                    bpy.ops.mesh.select_all(action="INVERT")  # 反选
                    bpy.ops.mesh.delete(type="FACE")  # 删除面

                    # 简并融并，两次
                    bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                    bpy.ops.mesh.dissolve_degenerate()
                    bpy.ops.mesh.dissolve_degenerate()
                    # 融并面
                    bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                    bpy.ops.mesh.dissolve_faces(use_verts=True)  # 融并面
                    # 合并顶点（按距离）
                    # bpy.ops.mesh.remove_doubles(threshold=0.0005)  # 0.5毫米

                # 纠正刀具顶点
                # for v in bm_edit.verts:
                #     key = (knife_matrix @ v.co).to_tuple(3)
                #     co = group_verts_dict.get(key)
                #     if co is None:
                #         co = verts_dict.get(key)
                #     if co is not None:
                #         v.co = knife_matrix.inverted() @ co
                # bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

                knife_verts_dict = {
                    (knife_matrix @ v.co).to_tuple(3) for v in bm_edit.verts
                }
                # print(knife_verts_dict)
                # print(verts_dict.keys())
                # 如果组面等于刀具，则无需切割
                if knife_verts_dict == set(group_verts_dict.keys()):
                    group_info["enable_cut"] = False
                # 如果连接扇区的面等于刀具，则无需切割
                if knife_verts_dict == set(verts_dict.keys()):
                    connect_info["enable_cut"] = False
                    disable_cut += 1
                    # if disable_cut == connect_num:
                    #     group_info["enable_cut"] = False
                    #     ag_utils.debugprint(f"Disable cut")

                bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
                bpy.ops.object.transform_apply(
                    location=True, rotation=True, scale=True
                )  # 应用变换
                connect_info["knife_obj"] = group_sep_obj

                # 保存刀具bm
                # bpy.ops.object.duplicate()  # 复制
                # knife_obj = context.active_object
                # bpy.ops.transform.translate(value=proj_normal * 5)  # 往投影法向移动5米
                # bpy.ops.object.transform_apply(
                #     location=True, rotation=True, scale=True
                # )  # 应用变换
                knife_bm = bmesh.new()
                knife_bm.from_mesh(group_sep_obj_mesh)  # type: ignore
                # 放大，再往投影法向移动1米
                # matrix = Matrix.Scale(1.001, 4)
                # matrix.translation = proj_normal
                bmesh.ops.transform(
                    knife_bm, matrix=Matrix.Translation(proj_normal), verts=knife_bm.verts  # type: ignore
                )  #
                connect_info["knife_bm"] = knife_bm

                # bpy.data.meshes.remove(knife_obj.data)  # type: ignore

                # bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
                # bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                # bpy.ops.mesh.edge_split(type="EDGE")  # 按边拆分
                # bpy.ops.mesh.separate(type="LOOSE")  # 分离松散块
                # bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

            # 清理
            if not group_info["connect_info"]:
                connect_list[key] = None

        for k in list(connect_list.keys()):
            if connect_list[k] is None:
                del connect_list[k]

            #

            # 刀具bm
            # knife_bm = bmesh.new()

            # main_faces_dup = bmesh.ops.duplicate(active_bm_edit, geom=main_faces)
            # faces_dup = bmesh.ops.duplicate(bm_edit, geom=faces)

            # bmesh.ops.split(
            #     active_bm_edit,
            #     geom=[elem for elem in main_faces_dup['geom'] if isinstance(elem, bmesh.types.BMFace)]
            # )
            # bmesh.ops.split(
            #     bm_edit,
            #     geom=[elem for elem in faces_dup['geom'] if isinstance(elem, bmesh.types.BMFace)]
            # )

            # knife_mesh = bpy.data.meshes.new(f"AG.{active_sector.name}_knife")
            # knife_obj = bpy.data.objects.new(
            #     f"AG.{active_sector.name}_knife", knife_mesh
            # )
            # knife_bm.to_mesh(knife_mesh)
            # data.link2coll(knife_obj, context.collection)

        # bmesh.ops.split(
        #     mesh,
        #     geom=selected_geom,
        #     dest=mesh  # 分离到当前mesh（实际会生成独立数据）
        # )
        # bmesh.update_edit_mesh(obj.data)

        # extruded = bmesh.ops.extrude_face_region(mesh, geom=selected_faces)
        # bmesh.ops.translate(
        #     mesh,
        #     vec=selected_faces[0].normal * 0.5,  # 使用第一个面的法线方向
        #     verts=[v for v in extruded['geom'] if isinstance(v, bmesh.types.BMVert)]
        # )

    # 交集（切割）
    def intersect(self, context: Context, connect_list: list, active_sector: Object):
        active_sec_data = active_sector.amagate_data.get_sector_data()
        active_sec_data.mesh_unique()  # 确保网格数据为单用户的
        active_mesh = active_sector.data  # type: bpy.types.Mesh # type: ignore

        def join_knife(enable_cut, knife_obj, sec, proj_normal):
            # type: (bool, Object, Object, Vector) -> None
            """合并刀具"""
            if enable_cut:
                # 确保刀具法线是相反的
                # fmt: off
                normal2 = knife_obj.data.polygons[0].normal  # type: Vector # type: ignore
                # fmt: on
                if normal2.dot(proj_normal) > 0:
                    ag_utils.select_active(context, knife_obj)  # 单选并设为活动
                    bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
                    bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
                    bpy.ops.mesh.flip_normals()  # 反转法向
                    # bpy.ops.mesh.normals_make_consistent(inside=True)# 重新计算法向（内侧）
                    bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

                # 合并刀具到主扇区
                ag_utils.select_active(context, sec)  # 单选并设为活动
                knife_obj.select_set(True)  # 选择刀具
                bpy.ops.object.join()  # 合并对象
            else:
                # 不需要切割，删除刀具
                bpy.data.meshes.remove(knife_obj.data)  # type: ignore

        # 合并刀具
        for group_info in connect_list:
            proj_normal = group_info["proj_normal"]  # type: Vector
            for connect_info in group_info["connect_info"]:
                sec = connect_info["sector"]  # type: Object
                sec_data = sec.amagate_data.get_sector_data()
                sec_data.mesh_unique()  # 确保网格数据为单用户的
                # 复制刀具物体
                knife_obj = connect_info["knife_obj"]  # type: Object
                ag_utils.select_active(context, knife_obj)  # 单选并设为活动
                bpy.ops.object.duplicate()  # 复制
                knife_obj_copy = context.active_object

                join_knife(
                    group_info["enable_cut"], knife_obj_copy, active_sector, proj_normal
                )
                join_knife(connect_info["enable_cut"], knife_obj, sec, -proj_normal)

        # 选择所有扇区
        ag_utils.select_active(context, active_sector)  # 单选并设为活动
        for group_info in connect_list:
            for connect_info in group_info["connect_info"]:
                connect_info["sector"].select_set(True)  # 选择扇区

        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格

        mesh_lst = []  # type: list[bpy.types.Mesh]

        enable_cut = False
        # 保存顶点和面法向，并选择代表面
        for group_info in connect_list:
            active_bm_edit = bmesh.from_edit_mesh(active_mesh)
            active_bm_edit.faces.ensure_lookup_table()
            face = active_bm_edit.faces[
                group_info["faces_idx"][0]
            ]  # type: bmesh.types.BMFace
            normal = face.normal
            dist_1 = face.verts[0].co.dot(normal)
            group_info["face_info"] = (dist_1, normal)
            if group_info["enable_cut"]:
                # 调整刀具面位置
                knife_face = active_bm_edit.faces[-1]
                dist_2 = knife_face.verts[0].co.dot(normal)
                offset = dist_1 - dist_2
                bmesh.ops.translate(
                    active_bm_edit,
                    vec=normal * offset,
                    verts=[v for v in knife_face.verts],
                )  # 移动刀具面

                face.select_set(True)  # 选择主扇区面
                bmesh.update_edit_mesh(
                    active_mesh, loop_triangles=False, destructive=False
                )  # 更新网格
                if not enable_cut:
                    enable_cut = True
            for connect_info in group_info["connect_info"]:
                sec = connect_info["sector"]
                mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                bm_edit = bmesh.from_edit_mesh(mesh)
                bm_edit.faces.ensure_lookup_table()
                mesh_lst.append(mesh)
                face = bm_edit.faces[
                    connect_info["faces_idx"][0]
                ]  # type: bmesh.types.BMFace
                normal = face.normal
                dist_1 = face.verts[0].co.dot(normal)
                connect_info["face_info"] = (dist_1, normal)
                if connect_info["enable_cut"]:
                    # 调整刀具面位置
                    knife_face = bm_edit.faces[-1]
                    dist_2 = knife_face.verts[0].co.dot(normal)
                    offset = dist_1 - dist_2
                    bmesh.ops.translate(
                        bm_edit,
                        vec=normal * offset,
                        verts=[v for v in knife_face.verts],
                    )  # 移动刀具面

                    face.select_set(True)  # 选择连接扇区面
                    bmesh.update_edit_mesh(
                        mesh, loop_triangles=False, destructive=False
                    )  # 更新网格
                    if not enable_cut:
                        enable_cut = True
        # 如果需要切
        if enable_cut:
            bpy.ops.mesh.select_linked()  # 选择关联项
            # return
            # 交集(切割)，剪切模式
            bpy.ops.mesh.intersect(mode="SELECT_UNSELECT", separate_mode="CUT")
            # 选择主扇区和所有连接扇区的面
            bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
            active_bm_edit.faces.ensure_lookup_table()
            active_bm_edit.faces[0].select_set(True)  # 选择主扇区面
            bmesh.update_edit_mesh(
                active_mesh, loop_triangles=False, destructive=False
            )  # 更新网格
            for mesh in mesh_lst:
                bm_edit = bmesh.from_edit_mesh(mesh)
                bm_edit.faces.ensure_lookup_table()
                bm_edit.faces[0].select_set(True)  # 选择连接扇区面
                bmesh.update_edit_mesh(
                    mesh, loop_triangles=False, destructive=False
                )  # 更新网格
            bpy.ops.mesh.select_linked()  # 选择关联项
            # 删除刀具面
            bpy.ops.mesh.select_all(action="INVERT")  # 反选
            bpy.ops.mesh.delete(type="FACE")  # 删除面

            bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
            with contextlib.redirect_stdout(StringIO()):
                # 简并融并，两次
                bpy.ops.mesh.dissolve_degenerate()
                bpy.ops.mesh.dissolve_degenerate()
            #     # 合并顶点（按距离）
            #     bpy.ops.mesh.remove_doubles(threshold=0.0003)  # 0.3毫米
            # 重新计算法向（内侧）
            bpy.ops.mesh.normals_make_consistent(inside=True)

    def connect(self, context: Context, connect_list: list, active_sector: Object):
        active_matrix = active_sector.matrix_world
        active_sec_data = active_sector.amagate_data.get_sector_data()
        # active_sec_ids = active_sec_data["ConnectManager"]["sec_ids"].to_list()
        active_mesh = active_sector.data  # type: bpy.types.Mesh # type: ignore
        active_bm_edit = bmesh.from_edit_mesh(active_mesh)
        active_bm_edit.verts.ensure_lookup_table()

        active_sec_faces = []
        sec_faces = []
        mesh_lst = []

        for group_info in connect_list:
            proj_normal = group_info["proj_normal"]  # type: Vector
            # 获取组面
            group_faces = []
            dist = group_info["face_info"][0]  # type: float
            normal = group_info["face_info"][1]  # type:  Vector
            for f in active_bm_edit.faces:
                if f.normal.dot(normal) < epsilon2:
                    continue
                # 如果法向一致，判断距离
                # diff = abs(f.verts[0].co.dot(normal) - dist)
                if abs(f.verts[0].co.dot(normal) - dist) < epsilon:
                    bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                    f.select_set(True)  # 选择主扇区面
                    bmesh.update_edit_mesh(
                        active_mesh, loop_triangles=False, destructive=False
                    )  # 更新网格
                    bpy.ops.mesh.faces_select_linked_flat(
                        sharpness=0.005
                    )  # 选中相连的平展面
                    bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
                    group_faces = [f for f in active_bm_edit.faces if f.select]
                    break

            if not group_faces:
                ag_utils.debugprint(f"No group faces")
                continue

            for connect_info in group_info["connect_info"]:
                sec = connect_info["sector"]  # type: Object
                sec_data = sec.amagate_data.get_sector_data()
                sec_matrix = sec.matrix_world
                mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                bm_edit = bmesh.from_edit_mesh(mesh)
                bm_edit.verts.ensure_lookup_table()
                mesh_lst.append(mesh)  # type: list[bmesh.types.BMesh]

                # 获取连接面
                connect_faces = []
                dist = connect_info["face_info"][0]  # type: float
                normal = connect_info["face_info"][1]  # type:  Vector
                for f in bm_edit.faces:
                    if f.normal.dot(normal) < epsilon2:
                        continue
                    # 如果法向一致，判断距离
                    if abs(f.verts[0].co.dot(normal) - dist) < epsilon:
                        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                        f.select_set(True)  # 选择主扇区面
                        bmesh.update_edit_mesh(
                            mesh, loop_triangles=False, destructive=False
                        )  # 更新网格
                        bpy.ops.mesh.faces_select_linked_flat(
                            sharpness=0.005
                        )  # 选中相连的平展面
                        bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
                        connect_faces = [f for f in bm_edit.faces if f.select]
                        break

                if not connect_faces:
                    ag_utils.debugprint(f"No connect faces")
                    continue

                # 融并切割出来的所有面
                knife_bm = connect_info["knife_bm"]  # type: bmesh.types.BMesh
                bvh = bvhtree.BVHTree.FromBMesh(knife_bm)
                # face_dict = {"group_faces": [], "connect_faces": []}  # type: dict[str, list[bmesh.types.BMFace]
                bm_edit.faces.ensure_lookup_table()

                hit = False
                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                # 倒序遍历，避免删除元素导致索引变化
                for index in range(len(group_faces) - 1, -1, -1):
                    f = group_faces[index]  # type: bmesh.types.BMFace
                    # 定义射线起点、方向和距离
                    ray_origin = active_matrix @ f.calc_center_bounds()
                    ray_direction = proj_normal
                    # 执行射线检测
                    hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                        bvh, ray_origin, ray_direction
                    )
                    if hit_index is not None:
                        if not hit:
                            hit = True
                        f.select_set(True)
                        del group_faces[index]
                if hit:
                    bmesh.update_edit_mesh(
                        active_mesh, loop_triangles=False, destructive=False
                    )  # 更新网格
                    bpy.ops.mesh.dissolve_faces(use_verts=True)  # 融并面
                    selected_faces = [f for f in active_bm_edit.faces if f.select]
                    active_face = selected_faces[0]
                else:
                    active_face = None
                    ag_utils.debugprint(f"No hit: active face")

                hit = False
                bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                for f in connect_faces:
                    # 定义射线起点、方向和距离
                    ray_origin = sec_matrix @ f.calc_center_bounds()
                    ray_direction = proj_normal
                    # ag_utils.debugprint(f"face_idx: {f.index}, ray_origin: {ray_origin}, ray_direction: {ray_direction}")
                    # 执行射线检测
                    hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                        bvh, ray_origin, ray_direction
                    )
                    if hit_index is not None:
                        if not hit:
                            hit = True
                        f.select_set(True)
                        # face_dict[hit_index]["connect_faces"].append(f)
                    # hit_loc, hit_normal, hit_index, hit_dist = bvhtree.BVHTree.ray_cast(
                    #     bvh, Vector([2.9, -4.5, -2.9]), ray_direction
                    # )
                    # ag_utils.debugprint(f"hit_index: {hit_index}")
                if hit:
                    bmesh.update_edit_mesh(
                        mesh, loop_triangles=False, destructive=False
                    )  # 更新网格
                    bpy.ops.mesh.dissolve_faces(use_verts=True)  # 融并面
                    selected_faces = [f for f in bm_edit.faces if f.select]
                    connect_face = selected_faces[0]
                else:
                    connect_face = None
                    ag_utils.debugprint(f"No hit: connect face")

                # 删除刀具bm
                connect_info["knife_bm"] = None
                knife_bm.free()

                if not active_face or not connect_face:
                    continue

                # for dict_ in face_dict.values():
                #     face_list = []  # type: list[bmesh.types.BMFace]
                #     bm_lst = (active_bm_edit, bm_edit)
                #     mesh_lst = (active_mesh, mesh)
                #     key = ("group_faces", "connect_faces")
                #     for i in range(2):
                #         faces = dict_[key[i]]
                #         if len(faces) > 1:
                #             bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
                #             for f in faces:
                #                 f.select_set(True)
                #                 bmesh.update_edit_mesh(
                #                     mesh_lst[i], loop_triangles=False, destructive=False
                #                 )
                #             # 尝试融并面
                #             bpy.ops.mesh.dissolve_faces()
                #             selected_faces = [f for f in bm_lst[i].faces if f.select]
                #             face_list.append(selected_faces[0])
                #         elif len(faces) == 1:
                #             face_list.append(faces[0])
                #         else:
                #             break
                #     else:
                #         # ag_utils.debugprint(f"face_list: {face_list}")
                #         active_face = face_list[0]
                #         connect_face = face_list[1]

                # 保留小数为毫米单位后一位
                verts1 = {(active_matrix @ v.co).to_tuple(4) for v in active_face.verts}
                verts2 = {(sec_matrix @ v.co).to_tuple(4) for v in connect_face.verts}
                if verts1.issubset(verts2) or verts2.issubset(verts1):
                    # sec_ids = sec_data["ConnectManager"]["sec_ids"].to_list()
                    # if sec_data.id not in active_sec_ids:
                    #     active_sec_ids.append(sec_data.id)
                    # if active_sec_data.id not in sec_ids:
                    #     sec_ids.append(active_sec_data.id)
                    # active_sec_data["ConnectManager"]["faces"][
                    #     str(active_face.index)
                    # ] = sec_data.id
                    # sec_data["ConnectManager"]["faces"][
                    #     str(connect_face.index)
                    # ] = active_sec_data.id
                    # sec_data["ConnectManager"]["sec_ids"] = sec_ids
                    layer = active_bm_edit.faces.layers.int.get("amagate_connected")
                    active_face[layer] = sec_data.id  # type: ignore
                    layer = bm_edit.faces.layers.int.get("amagate_connected")
                    connect_face[layer] = active_sec_data.id  # type: ignore
                    # active_mesh.attributes["amagate_connected"].data[active_face.index].value = sec_data.id  # type: ignore
                    # mesh.attributes["amagate_connected"].data[connect_face.index].value = active_sec_data.id  # type: ignore
                    active_sec_faces.append(active_face)
                    sec_faces.append(connect_face)
                    ag_utils.debugprint(
                        f"connect: {active_sector.name} {active_face.index}  <-> {sec.name} {connect_face.index}"
                    )

        faces = active_sec_faces + sec_faces
        if not faces:
            ag_utils.debugprint(f"No faces to connect")

        # 对平展面进行拆分凹面
        # bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        # for f in active_sec_faces + sec_faces:
        #     f.select_set(True)
        # for mesh in mesh_lst:
        #     bmesh.update_edit_mesh(
        #         mesh, loop_triangles=False, destructive=False
        #     )  # 更新网格
        # bmesh.update_edit_mesh(
        #     active_mesh, loop_triangles=False, destructive=False
        # )  # 更新网格
        # bpy.ops.mesh.faces_select_linked_flat(sharpness=0.005)  # 选中相连的平展面
        # # 排除连接面
        # for f in active_sec_faces + sec_faces:
        #     f.select_set(False)
        # for mesh in mesh_lst:
        #     bmesh.update_edit_mesh(
        #         mesh, loop_triangles=False, destructive=False
        #     )  # 更新网格
        # bmesh.update_edit_mesh(
        #     active_mesh, loop_triangles=False, destructive=False
        # )  # 更新网格
        # bpy.ops.mesh.vert_connect_concave()  # 拆分凹面

        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

    def connect_del(self, sec1: Object, sec2: Object):
        matrix1 = sec1.matrix_world
        matrix2 = sec2.matrix_world
        mesh1 = sec1.data  # type: bpy.types.Mesh # type: ignore
        mesh2 = sec2.data  # type: bpy.types.Mesh # type: ignore
        sec1_data = sec1.amagate_data.get_sector_data()
        sec2_data = sec2.amagate_data.get_sector_data()
        knife1 = {}
        knife2 = {}
        AG_COLL = data.ensure_collection(data.AG_COLL, hide_select=True)
        sec1_ids = sec1_data["ConnectManager"]["sec_ids"].to_list()
        sec2_ids = sec2_data["ConnectManager"]["sec_ids"].to_list()
        for face1_idx, face1 in enumerate(sec1.data.polygons):  # type: ignore
            for face2_idx, face2 in enumerate(sec2.data.polygons):  # type: ignore
                normal1 = matrix1.to_quaternion() @ face1.normal
                normal2 = matrix2.to_quaternion() @ face2.normal
                # 获取面的顶点坐标
                co1 = matrix1 @ mesh1.vertices[face1.vertices[0]].co
                co2 = matrix2 @ mesh2.vertices[face2.vertices[0]].co
                # 判断顶点是否在同一平面
                is_same_plane = (co2 - co1).dot(normal1) < 1e-5
                # 如果面可以连接, 法向完全相反且在同一平面
                if normal1.dot(normal2) + 1 < 1e-5 and is_same_plane:
                    # 保留小数为毫米单位后一位
                    verts1 = {
                        (matrix1 @ mesh1.vertices[i].co).to_tuple(4)
                        for i in face1.vertices
                    }
                    verts2 = {
                        (matrix2 @ mesh2.vertices[i].co).to_tuple(4)
                        for i in face2.vertices
                    }
                    if verts1.issubset(verts2) or verts2.issubset(verts1):
                        if sec2_data.id not in sec1_ids:
                            sec1_ids.append(sec2_data.id)
                        if sec1_data.id not in sec2_ids:
                            sec2_ids.append(sec1_data.id)
                        sec1_data["ConnectManager"]["faces"][
                            str(face1_idx)
                        ] = sec2_data.id
                        sec2_data["ConnectManager"]["faces"][
                            str(face2_idx)
                        ] = sec1_data.id
                        print(
                            f"connect: {sec1.name} {face1_idx} <-> {sec2.name} {face2_idx}"
                        )
                        continue

                    if knife1.get(face1_idx) is None:
                        bm = bmesh.new()
                        bm.faces.new(verts1)
                        knife_mesh = bpy.data.meshes.new(
                            f"AG.{sec1.name}_knife{face1_idx}"
                        )
                        knife_obj = bpy.data.objects.new(
                            f"AG.{sec1.name}_knife{face1_idx}", knife_mesh
                        )
                        bm.to_mesh(knife_mesh)
                        knife1[face1_idx] = knife_obj
                        data.link2coll(knife_obj, AG_COLL)
                    if knife2.get(face2_idx) is None:
                        bm = bmesh.new()
                        bm.faces.new(verts2)
                        knife_mesh = bpy.data.meshes.new(
                            f"AG.{sec2.name}_knife{face2_idx}"
                        )
                        knife_obj = bpy.data.objects.new(
                            f"AG.{sec2.name}_knife{face2_idx}", knife_mesh
                        )
                        bm.to_mesh(knife_mesh)
                        knife2[face2_idx] = knife_obj
                        data.link2coll(knife_obj, AG_COLL)

        sec1_data["ConnectManager"]["sec_ids"] = sec1_ids
        sec2_data["ConnectManager"]["sec_ids"] = sec2_ids

        for face_idx, knife_obj in knife1.items():
            ...
            # has_intersect = False
            # for vert1 in face1.vertices:
            #     hit, location, normal, index = sec2.ray_cast(
            #         matrix2.inverted() @ (matrix1 @ mesh1.vertices[vert1].co),
            #         matrix2.inverted() @ -normal1,
            #     )
            #     # 如果面之间有交集
            #     if hit and normal == face2.normal:
            #         has_intersect = True
            #         break
            # if has_intersect:
            #     print("connect", sec1.name, sec2.name)


# 分离凸多面体
class OT_Sector_SeparateConvex(bpy.types.Operator):
    bl_idname = "amagate.sector_separate_convex"
    bl_label = "Separate Convex"
    bl_description = "Separate selected sectors into convex parts"
    # bl_options = {"UNDO"}

    undo: BoolProperty(default=True)  # type: ignore
    is_button: BoolProperty(default=False)  # type: ignore
    # 自动连接，仅用于内部传参，如果为-1，则使用UI开关值
    auto_connect: IntProperty(default=-1)  # type: ignore

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
                key = co.to_tuple(4)
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
            # 跳过凸多面体
            if sec_data.is_convex:
                continue
            # 跳过非二维球面
            if not sec_data.is_2d_sphere:
                non_2d_sphere_list.append(sec)
                continue

            concave_type = sec_data["ConcaveData"]["concave_type"]
            # 跳过复杂凹多面体
            if concave_type == ag_utils.CONCAVE_T_COMPLEX:
                complex_list.append(sec)
                continue

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
                "auto_connect": self.auto_connect,
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
        #     self.report({"INFO"}, "No need to separate")
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
