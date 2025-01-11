# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import math
from typing import Any, TYPE_CHECKING

import bpy
import bmesh
from mathutils import *  # type: ignore

from .. import data

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene

############################
epsilon = 1e-5
epsilon2 = 1 - epsilon


# 预设颜色
class DefColor:
    white = (1, 1, 1, 1)
    black = (0, 0, 0, 1)
    red = (0.8, 0, 0, 1)
    green = (0, 0.8, 0, 1)
    blue = (0, 0, 0.8, 1)
    yellow = (0.8, 0.8, 0, 1)
    cyan = (0, 0.8, 0.8, 1)
    magenta = (0.8, 0, 0.8, 1)
    # 无焦点
    nofocus = (0.4, 0.4, 0.4, 1)


############################


# 获取同一直线的边
def get_edges_along_line(edge: bmesh.types.BMEdge, limit_face: bmesh.types.BMFace = None, vert: bmesh.types.BMVert = None):  # type: ignore
    """获取同一直线的边"""
    edges_index = []
    if not vert:
        edges_index.append(edge.index)
        for v in edge.verts:
            ret = get_edges_along_line(edge, limit_face, v)
            edges_index.extend(ret)
    else:
        dir1 = (edge.other_vert(vert).co - vert.co).normalized()  # type: Vector
        for e in vert.link_edges:
            if e == edge:
                continue
            if limit_face and limit_face not in e.link_faces:
                continue
            vert2 = e.other_vert(vert)
            dir2 = (vert.co - vert2.co).normalized()  # type: Vector
            # 判断是否在同一直线
            if dir1.dot(dir2) > epsilon2:
                edges_index.append(e.index)
                ret = get_edges_along_line(e, limit_face, vert2)
                edges_index.extend(ret)

    return edges_index


# 设置视图旋转
def set_view_rotation(region: bpy.types.Region, vector: Vector):
    """设置视图旋转"""
    rv3d = region.data  # type: bpy.types.RegionView3D
    init_dir = Vector((0, 0, -1))  # 初始方向
    # 计算旋转角度
    angle = init_dir.angle(vector)
    # 计算旋转轴
    axis = init_dir.cross(vector).normalized()
    # 如果旋转轴是0
    if axis.length == 0:
        axis = Vector((1, 0, 0))
    # 旋转视图
    rv3d.view_rotation = Quaternion(axis, angle)  # type: ignore


# 获得选中的扇区
def get_selected_sectors() -> tuple[list[Object], Object]:
    """获得选中的扇区"""
    context = bpy.context
    selected_objects = context.selected_objects  # type: list[Object] # type: ignore
    active_object = context.active_object  # type: Object # type: ignore
    if active_object and not active_object.select_get():
        selected_objects.append(active_object)
    if not selected_objects:
        return [], None  # type: ignore

    selected_sectors = [obj for obj in selected_objects if obj.amagate_data.is_sector]
    if selected_sectors:
        active_sector = (
            active_object if active_object in selected_sectors else selected_sectors[0]
        )
    else:
        active_sector = None

    return selected_sectors, active_sector  # type: ignore


# 判断物体是否为凸多面体
def is_convex(obj: Object):
    """判断物体是否为凸多面体"""
    sec_data = obj.amagate_data.get_sector_data()
    sec_bm = bmesh.new()
    sec_bm.from_mesh(obj.data)  # type: ignore
    bm = sec_bm.copy()

    # 融并内插面
    # bmesh.ops.dissolve_limit(bm, angle_limit=0.001, verts=bm.verts, edges=bm.edges)
    BMFaces = []
    for face1 in bm.faces:
        if next((1 for lst in BMFaces if face1 in lst), 0):
            continue

        Faces = [face1]
        normal = face1.normal
        D = -normal.dot(face1.verts[0].co)
        for face2 in bm.faces:
            if next((1 for lst in BMFaces if face2 in lst), 0):
                continue

            # 判断法向是否一致
            if face1 != face2 and abs(face2.normal.dot(normal)) > epsilon2:
                # 判断是否在同一平面
                if abs(normal.dot(face2.verts[0].co) + D) < epsilon:
                    Faces.append(face2)
        if len(Faces) > 1:
            BMFaces.append(Faces)
    if BMFaces:
        for Faces in BMFaces:
            bmesh.ops.dissolve_faces(bm, faces=Faces, use_verts=True)

    # 重置面法向
    # bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # type: ignore
    # 如果存在凹边，返回0，否则返回1
    # ret = next((0 for i in bm.edges if not i.is_convex), 1)
    # print(f"is_convex: {ret}")

    # 创建凸壳
    convex_hull = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=True)  # type: ignore
    # verts_interior = [v.index for v in convex_hull["geom_interior"]]  # type: list[int]
    # 如果没有未参与凸壳计算的顶点，则为凸多面体
    convex = convex_hull["geom_interior"] == []
    # print(convex_hull['geom'])
    # print("geom_interior", verts_interior)
    # print("geom_unused", [i.index for i in convex_hull["geom_unused"]])
    # print("geom_holes", [i.index for i in convex_hull["geom_holes"]])

    if not convex:
        # 生成空洞BMesh
        hole_bm = bmesh.new()
        # 创建一个字典来存储新顶点的引用
        vertex_map = {}
        # 将凸包的顶点添加到新的 BMesh 对象
        for geo in convex_hull["geom"]:
            if isinstance(geo, bmesh.types.BMVert):  # 顶点
                # 创建新的顶点并保存在字典中
                vertex = hole_bm.verts.new(geo.co)
                vertex_map[geo] = vertex

        # 处理边和面
        for geo in convex_hull["geom"]:
            if isinstance(geo, bmesh.types.BMEdge):  # 边
                # 使用 vertex_map 来获取对应的顶点
                v1, v2 = geo.verts
                hole_bm.edges.new([vertex_map[v1], vertex_map[v2]])

            elif isinstance(geo, bmesh.types.BMFace):  # 面
                # 使用 vertex_map 来获取对应的顶点
                verts = [vertex_map[v] for v in geo.verts]
                hole_bm.faces.new(verts)

        hole_bm.normal_update()
        # 判断唯一法向
        hole_bm.faces.ensure_lookup_table()
        normal = hole_bm.faces[0].normal
        is_normal_unique = True
        for face in hole_bm.faces:
            if face.index != 0 and face.normal.dot(normal) < epsilon2:
                is_normal_unique = False
                break
        print(f"is_normal_unique: {is_normal_unique}")
        if is_normal_unique:
            # 投影方向
            projection_dir = hole_bm.faces[0].normal
            # 刀具面索引
            geom_holes_idx = set(i.index for i in convex_hull["geom_holes"])
            faces = set(range(len(sec_bm.faces))) - geom_holes_idx
            # print(f"faces: {faces}")
            sec_data["ConcaveData"] = {
                "faces": list(faces),
                "proj_normal": projection_dir,
            }
        else:
            # 复杂凹多面体
            sec_data["ConcaveData"] = {"faces": [], "proj_normal": None}

        hole_bm.free()
        """
            sec_bm.verts.ensure_lookup_table()
            visited_verts = set()
            stack = [verts_interior[0]]
            while stack:
                v_index = stack.pop()

                # 标记为已访问
                visited_verts.add(v_index)

                # 遍历相邻的顶点
                for e in sec_bm.verts[v_index].link_edges:
                    for v in e.verts:
                        v_index = v.index
                        if v_index in verts_interior and v_index not in visited_verts:
                            stack.append(v_index)

            if len(visited_verts) != len(verts_interior):
                # 复杂凹多面体
                ...
        """

    # bm.faces.ensure_lookup_table()
    # geom=[], geom_interior=[], geom_unused=[], geom_holes=[]
    sec_bm.free()
    bm.free()
    return convex


############################
############################ For Separate Convex
############################

separate_data = {}


def pre_knife_project():
    """投影切割预处理"""
    context = bpy.context
    knife_project = separate_data[
        "knife_project"
    ]  # type: list[tuple[Object, list[Object], Vector]]
    region = separate_data["region"]  # type: bpy.types.Region
    sec, knifes, proj_normal_prime = knife_project.pop()

    bpy.ops.object.select_all(action="DESELECT")  # 取消选择
    context.view_layer.objects.active = sec  # 设置活动物体
    bpy.ops.object.mode_set(mode="EDIT")
    for knife in knifes:
        knife.select_set(True)
    set_view_rotation(region, proj_normal_prime)
    region.data.view_perspective = "ORTHO"

    separate_data["active_knifes"] = knifes
    bpy.app.timers.register(knife_project_timer, first_interval=0.05)


def knife_project_timer():
    """投影切割定时器"""
    context = bpy.context
    with context.temp_override(
        area=separate_data["area"],
        region=separate_data["region"],
    ):
        bpy.ops.mesh.knife_project()
        bpy.ops.object.mode_set(mode="OBJECT")
        for obj in separate_data["active_knifes"]:
            bpy.data.meshes.remove(obj.data)  # type: ignore

    knife_project = separate_data[
        "knife_project"
    ]  # type: list[tuple[Object, list[int], list[Object], Vector]]
    if knife_project:
        pre_knife_project()
    else:
        knife_project_done()


def knife_project_done():
    """投影切割完成"""
    context = bpy.context

    #
    separate_list = separate_data[
        "separate_list"
    ]  # type: list[tuple[Object, list[int], Vector]]
    for sec, faces_index, proj_normal_prime in separate_list:
        matrix_world = sec.matrix_world
        proj_normal_prime = matrix_world.inverted() @ proj_normal_prime
        proj_normal_prime = Vector(proj_normal_prime.to_tuple(4))
        sec_bm = bmesh.new()
        sec_bm.from_mesh(sec.data)  # type: ignore
        sec_bm.faces.ensure_lookup_table()
        sec_bm.edges.ensure_lookup_table()
        #
        for face_idx in faces_index:
            f = sec_bm.faces[face_idx]  # type: bmesh.types.BMFace
            faces = [f]
            edges = []
            edges_set = set()
            for e in f.edges:
                if e.index in edges_set:
                    continue
                ret = get_edges_along_line(e, limit_face=f)
                edges.append(ret)
                edges_set.update(set(ret))
            #
            for edges_index in edges:
                verts = set(v for i in edges_index for v in sec_bm.edges[i].verts)
                for v1 in verts.copy():
                    dir1 = (v1.co - proj_normal_prime).normalized()
                    for v2 in sec_bm.verts:
                        if v2 == v1:
                            continue
                        dir2 = (v2.co - v1.co).normalized()
                        # 如果顶点2在顶点1的投影法向上，添加到列表
                        if dir1.dot(dir2) > epsilon2:
                            verts.add(v2)
                # 判断verts中是否存在面
                for f2 in sec_bm.faces:
                    if f2 == f:
                        continue
                    if verts.issubset(set(f2.verts)):
                        break
                else:
                    f2 = sec_bm.faces.new(verts)
                faces.append(f2)
            # TODO
            # sep_bm = bmesh.new()
            # bmesh.ops.duplicate(sec_bm, geom=faces, dest=sep_bm)
            # sep_mesh = bpy.data.meshes.new(f"AG.{sec.name}_sep")
            # sep_bm.to_mesh(sep_mesh)
            # sep_obj = bpy.data.objects.new(f"AG.{sec.name}_sep", sep_mesh)
            # data.link2coll(sep_obj, context.scene.collection)
        sec_bm.to_mesh(sec.data)  # type: ignore

    area = separate_data["area"]  # type: bpy.types.Area
    region = separate_data["region"]  # type: bpy.types.Region
    region.data.view_rotation = separate_data["view_rotation"]
    region.data.view_perspective = separate_data["view_perspective"]
    area.spaces[0].shading.type = separate_data["shading_type"]  # type: ignore

    if separate_data["undo"]:
        bpy.ops.ed.undo_push(message="Separate Convex")


############################
############################
############################
