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

SKY_TEX_REFPATH = {
    "Casa": "../Casa/casa_d.mmp",
    "Kashgar": "../Barb_M1/barb_d.mmp",
    "Tabriz": "../Ragnar_M2/ragnar_d.mmp",
    "Khazel Zalam": "../Dwarf_M3/dwarf_d.mmp",
    "Marakamda": "../Ruins_M4/dome.mmp",
    "Mines of Kelbegen": "../Mine_M5/mine_d.mmp",
    "Fortress of Tell Halaf": "../Labyrinth_M6/dome.mmp",
    "Tombs of Ephyra": "../Tomb_M7/tomb_d.mmp",
    "Island of Karum": "../Island_M8/island_d.mmp",
    "Shalatuwar Fortress": "../Orc_M9/orcst_d.mmp",
    "The Gorge of Orlok": "../Orlok_M10/dome.mmp",
    "Fortress of Nemrut": "../Ice_M11/ice_d.mmp",
    "The Oasis of Nejeb": "../Btomb_M12/btomb_d.mmp",
    "Temple of Al Farum": "../Desert_M13/desert_d.mmp",
    "Forge of Xshathra": "../Volcano_M14/volcan_d.mmp",
    "The Temple of Ianna": "../Palace_M15/palace_d.mmp",
    "Tower of Dal Gurak": "../Tower_M16/tower_d.mmp",
    "The Abyss": "../Chaos_M17/chaos_d.mmp",
}

############################
steep_auto_code = """
for pos in steep_auto:
    s = Bladex.GetSector(pos[0], pos[1], pos[2])
    s.TooSteep = 1
    s.TooSteepAngle = 0.698132

"""

steep_yes_code = """
for pos in steep_yes:
    s = Bladex.GetSector(pos[0], pos[1], pos[2])
    s.TooSteep = 1
    s.TooSteepAngle = -1

"""

steep_no_code = """
for pos in steep_no:
    s = Bladex.GetSector(pos[0], pos[1], pos[2])
    s.TooSteep = 0
    s.TooSteepAngle = -1

"""


############################


# 切割平面
def bisect_plane(bm, plane_no, plane_co):
    # type: (bmesh.types.BMesh, Vector, Vector) -> tuple[bmesh.types.BMesh, bmesh.types.BMesh]
    # amagate_hole
    # ag_utils.debugprint(f"plane_no: {plane_no}, plane_co: {plane_co}")
    bm_layer = bm.faces.layers.int.get("amagate_connected")
    result = bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.verts) + list(bm.edges) + list(bm.faces),  # type: ignore
        dist=1e-4,
        plane_no=plane_no,
        plane_co=plane_co,
        clear_inner=False,
        clear_outer=False,
    )
    # 获取外部面
    cut_verts = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMVert)]
    cut_edges = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
    edge = cut_edges[0]
    face1, face2 = edge.link_faces
    co = next(v.co for v in face1.verts if v not in cut_verts)
    dir = (co - edge.verts[0].co).normalized()
    if plane_no.dot(dir) > 0:
        outer_face = face1
    else:
        outer_face = face2
    outer_faces = ag_utils.get_linked_flat_2d(outer_face, limit_edge=cut_edges)

    # 创建外部网格
    outer_bm = bmesh.new()
    layer = outer_bm.faces.layers.int.new("amagate_connected")
    verts_map = {}
    exist_edges = []
    for f in outer_faces:
        for v in f.verts:
            if v.index not in verts_map:
                verts_map[v.index] = outer_bm.verts.new(v.co)
    # for f in outer_faces:
    #     for e in f.edges:
    #         if e.index not in exist_edges:
    #             edge = outer_bm.edges.new([verts_map[v.index] for v in e.verts])
    #             exist_edges.append(e.index)
    # 复制属性
    # edge[layer] = e[bm_layer] # type: ignore
    for f in outer_faces:
        new_face = outer_bm.faces.new([verts_map[v.index] for v in f.verts])
        # 复制属性
        new_face[layer] = f[bm_layer]  # type: ignore

    outer_bm = ag_utils.ensure_lookup_table(outer_bm)

    # 删除原始网格中的外部网格
    bmesh.ops.delete(bm, geom=outer_faces, context="FACES")

    return bm, outer_bm


#
def hole_split(bm, hole_dict):
    # type: (bmesh.types.BMesh, dict[Any, Any]) -> Any
    cut_data = []
    cut_data_buff = []
    #
    stack = [(bm, 0)]
    while stack:
        bm, count = stack.pop()
        #
        # bm_mesh = bpy.data.meshes.new(f"AG.split")
        # bm.to_mesh(bm_mesh)
        # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
        # data.link2coll(bm_obj, bpy.context.scene.collection)
        #
        bm.verts.ensure_lookup_table()
        layer = bm.faces.layers.int.get("amagate_connected")
        hole = next(f for f in bm.faces if f[layer] != 0)  # type: ignore
        normal = hole.normal.copy()
        # conn_sid = hole[layer]  # type: ignore

        verts_sort = {v: i for i, v in enumerate(hole.verts)}
        last_pair = {0, len(hole.verts) - 1}
        tangent_data = []
        other_holes = [f for f in bm.faces if f != hole and f[layer] != 0]  # type: ignore
        #
        if other_holes:
            count += 1
            for edge in hole.edges:
                if edge.is_boundary:
                    continue
                #
                v1, v2 = edge.verts
                v1_idx, v2_idx = verts_sort[v1], verts_sort[v2]
                if {v1_idx, v2_idx} == last_pair:
                    if v1_idx == 0:
                        v1, v2 = v2, v1
                elif v2_idx < v1_idx:
                    v1, v2 = v2, v1
                # 计算切线
                cross = (v2.co - v1.co).cross(normal)  # type: Vector
                tangent = Vector(cross.normalized().to_tuple(5))
                dist = round((-v1.co).dot(tangent) * 1000, 1)
                clean_hole = set()  # 可清理的洞
                polluted_hole = set()  # 污染的洞
                #
                for hole_2 in other_holes:
                    conn_sid_2 = hole_2[layer]  # type: ignore
                    #
                    dot_lst = [
                        (v.co - v1.co).normalized().dot(tangent) for v in hole_2.verts
                    ]
                    # 所有点在切线空间内或与切线平行，则为可清理的洞
                    if all([i > -epsilon for i in dot_lst]):
                        clean_hole.add(conn_sid_2)
                    # 只有部分点在切线空间内（不包括与切线平行），则为不可清理的污染的洞
                    elif next((i > epsilon for i in dot_lst), None):
                        polluted_hole.add(conn_sid_2)
                if clean_hole or polluted_hole:
                    tangent_data.append(
                        [edge.verts[0].co, tangent, dist, clean_hole, polluted_hole]
                    )
            # if tangent_data:
            flag = [8003, 1]
            # 切割平面
            inner_cut = False
            while tangent_data:
                # 污染数量最少的排前面
                tangent_data.sort(key=lambda x: len(x[4]))
                # 清理数量最多的排前面
                tangent_data.sort(key=lambda x: -len(x[3]))
                #
                plane_co, tangent, dist, clean_hole, polluted_hole = tangent_data[0]
                _, outer_bm = bisect_plane(bm, tangent, plane_co)
                if inner_cut:
                    stack.append((outer_bm, 1))
                else:
                    stack.append((outer_bm, count))
                # cut_data.append(((tangent[0], -tangent[2], tangent[1]), dist))
                cut_data_buff.append(
                    struct.pack("<dddd", tangent[0], -tangent[2], tangent[1], dist)
                )
                #
                for i in range(len(tangent_data) - 1, 0, -1):
                    tangent_data[i][3].difference_update(clean_hole)
                    tangent_data[i][4].difference_update(clean_hole)
                    if not (tangent_data[i][3] or tangent_data[i][4]):
                        tangent_data.pop(i)
                tangent_data.pop(0)
                inner_cut = True
        else:
            flag = [8001] * count + [8003, 1]
        # 最终的块只剩下一个洞
        # bm_mesh = bpy.data.meshes.new(f"AG.split")
        # bm.to_mesh(bm_mesh)
        # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
        # data.link2coll(bm_obj, bpy.context.scene.collection)
        #
        hole = next(f for f in bm.faces if f[layer] != 0)  # type: ignore
        hole_data = hole_dict[hole[layer]]  # type: ignore
        tangent_idx = []
        # if not hole_data:
        #     hole_data = {"index": hole_index, "tangent": []}
        #     hole_dict[hole[layer]] = hole_data  # type: ignore
        #     hole_index += 1
        if len(bm.faces) != 1:
            verts_sort = {v: i for i, v in enumerate(hole.verts)}
            last_pair = {0, len(hole.verts) - 1}
            normal = hole.normal.copy()
            for edge in hole.edges:
                if edge.is_boundary:
                    continue
                v1, v2 = edge.verts
                v1_idx, v2_idx = verts_sort[v1], verts_sort[v2]
                if {v1_idx, v2_idx} == last_pair:
                    if v1_idx == 0:
                        v1, v2 = v2, v1
                elif v2_idx < v1_idx:
                    v1, v2 = v2, v1
                # 计算切线
                cross = (v2.co - v1.co).cross(normal)  # type: Vector
                tangent = Vector(cross.normalized().to_tuple(5))
                dist = round((-v1.co).dot(tangent) * 1000, 1)

                t = tangent[0], -tangent[2], tangent[1], dist
                if t not in hole_data["tangent"]:
                    hole_data["tangent"].append(t)
                    tangent_idx.append(len(hole_data["tangent"]) - 1)
                else:
                    index = hole_data["tangent"].index(t)
                    if index not in tangent_idx:
                        tangent_idx.append(index)
        # cut_data.append((flag, hole_data["index"], tangent_idx))
        cut_data_buff.append(
            struct.pack(
                f"<{'I'*len(flag)}II{'I'*len(tangent_idx)}",
                *flag,
                hole_data["index"],
                len(tangent_idx),
                *tangent_idx,
            )
        )
    #
    holes_data = [
        (v["index"], v["tangent"], v["verts_idx"], k) for k, v in hole_dict.items()
    ]
    holes_data.sort(key=lambda x: x[0])

    # print("\n".join(map(str, hole_dict.items())))
    # print("\n".join(map(str, cut_data)))
    return holes_data, cut_data_buff


#
def export_map(this: bpy.types.Operator, context: Context, with_run_script=False):
    scene_data = context.scene.amagate_data
    # 检查是否为无标题文件
    if not bpy.data.filepath:
        this.report({"WARNING"}, "Please save the file first")
        return {"CANCELLED"}

    # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
    if "EDIT" in context.mode:
        bpy.ops.object.mode_set(mode="OBJECT")
        selected_objects = context.selected_objects.copy()
        if context.active_object not in selected_objects:
            selected_objects.append(context.active_object)
        L3D_data.geometry_modify_post(selected_objects, check_connect=False)

    # 收集可见的凸扇区
    sectors_dict = scene_data["SectorManage"]["sectors"]
    sector_ids = [
        int(k)
        for k in sectors_dict
        if sectors_dict[k]["obj"].visible_get()
        and sectors_dict[k]["obj"].amagate_data.get_sector_data().is_convex
    ]

    if not sector_ids:
        this.report({"WARNING"}, "No visible sector found")
        return {"CANCELLED"}
    sector_ids.sort()

    # 导出扇区
    ## blender坐标转换到blade: x,-z,y

    bw_file = f"{os.path.splitext(bpy.data.filepath)[0]}.bw"
    global_face_count = 0
    global_vertex_count = 0
    global_vertex_map = {}  # {tuple(co): global_index}
    sector_vertex_indices = {}  # 每个扇区的全局顶点索引映射
    global_sector_map = {sid: i for i, sid in enumerate(sector_ids)}  # 全局扇区映射
    with open(bw_file, "wb") as f:
        # 写入大气数据
        f.write(struct.pack("<I", len(scene_data.atmospheres) + 1))
        for atm in scene_data.atmospheres:
            buffer = atm.item_name.encode("utf-8")
            f.write(struct.pack("<I", len(buffer)))
            f.write(buffer)
            f.write(
                struct.pack("<BBB", *(math.ceil(atm.color[i] * 255) for i in range(3)))
            )
            f.write(struct.pack("<f", atm.color[-1]))
        ## 写入Amagate元数据
        buffer = f"Metadata:\nAmagate-{data.VERSION} {data.Copyright}\nhttps://github.com/Sryml/Amagate".encode(
            "utf-8"
        )
        f.write(struct.pack("<I", len(buffer)))
        f.write(buffer)
        f.write(b"\x00" * 7)

        # 写入顶点数据
        number_pos = f.tell()
        f.write(struct.pack("<I", 0))  # 占位
        for i in sector_ids:
            sec = sectors_dict[str(i)]["obj"]  # type: Object
            sec_vertex_indices = []
            sec_data = sec.amagate_data.get_sector_data()
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            matrix_world = sec.matrix_world
            for v in mesh.vertices:
                # 变换顶点坐标并转换为毫米单位
                v_key = ((matrix_world @ v.co) * 1000).to_tuple(1)
                if v_key not in global_vertex_map:
                    global_vertex_map[v_key] = global_vertex_count
                    global_vertex_count += 1
                    f.write(struct.pack("<ddd", v_key[0], -v_key[2], v_key[1]))
                sec_vertex_indices.append(global_vertex_map[v_key])
            sector_vertex_indices[sec_data.id] = sec_vertex_indices
        # 暂存当前流位置并更正顶点数量
        stream_pos = f.tell()
        f.seek(number_pos)
        f.write(struct.pack("<I", global_vertex_count))
        f.seek(stream_pos)

        # 写入扇区数据
        v_factor = 0.86264  # 明度系数
        ambient_light_p = bytes.fromhex("0000803C")  # 0.015625 环境光精度
        ext_light_p = bytes.fromhex("0000003D")  # 0.03125 外部灯光精度
        spot_buffer = BytesIO()  # 缓存聚光灯数据
        spot_num = 0
        group_buffer = BytesIO()  # 缓存组数据
        sec_name_buffer = BytesIO()  # 缓存扇区名称数据
        steep_auto = []  # 自动陡峭
        steep_yes = []
        steep_no = []
        f.write(struct.pack("<I", len(sector_ids)))
        for sector_id in sector_ids:
            sec = sectors_dict[str(sector_id)]["obj"]  # type: Object
            sec_data = sec.amagate_data.get_sector_data()
            matrix_world = sec.matrix_world
            sec_mesh = sec.data  # type: bpy.types.Mesh # type: ignore

            # 聚光灯
            if sec_data.spot_light:
                spot_num += len(sec_data.spot_light)
                spot = None  # type: data.SectorFocoLightProperty # type: ignore
                for spot in sec_data.spot_light:
                    spot_buffer.write(struct.pack("<I", 15001))
                    spot_buffer.write(
                        struct.pack("<BBB", *(math.ceil(c * 255) for c in spot.color))
                    )
                    spot_buffer.write(struct.pack("<f", spot.strength))
                    spot_buffer.write(struct.pack("<f", spot.precision))
                    pos = spot.pos * 1000
                    spot_buffer.write(struct.pack("<ddd", pos[0], -pos[2], pos[1]))
                    spot_buffer.write(struct.pack("<f", global_sector_map[sector_id]))

            # 组
            group_buffer.write(struct.pack("<i", sec_data.group))  # 有符号整数

            # 扇区名称
            buffer = sec.name.encode("utf-8")
            sec_name_buffer.write(struct.pack("<I", len(buffer)))
            sec_name_buffer.write(buffer)

            # 大气名称
            atm_name = L3D_data.get_atmo_by_id(scene_data, sec_data.atmo_id)[
                1
            ].item_name
            buffer = atm_name.encode("utf-8")
            f.write(struct.pack("<I", len(buffer)))
            f.write(buffer)

            # 环境光
            color = sec_data.ambient_color
            f.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
            f.write(struct.pack("<f", color.v * v_factor))
            f.write(ambient_light_p)
            f.write(struct.pack("<ddd", 0, 0, 0))  # 未知用途 默认0
            f.write(bytes.fromhex("CD" * 8))
            f.write(struct.pack("<I", 0))

            # TODO 平面光
            f.write(struct.pack("<BBB", 0, 0, 0))
            f.write(struct.pack("<f", 0.0))
            f.write(ambient_light_p)
            f.write(struct.pack("<ddd", 0, 0, 0))  # # 未知用途 默认0
            f.write(bytes.fromhex("CD" * 8))
            f.write(struct.pack("<I", 0))
            ## 平面光向量
            f.write(struct.pack("<ddd", 0, 0, 0))

            # 面数据
            sec_vertex_indices = sector_vertex_indices[sec_data.id]
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated_obj = sec.evaluated_get(depsgraph)
            mesh = evaluated_obj.data  # type: bpy.types.Mesh # type: ignore
            sec_bm = bmesh.new()
            sec_bm.from_mesh(mesh)
            sec_bm.faces.ensure_lookup_table()
            sec_bm.verts.ensure_lookup_table()
            sec_bm_layer = sec_bm.faces.layers.int.get("amagate_connected")
            # global_face_count += len(mesh.polygons)
            # f.write(struct.pack("<I", len(mesh.polygons)))
            # 排序面，地板优先
            faces_sorted = []
            z_axis = Vector((0, 0, 1))

            conn_face_visited = set()
            connect_num = 0
            # 先找出连接面
            for face_index, face in enumerate(sec_bm.faces):
                if connect_num == sec_data.connect_num:
                    break
                if face_index in conn_face_visited:
                    continue

                connected_sid = mesh.attributes["amagate_connected"].data[face_index].value  # type: ignore
                if connected_sid == 0 or global_sector_map.get(connected_sid) is None:
                    continue

                # 如果是连接面且连接目标在导出列表中
                connect_num += 1
                connect_data = ()
                normal = matrix_world.to_quaternion() @ face.normal
                group_face_idx = ag_utils.get_linked_flat(face)
                conn_face_visited.update(group_face_idx)

                if len(group_face_idx) == 1:
                    face_type = 7002  # 整个面是连接的
                    verts_idx = [sec_vertex_indices[v.index] for v in face.verts]
                    connect_data = (connected_sid,)
                else:
                    conn_face_num = 0
                    hole_dict = {}  # type: Any
                    for i in group_face_idx:
                        conn_sid = mesh.attributes["amagate_connected"].data[i].value  # type: ignore
                        if conn_sid == 0:
                            continue
                        if conn_sid in hole_dict:
                            continue

                        face_conn = sec_bm.faces[i]
                        verts_sub_idx = [v.index for v in face_conn.verts]
                        verts_sub_idx = [sec_vertex_indices[i] for i in verts_sub_idx]
                        hole_dict[conn_sid] = {
                            "index": conn_face_num,
                            "tangent": [],
                            "verts_idx": verts_sub_idx,
                        }
                        #
                        conn_face_num += 1
                    #
                    if conn_face_num == 1:
                        face_type = 7003  # 平面中的单连接
                        #
                        # 按照顶点顺序计算切线
                        tangent_data = []  # 切线数据
                        verts_sub_idx = [v.index for v in face_conn.verts]
                        verts_sub_idx_num = len(verts_sub_idx)
                        for i in range(verts_sub_idx_num):
                            j = (i + 1) % verts_sub_idx_num

                            co1 = matrix_world @ sec_bm.verts[verts_sub_idx[i]].co
                            co2 = matrix_world @ sec_bm.verts[verts_sub_idx[j]].co
                            cross = (co2 - co1).cross(normal)  # type: Vector
                            cross.normalize()
                            dist = (-co1).dot(cross) * 1000

                            tangent_data.append((dist, cross))

                        # 转换为全局顶点索引
                        verts_sub_idx = [sec_vertex_indices[i] for i in verts_sub_idx]

                        connect_data = (face_conn[sec_bm_layer], verts_sub_idx, tangent_data)  # type: ignore
                    else:
                        face_type = 7004  # 平面中的多连接
                        # 复制平面
                        bm_plane = bmesh.new()
                        layer = bm_plane.faces.layers.int.new("amagate_connected")
                        verts_map = {}
                        for i in group_face_idx:
                            for v in sec_bm.faces[i].verts:
                                if v.index not in verts_map:
                                    verts_map[v.index] = bm_plane.verts.new(
                                        matrix_world @ v.co
                                    )
                        visited_conn_sid = []
                        for i in group_face_idx:
                            face = sec_bm.faces[i]
                            f_new = bm_plane.faces.new(
                                [verts_map[v.index] for v in face.verts]
                            )
                            conn_sid = face[sec_bm_layer]  # type: ignore
                            if conn_sid not in visited_conn_sid:
                                f_new[layer] = conn_sid  # type: ignore
                                visited_conn_sid.append(conn_sid)
                        bm_plane = ag_utils.ensure_lookup_table(bm_plane)
                        connect_data = hole_split(bm_plane, hole_dict)
                    # 获取凸壳顶点
                    bm_convex = sec_bm.copy()
                    bmesh.ops.delete(
                        bm_convex,
                        geom=[
                            f for f in bm_convex.faces if f.index not in group_face_idx
                        ],
                        context="FACES",
                    )  # 删除非组面
                    bmesh.ops.dissolve_faces(
                        bm_convex, faces=list(bm_convex.faces), use_verts=False
                    )  # 合并组面
                    ag_utils.unsubdivide(bm_convex)  # 反细分
                    bm_convex.faces.ensure_lookup_table()
                    verts_idx = [
                        global_vertex_map[((matrix_world @ v.co) * 1000).to_tuple(1)]
                        for v in bm_convex.faces[0].verts
                    ]
                    # 清理
                    bm_convex.free()

                faces_sorted.append(
                    (face_index, verts_idx, normal, face_type, connect_data)
                )

            # 再找出普通面和天空面
            connect_data = ()  # 空的连接信息
            for face_index, face in enumerate(sec_bm.faces):
                if face_index in conn_face_visited:
                    continue

                normal = matrix_world.to_quaternion() @ face.normal
                if mesh.attributes["amagate_tex_id"].data[face_index].value == -1:  # type: ignore
                    face_type = 7005  # 天空面
                else:
                    face_type = 7001  # 普通面
                verts_idx = [sec_vertex_indices[v.index] for v in face.verts]
                faces_sorted.append(
                    (face_index, verts_idx, normal, face_type, connect_data)
                )

            sec_bm.free()
            # ag_utils.debugprint(f"{sec.name}: {[i[0] for i in faces_sorted]}")
            # faces_sorted.sort(key=lambda x: -x[3]) # 连接面排前面
            # faces_sorted.sort(key=lambda x: x[2].to_tuple(3)) # 按法向排列
            faces_sorted.sort(
                key=lambda x: round(x[2].dot(-z_axis), 3)
            )  # 然后地板面排前面，避免滑坡问题

            # 如果不会被引擎设为滑坡且为自动模式
            if not sec_data.steep_check and sec_data.steep == "0":
                for item in faces_sorted:
                    cos = item[2].dot(z_axis)
                    # 与z轴点乘为0或负，跳过
                    if cos < epsilon:
                        continue
                    if cos < 0.7665:
                        steep_auto.append(sec)
            elif sec_data.steep == "1":
                steep_yes.append(sec)
            elif sec_data.steep == "2":
                steep_no.append(sec)

            global_face_count += len(faces_sorted)
            f.write(struct.pack("<I", len(faces_sorted)))
            for (
                face_index,
                verts_idx,
                normal,
                face_type,
                connect_data,
            ) in faces_sorted:
                f.write(struct.pack("<I", face_type))
                ## 法向
                # normal = matrix_world.to_quaternion() @ face.normal
                f.write(struct.pack("<ddd", normal[0], -normal[2], normal[1]))
                f.write(struct.pack("<d", mesh.attributes["amagate_v_dist"].data[face_index].value))  # type: ignore

                if face_type in (7002, 7005):
                    f.write(struct.pack("<I", len(verts_idx)))
                    for v_idx in verts_idx:
                        f.write(struct.pack("<I", v_idx))
                    if face_type == 7005:
                        continue
                    conn_sid = connect_data[0]
                    f.write(struct.pack("<I", global_sector_map[conn_sid]))
                ## 固定标识
                f.write(struct.pack("<I", 3))
                f.write(struct.pack("<I", 0))

                buffer = L3D_data.get_texture_by_id(mesh.attributes["amagate_tex_id"].data[face_index].value)[1].name.encode("utf-8")  # type: ignore
                f.write(struct.pack("<I", len(buffer)))
                f.write(buffer)
                tex_vx = mesh.attributes["amagate_tex_vx"].data[face_index].vector  # type: ignore
                f.write(struct.pack("<ddd", tex_vx[0], -tex_vx[2], tex_vx[1]))
                tex_vy = mesh.attributes["amagate_tex_vy"].data[face_index].vector  # type: ignore
                f.write(struct.pack("<ddd", tex_vy[0], -tex_vy[2], tex_vy[1]))
                tex_xpos = mesh.attributes["amagate_tex_xpos"].data[face_index].value  # type: ignore
                tex_ypos = mesh.attributes["amagate_tex_ypos"].data[face_index].value  # type: ignore
                f.write(struct.pack("<ff", tex_xpos, tex_ypos))

                f.write(b"\x00" * 8)  # 0
                #
                if face_type == 7002:
                    continue

                f.write(struct.pack("<I", len(verts_idx)))
                for v_idx in verts_idx:
                    f.write(struct.pack("<I", v_idx))
                #
                if face_type == 7003:
                    conn_sid, verts_sub_idx, tangent_data = connect_data
                    f.write(struct.pack("<I", len(verts_sub_idx)))
                    for v_idx in verts_sub_idx:
                        f.write(struct.pack("<I", v_idx))
                    f.write(struct.pack("<I", global_sector_map[conn_sid]))

                    f.write(struct.pack("<I", len(tangent_data)))
                    for dist, cross in tangent_data:
                        f.write(struct.pack("<ddd", cross[0], -cross[2], cross[1]))
                        f.write(struct.pack("<d", dist))
                #
                elif face_type == 7004:
                    holes_data, cut_data_buff = connect_data
                    f.write(struct.pack("<I", len(holes_data)))

                    for _, tangent_data, verts_sub_idx, conn_sid in holes_data:
                        f.write(struct.pack("<I", len(verts_sub_idx)))
                        for v_idx in verts_sub_idx:
                            f.write(struct.pack("<I", v_idx))
                        f.write(struct.pack("<I", global_sector_map[conn_sid]))

                        f.write(struct.pack("<I", len(tangent_data)))
                        for tx, ty, tz, dist in tangent_data:
                            f.write(struct.pack("<ddd", tx, ty, tz))
                            f.write(struct.pack("<d", dist))

                    while cut_data_buff:
                        f.write(cut_data_buff.pop())

                # elif face_type == 7004:
                #     f.write(struct.pack("<I", len(connect_info)))

                #     for conn_sid, verts_sub_idx, tangent_data in connect_info:
                #         f.write(struct.pack("<I", len(verts_sub_idx)))
                #         for v_idx in verts_sub_idx:
                #             f.write(struct.pack("<I", v_idx))
                #         f.write(struct.pack("<I", global_sector_map[conn_sid]))

                #         f.write(struct.pack("<I", len(tangent_data)))
                #         for dist, cross in tangent_data:
                #             f.write(
                #                 struct.pack("<ddd", cross[0], -cross[2], cross[1])
                #             )
                #             f.write(struct.pack("<d", dist))

                #     f.write(struct.pack("<I", 8001))  # 8001 固定标识
                #     for i in range(len(connect_info) - 1, -1, -1):
                #         f.write(struct.pack("<I", 8003))
                #         f.write(struct.pack("<I", 1))  # 隐藏面
                #         conn_sid, verts_sub_idx, tangent_data = connect_info[i]
                #         f.write(struct.pack("<I", i))
                #         edges_num = len(tangent_data)
                #         f.write(struct.pack("<I", edges_num))
                #         f.write(
                #             struct.pack(
                #                 f"<{'I'*edges_num}", *list(range(edges_num))
                #             )
                #         )

        # 写入外部光和聚光灯数据
        external_num = 0
        number_pos = f.tell()
        f.write(struct.pack("<I", 0))  # 占位
        ## 外部光
        for ext in scene_data.externals:
            if not ext.users_obj:
                continue

            color = ext.color
            vector = ext.vector.normalized()
            f.write(struct.pack("<I", 15002))
            f.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
            f.write(struct.pack("<f", color.v * v_factor))
            f.write(ext_light_p)
            f.write(struct.pack("<ddd", 0, 0, 0))
            f.write(bytes.fromhex("CD" * 8))
            f.write(struct.pack("<I", 0))
            f.write(struct.pack("<ddd", vector[0], -vector[2], vector[1]))
            ## 使用该外部光的扇区
            users_num = 0
            number_pos_2 = f.tell()
            f.write(struct.pack("<I", 0))  # 占位
            for i in ext.users_obj:
                sid = i.obj.amagate_data.get_sector_data().id
                # 如果扇区在导出列表中
                if global_sector_map.get(sid) is not None:
                    users_num += 1
                    f.write(struct.pack("<I", global_sector_map[sid]))
            stream_pos = f.tell()
            f.seek(number_pos_2)
            f.write(struct.pack("<I", users_num))
            f.seek(stream_pos)
            external_num += 1
        ## 聚光灯
        stream_pos = f.tell()
        f.seek(number_pos)
        f.write(struct.pack("<I", spot_num + external_num))
        f.seek(stream_pos)
        f.write(spot_buffer.getvalue())
        spot_buffer.close()

        ## 未知数据 地图边界？
        f.write(struct.pack("<ddd", 0, 0, 0))
        f.write(struct.pack("<ddd", 0, 0, 0))

        # 写入组数据
        f.write(group_buffer.getvalue())
        group_buffer.close()

        # 写入扇区名称数据
        f.write(struct.pack("<I", len(sector_ids)))
        f.write(sec_name_buffer.getvalue())
        sec_name_buffer.close()

    # 地图数据脚本
    map_dir = os.path.dirname(bpy.data.filepath)
    # 玩家位置
    player = bpy.data.objects.get("Player")
    if player is None:
        sec = sectors_dict[str(sector_ids[0])]["obj"]  # type: Object
        bbox_corners = [sec.matrix_world @ Vector(corner) for corner in sec.bound_box]
        center = sum(bbox_corners, Vector()) / 8
        player_pos = (center * 1000).to_tuple(0)  # 转换为毫米单位
    else:
        player_pos = (player.location * 1000).to_tuple(0)  # 转换为毫米单位
    player_pos = player_pos[0], -player_pos[2], player_pos[1]
    mapcfg = {
        "bw_file": os.path.basename(bw_file),
        "player_pos": player_pos,
    }
    with open(os.path.join(map_dir, "AG_MapCfg.py"), "w", encoding="utf-8") as file:
        file.write("# Automatically generated by Amagate\n\n")
        file.write("AG_MapCfg = ")
        pprint(mapcfg, stream=file, indent=0, sort_dicts=False)
    #
    with open(os.path.join(map_dir, "AG_dome.lvl"), "w", encoding="utf-8") as file:
        file.write("# Automatically generated by Amagate\n\n")
        if scene_data.sky_tex_enum != "-1":
            enum_items = scene_data.bl_rna.properties["sky_tex_enum"].enum_items  # type: ignore
            name = enum_items[int(scene_data.sky_tex_enum) - 1].description
            name = name.replace(" - Reforged", "")
            file.write(f"WorldDome -> {SKY_TEX_REFPATH[name]}")
    #
    with open(os.path.join(map_dir, "AG_Script.py"), "w", encoding="utf-8") as file:
        file.write("# Automatically generated by Amagate\n\n")
        file.write("import Bladex\n")
        file.write("import Raster\n\n")
        file.write("####\n")
        color = tuple(math.ceil(c * 255) for c in scene_data.sky_color)
        file.write(f"Raster.SetDomeColor{color}\n\n")
        #
        file.write("####\n")
        coll = (
            ("steep_auto", steep_auto_code),
            ("steep_yes", steep_yes_code),
            ("steep_no", steep_no_code),
        )
        for key, code in coll:
            pos_list = []
            for sec in locals()[key]:
                matrix_world = sec.matrix_world
                # 计算几何中心
                bbox_corners = [
                    matrix_world @ Vector(corner) for corner in sec.bound_box
                ]
                center = sum(bbox_corners, Vector()) / 8
                center = (center * 1000).to_tuple(0)
                pos_list.append((center[0], -center[2], center[1]))
            file.write(f"{key} = {pos_list}\n")
            file.write(code)
    # 地图运行脚本
    if with_run_script:
        scripts_dir = os.path.join(data.ADDON_PATH, "blade_scripts")
        for f in os.listdir(scripts_dir):
            shutil.copy(
                os.path.join(scripts_dir, f),
                os.path.join(os.path.dirname(bw_file), f),
            )
        # ag_utils.debugprint("Export Map (with Run Script)")

    # self.report({'WARNING'}, "Export Map Failed")
    this.report(
        {"INFO"},
        f"{pgettext('Export Map')} - {pgettext('Success')}:\n{global_vertex_count} {pgettext('Vertices')}, {global_face_count} {pgettext('Faces')}, {len(sector_ids)} {pgettext('Sectors')}",
    )
    return {"FINISHED"}


############################
############################ 导出地图操作
############################
class OT_ExportMapWithRunScript(bpy.types.Operator):
    bl_idname = "amagate.exportmap2"
    bl_label = "Export Map (with Run Script)"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        return export_map(self, context, with_run_script=True)


class OT_ExportMap(bpy.types.Operator):
    bl_idname = "amagate.exportmap"
    bl_label = "Export Map"
    bl_description = "Export Blade Map"
    bl_options = {"INTERNAL"}

    more: BoolProperty(default=False)  # type: ignore
    #

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.operator(OT_ExportMapWithRunScript.bl_idname)

    def execute(self, context: Context):
        return export_map(self, context)

    def invoke(self, context: Context, event):
        if self.more:
            return context.window_manager.invoke_popup(self, width=180)  # type: ignore
        else:
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
