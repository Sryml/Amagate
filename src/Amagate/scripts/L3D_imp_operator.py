# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

#
import struct
import math
import os
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

############################
logger = data.logger

epsilon: float = ag_utils.epsilon
epsilon2: float = ag_utils.epsilon2
############################


def unpack(fmat: str, f) -> Any:
    fmat_ = fmat.lower()
    if fmat_[-1] == "s":
        chunk = int(fmat_[:-1])
    else:
        chunk = (
            fmat_.count("i") * 4
            + fmat_.count("f") * 4
            + fmat_.count("d") * 8
            + fmat_.count("b")
        )

    if fmat_[-1] == "s":
        return struct.unpack(fmat, f.read(chunk))[0].decode("Latin1")
    return struct.unpack(fmat, f.read(chunk))


# 验证bw文件完整性
def verify_bw(bw_file):
    pass


# 分割洞
def hole_split(sec_bm, face, tangent_data):
    geom = list(face.verts) + list(face.edges) + [face]
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
        edge = cut_edges[0]
        face1, face2 = edge.link_faces
        co = next((v.co for v in face1.verts if v not in cut_verts), None)
        dir = (co - edge.verts[0].co).normalized()  # type: ignore
        if plane_no.dot(dir) < 0:
            inner_face = face1
        else:
            inner_face = face2
        geom = list(inner_face.verts) + list(inner_face.edges) + [inner_face]
    return inner_face


# 平展面分割
def flat_split(sec_bm, face, cut_data, layers):
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
                edge = cut_edges[0]
                face1, face2 = edge.link_faces
                co = next((v.co for v in face1.verts if v not in cut_verts), None)
                dir = (co - edge.verts[0].co).normalized()  # type: ignore
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
                    inner_face = hole_split(sec_bm, inner_face, tangent_data)
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
    tex_xzoom = 1 / tex_vx.length
    tex_yzoom = 1 / tex_vy.length
    tex_xpos *= 0.001 * tex_xzoom
    tex_ypos *= 0.001 * tex_yzoom

    dot = normal.dot(z_axis)
    # 计算纹理角度
    if dot > epsilon2 or dot < -epsilon2:
        vector_map = -x_axis.copy()
    else:
        vector_map = (normal.to_track_quat("-Y", "Z") @ x_axis).normalized()
    axis = tex_vx.cross(vector_map).normalized()  # type: Vector
    dot2 = tex_vx.dot(vector_map)
    if dot2 > epsilon2:
        tex_angle = 0
    elif dot2 < -epsilon2:
        tex_angle = math.pi
    else:
        tex_angle = math.acos(dot2)
    if axis.dot(normal) < -epsilon:
        tex_angle = -tex_angle
    # 判断纹理类型
    if dot > epsilon:
        tex_type = "Floor"
    elif dot < -epsilon:
        tex_type = "Ceiling"
    else:
        tex_type = "Wall"

    #
    tex_data = global_texture_map.get(texture_name)
    if tex_data is None:
        filepath = os.path.join(data.ADDON_PATH, "textures", "test.bmp")
        tex_data = OP_L3D.OT_Texture_Add.load_image(filepath, texture_name)
        tex_data.id_data.filepath = f"//textures/{texture_name}.bmp"
        global_texture_map[texture_name] = tex_data
    tex_id = tex_data.id
    slot_index = sec_mesh.materials.find(tex_data.mat_obj.name)
    if slot_index == -1:
        sec_mesh.materials.append(tex_data.mat_obj)
        slot_index = sec_mesh.materials.find(tex_data.mat_obj.name)
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


# 导入地图
def import_map(bw_file):
    scene_data = bpy.context.scene.amagate_data
    # 全局数据索引
    global_vertex_count = 0
    global_vertex_map = {}  # {global_index: tuple(co)}
    global_atmo_map = {}
    global_texture_map = {}
    atmos_name_len = []
    #
    v_factor = 0.86264  # 明度系数
    #
    x_axis = Vector((1, 0, 0))
    y_axis = Vector((0, 1, 0))
    z_axis = Vector((0, 0, 1))
    #
    context = bpy.context
    with open(bw_file, "rb") as f:
        # 创建大气
        atmo_num = unpack("<I", f)[0]
        for i in range(atmo_num):
            name_len = unpack("<I", f)[0]
            name = unpack(f"{name_len}s", f)
            rgb = unpack("<BBB", f)
            a = unpack("<f", f)[0]
            item = OP_L3D.OT_Scene_Atmo_Add.add(context)
            item["_item_name"] = name
            item.color = (*[i / 255 for i in rgb], a)
            global_atmo_map[name] = item.id
            atmos_name_len.append(name_len)

        # 全局顶点映射
        vertex_num = unpack("<I", f)[0]
        for i in range(vertex_num):
            vert = unpack("<ddd", f)
            vert = [i / 1000 for i in vert]
            vert = vert[0], vert[2], -vert[1]
            global_vertex_map[global_vertex_count] = vert
            global_vertex_count += 1

        # 扇区
        sector_num = unpack("<I", f)[0]
        for i in range(sector_num):
            # 扇区ID # XXX
            sid = i + 1
            #
            sec_mesh = bpy.data.meshes.new(f"Sector{sid}")
            sec = bpy.data.objects.new(
                f"Sector{sid}", sec_mesh
            )  # type: Object # type: ignore
            sec.amagate_data.set_sector_data()
            sec_data = sec.amagate_data.get_sector_data()
            sec_data.id = sid
            sec_vertex_map = {}

            #
            hole_split_list = []
            flat_split_list = []
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
                distance = unpack("<d", f)[0]  # XXX 是否需要？

                # 完全连接或天空面的情况
                if face_type in (7002, 7005):
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
                    # 跳过天空面
                    if face_type == 7005:
                        face[layers["tex_id"]] = -1
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
                            holes_idx_data = []
                            holes_num = unpack("<I", f)[0]
                            for i in range(holes_num):
                                hole_idx = unpack("<I", f)[0]
                                tangent_num = unpack("<I", f)[0]
                                tangent_data = [
                                    holes_data[hole_idx][0][unpack("<I", f)[0]]
                                    for i in range(tangent_num)
                                ]
                                conn_sid = holes_data[hole_idx][1]
                                holes_idx_data.append((tangent_data, conn_sid))
                            cut_data.append((mark, tangent_data, conn_sid))
                            if holes_num > 1:
                                logger.debug(f"Multi-hole cut: {holes_idx_data}")
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
                        holes_num = unpack("<I", f)[0]
                        for i in range(holes_num):
                            hole_idx = unpack("<I", f)[0]
                            tangent_num = unpack("<I", f)[0]
                            tangent_data = [
                                holes_data[hole_idx][0][unpack("<I", f)[0]]
                                for i in range(tangent_num)
                            ]
                            conn_sid = holes_data[hole_idx][1]
                            # inner_face = hole_split(sec_bm, face, tangent_data)
                            # inner_face[layers["connected"]] = holes_data[hole_idx][1]
                            hole_split_list.append((face, tangent_data, conn_sid))
                            sec_data.connect_num += 1
                    # 切割
                    else:
                        flat_split_list.append((face, cut_data))
                        # flat_split(sec_bm, face, cut_data, layers)

            # 切割
            # for face, tangent_data, conn_sid in hole_split_list:
            #     try:
            #         inner_face = hole_split(sec_bm, face, tangent_data.copy())
            #         inner_face[layers["connected"]] = conn_sid
            #     except:
            #         if len(tangent_data) > 1:
            #             logger.error(
            #                 f"Hole Split Error: {len(tangent_data)}, {sec_data.id}"
            #             )
            # for face, cut_data in flat_split_list:
            #     try:
            #         flat_split(sec_bm, face, cut_data, layers)
            #     except:
            #         logger.error(f"Flat Split Error: {cut_data}, {sec_data.id}")
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
            sec_bm.to_mesh(sec_mesh)
            sec_bm.free()
            # 有限融并
            # ag_utils.dissolve_limit_sectors([sec], check_convex=False)
            # 添加修改器
            modifier = sec.modifiers.new("", type="NODES")
            modifier.node_group = scene_data.sec_node  # type: ignore
            # 添加到扇区管理字典
            scene_data["SectorManage"]["sectors"][str(sid)] = {
                "obj": sec,
                "atmo_id": 0,
                "external_id": 0,
            }
            #
            sec_data.atmo_id = global_atmo_map[atmo_name]
            sec_data.ambient_color = ambient_color
            sec_data.flat_light.color = flat_color
            sec_data.is_2d_sphere = ag_utils.is_2d_sphere(sec)
            sec_data.is_convex = ag_utils.is_convex(sec)
            sec.amagate_data.is_sector = True
            #
            coll = L3D_data.ensure_collection(L3D_data.S_COLL)
            data.link2coll(sec, coll)

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
        for sid in range(1, sector_num + 1):
            sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
            sec_data = sec.amagate_data.get_sector_data()
            group = unpack("<i", f)[0]  # 有符号整数
            sec_data.group = group
        # 扇区名称数据
        sector_num = unpack("<I", f)[0]
        for sid in range(1, sector_num + 1):
            sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
            name_len = unpack("<I", f)[0]
            name = unpack(f"{name_len}s", f)
            sec.rename(name, mode="ALWAYS")
            sec.data.rename(name, mode="ALWAYS")

    ############################
    logger.debug("Import Map Done")
    return True


############################
############################ 导入地图操作
############################


def draw_dirty(self, context: Context):
    layout = self.layout  # type: bpy.types.UILayout
    # layout.use_property_decorate = True
    scene_data = context.scene.amagate_data

    row = layout.row()
    row.label(text="Save changes before closing?")

    row = layout.row()
    op = row.operator(OT_ImportMap.bl_idname, text="Save")
    op.execute_type = 1  # type: ignore
    row.operator(OT_ImportMap.bl_idname, text="Don't Save").execute_type = 2  # type: ignore
    row.operator(OT_ImportMap.bl_idname, text="Cancel").execute_type = 3  # type: ignore


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
    relative_path: BoolProperty(name="Relative Path", default=True)  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty()  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    # execute_type: IntProperty(default=0)  # type: ignore

    # @classmethod
    # def poll(cls, context: Context):
    #     return context.scene.amagate_data.is_blade and context.area.type == "VIEW_3D"

    def execute(self, context):
        file_name = next(
            (f.name for f in self.files if f.name[-3:].lower() == ".bw"), None
        )
        if not file_name:
            self.report({"ERROR"}, "No bw file selected")
            return {"CANCELLED"}

        filepath = os.path.join(self.directory, file_name)
        import_map(filepath)

        # bpy.ops.wm.read_homefile(app_template="")
        return {"FINISHED"}

    def invoke(self, context, event):
        # if self.execute_type == 0:
        #     if bpy.data.is_dirty:
        #         context.window_manager.popup_menu(draw_dirty)
        #         return {"FINISHED"}
        # elif self.execute_type == 1:  # Save
        #     logger.debug("Save")
        #     # ag_utils.simulate_keypress(27)
        #     ret = bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")  # type: ignore
        #     if ret != {"FINISHED"}:
        #         return ret
        # elif self.execute_type == 2:  # Don't Save
        #     # ag_utils.simulate_keypress(27)
        #     pass
        # elif self.execute_type == 3:  # Cancel
        #     ag_utils.simulate_keypress(27)
        #     return {"CANCELLED"}

        self.filepath = "//"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


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
