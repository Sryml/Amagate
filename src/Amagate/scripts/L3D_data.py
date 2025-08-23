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
import asyncio

from pathlib import Path
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
from ..service import ag_service, protocol

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
LAST_SENT_TIME = 0  # 上次发送时间
SYNC_INTERVAL = ag_service.SYNC_INTERVAL

# 大气切换
LAST_ATMO_SWITCH = 0
ATMO_SWITCH_INTERVAL = 0.5

#
ASYNC_THREAD = None  # type: AsyncThread | None

# 当前视角所在扇区
# CURRENT_SECTOR = None # type: Object  # type: ignore

AG_COLL = "Amagate Auto Generated"
S_COLL = "Sector Collection"
GS_COLL = "Ghost Sector Collection"
E_COLL = "Entity Collection"
C_COLL = "Camera Collection"
M_COLL = "Marked Collection"

# CONNECT_SECTORS = set()

# 锁
DEPSGRAPH_UPDATE_LOCK = threading.Lock()
CHECK_CONNECT = threading.Lock()

# 全景图下载锁
PANORAMA_LOCK = threading.Lock()

S_COLL_OBJECTS = 0
OPERATOR_POINTER = None
draw_handler = None
LOAD_POST_CALLBACK = None
SAVE_POST_CALLBACK = None
#
SELECTED_FACES = (
    []
)  # type: list[tuple[bmesh.types.BMesh, list[bmesh.types.BMFace], Object]]
SELECTED_SECTORS: list[Object] = []
ACTIVE_SECTOR: Object = None  # type: ignore

FACE_FLAG = {"Floor": 0, "Ceiling": 1, "Wall": 2, "Custom": 3}
#
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
    # type: (data.SceneProperty, Any) -> tuple[int, AtmosphereProperty]
    idx = scene_data.atmospheres.find(str(atmo_id))
    atmo = scene_data.atmospheres[idx] if idx != -1 else None
    return (idx, atmo)  # type: ignore


def get_external_by_id(scene_data, external_id):
    # type: (data.SceneProperty, Any) -> tuple[int, ExternalLightProperty]
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


def get_level_item(this, context):
    map_dir = Path(bpy.data.filepath).parent.name
    items = [
        ("-1", map_dir, map_dir),
        ("0", "Casa", "Casa"),
        ("1", "Kashgar", "Barb_M1"),
        ("2", "Tabriz", "Ragnar_M2"),
        ("3", "Khazel Zalam", "Dwarf_M3"),
        ("4", "Marakamda", "Ruins_M4"),
        ("5", "Mines of Kelbegen", "Mine_M5"),
        ("6", "Fortress of Tell Halaf", "Labyrinth_M6"),
        ("7", "Tombs of Ephyra", "Tomb_M7"),
        ("8", "Island of Karum", "Island_M8"),
        ("9", "Shalatuwar Fortress", "Orc_M9"),
        ("10", "The Gorge of Orlok", "Orlok_M10"),
        ("11", "Fortress of Nemrut", "Ice_M11"),
        ("12", "The Oasis of Nejeb", "Btomb_M12"),
        ("13", "Temple of Al Farum", "Desert_M13"),
        ("14", "Forge of Xshathra", "Volcano_M14"),
        ("15", "The Temple of Ianna", "Palace_M15"),
        ("16", "Tower of Dal Gurak", "Tower_M16"),
        ("17", "The Abyss", "Chaos_M17"),
    ]
    get_level_item.items = items
    return items


# 确保NULL纹理存在
def ensure_null_texture() -> Image:
    scene_data = bpy.context.scene.amagate_data
    img = scene_data.ensure_null_tex  # type: Image
    if not img:
        # img = bpy.data.images.new("NULL", width=256, height=256)  # type: ignore
        enum_items_static_ui = scene_data.bl_rna.properties["sky_tex_enum"].enum_items_static_ui  # type: ignore
        file_name = enum_items_static_ui[scene_data.get_sky_tex_enum()].description
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
        # cam_data.sensor_width = 100
        cam_data.passepartout_alpha = 0.98
        cam_data.angle = 1.59
        # cam_data.lens = 49.0
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
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        # )
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        # )

        data.import_nodes(NodeTree, nodes_data["Amagate Eval"])
        NodeTree.use_fake_user = True
        NodeTree.is_tool = True  # type: ignore
        NodeTree.is_type_mesh = True  # type: ignore
        scene_data.eval_node = NodeTree
    #
    # NodeTree = bpy.data.node_groups.get("AG.FrustumCulling")
    # if not NodeTree:
    #     NodeTree = bpy.data.node_groups.new("AG.FrustumCulling", "GeometryNodeTree")  # type: ignore
    # data.import_nodes(NodeTree, nodes_data["AG.FrustumCulling"])
    # NodeTree.use_fake_user = True
    # NodeTree.is_tool = True  # type: ignore
    # NodeTree.is_type_mesh = True  # type: ignore
    #
    NodeTree = scene_data.sec_node
    if not NodeTree:
        NodeTree = bpy.data.node_groups.new("AG.SectorNodes", "GeometryNodeTree")  # type: ignore
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        # )
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        # )
        data.import_nodes(NodeTree, nodes_data["AG.SectorNodes"])
        NodeTree.use_fake_user = True
        NodeTree.is_modifier = True  # type: ignore
        scene_data.sec_node = NodeTree
    # 烘焙世界节点
    # name = "AG.World Baking.NodeGroup"
    # if bpy.data.node_groups.get(name) is None:
    #     NodeTree = bpy.data.node_groups.new(name, "GeometryNodeTree")  # type: ignore
    #     data.import_nodes(NodeTree, nodes_data[name])
    #     NodeTree.use_fake_user = True
    # name = "AG.World Baking"
    # if bpy.data.node_groups.get(name) is None:
    #     NodeTree = bpy.data.node_groups.new(name, "GeometryNodeTree")  # type: ignore
    #     data.import_nodes(NodeTree, nodes_data[name])
    #     NodeTree.nodes["Collection Info"].inputs[0].default_value = ensure_collection(S_COLL)  # type: ignore
    #     NodeTree.use_fake_user = True
    #     NodeTree.is_modifier = True  # type: ignore


def update_scene_edit_mode():
    context = bpy.context
    scene_data = context.scene.amagate_data
    scene_data.is_edit_mode = context.mode != "OBJECT"
    scene_data.show_connected = scene_data.is_edit_mode and scene_data.show_connected_sw
    context.scene.update_tag()


############################
############################ 异步线程
############################


class AsyncThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()
        self.frustum_culling_event: asyncio.Event  # 视锥裁剪事件
        self.frustum_culling_args = ()  # type: tuple[Scene, Vector, Vector, int, int] # type: ignore

    def set_hide_viewport(self, queue):
        # type: (list[tuple[Object, bool]]) -> Callable[[], None]
        def func():
            for sec, hide_viewport in queue:
                if sec.hide_viewport != hide_viewport:
                    sec.hide_viewport = hide_viewport
            queue.clear()

        return func

    async def frustum_culling(self):
        try:
            while True:
                await self.frustum_culling_event.wait()
                #
                scene, origin, direction, front_id, back_id = self.frustum_culling_args
                SectorManage = scene.amagate_data["SectorManage"]
                max_id = SectorManage["max_id"]
                queue = []
                #
                while front_id <= max_id or back_id >= 1:
                    # if len(queue) > 10:
                    #     bpy.app.timers.register(self.set_hide_viewport(queue.copy()), first_interval=0.01)
                    #     queue.clear()
                    #
                    if front_id <= max_id:
                        sec = SectorManage["sectors"].get(str(front_id), {"obj": None})[
                            "obj"
                        ]  # type: Object
                        if sec:
                            bbox_corners = [
                                sec.matrix_world @ Vector(corner)
                                for corner in sec.bound_box
                            ]
                            center = sum(bbox_corners, Vector()) / 8
                            vector = (center - origin).normalized()
                            distance = (center - origin).length
                            if distance < 40:
                                hide_viewport = False
                            elif distance < 600 and vector.dot(direction) > 0.68:
                                hide_viewport = False
                            else:
                                hide_viewport = True
                            queue.append((sec, hide_viewport))
                        #
                        front_id += 1
                    #
                    if back_id >= 1:
                        sec = SectorManage["sectors"].get(str(back_id), {"obj": None})[
                            "obj"
                        ]  # type: Object
                        if sec:
                            bbox_corners = [
                                sec.matrix_world @ Vector(corner)
                                for corner in sec.bound_box
                            ]
                            center = sum(bbox_corners, Vector()) / 8
                            vector = (center - origin).normalized()
                            distance = (center - origin).length
                            if distance < 40:
                                hide_viewport = False
                            elif distance < 600 and vector.dot(direction) > 0.68:
                                hide_viewport = False
                            else:
                                hide_viewport = True
                            queue.append((sec, hide_viewport))
                        #
                        back_id -= 1
                #
                # logger.debug(f"len(queue) :{len(queue)}")
                if len(queue) > 0:
                    bpy.app.timers.register(
                        self.set_hide_viewport(queue), first_interval=0.0
                    )
                #
                await asyncio.sleep(6)
                self.frustum_culling_event.clear()
        except asyncio.CancelledError:
            pass

    #
    async def stop(self):
        for task in asyncio.all_tasks(self.loop):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.loop.stop()

    #
    def run(self):
        logger.debug("AsyncThread start")
        self.frustum_culling_event = asyncio.Event()
        asyncio.set_event_loop(self.loop)
        # self.loop.run_until_complete(self.frustum_culling())
        self.loop.create_task(self.frustum_culling())
        self.loop.run_forever()
        self.loop.close()
        logger.debug("AsyncThread closed")


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


# 删除检查
def check_delete():
    collection = bpy.context.scene.collection
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

    # 检查已删除的扇区
    coll = ensure_collection(S_COLL)
    SectorManage = scene_data.get("SectorManage")

    exist_ids = set(str(obj.amagate_data.get_sector_data().id) for obj in coll.all_objects if obj.amagate_data.is_sector)  # type: ignore
    all_ids = set(SectorManage["sectors"].keys())
    deleted_ids = sorted(all_ids - exist_ids, reverse=True)
    # 检查已删除的实体
    deleted_entities = [
        k
        for k, v in scene_data["EntityManage"].items()
        if v is None or collection.all_objects.get(v.name) is None
    ]

    if deleted_ids or deleted_entities:
        bpy.ops.ed.undo()
        #
        if deleted_ids:
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
        #
        for k in deleted_entities:
            ag_utils.delete_entity(k)
        #
        bpy.ops.ed.undo_push(message=f"L3D {pgettext('Delete')}")


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


# 复制检查
def check_duplicate():
    from . import entity_data

    context = bpy.context
    dup_sectors = [
        obj for obj in context.selected_objects if obj.amagate_data.is_sector
    ]
    dup_entities = [
        obj for obj in context.selected_objects if obj.amagate_data.is_entity
    ]
    if not (dup_sectors or dup_entities):
        return
    # 复制扇区
    sector_id_map = {}
    for sec in dup_sectors:
        sec_data = sec.amagate_data.get_sector_data()
        old_id = sec_data.id
        sec_data.init(post_copy=True)
        sector_id_map[old_id] = sec_data.id
    for sec in dup_sectors:
        sec_data = sec.amagate_data.get_sector_data()
        mesh = sec.data  # type: bpy.types.Mesh # type: ignore
        conn_count = 0
        for d in mesh.attributes["amagate_connected"].data:  # type: ignore
            conn_sid = sector_id_map.get(d.value, 0)
            if conn_sid != 0:
                conn_count += 1
            d.value = conn_sid
        sec_data.connect_num = conn_count
    ag_utils.dissolve_limit_sectors(dup_sectors)

    # 复制实体
    coll = ensure_collection(E_COLL)
    for ent in dup_entities:
        ent_data = ent.amagate_data.get_entity_data()
        split = ent_data.Name.split("_")
        if split[-1].isdecimal():
            prefix = "_".join(split[:-1]) + "_"
        else:
            prefix = f"{ent_data.Name}_"
        new_name = entity_data.get_name(context, prefix)
        ent_data.clear_deleted_children()
        # 复制库存
        coll_props = (
            ent_data.equipment_inv,
            ent_data.prop_inv,
            ent_data.contained_item,
        )
        # suffix = ("_Equip_", "_Prop_")
        for idx in (0, 1, 2):
            coll_prop = coll_props[idx]
            for item_idx in range(len(coll_prop) - 1, -1, -1):
                item = coll_prop[item_idx]
                obj = item.obj  # type: Object
                new_obj = obj.copy()
                new_ent_data = new_obj.amagate_data.get_entity_data()
                if idx == 2:
                    new_obj_name = entity_data.get_name(
                        context, f"{new_ent_data.Kind}_"
                    )
                    new_ent_data.Name = new_obj_name
                item.obj = new_obj
                data.link2coll(new_obj, coll)
        # 复制完库存再改名称
        ent_data.Name = new_name

    # 取消用户的操作选项
    if dup_sectors:
        context.view_layer.objects.active = dup_sectors[0]  # 设为活动对象
        bpy.ops.object.mode_set(mode="EDIT")

    def timer():
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.ed.undo_push(message=f"L3D {pgettext('Duplicate')}")

    bpy.app.timers.register(timer, first_interval=0.05)


# 粘贴检查
def check_paste():
    context = bpy.context
    paste_sectors = [
        obj for obj in context.selected_objects if obj.amagate_data.is_sector
    ]
    paste_entities = [
        obj for obj in context.selected_objects if obj.amagate_data.is_entity
    ]
    if paste_sectors or paste_entities:
        bpy.ops.ed.undo()
        bpy.ops.ed.undo_push(message="L3D Paste Check")


# 变换检查
def check_transform(bl_idname):
    context = bpy.context
    current_time = time.time()

    sectors = [obj for obj in context.selected_objects if obj.amagate_data.is_sector]
    conn_sectors = [
        sec for sec in sectors if sec.amagate_data.get_sector_data().connect_num != 0
    ]
    # if not conn_sectors:
    #     return

    for sec in conn_sectors:
        ag_utils.check_connect(sec)

    # 如果是旋转操作，检查陡峭
    if bl_idname == "TRANSFORM_OT_rotate":
        for sec in sectors:
            ag_utils.steep_check(sec)
    # 如果是移动操作，检查实体
    elif bl_idname == "TRANSFORM_OT_translate":
        obj = bpy.data.objects.get("AG.BakeWorld")  # type: Object # type: ignore
        if obj:
            entities = [
                obj for obj in context.selected_objects if obj.amagate_data.is_entity
            ]
            for entity in entities:
                result, location, normal, index = obj.ray_cast(
                    entity.location, (0, 0, -1)
                )
                if result:
                    color = obj.data.attributes["ambient_color"].data[index].vector  # type: ignore
                    entity["AG.ambient_color"] = color  # type: ignore
                    entity.update_tag()

    bpy.ops.ed.undo_push(message=f"L3D {pgettext('Transform')}")


# 扇区选择检查
def check_sector_select():
    context = bpy.context
    scene_data = context.scene.amagate_data
    selected_sectors, active_sector = ag_utils.get_selected_sectors()
    if active_sector:
        sec_data = active_sector.amagate_data.get_sector_data()
        # 显示活动扇区的外部光
        externals = scene_data.externals
        if len(externals) > 1:
            idx, item = get_external_by_id(scene_data, sec_data.external_id)
            if item and item.obj.hide_viewport:
                item.obj.hide_viewport = False
                for item_2 in externals:
                    if item_2 != item:
                        item_2.obj.hide_viewport = True
        # 显示活动扇区的大气
        idx, item = get_atmo_by_id(scene_data, sec_data.atmo_id)
        id_key = item.name
        if scene_data.atmo_id_key != id_key:
            scene_data.atmo_id_key = id_key


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
    global OPERATOR_POINTER, S_COLL_OBJECTS, LAST_SENT_TIME, LAST_ATMO_SWITCH
    scene_data = scene.amagate_data
    if not scene_data.is_blade:
        return

    # XXX 待优化。目前没有获取撤销堆栈的Python API，因此在模态模式也会执行回调
    if not DEPSGRAPH_UPDATE_LOCK.acquire(blocking=False):
        return

    context = bpy.context

    #
    current_time = time.time()
    # 摄像机移动检查
    for update in depsgraph.updates:
        obj = update.id
        if not isinstance(update.id, bpy.types.Object):
            continue
        if not update.is_updated_transform:
            continue
        if scene.camera and scene.camera.name == obj.name:
            cam = scene.camera
            #
            if (
                scene_data.frustum_culling
                and ASYNC_THREAD
                and not ASYNC_THREAD.frustum_culling_event.is_set()
            ):
                # logger.debug("frustum_culling_event.set")
                front_id = scene_data["SectorManage"]["max_id"] // 2
                back_id = front_id - 1
                origin = cam.matrix_world.to_translation()
                direction = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
                direction.normalize()
                hit_obj = None  # type: Object # type: ignore
                result, location, normal, index, hit_obj, matrix = scene.ray_cast(
                    bpy.context.evaluated_depsgraph_get(),
                    origin,
                    direction=(0, 0, 1),
                )
                if hit_obj:
                    sec_data = hit_obj.amagate_data.get_sector_data()
                    if sec_data:
                        front_id = sec_data.id
                        back_id = front_id - 1
                ASYNC_THREAD.frustum_culling_args = (
                    scene,
                    origin,
                    direction,
                    front_id,
                    back_id,
                )
                ASYNC_THREAD.loop.call_soon_threadsafe(
                    ASYNC_THREAD.frustum_culling_event.set
                )
            if current_time - LAST_ATMO_SWITCH > ATMO_SWITCH_INTERVAL:
                LAST_ATMO_SWITCH = current_time
                #
                origin = cam.matrix_world.to_translation()
                hit_obj = None  # type: Object # type: ignore
                result, location, normal, index, hit_obj, matrix = scene.ray_cast(
                    context.evaluated_depsgraph_get(), origin, direction=(0, 0, 1)
                )
                # logger.debug(f"hit_obj: {hit_obj}")
                if hit_obj:
                    sec_data = hit_obj.amagate_data.get_sector_data()
                    if sec_data:
                        # 切换大气
                        idx, item = get_atmo_by_id(scene_data, sec_data.atmo_id)
                        id_key = item.name
                        if scene_data.atmo_id_key != id_key:
                            scene_data.atmo_id_key = id_key
                        # 切换外部光
                        externals = scene_data.externals
                        if len(externals) > 1:
                            idx, item = get_external_by_id(
                                scene_data, sec_data.external_id
                            )
                            if item and item.obj.hide_viewport:
                                item.obj.hide_viewport = False
                                for item_2 in externals:
                                    if item_2 != item:
                                        item_2.obj.hide_viewport = True
            #
            break
    #
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
            if scene.camera and scene.camera.name == obj.name:
                # 同步活动摄像机
                if scene_data.operator_props.camera_sync:
                    # logger.debug("camera_sync")
                    cam_pos, target_pos = ag_utils.get_camera_transform(obj)  # type: ignore
                    ag_service.set_attr_send(
                        protocol.T_ENTITY,
                        "Camera",
                        {protocol.A_POSITION: cam_pos, protocol.A_TPOS: target_pos},
                    )
    #

    # s_coll_objects_neq = False  # 扇区集合对象数量是否发生变化
    # item = scene_data.ensure_coll.get(S_COLL)
    # if item and item.obj:
    #     all_objects = len(item.obj.all_objects)
    #     if S_COLL_OBJECTS != all_objects:
    #         S_COLL_OBJECTS = all_objects
    #         s_coll_objects_neq = True

    operator_pointer = context.window_manager.operators[-1].as_pointer() if context.window_manager.operators else None  # type: ignore
    if (operator_pointer is not None) and operator_pointer != OPERATOR_POINTER:
        OPERATOR_POINTER = operator_pointer
        #
        bl_label = context.window_manager.operators[-1].bl_label
        bl_idname = context.window_manager.operators[-1].bl_idname
        # print(bl_idname)
        if bl_idname == "OBJECT_OT_editmode_toggle":
            update_scene_edit_mode()
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
        # elif bl_idname in DELETE_OP and s_coll_objects_neq:
        #     check_sector_delete()
        # 任意删除的回调
        elif bl_idname in DELETE_OP:
            check_delete()
        # 合并扇区的回调
        elif bl_idname == "OBJECT_OT_join":
            check_sector_join()
        # 分离扇区的回调
        elif bl_idname == "MESH_OT_separate":
            check_sector_separate()
        # 复制回调 # FIXME 有时候没有触发该回调，原因未知
        elif bl_idname in DUPLICATE_OP:
            check_duplicate()
        # 粘贴回调
        elif bl_idname == "VIEW3D_OT_pastebuffer":
            check_paste()
        # 变换回调
        elif bl_idname in TRANSFORM_OP:
            check_transform(bl_idname)
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
    #             # if update.is_updated_transform:
    #             #     break

    #             obj = update.id
    #             if not isinstance(obj, bpy.types.Object):
    #                 break

    #             sec_data = obj.amagate_data.get_sector_data() # type: ignore
    #             if sec_data is None:
    #                 continue

    #             if scene_data["SectorManage"]["sectors"][str(sec_data.id)]["obj"] != obj:
    #                 check_sector_duplicate(is_repeat=True)
    #                 break
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

    #
    render_view_index = next((i for i, a in enumerate(bpy.context.screen.areas) if a.type == "VIEW_3D" and a.spaces[0].shading.type == "RENDERED"), -1)  # type: ignore
    scene_data.render_view_index = render_view_index  # 记录渲染区域索引
    # 写入版本信息
    scene_data.version = data.VERSION
    scene_data.version_date = data.VERSION_DATE
    #
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
            bpy.app.timers.register(lambda: (tuple(map(lambda x: setattr(x[0], "filepath", x[1]), img_list)), None)[-1], first_interval=0.2)  # type: ignore


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


# 保存后回调
@bpy.app.handlers.persistent
def save_post(filepath=""):
    global SAVE_POST_CALLBACK
    if SAVE_POST_CALLBACK is not None:
        SAVE_POST_CALLBACK[0](*SAVE_POST_CALLBACK[1])  # type: ignore
        SAVE_POST_CALLBACK = None


# 加载后回调
@bpy.app.handlers.persistent
def load_post(filepath=""):
    from . import entity_data, L3D_data
    from . import L3D_operator as OP_L3D

    global OPERATOR_POINTER, draw_handler, LOAD_POST_CALLBACK, ASYNC_THREAD
    context = bpy.context
    scene_data = context.scene.amagate_data
    wm_data = context.window_manager.amagate_data
    #
    if len(wm_data.ent_groups) == 0:
        for i in range(32):
            prop = wm_data.ent_groups.add()
            prop.index = i
            prop.layer_name = "amagate_group"
        for i in range(32):
            prop = wm_data.ent_mutilation_groups.add()
            prop.index = i
            prop.layer_name = "amagate_mutilation_group"
    wm_data.prefab_name = entity_data.ENT_ENUM[1][1]
    if scene_data.is_blade:
        # 向后兼容
        if bpy.data.filepath:
            if not scene_data.sector_public.textures.get("Face"):
                prop = scene_data.sector_public.textures.add()
                prop.name = "Face"
                prop.target = "SectorPublic"

            ############################
            # 初始版本
            if scene_data.version_date == 0:
                OP_L3D.OT_Node_Reset.reset_node()
                scene_data.atmo_id_key = scene_data.atmospheres[0].name

            # 1.4.0之前版本
            if scene_data.version_date < 20250820:
                scene_data["EntityManage"] = {}
                # 标记集合
                name = L3D_data.M_COLL
                coll = bpy.data.collections.get(name)
                if coll:
                    item = scene_data.ensure_coll.add()
                    item.name = name
                    item.obj = coll
                L3D_data.ensure_collection(name)
                # 加载放松动画
                OP_L3D.load_rlx_anim()
                # 添加玩家实体
                location = 0, 0, 0
                obj = bpy.data.objects.get("Player")
                if obj and obj.type == "EMPTY":
                    location = obj.location
                    bpy.data.objects.remove(obj)
                OP_L3D.CreatePlayer(context)
                ent = bpy.data.objects.get("Player1")  # type: Object # type: ignore
                if ent and ent.amagate_data.is_entity:
                    ent.location = location
            #
            scene_data.version = data.VERSION
            scene_data.version_date = data.VERSION_DATE
        ############################

        # 更新插件资产路径
        models_path = Path.joinpath(Path(data.ADDON_PATH), "Models")
        scene_data.sky_tex_enum = scene_data.sky_tex_enum
        for lib in bpy.data.libraries:
            if lib.get("AG.Library"):
                filepath = Path(lib.filepath)
                filepath = models_path.joinpath(*filepath.parts[-2:])
                lib.filepath = str(filepath)
        # 为链接的动作设置伪用户
        for a in bpy.data.actions:
            if a.library:
                a.use_fake_user = True

        # 更新集合名称
        for item in scene_data.ensure_coll:
            c_name = f"{pgettext(item.name)}"
            item.obj.name = c_name
        # 恢复渲染视图
        render_view_index = scene_data.render_view_index
        if render_view_index != -1 and render_view_index < len(context.screen.areas):
            spaces = context.screen.areas[render_view_index].spaces[0]
            if hasattr(spaces, "shading"):
                spaces.shading.type = "RENDERED"
        #
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
        # 启动异步线程
        if not ASYNC_THREAD:
            ASYNC_THREAD = AsyncThread()
            ASYNC_THREAD.start()
    else:
        if draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(draw_handler, "WINDOW")
            draw_handler = None
    #
    if LOAD_POST_CALLBACK is not None:
        # print("load_post callback")
        load_post_callback = LOAD_POST_CALLBACK
        LOAD_POST_CALLBACK = None
        # 延迟初始化，以免崩溃
        bpy.app.timers.register(lambda: (load_post_callback[0](*load_post_callback[1]), None)[-1], first_interval=0.15)  # type: ignore


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
        if self.use_filter_sort_alpha:
            # 按A-Z排序
            flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(items, "item_name")
            # flt_neworder = sorted(
            #     range(len(items)), key=lambda i: items[i].item_name.lower()
            # )
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
        from . import L3D_operator as OP_L3D

        scene_data = context.scene.amagate_data
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        # row.alignment = "LEFT"
        split = row.split(factor=0.49)
        row = split.row(align=True)
        # split = row

        # col = split.column()
        # col.enabled = False
        # col.label(text=f"ID: {item.id}")
        i = (
            data.ICONS["star"].icon_id
            if item.id == scene_data.defaults.atmo_id
            else data.BLANK1
        )
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)  # icon="CHECKMARK"

        col = row.column()
        if enabled:
            col.prop(item, "item_name", text="", emboss=False)
        else:
            col.label(text=item.item_name)

        row = split.row()
        row.operator(OP_L3D.OT_Atmo_Visible.bl_idname, text="", emboss=False, icon="HIDE_OFF" if scene_data.atmo_id_key == item.name else "HIDE_ON").id = item.id  # type: ignore
        # row.enabled = enabled
        row.prop(item, "color", text="")


class AMAGATE_UI_UL_ExternalLight(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        # 按A-Z排序
        if self.use_filter_sort_alpha:
            flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(items, "item_name")
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
        from . import L3D_operator as OP_L3D

        scene_data = context.scene.amagate_data
        light = item
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        split = row.split(factor=0.49)
        row = split.row(align=True)

        i = (
            data.ICONS["star"].icon_id
            if light.id == scene_data.defaults.external_id
            else data.BLANK1
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
        row.operator(OP_L3D.OT_External_Visible.bl_idname, text="", emboss=False, icon="HIDE_ON" if item.obj.hide_viewport else "HIDE_OFF").id = item.id  # type: ignore
        row.operator(
            "amagate.scene_external_set", text="", icon="LIGHT_SUN", emboss=False
        ).id = light.id  # type: ignore

        row = split.row()
        # color = "color" if enabled else "color_readonly"
        row.prop(light, "color", text="")


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
        # 天空纹理置顶
        img_idx = items.find(img.name)
        if img_idx != -1:
            flt_neworder = (
                list(range(1, img_idx + 1)) + [0] + list(range(img_idx + 1, len(items)))
            )
        else:
            flt_neworder = []

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
        i = tex.preview.icon_id if tex.preview else data.BLANK1
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
        i = data.ICONS["star"].icon_id if tex_data.id in default_id else data.BLANK1
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
        scene = bpy.context.scene
        scene_data = scene.amagate_data
        if scene_data.atmo_id_key == self.name:
            scene_data.update_atmo_id_key(bpy.context)
        #     scene_data.atmo_color = value[:3]
        #     scene_data.atmo_density = value[-1]
        #     scene.update_tag()
        # for user in self.users_obj:
        #     obj = user.obj  # type: Object
        #     obj.amagate_data.get_sector_data().update_atmo(self)
        # data.area_redraw("VIEW_3D")


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
        get=lambda self: self.get("_color", (0.784, 0.7, 0.22)),
        set=lambda self, value: self.set_dict("_color", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    color_readonly: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        get=lambda self: self.get("_color", (0.784, 0.7, 0.22)),
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
        scene_data = bpy.context.scene.amagate_data
        name = f"AG.Sun{self.id}"
        if not self.data:
            light_data = bpy.data.lights.get(name)
            if not (light_data and light_data.type == "SUN"):
                light_data = bpy.data.lights.new("", type="SUN")
                light_data.rename(name, mode="ALWAYS")
            light_data.volume_factor = 0.0  # 体积散射
            light_data.shadow_maximum_resolution = 0.03125  # type: ignore
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
            if len(scene_data.externals) > 1:
                light.hide_viewport = True  # 不可见
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
    camera_sync: BoolProperty(name="Camera Sync", default=False, get=lambda self: self.get_camera_sync(), set=lambda self, value: self.set_camera_sync(value))  # type: ignore

    def get_camera_sync(self):
        return ag_service.P_CAMERA_SYNC

    def set_camera_sync(self, value):
        ag_service.P_CAMERA_SYNC = value
        scene = bpy.context.scene
        #
        if not value:
            # 远程调用
            script = """restore_camera()"""
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
        ag_service.exec_script_send(script)


# 场景属性扩展，该类由 data.py 注册
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
        translation_context="Map",
        items=[
            ("", "Original", ""),
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
            ("-1", "Custom", "Custom"),
            #
            ("", "Reforged", ""),
            #
            ("16", "Casa", "Casa - Reforged"),
            ("17", "Kashgar", "Kashgar - Reforged"),
            ("18", "Khazel Zalam", "Khazel Zalam - Reforged"),
            ("19", "Marakamda", "Marakamda - Reforged"),
            ("20", "Mines of Kelbegen", "Mines of Kelbegen - Reforged"),
            ("21", "Tombs of Ephyra", "Tombs of Ephyra - Reforged"),
            ("22", "Shalatuwar Fortress", "Shalatuwar Fortress - Reforged"),
            ("23", "Fortress of Nemrut", "Fortress of Nemrut - Reforged"),
            ("24", "The Oasis of Nejeb", "The Oasis of Nejeb - Reforged"),
            ("25", "Temple of Al Farum", "Temple of Al Farum - Reforged"),
            ("26", "The Temple of Ianna", "The Temple of Ianna - Reforged"),
            ("27", "Tower of Dal Gurak", "Tower of Dal Gurak - Reforged"),
            ("28", "The Abyss", "The Abyss - Reforged"),
        ],
        # default="5",  # 默认选中项
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

    # 加载关卡
    level_enum: EnumProperty(
        name="",
        description="",
        translation_context="Map",
        items=get_level_item,
        get=lambda self: 0,
        set=lambda self, value: self.set_level_enum(value),
    )  # type: ignore

    # 空间转换
    coord_conv: StringProperty(name="Blade Position", get=lambda self: self.get_coord_conv(), set=lambda self, value: self.set_coord_conv(value))  # type: ignore
    tpos_conv: StringProperty(name="Blade TPos (For Camera)", get=lambda self: self.get_tpos_conv(), set=lambda self, value: self.set_tpos_conv(value))  # type: ignore
    rot_conv: StringProperty(name="Blade Orientation", get=lambda self: self.get_rot_conv(), set=lambda self, value: self.set_rot_conv(value))  # type: ignore

    x_dir_to: StringProperty(name="Blade Direction", get=lambda self: self.get_dir_to("x_dir_to", ""), set=lambda self, value: None)  # type: ignore
    y_dir_to: StringProperty(name="Blade Direction", get=lambda self: self.get_dir_to("y_dir_to", ""), set=lambda self, value: None)  # type: ignore
    z_dir_to: StringProperty(name="Blade Direction", get=lambda self: self.get_dir_to("z_dir_to", ""), set=lambda self, value: None)  # type: ignore

    # 编辑模式标识
    is_edit_mode: BoolProperty(name="Edit Mode", default=False)  # type: ignore
    # HUD开关
    hud_enable: BoolProperty(name="HUD", default=True, get=lambda self: self.get_hud_enable(), set=lambda self, value: self.set_hud_enable(value))  # type: ignore
    # 体积雾开关
    volume_enable: BoolProperty(name="Volume Fog", default=True, update=lambda self, context: self.update_volume_enable(context))  # type: ignore

    # 灯光链接管理器
    light_link_manager: CollectionProperty(type=data.ObjectCollection)  # type: ignore

    # 世界大气
    atmo_id_key: StringProperty(update=lambda self, context: self.update_atmo_id_key(context))  # type: ignore
    atmo_color: FloatVectorProperty(name="Color", description="", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0))  # type: ignore
    atmo_density: FloatProperty(name="Density", default=0.02, min=0.0, soft_max=1.0)  # type: ignore
    # 视锥裁剪
    frustum_culling: BoolProperty(name="Frustum Culling", default=False, update=lambda self, context: self.update_frustum_culling(context))  # type: ignore
    # 显示连接面
    show_connected: BoolProperty(default=False)  # type: ignore
    show_connected_sw: BoolProperty(name="Show Connected Face", default=False, update=lambda self, context: self.update_show_connected_sw(context))  # type: ignore

    ############################

    def get_coord_conv(self):
        context = bpy.context
        selected_objects = context.selected_objects
        if selected_objects:
            location = selected_objects[0].matrix_world.translation * 1000
        # 如果没有选中物体，则返回游标位置
        else:
            location = context.scene.cursor.location * 1000
        location.yz = -location.z, location.y
        return str(location.to_tuple(1))

    def set_coord_conv(self, value):
        # key = "coord_conv"
        # self[key] = value
        value = value.strip()
        if not value:
            return
        context = bpy.context
        scene_data = context.scene.amagate_data
        try:
            position = tuple(ast.literal_eval(value))
        except:
            ag_utils.popup_menu(
                context, "Input format error", pgettext("Error"), "ERROR"
            )
            return
        # 如果元组不是3个数字，则不处理
        if len(position) != 3 or not all(isinstance(i, (int, float)) for i in position):
            ag_utils.popup_menu(
                context, "Input format error", pgettext("Error"), "ERROR"
            )
            return

        position = tuple(round(i, 1) for i in position)
        # self[key] = str(position)
        location = position[0] / 1000.0, position[2] / 1000.0, -position[1] / 1000.0

        selected_objects = context.selected_objects
        if selected_objects:
            for obj in selected_objects:
                obj.matrix_world.translation = location
        # 如果没有选中物体，则设置游标位置
        else:
            context.scene.cursor.location = location

    ############################

    def get_tpos_conv(self):
        context = bpy.context
        scene = context.scene
        cam = scene.camera
        if not cam:
            return ""

        direction = -cam.matrix_world.col[2].xyz.normalized()  # type: Vector
        location = (cam.matrix_world.translation + direction) * 1000
        location.yz = -location.z, location.y
        return str(location.to_tuple(1))

    def set_tpos_conv(self, value):
        context = bpy.context
        scene = context.scene
        cam = scene.camera
        if not cam:
            return
        value = value.strip()
        if not value:
            return
        context = bpy.context
        scene_data = context.scene.amagate_data
        try:
            position = tuple(ast.literal_eval(value))
        except:
            ag_utils.popup_menu(
                context, "Input format error", pgettext("Error"), "ERROR"
            )
            return
        # 如果元组不是3个数字，则不处理
        if len(position) != 3 or not all(isinstance(i, (int, float)) for i in position):
            ag_utils.popup_menu(
                context, "Input format error", pgettext("Error"), "ERROR"
            )
            return
        #
        position = Vector(round(i, 1) for i in position) / 1000
        position.yz = position.z, -position.y
        direction = position - cam.matrix_world.translation
        new_quat = direction.to_track_quat("-Z", "Y")
        cam.rotation_euler = new_quat.to_euler()

    ############################

    def get_rot_conv(self):
        context = bpy.context
        target_space = Matrix.Rotation(-math.pi / 2, 4, "X")
        selected_objects = context.selected_objects
        if selected_objects:
            quat = (
                target_space.inverted()
                @ selected_objects[0].matrix_world
                @ target_space
            ).to_quaternion()
            return str(tuple(round(i, 3) for i in quat))
        return ""

    def set_rot_conv(self, value):
        # key = "rot_conv"
        # self[key] = value
        value = value.strip()
        if not value:
            return
        context = bpy.context
        scene_data = context.scene.amagate_data
        try:
            quat_tuple = tuple(ast.literal_eval(value))
        except:
            ag_utils.popup_menu(
                context, "Input format error", pgettext("Error"), "ERROR"
            )
            return
        # 如果元组不是4个数字，则不处理
        if len(quat_tuple) != 4 or not all(
            isinstance(i, (int, float)) for i in quat_tuple
        ):
            ag_utils.popup_menu(
                context, "Input format error", pgettext("Error"), "ERROR"
            )
            return

        quat = Quaternion(quat_tuple).normalized()
        # self[key] = str(tuple(round(i, 3) for i in quat))

        target_space = Matrix.Rotation(-math.pi / 2, 4, "X").to_quaternion()
        quat_conv = target_space @ quat @ target_space.inverted()

        selected_objects = context.selected_objects
        if selected_objects:
            for obj in selected_objects:
                # 替换旋转分量
                loc, rot, scale = obj.matrix_world.decompose()
                obj.matrix_world = Matrix.LocRotScale(loc, quat_conv, scale)

    ############################

    def get_dir_to(self, key, default):
        context = bpy.context
        selected_objects = context.selected_objects
        if selected_objects:
            obj = selected_objects[0]
            matrix = obj.matrix_world.to_3x3()
            axis = ("x_dir_to", "y_dir_to", "z_dir_to")
            direction = matrix.col[axis.index(key)]  # type: Vector
            direction.normalize()
            direction.yz = -direction.z, direction.y
            return str(direction.to_tuple(4))
        return default

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
        return self.get("sky_tex_enum", 5)

    # def update_sky_tex_enum(self, context: Context):
    def set_sky_tex_enum(self, value):
        prop_rna = self.bl_rna.properties["sky_tex_enum"]
        enum_items_static_ui = prop_rna.enum_items_static_ui  # type: ignore
        item = enum_items_static_ui[value]
        # enum_id = item.identifier
        # if enum_id == "-1":
        #     return

        # 通过ID查找名称
        # selected_name = next(
        #     (item.description for item in enum_items if item.identifier == enum_id),
        #     None,
        # )
        selected_name = item.description
        if selected_name != "Custom":
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
    def set_level_enum(self, value):
        # prop_rna = self.bl_rna.properties["level_enum"]
        dynamic_items = get_level_item(None, None)
        item = dynamic_items[value]
        map_dir = item[2]
        if not map_dir:
            return

        # 如果选择的是当前编辑地图，检查运行时文件
        if value == 0:
            runtime_file = set()
            map_path = Path(bpy.data.filepath).parent
            for f in os.listdir(map_path):
                name = f.lower()
                if name in ("cfg.py", "pj.py"):
                    runtime_file.add(name)
                elif name.endswith(".bw"):
                    runtime_file.add(".bw")
            if runtime_file != {"cfg.py", "pj.py", ".bw"}:
                bpy.context.window_manager.popup_menu(
                    lambda self, context: self.layout.label(
                        text="Missing runtime files"
                    ),
                    title=pgettext("Warning"),
                    icon="ERROR",
                )
                return

        ag_service.exec_script_ret_send(
            f"result=load_map('{map_dir}')", self.response_load_level
        )

    def response_load_level(self, result):
        if not result:
            logger.error(
                pgettext(
                    "Map directory not found, please ensure that the map is located in the Maps folder at the root of the game directory."
                )
            )
        else:
            logger.debug("Map loaded successfully.")

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
    def update_volume_enable(self, context):
        scene = self.id_data  # type: Scene
        world = scene.world
        nodes = world.node_tree.nodes  # type: bpy.types.Nodes
        links = world.node_tree.links  # type: bpy.types.NodeLinks
        from_node = nodes["Principled Volume"]
        to_node = nodes["World Output"]

        if self.volume_enable:
            from_socket = from_node.outputs[0]
            to_socket = to_node.inputs[1]
            links.new(from_socket, to_socket)
        else:
            for link in links:
                if link.from_node == from_node and link.to_node == to_node:
                    links.remove(link)

        # for i in bpy.data.images:
        #     img_data = i.amagate_data
        #     if img_data.id > 0:
        #         mat = img_data.mat_obj  # type: bpy.types.Material
        #         if not mat:
        #             continue
        #         nodes = mat.node_tree.nodes  # type: bpy.types.Nodes
        #         links = mat.node_tree.links  # type: bpy.types.NodeLinks
        #         from_node = nodes["Add Shader - Volume"]
        #         to_node = nodes["Material Output"]

        #         if self.volume_enable:
        #             from_socket = from_node.outputs[0]
        #             to_socket = to_node.inputs[1]
        #             links.new(from_socket, to_socket)
        #         else:
        #             for link in links:
        #                 if link.from_node == from_node and link.to_node == to_node:
        #                     links.remove(link)

        # scene.update_tag()

    def get_hud_enable(self):
        context = bpy.context
        area_index = next(
            i for i, a in enumerate(context.screen.areas) if a == context.area
        )
        return True if self.areas_show_hud.get(str(area_index)) else False

    def set_hud_enable(self, value):
        context = bpy.context
        area_index = next(
            i for i, a in enumerate(context.screen.areas) if a == context.area
        )
        item_index = self.areas_show_hud.find(str(area_index))
        # print(f"item_index: {item_index}")
        if item_index != -1:
            self.areas_show_hud.remove(item_index)
        else:
            self.areas_show_hud.add().value = area_index
        data.region_redraw("WINDOW")

    ############################
    def update_atmo_id_key(self, context: Context):
        atmo = self.atmospheres[self.atmo_id_key]
        self.atmo_color = atmo.color[:3]
        self.atmo_density = atmo.color[-1]
        world = context.scene.world
        world.node_tree.nodes["Principled Volume"].inputs[2].default_value = self.atmo_density if self.atmo_color.v == 0 else 0  # type: ignore
        # data.area_redraw("VIEW_3D")

    def update_frustum_culling(self, context: Context):
        if not self.frustum_culling:
            for k in self["SectorManage"]["sectors"]:
                sec = self["SectorManage"]["sectors"][k]["obj"]
                sec.hide_viewport = False

    def update_show_connected_sw(self, context: Context):
        update_scene_edit_mode()

    ############################
    def init(self):
        self["SectorManage"] = {"deleted_id_count": 0, "max_id": 0, "sectors": {}}
        self["EntityManage"] = {}
        defaults = self.defaults

        defaults.target = "Scene"
        defaults.atmo_id = 1
        defaults.external_id = 1
        defaults.ambient_color = (0.42, 0.42, 0.42)

        defaults.flat_light.target = "Scene"
        defaults.flat_light["color"] = (0.784, 0.784, 0.784)
        self.sector_public.target = "SectorPublic"
        self.sector_public.flat_light.target = "SectorPublic"
        ############################
        tex_ids = (1, 2 if get_texture_by_id(2)[0] != -1 else 1)
        for i in ("Floor", "Ceiling", "Wall"):
            prop = defaults.textures.add()
            prop.target = "Scene"
            prop.name = i
            tex_id = tex_ids[1] if i == "Wall" else tex_ids[0]
            prop.id = tex_id
            prop.xpos = prop.ypos = 0.0
            prop.xzoom = prop.yzoom = 20.0
            if i == "Wall":
                prop.angle = -math.pi * 0.5
            else:
                prop.angle = 0.0

            prop = self.sector_public.textures.add()
            prop.name = i
            prop.target = "SectorPublic"
        #
        prop = self.sector_public.textures.add()
        prop.name = "Face"
        prop.target = "SectorPublic"

        # 添加32个组
        for i in range(32):
            prop = self.sector_public.group_set.add()
            prop.index = i


############################


def register_timer():
    load_post(None)


############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type)
    and any(issubclass(cls, parent) for parent in class_tuple)
    and cls != SceneProperty
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # 注册回调函数
    bpy.app.handlers.save_post.append(save_post)
    bpy.app.handlers.load_post.append(load_post)  # type: ignore
    bpy.app.timers.register(register_timer, first_interval=0.5)  # type: ignore


def unregister():
    global draw_handler

    # 关闭线程
    if ASYNC_THREAD:
        run_coroutine_threadsafe(ASYNC_THREAD.stop(), ASYNC_THREAD.loop)
        ASYNC_THREAD.join()
    #
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # 注销回调函数
    if save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(save_post)  # type: ignore
    if load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post)  # type: ignore
    if check_before_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(check_before_save)  # type: ignore
    if depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)  # type: ignore
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, "WINDOW")
        draw_handler = None
