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
epsilon = ag_utils.epsilon
epsilon2 = ag_utils.epsilon2


############################
############################ For Separate Convex
############################

separate_data = {}  # type: Any


def pre_knife_project():
    """投影切割预处理"""
    context = bpy.context
    separate = separate_data["separate_list"][
        separate_data["index"]
    ]  # type: tuple[Object, set[int], set[int], list[int], list[Object], Vector]
    (
        sec,
        faces_index,
        faces_index_prime,
        faces_exterior_idx,
        knife_project,
        proj_normal_prime,
    ) = separate
    region = separate_data["region"]  # type: bpy.types.Region
    # sec, faces_index, knifes, proj_normal_prime = knife_project.pop()

    # 确保网格数据为单用户的
    sec_data = sec.amagate_data.get_sector_data()
    sec_data.mesh_unique()

    bpy.ops.object.select_all(action="DESELECT")  # 取消选择
    context.view_layer.objects.active = sec  # 设置活动物体
    bpy.ops.object.mode_set(mode="EDIT")
    for knife in knife_project:
        knife.select_set(True)
    ag_utils.set_view_rotation(region, proj_normal_prime)
    region.data.view_perspective = "ORTHO"

    bpy.app.timers.register(knife_project_timer, first_interval=0.05)


def knife_project_timer():
    """投影切割定时器"""
    context = bpy.context
    separate = separate_data["separate_list"][
        separate_data["index"]
    ]  # type: tuple[Object, set[int], set[int], list[int], list[Object], Vector]
    (
        sec,
        faces_index,  # 刀具面
        faces_index_prime,  # 排除垂直面的刀具面
        faces_exterior_idx,  # 与刀具面共边的外部面
        knife_project,  # 投影切割刀具
        proj_normal_prime,
    ) = separate
    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
    # 隐藏刀具面
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    for i in faces_index:
        bm.faces[i].hide = True
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    # 投影切割
    with context.temp_override(
        area=separate_data["area"],
        region=separate_data["region"],
    ):
        bpy.ops.mesh.knife_project()
        for obj in knife_project:
            bpy.data.meshes.remove(obj.data)  # type: ignore
    # 显示刀具面
    bm.faces.ensure_lookup_table()
    for i in faces_index:
        bm.faces[i].hide = False
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    separate_data["index"] += 1
    if separate_data["index"] < len(separate_data["separate_list"]):
        pre_knife_project()
    else:
        knife_project_done()


def knife_project_done():
    """投影切割完成，开始分离"""
    context = bpy.context

    #
    separate_list = separate_data[
        "separate_list"
    ]  # type: list[tuple[Object, set[int], set[int], list[int], list[Object], Vector]]
    for (
        sec,
        faces_index,
        faces_index_prime,
        faces_exterior_idx,
        knife_project,
        proj_normal_prime,
    ) in separate_list:
        main_sec = sec
        sec_data = sec.amagate_data.get_sector_data()
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
        sec_bm.verts.ensure_lookup_table()
        faces = [sec_bm.faces[i] for i in faces_index_prime]
        verts_index = sec_data["ConcaveData"]["verts_index"]
        # 与刀具面共边的外部面顶点
        verts_exterior = set(
            v for i in faces_exterior_idx for v in sec_bm.faces[i].verts
        )

        # 遍历刀具面
        for face in faces:
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
                for v3 in face.verts:
                    # 投影到顶点的情况
                    if (proj_point - v3.co).length < 1e-4:
                        verts_index.add(v2.index)
                        # 如果是外部顶点的子集
                        if {v2, v3}.issubset(verts_exterior):
                            for e in v2.link_edges:
                                # v2与v3存在边，跳过
                                if e.other_vert(v2) == v3:
                                    break
                            # v2与v3不存在边，添加边
                            else:
                                bmesh.ops.connect_vert_pair(sec_bm, verts=[v2, v3])
                                bmesh.update_edit_mesh(mesh)
                        break
                # 没有投影到顶点，也许在边上或者在面的内部
                else:
                    proj_point_2d = u.dot(proj_point), v.dot(proj_point)
                    if ag_utils.is_point_in_polygon(proj_point_2d, polygon):
                        verts_index.add(v2.index)

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

        # 分离完成后，进一步处理
        bpy.ops.object.mode_set(mode="OBJECT")
        selected_objects = (
            context.selected_objects.copy()
        )  # type: list[Object] # type: ignore
        selected_objects.remove(main_sec)
        # 删除空网格
        if len(main_sec.data.vertices) == 0:  # type: ignore
            ag_utils.delete_sector(main_sec)
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
                for v_idx in f.vertices:
                    if v_idx not in visited_verts:
                        visited_verts.append(v_idx)
                        vector2 = mesh.vertices[v_idx].co - base_point
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

    area = separate_data["area"]  # type: bpy.types.Area
    region = separate_data["region"]  # type: bpy.types.Region
    region.data.view_rotation = separate_data["view_rotation"]
    region.data.view_perspective = separate_data["view_perspective"]
    area.spaces[0].shading.type = separate_data["shading_type"]  # type: ignore

    if separate_data["undo"]:
        bpy.ops.ed.undo_push(message="Separate Convex")


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
        return context.scene.amagate_data.is_blade

    def execute(self, context: Context):
        original_selection = context.selected_objects
        if not original_selection:
            self.report({"INFO"}, "No objects selected")
            return {"CANCELLED"}

        mesh_objects = [
            obj for obj in original_selection if obj.type == "MESH"
        ]  # type: list[Object] # type: ignore
        if not mesh_objects:
            self.report({"INFO"}, "No mesh objects selected")
            return {"CANCELLED"}

        # 选择所有 MESH 对象
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)  # 选择 MESH 对象

        bpy.ops.object.mode_set(mode="EDIT")
        # 全选所有面
        bpy.ops.mesh.select_all(action="SELECT")
        # 调整法线一致性
        bpy.ops.mesh.normals_make_consistent(inside=True)
        bpy.ops.object.mode_set(mode="OBJECT")

        # 恢复选择
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selection:
            obj.select_set(True)

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
    bl_options = {"UNDO"}

    is_button: BoolProperty(default=False)  # type: ignore
    # 自动分离

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade

    def execute(self, context: Context):
        if self.is_button:
            selected_sectors = data.SELECTED_SECTORS
        else:
            selected_sectors = ag_utils.get_selected_sectors()[0]
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        if len(selected_sectors) < 2:
            self.report({"WARNING"}, "Select at least two sectors")
            return {"CANCELLED"}

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

        # TODO: 自动分离 scene_data.operator_props.sec_connect_sep_convex

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

    def connect(self, sec1: Object, sec2: Object):
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

    is_button: BoolProperty(default=False)  # type: ignore
    from_connect: BoolProperty(default=False)  # type: ignore
    undo: BoolProperty(default=True)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade

    def separate_simple(self, context: Context, sec: Object):
        """分割（简单）"""
        sec_data = sec.amagate_data.get_sector_data()

    def pre_separate_normal(self, context: Context, sec: Object):
        """预分割（普通）"""
        sec_data = sec.amagate_data.get_sector_data()
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        matrix_world = sec.matrix_world

        separate = ()  # 分割数据
        is_complex = False
        # 内部顶点序号
        verts_inter_idx = sec_data["ConcaveData"]["verts_index"]

        sec_bm = bmesh.new()
        sec_bm.from_mesh(mesh)
        sec_bm.verts.ensure_lookup_table()
        sec_bm.faces.ensure_lookup_table()

        # START: 获取刀具面索引
        # 内部顶点
        verts_interior = set(
            sec_bm.verts[i] for i in verts_inter_idx
        )  # type: set[bmesh.types.BMVert]
        # 刀具面索引
        faces_index = set()  # type: set[int]
        # 内部顶点围成的边
        edges = []  # type: list[bmesh.types.BMEdge]
        for e in sec_bm.edges:
            s = set(e.verts)
            if s.issubset(verts_interior):
                edges.append(e)
        # 边连接的面
        for e in edges:
            faces_index.update(f.index for f in e.link_faces)

        # 拆分凹面（平面）
        bpy.ops.object.select_all(action="DESELECT")  # 取消选择
        context.view_layer.objects.active = sec  # 设置活动物体
        bpy.ops.object.mode_set(mode="EDIT")  # 进入编辑模式
        bpy.ops.mesh.select_all(action="DESELECT")  # 取消选择网格
        bm_tmp = bmesh.from_edit_mesh(mesh)
        bm_tmp.faces.ensure_lookup_table()
        for i in faces_index:
            bm_tmp.faces[i].select_set(True)  # 选择面
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        face_num = len(bm_tmp.faces)
        bpy.ops.mesh.vert_connect_concave()  # 拆分凹面
        if len(bm_tmp.faces) != face_num:
            faces_index = set(f.index for f in bm_tmp.faces if f.select)
            # 更新sec_bm数据
            sec_bm.free()
            sec_bm = bm_tmp.copy()
            sec_bm.verts.ensure_lookup_table()
            sec_bm.faces.ensure_lookup_table()
            # 内部顶点
            verts_interior = set(sec_bm.verts[i] for i in verts_inter_idx)
        bpy.ops.object.mode_set(mode="OBJECT")
        # END: 获取刀具面索引

        # 外部顶点
        verts_exterior = set(i for i in sec_bm.verts if i.index not in verts_inter_idx)

        # 判断与内部点相连的外部点
        verts_ext_conn = []  # type: list[bmesh.types.BMVert]
        visited_edges = set()
        for v in verts_interior:
            vert_conn = None  # type: typing.Optional[bmesh.types.BMVert]
            for e in v.link_edges:
                if e in visited_edges:
                    continue
                visited_edges.add(e)

                v2 = e.other_vert(v)
                # 如果连接了外部点
                if v2 in verts_exterior:
                    # 如果连接的外部点大于1个，则跳过
                    if vert_conn is not None:
                        break
                    vert_conn = v2
            # 如果连接的外部点 <= 1个
            else:
                # 如果存在连接的外部点，且该点不在现有列表中
                if (vert_conn is not None) and (vert_conn not in verts_ext_conn):
                    verts_ext_conn.append(vert_conn)

        # 取投影法线
        proj_normal = geometry.normal([verts_ext_conn[i].co for i in range(3)])
        # 检查所有点是否都在同一平面
        base_point = verts_ext_conn[0].co
        for v in verts_ext_conn[3:]:
            co = v.co
            distance = abs(proj_normal.dot(co - base_point))  # 点到平面的距离
            if distance > ag_utils.epsilon:
                # 超过容差范围的点，不共面，复杂凹多面体
                # print(f"complex: {sec.name}")
                sec_bm.free()
                sec_data["ConcaveData"]["concave_type"] = ag_utils.CONCAVE_T_COMPLEX
                is_complex = True
                return {"is_complex": is_complex, "separate": separate}

        # 纠正投影法线
        v1 = verts_ext_conn[0]
        for e in v1.link_edges:
            v2 = e.other_vert(v1)
            dot_n = proj_normal.dot(v2.co - v1.co)
            # 如果不是垂直的
            if abs(dot_n) > ag_utils.epsilon:
                if dot_n > 0:
                    proj_normal = -proj_normal
                break

        # 投影法线是否重新计算
        is_recalc_proj_normal = False
        for i in faces_index:
            f = sec_bm.faces[i]
            normal1 = f.normal
            # 如果是同方向的
            if normal1.dot(proj_normal) > ag_utils.epsilon:
                # 相连面
                faces_conn = set(f for e in f.edges for f in e.link_faces)
                for f2 in faces_conn:
                    normal2 = normal1.cross(f2.normal)  # type: Vector
                    normal2.normalize()
                    dot_n = normal2.dot(proj_normal)
                    # 如果与投影法线垂直，则为不合法的法向，跳过
                    if abs(dot_n) < ag_utils.epsilon:
                        continue
                    # 纠正到与投影法线同方向
                    if dot_n < 0:
                        normal2 = -normal2
                    proj_normal = normal2
                    is_recalc_proj_normal = True
                    break
            if is_recalc_proj_normal:
                break
        # 如果重新计算了投影法线，判断该法线是否合法
        if is_recalc_proj_normal:
            for i in faces_index:
                f = sec_bm.faces[i]
                # 如果是同方向的，不合法，复杂凹多面体
                if f.normal.dot(proj_normal) > ag_utils.epsilon:
                    sec_bm.free()
                    sec_data["ConcaveData"]["concave_type"] = ag_utils.CONCAVE_T_COMPLEX
                    is_complex = True
                    return {"is_complex": is_complex, "separate": separate}

        # 投影法线应用物体变换
        proj_normal_prime = (matrix_world.to_quaternion() @ proj_normal).normalized()
        proj_normal_prime = Vector(proj_normal_prime.to_tuple(4))
        # print(f"proj_normal: {proj_normal}")

        # 与刀具面共边的外部面
        faces_exterior_idx = []  # type: list[int]
        knife_edges = set(e for i in faces_index for e in sec_bm.faces[i].edges)
        faces_exterior = set(f for f in sec_bm.faces if f.index not in faces_index)
        for f in faces_exterior:
            for e in f.edges:
                if e in knife_edges:
                    faces_exterior_idx.append(f.index)
                    break

        # 排除垂直面
        faces_index_prime = faces_index.copy()
        # 创建刀具BMesh
        knife_bm = bmesh.new()
        exist_verts = {}
        for face_idx in faces_index:
            f = sec_bm.faces[face_idx]  # type: bmesh.types.BMFace
            # 跳过垂直面
            if abs(f.normal.dot(proj_normal)) < ag_utils.epsilon:
                faces_index_prime.remove(face_idx)
                continue
            verts = []
            # 重复顶点
            is_dup_vert = False
            for i in f.verts:
                co = Vector((matrix_world @ i.co).to_tuple(4))
                dist = (-co).dot(proj_normal_prime)
                co = proj_normal_prime * dist + co
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
                faces_index_prime.remove(face_idx)
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
        bm_tmp = bmesh.from_edit_mesh(knife_obj.data)  # type: ignore
        face_num = len(bm_tmp.faces)
        with contextlib.redirect_stdout(StringIO()):
            # 交集(切割)
            bpy.ops.mesh.intersect(mode="SELECT")
        # 如果存在交集
        if len(bm_tmp.faces) != face_num:
            print(f"{knife_obj.name} has intersect")
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.data.meshes.remove(knife_mesh)
            is_complex = True
        # 不存在交集
        else:
            bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
            bpy.ops.mesh.edge_split(type="EDGE")  # 按边拆分
            bpy.ops.mesh.separate(type="LOOSE")  # 分离松散块
            bpy.ops.object.mode_set(mode="OBJECT")
            context.active_object.select_set(True)  # 刀具本体也需选择

            # 添加到投影切割列表
            knife_project = context.selected_objects
            separate = (
                sec,
                faces_index,
                faces_index_prime,
                faces_exterior_idx,
                knife_project,
                proj_normal_prime,
            )

        sec_bm.free()
        knife_bm.free()

        return {"is_complex": is_complex, "separate": separate}

    def execute(self, context: Context):
        global separate_data
        if self.is_button:
            selected_sectors = data.SELECTED_SECTORS
        else:
            selected_sectors = ag_utils.get_selected_sectors()[0]
        self.is_button = False  # 重置，因为从F3执行时会使用缓存值

        if len(selected_sectors) == 0:
            self.report({"WARNING"}, "Select at least one sector")
            return {"CANCELLED"}

        #
        if context.mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
            data.geometry_modify_post(selected_sectors)

        # knife_project = []
        separate_list = []
        complex_list = []
        has_separate_simple = False
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            # 跳过凸多面体
            if sec_data.is_convex:
                continue

            concave_type = sec_data["ConcaveData"]["concave_type"]
            # # 跳过复杂凹多面体
            if concave_type == ag_utils.CONCAVE_T_COMPLEX:
                complex_list.append(sec)
                continue

            # 简单凹面的情况
            if concave_type == ag_utils.CONCAVE_T_SIMPLE:
                self.separate_simple(context, sec)
                has_separate_simple = True
            # 其它情况
            else:
                ret = self.pre_separate_normal(context, sec)
                if ret["is_complex"]:
                    complex_list.append(sec)
                else:
                    separate_list.append(ret["separate"])

                # knife_project.extend(ret["knife_project"])
                # separate_list.extend(ret["separate_list"])
                # complex_list.extend(ret["complex_list"])
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
            separate_data = {
                "index": 0,
                "separate_list": separate_list,
                "area": area,
                "region": region,
                "view_rotation": region.data.view_rotation.copy(),
                "view_perspective": region.data.view_perspective,
                "shading_type": area.spaces[0].shading.type,  # type: ignore
                "undo": self.undo,
            }
            area.spaces[0].shading.type = "WIREFRAME"  # type: ignore
            pre_knife_project()
            return {"FINISHED"}

        #
        ret = {"FINISHED"}
        if not has_separate_simple:
            ret = {"CANCELLED"}
            # 没有切割简单/普通凹面，且不存在复杂凹面
            if not complex_list:
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
