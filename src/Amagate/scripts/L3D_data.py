# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import re
import os
import math
import shutil
import pickle
import threading
import contextlib
import ast
import time

from asyncio import run_coroutine_threadsafe
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

# from collections import Counter
#
import bpy

import bmesh
from bpy.app.translations import pgettext

# from bpy.types import Context
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
import rna_keymap_ui
import blf
from mathutils import *  # type: ignore

#
from . import ag_utils, data
from ..service import ag_service

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
############################
LAST_SENT_TIME = 0
SYNC_INTERVAL = ag_service.SYNC_INTERVAL


AG_COLL = "Amagate Auto Generated"
S_COLL = "Sector Collection"
GS_COLL = "Ghost Sector Collection"
E_COLL = "Entity Collection"
C_COLL = "Camera Collection"

DEPSGRAPH_UPDATE_LOCK = threading.Lock()
CHECK_CONNECT = threading.Lock()
CONNECT_SECTORS = set()

# 全景图下载锁
PANORAMA_LOCK = threading.Lock()

S_COLL_OBJECTS = 0
OPERATOR_POINTER = None
draw_handler = None

SELECTED_FACES = (
    []
)  # type: list[tuple[bmesh.types.BMesh, list[bmesh.types.BMFace], Object]]
SELECTED_SECTORS: list[Object] = []
ACTIVE_SECTOR: Object = None  # type: ignore

FACE_FLAG = {"Floor": 0, "Ceiling": 1, "Wall": 2, "Custom": 3}

COLLECTION_OP = (
    "Move to Collection",
    "Remove from Collection",
    "Remove from All Collections",
    "Remove Selected from Active Collection",
    "Remove Collection",
    "Unlink Collection",
)

DELETE_OP = ("OBJECT_OT_delete", "OUTLINER_OT_delete")

DUPLICATE_OP = (
    "OBJECT_OT_duplicate_move",
    "OBJECT_OT_duplicate_move_linked",
)

TRANSFORM_OP = ("TRANSFORM_OT_translate", "TRANSFORM_OT_resize", "TRANSFORM_OT_rotate")

SELECT_OP = (
    "VIEW3D_OT_select",
    "VIEW3D_OT_select_box",
    "OUTLINER_OT_item_activate",
    "OUTLINER_OT_select_box",
)

############################


#
def get_atmo_by_id(scene_data, atmo_id):
    # type: (SceneProperty, Any) -> tuple[int, AtmosphereProperty]
    idx = scene_data.atmospheres.find(str(atmo_id))
    atmo = scene_data.atmospheres[idx] if idx != -1 else None
    return (idx, atmo)  # type: ignore


def get_external_by_id(scene_data, external_id):
    # type: (SceneProperty, Any) -> tuple[int, ExternalLightProperty]
    idx = scene_data.externals.find(str(external_id))
    external = scene_data.externals[idx] if idx != -1 else None
    return (idx, external)  # type: ignore


def get_texture_by_id(texture_id) -> tuple[int, Image]:
    if texture_id != 0:
        for i, texture in enumerate(bpy.data.images):
            if texture.amagate_data.id == texture_id:  # type: ignore
                return (i, texture)  # type: ignore
    return (-1, None)  # type: ignore


def get_sector_by_id(scene_data, sector_id) -> Object:
    return scene_data["SectorManage"]["sectors"][str(sector_id)]["obj"]


# 确保NULL纹理存在
def ensure_null_texture() -> Image:
    scene_data = bpy.context.scene.amagate_data
    img = scene_data.ensure_null_tex  # type: Image
    if not img:
        # img = bpy.data.images.new("NULL", width=256, height=256)  # type: ignore
        enum_items = scene_data.bl_rna.properties["sky_tex_enum"].enum_items  # type: ignore
        file_name = enum_items[int(scene_data.sky_tex_enum) - 1].description
        filepath = os.path.join(data.ADDON_PATH, f"textures/panorama/{file_name}.jpg")
        img = bpy.data.images.load(filepath)  # type: Image # type: ignore
        img.name = "NULL"
        img.amagate_data.id = -1  # type: ignore
        scene_data.ensure_null_tex = img
        ensure_material(img)
    # elif not img.amagate_data.id:  # type: ignore
    #     img.amagate_data.id = -1  # type: ignore
    if not img.use_fake_user:
        img.use_fake_user = True
    return img


# 确保NULL物体存在
def ensure_null_object() -> Object:
    scene_data = bpy.context.scene.amagate_data
    null_obj = scene_data.ensure_null_obj  # type: Object
    if not null_obj:
        # obj_data = bpy.data.meshes.new("NULL")
        null_obj = bpy.data.objects.new("NULL", None)  # type: ignore
        # bpy.ops.mesh.primitive_cube_add()
        # null_obj = bpy.context.active_object

        null_obj.use_fake_user = True

        # 可见性
        null_obj.hide_viewport = True
        null_obj.visible_shadow = False

        scene_data.ensure_null_obj = null_obj
    return null_obj


# 确保渲染摄像机
def ensure_render_camera() -> Object:
    scene_data = bpy.context.scene.amagate_data
    render_cam = scene_data.render_cam  # type: Object
    if not render_cam:
        cam_data = bpy.data.cameras.new("AG.RenderCamera")
        render_cam = bpy.data.objects.new("AG.RenderCamera", cam_data)  # type: ignore
        cam_data.sensor_width = 100
        cam_data.passepartout_alpha = 0.98
        # cam_data.show_limits = True
        render_cam.location = (0, -0.1, 0)  # 避免0位置崩溃
        render_cam.rotation_euler = (math.pi / 2, 0, 0)
        # 正交摄像机
        # render_cam.data.type = "ORTHO"
        data.link2coll(render_cam, ensure_collection(C_COLL))
        bpy.context.scene.camera = render_cam
        scene_data.render_cam = render_cam
    return render_cam


# 确保集合
def ensure_collection(name, hide_select=False) -> Collection:
    scene = bpy.context.scene
    scene_data = scene.amagate_data
    item = scene_data.ensure_coll.get(name)
    if (not item) or (not item.obj):
        c_name = f"{pgettext(name)}"
        coll = bpy.data.collections.new(c_name)
        scene.collection.children.link(coll)
        coll.hide_select = hide_select
        if not item:
            item = scene_data.ensure_coll.add()
            item.name = name
        item.obj = coll
    elif item.obj.name not in scene.collection.children:
        scene.collection.children.link(item.obj)
    return item.obj  # type: ignore


# 确保材质
def ensure_material(tex: Image) -> bpy.types.Material:
    tex_data = tex.amagate_data
    name = f"AG.Mat{tex_data.id}"
    mat = tex_data.mat_obj
    if not mat:
        mat = bpy.data.materials.new("")
        mat.rename(name, mode="ALWAYS")
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))
        if tex_data.id == -1:
            data.import_nodes(mat, nodes_data["AG.Mat-1"])
        else:
            data.import_nodes(mat, nodes_data["AG.Mat1"])
        mat.use_fake_user = True
        if tex_data.id == -1:
            mat.node_tree.nodes["Environment Texture"].image = tex  # type: ignore
        else:
            mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
        mat.use_backface_culling = True
        tex_data.mat_obj = mat

    return mat


# 确保节点
def ensure_node():
    filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
    nodes_data = pickle.load(open(filepath, "rb"))
    scene_data = bpy.context.scene.amagate_data
    #
    NodeTree = scene_data.eval_node
    if not NodeTree:
        NodeTree = bpy.data.node_groups.new("Amagate Eval", "GeometryNodeTree")  # type: ignore
        NodeTree.interface.new_socket(
            "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )
        NodeTree.interface.new_socket(
            "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )

    data.import_nodes(NodeTree, nodes_data["Amagate Eval"])
    NodeTree.use_fake_user = True
    NodeTree.is_tool = True  # type: ignore
    NodeTree.is_type_mesh = True  # type: ignore
    scene_data.eval_node = NodeTree
    #
    NodeTree = scene_data.sec_node
    if not NodeTree:
        NodeTree = bpy.data.node_groups.new("AG.SectorNodes", "GeometryNodeTree")  # type: ignore
        NodeTree.interface.new_socket(
            "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )
        NodeTree.interface.new_socket(
            "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )
    NodeTree.nodes.clear()

    input_node = NodeTree.nodes.new("NodeGroupInput")
    input_node.select = False
    input_node.location.x = -200 - input_node.width

    output_node = NodeTree.nodes.new("NodeGroupOutput")
    output_node.is_active_output = True  # type: ignore
    output_node.select = False
    output_node.location.x = 200

    group = NodeTree.nodes.new(type="GeometryNodeGroup")
    group.location.x = -group.width / 2
    group.select = False
    group.node_tree = scene_data.eval_node  # type: ignore

    # NodeTree.links.new(input_node.outputs[0], output_node.inputs[0])
    NodeTree.links.new(input_node.outputs[0], group.inputs[0])
    NodeTree.links.new(group.outputs[0], output_node.inputs[0])

    NodeTree.use_fake_user = True
    NodeTree.is_modifier = True  # type: ignore
    scene_data.sec_node = NodeTree


def update_scene_edit_mode():
    context = bpy.context
    scene_data = context.scene.amagate_data
    scene_data.is_edit_mode = context.mode != "OBJECT"
    context.scene.update_tag()


############################
############################ 回调函数
############################


# 扇区集合检查
def check_sector_coll():
    scene_data = bpy.context.scene.amagate_data

    coll = ensure_collection(S_COLL)
    SectorManage = scene_data.get("SectorManage")

    exist_ids = set(str(obj.amagate_data.get_sector_data().id) for obj in coll.all_objects if obj.amagate_data.is_sector)  # type: ignore
    all_ids = set(SectorManage["sectors"].keys())
    deleted_ids = sorted(all_ids - exist_ids, reverse=True)

    if deleted_ids:
        # 如果只是移动到其它集合，则撤销操作
        obj = SectorManage["sectors"][deleted_ids[0]]["obj"]
        if obj and bpy.context.scene in obj.users_scene:
            bpy.ops.ed.undo()
            bpy.ops.ed.undo_push(message="Sector Collection Check")
            return


# 扇区删除检查
def check_sector_delete():
    scene_data = bpy.context.scene.amagate_data

    # 如果用户删除了扇区物体，则进行自动清理
    coll = ensure_collection(S_COLL)
    SectorManage = scene_data.get("SectorManage")

    exist_ids = set(str(obj.amagate_data.get_sector_data().id) for obj in coll.all_objects if obj.amagate_data.is_sector)  # type: ignore
    all_ids = set(SectorManage["sectors"].keys())
    deleted_ids = sorted(all_ids - exist_ids, reverse=True)

    if deleted_ids:
        bpy.ops.ed.undo()
        coll = ensure_collection(S_COLL)
        scene_data = bpy.context.scene.amagate_data
        SectorManage = scene_data["SectorManage"]

        disconnect = []  # 需要与删除扇区解除连接的扇区
        sectors_del = [
            SectorManage["sectors"][id_key]["obj"] for id_key in deleted_ids
        ]  # type: list[Object]
        for sec in sectors_del:
            sec_data = sec.amagate_data.get_sector_data()
            # 如果没有连接，跳过
            if sec_data.connect_num == 0:
                continue

            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            connect = {
                mesh.attributes["amagate_connected"].data[i].value  # type: ignore
                for i in range(len(mesh.polygons))
            }
            connect.discard(0)
            if connect:
                sectors = [
                    SectorManage["sectors"][f"{i}"]["obj"]
                    for i in connect
                    if SectorManage["sectors"][f"{i}"]["obj"] not in sectors_del
                ]
                disconnect.append((sectors, sec_data.id))
        for sectors, sid in disconnect:
            ag_utils.disconnect(None, bpy.context, sectors, sid, dis_target=False)

        for id_key in deleted_ids:
            ag_utils.delete_sector(id_key=id_key)

        bpy.ops.ed.undo_push(message="Delete Sector")


# 特殊对象检查
def check_special_objects():
    scene_data = bpy.context.scene.amagate_data
    for i in [
        scene_data.ensure_null_obj,
        scene_data.ensure_null_tex,
        scene_data.sec_node,
        scene_data.eval_node,
    ] + [item.obj for item in scene_data.ensure_coll]:
        if not i:
            bpy.ops.ed.undo()
            bpy.ops.ed.undo_push(message="Special Object Check")
            return


# 扇区合并检查
def check_sector_join():
    context = bpy.context
    bpy.ops.ed.undo()

    active_object = context.active_object
    selected_sectors = ag_utils.get_selected_sectors()[0]
    if active_object in selected_sectors:
        selected_sectors.remove(active_object)
    remove_ids = [sec.amagate_data.get_sector_data().id for sec in selected_sectors]

    for sec in selected_sectors:
        ag_utils.delete_bulb(sec)

    if selected_sectors:
        ag_utils.disconnect(None, context, selected_sectors)
    bpy.ops.object.join()
    if active_object.amagate_data.is_sector:
        sec_data = active_object.amagate_data.get_sector_data()
        sec_data.is_2d_sphere = ag_utils.is_2d_sphere(active_object)
        sec_data.is_convex = ag_utils.is_convex(active_object)

    for id in remove_ids:
        ag_utils.sector_mgr_remove(str(id))
    bpy.ops.ed.undo_push(message="Join Sector")


# 分离扇区检查
def check_sector_separate():
    context = bpy.context
    # 编辑模式下的物体
    edit_objects = context.objects_in_mode.copy()
    # 编辑模式下的扇区
    edit_sectors = [obj for obj in edit_objects if obj.amagate_data.is_sector]

    if not edit_sectors:
        return

    sec_ids = [sec.amagate_data.get_sector_data().id for sec in edit_sectors]
    # 编辑模式之外的选中物体
    selected_objects = [
        obj for obj in context.selected_objects if obj not in edit_objects
    ]
    # 分离出的扇区
    sep_sectors = [
        obj
        for obj in selected_objects
        if obj.amagate_data.is_sector
        and obj.amagate_data.get_sector_data().id in sec_ids
    ]
    if not sep_sectors:
        return

    bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

    # 分离出的扇区ID
    sec_ids_2 = [sec.amagate_data.get_sector_data().id for sec in sep_sectors]
    for sec in sep_sectors:
        sec_data = sec.amagate_data.get_sector_data()
        sid = sec_data.id
        sec_data.init(post_copy=True)
        ag_utils.check_connect(sec, sid)

    for sec in edit_sectors:
        sec_data = sec.amagate_data.get_sector_data()
        # 如果该扇区被分离了，检查连接
        if sec_data.id in sec_ids_2:
            ag_utils.check_connect(sec)

    # 只选择分离出的扇区
    bpy.ops.object.select_all(action="DESELECT")
    for sec in sep_sectors:
        sec.select_set(True)
    context.view_layer.objects.active = sep_sectors[0]  # 设为活动对象
    update_scene_edit_mode()

    # 恢复选择
    # ag_utils.select_active(context, edit_objects[0])  # 单选并设为活动
    # for obj in edit_objects:
    #     obj.select_set(True)
    # bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式
    # for obj in selected_objects:
    #     obj.select_set(True)

    bpy.ops.ed.undo_push(message="Sector Check")


# 复制扇区检查
def check_sector_duplicate():
    context = bpy.context
    dup_sectors = [
        obj for obj in context.selected_objects if obj.amagate_data.is_sector
    ]
    if not dup_sectors:
        return

    for sec in dup_sectors:
        sec_data = sec.amagate_data.get_sector_data()
        sec_data.init(post_copy=True)
    ag_utils.disconnect(None, context, dup_sectors, dis_target=False)

    # XXX 待优化。取消用户的操作选项
    context.view_layer.objects.active = dup_sectors[0]  # 设为活动对象
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.app.timers.register(
        lambda: bpy.ops.object.mode_set(mode="OBJECT") and None, first_interval=0.1
    )

    bpy.ops.ed.undo_push(message="Sector Check")


# 粘贴扇区检查
def check_sector_paste():
    context = bpy.context
    copy_sectors = [
        obj for obj in context.selected_objects if obj.amagate_data.is_sector
    ]
    bpy.ops.ed.undo()
    bpy.ops.ed.undo_push(message="Sector Paste Check")


# 扇区变换检查
def check_sector_transform(bl_idname):
    context = bpy.context

    sectors = [obj for obj in context.selected_objects if obj.amagate_data.is_sector]
    conn_sectors = [
        sec for sec in sectors if sec.amagate_data.get_sector_data().connect_num != 0
    ]
    if not conn_sectors:
        return

    for sec in conn_sectors:
        ag_utils.check_connect(sec)

    # 如果是旋转操作，检查陡峭
    if bl_idname == "TRANSFORM_OT_rotate":
        for sec in sectors:
            ag_utils.steep_check(sec)

    bpy.ops.ed.undo_push(message="Sector Check")


# 扇区选择检查
def check_sector_select():
    context = bpy.context
    scene_data = context.scene.amagate_data
    selected_sectors, active_sector = ag_utils.get_selected_sectors()
    # 显示活动扇区的外部光
    if active_sector:
        externals = scene_data.externals
        if len(externals) > 1:
            sec_data = active_sector.amagate_data.get_sector_data()
            idx, item = get_external_by_id(scene_data, sec_data.external_id)
            if item:
                item.obj.hide_viewport = False
                for item_2 in externals:
                    if item_2 != item:
                        item_2.obj.hide_viewport = True


def geometry_modify_post(
    selected_sectors: list[Object] = [], undo=True, check_connect=True
):
    if not selected_sectors:
        selected_sectors = ag_utils.get_selected_sectors()[0]
    if selected_sectors:
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            # if sec_data is None:
            #     continue
            sec_data.is_2d_sphere = ag_utils.is_2d_sphere(sec)
            sec_data.is_convex = ag_utils.is_convex(sec)

        ag_utils.dissolve_limit_sectors(selected_sectors)

        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.connect_num != 0 and check_connect:
                ag_utils.check_connect(sec)
            ag_utils.steep_check(sec)

        # 扇区编辑检查
        if undo:
            bpy.ops.ed.undo_push(message="Sector Check")


# def check_connect_timer():
#     global CONNECT_SECTORS

#     for sec in CONNECT_SECTORS:
#         ag_utils.check_connect(sec)

#     ag_utils.debugprint("check_connect_timer done")

#     CONNECT_SECTORS = set()
#     CHECK_CONNECT.release()


# def delete_post_func_release():
#     DELETE_POST_LOCK.release()


# @bpy.app.handlers.persistent
def depsgraph_update_post(scene: Scene, depsgraph: bpy.types.Depsgraph):
    global OPERATOR_POINTER, S_COLL_OBJECTS, LAST_SENT_TIME
    scene_data = scene.amagate_data
    if not scene_data.is_blade:
        return

    # XXX 待优化。目前没有获取撤销堆栈的Python API，因此在模态模式也会执行回调
    if not DEPSGRAPH_UPDATE_LOCK.acquire(blocking=False):
        return

    context = bpy.context

    #
    current_time = time.time()
    server_thread = ag_service.server_thread
    if (
        server_thread
        and server_thread.clients
        and current_time - LAST_SENT_TIME >= SYNC_INTERVAL
    ):
        LAST_SENT_TIME = current_time
        for update in depsgraph.updates:
            obj = update.id
            if not isinstance(update.id, bpy.types.Object):
                continue
            if not update.is_updated_transform:
                continue
            # logger.debug(update.id)
            if (
                scene_data.operator_props.camera_sync
                and scene.camera
                and scene.camera.name == obj.name
            ):
                # logger.debug("camera_sync")
                ag_service.send_camera_data(obj)  # type: ignore
    #

    s_coll_objects_neq = False  # 扇区集合对象数量是否发生变化
    item = scene_data.ensure_coll.get(S_COLL)
    if item and item.obj:
        all_objects = len(item.obj.all_objects)
        if S_COLL_OBJECTS != all_objects:
            S_COLL_OBJECTS = all_objects
            s_coll_objects_neq = True

    operator_pointer = context.window_manager.operators[-1].as_pointer() if context.window_manager.operators else None  # type: ignore
    if (operator_pointer is not None) and operator_pointer != OPERATOR_POINTER:
        OPERATOR_POINTER = operator_pointer
        #
        bl_label = context.window_manager.operators[-1].bl_label
        bl_idname = context.window_manager.operators[-1].bl_idname
        # print(bl_idname)
        if bl_idname == "OBJECT_OT_editmode_toggle":
            scene_data.is_edit_mode = context.mode != "OBJECT"
            scene.update_tag()
            # 从编辑模式切换到物体模式的回调
            if context.mode == "OBJECT":
                geometry_modify_post()
        # 应用修改器的回调
        elif bl_idname == "OBJECT_OT_modifier_apply":
            geometry_modify_post()
        # 移动/移除扇区集合的回调
        elif bl_label in COLLECTION_OP:
            check_sector_coll()
        # 删除扇区的回调
        elif bl_idname in DELETE_OP and s_coll_objects_neq:
            check_sector_delete()
        # 任意删除的回调
        elif bl_idname in DELETE_OP:
            check_special_objects()
        # 合并扇区的回调
        elif bl_idname == "OBJECT_OT_join":
            check_sector_join()
        # 分离扇区的回调
        elif bl_idname == "MESH_OT_separate":
            check_sector_separate()
        # 复制扇区的回调 # FIXME 有时候没有触发该回调，原因未知
        elif bl_idname in DUPLICATE_OP:
            check_sector_duplicate()
        # 粘贴扇区的回调
        elif bl_idname == "VIEW3D_OT_pastebuffer":
            check_sector_paste()
        # 扇区变换的回调
        elif bl_idname in TRANSFORM_OP:
            check_sector_transform(bl_idname)
        # 选择物体的回调
        elif bl_idname in SELECT_OP:
            check_sector_select()
        # 编辑模式删除的回调，有点复杂，因为不知道用户是单独删除面还是包括顶点
        # elif bl_idname == "MESH_OT_delete":
        #     ...
    # 无操作回调，例如在属性面板修改
    # else:
    #     if depsgraph.id_type_updated("OBJECT") and context.mode == "OBJECT":
    #         for update in depsgraph.updates:
    #             if not update.is_updated_transform:
    #                 break

    #             obj = update.id  # type: Object # type: ignore
    #             if not isinstance(obj, bpy.types.Object):
    #                 break

    #             sec_data = obj.amagate_data.get_sector_data()
    #             if sec_data is None:
    #                 continue
    #             if sec_data.connect_num != 0:
    #                 CONNECT_SECTORS.add(obj)

    #                 if CHECK_CONNECT.acquire(blocking=False):
    #                     bpy.app.timers.register(check_connect_timer, first_interval=2.0)

    DEPSGRAPH_UPDATE_LOCK.release()


# 定义检查函数
# @bpy.app.handlers.persistent
def check_before_save(filepath):
    scene_data = bpy.context.scene.amagate_data
    if not scene_data.is_blade:
        return

    render_view_index = next((i for i, a in enumerate(bpy.context.screen.areas) if a.type == "VIEW_3D" and a.spaces[0].shading.type == "RENDERED"), -1)  # type: ignore
    scene_data.render_view_index = render_view_index  # 记录渲染区域索引

    scene_data.ensure_coll.values()
    for i in [
        scene_data.ensure_null_obj,
        scene_data.ensure_null_tex,
        scene_data.sec_node,
        scene_data.eval_node,
    ] + [item.obj for item in scene_data.ensure_coll]:
        if i:
            i.use_fake_user = True
    # 保存内置纹理
    if not scene_data.builtin_tex_saved:
        scene_data.builtin_tex_saved = True
        img = None  # type: Image # type: ignore
        img_list = []
        for img in bpy.data.images:  # type: ignore
            img_data = img.amagate_data
            if img_data.builtin:
                img_data.builtin = False
                os.makedirs(
                    os.path.join(os.path.dirname(filepath), "textures"), exist_ok=True
                )
                new_path = os.path.join(
                    os.path.dirname(filepath),
                    "textures",
                    os.path.basename(img.filepath),
                )
                shutil.copy(img.filepath, new_path)
                img_list.append(
                    (img, f"//{os.path.relpath(new_path, os.path.dirname(filepath))}")
                )
        # 保存内置纹理后，延迟设置文件路径
        if img_list:
            bpy.app.timers.register(lambda: tuple(map(lambda x: setattr(x[0], "filepath", x[1]), img_list)) and None, first_interval=0.2)  # type: ignore


def draw_callback_3d():
    context = bpy.context
    scene_data = context.scene.amagate_data
    if not scene_data.is_blade:
        return

    # 当前区域和窗口
    region = context.region
    area = context.area

    # 确保是 VIEW_3D 的 WINDOW 区域
    if area.type != "VIEW_3D" or region.type != "WINDOW":
        return

    index = next(i for i, a in enumerate(context.screen.areas) if a == area)
    if not scene_data.areas_show_hud.get(str(index)):
        return

    # if context.screen.show_fullscreen:
    #     return

    # 获取区域宽高
    width = region.width
    height = region.height

    texts = []

    # 由于该回调在N面板之后，所以不能在这里缓存选中扇区数据
    selected_sectors, active_sector = ag_utils.get_selected_sectors()
    sector_num = len(selected_sectors)

    # 二维球面
    is_2d_sphere_text = pgettext("None")
    color = ag_utils.DefColor.nofocus
    if selected_sectors:
        color = ag_utils.DefColor.red
        is_2d_sphere = selected_sectors[0].amagate_data.get_sector_data().is_2d_sphere
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.is_2d_sphere != is_2d_sphere:
                is_2d_sphere = -1
                is_2d_sphere_text = "*"
                break
        if is_2d_sphere == True:
            is_2d_sphere_text = pgettext("Yes", "Property")
            color = ag_utils.DefColor.white
        elif is_2d_sphere == False:
            is_2d_sphere_text = pgettext("No", "Property")
    _2d_sphere_label = (f"{pgettext('Is 2-Sphere')}: {is_2d_sphere_text}", color)

    # 凸多面体
    is_convex_text = pgettext("None")
    color = ag_utils.DefColor.nofocus
    if selected_sectors:
        color = ag_utils.DefColor.red
        # 如果选中的扇区不是二维球面，则显示为空
        if is_2d_sphere == False:
            is_convex_text = ""
        # 如果选中的扇区是混合拓扑类型，则显示为`*`
        elif is_2d_sphere == -1:
            is_convex_text = "*"
        else:
            is_convex = selected_sectors[0].amagate_data.get_sector_data().is_convex
            for sec in selected_sectors:
                sec_data = sec.amagate_data.get_sector_data()
                if sec_data.is_convex != is_convex:
                    is_convex = -1
                    is_convex_text = "*"
                    break
            if is_convex == True:
                is_convex_text = pgettext("Yes", "Property")
                color = ag_utils.DefColor.white
            elif is_convex == False:
                is_convex_text = pgettext("No", "Property")
    convex_label = (f"{pgettext('Convex Polyhedron')}: {is_convex_text}", color)

    # 选中的扇区
    text = (
        f"{pgettext('Selected Sector')}: {sector_num} / {len(context.selected_objects)}"
    )
    if sector_num == 0:
        color = ag_utils.DefColor.nofocus
    else:
        color = ag_utils.DefColor.white
    selected_sector_label = (text, color)

    # 从下往上绘制HUD信息
    texts.append(convex_label)
    texts.append(_2d_sphere_label)
    texts.append(selected_sector_label)
    #
    font_id = 0  # 内置字体
    for i in range(len(texts)):
        text, color = texts[i]
        # 设置文本属性
        blf.size(font_id, 18)
        blf.color(font_id, *color)

        text_width, text_height = blf.dimensions(font_id, text)
        # 计算右下角的绘制位置
        # x = width - text_width - 40  # 右边距
        # 计算左下角的绘制位置
        x = 20  # 左边距
        y = text_height * i + 10 * (i + 1)  # 下边距

        # 绘制文本
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, text)

    # print("draw_callback_3d")


# 加载后回调
@bpy.app.handlers.persistent
def load_post(filepath=""):
    global OPERATOR_POINTER, draw_handler
    context = bpy.context
    scene_data = context.scene.amagate_data
    if scene_data.is_blade:
        if scene_data.render_view_index != -1:
            spaces = context.screen.areas[scene_data.render_view_index].spaces[0]
            if hasattr(spaces, "shading"):
                spaces.shading.type = "RENDERED"
        bpy.app.handlers.save_pre.append(check_before_save)  # type: ignore
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)  # type: ignore
        if draw_handler is None:
            draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_3d, (), "WINDOW", "POST_PIXEL"
            )
        OPERATOR_POINTER = (
            context.window_manager.operators[-1].as_pointer()
            if context.window_manager.operators
            else None
        )
    else:
        if draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(draw_handler, "WINDOW")
            draw_handler = None


############################
############################ 模板列表
############################


class AMAGATE_UI_UL_StrList(bpy.types.UIList):
    # def draw_filter(self, context, layout):
    #     pass

    def draw_item(
        self,
        context,
        layout: bpy.types.UILayout,
        data,
        item,
        icon,
        active_data,
        active_prop,
    ):
        row = layout.row()
        row.label(text=item.name)


class AMAGATE_UI_UL_AtmoList(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        # 按A-Z排序 # FIXME 没有按照预期排序，不知道为什么
        if self.use_filter_sort_alpha:
            flt_neworder = sorted(
                range(len(items)), key=lambda i: items[i].item_name.lower()
            )
        else:
            flt_neworder = []
        # 按名称过滤
        if self.filter_name:
            flt_flags = [self.bitflag_filter_item] * len(items)  # 默认全部显示
            regex_pattern = re.escape(self.filter_name).replace(r"\*", ".*")
            regex = re.compile(f"{regex_pattern}", re.IGNORECASE)  # 全匹配忽略大小写
            for idx, item in enumerate(items):
                if not regex.search(item.item_name):
                    flt_flags[idx] = 0
        elif self.use_filter_invert:
            flt_flags = [0] * len(items)
        else:
            flt_flags = [self.bitflag_filter_item] * len(items)

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context: Context,
        layout: bpy.types.UILayout,
        data_,
        item,
        icon,
        active_data,
        active_prop,
    ):
        scene_data = context.scene.amagate_data
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        # row.alignment = "LEFT"
        split = row.split(factor=0.6)
        row = split.row()
        # split = row

        # col = split.column()
        # col.enabled = False
        # col.label(text=f"ID: {item.id}")
        i = data.ICONS["star"].icon_id if item.id == scene_data.defaults.atmo_id else 1
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)  # icon="CHECKMARK"

        col = row.column()
        if enabled:
            col.prop(item, "item_name", text="", emboss=False)
        else:
            col.label(text=item.item_name)

        row = split.row()
        row.enabled = enabled
        row.prop(item, "color", text="")


class AMAGATE_UI_UL_ExternalLight(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        # 按A-Z排序
        if self.use_filter_sort_alpha:
            flt_neworder = sorted(
                range(len(items)), key=lambda i: items[i].item_name.lower()
            )
        else:
            flt_neworder = []
        # 按名称过滤
        if self.filter_name:
            flt_flags = [self.bitflag_filter_item] * len(items)  # 默认全部显示
            regex_pattern = re.escape(self.filter_name).replace(r"\*", ".*")
            regex = re.compile(f"{regex_pattern}", re.IGNORECASE)  # 全匹配忽略大小写
            for idx, item in enumerate(items):
                if not regex.search(item.item_name):
                    flt_flags[idx] = 0
        elif self.use_filter_invert:
            flt_flags = [0] * len(items)
        else:
            flt_flags = [self.bitflag_filter_item] * len(items)

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context: Context,
        layout: bpy.types.UILayout,
        data_,
        item,
        icon,
        active_data,
        active_prop,
    ):
        scene_data = context.scene.amagate_data
        light = item
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        split = row.split(factor=0.5)
        row = split.row()

        i = (
            data.ICONS["star"].icon_id
            if light.id == scene_data.defaults.external_id
            else 1
        )
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)

        col = row.column()
        if enabled:
            col.prop(light, "item_name", text="", emboss=False)
        else:
            col.label(text=light.item_name)

        # if enabled:
        split = split.split(factor=0.4)
        row = split.row()
        row.alignment = "RIGHT"
        row.operator(
            "amagate.scene_external_set", text="", icon="LIGHT_SUN", emboss=False
        ).id = light.id  # type: ignore

        row = split.row()
        color = "color" if enabled else "color_readonly"
        row.prop(light, color, text="")


class AMAGATE_UI_UL_TextureList(bpy.types.UIList):
    def draw_filter(self, context, layout):
        row = layout.row()
        row.prop(self, "filter_name", text="", icon="VIEWZOOM")

    def filter_items(self, context, data, propname):
        scene_data = bpy.context.scene.amagate_data
        img = scene_data.ensure_null_tex  # type: Image

        items = getattr(data, propname)
        if self.use_filter_invert:
            invisible = self.bitflag_filter_item
        else:
            invisible = 0
        flt_flags = [self.bitflag_filter_item] * len(items)
        # 天空纹理置顶 # FIXME 没有按照预期排序，不知道为什么
        img_idx = items.find(img.name)
        flt_neworder = [img_idx] + [i for i in range(len(items)) if i != img_idx]

        # 按名称过滤
        regex = None
        if self.filter_name:
            regex_pattern = re.escape(self.filter_name).replace(r"\*", ".*")
            regex = re.compile(f"{regex_pattern}", re.IGNORECASE)  # 全匹配忽略大小写
        for idx, item in enumerate(items):
            if item.amagate_data.id == 0:
                flt_flags[idx] = invisible
            elif regex and not regex.search(item.name):
                flt_flags[idx] = invisible

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context: Context,
        layout: bpy.types.UILayout,
        data_,
        item: Image,
        icon,
        active_data,
        active_prop,
    ):
        scene_data = context.scene.amagate_data
        tex = item
        tex_data = tex.amagate_data  # type: ignore
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()

        # tex.preview.reload()
        i = tex.preview.icon_id if tex.preview else 1
        col = row.column()
        col.alignment = "LEFT"
        # col.label(text="", icon_value=i)
        op = col.operator(
            "amagate.texture_preview", text="", icon_value=i, emboss=False
        )
        op.index = bpy.data.images.find(tex.name)  # type: ignore

        col = row.column()
        if enabled and tex != scene_data.ensure_null_tex:
            col.prop(tex, "name", text="", emboss=False)
        else:
            col.label(text=tex.name)

        row = row.row(align=True)
        col = row.column()
        col.alignment = "RIGHT"
        default_id = [i.id for i in scene_data.defaults.textures if i.id != 0]
        i = data.ICONS["star"].icon_id if tex_data.id in default_id else 1
        col.label(text="", icon_value=i)

        col = row.column()
        col.alignment = "RIGHT"
        i = "UGLYPACKAGE" if tex.packed_file else "BLANK1"
        col.label(text="", icon=i)


############################
############################ 属性回调
############################


############################
############################ Operator Props
############################


# 选择大气
class Atmo_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data = bpy.context.scene.amagate_data
        if self.target == "SectorPublic":
            for sec in SELECTED_SECTORS:
                sec_data = sec.amagate_data.get_sector_data()  # type: ignore
                sec_data.atmo_id = scene_data.atmospheres[value].id
        elif self.target == "Scene":
            scene_data.defaults.atmo_id = scene_data.atmospheres[value].id
        # region_redraw("UI")
        data.area_redraw("VIEW_3D")

        bpy.ops.ed.undo_push(message="Select Atmosphere")


# 选择外部光
class External_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data = bpy.context.scene.amagate_data
        if self.target == "SectorPublic":
            for sec in SELECTED_SECTORS:
                sec_data = sec.amagate_data.get_sector_data()  # type: ignore
                sec_data.external_id = scene_data.externals[value].id
        elif self.target == "Scene":
            scene_data.defaults.external_id = scene_data.externals[value].id
        data.region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select External Light")


# 选择纹理
class Texture_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="")  # type: ignore
    name: StringProperty(default="")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value: int):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data = bpy.context.scene.amagate_data
        if self.target == "SectorPublic":
            scene_data.sector_public.textures[self.name].id = bpy.data.images[
                value
            ].amagate_data.id
        elif self.target == "Scene":
            scene_data.defaults.textures[self.name].id = bpy.data.images[
                value
            ].amagate_data.id

        # data.region_redraw("UI")
        data.area_redraw("VIEW_3D")

        bpy.ops.ed.undo_push(message="Select Texture")


############################
############################ Object Props
############################


# 大气属性
class AtmosphereProperty(bpy.types.PropertyGroup):
    """id从1开始"""

    id: IntProperty(name="ID", default=0, get=lambda self: int(self["name"]))  # type: ignore
    name: StringProperty(name="id key", default="0")  # type: ignore
    item_name: StringProperty(name="Atmosphere Name", default="", get=lambda self: self.get_item_name(), set=lambda self, value: self.set_item_name(value))  # type: ignore
    users_obj: CollectionProperty(type=data.SectorCollection)  # type: ignore
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=4,  # RGBA
        min=0.0,
        max=1.0,
        default=(0.0, 0.0, 0.0, 0.0),
        get=lambda self: self.get_color(),
        set=lambda self, value: self.set_color(value),
    )  # type: ignore
    # intensity: FloatProperty(name="Intensity", default=0.02)  # type: ignore

    def get_item_name(self):
        return self.get("_item_name", "")

    def set_item_name(self, value):
        if value == "":
            return

        scene_data = bpy.context.scene.amagate_data
        atmos = scene_data.atmospheres
        for atmo in atmos:
            if atmo.item_name == value and atmo != self:
                atmo["_item_name"] = self["_item_name"]
                break
        self["_item_name"] = value

    def get_color(self):
        return self.get("_color", (0.0, 0.0, 0.0, 0.002))

    def set_color(self, value):
        if value == tuple(self.color):
            return

        self["_color"] = value
        for user in self.users_obj:
            obj = user.obj  # type: Object
            obj.amagate_data.get_sector_data().update_atmo(self)
        data.area_redraw("VIEW_3D")


# 外部光属性
class ExternalLightProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0, get=lambda self: int(self["name"]))  # type: ignore
    name: StringProperty(name="id key", default="0")  # type: ignore
    item_name: StringProperty(name="Light Name", default="", get=lambda self: self.get_item_name(), set=lambda self, value: self.set_item_name(value))  # type: ignore
    obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    data: PointerProperty(type=bpy.types.Light)  # type: ignore
    users_obj: CollectionProperty(type=data.SectorCollection)  # type: ignore

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        # default=(0.784, 0.784, 0.784),
        get=lambda self: self.get("_color", (0.784, 0.784, 0.392)),
        set=lambda self, value: self.set_dict("_color", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    color_readonly: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        get=lambda self: self.get("_color", (0.784, 0.784, 0.392)),
        set=lambda self, value: None,
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Direction",
        subtype="XYZ",
        # default=(0.0, 0.0, -1.0),  # 默认向量值
        size=3,  # 必须是 3 维向量
        min=-1.0,
        max=1.0,
        get=lambda self: self.get("_vector", (-1, 0, -1)),
        set=lambda self, value: self.set_dict("_vector", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    vector2: FloatVectorProperty(
        name="Direction",
        subtype="DIRECTION",
        size=3,  # 必须是 3 维向量
        min=-1.0,
        max=1.0,
        get=lambda self: self.get("_vector", (-1, 0, -1)),
        set=lambda self, value: self.set_dict("_vector", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore

    def set_dict(self, key, value):
        self[key] = value

    def get_item_name(self):
        return self.get("_item_name", "")

    def set_item_name(self, value):
        if value == "":
            return

        scene_data = bpy.context.scene.amagate_data
        lights = scene_data.externals
        for l in lights:
            if l.item_name == value and l != self:
                l["_item_name"] = self["_item_name"]
                break
        self["_item_name"] = value

    def ensure_obj(self):
        name = f"AG.Sun{self.id}"
        if not self.data:
            light_data = bpy.data.lights.get(name)
            if not (light_data and light_data.type == "SUN"):
                light_data = bpy.data.lights.new("", type="SUN")
                light_data.rename(name, mode="ALWAYS")
            light_data.volume_factor = 0.0  # 体积散射
            self.data = light_data
        if not self.obj:
            light_data = self.data
            light = bpy.data.objects.get(name)
            if not light:
                light = bpy.data.objects.new(name, light_data)
            else:
                light.data = light_data
            self.obj = light
            light.hide_select = True  # 不可选
            data.link2coll(light, ensure_collection(AG_COLL, hide_select=True))

        # return self.data

    # def sync_users(self, rotation_euler):
    #     for i in self.users_obj:
    #         sec = i.obj  # type: Object
    #         sec.amagate_data.get_sector_data().update_external(self, rotation_euler)

    def update_obj(self, context=None):
        self.ensure_obj()
        self.data.color = self.color  # 设置颜色
        self.data.energy = self.color.v * 1.7  # 设置强度
        rotation_euler = self.vector.to_track_quat("-Z", "Z").to_euler()
        self.obj.rotation_euler = rotation_euler  # 设置方向
        # self.sync_users(rotation_euler)


# 环境光属性
# class AmbientLightProperty(bpy.types.PropertyGroup):
#     color: FloatVectorProperty(
#         name="Color",
#         subtype="COLOR",
#         size=3,
#         min=0.0,
#         max=1.0,
#         default=(0.784, 0.784, 0.784),
#     )  # type: ignore


# 操作属性
class OperatorProperty(bpy.types.PropertyGroup):
    # OT_Sector_Connect
    sec_connect_sep_convex: BoolProperty(name="Auto Separate Convex", default=True)  # type: ignore
    # OT_Sector_SeparateConvex
    sec_separate_connect: BoolProperty(name="Auto Connect", default=True)  # type: ignore
    camera_sync: BoolProperty(name="Camera Sync", default=False, get=lambda self: self.get("camera_sync", False), set=lambda self, value: self.set_camera_sync(value))  # type: ignore

    def set_camera_sync(self, value):
        self["camera_sync"] = value
        scene = bpy.context.scene
        #
        if not value:
            script = (
                """e=Bladex.GetEntity("Camera");e.SetPersonView("Player1");e.Cut()"""
            )
        else:
            cam = scene.camera
            if cam:
                cam_pos, target_pos = ag_utils.get_camera_transform(cam)  # type: ignore
                script_extra = f"e.Position={cam_pos};e.TPos={target_pos}"
            else:
                script_extra = ""
            script = f"""
if 1:
    e=Bladex.GetEntity("Camera")
    e.TType=e.SType=0
    {script_extra}
"""
        ag_service.send_exec_script(script)


# 图像属性
class ImageProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    mat_obj: PointerProperty(type=bpy.types.Material)  # type: ignore
    # Amagate内置纹理标识
    builtin: BoolProperty(name="Builtin", default=False)  # type: ignore


# 场景属性
class SceneProperty(bpy.types.PropertyGroup):
    from . import sector_data

    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore
    # 大气
    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(name="Atmosphere", default=0)  # type: ignore

    # 外部光
    externals: CollectionProperty(type=ExternalLightProperty)  # type: ignore
    active_external: IntProperty(name="External Light", default=0)  # type: ignore
    # 平面光设置
    flat_light: BoolProperty(get=lambda self: sector_data.get_flat_light(), set=lambda self, value: sector_data.set_flat_light(value))  # type: ignore

    active_texture: IntProperty(name="Texture", default=0, set=lambda self, value: self.set_active_texture(value), get=lambda self: self.get_active_texture())  # type: ignore

    defaults: PointerProperty(type=sector_data.SectorProperty)  # type: ignore # 扇区默认属性

    # 纹理预览
    tex_preview: PointerProperty(type=bpy.types.Image)  # type: ignore
    builtin_tex_saved: BoolProperty(name="Builtin Tex Saved", default=False)  # type: ignore
    # 存储确保对象
    ensure_null_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    ensure_null_tex: PointerProperty(type=bpy.types.Image)  # type: ignore
    ensure_coll: CollectionProperty(type=data.CollCollection)  # type: ignore
    render_cam: PointerProperty(type=bpy.types.Object)  # type: ignore
    # 存储节点
    sec_node: PointerProperty(type=bpy.types.NodeTree)  # type: ignore
    eval_node: PointerProperty(type=bpy.types.NodeTree)  # type: ignore

    # 渲染视图索引
    render_view_index: IntProperty(name="Render View Index", default=-1)  # type: ignore

    areas_show_hud: CollectionProperty(type=data.IntegerCollection)  # type: ignore

    # 操作属性
    operator_props: PointerProperty(type=OperatorProperty)  # type: ignore

    # 扇区灯泡操作
    bulb_operator: PointerProperty(type=sector_data.BulbOperatorProp)  # type: ignore

    # 通用属性
    sector_public: PointerProperty(type=sector_data.SectorProperty)  # type: ignore
    face_type: EnumProperty(
        name="",
        description="",
        translation_context="Property",
        items=[
            ("Floor", "Floor", ""),
            ("Ceiling", "Ceiling", ""),
            ("Wall", "Wall", ""),
            ("Custom", "Custom", ""),
        ],
        default="Floor",
        get=lambda self: self.get_face_type(),
        set=lambda self, value: self.set_face_type(value),
    )  # type: ignore

    # 进度条
    progress_bar: PointerProperty(type=data.ProgressBarProperty)  # type: ignore

    # 天空纹理枚举
    sky_tex_enum: EnumProperty(
        name="",
        description="",
        items=[
            ("1", "Casa", "Casa"),
            ("2", "Kashgar", "Kashgar"),
            ("3", "Tabriz (The Abyss)", "Tabriz"),
            ("4", "Khazel Zalam (Fortress of Nemrut)", "Khazel Zalam"),
            ("5", "Marakamda", "Marakamda"),
            ("6", "Mines of Kelbegen", "Mines of Kelbegen"),
            (
                "7",
                "Fortress of Tell Halaf (The Gorge of Orlok)",
                "Fortress of Tell Halaf",
            ),
            ("8", "Tombs of Ephyra", "Tombs of Ephyra"),
            ("9", "Island of Karum", "Island of Karum"),
            ("10", "Shalatuwar Fortress", "Shalatuwar Fortress"),
            ("11", "The Oasis of Nejeb", "The Oasis of Nejeb"),
            ("12", "Temple of Al Farum", "Temple of Al Farum"),
            ("13", "Forge of Xshathra", "Forge of Xshathra"),
            ("14", "The Temple of Ianna", "The Temple of Ianna"),
            ("15", "Tower of Dal Gurak", "Tower of Dal Gurak"),
            #
            ("", "", ""),
            #
            ("16", "Casa - Reforged", "Casa - Reforged"),
            ("17", "Kashgar - Reforged", "Kashgar - Reforged"),
            ("18", "Khazel Zalam - Reforged", "Khazel Zalam - Reforged"),
            ("19", "Marakamda - Reforged", "Marakamda - Reforged"),
            ("20", "Mines of Kelbegen - Reforged", "Mines of Kelbegen - Reforged"),
            ("21", "Tombs of Ephyra - Reforged", "Tombs of Ephyra - Reforged"),
            ("22", "Shalatuwar Fortress - Reforged", "Shalatuwar Fortress - Reforged"),
            ("23", "Fortress of Nemrut - Reforged", "Fortress of Nemrut - Reforged"),
            ("24", "The Oasis of Nejeb - Reforged", "The Oasis of Nejeb - Reforged"),
            ("25", "Temple of Al Farum - Reforged", "Temple of Al Farum - Reforged"),
            ("26", "The Temple of Ianna - Reforged", "The Temple of Ianna - Reforged"),
            ("27", "Tower of Dal Gurak - Reforged", "Tower of Dal Gurak - Reforged"),
            ("28", "The Abyss - Reforged", "The Abyss - Reforged"),
            ("-1", "Custom", ""),
        ],
        default="5",  # 默认选中项
        get=lambda self: self.get_sky_tex_enum(),
        set=lambda self, value: self.set_sky_tex_enum(value),
        # update=lambda self, context: self.update_sky_tex_enum(context),
    )  # type: ignore
    # 天空颜色
    sky_color: FloatVectorProperty(
        name="Color",
        description="Not supported in the Reissue version",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1, 1, 1),
        update=lambda self, context: self.update_sky_color(context),
    )  # type: ignore

    # 坐标转换
    coord_conv_1: StringProperty(name="Blade Coord", default="0, 0, 0", get=lambda self: self.get_coord_conv_1(), set=lambda self, value: None)  # type: ignore
    coord_conv_2: StringProperty(name="Blade Coord", default="0, 0, 0", get=lambda self: self.get("set_coord_conv_2", "0, 0, 0"), set=lambda self, value: self.set_coord_conv_2(value))  # type: ignore

    # 编辑模式标识
    is_edit_mode: BoolProperty(name="Edit Mode", default=False)  # type: ignore

    # 灯光链接管理器
    light_link_manager: CollectionProperty(type=data.ObjectCollection)  # type: ignore

    ############################

    def get_coord_conv_1(self):
        context = bpy.context
        selected_objects = context.selected_objects
        if selected_objects:
            location = (selected_objects[0].location * 1000).to_tuple(0)
        # 如果没有选中物体，则返回游标位置
        else:
            location = (context.scene.cursor.location * 1000).to_tuple(0)
        return f"{location[0], -location[2], location[1]}"

    def set_coord_conv_2(self, value):
        self["set_coord_conv_2"] = value
        context = bpy.context
        scene_data = context.scene.amagate_data
        try:
            position = ast.literal_eval(scene_data.coord_conv_2)
        except:
            return
        # 如果元组不是3个数字，则不处理
        if len(position) != 3 or not all(isinstance(i, (int, float)) for i in position):
            return

        self["set_coord_conv_2"] = str(position)
        location = position[0] / 1000.0, position[2] / 1000.0, -position[1] / 1000.0

        selected_objects = context.selected_objects
        if selected_objects:
            for obj in selected_objects:
                obj.location = location
        # 如果没有选中物体，则设置游标位置
        else:
            context.scene.cursor.location = location

    ############################

    def get_active_texture(self):
        value = self.get("_active_texture", 0)

        if value >= len(bpy.data.images) or bpy.data.images[value].amagate_data.id == 0:
            value = next((i for i, img in enumerate(bpy.data.images) if img.amagate_data.id != 0), 0)  # type: ignore

        return value

    def set_active_texture(self, value):
        self["_active_texture"] = value

    ############################

    def get_sky_tex_enum(self):
        return self.get("sky_tex_enum", 4)

    # def update_sky_tex_enum(self, context: Context):
    def set_sky_tex_enum(self, value):
        prop_rna = self.bl_rna.properties["sky_tex_enum"]
        enum_items = prop_rna.enum_items  # type: ignore
        item = enum_items[value]
        enum_id = item.identifier
        if enum_id == "-1":
            return

        # 通过ID查找名称
        selected_name = item.description
        # selected_name = next(
        #     (item.description for item in enum_items if item.identifier == enum_id),
        #     None,
        # )
        if selected_name is None:
            return

        filepath = os.path.join(
            data.ADDON_PATH, f"textures/panorama/{selected_name}.jpg"
        )
        if not os.path.exists(filepath):
            bpy.context.window_manager.popup_menu(
                lambda self, context: self.layout.label(
                    text="Texture not found, please click the download button."
                ),
                title=pgettext("Warning"),
                icon="ERROR",
            )
            return

        img = ensure_null_texture()
        img.filepath = filepath
        img.reload()
        # print(f"selected_name: {selected_name}")
        self["sky_tex_enum"] = value

    def update_sky_color(self, context):
        scene = self.id_data  # type: Scene
        scene.update_tag()
        data.area_redraw("VIEW_3D")

    ############################

    def get_face_type(self):
        # 选择的面
        selected_faces = SELECTED_FACES
        if not selected_faces:
            return -1

        layers = selected_faces[0][0].faces.layers.int.get("amagate_flag")
        face_type = selected_faces[0][1][0][layers]  # type: ignore
        for item in selected_faces:
            layers = item[0].faces.layers.int.get("amagate_flag")
            for f in item[1]:
                if f[layers] != face_type:  # type: ignore
                    return -1

        return face_type

    def set_face_type(self, value):
        identifier = self.bl_rna.properties["face_type"].enum_items[value].identifier  # type: ignore
        # 选择的面
        for item in SELECTED_FACES:
            sec = item[2]
            sec_data = sec.amagate_data.get_sector_data()
            bm = item[0]
            if identifier != "Custom":
                tex_prop = sec_data.textures[identifier]
                tex_id = tex_prop.id
                tex = get_texture_by_id(tex_id)[1]
                attr_list = (
                    (bm.faces.layers.int.get("amagate_tex_id"), tex_id),
                    (bm.faces.layers.float.get("amagate_tex_xpos"), tex_prop.xpos),
                    (bm.faces.layers.float.get("amagate_tex_ypos"), tex_prop.ypos),
                    (bm.faces.layers.float.get("amagate_tex_xzoom"), tex_prop.xzoom),
                    (bm.faces.layers.float.get("amagate_tex_yzoom"), tex_prop.yzoom),
                    (bm.faces.layers.float.get("amagate_tex_angle"), tex_prop.angle),
                )

            flag_layer = bm.faces.layers.int.get("amagate_flag")
            # selected_faces = ag_utils.expand_conn(item[1], bm)
            selected_faces = item[1]
            for face in selected_faces:
                face[flag_layer] = FACE_FLAG[identifier]  # type: ignore
                #
                if identifier != "Custom":
                    for layer, value in attr_list:
                        face[layer] = value  # type: ignore
            #
            if identifier != "Custom":
                sec_data.set_matslot(ensure_material(tex), selected_faces, bm)
                sec.update_tag()
        data.area_redraw("VIEW_3D")

    ############################
    def init(self):
        #
        self["SectorManage"] = {"deleted_id_count": 0, "max_id": 0, "sectors": {}}
        defaults = self.defaults

        defaults.target = "Scene"
        defaults.atmo_id = 1
        defaults.external_id = 1
        defaults.ambient_color = (0.5, 0.5, 0.5)

        defaults.flat_light.target = "Scene"
        self.sector_public.target = "SectorPublic"
        self.sector_public.flat_light.target = "SectorPublic"
        ############################
        for i in ("Floor", "Ceiling", "Wall"):
            prop = defaults.textures.add()
            prop.target = "Scene"
            prop.name = i
            prop.id = 1
            prop.xpos = prop.ypos = 0.0
            prop.xzoom = prop.yzoom = 20.0
            if i == "Wall":
                prop.angle = -math.pi * 0.5
            else:
                prop.angle = 0.0

            prop = self.sector_public.textures.add()
            prop.name = i
            prop.target = "SectorPublic"

        # 添加32个组
        for i in range(32):
            prop = self.sector_public.group_set.add()
            prop.index = i


############################


def register_timer():
    bpy.app.handlers.load_post.append(load_post)  # type: ignore
    load_post(None)


############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and any(issubclass(cls, parent) for parent in class_tuple)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty, name="Amagate Data")  # type: ignore
    bpy.types.Image.amagate_data = PointerProperty(type=ImageProperty, name="Amagate Data")  # type: ignore

    # 注册回调函数
    bpy.app.timers.register(register_timer, first_interval=0.5)  # type: ignore


def unregister():
    global draw_handler
    del bpy.types.Scene.amagate_data  # type: ignore
    del bpy.types.Image.amagate_data  # type: ignore

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # 注销回调函数
    if load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post)  # type: ignore
    if check_before_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(check_before_save)  # type: ignore
    if depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)  # type: ignore
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, "WINDOW")
        draw_handler = None
    # 关闭服务器
    ag_service.stop_server()
