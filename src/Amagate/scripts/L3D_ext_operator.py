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
logger = data.logger

epsilon: float = ag_utils.epsilon
epsilon2: float = ag_utils.epsilon2

COMPILE_STATUS = False

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
    layers_1 = [
        bm.faces.layers.int.get("amagate_connected"),
        bm.faces.layers.int.get("amagate_tex_id"),
        bm.faces.layers.float.get("amagate_tex_xpos"),
        bm.faces.layers.float.get("amagate_tex_ypos"),
        bm.faces.layers.float.get("amagate_tex_xzoom"),
        bm.faces.layers.float.get("amagate_tex_yzoom"),
        bm.faces.layers.float.get("amagate_tex_angle"),
        bm.faces.layers.float_vector.get("amagate_tex_vx"),
        bm.faces.layers.float_vector.get("amagate_tex_vy"),
    ]
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
    #
    if not cut_edges:
        print(f"\nNo cut edges")
        #
        # bm_mesh = bpy.data.meshes.new(f"AG.split")
        # bm.to_mesh(bm_mesh)
        # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
        # data.link2coll(bm_obj, bpy.context.scene.collection)
        # logger.debug(f"bisect_plane: {plane_no}, {plane_co}")
        #
        return bm, None  # type: ignore

    edge = cut_edges[0]
    if len(edge.link_faces) != 2:
        print(f"\nLink faces != 2, index: {edge.link_faces[0].index}")
        #
        # bm_mesh = bpy.data.meshes.new(f"AG.split")
        # bm.to_mesh(bm_mesh)
        # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
        # data.link2coll(bm_obj, bpy.context.scene.collection)
        #
        print(f"bisect_plane: {plane_no}, {plane_co}")
        #
        return bm, None  # type: ignore

    face1, face2 = edge.link_faces
    line_p1 = edge.verts[0].co.copy()
    line_p2 = edge.verts[1].co.copy()
    co = next(
        (
            v.co.copy()
            for v in face1.verts
            if v not in cut_verts
            and (geometry.intersect_point_line(v.co, line_p1, line_p2)[0] - v.co).length
            > 1e-4
        ),
        None,
    )
    if not co:
        return bm, None  # type: ignore
    pt, pct = geometry.intersect_point_line(co, line_p1, line_p2)
    dir = (co - pt).normalized()
    if plane_no.dot(dir) > 0:
        outer_face = face1
    else:
        outer_face = face2
    outer_faces = ag_utils.get_linked_flat_2d(outer_face, limit_edge=cut_edges)

    # 创建外部网格
    outer_bm = bmesh.new()
    layers_2 = [
        outer_bm.faces.layers.int.new("amagate_connected"),
        outer_bm.faces.layers.int.new("amagate_tex_id"),
        outer_bm.faces.layers.float.new("amagate_tex_xpos"),
        outer_bm.faces.layers.float.new("amagate_tex_ypos"),
        outer_bm.faces.layers.float.new("amagate_tex_xzoom"),
        outer_bm.faces.layers.float.new("amagate_tex_yzoom"),
        outer_bm.faces.layers.float.new("amagate_tex_angle"),
        outer_bm.faces.layers.float_vector.new("amagate_tex_vx"),
        outer_bm.faces.layers.float_vector.new("amagate_tex_vy"),
    ]
    verts_map = {}
    exist_edges = []
    for f in outer_faces:
        for v in f.verts:
            if v.index not in verts_map:
                verts_map[v.index] = outer_bm.verts.new(v.co)
    for f in outer_faces:
        new_face = outer_bm.faces.new([verts_map[v.index] for v in f.verts])
        # 复制属性
        for idx, layer in enumerate(layers_1):
            new_face[layers_2[idx]] = f[layer]  # type: ignore

    # 删除原始网格中的外部网格
    bmesh.ops.delete(bm, geom=outer_faces, context="FACES")
    #
    inner_bm = ag_utils.ensure_lookup_table(bm)
    outer_bm = ag_utils.ensure_lookup_table(outer_bm)

    return inner_bm, outer_bm


# 平展面分割
def flat_split(sec, bm, hole_dict):
    # type: (Object, bmesh.types.BMesh, dict[Any, Any]) -> Any
    global COMPILE_STATUS
    # cut_data_list = []
    #
    cut_data_buffer = []
    #
    stack = [(bm, [], -1)]
    while stack:
        bm, block_mark, cut_data_idx = stack.pop()
        bm.faces.ensure_lookup_table()
        conn_layer = bm.faces.layers.int.get("amagate_connected")
        layer_list = [
            bm.faces.layers.int.get("amagate_tex_id"),
            bm.faces.layers.float.get("amagate_tex_xpos"),
            bm.faces.layers.float.get("amagate_tex_ypos"),
            bm.faces.layers.float.get("amagate_tex_xzoom"),
            bm.faces.layers.float.get("amagate_tex_yzoom"),
            bm.faces.layers.float.get("amagate_tex_angle"),
            bm.faces.layers.float_vector.get("amagate_tex_vx"),
            bm.faces.layers.float_vector.get("amagate_tex_vy"),
        ]

        hole = next((f for f in bm.faces if f[conn_layer] != 0), None)  # type: ignore
        if hole:
            other_holes = [f for f in bm.faces if f != hole and f[conn_layer] != 0]  # type: ignore
        else:
            other_holes = []
        #
        if other_holes:
            verts_sort = {v: i for i, v in enumerate(hole.verts)}
            last_pair = {0, len(hole.verts) - 1}
            tangent_data = []
            normal = hole.normal.copy()

            # count += 1
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
                    conn_sid_2 = hole_2[conn_layer]  # type: ignore
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
                        [v1.co.copy(), tangent, dist, clean_hole, polluted_hole]
                    )
            ####
            # 切割平面
            clear_mark = True
            inner_cut = False
            while tangent_data:
                bm.faces.ensure_lookup_table()
                # 判断纹理一致性
                face = bm.faces[0]
                for layer in layer_list[:-2]:
                    if layer.name[12:] == "angle":
                        val_1 = round(face[layer], 3)  # type: ignore
                        is_tex_uniform = next((0 for f in bm.faces if round(f[layer], 3) != val_1), 1)  # type: ignore
                    else:
                        val_1 = face[layer]  # type: ignore
                        is_tex_uniform = next((0 for f in bm.faces if f[layer] != val_1), 1)  # type: ignore
                    if not is_tex_uniform:
                        break
                # 污染数量最少的排前面
                tangent_data.sort(key=lambda x: len(x[4]))
                # 清理数量最多的排前面
                tangent_data.sort(key=lambda x: -len(x[3]))
                #
                plane_co, tangent, dist, clean_hole, polluted_hole = tangent_data[0]
                bm, outer_bm = bisect_plane(bm, tangent, plane_co)
                if outer_bm is None:
                    COMPILE_STATUS = False
                    print(f"bisect_plane failed: {sec.name}")
                    if not inner_cut:
                        clear_mark = False
                    break
                cut_data_buffer.append(
                    struct.pack("<dddd", tangent[0], -tangent[2], tangent[1], dist)
                )
                if inner_cut:
                    stack.append(
                        (outer_bm, [8001 if is_tex_uniform else 8002], cut_data_idx)
                    )
                else:
                    block_mark.append(8001 if is_tex_uniform else 8002)
                    stack.append((outer_bm, block_mark, cut_data_idx))
                if not is_tex_uniform:
                    cut_data_idx = len(cut_data_buffer) - 1
                else:
                    cut_data_idx = -1
                # cut_data.append(((tangent[0], -tangent[2], tangent[1]), dist))
                #
                for i in range(len(tangent_data) - 1, 0, -1):
                    tangent_data[i][3].difference_update(clean_hole)
                    tangent_data[i][4].difference_update(clean_hole)
                    if not (tangent_data[i][3] or tangent_data[i][4]):
                        tangent_data.pop(i)
                tangent_data.pop(0)
                inner_cut = True
                # 更新bm属性
                conn_layer = bm.faces.layers.int.get("amagate_connected")
                layer_list = [
                    bm.faces.layers.int.get("amagate_tex_id"),
                    bm.faces.layers.float.get("amagate_tex_xpos"),
                    bm.faces.layers.float.get("amagate_tex_ypos"),
                    bm.faces.layers.float.get("amagate_tex_xzoom"),
                    bm.faces.layers.float.get("amagate_tex_yzoom"),
                    bm.faces.layers.float.get("amagate_tex_angle"),
                    bm.faces.layers.float_vector.get("amagate_tex_vx"),
                    bm.faces.layers.float_vector.get("amagate_tex_vy"),
                ]
            #
            if clear_mark:
                block_mark = []
        ####
        bm.faces.ensure_lookup_table()
        face = bm.faces[0]
        for layer in layer_list[:-2]:
            if layer.name[12:] == "angle":
                val_1 = round(face[layer], 3)  # type: ignore
                is_tex_uniform = next((0 for f in bm.faces if round(f[layer], 3) != val_1), 1)  # type: ignore
            else:
                val_1 = face[layer]  # type: ignore
                is_tex_uniform = next((0 for f in bm.faces if f[layer] != val_1), 1)  # type: ignore
            if not is_tex_uniform:
                break
        #
        if not is_tex_uniform:
            # logger.debug(layer.name)
            faces_dict = {}
            for f in bm.faces:
                if layer.name[12:] == "angle":
                    faces_dict.setdefault(round(f[layer], 3), []).append(f)  # type: ignore
                else:
                    faces_dict.setdefault(f[layer], []).append(f)  # type: ignore
            faces_list = [(k, list(v)) for k, v in faces_dict.items()]
            #
            faces_list.sort(key=lambda x: len(x[1]))
            val_1 = faces_list[0][0]
            face = faces_list[0][1][0]
            verts_sort = {v: i for i, v in enumerate(face.verts)}
            last_pair = {0, len(face.verts) - 1}
            normal = face.normal.copy()
            for edge in face.edges:
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
                # ag_utils.debugprint(f"tangent: {tangent}")
                #
                for face2 in bm.faces:
                    if layer.name[12:] == "angle":
                        val_2 = round(face2[layer], 3)  # type: ignore
                    else:
                        val_2 = face2[layer]  # type: ignore
                    if val_2 == val_1:
                        continue
                    is_polluted = next(
                        (
                            1
                            for v in face2.verts
                            if (v.co - v1.co).normalized().dot(tangent) > epsilon
                        ),
                        0,
                    )
                    if is_polluted:
                        inner_bm, outer_bm = bisect_plane(bm, tangent, v1.co)
                        if outer_bm is None:
                            COMPILE_STATUS = False
                            logger.error(f"tex bisect_plane failed: {sec.name}")
                            break
                        cut_data_buffer.append(
                            struct.pack(
                                "<dddd", tangent[0], -tangent[2], tangent[1], dist
                            )
                        )
                        block_mark.append(8002)
                        stack.append((outer_bm, block_mark, cut_data_idx))
                        stack.append((inner_bm, [], len(cut_data_buffer) - 1))

                        break
                # 如果没有发生break
                else:
                    continue
                break
        else:
            # 最终的块只剩下一个洞或1个纹纹理
            # bm_mesh = bpy.data.meshes.new(f"AG.split")
            # bm.to_mesh(bm_mesh)
            # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
            # data.link2coll(bm_obj, bpy.context.scene.collection)
            #
            bm.faces.ensure_lookup_table()
            if cut_data_idx != -1 or (not stack):
                face = bm.faces[0]
                tex_id = face[layer_list[0]]  # type: ignore
                img = L3D_data.get_texture_by_id(tex_id)[1]
                # tex_data = (img.name, face[layer_list[1]], face[layer_list[2]], face[layer_list[3]], face[layer_list[4]])  # type: ignore
                tex_vx = face[layer_list[6]]
                tex_vy = face[layer_list[7]]
                tex_vx = Vector((tex_vx[0], -tex_vx[2], tex_vx[1]))
                tex_vy = Vector((tex_vy[0], -tex_vy[2], tex_vy[1]))
                name = img.name.encode("utf-8")
                tex_buffer = b"".join(
                    (
                        struct.pack("<I", len(name)),
                        name,
                        struct.pack(
                            "<ddddddff",
                            *tex_vx,
                            *tex_vy,
                            face[layer_list[1]] / (0.001 * face[layer_list[3]]),
                            face[layer_list[2]] / (0.001 * face[layer_list[4]]),
                        ),
                    )
                )
                # 如果不是最后一个块
                if cut_data_idx != -1:
                    buffer = b"".join(
                        (
                            cut_data_buffer[cut_data_idx],
                            struct.pack("<II", 3, 0),
                            tex_buffer,
                            b"\x00" * 8,
                        )
                    )
                    cut_data_buffer[cut_data_idx] = buffer
            hole = next((f for f in bm.faces if f[conn_layer] != 0), None)  # type: ignore
            hole_fmt = ""
            hole_v = []
            if hole:
                hole_data = hole_dict[hole[conn_layer]]  # type: ignore
                tangent_idx = []
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
                hole_fmt = f"II{'I'*len(tangent_idx)}"
                hole_v = (hole_data["index"], len(tangent_idx), *tangent_idx)
                # cut_data.append((flag, hole_data["index"], tangent_idx))
            cut_data_buffer.append(
                struct.pack(
                    f"<{'I'*len(block_mark)}II{hole_fmt}",
                    *block_mark,
                    8003,
                    1 if hole else 0,
                    *hole_v,
                )
            )
            bm.free()
    #
    holes_data = [
        (v["index"], v["tangent"], v["verts_idx"], k) for k, v in hole_dict.items()
    ]
    holes_data.sort(key=lambda x: x[0])

    # print("\n".join(map(str, hole_dict.items())))
    # print("\n".join(map(str, cut_data)))
    return holes_data, cut_data_buffer, tex_buffer


def copy_flat(matrix_world, global_sector_map, group_faces, layer_list, conn_layer):
    # type: (Matrix, dict[int, int], list[bmesh.types.BMFace], list[bmesh.types.BMLayerItem],bmesh.types.BMLayerItem[int]|None) -> bmesh.types.BMesh
    bm_flat = bmesh.new()
    conn_layer_2 = bm_flat.faces.layers.int.new("amagate_connected")
    layer_list_2 = [
        bm_flat.faces.layers.int.new("amagate_tex_id"),
        bm_flat.faces.layers.float.new("amagate_tex_xpos"),
        bm_flat.faces.layers.float.new("amagate_tex_ypos"),
        bm_flat.faces.layers.float.new("amagate_tex_xzoom"),
        bm_flat.faces.layers.float.new("amagate_tex_yzoom"),
        bm_flat.faces.layers.float.new("amagate_tex_angle"),
        bm_flat.faces.layers.float_vector.new("amagate_tex_vx"),
        bm_flat.faces.layers.float_vector.new("amagate_tex_vy"),
    ]
    verts_map = {}
    for face in group_faces:
        for v in face.verts:
            if v.index not in verts_map:
                verts_map[v.index] = bm_flat.verts.new(matrix_world @ v.co)
    for face in group_faces:
        f_new = bm_flat.faces.new([verts_map[v.index] for v in face.verts])
        for idx, layer in enumerate(layer_list):
            f_new[layer_list_2[idx]] = face[layer]  # type: ignore

        conn_sid = face[conn_layer]  # type: ignore
        if conn_sid in global_sector_map:
            f_new[conn_layer_2] = conn_sid  # type: ignore
    bm_flat = ag_utils.ensure_lookup_table(bm_flat)
    return bm_flat


#
def export_map(
    this: bpy.types.Operator,
    context: Context,
    visible_only=False,
    with_run_script=False,
):
    global COMPILE_STATUS
    scene_data = context.scene.amagate_data
    # 检查是否为无标题文件
    if not bpy.data.filepath:
        this.report({"WARNING"}, "Please save the file first")
        return {"CANCELLED"}

    # 如果在编辑模式下，切换到物体模式并调用`几何修改回调`函数更新数据
    if "EDIT" in context.mode:
        objects_in_mode = context.objects_in_mode
        bpy.ops.object.mode_set(mode="OBJECT")
        sectors_in_mode = [obj for obj in objects_in_mode if obj.amagate_data.is_sector]
        if sectors_in_mode:
            L3D_data.geometry_modify_post(sectors_in_mode)
        L3D_data.update_scene_edit_mode()

    # 收集可见的凸扇区
    sectors_dict = scene_data["SectorManage"]["sectors"]
    sector_ids = [
        int(k)
        for k in sectors_dict
        if (not visible_only or sectors_dict[k]["obj"].visible_get())
        and sectors_dict[k]["obj"].amagate_data.get_sector_data().is_convex
    ]

    if not sector_ids:
        this.report({"WARNING"}, "No visible sector found")
        return {"CANCELLED"}
    sector_ids.sort()

    # 导出扇区
    ## blender坐标转换到blade: x,-z,y
    COMPILE_STATUS = True
    start_time = time.time()
    sec_total = len(sector_ids)
    bar_length = 20  # 进度条长度
    wm = bpy.context.window_manager
    wm.progress_begin(0, 1)  # 初始化进度条

    bw_file = f"{os.path.splitext(bpy.data.filepath)[0]}.bw"
    global_face_count = 0
    global_vertex_count = 0
    global_vertex_map = {}  # {tuple(co): global_index}
    sector_vertex_indices = {}  # 每个扇区的全局顶点索引映射
    global_sector_map = {sid: i for i, sid in enumerate(sector_ids)}  # 全局扇区映射
    #
    verts_buffer = BytesIO()  # 缓存顶点数据
    sec_buffer = BytesIO()  # 缓存扇区数据
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
        # number_pos = f.tell()
        # f.write(struct.pack("<I", 0))  # 占位
        # for i in sector_ids:
        #     sec = sectors_dict[str(i)]["obj"]  # type: Object
        #     sec_vertex_indices = []
        #     sec_data = sec.amagate_data.get_sector_data()
        #     mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        #     matrix_world = sec.matrix_world
        #     for v in mesh.vertices:
        #         # 变换顶点坐标并转换为毫米单位
        #         v_key = ((matrix_world @ v.co) * 1000).to_tuple(1)
        #         if v_key not in global_vertex_map:
        #             global_vertex_map[v_key] = global_vertex_count
        #             global_vertex_count += 1
        #             f.write(struct.pack("<ddd", v_key[0], -v_key[2], v_key[1]))
        #         sec_vertex_indices.append(global_vertex_map[v_key])
        #     sector_vertex_indices[sec_data.id] = sec_vertex_indices
        # # 暂存当前流位置并更正顶点数量
        # stream_pos = f.tell()
        # f.seek(number_pos)
        # f.write(struct.pack("<I", global_vertex_count))
        # f.seek(stream_pos)

        # 写入扇区数据
        # XXX 该明度系数只是近似效果，具体算法未知
        v_factor = 0.86264  # 明度系数
        ambient_light_p = bytes.fromhex("0000803C")  # 0.015625 环境光精度
        ext_light_p = bytes.fromhex("0000003D")  # 0.03125 外部灯光精度
        bulb_buffer = BytesIO()  # 缓存灯泡数据
        bulb_num = 0
        group_buffer = BytesIO()  # 缓存组数据
        sec_name_buffer = BytesIO()  # 缓存扇区名称数据
        steep_auto = []  # 自动陡峭
        steep_yes = []
        steep_no = []
        sec_buffer.write(struct.pack("<I", sec_total))
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for progress, sector_id in enumerate(sector_ids):
            # 进度条
            i = progress + 1
            percent = i / sec_total
            wm.progress_update(percent)
            #
            filled = int(bar_length * percent)
            bar = ("█" * filled).ljust(bar_length, "-")
            print(
                f"\rSector Compiling: |{bar}| {percent*100:.1f}% | {i} of {sec_total}",
                end="",
                flush=True,
            )
            #

            sec = sectors_dict[str(sector_id)]["obj"]  # type: Object
            sec_data = sec.amagate_data.get_sector_data()
            matrix_world = sec.matrix_world
            sec_mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            #
            # sec_vertex_indices = sector_vertex_indices[sec_data.id]
            evaluated_obj = sec.evaluated_get(depsgraph)
            mesh = evaluated_obj.data  # type: bpy.types.Mesh # type: ignore
            sec_bm = bmesh.new()
            sec_bm.from_mesh(mesh)
            sec_bm.faces.ensure_lookup_table()
            sec_bm.verts.ensure_lookup_table()
            flat_light_layer = sec_bm.faces.layers.int.get("amagate_flat_light")
            conn_layer = sec_bm.faces.layers.int.get("amagate_connected")
            tex_id_layer = sec_bm.faces.layers.int.get("amagate_tex_id")
            tex_vx_layer = sec_bm.faces.layers.float_vector.get("amagate_tex_vx")
            tex_vy_layer = sec_bm.faces.layers.float_vector.get("amagate_tex_vy")
            xpos_layer = sec_bm.faces.layers.float.get("amagate_tex_xpos")
            ypos_layer = sec_bm.faces.layers.float.get("amagate_tex_ypos")
            layer_list = [
                tex_id_layer,
                xpos_layer,
                ypos_layer,
                sec_bm.faces.layers.float.get("amagate_tex_xzoom"),
                sec_bm.faces.layers.float.get("amagate_tex_yzoom"),
                sec_bm.faces.layers.float.get("amagate_tex_angle"),
                tex_vx_layer,
                tex_vy_layer,
            ]

            # 灯泡
            if sec_data.bulb_light:
                bulb_num += len(sec_data.bulb_light)
                # bulb = None
                for bulb in sec_data.bulb_light:
                    light = bulb.light_obj  # type: Object
                    if light:
                        light_data = light.data  # type: bpy.types.Light # type: ignore
                        bulb_buffer.write(struct.pack("<I", 15001))
                        bulb_buffer.write(
                            struct.pack(
                                "<BBB", *(math.ceil(c * 255) for c in light_data.color)
                            )
                        )
                        bulb_buffer.write(struct.pack("<f", bulb.strength))
                        bulb_buffer.write(struct.pack("<f", bulb.precision))
                        pos = (light.matrix_world.translation * 1000).to_tuple(1)
                        bulb_buffer.write(struct.pack("<ddd", pos[0], -pos[2], pos[1]))
                        bulb_buffer.write(
                            struct.pack("<I", global_sector_map[sector_id])
                        )

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
            sec_buffer.write(struct.pack("<I", len(buffer)))
            sec_buffer.write(buffer)

            # 环境光
            color = sec_data.ambient_color
            sec_buffer.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
            sec_buffer.write(struct.pack("<f", color.v * v_factor))
            sec_buffer.write(ambient_light_p)
            sec_buffer.write(struct.pack("<ddd", 0, 0, 0))  # 未知用途 默认0
            sec_buffer.write(bytes.fromhex("CD" * 8))
            sec_buffer.write(struct.pack("<I", 0))

            # 平面光
            face = next((f for f in sec_bm.faces if f[flat_light_layer] == 1), None)  # type: ignore
            if face:
                vector = matrix_world.to_quaternion() @ -face.normal
                vector = vector[0], -vector[2], vector[1]
            else:
                vector = (0, 0, 0)
            color = sec_data.flat_light.color
            sec_buffer.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
            sec_buffer.write(struct.pack("<f", color.v * v_factor))
            sec_buffer.write(ambient_light_p)
            sec_buffer.write(struct.pack("<ddd", 0, 0, 0))  # # 未知用途 默认0
            sec_buffer.write(bytes.fromhex("CD" * 8))
            sec_buffer.write(struct.pack("<I", 0))
            ## 平面光向量
            sec_buffer.write(struct.pack("<ddd", *vector))

            # 面数据
            faces_sorted = []
            z_axis = Vector((0, 0, 1))

            conn_face_visited = set()
            # connect_num = 0
            for face_index, face in enumerate(sec_bm.faces):
                # if connect_num == sec_data.connect_num:
                #     break
                if face in conn_face_visited:
                    continue

                # connected_sid = mesh.attributes["amagate_connected"].data[face_index].value  # type: ignore
                # if connected_sid == 0 or global_sector_map.get(connected_sid) is None:
                #     continue

                connect_data = ()
                normal = matrix_world.to_quaternion() @ face.normal
                group_faces = ag_utils.get_linked_flat(face)
                conn_face_visited.update(group_faces)
                # 如果该平面只有一个面
                if len(group_faces) == 1:
                    conne_sid = face[conn_layer]  # type: ignore
                    # 如果没有连接或者连接的扇区不在导出列表中
                    if conne_sid == 0 or global_sector_map.get(conne_sid) is None:
                        if face[tex_id_layer] == -1:  # type: ignore
                            face_type = 7005  # 天空面
                        else:
                            face_type = 7001  # 普通面
                    else:
                        face_type = 7002  # 整个面是连接的
                        connect_data = (conne_sid,)
                    # verts_idx = [sec_vertex_indices[v.index] for v in face.verts]
                    # connect_num += 1
                # 如果该平面有多个面
                else:
                    conn_face_num = 0
                    hole_dict = {}  # type: Any
                    for face in group_faces:
                        conn_sid = face[conn_layer]  # type: ignore
                        if conn_sid == 0 or global_sector_map.get(conn_sid) is None:
                            continue
                        if conn_sid in hole_dict:
                            continue

                        face_conn = face
                        verts_sub_idx = []
                        for v in face_conn.verts:
                            v_key = ((matrix_world @ v.co) * 1000).to_tuple(0)
                            v_key = v_key[0], -v_key[2], v_key[1]
                            vert_idx = global_vertex_map.get(v_key)
                            if vert_idx is None:
                                vert_idx = global_vertex_map.setdefault(
                                    v_key, global_vertex_count
                                )
                                global_vertex_count += 1
                                verts_buffer.write(struct.pack("<ddd", *v_key))
                            verts_sub_idx.append(vert_idx)
                        hole_dict[conn_sid] = {
                            "index": conn_face_num,
                            "tangent": [],
                            "verts_idx": verts_sub_idx,
                        }
                        #
                        conn_face_num += 1
                    # 连接数量是0或1，判断纹理一致性
                    if conn_face_num < 2:
                        face = group_faces[0]
                        for layer in layer_list[:-2]:
                            if layer.name[12:] == "angle":
                                val_1 = round(face[layer], 3)  # type: ignore
                                is_tex_uniform = next((0 for f in group_faces if round(f[layer], 3) != val_1), 1)  # type: ignore
                            else:
                                val_1 = face[layer]  # type: ignore
                                is_tex_uniform = next((0 for f in group_faces if f[layer] != val_1), 1)  # type: ignore
                            if not is_tex_uniform:
                                face_type = 7004  # 平面中的多纹理
                                # 复制平面
                                bm_flat = copy_flat(
                                    matrix_world,
                                    global_sector_map,
                                    group_faces,
                                    layer_list,
                                    conn_layer,
                                )
                                connect_data = flat_split(sec, bm_flat, hole_dict)
                                break
                        # 没有发生break，纹理是一致的
                        else:
                            # 如果连接数量是1, 7003类型
                            if conn_face_num == 1:
                                face_type = 7003  # 平面中的单连接
                                #
                                # 按照顶点顺序计算切线
                                tangent_data = []  # 切线数据
                                # for idx, edge in enumerate(face_conn.edges):
                                #     # 跳过边界
                                #     if (
                                #         edge.link_faces[0].normal.dot(
                                #             edge.link_faces[1].normal
                                #         )
                                #         < epsilon2
                                #     ):
                                #         continue

                                #     co1 = matrix_world @ face_conn.verts[idx].co
                                #     co2 = (
                                #         matrix_world
                                #         @ face_conn.verts[
                                #             (idx + 1) % len(face_conn.verts)
                                #         ].co
                                #     )

                                verts_sub_idx_num = len(verts_sub_idx)
                                for i in range(verts_sub_idx_num):
                                    j = (i + 1) % verts_sub_idx_num

                                    co1 = matrix_world @ face_conn.verts[i].co
                                    co2 = matrix_world @ face_conn.verts[j].co
                                    cross = (co2 - co1).cross(normal)  # type: Vector
                                    cross.normalize()
                                    dist = (-co1).dot(cross) * 1000

                                    tangent_data.append((dist, cross))

                                connect_data = (face_conn[conn_layer], verts_sub_idx, tangent_data)  # type: ignore
                            # 如果连接数量是0
                            elif face[tex_id_layer] == -1:  # type: ignore
                                face_type = 7005  # 天空面
                            else:
                                face_type = 7001  # 普通面
                    # 连接数量大于1，直接为7004类型
                    else:
                        face_type = 7004  # 平面中的多连接
                        # 复制平面
                        bm_flat = copy_flat(
                            matrix_world,
                            global_sector_map,
                            group_faces,
                            layer_list,
                            conn_layer,
                        )
                        connect_data = flat_split(sec, bm_flat, hole_dict)
                # 获取凸壳顶点
                bm_convex = sec_bm.copy()
                group_faces_idx = [f.index for f in group_faces]
                bmesh.ops.delete(
                    bm_convex,
                    geom=[f for f in bm_convex.faces if f.index not in group_faces_idx],
                    context="FACES",
                )  # 删除非组面
                if len(group_faces) > 1:
                    bmesh.ops.dissolve_faces(
                        bm_convex, faces=list(bm_convex.faces), use_verts=False
                    )  # 合并组面
                ag_utils.unsubdivide(bm_convex)  # 反细分
                if len(bm_convex.faces) == 0:
                    bm_convex.free()
                    continue
                bm_convex.faces.ensure_lookup_table()
                # verts_idx = [
                #     global_vertex_map[((matrix_world @ v.co) * 1000).to_tuple(1)]
                #     for v in bm_convex.faces[0].verts
                # ]
                verts_idx = []
                for v in bm_convex.faces[0].verts:
                    v_key = ((matrix_world @ v.co) * 1000).to_tuple(0)
                    v_key = v_key[0], -v_key[2], v_key[1]
                    vert_idx = global_vertex_map.get(v_key)
                    if vert_idx is None:
                        vert_idx = global_vertex_map.setdefault(
                            v_key, global_vertex_count
                        )
                        global_vertex_count += 1
                        verts_buffer.write(struct.pack("<ddd", *v_key))
                    verts_idx.append(vert_idx)
                # 清理
                bm_convex.free()

                faces_sorted.append(
                    (face_index, verts_idx, normal, face_type, connect_data)
                )

            sec_bm.free()
            # ag_utils.debugprint(f"{sec.name}: {[i[0] for i in faces_sorted]}")
            # faces_sorted.sort(key=lambda x: -x[3]) # 连接面排前面
            # faces_sorted.sort(key=lambda x: x[2].to_tuple(3)) # 按法向排列
            faces_sorted.sort(
                key=lambda x: round(x[2].dot(-z_axis), 3)
            )  # 地板面排前面，避免滑坡问题

            # 如果不会被引擎设为滑坡且为自动模式
            if not sec_data.steep_check and sec_data.steep == "0":
                for item in faces_sorted:
                    cos = item[2].dot(z_axis)
                    # 与z轴点乘为0或负，跳过
                    if cos < epsilon:
                        continue
                    if cos < 0.7665:
                        steep_auto.append(sec)
                        break
            elif sec_data.steep == "1":
                steep_yes.append(sec)
            elif sec_data.steep == "2":
                steep_no.append(sec)

            global_face_count += len(faces_sorted)
            sec_buffer.write(struct.pack("<I", len(faces_sorted)))
            for (
                face_index,
                verts_idx,
                normal,
                face_type,
                connect_data,
            ) in faces_sorted:
                sec_buffer.write(struct.pack("<I", face_type))
                ## 法向
                # normal = matrix_world.to_quaternion() @ face.normal
                sec_buffer.write(struct.pack("<ddd", normal[0], -normal[2], normal[1]))
                sec_buffer.write(struct.pack("<d", mesh.attributes["amagate_v_dist"].data[face_index].value))  # type: ignore

                if face_type in (7002, 7005):
                    sec_buffer.write(struct.pack("<I", len(verts_idx)))
                    for v_idx in verts_idx:
                        sec_buffer.write(struct.pack("<I", v_idx))
                    if face_type == 7005:
                        continue
                    conn_sid = connect_data[0]
                    sec_buffer.write(struct.pack("<I", global_sector_map[conn_sid]))
                ## 固定标识
                sec_buffer.write(struct.pack("<I", 3))
                sec_buffer.write(struct.pack("<I", 0))

                # 写入纹理数据
                if face_type == 7004:
                    tex_buffer = connect_data[2]
                    sec_buffer.write(tex_buffer)
                else:
                    buffer = L3D_data.get_texture_by_id(mesh.attributes["amagate_tex_id"].data[face_index].value)[1].name.encode("utf-8")  # type: ignore
                    sec_buffer.write(struct.pack("<I", len(buffer)))
                    sec_buffer.write(buffer)
                    # if face_index == 1:
                    #     tex_vx = Vector((1, 0, 0)).normalized()/10
                    #     tex_vy = Vector((0, 0, 1)).normalized()/10
                    # else:
                    tex_vx = mesh.attributes["amagate_tex_vx"].data[face_index].vector  # type: ignore
                    tex_vy = mesh.attributes["amagate_tex_vy"].data[face_index].vector  # type: ignore
                    sec_buffer.write(
                        struct.pack("<ddd", tex_vx[0], -tex_vx[2], tex_vx[1])
                    )
                    sec_buffer.write(
                        struct.pack("<ddd", tex_vy[0], -tex_vy[2], tex_vy[1])
                    )
                    tex_xpos = mesh.attributes["amagate_tex_xpos"].data[face_index].value  # type: ignore
                    tex_ypos = mesh.attributes["amagate_tex_ypos"].data[face_index].value  # type: ignore
                    tex_xzoom = mesh.attributes["amagate_tex_xzoom"].data[face_index].value  # type: ignore
                    tex_yzoom = mesh.attributes["amagate_tex_yzoom"].data[face_index].value  # type: ignore
                    sec_buffer.write(
                        struct.pack(
                            "<ff",
                            tex_xpos / (0.001 * tex_xzoom),
                            tex_ypos / (0.001 * tex_yzoom),
                        )
                    )

                sec_buffer.write(b"\x00" * 8)  # 0
                #
                if face_type == 7002:
                    continue

                sec_buffer.write(struct.pack("<I", len(verts_idx)))
                for v_idx in verts_idx:
                    sec_buffer.write(struct.pack("<I", v_idx))
                #
                if face_type == 7003:
                    conn_sid, verts_sub_idx, tangent_data = connect_data
                    sec_buffer.write(struct.pack("<I", len(verts_sub_idx)))
                    for v_idx in verts_sub_idx:
                        sec_buffer.write(struct.pack("<I", v_idx))
                    sec_buffer.write(struct.pack("<I", global_sector_map[conn_sid]))

                    sec_buffer.write(struct.pack("<I", len(tangent_data)))
                    for dist, cross in tangent_data:
                        sec_buffer.write(
                            struct.pack("<ddd", cross[0], -cross[2], cross[1])
                        )
                        sec_buffer.write(struct.pack("<d", dist))
                #
                elif face_type == 7004:
                    holes_data, cut_data_buff, _ = connect_data
                    sec_buffer.write(struct.pack("<I", len(holes_data)))

                    for _, tangent_data, verts_sub_idx, conn_sid in holes_data:
                        sec_buffer.write(struct.pack("<I", len(verts_sub_idx)))
                        for v_idx in verts_sub_idx:
                            sec_buffer.write(struct.pack("<I", v_idx))
                        sec_buffer.write(struct.pack("<I", global_sector_map[conn_sid]))

                        sec_buffer.write(struct.pack("<I", len(tangent_data)))
                        for tx, ty, tz, dist in tangent_data:
                            sec_buffer.write(struct.pack("<ddd", tx, ty, tz))
                            sec_buffer.write(struct.pack("<d", dist))

                    while cut_data_buff:
                        sec_buffer.write(cut_data_buff.pop())

        # 写入外部光和灯泡数据
        external_num = 0
        number_pos = sec_buffer.tell()
        sec_buffer.write(struct.pack("<I", 0))  # 占位
        ## 外部光
        for ext in scene_data.externals:
            if not ext.users_obj:
                continue

            color = ext.color
            vector = ext.vector.normalized()
            precision = ext.data.shadow_maximum_resolution
            sec_buffer.write(struct.pack("<I", 15002))
            sec_buffer.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
            sec_buffer.write(struct.pack("<f", color.v * v_factor))
            sec_buffer.write(struct.pack("<f", precision))
            sec_buffer.write(struct.pack("<ddd", 0, 0, 0))
            sec_buffer.write(bytes.fromhex("CD" * 8))
            sec_buffer.write(struct.pack("<I", 0))
            sec_buffer.write(struct.pack("<ddd", vector[0], -vector[2], vector[1]))
            ## 使用该外部光的扇区
            users_num = 0
            number_pos_2 = sec_buffer.tell()
            sec_buffer.write(struct.pack("<I", 0))  # 占位
            for i in ext.users_obj:
                sid = i.obj.amagate_data.get_sector_data().id
                # 如果扇区在导出列表中
                if global_sector_map.get(sid) is not None:
                    users_num += 1
                    sec_buffer.write(struct.pack("<I", global_sector_map[sid]))
            stream_pos = sec_buffer.tell()
            sec_buffer.seek(number_pos_2)
            sec_buffer.write(struct.pack("<I", users_num))
            sec_buffer.seek(stream_pos)
            external_num += 1
        ## 灯泡
        stream_pos = sec_buffer.tell()
        sec_buffer.seek(number_pos)
        sec_buffer.write(struct.pack("<I", bulb_num + external_num))
        sec_buffer.seek(stream_pos)
        sec_buffer.write(bulb_buffer.getvalue())
        bulb_buffer.close()

        ## 未知数据 地图边界？
        sec_buffer.write(struct.pack("<ddd", 0, 0, 0))
        sec_buffer.write(struct.pack("<ddd", 0, 0, 0))

        # 写入组数据
        sec_buffer.write(group_buffer.getvalue())
        group_buffer.close()

        # 写入扇区名称数据
        sec_buffer.write(struct.pack("<I", sec_total))
        sec_buffer.write(sec_name_buffer.getvalue())
        sec_name_buffer.close()

        #
        f.write(struct.pack("<I", global_vertex_count))
        f.write(verts_buffer.getvalue())
        f.write(sec_buffer.getvalue())
        verts_buffer.close()
        sec_buffer.close()

    #
    wm.progress_end()
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
                mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                matrix_world = sec.matrix_world
                # 计算几何中心
                faces_center = [matrix_world @ f.center for f in mesh.polygons]
                center = sum(faces_center, Vector()) / len(faces_center)
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
        # ag_utils.debugprint("Compile to bw (with Run Script)")

    # self.report({'WARNING'}, "Compile to bw Failed")

    print(f", Done in {time.time() - start_time:.2f}s")
    if COMPILE_STATUS:
        this.report(
            {"INFO"},
            f"{pgettext('Compile Success')}:\n{global_vertex_count} {pgettext('Vertices')}, {global_face_count} {pgettext('Faces')}, {sec_total} {pgettext('Sectors')}",
        )
    else:
        this.report({"WARNING"}, f"{pgettext('Compile Exception')}")
    return {"FINISHED"}


############################
############################ 导出地图操作
############################
class OT_ExportMapOnlyVisible(bpy.types.Operator):
    bl_idname = "amagate.exportmap_visible"
    bl_label = "Compile to bw (Visible Only)"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        return export_map(self, context, visible_only=True)


class OT_ExportMapWithRunScript(bpy.types.Operator):
    bl_idname = "amagate.exportmap2"
    bl_label = "Compile to bw (with Run Script)"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        return export_map(self, context, with_run_script=True)


class OT_ExportMap(bpy.types.Operator):
    bl_idname = "amagate.exportmap"
    bl_label = "Compile to bw"
    bl_description = "Compile to Blade World"
    bl_options = {"INTERNAL"}

    more: BoolProperty(default=False)  # type: ignore
    #

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def draw(self, context):
        layout = self.layout
        column = layout.column()
        column.operator(OT_ExportMapOnlyVisible.bl_idname)
        column.operator(OT_ExportMapWithRunScript.bl_idname)

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
