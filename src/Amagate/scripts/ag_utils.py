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
import importlib
import contextlib
import math
import requests
import zipfile
import tempfile
import typing
import struct

from typing import Any, TYPE_CHECKING
from io import StringIO, BytesIO

#
import numpy as np

#
import bpy
import bmesh
from mathutils import *  # type: ignore

#
from . import data, L3D_data

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection

############################
epsilon: float = 1e-5
epsilon2: float = 1 - epsilon

logger = data.logger


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


#
K_ESC = 27

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
def pyp_install_progress_timer(start_time, total_time=25.0, fps=24, timeout=180):
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
        scene_data = bpy.context.scene.amagate_data
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
                    for m in data.PY_PACKAGES_REQUIRED:
                        importlib.import_module(m)

                    glob["success"] = True
                except ImportError:
                    data.PY_PACKAGES_INSTALLING = False
                    data.area_redraw("VIEW_3D")
                    return None
            # 超时情况
            elif elapsed_time > timeout:
                scene_data.progress_bar.pyp_install_progress = 0
                data.PY_PACKAGES_INSTALLING = False
                data.area_redraw("VIEW_3D")
                return None

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
            # data.area_redraw("VIEW_3D")
            return None
        else:
            return interval

    ####
    return warp


# 安装包
def install_packages():
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
    # 构建命令
    target = bpy.utils.user_resource("SCRIPTS", path="site-packages", create=True)
    requirements = os.path.join(data.ADDON_PATH, "_BAT", "requirements.txt")
    combined_cmd = f'"{python_exe}" -m pip install --no-deps --target="{target}" -r "{requirements}"{args}'
    # --no-cache-dir
    # 写入批处理文件
    bat_path = os.path.join(data.ADDON_PATH, "_BAT", "install_py_package.bat")
    with open(bat_path, "w") as f:
        f.write(f"{combined_cmd}\n")
        f.write("@timeout /t 2 /nobreak > nul\n")
        f.write(f'@echo 0 > "{log_path}"\n')
        f.write("@echo install_py_package.bat done.")

    # 调用子进程执行批处理文件
    subprocess.Popen(
        bat_path,
        shell=True,
        # creationflags=subprocess.CREATE_NO_WINDOW,  # 彻底不显示窗口
        # stdin=subprocess.PIPE,
        # stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE,
    )

    # python.exe -m pip uninstall MarkupSafe joblib scs jinja2 ecos clarabel osqp cvxpy -y
    # python.exe -m pip uninstall scipy -y


def debugprint(*args, **kwargs):
    if data.DEBUG:
        print("[DEBUG]", *args, **kwargs)


# 定义 Windows API 中的 keybd_event 函数
def simulate_keypress(keycode: int):
    # 0x1B 是 Esc 键的虚拟键码

    # 定义 keybd_event 参数
    # 按下键
    ctypes.windll.user32.keybd_event(keycode, 0, 0, 0)
    # time.sleep(0.01)  # 按键按下后等待一段时间

    # 释放键
    bpy.app.timers.register(
        lambda keycode=keycode: (
            ctypes.windll.user32.keybd_event(keycode, 0, 2, 0),
            None,
        )[-1],
        first_interval=0.01,
    )
    # ctypes.windll.user32.keybd_event(keycode, 0, 2, 0)


# 获取相连的平展面
def get_linked_flat(face, bm=None, check_conn=False, limit_edge=[]):  # type: ignore
    # type: (bmesh.types.BMFace, bmesh.types.BMesh, bool, list[bmesh.types.BMEdge]) -> list[bmesh.types.BMFace]
    visited = []  # type: list[bmesh.types.BMFace]
    stack = [face]  # type: list[bmesh.types.BMFace]
    normal = face.normal.copy()

    while stack:
        f = stack.pop()
        if f not in visited:
            visited.append(f)

            for e in f.edges:
                if e in limit_edge:
                    continue
                for f2 in e.link_faces:
                    if f2 not in visited:  # 避免重复访问
                        if (
                            f2.normal.dot(normal) > epsilon2
                        ):  # 使用阈值来判断法线是否相同
                            stack.append(f2)
    # 获取存在连接的平展面，如果没有连接就返回自身
    if check_conn:
        layers = bm.faces.layers.int.get("amagate_connected")
        bm.faces.ensure_lookup_table()
        for face in visited:
            if face[layers] != 0:  # type: ignore
                break
        # 如果没有发生break，也就是没有连接
        else:
            return [face]

    return visited


# 获取相连的平展面 (2d)
def get_linked_flat_2d(face, limit_edge=[]):  # type: ignore
    # type: (bmesh.types.BMFace, list[bmesh.types.BMEdge]) -> list[bmesh.types.BMFace]
    visited = []  # 初始化已访问集合
    stack = [face]  # type: list[bmesh.types.BMFace]

    while stack:
        f = stack.pop()
        if f not in visited:
            visited.append(f)

            for e in f.edges:
                if e in limit_edge:
                    continue
                for f2 in e.link_faces:
                    if f2 not in visited:  # 避免重复访问
                        stack.append(f2)
    return visited


# 获取在同一直线的相连边
def get_edges_along_line(edge, limit_face=None):  # type: ignore
    # type: (bmesh.types.BMEdge, bmesh.types.BMFace) -> list[int]
    co = (edge.verts[0].co + edge.verts[1].co) / 2.0
    dir = (edge.verts[1].co - co).normalized()
    visited = []  # type: list[int]
    stack = [edge]  # type: list[bmesh.types.BMEdge]

    while stack:
        e = stack.pop()
        if e.index not in visited:
            visited.append(e.index)

            for v in e.verts:
                for e2 in v.link_edges:
                    if e2.index in visited:  # 避免重复访问
                        continue
                    if limit_face and limit_face not in e2.link_faces:
                        continue
                    dir2 = (v.co - e2.other_vert(v).co).normalized()  # type: Vector
                    if abs(dir.dot(dir2)) > epsilon2:
                        stack.append(e2)
    return visited


# 获取共线的子顶点
def get_sub_verts_along_line(vert, dir):
    # type: (bmesh.types.BMVert, Vector) -> tuple[list[bmesh.types.BMVert], bmesh.types.BMVert]
    visited = []
    endpoint = None  # type: bmesh.types.BMVert # type: ignore
    stack = [vert]  # type: list[bmesh.types.BMVert]

    while stack:
        v = stack.pop()
        if v not in visited:
            visited.append(v)

            for e in v.link_edges:
                v2 = e.other_vert(v)  # type: bmesh.types.BMVert
                if v2 in visited:  # 避免重复访问
                    continue

                link_num = len(v2.link_edges)
                if link_num > 2:
                    endpoint = v
                    continue
                elif link_num == 2:
                    edge2 = v2.link_edges[0]
                    if edge2 == e:
                        edge2 = v2.link_edges[1]

                    v3 = edge2.other_vert(v2)  # type: bmesh.types.BMVert
                    dir2 = (v2.co - v3.co).normalized()
                    # 如果连接边等于2且另一条边不共线，说明是端点
                    if abs(dir2.dot(dir)) < 0.999999:
                        endpoint = v
                        continue

                stack.append(v2)

    return visited, endpoint


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


# 获取投影法线
def get_project_normal(internal_v, external_v, tolerance=1e-5) -> Any:
    # 延迟导入
    from scipy.optimize import minimize

    # 转换为numpy数组
    V_INT = np.array(internal_v)
    V_INT_UNIQUE = []
    for v1 in internal_v:
        for v2 in V_INT_UNIQUE:
            # 去重
            if v1.dot(v2) > epsilon2:
                break
        else:
            V_INT_UNIQUE.append(v1)
    V_INT_UNIQUE = np.array(V_INT_UNIQUE)

    V_EXT = np.array(external_v)

    def objective(u):
        return max(-np.dot(V_INT_UNIQUE, u))  # 最大负点积

    # 初始猜测（如平均向量归一化）
    initial_guess = np.mean(V_INT_UNIQUE, axis=0)
    norm = np.linalg.norm(initial_guess)
    if norm < 1e-6:
        # debugprint("norm is too small, use svd")
        initial_guess = np.linalg.svd(V_INT_UNIQUE)[2][0]
    else:
        initial_guess /= norm

    # 最小化最大负点积
    result = minimize(
        objective,
        initial_guess,
        constraints={"type": "eq", "fun": lambda u: np.linalg.norm(u) - 1},
        method="SLSQP",
        # options={'ftol': 1e-8, 'eps': 1e-8}
    )
    if result.success:
        u = result.x / np.linalg.norm(result.x)  # 确保严格单位长度
        # 取反，得到投影法向
        proj_normal_init = -u  # type: Any
        max_dot = max(np.dot(V_INT_UNIQUE, proj_normal_init))
        # 无效法向，与内部向量的点积存在大于0的情况
        if max_dot > tolerance:
            # 查找两个近似垂直的内部向量
            v_int = []
            for v in V_INT_UNIQUE:
                count = len(v_int)
                if count == 2:
                    break
                if count == 1:
                    # 如果与第一个向量平行，跳过
                    if abs(np.dot(v_int[0], v)) > epsilon2:
                        continue
                if abs(np.dot(v, proj_normal_init)) < 1e-3:
                    v_int.append(v)
            if len(v_int) == 2:
                v = np.cross(v_int[0], v_int[1])
                v /= np.linalg.norm(v)
                # 如果和初始法向方向相反，则取反
                if np.dot(v, proj_normal_init) < 0:
                    v = -v
                proj_normal_init = v
                # 验证内部向量所有点积是否<=0（考虑数值误差）
                max_dot = max(np.dot(proj_normal_init, v) for v in V_INT_UNIQUE)
                if max_dot > tolerance:
                    proj_normal_init = None
            else:
                proj_normal_init = None
    else:
        proj_normal_init = None
        # debugprint(f"初始投影法向无效: {result.message}")

    # 尝试优化投影法向

    # 通过权重筛选投影法向
    def filter_proj_normal(proj_normal_lst, v_ext, v_int) -> Any:
        for lst in proj_normal_lst:
            v, w_ext, w_int = lst
            if w_ext is not None:
                continue
            # 与外部平面垂直+1分
            w_ext = sum(1 for v2 in v_ext if abs(np.dot(v, v2)) < tolerance)
            lst[1] = w_ext
        # 排序权重
        proj_normal_lst.sort(key=lambda x: x[1], reverse=True)
        # 查找与最大权重一致的其它项
        weight_max = proj_normal_lst[0][1]
        proj_normal_lst = [
            [v, w_ext, _] for v, w_ext, _ in proj_normal_lst if w_ext == weight_max
        ]

        # 如果符合条件的仍然超过1个
        if len(proj_normal_lst) > 1:
            # 与z轴垂直的向量优先
            z_axis = Vector((0, 0, 1))
            proj_normal_lst.sort(key=lambda x: abs(x[0].dot(z_axis)))
            # 计算内部面权重进一步筛选
            # for lst in proj_normal_lst:
            #     v, w_ext, w_int = lst
            #     if w_int is not None:
            #         continue
            #     # 与内部面垂直-1分
            #     w_int = sum(1 for v2 in v_int if abs(np.dot(v, v2)) < tolerance)
            #     lst[2] = w_int
            # # 排序权重, 选择权重最小的项
            # proj_normal_lst.sort(key=lambda x: x[2])

        return proj_normal_lst[0]

    # 能作为投影法向的外部平面，需满足与所有内部面的点积<=0
    proj_normal_ext_lst = []
    for v in V_EXT:
        max_dot = max(np.dot(v, v2) for v2 in V_INT_UNIQUE)
        if max_dot <= tolerance:
            # 向量，外部平面权重，内部面权重
            proj_normal_ext_lst.append([v, None, None])

    # 如果符合条件的外部平面超过1个，调用过滤函数
    if len(proj_normal_ext_lst) > 1:
        proj_normal_ext = filter_proj_normal(proj_normal_ext_lst, V_EXT, V_INT)
    elif len(proj_normal_ext_lst) == 1:
        proj_normal_ext = proj_normal_ext_lst[0]
    else:
        proj_normal_ext = None  # type: Any

    # 如果外部平面投影法向与初始投影法向都存在，进行过滤
    if proj_normal_ext and (proj_normal_init is not None):
        # 如果法向一致，选择外部平面法向
        if np.dot(proj_normal_ext[0], proj_normal_init) > epsilon2:
            proj_normal = proj_normal_ext[0]
        else:
            proj_normal = filter_proj_normal(
                [proj_normal_ext, [proj_normal_init, None, None]], V_EXT, V_INT
            )[0]
    # 如果都不存在，则为None
    elif not (proj_normal_ext or (proj_normal_init is not None)):
        proj_normal = None  # type: Any
    # 只有一方存在
    else:
        proj_normal = proj_normal_ext[0] if proj_normal_ext else proj_normal_init

    # debugprint(f"proj_normal: {proj_normal}")
    return proj_normal


# 获取顶点组中的顶点索引
def get_vertex_in_group(obj: Object, vg_name):
    """返回指定顶点组中的所有顶点索引集合。

    Args:
        obj (bpy.types.Object): 目标物体（必须为网格）。
        vg_name (str): 顶点组名称。

    Returns:
        set[int]: 顶点索引集合，若顶点组不存在则返回空集合。
    """
    if not obj or obj.type != "MESH" or vg_name not in obj.vertex_groups:
        return set()

    mesh = obj.data  # type: bpy.types.Mesh # type: ignore
    vg = obj.vertex_groups[vg_name]
    group_idx = vg.index
    vertex_indices = set()

    for v in mesh.vertices:
        for g in v.groups:
            if g.group == group_idx:
                vertex_indices.add(v.index)
                break
    return vertex_indices


# 获取摄像机变换并转换为Blade坐标空间
def get_camera_transform(cam):
    # type: (Object) -> tuple[tuple[float, float, float], tuple[float, float, float]]
    """获取摄像机变换并转换为Blade坐标空间"""
    # 获取摄像机的位置和旋转矩阵
    cam_pos = cam.matrix_world.translation
    cam_rot = cam.matrix_world.to_quaternion()
    distance = 5.0

    # 摄像机默认朝向-z方向，创建一个向前的向量
    forward = Vector((0.0, 0.0, -1.0))

    # 应用摄像机的旋转得到实际朝向
    forward.rotate(cam_rot)

    # 计算前方distance米的位置
    target_pos = cam_pos + forward * distance

    # 转换坐标
    cam_pos = (cam_pos * 1000).to_tuple(1)
    cam_pos = cam_pos[0], -cam_pos[2], cam_pos[1]
    target_pos = (target_pos * 1000).to_tuple(1)
    target_pos = target_pos[0], -target_pos[2], target_pos[1]

    return cam_pos, target_pos


############################
def get_pose_matrix_from_fcurves(armature, bone_name, channelbag, frame):
    # type: (Object, str, bpy.types.Action, int) -> Any
    """计算骨骼的 Pose 变换矩阵"""
    pose_bone = armature.pose.bones[bone_name]

    # 默认使用当前骨骼的变换（如果没有动画）
    loc = pose_bone.location.copy()
    rot = (
        pose_bone.rotation_quaternion.copy()
        if pose_bone.rotation_mode == "QUATERNION"
        else pose_bone.rotation_euler.copy()
    )
    scale = pose_bone.scale.copy()
    attr = (
        "rotation_quaternion"
        if pose_bone.rotation_mode == "QUATERNION"
        else "rotation_euler"
    )
    data_path = f'pose.bones["{bone_name}"].{attr}'

    # 从 F-Curves 获取动画数据（覆盖默认值）
    for i in range(4):
        fc = channelbag.fcurves.find(data_path, index=i)
        if fc is not None:
            rot[i] = fc.evaluate(frame)

    return rot.to_quaternion() if isinstance(rot, Euler) else rot


# def get_bone_local_matrix(armature, bone_name, channelbag, frame):
#     # type: (Object, str, bpy.types.Action, int) -> Matrix
#     """骨骼的最终局部变换 = Pose 矩阵 @ Rest 矩阵"""
#     pose_matrix = get_pose_matrix_from_fcurves(armature, bone_name, channelbag, frame)
#     data_bone = armature.data.bones[bone_name] # type: ignore

#     # Rest 矩阵（Head -> Tail 的变换，包含 Bone Length）
#     rest_matrix = data_bone.matrix_local.copy()
#     if data_bone.parent:
#         rest_matrix = data_bone.parent.matrix_local.inverted() @ rest_matrix

#     return pose_matrix @ rest_matrix


# 获取骨骼的世界变换矩阵
def get_bone_world_matrix(armature, bone_name, channelbag, frame):
    # type: (Object, str, bpy.types.Action, int) -> Any
    world_matrix = Quaternion()
    current_bone = armature.pose.bones[bone_name]

    # 存储骨骼链（从当前骨骼到根骨骼）
    bone_chain = [current_bone]  # type: list[bpy.types.PoseBone]
    parent_bone = current_bone.parent
    while parent_bone:
        bone_chain.append(parent_bone)
        parent_bone = parent_bone.parent

    # 从根骨骼到当前骨骼，逐级计算
    for bone in reversed(bone_chain):
        data_bone = armature.data.bones[bone.name]  # type: ignore
        bone_quat = data_bone.matrix_local.to_quaternion()
        quat_pose = get_pose_matrix_from_fcurves(armature, bone.name, channelbag, frame)
        quat = bone_quat @ quat_pose
        world_matrix = world_matrix @ quat

    return world_matrix @ quat_pose.inverted(), world_matrix


############################


def set_dict(this, key, value):
    this[key] = value


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
    bm = bmesh.new()
    bm.from_mesh(mesh)

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)  # type: ignore # 按距离合并顶点
    bm.to_mesh(mesh)

    def check():
        # 检查流形性
        non_manifold_edges = next((1 for e in bm.edges if not e.is_manifold), 0)
        non_manifold_verts = next((1 for v in bm.verts if not v.is_manifold), 0)
        if non_manifold_edges or non_manifold_verts:
            return False

        # 检查连通性
        if not bm.verts:
            return False
        bm.verts.ensure_lookup_table()
        visited = set()
        stack = [bm.verts[0]]
        while stack:
            v = stack.pop()
            if v not in visited:
                visited.add(v)

                for e in v.link_edges:
                    v2 = e.other_vert(v)
                    if v2 not in visited:
                        stack.append(v2)
        if len(visited) != len(bm.verts):
            return False

        # 检查封闭性（无边界）
        boundary_edges = next((1 for e in bm.edges if e.is_boundary), 0)
        if boundary_edges:
            return False

        return True

    # 检查欧拉特征
    V = len(bm.verts)
    E = len(bm.edges)
    F = len(bm.faces)
    euler_characteristic = V - E + F
    if euler_characteristic != 2:
        ret = False
    else:
        ret = check()

    bm.free()
    return ret


# 判断物体是否为凸多面体
def is_convex(obj: Object):
    """判断物体是否为凸多面体"""
    sec_data = obj.amagate_data.get_sector_data()

    # 如果不是二维球面，直接返回False
    if not sec_data.is_2d_sphere:
        return False

    sec_bm = bmesh.new()
    mesh = obj.data  # type: bpy.types.Mesh # type: ignore
    sec_bm.from_mesh(mesh)
    sec_bm.faces.ensure_lookup_table()

    # 重新计算法线
    bmesh.ops.recalc_face_normals(sec_bm, faces=sec_bm.faces)  # type: ignore
    # 反转法线
    bmesh.ops.reverse_faces(sec_bm, faces=sec_bm.faces)  # type: ignore
    sec_bm.to_mesh(mesh)

    bm_convex = sec_bm.copy()
    bm_convex.faces.ensure_lookup_table()

    # 顶点映射
    # vert_map = {v.co.to_tuple(4): i for i, v in enumerate(sec_bm.verts)}

    # 融并内插面
    # bmesh.ops.dissolve_limit(bm, angle_limit=0.002, verts=bm.verts, edges=bm.edges)
    # 融并面及反细分边
    # bmesh.ops.dissolve_limit(bm_convex, angle_limit=0.002, edges=bm_convex.edges) # type: ignore # verts=bm_convex.verts
    # unsubdivide(bm_convex)
    dissolve_unsubdivide(bm_convex)
    # 创建物体
    # convex_mesh = bpy.data.meshes.new("AG.convex_obj")
    # bm_convex.to_mesh(convex_mesh)  # type: ignore
    # convex_obj = bpy.data.objects.new("AG.convex_obj", convex_mesh) # type: Object # type: ignore
    # data.link2coll(convex_obj, bpy.context.scene.collection)

    # 重置面法向
    # bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # type: ignore
    # 如果存在凹边，返回0，否则返回1
    # ret = next((0 for i in bm.edges if not i.is_convex), 1)
    # print(f"is_convex: {ret}")

    # 创建凸壳
    convex_hull = bmesh.ops.convex_hull(bm_convex, input=bm_convex.verts, use_existing_faces=True)  # type: ignore
    # verts_interior = [v.index for v in convex_hull["geom_interior"]]  # type: list[int]
    # 未参与凸壳计算的顶点
    geom_interior = convex_hull["geom_interior"]  # type: list[bmesh.types.BMVert]
    # 参与凸壳计算的面
    geom_holes = convex_hull["geom_holes"]  # type: list[bmesh.types.BMFace]
    # 如果没有未参与凸壳计算的顶点，则为凸多面体
    convex = geom_interior == []
    # print("geom", [(type(i), i.index) for i in convex_hull['geom']])
    # print("geom_interior", [v.index for v in convex_hull["geom_interior"]])
    # print("geom_unused", [i.index for i in convex_hull["geom_unused"]])
    # print("geom_holes", [i.index for i in convex_hull["geom_holes"]])

    # def get_vert_index(verts) -> list[int]:
    #     vert_index = []
    #     # 遍历未参与凸壳计算的顶点
    #     for v in verts:
    #         idx = vert_map.get(v.co.to_tuple(4), None)
    #         if idx is None:
    #             print(f"error: {v.co.to_tuple(4)} not in vert_map")
    #             vert_index = []
    #             break
    #         vert_index.append(idx)
    #     return vert_index

    ########
    flat_ext = []
    faces_int_idx = []
    concave_type = CONCAVE_T_NONE
    ########
    # 如果不是凸多面体
    if not convex:
        # 获取准确的内部顶点，geom_interior并不准确
        # 提取外部面平面信息
        flat_ext = [
            (f.normal.copy(), f.calc_center_median()) for f in geom_holes
        ]  # type: list[tuple[Vector, Vector]]

        # 获取实际的外部面
        faces_ext = []  # type: list[bmesh.types.BMFace]
        for i in flat_ext:
            normal_ext = i[0]
            for f in sec_bm.faces:
                # 如果法线方向一致，则与外部面平行
                if f.normal.dot(normal_ext) > epsilon2:
                    # 如果是同一平面，则为外部面
                    if abs((f.verts[0].co - i[1]).dot(normal_ext)) < epsilon:
                        faces_ext.extend(get_linked_flat(f))
                        break
        # 外部顶点
        # verts_ext_idx = set(v.index for i in faces_ext_idx for v in sec_bm.faces[i])
        # 内部面索引
        faces_int_idx = list(
            set(range(len(sec_bm.faces))) - {f.index for f in faces_ext}
        )

    sec_data["ConcaveData"] = {
        "flat_ext": [i[0] for i in flat_ext],
        "faces_int_idx": faces_int_idx,
        "concave_type": concave_type,
    }

    # geom=[], geom_interior=[], geom_unused=[], geom_holes=[]
    sec_bm.free()
    bm_convex.free()
    return convex


# 断开连接
def disconnect(
    this,
    context: Context,
    sectors: list[Object],
    target_id: int | None = None,  # 断开指定id的连接
    dis_target=True,
    edit_mode=False,
):
    """断开连接"""
    if "EDIT" in context.mode:
        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

    scene_data = context.scene.amagate_data
    sectors_dict = scene_data["SectorManage"]["sectors"]  # type: dict

    for sec in sectors:
        sec_data = sec.amagate_data.get_sector_data()
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        sec_bm = bmesh.new()
        sec_bm.from_mesh(mesh)
        conn_layer = sec_bm.faces.layers.int.get("amagate_connected")

        dis_face_list = []
        dis_target_list = []
        for face in sec_bm.faces:
            if edit_mode and not face.select:
                continue
            conn_sid = face[conn_layer]  # type: ignore
            # 如果没有连接面，跳过
            if conn_sid == 0:
                continue
            # 如果连接面不是目标面，跳过
            if target_id is not None and conn_sid != target_id:
                continue
            #
            face[conn_layer] = 0  # type: ignore
            dis_face_list.append(face)

            if dis_target:
                dis_target_list.append(conn_sid)

        # 有限融并普通面
        dis_face_num = len(dis_face_list)
        faces = set()
        for face in dis_face_list:
            if face in faces:
                continue
            faces.update(get_linked_flat(face))
        # 重置标记
        for f in faces:
            for e in f.edges:
                e.seam = False
        for f in faces:
            if f[conn_layer] != 0:  # type: ignore
                for e in f.edges:
                    e.seam = True
        edges = {e for f in faces for e in f.edges}
        bmesh.ops.dissolve_limit(
            sec_bm, angle_limit=0.002, edges=list(edges), delimit={"SEAM", "MATERIAL"}
        )  # NORMAL

        # 断开目标
        conn_sid = sec_data.id
        for sid in dis_target_list:
            sec_dict = sectors_dict.get(str(sid))
            if not sec_dict:
                continue
            conn_sec = sec_dict["obj"]  # type: Object
            conn_sec_data = conn_sec.amagate_data.get_sector_data()
            if conn_sec_data.connect_num == 0:
                continue

            mesh_2 = conn_sec.data  # type: bpy.types.Mesh # type: ignore
            sec_bm_2 = bmesh.new()
            sec_bm_2.from_mesh(mesh_2)
            conn_layer_2 = sec_bm_2.faces.layers.int.get("amagate_connected")

            for face in sec_bm_2.faces:
                conn_sid_2 = face[conn_layer_2]  # type: ignore
                if conn_sid_2 == conn_sid:
                    face[conn_layer_2] = 0  # type: ignore
                    conn_sec_data.connect_num -= 1
                    # 有限融并普通面
                    faces = get_linked_flat(face)
                    # 重置标记
                    for f in faces:
                        for e in f.edges:
                            e.seam = False
                    for f in faces:
                        if f[conn_layer_2] != 0:  # type: ignore
                            for e in f.edges:
                                e.seam = True
                    edges = {e for f in faces for e in f.edges}
                    bmesh.ops.dissolve_limit(
                        sec_bm_2,
                        angle_limit=0.002,
                        edges=list(edges),
                        delimit={"SEAM", "MATERIAL"},
                    )  # NORMAL

                    unsubdivide(sec_bm_2)  # 反细分边
                    conn_sec_data.mesh_unique()
                    sec_bm_2.to_mesh(conn_sec.data)  # type: ignore
                    sec_bm_2.free()
                    break
            # 如果没有发生break，说明没有找到对应的连接面
            else:
                sec_bm_2.free()
        ##############
        if dis_face_num != 0:
            unsubdivide(sec_bm)  # 反细分边
            sec_data.mesh_unique()
            sec_bm.to_mesh(sec.data)  # type: ignore
        if isinstance(this, bpy.types.Operator):
            if edit_mode:
                sec_data.connect_num -= dis_face_num
            else:
                sec_data.connect_num = 0
        else:
            sec_data.connect_num -= dis_face_num
        sec_bm.free()
        # 重置连接属性
        # attributes = mesh.attributes.get("amagate_connected")
        # if attributes:
        #     mesh.attributes.remove(attributes)
        # mesh.attributes.new(
        #     name="amagate_connected", type="INT", domain="FACE"
        # )

    data.area_redraw("VIEW_3D")


# 检查连接
def check_connect(sec, check_id=None):
    # type: (Object, int | None) -> None
    """check_id参数只有当自身id发生变化时才需要传值"""
    context = bpy.context
    matrix_1 = sec.matrix_world.copy()
    sec_data = sec.amagate_data.get_sector_data()
    sid = sec_data.id
    if check_id is None:
        check_id = sid

    scene_data = context.scene.amagate_data
    sectors_dict = scene_data["SectorManage"]["sectors"]  # type: dict

    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
    sec_bm = bmesh.new()
    sec_bm.from_mesh(mesh)
    conn_layer = sec_bm.faces.layers.int.get("amagate_connected")
    faces_set = set(sec_bm.faces)

    match_count = 0
    dis_face_list = []
    dis_target_list = (
        []
    )  # type: list[tuple[Object, bmesh.types.BMesh, bmesh.types.BMFace]]
    while faces_set and sec_data.connect_num > 0:
        face_1 = faces_set.pop()
        conn_sid = face_1[conn_layer]  # type: ignore
        # 如果没有连接面，跳过
        if conn_sid == 0:
            continue

        normal_1 = matrix_1.to_quaternion() @ face_1.normal.copy()
        # 连接目标
        sec_dict = sectors_dict.get(str(conn_sid))
        if not sec_dict:
            continue
        conn_sec = sec_dict["obj"]  # type: Object
        conn_sec_data = conn_sec.amagate_data.get_sector_data()
        if conn_sec_data.connect_num == 0:
            continue

        matrix_2 = conn_sec.matrix_world.copy()
        mesh_2 = conn_sec.data  # type: bpy.types.Mesh # type: ignore
        sec_bm_2 = bmesh.new()
        sec_bm_2.from_mesh(mesh_2)
        conn_layer_2 = sec_bm_2.faces.layers.int.get("amagate_connected")

        # has_coplanar = False
        for face_2 in sec_bm_2.faces:
            if face_2[conn_layer_2] == check_id:  # type: ignore
                # 判断共面性
                normal_2 = matrix_2.to_quaternion() @ face_2.normal.copy()
                # 如果法向不是完全相反，断开连接
                if normal_1.dot(normal_2) > -epsilon2:
                    face_1[conn_layer] = 0  # type: ignore
                    dis_face_list.append(face_1)
                    dis_target_list.append((conn_sec, sec_bm_2, face_2))
                    sec_data.connect_num -= 1
                    # disconnect_face(faces, sec_bm_2, face_2, conn_layer_2, conn_sec_data, mesh_2)
                    # logger.debug("normal not match")
                    break

                # 获取面的顶点坐标
                # D = -(matrix_1 @ face_1.verts[0].co).dot(normal_1)
                # co2 = matrix_2 @ face_2.verts[0].co
                # dir = (co2 - co1).normalized()
                # dot = dir.dot(normal_1)
                # # 如果顶点不是在同一平面，断开连接
                # if abs(dot) > 2e-5:
                #     face_1[conn_layer] = 0  # type: ignore
                #     dis_face_list.append(face_1)
                #     dis_target_list.append((conn_sec, sec_bm_2, face_2))
                #     sec_data.connect_num -= 1
                #     logger.debug(f"vertex not on same plane: {dot}")
                #     break

                # 计算两个面顶点是否匹配
                bm_cmp = bmesh.new()
                for v in face_1.verts:
                    bm_cmp.verts.new(matrix_1 @ v.co)
                bm_cmp.faces.new(bm_cmp.verts[-len(face_1.verts) :])
                for v in face_2.verts:
                    bm_cmp.verts.new(matrix_2 @ v.co)
                bm_cmp.faces.new(bm_cmp.verts[-len(face_2.verts) :])
                unsubdivide(bm_cmp)
                verts_num = len(bm_cmp.verts) / 2
                bmesh.ops.remove_doubles(bm_cmp, verts=bm_cmp.verts, dist=0.0015)  # type: ignore
                verts_num_2 = len(bm_cmp.verts)
                bm_cmp.free()
                # for f, matrix in ((face_1, matrix_1), (face_2, matrix_2)):
                #     for v in f.verts:
                #         bm_cmp.verts.new(matrix @ v.co)
                #     bm_cmp.faces.new(bm_cmp.verts[-len(f.verts) :])
                # bm_cmp = ensure_lookup_table(bm_cmp)
                # unsubdivide(bm_cmp)  # 反细分边
                # bm_cmp.faces.ensure_lookup_table()
                # verts_set_1 = {v.co.to_tuple(3) for v in bm_cmp.faces[0].verts}
                # verts_set_2 = {v.co.to_tuple(3) for v in bm_cmp.faces[1].verts}
                # bm_cmp.free()

                # 如果连接面不匹配，断开连接
                if verts_num != verts_num_2:
                    face_1[conn_layer] = 0  # type: ignore
                    dis_face_list.append(face_1)
                    dis_target_list.append((conn_sec, sec_bm_2, face_2))
                    sec_data.connect_num -= 1
                    # logger.debug(f"vertex not on same plane")
                # 如果是匹配的
                else:
                    # 纠正连接的扇区ID
                    if check_id != sid:
                        # face_2[conn_layer_2] = sid  # type: ignore
                        mesh_2.attributes["amagate_connected"].data[face_2.index].value = sid  # type: ignore
                    match_count += 1
                    sec_bm_2.free()
                    # debugprint(f"connect_match: {sec.name} -> {conn_sec.name}")
                break
        # 如果没有发生break，说明没有找到目标面
        else:
            sec_bm_2.free()
            face_1[conn_layer] = 0  # type: ignore
            dis_face_list.append(face_1)
            sec_data.connect_num -= 1
            # 融并连接面
            # for f in faces:
            #     f[conn_layer] = 0  # type: ignore
            # bmesh.ops.dissolve_faces(sec_bm, faces=faces, use_verts=False)
            # sec_data.connect_num -= 1
            # if not has_dissolve[0]:
            #     has_dissolve[0] = True

    # 有限融并普通面
    dis_face_num = len(dis_face_list)
    faces = set()
    for face in dis_face_list:
        if face in faces:
            continue
        faces.update(get_linked_flat(face))
    # 重置标记
    for f in faces:
        for e in f.edges:
            e.seam = False
    for f in faces:
        if f[conn_layer] != 0:  # type: ignore
            for e in f.edges:
                e.seam = True
    edges = {e for f in faces for e in f.edges}
    bmesh.ops.dissolve_limit(
        sec_bm, angle_limit=0.002, edges=list(edges), delimit={"SEAM", "MATERIAL"}
    )  # NORMAL
    if dis_face_num != 0:
        unsubdivide(sec_bm)  # 反细分边
        sec_data.mesh_unique()
        sec_bm.to_mesh(sec.data)  # type: ignore
    sec_bm.free()
    sec_data.connect_num = match_count

    # 断开目标
    conn_sid = sec_data.id
    for conn_sec, sec_bm_2, face_2 in dis_target_list:
        conn_sec_data = conn_sec.amagate_data.get_sector_data()
        conn_sec_data.mesh_unique()
        mesh_2 = conn_sec.data  # type: bpy.types.Mesh # type: ignore
        conn_layer_2 = sec_bm_2.faces.layers.int.get("amagate_connected")

        face_2[conn_layer_2] = 0  # type: ignore
        conn_sec_data.connect_num -= 1
        # 有限融并普通面
        faces = get_linked_flat(face_2)
        # 重置标记
        for f in faces:
            for e in f.edges:
                e.seam = False
        for f in faces:
            if f[conn_layer_2] != 0:  # type: ignore
                for e in f.edges:
                    e.seam = True
        edges = {e for f in faces for e in f.edges}
        bmesh.ops.dissolve_limit(
            sec_bm_2, angle_limit=0.002, edges=list(edges), delimit={"SEAM", "MATERIAL"}
        )  # NORMAL

        unsubdivide(sec_bm_2)  # 反细分边
        sec_bm_2.to_mesh(mesh_2)
        sec_bm_2.free()

    #
    data.area_redraw("VIEW_3D")


# 删除扇区
def delete_sector(obj: Object | Any = None, id_key: str | Any = None):
    """删除扇区"""
    scene_data = bpy.context.scene.amagate_data
    SectorManage = scene_data["SectorManage"]

    if not obj:
        if not id_key:
            return
        obj = SectorManage["sectors"][id_key]["obj"]

    delete_bulb(obj)

    sec_data = obj.amagate_data.get_sector_data()
    mesh = obj.data  # type: bpy.types.Mesh # type: ignore
    id_key = str(sec_data.id)
    #
    if mesh.users == 1:
        bpy.data.meshes.remove(mesh)
    else:
        bpy.data.objects.remove(obj)

    sector_mgr_remove(id_key)


# 扇区管理移除
def sector_mgr_remove(id_key: str):
    scene_data = bpy.context.scene.amagate_data
    SectorManage = scene_data["SectorManage"]
    # 移除大气引用
    atmo = L3D_data.get_atmo_by_id(
        scene_data, SectorManage["sectors"][id_key]["atmo_id"]
    )[1]
    if atmo:
        atmo.users_obj.remove(atmo.users_obj.find(id_key))
    # 移除外部光引用
    external = L3D_data.get_external_by_id(
        scene_data, SectorManage["sectors"][id_key]["external_id"]
    )[1]
    if external:
        external.users_obj.remove(external.users_obj.find(id_key))
    # 调整id管理
    if int(id_key) != SectorManage["max_id"]:
        SectorManage["deleted_id_count"] += 1
    else:
        SectorManage["max_id"] -= 1
    SectorManage["sectors"].pop(id_key)


# 删除灯泡
def delete_bulb(sec: Object):
    scene_data = bpy.context.scene.amagate_data
    light_link_manager = scene_data.light_link_manager
    sec_data = sec.amagate_data.get_sector_data()

    for item in sec_data.bulb_light:
        key = item.name
        if key in light_link_manager:
            light_link_manager.remove(light_link_manager.find(key))
        #
        light = item.light_obj
        if light:
            bpy.data.lights.remove(light.data)
    #
    for coll in (sec_data.bulb_light_link, sec_data.bulb_shadow_link):
        if coll:
            bpy.data.collections.remove(coll)


# 删除实体
def delete_entity(key="", ent=None):  # type: ignore
    scene_data = bpy.context.scene.amagate_data
    if key == "":
        if ent is None:
            return
        ent_data = ent.amagate_data.get_entity_data()
        key = ent_data.Name
    if key not in scene_data["EntityManage"]:
        return

    ent = scene_data["EntityManage"][key]  # type: Object
    if ent is not None:
        ent_data = ent.amagate_data.get_entity_data()
        if ent_data.ObjType == "0":  # "Person"
            ent_data.clear_inv()
        ent_data.clear_contained()
        bpy.data.objects.remove(ent)
    scene_data["EntityManage"].pop(key)


# 单选并设为活动对象
def select_active(context: Context, obj: Object):
    """单选并设为活动对象"""
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式
    bpy.ops.object.select_all(action="DESELECT")  # 取消选择
    context.view_layer.objects.active = obj  # 设置活动物体
    obj.select_set(True)  # 选择


# 反细分边
def unsubdivide(bm: bmesh.types.BMesh):
    verts_lst = []  # type: list[tuple[list[bmesh.types.BMVert], bmesh.types.BMVert]]
    visited = set()
    # bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if v in visited:
            continue

        if len(v.link_edges) == 2:
            dir1 = (v.link_edges[0].other_vert(v).co - v.co).normalized()
            dir2 = (v.link_edges[1].other_vert(v).co - v.co).normalized()
            # 如果该顶点只连接两条边且共线，则为子顶点
            if dir1.dot(dir2) < -0.999999:
                verts, endpoint = get_sub_verts_along_line(v, dir1)
                # verts = [bm.verts[i] for i in verts_index]
                verts_lst.append((verts, endpoint))
                visited.update(verts)

    # debugprint(f"verts_lst: {verts_lst}")
    for verts, endpoint in verts_lst:
        endpoint2 = endpoint.link_edges[0].other_vert(endpoint)
        if endpoint2 in verts:
            endpoint2 = endpoint.link_edges[1].other_vert(endpoint)
        bmesh.ops.pointmerge(bm, verts=verts + [endpoint2], merge_co=endpoint2.co)


def dissolve_unsubdivide(bm: bmesh.types.BMesh, del_connected=False):
    """融并面及反细分边"""
    # 待融并面列表
    faces_lst = []
    visited = []  # type: list[bmesh.types.BMFace]
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        if f in visited:
            continue

        # 获取相同法线的相连面
        faces = get_linked_flat(f)
        visited.extend(faces)
        faces_lst.append(faces)

    layer = bm.faces.layers.int.get("amagate_connected")
    for faces in faces_lst:
        faces = [f for f in faces if f.is_valid]  # XXX 未知问题，会包含被删除的面
        if del_connected:
            for f in faces:
                if f[layer] != 0:
                    bmesh.ops.delete(bm, geom=faces, context="FACES")
                    faces = []
                    break

        if len(faces) > 1:
            bmesh.ops.dissolve_faces(bm, faces=faces, use_verts=False)

    # 反细分
    unsubdivide(bm)


def ensure_lookup_table(bm: bmesh.types.BMesh):
    """确保索引映射表，使其不再是-1"""
    mesh = bpy.data.meshes.new("AG.ensure_lookup_table")
    bm.to_mesh(mesh)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bpy.data.meshes.remove(mesh)  # 删除网格
    return bm


############################

# 无符号与有符号整数之间的转换


def int_to_uint(i: int) -> int:
    """将整数转换为无符号整数"""
    return i & 0xFFFFFFFF if i < 0 else i


def uint_to_int(i: int) -> int:
    """将无符号整数转换为整数"""
    return i - (1 << 32) if i >= (1 << 31) else i


############################


def steep_check(sec: Object):
    sec_data = sec.amagate_data.get_sector_data()
    if not sec_data.is_convex:
        return

    matrix_world = sec.matrix_world
    quat = matrix_world.to_quaternion()
    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
    z_axis = Vector((0, 0, 1))

    faces_normal = [quat @ f.normal for f in mesh.polygons]
    faces_normal.sort(key=lambda x: round(x.dot(-z_axis), 3))
    first_normal = faces_normal[0]
    cos = first_normal.dot(z_axis)
    if cos < 0.7665:  # 地面大于39.96（误差）度，会被引擎设为滑坡
        sec_data.steep_check = True
    else:
        sec_data.steep_check = False


# 扩展连接面
def expand_conn(faces, bm):
    # type: (list[bmesh.types.BMFace], bmesh.types.BMesh) -> list[bmesh.types.BMFace]
    selected_faces = []
    stack = set(faces)
    while stack:
        face = stack.pop()

        flat_faces = get_linked_flat(face, bm=bm, check_conn=True)
        if len(flat_faces) > 1:
            stack.difference_update(flat_faces)
        else:
            flat_faces = [face]

        selected_faces.extend(flat_faces)

    return selected_faces


# 有限融并扇区
def dissolve_limit_sectors(sectors, check_convex=True):
    # type: (list[Object], bool) -> None
    for sec in sectors:
        sec_data = sec.amagate_data.get_sector_data()
        # 如果不是凸扇区，跳过
        if check_convex and not sec_data.is_convex:
            continue
        # if sec_data.connect_num == 0:
        #     continue

        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        bm = bmesh.new()
        bm.from_mesh(mesh)
        conn_layer = bm.faces.layers.int.get("amagate_connected")
        tex_id_layer = bm.faces.layers.int.get("amagate_tex_id")
        flag_layer = bm.faces.layers.int.get("amagate_flag")
        # has_dissolve = False

        conn_dict = {}
        for face in bm.faces:
            conn_sid = face[conn_layer]  # type: ignore
            if conn_sid != 0:  # type: ignore
                conn_dict.setdefault(conn_sid, []).append(face)
        for conn_sid, faces in conn_dict.items():
            if len(faces) > 1:
                bmesh.ops.dissolve_faces(bm, faces=faces, use_verts=False)

        # 确保天空纹理与普通纹理不在同一平展面
        visited = set()
        for f in bm.faces:
            if f in visited:
                continue
            flat_faces = get_linked_flat(f)
            visited.update(flat_faces)
            face = next((f for f in flat_faces if f[tex_id_layer] != -1), None)  # type: ignore
            if face:
                for f in flat_faces:
                    if f[tex_id_layer] == -1:  # type: ignore
                        f[tex_id_layer] = face[tex_id_layer]  # type: ignore
                        f[flag_layer] = face[flag_layer]  # type: ignore
                        f.material_index = face.material_index

        # 有限融并扇区
        # 重置缝合边标记
        for e in bm.edges:
            e.seam = False
        for f in bm.faces:
            if f[conn_layer] != 0:  # type: ignore
                for e in f.edges:
                    e.seam = True
        bmesh.ops.dissolve_limit(
            bm,
            angle_limit=0.002,
            edges=list(bm.edges),
            delimit={"SEAM", "MATERIAL", "SHARP"},
        )  # NORMAL

        unsubdivide(bm)
        bm.to_mesh(mesh)  # type: ignore
        bm.free()


############################


def download_file(url, save_file, referer):
    # type: (str, tempfile._TemporaryFileWrapper, str) -> bool
    """
    下载文件到指定路径
    """
    proxies = {
        "http": "http://127.0.0.1:10809",  # HTTP 代理
        "https": "http://127.0.0.1:10809",  # HTTPS 代理（如果代理支持）
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": referer,
        # "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        # "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        # "Accept-Encoding": "gzip, deflate, br",  # 注意：requests 默认不自动解压 br（Brotli）
    }

    with requests.Session() as session:
        try:
            response = session.get(
                url, headers=headers, stream=True, timeout=10
            )  # proxies=proxies
            # logger.debug(f"status_code: {response.status_code}")
            response.raise_for_status()

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    save_file.write(chunk)
            return True
        except Exception as e:
            logger.info(f"下载文件时出错: {e}")
            return False


def extract_file(archive_file, extract_to):
    # type: (tempfile._TemporaryFileWrapper, str) -> bool
    """
    解压文件到指定目录
    """
    try:
        if not os.path.exists(extract_to):
            os.makedirs(extract_to, exist_ok=True)

        if archive_file.name.endswith(".zip"):
            with zipfile.ZipFile(archive_file, "r") as zip_ref:
                # zip_ref.extractall(extract_to)
                for member in zip_ref.infolist():
                    target_path = os.path.join(extract_to, member.filename)
                    # 检查文件是否存在且不是目录
                    if not (
                        os.path.exists(target_path) and not os.path.isdir(target_path)
                    ):
                        zip_ref.extract(member, extract_to)
                    else:
                        pass
                        # logger.info(f"文件已存在，跳过: {member.filename}")
        # elif archive_path.endswith(('.tar.gz', '.tgz')):
        #     with tarfile.open(archive_path, 'r:gz') as tar_ref:
        #         tar_ref.extractall(extract_to)
        # elif archive_path.endswith(('.tar.bz2', '.tbz2')):
        #     with tarfile.open(archive_path, 'r:bz2') as tar_ref:
        #         tar_ref.extractall(extract_to)
        # elif archive_path.endswith('.tar'):
        #     with tarfile.open(archive_path, 'r:') as tar_ref:
        #         tar_ref.extractall(extract_to)
        else:
            logger.info("不支持的文件格式")
            return False

        return True
    except Exception as e:
        logger.info(f"解压文件时出错: {e}")
        return False


############################


def popup_menu(context: Context, text, title, icon):
    context.window_manager.popup_menu(
        lambda self, context: self.layout.label(text=text),
        title=title,
        icon=icon,
    )


############################
############################
############################
