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
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

# from collections import Counter
#
import bpy

# import bmesh
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
from .scripts import ag_utils

#

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene

############################ 全局变量
Copyright = "(C) 2024-2025 Sryml"

ADDON_PATH = os.path.dirname(__file__)

with open(os.path.join(ADDON_PATH, "version"), "r") as v:
    VERSION = v.read().strip()

DEBUG = os.path.exists(os.path.join(ADDON_PATH, "DEBUG"))

ICONS: Any = None

AG_COLL = "Amagate Auto Generated"
S_COLL = "Sector Collection"
GS_COLL = "Ghost Sector Collection"
E_COLL = "Entity Collection"
C_COLL = "Camera Collection"

DEPSGRAPH_UPDATE_LOCK = threading.Lock()
# DELETE_POST_LOCK = threading.Lock()

WM_OPERATORS = 0
draw_handler = None

SELECTED_SECTORS: list[Object] = []
ACTIVE_SECTOR: Object = None  # type: ignore

FACE_FLAG = {"Floor": -1, "Ceiling": -2, "Wall": -3}

############################


def region_redraw(target):
    for region in bpy.context.area.regions:
        if region.type == target:
            region.tag_redraw()  # 刷新该区域


def area_redraw(target):
    for area in bpy.context.screen.areas:
        if area.type == target:
            area.tag_redraw()


# XXX 弃用的
# def get_scene_suffix(scene: bpy.types.Scene = None) -> str:  # type: ignore
#     if not scene:
#         scene = bpy.context.scene
#     scene_data = scene.amagate_data  # type: ignore
#     suffix = ""
#     if scene_data.id != 1:
#         suffix = f" (BS{scene_data.id})"
#     return suffix


#
def get_id(used_ids, start_id=1) -> int:
    id_ = start_id
    while id_ in used_ids:
        id_ += 1
    return id_


def get_name(used_names, f, id_) -> str:
    name = f.format(id_)
    while name in used_names:
        id_ += 1
        name = f.format(id_)
    return name


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


# 确保NULL纹理存在
def ensure_null_texture() -> Image:
    scene_data = bpy.context.scene.amagate_data
    img = scene_data.ensure_null_tex  # type: Image
    if not img:
        img = bpy.data.images.new("NULL", width=256, height=256)  # type: ignore
        img.amagate_data.id = -1  # type: ignore
        scene_data.ensure_null_tex = img
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
        null_obj.use_fake_user = True
        scene_data.ensure_null_obj = null_obj
    return null_obj


# 确保切割摄像机
def ensure_render_camera() -> Object:
    scene_data = bpy.context.scene.amagate_data
    render_cam = scene_data.render_cam  # type: Object
    if not render_cam:
        cam_data = bpy.data.cameras.new("AG.RenderCamera")
        render_cam = bpy.data.objects.new("AG.RenderCamera", cam_data)  # type: ignore
        cam_data.sensor_width = 100
        cam_data.passepartout_alpha = 0.9
        # cam_data.show_limits = True
        render_cam.rotation_euler = (math.pi / 2, 0, 0)
        # 正交摄像机
        # render_cam.data.type = "ORTHO"
        link2coll(render_cam, ensure_collection(C_COLL))
        bpy.context.scene.camera = render_cam
        scene_data.render_cam = render_cam
    return render_cam


# 确保集合
def ensure_collection(name, hide_select=False) -> bpy.types.Collection:
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
    return item.obj


# 确保材质
def ensure_material(tex: Image) -> bpy.types.Material:
    tex_data = tex.amagate_data
    name = f"AG.Mat{tex_data.id}"
    mat = tex_data.mat_obj
    if not mat:
        mat = bpy.data.materials.new("")
        mat.rename(name, mode="ALWAYS")
        filepath = os.path.join(ADDON_PATH, "nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))
        import_nodes(mat, nodes_data["AG.Mat1"])
        mat.use_fake_user = True
        mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
        mat.use_backface_culling = True
        tex_data.mat_obj = mat

    return mat


# 确保节点
def ensure_node():
    filepath = os.path.join(ADDON_PATH, "nodes.dat")
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

    import_nodes(NodeTree, nodes_data["Amagate Eval"])
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


def link2coll(obj, coll):
    if coll.objects.get(obj.name) is None:
        coll.objects.link(obj)


############################
############################ 节点导入导出
############################


def to_primitive(obj):
    """将对象转化为基本类型"""
    if obj is None:
        return None

    if isinstance(obj, (int, float, str, bool)):
        return obj
    if hasattr(obj, "type") and obj.type == "FRAME":
        return obj.name

    try:
        return tuple(obj)
    except TypeError:
        return None


def serialize_node(node: bpy.types.Node, temp_node):
    """序列化节点为字典"""
    node_data = {
        "type": node.bl_idname,
        "name": node.name,
        # "location": tuple(node.location),  # type: ignore
        "properties": {},
    }
    for prop in node.bl_rna.properties:
        identifier = prop.identifier
        if (
            not prop.is_readonly
            and not identifier.startswith("bl_")
            and identifier not in ("name", "select", "location")
        ):
            value = to_primitive(getattr(node, identifier))
            if value is not None:
                if value != to_primitive(
                    getattr(temp_node, identifier)
                ):  # 只存储非默认值
                    node_data["properties"][identifier] = value
                elif identifier in (
                    "input_type",
                    "data_type",
                    "mode",
                    "operation",
                    "domain",
                ):
                    node_data["properties"][identifier] = value
    # 处理输入
    inputs_data = []
    for i, input_socket in enumerate(node.inputs):
        if not input_socket.is_linked:
            if not hasattr(input_socket, "default_value") or not hasattr(
                temp_node.inputs[i], "default_value"
            ):
                continue
            value = to_primitive(input_socket.default_value)  # type: ignore
            if value is not None:
                if value != to_primitive(
                    temp_node.inputs[i].default_value
                ):  # 只存储非默认值
                    inputs_data.append(
                        {"idx": i, "value": value}  # "name": input_socket.name
                    )

    node_data["inputs"] = inputs_data

    parent_node = node.parent
    node.parent = None
    node_data["location"] = tuple(node.location)  # type: ignore
    node.parent = parent_node

    return node_data


def deserialize_node(nodes, node_data):
    """根据字典数据重建节点"""
    node = nodes.new(type=node_data["type"])
    node.select = False
    node.name = node_data["name"]
    # node.location = tuple(node_data["location"])
    for prop, value in node_data["properties"].items():
        if prop != "parent":
            setattr(node, prop, value)

    for input_data in node_data.get("inputs", []):
        input_socket = node.inputs[input_data["idx"]]
        input_socket.default_value = input_data["value"]

    node.location = node_data["location"]

    return node


def get_socket_index(coll, target_socket):
    for i, socket in enumerate(coll):
        if socket == target_socket:
            return i
    return None


def export_nodes(target):
    if hasattr(target, "node_tree"):
        nodes = target.node_tree.nodes  # type: bpy.types.Nodes
        links = target.node_tree.links  # type: bpy.types.NodeLinks
    else:
        nodes = target.nodes  # type: bpy.types.Nodes
        links = target.links  # type: bpy.types.NodeLinks

    temp_nodes = {}

    # 存储节点和连接的字典
    nodes_data = {"nodes": [], "links": []}
    for node in list(nodes):
        temp_node_data = {"bl_idname": node.bl_idname}
        dynamic_props = ("input_type", "data_type", "mode", "operation", "domain")
        for prop in dynamic_props:
            temp_node_data[prop] = getattr(node, prop) if hasattr(node, prop) else ""

        k = ".".join(temp_node_data.values())
        temp_node = temp_nodes.get(k)
        if not temp_node:
            temp_node = temp_nodes.setdefault(k, nodes.new(type=node.bl_idname))
            for prop in dynamic_props:
                if hasattr(temp_node, prop):
                    setattr(temp_node, prop, temp_node_data[prop])

        node_data = serialize_node(node, temp_node)
        nodes_data["nodes"].append(node_data)

    for node in temp_nodes.values():
        nodes.remove(node)

    # 遍历连接
    for link in links:
        from_socket = get_socket_index(link.from_node.outputs, link.from_socket)
        to_socket = get_socket_index(link.to_node.inputs, link.to_socket)
        link_data = {
            "from_node": link.from_node.name,
            "from_socket": from_socket,
            "to_node": link.to_node.name,
            "to_socket": to_socket,
        }
        nodes_data["links"].append(link_data)

    print("导出成功")
    return nodes_data


def import_nodes(target, nodes_data):
    if hasattr(target, "node_tree"):
        target.use_nodes = True
        nodes = target.node_tree.nodes  # type: bpy.types.Nodes
        links = target.node_tree.links  # type: bpy.types.NodeLinks
    else:
        nodes = target.nodes  # type: bpy.types.Nodes
        links = target.links  # type: bpy.types.NodeLinks

    # 清空默认节点
    nodes.clear()

    node_map = {}
    for node_data in nodes_data["nodes"]:
        node = deserialize_node(nodes, node_data)
        node_map[node.name] = node

    for link_data in nodes_data["links"]:
        from_node = node_map[link_data["from_node"]]
        to_node = node_map[link_data["to_node"]]
        from_socket = from_node.outputs[link_data["from_socket"]]
        to_socket = to_node.inputs[link_data["to_socket"]]
        links.new(from_socket, to_socket)

    for node_data in nodes_data["nodes"]:
        parent_name = node_data["properties"].get("parent")
        if parent_name:
            node_map[node_data["name"]].parent = node_map[parent_name]

    # print("导入成功")


############################
############################ 偏好设置
############################

addon_keymaps = []


class AmagatePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__  # type: ignore

    # 用于保存面板的展开状态
    fold_state: BoolProperty(name="Fold State", default=True)  # type: ignore
    is_user_modified: BoolProperty(default=False)  # type: ignore

    def __init__(self):
        super().__init__()
        # self.fold_state = False

    def draw(self, context: Context):
        self.is_user_modified = False
        layout = self.layout
        wm = context.window_manager
        kc = wm.keyconfigs.user
        km = kc.keymaps["3D View"]
        keymap_items = [
            kmi for kmi in km.keymap_items if kmi.idname.startswith("amagate.")
        ]
        if len(keymap_items) < 1:
            self.is_user_modified = True
        else:
            for kmi in keymap_items:
                if kmi.is_user_modified:
                    self.is_user_modified = True

        row = layout.row()
        col = row.column()
        col.alignment = "LEFT"
        col.prop(
            self,
            "fold_state",
            text="",
            icon="TRIA_DOWN" if self.fold_state else "TRIA_RIGHT",
            emboss=False,
        )
        row.label(text="Keymap")
        # if self.is_user_modified:
        #     col = row.column()
        #     col.alignment = "RIGHT"
        #     col.operator("preferences.keymap_restore", text="Restore")

        if self.fold_state and keymap_items:
            box = layout.box()
            split = box.split()
            col = split.column()
            for kmi in keymap_items:
                col.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)


def register_shortcuts():
    global addon_keymaps
    # preferences = bpy.context.preferences.addons[__package__].preferences  # type: ignore

    wm = bpy.context.window_manager  # type: ignore
    kc = wm.keyconfigs.addon

    if kc:
        # shortcut_key = preferences.shortcut_key

        km = kc.keymaps.get("3D View")
        if km is None:
            km = kc.keymaps.new(
                name="3D View", space_type="VIEW_3D", region_type="WINDOW"
            )
        kmi = km.keymap_items.new(
            idname="amagate.sector_convert",
            type="ONE",
            value="PRESS",
            ctrl=True,
            alt=True,
        )
        # kmi.properties.name = "test"
        kmi.active = True
        addon_keymaps.append((km, kmi))


def unregister_shortcuts():
    global addon_keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


############################
############################ 回调函数
############################


def delete_post_func():
    scene_data = bpy.context.scene.amagate_data

    # XXX 不起作用，因为复制场景不会触发依赖图更新
    # 如果用户复制了场景(存在2个blade场景)，则撤销操作
    # if len([1 for i in bpy.data.scenes if i.amagate_data.is_blade]) > 1:  # type: ignore
    #     print("撤销操作")
    #     bpy.ops.ed.undo()
    #     return

    # 如果用户删除了特殊对象，则撤销操作
    for i in [
        scene_data.ensure_null_obj,
        scene_data.ensure_null_tex,
        scene_data.sec_node,
        scene_data.eval_node,
    ] + [item.obj for item in scene_data.ensure_coll]:
        if not i:
            bpy.ops.ed.undo()
            return

    # 如果用户删除了扇区物体，则进行自动清理
    coll = ensure_collection(S_COLL)
    SectorManage = scene_data.get("SectorManage")
    if len(SectorManage["sectors"]) != len(coll.all_objects):
        exist_ids = set(str(obj.amagate_data.get_sector_data().id) for obj in coll.all_objects if obj.amagate_data.is_sector)  # type: ignore
        all_ids = set(SectorManage["sectors"].keys())
        deleted_ids = sorted(all_ids - exist_ids, reverse=True)

        if deleted_ids:
            # 如果只是移动到其它集合，则撤销操作
            obj = SectorManage["sectors"][deleted_ids[0]]["obj"]
            if obj and bpy.context.scene in obj.users_scene:
                bpy.ops.ed.undo()
                return

            bpy.ops.ed.undo()
            scene_data = bpy.context.scene.amagate_data
            coll = ensure_collection(S_COLL)
            SectorManage = scene_data["SectorManage"]

            for id_key in deleted_ids:
                obj = SectorManage["sectors"][id_key]["obj"]
                if obj.data.users == 1:
                    bpy.data.meshes.remove(obj.data)
                else:
                    bpy.data.objects.remove(obj)
                for l in SectorManage["sectors"][id_key]["light_objs"]:
                    l.hide_viewport = True
                atmo = get_atmo_by_id(
                    scene_data, SectorManage["sectors"][id_key]["atmo_id"]
                )[1]
                if atmo:
                    atmo.users_obj.remove(atmo.users_obj.find(id_key))
                external = get_external_by_id(
                    scene_data, SectorManage["sectors"][id_key]["external_id"]
                )[1]
                if external:
                    external.users_obj.remove(external.users_obj.find(id_key))

                if int(id_key) != SectorManage["max_id"]:
                    SectorManage["deleted_id_count"] += 1
                else:
                    SectorManage["max_id"] -= 1
                SectorManage["sectors"].pop(id_key)

            bpy.ops.ed.undo_push(message="Delete Sector")


def geometry_modify_post(selected_sectors: list[Object] = []):
    if not selected_sectors:
        selected_sectors = ag_utils.get_selected_sectors()[0]
    for sec in selected_sectors:
        sec.amagate_data.get_sector_data().is_convex = ag_utils.is_convex(sec)
    # 凸面检查
    bpy.ops.ed.undo_push(message="Convex Check")


# def delete_post_func_release():
#     DELETE_POST_LOCK.release()


# @bpy.app.handlers.persistent
def depsgraph_update_post(scene: Scene, depsgraph: bpy.types.Depsgraph):
    global WM_OPERATORS
    scene_data = scene.amagate_data
    if not scene_data.is_blade:
        return

    # XXX 待优化。目前没有获取撤销堆栈的Python API，因此在模态模式也会执行回调
    if not DEPSGRAPH_UPDATE_LOCK.acquire(blocking=False):
        return

    # 删除操作后的回调
    delete_post_func()
    # if DELETE_POST_LOCK.acquire(blocking=False):
    # delete_post_func()
    # DELETE_POST_LOCK.release()
    # bpy.app.timers.register(delete_post_func_release, first_interval=0.2)

    # 从编辑模式切换到物体模式的回调
    wm_operators = len(bpy.context.window_manager.operators)
    if wm_operators != WM_OPERATORS:
        WM_OPERATORS = wm_operators
        if WM_OPERATORS != 0:
            bl_idname = bpy.context.window_manager.operators[-1].bl_idname
            # print(bl_idname)
            if bl_idname == "OBJECT_OT_editmode_toggle":
                if bpy.context.mode == "OBJECT":
                    geometry_modify_post()
            elif bl_idname == "OBJECT_OT_modifier_apply":
                geometry_modify_post()

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

    if not scene_data.builtin_tex_saved:
        scene_data.builtin_tex_saved = True
        img = None  # type: Image # type: ignore
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
                img.filepath = (
                    f"//{os.path.relpath(new_path, os.path.dirname(filepath))}"
                )


def draw_callback_3d():
    context = bpy.context
    scene_data = context.scene.amagate_data
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
    selected_sectors = ag_utils.get_selected_sectors()[0]
    sector_num = len(selected_sectors)

    #
    is_convex = pgettext("None")
    color = ag_utils.DefColor.nofocus
    if selected_sectors:
        color = ag_utils.DefColor.red
        is_convex = selected_sectors[0].amagate_data.get_sector_data().is_convex
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.is_convex != is_convex:
                is_convex = "*"
                break
        if is_convex == 1:
            is_convex = pgettext("Yes", "Property")
            color = ag_utils.DefColor.white
        elif is_convex == 0:
            is_convex = pgettext("No", "Property")
    texts.append((f"{pgettext('Convex Polyhedron')}: {is_convex}", color))
    #
    text = (
        f"{pgettext('Selected Sector')}: {sector_num} / {len(context.selected_objects)}"
    )
    if sector_num == 0:
        color = ag_utils.DefColor.nofocus
    else:
        color = ag_utils.DefColor.white
    texts.append((text, color))
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
    global WM_OPERATORS, draw_handler
    scene_data = bpy.context.scene.amagate_data
    if scene_data.is_blade:
        if scene_data.render_view_index != -1:
            spaces = bpy.context.screen.areas[scene_data.render_view_index].spaces[0]
            if hasattr(spaces, "shading"):
                spaces.shading.type = "RENDERED"
        bpy.app.handlers.save_pre.append(check_before_save)  # type: ignore
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)  # type: ignore
        if draw_handler is None:
            draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_3d, (), "WINDOW", "POST_PIXEL"
            )
        WM_OPERATORS = len(bpy.context.window_manager.operators)
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
        # 按A-Z排序 FIXME 没有按照预期排序，不知道为什么
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
        data,
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
        i = ICONS["star"].icon_id if item.id == scene_data.defaults.atmo_id else 1
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
        data,
        item,
        icon,
        active_data,
        active_prop,
    ):
        scene_data = context.scene.amagate_data
        light = item
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        split = row.split(factor=0.6)
        row = split.row()

        i = ICONS["star"].icon_id if light.id == scene_data.defaults.external_id else 1
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)

        col = row.column()
        if enabled:
            col.prop(light, "item_name", text="", emboss=False)
        else:
            col.label(text=light.item_name)

        if enabled:
            split = split.split(factor=0.5)
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
        items = getattr(data, propname)
        if self.use_filter_invert:
            invisible = self.bitflag_filter_item
        else:
            invisible = 0
        flt_flags = [self.bitflag_filter_item] * len(items)
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
                flt_flags[idx] = 0

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context: Context,
        layout: bpy.types.UILayout,
        data,
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
        i = ICONS["star"].icon_id if tex_data.id in default_id else 1
        col.label(text="", icon_value=i)

        col = row.column()
        col.alignment = "RIGHT"
        i = "UGLYPACKAGE" if tex.packed_file else "BLANK1"
        col.label(text="", icon=i)


############################
############################ Collection Props
############################


class IntegerCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    value: IntProperty(default=0, update=lambda self, context: self.update_value(context))  # type: ignore

    def update_value(self, context):
        self.name = str(self.value)


class StringCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore


class SectorCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    obj: PointerProperty(type=bpy.types.Object, update=lambda self, context: self.update_obj(context))  # type: ignore

    def update_obj(self, context):
        if self.obj:
            self.name = str(self.obj.amagate_data.get_sector_data().id)


class CollCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    obj: PointerProperty(type=bpy.types.Collection)  # type: ignore


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
                sector_data = sec.amagate_data.get_sector_data()  # type: ignore
                sector_data.atmo_id = scene_data.atmospheres[value].id
        elif self.target == "Scene":
            scene_data.defaults.atmo_id = scene_data.atmospheres[value].id
        # region_redraw("UI")
        area_redraw("VIEW_3D")

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
                sector_data = sec.amagate_data.get_sector_data()  # type: ignore
                sector_data.external_id = scene_data.externals[value].id
        elif self.target == "Scene":
            scene_data.defaults.external_id = scene_data.externals[value].id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select External Light")


# 选择纹理
class Texture_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="")  # type: ignore
    name: StringProperty(default="")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
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

        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select Texture")


############################
############################ Object Props
############################


# 大气属性
class AtmosphereProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0, get=lambda self: int(self["name"]))  # type: ignore
    name: StringProperty(name="id key", default="0")  # type: ignore
    item_name: StringProperty(name="Atmosphere Name", default="", get=lambda self: self.get_item_name(), set=lambda self, value: self.set_item_name(value))  # type: ignore
    users_obj: CollectionProperty(type=SectorCollection)  # type: ignore
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
        area_redraw("VIEW_3D")


# 纹理属性
class TextureProperty(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    target: StringProperty(default="")  # type: ignore

    id: IntProperty(name="ID", default=0, get=lambda self: self.get_id(), set=lambda self, value: self.set_id(value))  # type: ignore

    pos: FloatVectorProperty(subtype="XYZ", size=2, get=lambda self: (self.xpos, self.ypos))  # type: ignore
    xpos: FloatProperty(description="X Position", step=10, default=0.0, get=lambda self: self.get_pos(0), set=lambda self, value: self.set_pos(value, 0))  # type: ignore
    ypos: FloatProperty(description="Y Position", step=10, default=0.0, get=lambda self: self.get_pos(1), set=lambda self, value: self.set_pos(value, 1))  # type: ignore

    zoom: FloatVectorProperty(subtype="XYZ", size=2, get=lambda self: (self.xzoom, self.yzoom))  # type: ignore
    xzoom: FloatProperty(description="X Zoom", step=10, default=0.0, get=lambda self: self.get_zoom(0), set=lambda self, value: self.set_zoom(value, 0))  # type: ignore
    yzoom: FloatProperty(description="Y Zoom", step=10, default=0.0, get=lambda self: self.get_zoom(1), set=lambda self, value: self.set_zoom(value, 1))  # type: ignore
    zoom_constraint: BoolProperty(
        name="Constraint",
        # description="Zoom Constraint",
        default=True,
    )  # type: ignore

    angle: FloatProperty(name="Angle", unit="ROTATION", subtype="ANGLE", default=0.0, step=10, precision=5, get=lambda self: self.get_angle(), set=lambda self, value: self.set_angle(value))  # type: ignore
    ############################

    def get_id(self):
        return self.get("id", 0)

    def set_id(self, value):
        if self.target == "SectorPublic":
            # 单独修改面的情况
            if ACTIVE_SECTOR.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
                tex = get_texture_by_id(value)[1]
                mat = ensure_material(tex)
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                    faces = []
                    update = False
                    for i, face in enumerate(mesh.polygons):
                        if face.select:
                            face_attr = mesh.attributes["amagate_tex_id"].data[i]  # type: ignore
                            if face_attr.value != value:
                                face_attr.value = value
                                update = True
                                faces.append(i)
                    if faces:
                        sec_data.set_matslot(mat, faces)
                    # if update:
                    #     sec.update_tag()
                bpy.ops.object.mode_set(mode="EDIT")
            # 修改预设纹理的情况
            else:
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_id(value)
        else:
            if value == self.id:
                return

            self["id"] = value

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            sec_data = sec.amagate_data.get_sector_data()
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            tex = get_texture_by_id(value)[1]

            faces = []
            face_flag = FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes["amagate_tex_id"].data[i]  # type: ignore
                    if face_attr.value != value:
                        face_attr.value = value
                        update = True
                        faces.append(i)
            if faces:
                sec_data.set_matslot(ensure_material(tex), faces)
            # if update:
            #     sec.update_tag()

    ############################
    def get_pos(self, index=0):
        attr = ("xpos", "ypos")[index]
        if self.target == "SectorPublic":
            sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
            if ACTIVE_SECTOR.mode == "OBJECT":
                return getattr(sec_data.textures[self.name], attr)
            elif ACTIVE_SECTOR.mode == "EDIT":
                ret = 0.0
                bpy.ops.object.mode_set(mode="OBJECT")
                mesh = ACTIVE_SECTOR.data  # type: bpy.types.Mesh # type: ignore
                for i, face in enumerate(mesh.polygons):
                    if face.select:
                        ret = mesh.attributes["amagate_tex_pos"].data[i].vector[index]  # type: ignore
                        break
                bpy.ops.object.mode_set(mode="EDIT")
                return ret
        else:
            return self.get(attr, -1.0)

    def set_pos(self, value, index=0):
        attr = ("xpos", "ypos")[index]

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if ACTIVE_SECTOR.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
                for sec in SELECTED_SECTORS:
                    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                    update = False
                    for i, face in enumerate(mesh.polygons):
                        if face.select:
                            face_attr = mesh.attributes["amagate_tex_pos"].data[i]  # type: ignore
                            if face_attr.vector[index] != value:
                                face_attr.vector[index] = value
                                update = True
                    # if update:
                    #     sec.update_tag()
                bpy.ops.object.mode_set(mode="EDIT")
            # 修改预设纹理的情况
            else:
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_pos(value, index)
        else:
            self[attr] = value

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            face_flag = FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes["amagate_tex_pos"].data[i]  # type: ignore
                    if face_attr.vector[index] != value:
                        face_attr.vector[index] = value
                        update = True
            # if update:
            #     sec.update_tag()

    ############################
    def get_zoom(self, index):
        attr = ("xzoom", "yzoom")[index]
        if self.target == "SectorPublic":
            sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
            if ACTIVE_SECTOR.mode == "OBJECT":
                return getattr(sec_data.textures[self.name], attr)
            elif ACTIVE_SECTOR.mode == "EDIT":
                ret = 0.0
                bpy.ops.object.mode_set(mode="OBJECT")
                mesh = ACTIVE_SECTOR.data  # type: bpy.types.Mesh # type: ignore
                for i, face in enumerate(mesh.polygons):
                    if face.select:
                        ret = mesh.attributes["amagate_tex_scale"].data[i].vector[index]  # type: ignore
                        break
                bpy.ops.object.mode_set(mode="EDIT")
                return ret
        else:
            return self.get(attr, -1.0)

    def set_zoom(self, value, index, constraint=None):
        attr = ("xzoom", "yzoom")[index]
        attr2 = ("xzoom", "yzoom")[1 - index]
        value2 = None
        if (constraint is None and self.zoom_constraint) or (
            constraint is not None and constraint
        ):
            old_value = getattr(self, attr)
            if old_value == 0:
                value2 = value
            else:
                factor = value / old_value
                value2 = getattr(self, attr2) * factor

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if ACTIVE_SECTOR.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
                for sec in SELECTED_SECTORS:
                    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                    update = False
                    for i, face in enumerate(mesh.polygons):
                        if face.select:
                            face_attr = mesh.attributes["amagate_tex_scale"].data[i]  # type: ignore
                            if face_attr.vector[index] != value:
                                face_attr.vector[index] = value
                                update = True
                    # if update:
                    #     sec.update_tag()
                bpy.ops.object.mode_set(mode="EDIT")
            # 修改预设纹理的情况
            else:
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_zoom(
                        value, index, constraint=self.zoom_constraint
                    )
        else:
            self[attr] = value
            if value2 is not None:
                self[attr2] = value2

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            face_flag = FACE_FLAG[self.name]
            update = False
            vector = self.zoom
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes["amagate_tex_scale"].data[i]  # type: ignore
                    if face_attr.vector != vector:
                        face_attr.vector = vector
                        update = True
            # if update:
            #     sec.update_tag()

    ############################
    def get_angle(self):
        attr = "angle"
        if self.target == "SectorPublic":
            sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
            if ACTIVE_SECTOR.mode == "OBJECT":
                return getattr(sec_data.textures[self.name], attr)
            elif ACTIVE_SECTOR.mode == "EDIT":
                ret = 0.0
                bpy.ops.object.mode_set(mode="OBJECT")
                mesh = ACTIVE_SECTOR.data  # type: bpy.types.Mesh # type: ignore
                for i, face in enumerate(mesh.polygons):
                    if face.select:
                        ret = mesh.attributes["amagate_tex_rotate"].data[i].value  # type: ignore
                        break
                bpy.ops.object.mode_set(mode="EDIT")
                return ret
        else:
            return self.get(attr, -1.0)

    def set_angle(self, value):
        attr = "angle"

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if ACTIVE_SECTOR.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
                for sec in SELECTED_SECTORS:
                    mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                    update = False
                    for i, face in enumerate(mesh.polygons):
                        if face.select:
                            face_attr = mesh.attributes["amagate_tex_rotate"].data[i]  # type: ignore
                            if face_attr.value != value:
                                face_attr.value = value
                                update = True
                    # if update:
                    #     sec.update_tag()
                bpy.ops.object.mode_set(mode="EDIT")
            # 修改预设纹理的情况
            else:
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_angle(value)
        else:
            self[attr] = value

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            face_flag = FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes["amagate_tex_rotate"].data[i]  # type: ignore
                    if face_attr.value != value:
                        face_attr.value = value
                        update = True
            # if update:
            #     sec.update_tag()


# 外部光属性
class ExternalLightProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0, get=lambda self: int(self["name"]))  # type: ignore
    name: StringProperty(name="id key", default="0")  # type: ignore
    item_name: StringProperty(name="Light Name", default="", get=lambda self: self.get_item_name(), set=lambda self, value: self.set_item_name(value))  # type: ignore
    obj: PointerProperty(type=bpy.types.Light)  # type: ignore
    users_obj: CollectionProperty(type=SectorCollection)  # type: ignore

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
        get=lambda self: self.get("_color", (0.784, 0.784, 0.784)),
        set=lambda self, value: self.set_dict("_color", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    color_readonly: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        get=lambda self: self.get("_color", (0.784, 0.784, 0.784)),
        set=lambda self, value: None,
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Direction",
        subtype="XYZ",
        default=(0.0, 0.0, -1.0),  # 默认向量值
        size=3,  # 必须是 3 维向量
        min=-1.0,
        max=1.0,
        get=lambda self: self.get("_vector", (0.0, 0.0, -1.0)),
        set=lambda self, value: self.set_dict("_vector", value),
        update=lambda self, context: self.update_obj(context),
    )  # type: ignore
    vector2: FloatVectorProperty(
        name="Direction",
        subtype="DIRECTION",
        default=(0.0, 0.0, -1.0),  # 默认向量值
        size=3,  # 必须是 3 维向量
        min=-1.0,
        max=1.0,
        get=lambda self: self.get("_vector", (0.0, 0.0, -1.0)),
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
        if not self.obj:
            name = f"AG.Sun{self.id}"
            light_data = bpy.data.lights.get(name)
            if not (light_data and light_data.type == "SUN"):
                light_data = bpy.data.lights.new("", type="SUN")
                light_data.volume_factor = 0.0
                light_data.rename(name, mode="ALWAYS")
            self.obj = light_data

        return self.obj

    def sync_users(self, rotation_euler):
        for i in self.users_obj:
            sec = i.obj  # type: Object
            sec.amagate_data.get_sector_data().update_external(self, rotation_euler)

    def update_obj(self, context=None):
        self.ensure_obj()
        self.obj.color = self.color  # 设置颜色
        rotation_euler = self.vector.to_track_quat("-Z", "Z").to_euler()
        self.sync_users(rotation_euler)
        # light_data.energy = self.energy  # 设置能量


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


# 平面光属性
class FlatLightProperty(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Direction",
        subtype="XYZ",
        default=(0.0, 0.0, 0.0),
        size=3,
        min=-1.0,
        max=1.0,
    )  # type: ignore


class SectorFocoLightProperty(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="")  # type: ignore
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0, 0, 0),  # 0.784, 0.784, 0.392
    )  # type: ignore
    pos: FloatVectorProperty(
        name="Position",
        subtype="XYZ",
        default=(0.0, 0.0, 0.0),
        size=3,
    )  # type: ignore
    strength: FloatProperty(
        name="Strength",
        description="Strength of the light",  # 光照强度
        default=1.0,
    )  # type: ignore
    precision: FloatProperty(
        name="Precision",
        description="Precision of the light",  # 精度
        default=0.03125,
    )  # type: ignore
    # TODO


# 操作属性
class OperatorProperty(bpy.types.PropertyGroup):
    # OT_Sector_Connect
    sec_connect_sep_convex: BoolProperty(name="Auto Separate Convex", default=True)  # type: ignore


# 扇区属性
class SectorProperty(bpy.types.PropertyGroup):
    target: StringProperty(name="Target", default="Sector")  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore
    has_sky: BoolProperty(default=False)  # type: ignore
    is_convex: BoolProperty(default=False)  # type: ignore
    # 大气
    atmo_id: IntProperty(name="Atmosphere", description="", default=0, get=lambda self: self.get_atmo_id(), set=lambda self, value: self.set_atmo_id(value))  # type: ignore
    atmo_color: FloatVectorProperty(name="Color", description="", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0))  # type: ignore
    atmo_density: FloatProperty(name="Density", description="", default=0.02, min=0.0, soft_max=1.0)  # type: ignore
    # 纹理
    textures: CollectionProperty(type=TextureProperty)  # type: ignore
    # 外部光
    # 环境光
    ambient_color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0, 0, 0),
        get=lambda self: self.get_ambient_color(),
        set=lambda self, value: self.set_ambient_color(value),
    )  # type: ignore
    # 外部光
    external_id: IntProperty(name="External Light", description="", default=0, get=lambda self: self.get_external_id(), set=lambda self, value: self.set_external_id(value))  # type: ignore
    external_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    flat_light: PointerProperty(type=FlatLightProperty)  # type: ignore # 平面光

    spot_light: CollectionProperty(type=SectorFocoLightProperty)  # type: ignore # 聚光灯

    group: IntProperty(
        name="Group",
        description="",
        default=0,  # 默认值为0
    )  # type: ignore
    comment: StringProperty(name="Comment", description="", default="")  # type: ignore

    ############################
    def update_atmo(self, atmo):
        self.atmo_color = atmo.color[:3]
        f = 1.0
        if tuple(self.atmo_color) == (0.0, 0.0, 0.0):
            f = 2.0
        self.atmo_density = atmo.color[-1] * f
        self.id_data.update_tag(refresh={"OBJECT"})

    def get_atmo_id(self):
        return self.get("_atmo_id", 0)

    def set_atmo_id(self, value):
        if self.target == "Scene":
            self["_atmo_id"] = value
            return

        scene_data = bpy.context.scene.amagate_data
        obj = self.id_data
        atmo = get_atmo_by_id(scene_data, value)[1]
        if not atmo:
            return

        if value != self.atmo_id:
            old_atmo = get_atmo_by_id(scene_data, self.atmo_id)[1]
            if old_atmo:
                old_atmo.users_obj.remove(old_atmo.users_obj.find(f"{self.id}"))

            atmo.users_obj.add().obj = obj
            self["_atmo_id"] = value
            scene_data["SectorManage"]["sectors"][str(self.id)]["atmo_id"] = value
        self.update_atmo(atmo)

    ############################
    def get_external_id(self):
        return self.get("_external_id", 0)

    def set_external_id(self, value):
        if self.target == "Scene":
            self["_external_id"] = value
            return

        scene_data = bpy.context.scene.amagate_data
        obj = self.id_data
        external = get_external_by_id(scene_data, value)[1]
        if not external:
            return
        if not external.obj:
            external.update_obj()

        if value != self.external_id:
            old_external_id = self.external_id
            old_external = get_external_by_id(scene_data, old_external_id)[1]
            if old_external:
                old_external.users_obj.remove(old_external.users_obj.find(f"{self.id}"))

            external.users_obj.add().obj = obj
            self["_external_id"] = value
            scene_data["SectorManage"]["sectors"][str(self.id)]["external_id"] = value
        self.update_external(external)

    def update_external(self, external, rotation_euler=None):
        if not rotation_euler:
            rotation_euler = external.vector.to_track_quat("-Z", "Z").to_euler()
        obj = self.ensure_external_obj(external)
        obj.rotation_euler = rotation_euler

    def ensure_external_obj(self, external):
        light_data = external.obj

        light = self.external_obj
        if not light:
            name = f"AG.Sector{self.id}.Sun"
            light = bpy.data.objects.get(name)
            if not light:
                light = bpy.data.objects.new(name, object_data=light_data)
            else:
                light.data = light_data
            self.external_obj = light

            light.hide_select = True
            # self.id_data.users_collection[0].objects.link(light)
            # light.parent = self.id_data
            link2coll(light, ensure_collection(AG_COLL, hide_select=True))
            # 创建灯光链接集合
            collections = bpy.data.collections
            name = f"{name}.Linking"
            lightlink_coll = collections.get(name)
            if lightlink_coll:
                collections.remove(lightlink_coll)
            lightlink_coll = collections.new(name)
            light.light_linking.receiver_collection = lightlink_coll
            light.light_linking.blocker_collection = lightlink_coll
            link2coll(ensure_null_object(), lightlink_coll)

            # TODO 将外部光物体约束到扇区中心，如果为天空扇区则可见，否则不可见
        elif light.data != light_data:
            light.data = light_data

        return self.external_obj

    ############################
    def get_ambient_color(self):
        attr = "ambient_color"
        if self.target == "SectorPublic":
            sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
            return getattr(sec_data, attr)
        else:
            return self.get(attr, (0.784, 0.784, 0.784))

    def set_ambient_color(self, value):
        attr = "ambient_color"

        if self.target == "SectorPublic":
            for sec in SELECTED_SECTORS:
                sec_data = sec.amagate_data.get_sector_data()
                setattr(sec_data, attr, value)
        else:
            # if value == tuple(getattr(self, attr)):
            #     return

            self[attr] = value

            if self.target == "Sector":
                light_data = self.ensure_ambient_light()
                light_data.color = getattr(self, attr)

    def ensure_ambient_light(self):
        scene_data = bpy.context.scene.amagate_data
        name = f"AG.Sector{self.id}.Ambient"
        light_data = bpy.data.lights.get(name)
        if not light_data:
            light_data = bpy.data.lights.new(name, type="SUN")
            light_data.volume_factor = 0.0
            light_data.use_shadow = False
            light_data.angle = math.pi  # type: ignore
            light_data.energy = 8.0  # type: ignore
            light_data.color = self.ambient_color
        # 创建灯光链接集合
        collections = bpy.data.collections
        name = f"{name}.Linking"
        lightlink_coll = collections.get(name)
        if not lightlink_coll:
            lightlink_coll = collections.new(name)
            link2coll(ensure_null_object(), lightlink_coll)
        link2coll(self.id_data, lightlink_coll)

        for i in range(1, 3):  # 1 2
            name = f"{light_data.name}{i}"
            obj = bpy.data.objects.get(name)
            if not obj:
                obj = bpy.data.objects.new(name, object_data=light_data)
            elif obj.data != light_data:
                obj.data = light_data
            if i == 1:
                obj.rotation_euler = (0, 0, 0)
            else:
                obj.rotation_euler = (math.pi, 0, 0)
            link2coll(obj, ensure_collection(AG_COLL, hide_select=True))
            obj.light_linking.receiver_collection = lightlink_coll
            obj.light_linking.blocker_collection = lightlink_coll

        return light_data

    ############################
    def set_matslot(self, mat, faces=[]):
        """设置材质槽位"""
        obj = self.id_data  # type: Object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore

        slot = obj.material_slots.get(mat.name)
        if not slot:
            # 排除已使用的槽位
            slots = set(range(len(obj.material_slots)))
            for face in mesh.polygons:
                if face.index in faces:
                    continue
                slots.discard(face.material_index)
                if not slots:
                    break

            # 选择空槽位，如果没有的话则新建
            if slots:
                slot = obj.material_slots[slots.pop()]
            else:
                mesh.materials.append(None)
                slot = obj.material_slots[-1]
            slot.material = mat

        if slot.link != "OBJECT":
            slot.link = "OBJECT"
        if not slot.material:
            slot.material = mat
        slot_index = slot.slot_index
        for i in faces:
            mesh.polygons[i].material_index = slot_index

    ############################
    def get_id(self):
        scene_data = bpy.context.scene.amagate_data
        SectorManage = scene_data["SectorManage"]

        if SectorManage["deleted_id_count"]:
            SectorManage["deleted_id_count"] -= 1
            id_ = 1
            while f"{id_}" in SectorManage["sectors"]:
                id_ += 1
        else:
            SectorManage["max_id"] += 1
            id_ = SectorManage["max_id"]
        return id_

    ############################
    def init(self):
        scene = bpy.context.scene
        scene_data = scene.amagate_data

        id_ = self.get_id()
        self.id = id_

        obj = self.id_data  # type: Object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        # 添加到扇区管理字典
        scene_data["SectorManage"]["sectors"][str(id_)] = {
            "obj": obj,
            "light_objs": [],
            "atmo_id": 0,
            "external_id": 0,
        }
        # 初始化连接管理器
        self["ConnectManager"] = {"sec_ids": [], "faces": {}, "new_verts": []}

        # 在属性面板显示ID
        obj[f"AG.Sector ID"] = id_

        # 凹多面体投影切割数据
        self["ConcaveData"] = {"verts": [], "faces": [], "proj_normal": None}

        # 命名并链接到扇区集合
        name = f"Sector{self.id}"
        obj.rename(name, mode="ALWAYS")
        obj.data.rename(name, mode="ALWAYS")
        coll = ensure_collection(S_COLL)
        if coll not in obj.users_collection:
            # 清除集合
            obj.users_collection[0].objects.unlink(obj)
            # 链接到集合
            link2coll(obj, coll)

        # self.flat_light.color = scene_data.defaults.flat_light.color

        # 添加修改器
        modifier = obj.modifiers.new("", type="NODES")
        modifier.node_group = scene_data.sec_node  # type: ignore

        # 添加网格属性
        mesh.attributes.new(name="amagate_connected", type="INT", domain="FACE")
        mesh.attributes.new(name="amagate_flag", type="INT", domain="FACE")
        mesh.attributes.new(name="amagate_tex_id", type="INT", domain="FACE")
        mesh.attributes.new(name="amagate_tex_pos", type="FLOAT2", domain="FACE")
        mesh.attributes.new(name="amagate_tex_rotate", type="FLOAT", domain="FACE")
        mesh.attributes.new(name="amagate_tex_scale", type="FLOAT2", domain="FACE")

        # 设置预设纹理
        for i in ("Floor", "Ceiling", "Wall"):
            def_prop = scene_data.defaults.textures[i]

            prop = self.textures.add()
            prop.target = "Sector"
            prop.name = i
            prop.id = def_prop.id
            prop.xpos = def_prop.xpos
            prop.ypos = def_prop.ypos
            prop.xzoom = def_prop.xzoom
            prop.yzoom = def_prop.yzoom
            prop.angle = def_prop.angle

        for face in mesh.polygons:  # polygons 代表面
            face_index = face.index  # 面的索引
            face_normal = face.normal  # 面的法线方向（Vector）

            # 设置纹理
            dp = face_normal.dot(Vector((0, 0, 1)))
            if dp > 0.99999:  # 地板
                face_flag_name = "Floor"
            elif dp < -0.99999:  # 天花板
                face_flag_name = "Ceiling"
            else:  # 墙壁
                face_flag_name = "Wall"

            tex_prop = self.textures[face_flag_name]
            tex_id = tex_prop.id
            mesh.attributes["amagate_flag"].data[face_index].value = FACE_FLAG[face_flag_name]  # type: ignore
            mesh.attributes["amagate_tex_id"].data[face_index].value = tex_id  # type: ignore
            mat = None
            tex = get_texture_by_id(tex_id)[1]
            self.set_matslot(ensure_material(tex), [face_index])

            # 设置纹理参数
            mesh.attributes["amagate_tex_pos"].data[face_index].vector = tex_prop.pos  # type: ignore
            mesh.attributes["amagate_tex_rotate"].data[face_index].value = tex_prop.angle  # type: ignore
            mesh.attributes["amagate_tex_scale"].data[face_index].vector = tex_prop.zoom  # type: ignore

        # 指定大气
        self.atmo_id = scene_data.defaults.atmo_id
        # 指定外部光
        self.external_id = scene_data.defaults.external_id
        # 设置环境光
        self.ambient_color = scene_data.defaults.ambient_color

        # 判断是否为凸物体
        self.is_convex = ag_utils.is_convex(obj)

        obj.amagate_data.is_sector = True


# 图像属性
class ImageProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    mat_obj: PointerProperty(type=bpy.types.Material)  # type: ignore
    builtin: BoolProperty(name="Builtin", default=False)  # type: ignore


# 场景属性
class SceneProperty(bpy.types.PropertyGroup):
    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore

    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(name="Atmosphere", default=0)  # type: ignore

    # 外部光
    externals: CollectionProperty(type=ExternalLightProperty)  # type: ignore
    active_external: IntProperty(name="External Light", default=0)  # type: ignore

    active_texture: IntProperty(name="Texture", default=0, set=lambda self, value: self.set_active_texture(value), get=lambda self: self.get_active_texture())  # type: ignore

    defaults: PointerProperty(type=SectorProperty)  # type: ignore # 扇区默认属性

    # 纹理预览
    tex_preview: PointerProperty(type=bpy.types.Image)  # type: ignore
    builtin_tex_saved: BoolProperty(name="Builtin Tex Saved", default=False)  # type: ignore
    # 存储确保对象
    ensure_null_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    ensure_null_tex: PointerProperty(type=bpy.types.Image)  # type: ignore
    ensure_coll: CollectionProperty(type=CollCollection)  # type: ignore
    render_cam: PointerProperty(type=bpy.types.Object)  # type: ignore
    # 存储节点
    sec_node: PointerProperty(type=bpy.types.NodeTree)  # type: ignore
    eval_node: PointerProperty(type=bpy.types.NodeTree)  # type: ignore

    # 渲染视图索引
    render_view_index: IntProperty(name="Render View Index", default=-1)  # type: ignore

    areas_show_hud: CollectionProperty(type=IntegerCollection)  # type: ignore

    # 操作属性
    operator_props: PointerProperty(type=OperatorProperty)  # type: ignore

    # 通用属性
    sector_public: PointerProperty(type=SectorProperty)  # type: ignore
    ############################

    def get_active_texture(self):
        value = self.get("_active_texture", 0)

        if value >= len(bpy.data.images) or bpy.data.images[value].amagate_data.id == 0:
            value = next((i for i, img in enumerate(bpy.data.images) if img.amagate_data.id != 0), 0)  # type: ignore

        return value

    def set_active_texture(self, value):
        self["_active_texture"] = value

    ############################
    def init(self):
        #
        self["SectorManage"] = {"deleted_id_count": 0, "max_id": 0, "sectors": {}}
        defaults = self.defaults

        defaults.target = "Scene"
        defaults.atmo_id = 1
        defaults.external_id = 1

        self.sector_public.target = "SectorPublic"
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


# 物体属性
class ObjectProperty(bpy.types.PropertyGroup):
    SectorData: CollectionProperty(type=SectorProperty)  # type: ignore
    is_sector: BoolProperty(default=False)  # type: ignore

    def get_sector_data(self) -> SectorProperty:
        if len(self.SectorData) == 0:
            return None  # type: ignore
        return self.SectorData[0]

    def set_sector_data(self):
        if not self.SectorData:
            self.SectorData.add()
            # return self.SectorData[0]


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
    global ICONS

    import bpy.utils.previews

    ICONS = bpy.utils.previews.new()
    icons_dir = os.path.join(ADDON_PATH, "icons")
    ICONS.load("star", os.path.join(icons_dir, "star.png"), "IMAGE")
    ICONS.load("blade", os.path.join(icons_dir, "blade.png"), "IMAGE")

    bpy.utils.register_class(AmagatePreferences)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.amagate_data = PointerProperty(type=ObjectProperty, name="Amagate Data")  # type: ignore
    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty, name="Amagate Data")  # type: ignore
    bpy.types.Image.amagate_data = PointerProperty(type=ImageProperty, name="Amagate Data")  # type: ignore

    # 注册回调函数
    bpy.app.timers.register(register_timer, first_interval=0.5)  # type: ignore


def unregister():
    global ICONS, draw_handler
    del bpy.types.Object.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    del bpy.types.Image.amagate_data  # type: ignore

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.utils.unregister_class(AmagatePreferences)

    bpy.utils.previews.remove(ICONS)
    ICONS = None

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
