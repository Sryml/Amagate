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

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene

############################
epsilon = 1e-5

############################


def get_selected_sectors() -> tuple[list[Object], Object]:
    """获得选中的扇区"""
    context = bpy.context
    selected_objects = context.selected_objects  # type: list[Object] # type: ignore
    if not selected_objects:
        return [], None  # type: ignore

    selected_sectors = [obj for obj in selected_objects if obj.amagate_data.is_sector]
    if selected_sectors:
        active_sector = (
            context.active_object
            if context.active_object in selected_sectors
            else selected_sectors[0]
        )
    else:
        active_sector = None

    return selected_sectors, active_sector  # type: ignore


# 判断凸物体
def is_convex(obj: Object):
    bm = bmesh.new()
    bm.from_mesh(obj.data)  # type: ignore

    # 融并内插面
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
            if face1 != face2 and 1 - abs(face2.normal.dot(normal)) < epsilon:
                # 判断是否在同一平面
                if abs(normal.dot(face2.verts[0].co) + D) < epsilon:
                    Faces.append(face2)
        if len(Faces) > 1:
            BMFaces.append(Faces)
    if BMFaces:
        for Faces in BMFaces:
            bmesh.ops.dissolve_faces(bm, faces=Faces, use_verts=True)
    # 重置面法向
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # type: ignore
    # 如果存在凹边，返回0，否则返回1
    ret = next((0 for i in bm.edges if not i.is_convex), 1)
    bm.free()
    print(f"is_convex: {ret}")
    return ret

    # 创建凸壳
    # ret = bmesh.ops.convex_hull(bm, input=bm.faces, use_existing_faces=True)  # type: ignore
    # bm.free()
    # 如果没有未参与凸壳计算的顶点，则为凸物体
    # return ret["geom_interior"] == []

    # bm.faces.ensure_lookup_table()
    # geom=[], geom_interior=[], geom_unused=[], geom_holes=[]
