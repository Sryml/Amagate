# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

#
import struct
import math
import os
import time
import contextlib

from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

#
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

#
from . import data, L3D_data, ag_utils
from . import L3D_operator as OP_L3D
from . import sector_operator as OP_SECTOR

#
if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection

############################
logger = data.logger

epsilon: float = ag_utils.epsilon
epsilon2: float = ag_utils.epsilon2
unpack = ag_utils.unpack
############################


# 验证bw文件完整性
def verify_bw(bw_file):
    pass


# 分割洞
def hole_split(sec_bm, inner_face, tangent_data, sector_id):
    geom = list(inner_face.verts) + list(inner_face.edges) + [inner_face]
    while tangent_data:
        plane_no, plane_co = tangent_data.pop()
        result = bmesh.ops.bisect_plane(
            sec_bm,
            geom=geom,  # type: ignore
            dist=1e-4,
            plane_no=plane_no,
            plane_co=plane_co,
            clear_inner=False,
            clear_outer=False,
        )
        # 获取内部面
        cut_verts = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMVert)]
        cut_edges = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
        if not cut_edges:
            continue
        edge = cut_edges[0]
        if len(edge.link_faces) == 1:
            #
            # bm_mesh = bpy.data.meshes.new(f"AG.split")
            # sec_bm.to_mesh(bm_mesh)
            # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
            # data.link2coll(bm_obj, bpy.context.scene.collection)
            # logger.debug(f"bisect_plane: {plane_no}, {plane_co}")
            #
            return None
        if edge.link_faces[0].normal.dot(edge.link_faces[1].normal) < epsilon2:
            continue

        face1, face2 = edge.link_faces
        line_p1 = edge.verts[0].co.copy()
        line_p2 = edge.verts[1].co.copy()
        co = next(
            v.co.copy()
            for v in face1.verts
            if v not in cut_verts
            and (geometry.intersect_point_line(v.co, line_p1, line_p2)[0] - v.co).length
            > 1e-4
        )
        pt, pct = geometry.intersect_point_line(co, line_p1, line_p2)
        dir = (co - pt).normalized()
        if plane_no.dot(dir) < 0:
            inner_face = face1
        else:
            inner_face = face2
        geom = list(inner_face.verts) + list(inner_face.edges) + [inner_face]
    return inner_face


# 平展面分割
def flat_split(sec_bm, face, cut_data, layers, sector_id):
    stack = [face]
    while stack:
        inner_face = stack.pop()
        while cut_data:
            tuple_data = cut_data.pop()
            if tuple_data[0] == "cut":
                _, plane_no, plane_co, tex_data = tuple_data
                geom = list(inner_face.verts) + list(inner_face.edges) + [inner_face]
                result = bmesh.ops.bisect_plane(
                    sec_bm,
                    geom=geom,  # type: ignore
                    dist=1e-4,
                    plane_no=plane_no,
                    plane_co=plane_co,
                    clear_inner=False,
                    clear_outer=False,
                )
                # 获取内部面
                cut_verts = [
                    g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMVert)
                ]
                cut_edges = [
                    g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMEdge)
                ]
                #
                if not cut_edges:
                    continue
                #     bm_mesh = bpy.data.meshes.new(f"AG.split")
                #     sec_bm.to_mesh(bm_mesh)
                #     bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
                #     data.link2coll(bm_obj, bpy.context.scene.collection)
                #     logger.debug(f"bisect_plane: {plane_no}, {plane_co}")
                #
                edge = cut_edges[0]
                face1, face2 = edge.link_faces
                line_p1 = edge.verts[0].co.copy()
                line_p2 = edge.verts[1].co.copy()
                co = next(
                    v.co.copy()
                    for v in face1.verts
                    if v not in cut_verts
                    and (
                        geometry.intersect_point_line(v.co, line_p1, line_p2)[0] - v.co
                    ).length
                    > 1e-4
                )
                pt, pct = geometry.intersect_point_line(co, line_p1, line_p2)
                dir = (co - pt).normalized()
                if plane_no.dot(dir) < 0:
                    inner_face = face1
                    outer_face = face2
                else:
                    inner_face = face2
                    outer_face = face1
                stack.append(outer_face)
                # 如果有纹理数据
                if tex_data:
                    (
                        tex_type,
                        slot_index,
                        tex_id,
                        tex_xpos,
                        tex_ypos,
                        tex_angle,
                        tex_xzoom,
                        tex_yzoom,
                    ) = tex_data
                    inner_face.material_index = slot_index
                    inner_face[layers["flag"]] = L3D_data.FACE_FLAG[tex_type]
                    inner_face[layers["tex_id"]] = tex_id
                    inner_face[layers["tex_xpos"]] = tex_xpos
                    inner_face[layers["tex_ypos"]] = tex_ypos
                    inner_face[layers["tex_angle"]] = tex_angle
                    inner_face[layers["tex_xzoom"]] = tex_xzoom
                    inner_face[layers["tex_yzoom"]] = tex_yzoom
            elif tuple_data[0] == 8003:
                _, tangent_data, conn_sid = tuple_data
                # 有洞，需要分割
                if tangent_data:
                    inner_face = hole_split(sec_bm, inner_face, tangent_data, sector_id)
                    if inner_face is not None:
                        inner_face[layers["connected"]] = conn_sid
                # 有洞，无需分割
                elif conn_sid:
                    inner_face[layers["connected"]] = conn_sid
                # 无洞
                else:
                    pass
                #
                break


# 解包纹理数据
def unpack_texture(sec_mesh, sec_data, normal, f, global_texture_map):
    x_axis = Vector((1, 0, 0))
    y_axis = Vector((0, 1, 0))
    z_axis = Vector((0, 0, 1))
    #
    name_len = unpack("<I", f)[0]
    texture_name = unpack(f"{name_len}s", f)
    tex_vx = Vector(unpack("<ddd", f))
    tex_vx.yz = tex_vx.z, -tex_vx.y
    tex_vy = Vector(unpack("<ddd", f))
    tex_vy.yz = tex_vy.z, -tex_vy.y
    tex_xpos = unpack("<f", f)[0]
    tex_ypos = unpack("<f", f)[0]
    #
    tex_vx_len = tex_vx.length
    tex_vy_len = tex_vy.length
    if math.isnan(tex_vx_len):
        tex_vx_len = 0.05
        tex_vx = Vector((0, 0, 0))
        # logger.debug(f"isnan: {f.tell()}")
    if math.isnan(tex_vy_len):
        tex_vy_len = 0.05
        tex_vy = Vector((0, 0, 0))
        # logger.debug(f"isnan: {f.tell()}")

    dot = normal.dot(z_axis)
    # 计算纹理初始映射
    if dot > epsilon2:
        vx_map = -x_axis
        vy_map = y_axis
    elif dot < -epsilon2:
        vx_map = -x_axis
        vy_map = -y_axis
    else:
        vx_map = (normal.to_track_quat("-Y", "Z") @ x_axis).normalized()
        vy_map = (normal.to_track_quat("-Y", "Z") @ -z_axis).normalized()
    # 判断纹理类型
    if dot > epsilon:
        tex_type = "Floor"
    elif dot < -epsilon:
        tex_type = "Ceiling"
    else:
        tex_type = "Wall"

    tex_vx.normalize()
    tex_vy.normalize()
    #
    axis = tex_vx.cross(vx_map).normalized()  # type: Vector
    dot = tex_vx.dot(vx_map)
    dot = max(-1.0, min(1.0, dot))
    vx_angle = math.acos(dot)
    if axis.dot(normal) < 0:
        vx_angle = math.pi * 2 - vx_angle
    #
    axis = tex_vy.cross(vy_map).normalized()  # type: Vector
    dot = tex_vy.dot(vy_map)
    dot = max(-1.0, min(1.0, dot))
    vy_angle = math.acos(dot)
    if axis.dot(normal) < 0:
        vy_angle = math.pi * 2 - vy_angle
    # 计算缩放
    tex_xzoom = 1 / tex_vx_len
    tex_yzoom = 1 / tex_vy_len

    # 镜像纹理
    if abs(vx_angle - vy_angle) > 0.002:
        if vx_angle < vy_angle:
            tex_angle = vx_angle
            tex_yzoom = -tex_yzoom
        else:
            tex_angle = vy_angle
            tex_xzoom = -tex_xzoom
    else:
        tex_angle = vx_angle
    # 计算位置
    tex_xpos *= 0.001 * tex_xzoom
    tex_ypos *= 0.001 * tex_yzoom

    #
    img_data = global_texture_map.get(texture_name)
    if img_data is None:
        filepath = os.path.join(data.ADDON_PATH, "textures", "test.bmp")
        img_data = OP_L3D.OT_Texture_Add.load_image(filepath, texture_name)
        img_data.id_data.filepath = f"//textures/{texture_name}.bmp"
        global_texture_map[texture_name] = img_data
    tex_id = img_data.id
    slot_index = sec_mesh.materials.find(img_data.mat_obj.name)
    if slot_index == -1:
        sec_mesh.materials.append(img_data.mat_obj)
        slot_index = sec_mesh.materials.find(img_data.mat_obj.name)
    # 设置扇区预设纹理
    tex_prop = sec_data.textures.get(tex_type)
    if not tex_prop:
        tex_prop = sec_data.textures.add()
        tex_prop.target = "Sector"
        tex_prop.name = tex_type
        tex_prop["id"] = tex_id
        tex_prop["xpos"] = tex_xpos
        tex_prop["ypos"] = tex_ypos
        tex_prop["angle"] = tex_angle
        tex_prop["xzoom"] = tex_xzoom
        tex_prop["yzoom"] = tex_yzoom
    else:
        custom = next(
            (
                1
                for k, v in (
                    ("id", tex_id),
                    ("xpos", tex_xpos),
                    ("ypos", tex_ypos),
                    ("angle", tex_angle),
                    ("xzoom", tex_xzoom),
                    ("yzoom", tex_yzoom),
                )
                if round(tex_prop[k], 5) != round(v, 5)
            ),
            0,
        )
        if custom:
            tex_type = "Custom"
    ############################
    return (
        tex_type,
        slot_index,
        tex_id,
        tex_xpos,
        tex_ypos,
        tex_angle,
        tex_xzoom,
        tex_yzoom,
    )


# 顶点匹配连接
def connect_vm(sec_bm, link_face, sid, layers, conn_sec):
    # type: (bmesh.types.BMesh, bmesh.types.BMFace, int, dict, Object) -> bool
    conn_sec_data = conn_sec.amagate_data.get_sector_data()
    conn_sec_mesh = conn_sec.data  # type: bpy.types.Mesh # type: ignore
    conn_sec_bm = bmesh.new()
    conn_sec_bm.from_mesh(conn_sec_mesh)
    #
    verts_dict_1 = {v.co.to_tuple(3): v for v in sec_bm.verts}
    verts_dict_2 = {v.co.to_tuple(3): v for v in conn_sec_bm.verts}
    intersection = set(verts_dict_1.keys()).intersection(set(verts_dict_2.keys()))
    # if sid == 1446:
    #     logger.debug(f"intersection: {len(intersection)} {conn_sec_data.id}")
    #     if conn_sec_data.id == 1447:
    #         print(f"verts_dict_2: {len(verts_dict_2)}")
    if len(intersection) < 3:
        conn_sec_bm.free()
        return False
    #
    verts_set = [verts_dict_1[k] for k in intersection]
    center = sum([v.co for v in verts_set], Vector((0, 0, 0))) / len(verts_set)
    start_edge = next(
        (e for e in sec_bm.edges if set(e.verts).issubset(verts_set)), None
    )
    normal = link_face.normal.copy()
    v_a, v_b = start_edge.verts
    cross = (v_a.co - center).cross(v_b.co - center).normalized()
    if cross.dot(normal) < 0:
        v_a, v_b = v_b, v_a
    #
    convex_hull = []  # type: list[bmesh.types.BMVert]
    # 初始化凸包, v_a -> v_b
    convex_hull.append(v_a)
    convex_hull.append(v_b)
    remaining_verts = [v for v in verts_set if v not in convex_hull]

    while remaining_verts:
        edge_vec = (v_a.co - v_b.co).normalized()
        remaining_verts_len = len(remaining_verts)
        if remaining_verts_len == 1:
            next_vert = remaining_verts[0]
        else:
            point_lst = []
            for v in remaining_verts:
                # 计算向量 v_b -> v
                point_vec = v.co - v_b.co
                point_lst.append(
                    (v, point_vec.length, point_vec.normalized().dot(edge_vec))
                )

            point_lst.sort(key=lambda x: x[1])
            point_lst.sort(key=lambda x: x[2])
            next_vert = point_lst[0][0]

        # 更新当前边
        v_a, v_b = v_b, next_vert
        edge_vec = v_a.co - v_b.co
        length = edge_vec.length
        edge_vec.normalize()
        # 加入边内点
        inners = []
        for v in sec_bm.verts:
            if v in convex_hull or v in remaining_verts:
                continue
            vec = v.co - v_b.co
            length2 = vec.length
            if vec.normalized().dot(edge_vec) > epsilon2 and length2 < length:
                inners.append((v, length2))
        inners.sort(key=lambda x: x[1])
        inners = [v for v, _ in inners]
        convex_hull.extend(inners)
        # 更新凸包和剩余顶点
        convex_hull.append(next_vert)
        remaining_verts.remove(next_vert)
    #
    v_a, v_b = convex_hull[0], convex_hull[-1]
    edge_vec = v_a.co - v_b.co
    length = edge_vec.length
    edge_vec.normalize()
    # 加入边内点
    inners = []
    for v in sec_bm.verts:
        if v in convex_hull:
            continue
        vec = v.co - v_b.co
        length2 = vec.length
        dot = vec.normalized().dot(edge_vec)
        # if conn_sec_data.id == 2011:
        #     logger.debug(f"dot: {dot}")
        if dot > epsilon2 and length2 < length:
            inners.append((v, length2))
    inners.sort(key=lambda x: x[1])
    inners = [v for v, _ in inners]
    convex_hull.extend(inners)
    # if conn_sec_data.id == 2011:
    #     logger.debug(f"convex_hull: {[v.index for v in convex_hull]}")
    #
    face = sec_bm.faces.new(convex_hull)

    # 设置层属性
    for key in layers:
        if key == "connected":
            face[layers[key]] = conn_sec_data.id
        else:
            face[layers[key]] = link_face[layers[key]]
    #
    conn_sec_bm.free()
    return True


# 导入地图
def import_map(bw_file):
    scene = bpy.context.scene
    scene_data = scene.amagate_data
    # 全局数据索引
    global_vertex_count = 0
    global_vertex_map = {}  # {global_index: tuple(co)}
    global_atmo_map = {}
    global_texture_map = {}
    atmos_name_len = []
    #
    abnormal_sec = []
    fix_sec = []
    #
    v_factor = 0.86264  # 明度系数
    #
    x_axis = Vector((1, 0, 0))
    y_axis = Vector((0, 1, 0))
    z_axis = Vector((0, 0, 1))
    #
    context = bpy.context
    #
    wm = context.window_manager
    wm.progress_begin(0, 1)  # 初始化进度条
    with open(bw_file, "rb") as f:
        # 创建大气
        atmo_num = unpack("<I", f)[0]
        for i in range(atmo_num):
            name_len = unpack("<I", f)[0]
            name = unpack(f"{name_len}s", f)
            rgb = unpack("<BBB", f)
            a = unpack("<f", f)[0]
            if name.startswith("Metadata:"):
                continue

            item = OP_L3D.OT_Scene_Atmo_Add.add(context)
            item["_item_name"] = name
            item["_color"] = (*[i / 255 for i in rgb], a)
            global_atmo_map[name] = item.id
            atmos_name_len.append(name_len)

        # 全局顶点映射
        vertex_num = unpack("<I", f)[0]
        for i in range(vertex_num):
            vert = Vector(unpack("<ddd", f)) / 1000
            vert.yz = vert.z, -vert.y
            global_vertex_map[global_vertex_count] = vert
            global_vertex_count += 1

        # 扇区
        sec_total = unpack("<I", f)[0]
        scene_data["SectorManage"]["max_id"] = sec_total
        #
        start_time = time.time()
        bar_length = 20  # 进度条长度
        for sector_id in range(1, sec_total + 1):
            # 进度条
            i = sector_id
            percent = i / sec_total
            wm.progress_update(percent)
            filled = int(bar_length * percent)
            bar = ("█" * filled).ljust(bar_length, "-")
            print(
                f"\rSector Importing: |{bar}| {percent*100:.1f}% | {i} of {sec_total}",
                end="",
                flush=True,
            )
            #
            sec_mesh = bpy.data.meshes.new(f"Sector{sector_id}")
            sec = bpy.data.objects.new(
                f"Sector{sector_id}", sec_mesh
            )  # type: Object # type: ignore
            sec.amagate_data.set_sector_data()
            sec_data = sec.amagate_data.get_sector_data()
            sec_data.id = sector_id
            sec_vertex_map = {}

            #
            hole_split_list = []
            flat_split_list = []
            need_fix = False
            #
            sec_bm = bmesh.new()
            layers = {
                "connected": sec_bm.faces.layers.int.new("amagate_connected"),
                "flag": sec_bm.faces.layers.int.new("amagate_flag"),
                "flat_light": sec_bm.faces.layers.int.new("amagate_flat_light"),
                "tex_id": sec_bm.faces.layers.int.new("amagate_tex_id"),
                "tex_xpos": sec_bm.faces.layers.float.new("amagate_tex_xpos"),
                "tex_ypos": sec_bm.faces.layers.float.new("amagate_tex_ypos"),
                "tex_angle": sec_bm.faces.layers.float.new("amagate_tex_angle"),
                "tex_xzoom": sec_bm.faces.layers.float.new("amagate_tex_xzoom"),
                "tex_yzoom": sec_bm.faces.layers.float.new("amagate_tex_yzoom"),
            }
            # 大气
            name_len = unpack("<I", f)[0]
            atmo_name = unpack(f"{name_len}s", f)

            # 环境光
            rgb = unpack("<BBB", f)
            v = unpack("<f", f)[0]
            precision = unpack("<f", f)[0]
            ambient_color = Color(i / 255 for i in rgb)
            ambient_color.v = v / v_factor
            # 跳过 (0,0,0) unknown1 = unpack("<ddd", f)
            f.seek(24, 1)
            # 跳过12个字节 (b"\xCD"*8, 0)
            f.seek(12, 1)

            # 平面光
            rgb = unpack("<BBB", f)
            v = unpack("<f", f)[0]
            precision = unpack("<f", f)[0]
            # 跳过 (0,0,0) unknown1 = unpack("<ddd", f)
            f.seek(24, 1)
            # 跳过12个字节 (b"\xCD"*8, 0)
            f.seek(12, 1)
            flat_vector = Vector(unpack("<ddd", f))
            flat_vector.yz = flat_vector.z, -flat_vector.y
            flat_color = Color(i / 255 for i in rgb)
            flat_color.v = v / v_factor

            # 读取面
            face_num = unpack("<I", f)[0]
            for i in range(face_num):
                # 面类型
                face_type = unpack("<I", f)[0]
                # 法向
                normal = Vector(unpack("<ddd", f))
                normal.yz = normal.z, -normal.y
                # 距离
                distance = unpack("<d", f)[0]
                # if sector_id == 2048:
                #     logger.debug(f"normal: {normal}, face_type: {face_type}")
                # edges_dict = {}

                # 完全连接或天空面的情况
                if face_type in (7002, 7005):
                    vertex_num = unpack("<I", f)[0]
                    verts_list = []
                    for i in range(vertex_num):
                        verts_idx = unpack("<I", f)[0]
                        vert = sec_vertex_map.get(verts_idx)
                        if vert is None:
                            co1 = global_vertex_map[verts_idx]
                            # 是否在现有边内部
                            # for dir2, len2, vert, edge in edges_dict.values():
                            #     dir1 = (co1 - vert.co)
                            #     len1 = dir1.length
                            #     dir1.normalize()
                            #     dot = dir1.dot(dir2)
                            #     # 共线
                            #     if abs(dot) > epsilon2:
                            #         # 在边内
                            #         if len1 < len2 and dot > epsilon2:
                            #             new_edge, new_vert = bmesh.utils.edge_split(edge, vert, 0.5)
                            #             new_vert.co = co1
                            #             vert = new_vert
                            #             # bmesh.ops.subdivide_edges
                            #         # 在边外
                            #         else:
                            #             vert = sec_bm.verts.new(co1)
                            #         break
                            # 如果没有发生break，则创建新的顶点
                            vert = sec_bm.verts.new(co1)
                            sec_vertex_map[verts_idx] = vert
                        #
                        verts_list.append(vert)
                    face = sec_bm.faces.new(verts_list)
                    # for edge in face.edges:
                    #     edges_dict.setdefault(edge, ((edge.verts[1].co - edge.verts[0].co).normalized(), edge.calc_length(), edge.verts[0], edge))
                    # sec_bm.to_mesh(sec_mesh)
                    # 跳过天空面
                    if face_type == 7005:
                        tex_id = -1
                        dot = normal.dot(z_axis)
                        # 判断纹理类型
                        if dot > epsilon:
                            tex_type = "Floor"
                        elif dot < -epsilon:
                            tex_type = "Ceiling"
                        else:
                            tex_type = "Wall"

                        # 设置扇区预设纹理
                        tex_prop = sec_data.textures.get(tex_type)
                        if not tex_prop:
                            tex_prop = sec_data.textures.add()
                            tex_prop.target = "Sector"
                            tex_prop.name = tex_type
                            tex_prop["id"] = tex_id
                            tex_prop["xpos"] = 0
                            tex_prop["ypos"] = 0
                            tex_prop["angle"] = 0
                            tex_prop["xzoom"] = 20
                            tex_prop["yzoom"] = 20
                        else:
                            tex_type = "Custom"

                        img = scene_data.ensure_null_tex  # type: Image
                        img_data = img.amagate_data
                        slot_index = sec_mesh.materials.find(img_data.mat_obj.name)
                        if slot_index == -1:
                            sec_mesh.materials.append(img_data.mat_obj)
                            slot_index = sec_mesh.materials.find(img_data.mat_obj.name)
                        face[layers["flag"]] = L3D_data.FACE_FLAG[tex_type]
                        face.material_index = slot_index
                        face[layers["tex_id"]] = tex_id
                        face[layers["tex_xpos"]] = 0
                        face[layers["tex_ypos"]] = 0
                        face[layers["tex_angle"]] = 0
                        face[layers["tex_xzoom"]] = 20
                        face[layers["tex_yzoom"]] = 20
                        continue
                    # 设置连接面
                    sec_data.connect_num += 1
                    conn_sid = unpack("<I", f)[0] + 1
                    face[layers["connected"]] = conn_sid

                ## 跳过固定标识 (3,0)
                f.seek(8, 1)

                # 解包纹理数据
                (
                    tex_type,
                    slot_index,
                    tex_id,
                    tex_xpos,
                    tex_ypos,
                    tex_angle,
                    tex_xzoom,
                    tex_yzoom,
                ) = unpack_texture(sec_mesh, sec_data, normal, f, global_texture_map)

                #
                if face_type == 7002:
                    face[layers["flag"]] = L3D_data.FACE_FLAG[tex_type]
                    face.material_index = slot_index
                    face[layers["tex_id"]] = tex_id
                    face[layers["tex_xpos"]] = tex_xpos
                    face[layers["tex_ypos"]] = tex_ypos
                    face[layers["tex_angle"]] = tex_angle
                    face[layers["tex_xzoom"]] = tex_xzoom
                    face[layers["tex_yzoom"]] = tex_yzoom

                # 跳过 b"\x00" * 8
                f.seek(8, 1)

                #
                if face_type == 7002:
                    continue

                # 非7002/7005的情况
                vertex_num = unpack("<I", f)[0]
                verts_list = []
                for i in range(vertex_num):
                    verts_idx = unpack("<I", f)[0]
                    vert = sec_vertex_map.get(verts_idx)
                    if vert is None:
                        vert = sec_bm.verts.new(global_vertex_map[verts_idx])
                        sec_vertex_map[verts_idx] = vert
                    verts_list.append(vert)
                face = sec_bm.faces.new(verts_list)
                # sec_bm.to_mesh(sec_mesh)
                #
                face[layers["flag"]] = L3D_data.FACE_FLAG[tex_type]
                face.material_index = slot_index
                face[layers["tex_id"]] = tex_id
                face[layers["tex_xpos"]] = tex_xpos
                face[layers["tex_ypos"]] = tex_ypos
                face[layers["tex_angle"]] = tex_angle
                face[layers["tex_xzoom"]] = tex_xzoom
                face[layers["tex_yzoom"]] = tex_yzoom
                # 切割面
                if face_type == 7003:
                    vertex_sub_num = unpack("<I", f)[0]
                    f.seek(4 * vertex_sub_num, 1)
                    conn_sid = unpack("<I", f)[0] + 1

                    tangent_data = []
                    tangent_num = unpack("<I", f)[0]
                    for i in range(tangent_num):
                        plane_no = Vector(unpack("<ddd", f))
                        plane_no.yz = plane_no.z, -plane_no.y
                        dist = unpack("<d", f)[0] / 1000
                        plane_co = plane_no * -dist
                        tangent_data.append((plane_no, plane_co))

                    # inner_face = hole_split(sec_bm, face, tangent_data)
                    # inner_face[layers["connected"]] = conn_sid
                    hole_split_list.append((face, tangent_data, conn_sid))
                    #
                    sec_data.connect_num += 1
                #
                elif face_type == 7004:
                    holes_data = []
                    cut_data = []
                    cut_num = 0
                    block_mark_num = 0
                    hole_num = unpack("<I", f)[0]
                    for i in range(hole_num):
                        hole_vx_num = unpack("<I", f)[0]
                        f.seek(4 * hole_vx_num, 1)
                        conn_sid = unpack("<I", f)[0] + 1

                        tangent_data = []
                        tangent_num = unpack("<I", f)[0]
                        for i in range(tangent_num):
                            plane_no = Vector(unpack("<ddd", f))
                            plane_no.yz = plane_no.z, -plane_no.y
                            dist = unpack("<d", f)[0] / 1000
                            plane_co = plane_no * -dist
                            tangent_data.append((plane_no, plane_co))
                        holes_data.append((tangent_data, conn_sid))
                    #
                    sec_data.connect_num += hole_num
                    #
                    block_mark = unpack("<I", f)[0]
                    if block_mark in (8001, 8002):
                        block_mark_num += 1
                    # while True:
                    while cut_num < block_mark_num:
                        mark = unpack("<I", f)[0]
                        if mark in (8001, 8002):
                            block_mark_num += 1
                        elif mark == 8003:
                            tangent_data = conn_sid = None
                            # holes_idx_data = []
                            holes_idx_num = unpack("<I", f)[0]
                            for i in range(holes_idx_num):
                                hole_idx = unpack("<I", f)[0]
                                tangent_num = unpack("<I", f)[0]
                                tangent_data = [
                                    holes_data[hole_idx][0][unpack("<I", f)[0]]
                                    for i in range(tangent_num)
                                ]
                                conn_sid = holes_data[hole_idx][1]
                                # holes_idx_data.append((tangent_data, conn_sid))
                            cut_data.append((mark, tangent_data, conn_sid))
                            if holes_idx_num > 1:
                                # 添加到异常扇区
                                abnormal_sec.append(sec)
                        # elif mark in (7001, 7002, 7003, 7004, 7005):
                        #     f.seek(-4, 1)  # back 4
                        #     break
                        # 切割数据
                        else:
                            # mark2 = unpack("I", f)[0]
                            # f.seek(-4, 1)
                            # if mark2 in (15001, 15002):
                            #     f.seek(-4, 1)  # back 8
                            #     break
                            # if mark in atmos_name_len:
                            #     name = unpack(f"{mark}s", f)
                            #     f.seek(-mark, 1)
                            #     if name in global_atmo_map:
                            #         f.seek(-4, 1)
                            #         break

                            f.seek(-4, 1)
                            plane_no = Vector(unpack("<ddd", f))
                            plane_no.yz = plane_no.z, -plane_no.y
                            dist = unpack("<d", f)[0] / 1000
                            plane_co = plane_no * -dist
                            # 检查是否有纹理
                            flag = unpack("<II", f)
                            if tuple(flag) == (3, 0):
                                tex_data = unpack_texture(
                                    sec_mesh, sec_data, normal, f, global_texture_map
                                )
                                # 跳过 b"\x00" * 8
                                f.seek(8, 1)
                            else:
                                tex_data = None
                                f.seek(-8, 1)
                            cut_data.append(("cut", plane_no, plane_co, tex_data))
                            #
                            cut_num += 1
                    # 退化为7003
                    if cut_num == 0 and block_mark == 8003:
                        holes_idx_num = unpack("<I", f)[0]
                        for i in range(holes_idx_num):
                            hole_idx = unpack("<I", f)[0]
                            tangent_num = unpack("<I", f)[0]
                            tangent_data = [
                                holes_data[hole_idx][0][unpack("<I", f)[0]]
                                for i in range(tangent_num)
                            ]
                            conn_sid = holes_data[hole_idx][1]
                            # inner_face = hole_split(sec_bm, face, tangent_data)
                            # inner_face[layers["connected"]] = holes_data[hole_idx][1]
                        if holes_idx_num != 0:
                            hole_split_list.append((face, tangent_data, conn_sid))
                            sec_data.connect_num += 1
                    # 切割
                    else:
                        flat_split_list.append((face, cut_data))
                        # flat_split(sec_bm, face, cut_data, layers)

            # if sector_id == 1447:
            #     logger.debug(flat_split_list)

            # 处理非连续边
            edges_list = []  # type: list[tuple[Vector, float, bmesh.types.BMEdge]]
            for e in sec_bm.edges:
                if len(e.link_faces) == 1:
                    vector = e.verts[1].co - e.verts[0].co
                    edges_list.append((vector.normalized(), vector.length, e))
            need_fix = len(edges_list) > 0
            # logger.debug(f"edges_list: {len(edges_list)}")
            #
            while edges_list:
                dir1, len1, e1 = edges_list.pop()
                # logger.debug(f"dir: {dir1.to_tuple()}, len: {len1}")
                for idx, (dir2, len2, e2) in enumerate(edges_list):
                    if abs(dir1.dot(dir2)) < epsilon2:
                        continue

                    vert = e2.verts[1] if e2.verts[0] in e1.verts else e2.verts[0]
                    vector = vert.co - e1.verts[0].co
                    # logger.debug(f"intersection: {set(e2.verts).intersection(set(e1.verts))}")
                    direction = vector.normalized()
                    dot = dir1.dot(direction)
                    # 不共线，跳过
                    if abs(dot) < epsilon2:
                        continue

                    edges_list.pop(idx)
                    edges = ((dir1, len1, e1), (dir2, len2, e2))
                    for i in (0, 1):
                        dir1, len1, e1 = edges[i]
                        dir2, len2, e2 = edges[1 - i]
                        for vert in e2.verts:
                            if vert in e1.verts:
                                continue

                            vector = vert.co - e1.verts[0].co
                            direction = vector.normalized()
                            dot = dir1.dot(direction)
                            # 点不在e1上，跳过
                            if dir1.dot(direction) < epsilon2 or vector.length > len1:
                                continue
                            #
                            new_edge, new_vert = bmesh.utils.edge_split(
                                e1, e1.verts[0], 0.5
                            )
                            new_vert.co = vert.co
                    # 存在边内顶点
                    break

            # 按距离合并顶点
            bmesh.ops.remove_doubles(sec_bm, verts=sec_bm.verts, dist=0.0001)  # type: ignore
            mesh_tmp = bpy.data.meshes.new("")
            sec_bm.to_mesh(mesh_tmp)
            bpy.data.meshes.remove(mesh_tmp)
            # 切割
            if not need_fix:
                # if sector_id == 6:
                #     bm_mesh = bpy.data.meshes.new(f"AG.split")
                #     sec_bm.to_mesh(bm_mesh)
                #     bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
                #     data.link2coll(bm_obj, bpy.context.scene.collection)
                for face, tangent_data, conn_sid in hole_split_list:
                    # if sector_id == 6:
                    #     logger.debug(f"face: {face.index}, tangent_data: {tangent_data}")
                    inner_face = hole_split(sec_bm, face, tangent_data, sector_id)
                    if inner_face is not None:
                        inner_face[layers["connected"]] = conn_sid
                for face, cut_data in flat_split_list:
                    flat_split(sec_bm, face, cut_data, layers, sector_id)
                #
                sec_bm.to_mesh(sec_mesh)
                sec_bm.free()
                # 有限融并
                ag_utils.dissolve_limit_sectors([sec], check_convex=False)
                sec_data.is_2d_sphere = ag_utils.is_2d_sphere(sec)
                sec_data.is_convex = ag_utils.is_convex(sec)
            else:
                sec_bm.to_mesh(sec_mesh)
                for idx, (face, tangent_data, conn_sid) in enumerate(hole_split_list):
                    hole_split_list[idx] = (face.index, tangent_data, conn_sid)
                for idx, (face, cut_data) in enumerate(flat_split_list):
                    flat_split_list[idx] = (face.index, cut_data)
                #
                fix_sec.append((sec, hole_split_list, flat_split_list))
                sec_bm.free()

            #
            for tex_type in ("Floor", "Ceiling", "Wall"):
                tex_prop = sec_data.textures.get(tex_type)
                if not tex_prop:
                    tex_prop = sec_data.textures.add()
                    tex_prop.target = "Sector"
                    tex_prop.name = tex_type
                    tex_prop["id"] = -1
                    tex_prop["xpos"] = 0
                    tex_prop["ypos"] = 0
                    tex_prop["angle"] = 0
                    tex_prop["xzoom"] = 20
                    tex_prop["yzoom"] = 20
            ############################
            # sec_mesh.clear_geometry()
            # vertices = [v.co for v in sec_bm.verts]
            # center = sum(vertices, Vector()) / len(vertices)
            # sec.location = center

            # 添加修改器
            modifier = sec.modifiers.new("", type="NODES")
            modifier.node_group = scene_data.sec_node  # type: ignore
            # 添加到扇区管理字典
            scene_data["SectorManage"]["sectors"][str(sector_id)] = {
                "obj": sec,
                "atmo_id": 0,
                "external_id": 0,
            }
            #
            sec_data.atmo_id = global_atmo_map[atmo_name]
            sec_data.ambient_color = ambient_color
            sec_data.flat_light.color = flat_color
            sec.amagate_data.is_sector = True
            #
            sec_coll = L3D_data.ensure_collection(L3D_data.S_COLL)
            if need_fix:
                pass
            elif sec in abnormal_sec:
                coll_name = "Abnormal"
                coll = bpy.data.collections.get(coll_name)
                if not coll:
                    coll = bpy.data.collections.new(coll_name)
                    sec_coll.children.link(coll)
                data.link2coll(sec, coll)
            else:
                data.link2coll(sec, sec_coll)
            # 平面光设置
            if flat_vector.length != 0:
                dot_list = [
                    (f.index, f.normal.dot(flat_vector)) for f in sec_mesh.polygons
                ]
                dot_list.sort(key=lambda x: x[1])
                sec_mesh.attributes["amagate_flat_light"].data[dot_list[0][0]].value = 1  # type: ignore

            # 耗时操作
            # sec.select_set(True)
            # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
            # sec.select_set(False)

        # 修复扇区
        for sec, hole_split_list, flat_split_list in fix_sec:
            # sec_data = sec.amagate_data.get_sector_data()
            sec_mesh = sec.data  # type: bpy.types.Mesh  # type: ignore
            sec_bm = bmesh.new()
            sec_bm.from_mesh(sec_mesh)
            layers = {
                "connected": sec_bm.faces.layers.int.get("amagate_connected"),
                "flag": sec_bm.faces.layers.int.get("amagate_flag"),
                "flat_light": sec_bm.faces.layers.int.get("amagate_flat_light"),
                "tex_id": sec_bm.faces.layers.int.get("amagate_tex_id"),
                "tex_xpos": sec_bm.faces.layers.float.get("amagate_tex_xpos"),
                "tex_ypos": sec_bm.faces.layers.float.get("amagate_tex_ypos"),
                "tex_angle": sec_bm.faces.layers.float.get("amagate_tex_angle"),
                "tex_xzoom": sec_bm.faces.layers.float.get("amagate_tex_xzoom"),
                "tex_yzoom": sec_bm.faces.layers.float.get("amagate_tex_yzoom"),
            }
            # 切割
            for idx in range(len(hole_split_list) - 1, -1, -1):
                face_idx, tangent_data, conn_sid = hole_split_list[idx]
                if len(tangent_data) == 1:
                    continue

                hole_split_list.pop(idx)
                sec_bm.faces.ensure_lookup_table()
                face = sec_bm.faces[face_idx]
                inner_face = hole_split(sec_bm, face, tangent_data, sector_id)
                if inner_face is not None:
                    inner_face[layers["connected"]] = conn_sid
            for face_idx, cut_data in flat_split_list:
                sec_bm.faces.ensure_lookup_table()
                face = sec_bm.faces[face_idx]
                flat_split(sec_bm, face, cut_data, layers, sector_id)
            #
            sec_bm.to_mesh(sec_mesh)
            sec_bm.free()
            # 有限融并
            ag_utils.dissolve_limit_sectors([sec], check_convex=False)
        # 顶点匹配连接
        for sec, hole_split_list, flat_split_list in fix_sec:
            sec_data = sec.amagate_data.get_sector_data()
            sec_mesh = sec.data  # type: bpy.types.Mesh  # type: ignore
            sec_bm = bmesh.new()
            sec_bm.from_mesh(sec_mesh)
            layers = {
                "connected": sec_bm.faces.layers.int.get("amagate_connected"),
                "flag": sec_bm.faces.layers.int.get("amagate_flag"),
                "flat_light": sec_bm.faces.layers.int.get("amagate_flat_light"),
                "tex_id": sec_bm.faces.layers.int.get("amagate_tex_id"),
                "tex_xpos": sec_bm.faces.layers.float.get("amagate_tex_xpos"),
                "tex_ypos": sec_bm.faces.layers.float.get("amagate_tex_ypos"),
                "tex_angle": sec_bm.faces.layers.float.get("amagate_tex_angle"),
                "tex_xzoom": sec_bm.faces.layers.float.get("amagate_tex_xzoom"),
                "tex_yzoom": sec_bm.faces.layers.float.get("amagate_tex_yzoom"),
            }
            for idx in range(len(hole_split_list) - 1, -1, -1):
                face_idx, tangent_data, conn_sid = hole_split_list[idx]
                if len(tangent_data) == 1:
                    conn_sec = scene_data["SectorManage"]["sectors"][str(conn_sid)][
                        "obj"
                    ]
                    sec_bm.faces.ensure_lookup_table()
                    face = sec_bm.faces[face_idx]
                    result = connect_vm(sec_bm, face, sec_data.id, layers, conn_sec)
                    # logger.debug(f"connect_vm: {result}")
                    # if result:
                    #     hole_split_list.pop(idx)
            #
            sec_bm.to_mesh(sec_mesh)
            sec_bm.free()
            # 有限融并
            # ag_utils.dissolve_limit_sectors([sec], check_convex=False)
            sec_data.is_2d_sphere = ag_utils.is_2d_sphere(sec)
            sec_data.is_convex = ag_utils.is_convex(sec)
            #
            if not sec_data.is_2d_sphere:
                coll_name = "Need Fix"
                coll = bpy.data.collections.get(coll_name)
                if not coll:
                    coll = bpy.data.collections.new(coll_name)
                    sec_coll.children.link(coll)
                data.link2coll(sec, coll)
            else:
                data.link2coll(sec, sec_coll)

        # 外部光和灯泡数据
        light_num = unpack("<I", f)[0]
        for i in range(light_num):
            light_type = unpack("<I", f)[0]
            # 外部光
            if light_type == 15002:
                rgb = unpack("<BBB", f)
                v = unpack("<f", f)[0]
                precision = unpack("<f", f)[0]
                # 跳过 (0,0,0, b"\xCD"*8, 0)
                f.seek(36, 1)
                ext_vector = Vector(unpack("<ddd", f))
                ext_vector.yz = ext_vector.z, -ext_vector.y
                ext_color = Color(i / 255 for i in rgb)
                ext_color.v = v / v_factor
                # 创建外部光
                item = OP_L3D.OT_Scene_External_Add.add(context)
                item.color = ext_color
                item.vector = ext_vector
                item.data.shadow_maximum_resolution = precision
                # 使用该外部光的扇区
                sec_num = unpack("<I", f)[0]
                # logger.debug(f"External light: {sec_num}")
                for i in range(sec_num):
                    sid = unpack("<I", f)[0] + 1
                    sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.external_id = item.id
            # 灯泡光
            elif light_type == 15001:
                rgb = unpack("<BBB", f)
                rgb = [i / 255 for i in rgb]
                strength = unpack("<f", f)[0]
                precision = unpack("<f", f)[0]
                pos = Vector(unpack("<ddd", f)) / 1000
                pos.yz = pos.z, -pos.y
                sid = unpack("<I", f)[0] + 1
                #
                sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
                sec_data = sec.amagate_data.get_sector_data()
                item = OP_SECTOR.OT_Bulb_Add.add(context, sec)
                item.light_obj.data.color = rgb
                item.light_obj.matrix_world.translation = pos
                item.strength = strength
                item.precision = precision
                item.update_location(context)
        # 跳过未知数据 (ddd, ddd)
        f.seek(48, 1)
        # 组数据
        for sid in range(1, sec_total + 1):
            sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
            sec_data = sec.amagate_data.get_sector_data()
            group = unpack("<i", f)[0]  # 有符号整数
            sec_data.group = group
        # 扇区名称数据
        sec_total = unpack("<I", f)[0]
        for sid in range(1, sec_total + 1):
            sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
            name_len = unpack("<I", f)[0]
            name = unpack(f"{name_len}s", f)
            sec.rename(name, mode="ALWAYS")
            sec.data.rename(name, mode="ALWAYS")
    #
    wm.progress_end()
    print(f", Done in {time.time() - start_time:.2f}s")

    ############################
    return True


############################
############################ 导入地图操作
############################


class OT_ImportMap(bpy.types.Operator):
    bl_idname = "amagate.importmap"
    bl_label = "Import Map"
    bl_description = "Import Map"
    bl_options = {"INTERNAL"}

    # 过滤文件
    # filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    # filter_image: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_glob: StringProperty(default="*.bw", options={"HIDDEN"})  # type: ignore

    # 相对路径
    # relative_path: BoolProperty(name="Relative Path", default=True)  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    execute_type: IntProperty(default=0, options={"HIDDEN"})  # type: ignore

    # @classmethod
    # def poll(cls, context: Context):
    #     return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context):
        filepath = self.filepath
        if os.path.splitext(filepath)[1].lower() != ".bw":
            self.report({"ERROR"}, "No bw file selected")
            return {"CANCELLED"}
        # file_name = next(
        #     (f.name for f in self.files if f.name[-3:].lower() == ".bw"), None
        # )
        # if not file_name:
        #     self.report({"ERROR"}, "No bw file selected")
        #     return {"CANCELLED"}

        L3D_data.LOAD_POST_CALLBACK = (OP_L3D.InitMap, (filepath,))
        bpy.ops.wm.read_homefile(app_template="")

        return {"FINISHED"}

    def invoke(self, context, event):
        if self.execute_type == 0:
            if bpy.data.is_dirty:
                return context.window_manager.invoke_popup(self)
            else:
                self.execute_type = 2
        elif self.execute_type == 1:  # Save
            ag_utils.simulate_keypress(27)
            ret = bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")  # type: ignore
            if ret != {"FINISHED"}:
                return ret
        elif self.execute_type == 2:  # Don't Save
            pass
        elif self.execute_type == 3:  # Cancel
            ag_utils.simulate_keypress(27)
            return {"CANCELLED"}

        # 设为上次选择目录，文件名为空
        # self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context: Context):
        if self.execute_type != 0:
            return

        layout = self.layout  # type: bpy.types.UILayout
        # layout.use_property_decorate = True
        scene_data = context.scene.amagate_data

        layout.label(text="Save changes before closing?", icon="QUESTION")
        layout.separator(type="LINE")

        row = layout.row()
        op = row.operator(OT_ImportMap.bl_idname, text="Save").execute_type = 1  # type: ignore
        row.operator(OT_ImportMap.bl_idname, text="Don't Save").execute_type = 2  # type: ignore
        row.operator(OT_ImportMap.bl_idname, text="Cancel").execute_type = 3  # type: ignore


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
