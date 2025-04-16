# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import os
import subprocess
import sys
import locale
import ctypes
import time
import contextlib

import math
from typing import Any, TYPE_CHECKING
from io import StringIO, BytesIO

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


# Blender 的 Python 路径
python_exe = sys.executable

# 根据系统语言设置pip源
# 如果是中文系统,使用阿里云镜像源加快下载速度
# 否则使用默认pip源
if locale.setlocale(locale.LC_ALL, "").startswith("Chinese"):
    pip_index_url = "https://mirrors.aliyun.com/pypi/simple"
else:
    pip_index_url = ""

############################


# pyp安装进度定时器
def pyp_install_progress_timer(start_time, total_time=10.0, fps=24):
    interval = 1.0 / fps
    # 增量值
    increment = 1.0 / (total_time * fps)
    increment_fast = 1.0 / fps
    glob = {
        "increment": increment,
        "increment_fast": increment_fast,
        "installing": True,
        "success": False,
    }

    ####
    def warp():
        current_time = time.time()
        elapsed_time = current_time - start_time
        # 如果正在安装包，读取日志文件判断是否安装完成
        if elapsed_time > 3 and glob["installing"]:
            log_path = os.path.join(data.ADDON_PATH, "_LOG", "install_py_package.log")
            with open(log_path, "r") as f:
                installing = f.read().strip()
            # 如果安装完成，判断是否安装成功
            if installing == "0":
                glob["installing"] = False

                try:
                    import cvxpy
                    import ecos

                    glob["success"] = True
                except ImportError:
                    data.PY_PACKAGES_INSTALLING = False
                    return None
            # 超时情况
            elif elapsed_time > 180:
                data.PY_PACKAGES_INSTALLING = False
                return None

        scene_data = bpy.context.scene.amagate_data
        pre_v = scene_data.progress_bar.pyp_install_progress

        # 如果安装完成，加快进度条速度
        if glob["success"]:
            increment = glob["increment_fast"]
        elif pre_v >= 0.95:
            increment = 0.0
        else:
            increment = glob["increment"]

        new_v = min(1.0, pre_v + increment)
        scene_data.progress_bar.pyp_install_progress = new_v
        if new_v == 1.0:
            data.PY_PACKAGES_INSTALLING = False
            data.PY_PACKAGES_INSTALLED = True
            return None
        else:
            return interval

    ####
    return warp


# 安装包
def install_packages(packages_name):
    # 设置安装状态
    data.PY_PACKAGES_INSTALLING = True
    log_path = os.path.join(data.ADDON_PATH, "_LOG", "install_py_package.log")
    with open(log_path, "w") as f:
        # 日志写入1表示正在安装中，0表示安装结束
        f.write("1")

    # 启动进度条
    bpy.app.timers.register(
        pyp_install_progress_timer(time.time()),  # type: ignore
        first_interval=0.1,
    )

    # 开始安装
    # 检查是否设置了pip镜像源，根据设置，构建pip命令参数
    if pip_index_url:
        args = f" -i {pip_index_url}"
    else:
        args = ""
    # 构建命令行命令
    combined_cmd = f'"{python_exe}" -m pip install {" ".join(packages_name)}{args}'
    # f"{python_exe} -m pip install --no-cache-dir {' '.join(packages_name)}{args}"
    # 写入批处理文件
    bat_path = os.path.join(data.ADDON_PATH, "_BAT", "install_py_package.bat")
    with open(bat_path, "w") as f:
        f.write(f"{combined_cmd}\n")
        f.write("@timeout /t 2 /nobreak > nul\n")
        f.write(f'@echo 0 > "{log_path}"\n')
        f.write("@echo install_py_package.bat done.")

    # 调用子进程执行批处理文件
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        shell=True,
        # creationflags=subprocess.CREATE_NO_WINDOW,  # 彻底不显示窗口
        # stdin=subprocess.PIPE,
        # stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE,
    )

    # python.exe -m pip uninstall MarkupSafe joblib scs jinja2 ecos clarabel osqp cvxpy -y


# 定义 Windows API 中的 keybd_event 函数
def simulate_keypress(keycode: int):
    # 0x1B 是 Esc 键的虚拟键码

    # 定义 keybd_event 参数
    # 按下键
    ctypes.windll.user32.keybd_event(keycode, 0, 0, 0)
    time.sleep(0.01)  # 按键按下后等待一段时间

    # 释放键
    ctypes.windll.user32.keybd_event(keycode, 0, 2, 0)


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


# 判断物体拓扑类型是否为二维球面
def is_2d_sphere(obj: Object):
    """判断物体拓扑类型是否为二维球面"""
    sec_data = obj.amagate_data.get_sector_data()
    mesh = obj.data  # type: bpy.types.Mesh # type: ignore
    # 检查欧拉特征
    euler_characteristic = len(mesh.vertices) - len(mesh.edges) + len(mesh.polygons)
    if euler_characteristic != 2:
        return False
    return True


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
    geom_holes = convex_hull["geom_holes"]  # type: list[bmesh.types.BMFace]
    # 如果没有未参与凸壳计算的顶点，则为凸多面体
    convex = geom_interior == []
    # print(convex_hull['geom'])
    # print("geom_interior", [v.index for v in convex_hull["geom_interior"]])
    # print("geom_unused", [i.index for i in convex_hull["geom_unused"]])
    # print("geom_holes", [i.index for i in convex_hull["geom_holes"]])

    def get_vert_index(verts) -> list[int]:
        vert_index = []
        # 遍历未参与凸壳计算的顶点
        for v in verts:
            idx = vert_map.get(v.co.to_tuple(4), None)
            if idx is None:
                print(f"error: {v.co.to_tuple(4)} not in vert_map")
                vert_index = []
                break
            vert_index.append(idx)
        return vert_index

    # 如果不是凸多面体
    if not convex:
        ########
        verts_index = []
        # proj_normal = None
        concave_type = CONCAVE_T_NONE
        ########

        # 获取准确的内部顶点，geom_interior并不准确
        verts_exterior = set(v for f in geom_holes for v in f.verts)
        verts_ext_idx = get_vert_index(verts_exterior)
        # 如果找不到对应顶点，也就是出错了，归为复杂凹多面体
        if not verts_ext_idx:
            concave_type = CONCAVE_T_COMPLEX
        else:
            geom_interior = [v for v in sec_bm.verts if v.index not in verts_ext_idx]
            verts_index = [v.index for v in geom_interior]

            # 判断内部顶点是否共面
            is_interior_coplanar = True
            if len(geom_interior) > 2:
                pt = geom_interior[0].co
                dir1 = geom_interior[1].co - pt
                normal = None  # type: Vector # type: ignore
                for v in geom_interior[2:]:
                    dir2 = v.co - pt
                    normal2 = dir1.cross(dir2).normalized()  # type: Vector
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

            # 内部顶点共面的情况
            if is_interior_coplanar:
                concave_type = CONCAVE_T_SIMPLE

        sec_data["ConcaveData"] = {
            "verts_index": verts_index,
            # "proj_normal": proj_normal,
            "concave_type": concave_type,
        }

    # geom=[], geom_interior=[], geom_unused=[], geom_holes=[]
    sec_bm.free()
    bm.free()
    return convex


# 删除扇区
def delete_sector(obj: Object | Any = None, id_key: str | Any = None):
    """删除扇区"""
    scene_data = bpy.context.scene.amagate_data
    SectorManage = scene_data["SectorManage"]

    if not obj:
        if not id_key:
            return
        obj = SectorManage["sectors"][id_key]["obj"]

    sec_data = obj.amagate_data.get_sector_data()
    mesh = obj.data  # type: bpy.types.Mesh # type: ignore
    id_key = str(sec_data.id)

    if mesh.users == 1:
        bpy.data.meshes.remove(mesh)
    else:
        bpy.data.objects.remove(obj)
    #
    for l in SectorManage["sectors"][id_key]["light_objs"]:
        l.hide_viewport = True
    #
    atmo = data.get_atmo_by_id(scene_data, SectorManage["sectors"][id_key]["atmo_id"])[
        1
    ]
    if atmo:
        atmo.users_obj.remove(atmo.users_obj.find(id_key))
    #
    external = data.get_external_by_id(
        scene_data, SectorManage["sectors"][id_key]["external_id"]
    )[1]
    if external:
        external.users_obj.remove(external.users_obj.find(id_key))
    #
    if int(id_key) != SectorManage["max_id"]:
        SectorManage["deleted_id_count"] += 1
    else:
        SectorManage["max_id"] -= 1
    SectorManage["sectors"].pop(id_key)


############################
############################
############################
