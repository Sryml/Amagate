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

from . import data

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


# 凹面类型: 无，简单，普通，复杂
CONCAVE_T_NONE = 0
CONCAVE_T_SIMPLE = 1
CONCAVE_T_NORMAL = 2
CONCAVE_T_COMPLEX = 3
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
    if not selected_objects:
        return [], None  # type: ignore
    # if active_object and not active_object.select_get():
    #     selected_objects.append(active_object)

    selected_sectors = [obj for obj in selected_objects if obj.amagate_data.is_sector]
    if selected_sectors:
        active_sector = (
            active_object if active_object in selected_sectors else selected_sectors[0]
        )
    else:
        active_sector = None

    return selected_sectors, active_sector  # type: ignore


# 射线法，判断点是否在多边形内
def is_point_in_polygon(pt, poly):
    x, y = pt
    n = len(poly)
    inside = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]

        # 检查点是否在线段上
        if is_point_on_segment(pt, (x1, y1), (x2, y2)):
            # print(f"is_point_on_segment: {pt} in {(x1, y1), (x2, y2)}")
            return True

        if (y1 > y) != (y2 > y):  # 检查 y 是否在边的范围内
            t = (y - y1) / (y2 - y1)
            intersect_x = x1 + t * (x2 - x1)
            if intersect_x > x:  # 检查交点是否在射线右侧
                inside = not inside
    return inside  # 奇数为内部，偶数为外部


# 判断点是否在线段上 (不考虑端点)
def is_point_on_segment(pt, p1, p2):
    """判断点 pt 是否在线段 p1-p2 上"""
    x, y = pt
    x1, y1 = p1
    x2, y2 = p2
    # 检查点是否在边的范围内，且向量点积为 0（共线）
    v1 = Vector((x2 - x1, y2 - y1))
    v2 = Vector((x - x1, y - y1))
    return v1.normalized().dot(v2.normalized()) > epsilon2 and v2.length < v1.length


# 判断物体是否为凸多面体
def is_convex(obj: Object):
    """判断物体是否为凸多面体"""
    sec_data = obj.amagate_data.get_sector_data()
    sec_bm = bmesh.new()
    sec_bm.from_mesh(obj.data)  # type: ignore
    bm = sec_bm.copy()

    # 顶点映射
    vert_map = {v.co.to_tuple(4): i for i, v in enumerate(sec_bm.verts)}

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

            # 判断法向是否在同一直线
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
    geom_interior = convex_hull["geom_interior"]  # type: list[bmesh.types.BMVert]
    # 如果没有未参与凸壳计算的顶点，则为凸多面体
    convex = geom_interior == []
    # print(convex_hull['geom'])
    # print("geom_interior", verts_interior)
    # print("geom_unused", [i.index for i in convex_hull["geom_unused"]])
    # print("geom_holes", [i.index for i in convex_hull["geom_holes"]])
    # 如果不是凸多面体
    if not convex:
        # 判断内部顶点是否共面
        is_interior_coplanar = True
        if len(geom_interior) > 2:
            pt = geom_interior[0].co
            dir1 = geom_interior[1].co - pt
            normal = None  # type: Vector # type: ignore
            for v in geom_interior[2:]:
                dir2 = v.co - pt
                normal2 = dir1.cross(dir2).normalized()
                # 长度为0，跳过共线顶点
                if normal2.length == 0:
                    continue
                # 初次赋值
                if normal is None:
                    normal = normal2
                    continue
                # 如果法向不在同一直线
                if abs(normal.dot(normal2)) < epsilon2:
                    is_interior_coplanar = False
                    break
        ########
        verts_index = []
        # proj_normal = None
        concave_type = CONCAVE_T_NONE

        def get_vert_index():
            vert_index = []
            for i in geom_interior:
                idx = vert_map.get(i.co.to_tuple(4), None)
                if idx is None:
                    print(f"error: {i.co.to_tuple(4)} not in vert_map")
                    vert_index = []
                    break
                vert_index.append(idx)
            return vert_index

        ########
        verts_index = get_vert_index()
        # 如果找不到对应顶点，归为复杂凹多面体
        if not verts_index:
            concave_type = CONCAVE_T_COMPLEX
        # 内部顶点共面的情况
        elif is_interior_coplanar:
            concave_type = CONCAVE_T_SIMPLE
        # 内部顶点不共面的情况
        # else:
        #     # 判断唯一法向
        #     normal = None  # type: Vector # type: ignore
        #     for geo in convex_hull["geom"]:
        #         if isinstance(geo, bmesh.types.BMFace):
        #             if normal is None:
        #                 normal = geo.normal
        #             else:
        #                 # 法向不唯一，复杂凹多面体
        #                 if abs(geo.normal.dot(normal)) < epsilon2:
        #                     concave_type = CONCAVE_T_COMPLEX
        #                     break
        #     # 如果不是复杂凹面
        #     if concave_type != CONCAVE_T_COMPLEX:
        #         vert_index = get_vert_index()
        #         # 如果找不到对应顶点，归为复杂凹多面体
        #         if not vert_index:
        #             concave_type = CONCAVE_T_COMPLEX
        #         else:
        #             proj_normal = normal
        #             concave_type = CONCAVE_T_NORMAL
        #
        sec_data["ConcaveData"] = {
            "verts_index": verts_index,
            # "proj_normal": proj_normal,
            "concave_type": concave_type,
        }

        # 生成空洞BMesh
        # hole_bm = bmesh.new()
        # # 创建一个字典来存储新顶点的引用
        # vertex_map = {}
        # # 将凸包的顶点添加到新的 BMesh 对象
        # for geo in convex_hull["geom"]:
        #     if isinstance(geo, bmesh.types.BMVert):  # 顶点
        #         # 创建新的顶点并保存在字典中
        #         vertex = hole_bm.verts.new(geo.co)
        #         vertex_map[geo] = vertex

        # # 创建新的面
        # for geo in convex_hull["geom"]:
        #     if isinstance(geo, bmesh.types.BMFace):  # 面
        #         # 使用 vertex_map 来获取对应的顶点
        #         verts = [vertex_map[v] for v in geo.verts]
        #         hole_bm.faces.new(verts)

        # hole_bm.normal_update()
        # # 判断唯一法向
        # hole_bm.faces.ensure_lookup_table()
        # normal = hole_bm.faces[0].normal
        # is_normal_unique = True
        # for face in hole_bm.faces:
        #     if face.index != 0 and face.normal.dot(normal) < epsilon2:

        #         is_normal_unique = False
        #         break
        # print(f"is_normal_unique: {is_normal_unique}")
        # if is_normal_unique:
        #     # 投影方向
        #     projection_dir = hole_bm.faces[0].normal
        #     # 刀具面索引
        #     geom_holes_idx = set(i.index for i in convex_hull["geom_holes"])
        #     faces = set(range(len(sec_bm.faces))) - geom_holes_idx
        #     # print(f"faces: {faces}")
        #     sec_data["ConcaveData"] = {
        #         "verts": [],
        #         "faces": list(faces),
        #         "geom_holes": [i.index for i in convex_hull["geom_holes"]],
        #         "proj_normal": projection_dir,
        #         "is_complex": False,
        #     }
        # else:
        #     # 复杂凹多面体
        #     sec_data["ConcaveData"] = {"verts": [], "faces": [], "geom_holes": [], "proj_normal": None, "is_complex": True}

        # hole_bm.free()
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

    # geom=[], geom_interior=[], geom_unused=[], geom_holes=[]
    sec_bm.free()
    bm.free()
    return convex


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

    bpy.ops.object.select_all(action="DESELECT")  # 取消选择
    context.view_layer.objects.active = sec  # 设置活动物体
    bpy.ops.object.mode_set(mode="EDIT")
    for knife in knife_project:
        knife.select_set(True)
    set_view_rotation(region, proj_normal_prime)
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
                    if is_point_in_polygon(proj_point_2d, polygon):
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
        #
        bpy.ops.object.mode_set(mode="OBJECT")
        # 删除空网格
        if main_sec.data.vertices == 0:  # type: ignore
            bpy.data.meshes.remove(mesh)
        selected_objects = (
            context.selected_objects.copy()
        )  # type: list[Object] # type: ignore
        # 修正扇区属性
        for sec in selected_objects.copy():
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            # 按距离合并顶点
            bpy.ops.object.select_all(action="DESELECT")  # 取消选择
            context.view_layer.objects.active = sec  # 设置活动物体
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(type="VERT")  # 选择顶点模式
            bpy.ops.mesh.select_all(action="SELECT")  # 全选
            bpy.ops.mesh.remove_doubles(threshold=0.0001)  # 合并顶点
            bpy.ops.object.mode_set(mode="OBJECT")
            # 删除平面物体
            normal = mesh.polygons[0].normal
            for f in mesh.polygons[1:]:
                if abs(f.normal.dot(normal)) < epsilon2:
                    break
            else:
                selected_objects.remove(sec)
                bpy.data.meshes.remove(mesh)
                continue
            #
            sec_data = sec.amagate_data.get_sector_data()

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
