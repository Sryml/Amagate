# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import re
import ast
import os
import math
import shutil
import pickle
import threading
import contextlib
import json
import logging

from pathlib import Path
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

# from collections import Counter
#
import bpy
import bpy.utils.previews

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

# import blf
from mathutils import *  # type: ignore


#
if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection

############################ 全局变量
Copyright = "(C) 2024-2025 Sryml"

# 获取插件包名
PACKAGE = ".".join(__package__.split(".")[:-1])
# 获取插件根目录路径
ADDON_PATH = os.path.abspath(f"{os.path.dirname(__file__)}/..")

# 创建目录
os.makedirs(os.path.join(ADDON_PATH, "_LOG"), exist_ok=True)

# 需要的python包
PY_PACKAGES_REQUIRED = ["scipy.optimize"]

# pattern = r"^([a-zA-Z0-9_-]+)"  # 匹配行首的字母、数字、下划线或连字符
# with open(os.path.join(ADDON_PATH, "_BAT", "requirements.txt"), "r") as f:
#     for line in f:
#         line = line.strip()  # 去除首尾空白
#         if line and not line.startswith("#"):  # 跳过空行和注释
#             match = re.match(pattern, line)
#             if match:
#                 PY_PACKAGES_REQUIRED.append(match.group(1))

# python包是否安装
PY_PACKAGES_INSTALLED = False
# python包正在安装
PY_PACKAGES_INSTALLING = False

# 版本号和日期
with open(os.path.join(ADDON_PATH, "version"), "r") as v:
    VERSION = v.readline().strip()
    VERSION_DATE = int(v.readline().strip())

# 模型包版本
filepath = Path(ADDON_PATH) / "Models/version"
if filepath.exists():
    with open(filepath, "r") as f:
        MODELPACKAGE_VERSION = f.readline().strip()
else:
    MODELPACKAGE_VERSION = "None"

#
DEBUG = os.path.exists(os.path.join(ADDON_PATH, "DEBUG"))

ICONS: Any = None
ENT_PREVIEWS: Any = None
BLANK1 = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items["BLANK1"].value  # type: ignore

# fmt: off
IMAGE_FILTER = (
    # 常见格式
    ".png", ".jpg", ".jpeg",
    ".tga", ".tif", ".tiff",
    ".exr", ".hdr", ".webp",
    ".bmp", 
    # 较少见的格式
    ".iris", ".iriz", ".aviraw", ".avijpeg",
)
# fmt: on

# 日志相关
logger = logging.getLogger(PACKAGE)
if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("[Amagate] %(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(handler)
logger.propagate = False

# 模型包清单
E_MANIFEST = json.load(
    open(os.path.join(ADDON_PATH, "Models/manifest.json"), "r", encoding="utf-8")
)

RENDER_ENGINES = {}


# 可用的渲染引擎
def get_render_engines():
    result = {
        "EEVEE": "BLENDER_EEVEE",
        "WORKBENCH": "BLENDER_EEVEE",
        "CYCLES": "BLENDER_EEVEE",
    }
    try:
        bpy.data.scenes[0].render.engine = ""  # type: ignore
    except Exception as e:
        match = re.search(r"\((.*?)\)", str(e))
        try:
            for engine in ast.literal_eval(match.group(1)):
                if "EEVEE" in engine.upper():
                    result["EEVEE"] = engine
                elif "WORKBENCH" in engine.upper():
                    result["WORKBENCH"] = engine
                elif "CYCLES" in engine.upper():
                    result["CYCLES"] = engine
        except:
            pass
    return result


############################


def region_redraw(target):
    area = bpy.context.area
    if not area:
        area = next(
            (area for area in bpy.context.screen.areas if area.type == "VIEW_3D"), None
        )

    if area:
        for region in area.regions:
            if region.type == target:
                region.tag_redraw()  # 刷新该区域


def area_redraw(target):
    for area in bpy.context.screen.areas:
        if area.type == target:
            area.tag_redraw()


def active_panel_category(region, category):
    def warp():
        try:
            region.active_panel_category = category  # type: ignore
        except:
            pass

    return warp


def show_region_ui():
    area = next(
        (area for area in bpy.context.screen.areas if area.type == "VIEW_3D"), None
    )

    if area:
        # 显示N面板
        with bpy.context.temp_override(area=area):
            bpy.ops.wm.context_toggle(data_path="space_data.show_region_ui")

        region = next(r for r in area.regions if r.type == "UI")
        bpy.app.timers.register(
            active_panel_category(region, "Amagate"), first_interval=0.05
        )
        # 更新UI
        area_redraw("VIEW_3D")


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


def get_object_name(prefix, start_id=1) -> str:
    while (obj := bpy.data.objects.get(f"{prefix}{start_id}")) and obj.users > 0:
        start_id += 1
    if obj:
        bpy.data.objects.remove(obj)
    return f"{prefix}{start_id}"


def get_coll_name(prefix, start_id=1) -> str:
    while (coll := bpy.data.collections.get(f"{prefix}{start_id}")) and coll.users > 0:
        start_id += 1
    if coll:
        bpy.data.collections.remove(coll)
    return f"{prefix}{start_id}"


#
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
    if hasattr(obj, "type"):
        if obj.type == "FRAME":
            return obj.name
        elif obj.type == "GEOMETRY":
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
        if hasattr(node, prop):  # 兼容旧版本
            if prop == "node_tree":
                setattr(node, prop, bpy.data.node_groups.get(value))
            elif prop != "parent":
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
    nodes_data = {"nodes": [], "links": [], "socket": []}
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

    # 保存接口
    if hasattr(target, "type") and target.type == "GEOMETRY":
        for item in target.interface.items_tree:
            item_data = {
                "name": item.name,
                "socket_type": item.socket_type,
                "in_out": item.in_out if hasattr(item, "in_out") else "NONE",
                # "item_type": item.item_type,
                # "description": item.description,
                # "position": item.position,
            }
            nodes_data["socket"].append(item_data)

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

    # 导入接口
    if hasattr(target, "type") and target.type == "GEOMETRY":
        target.interface.clear()
        for item_data in nodes_data["socket"]:
            socket = target.interface.new_socket(
                name=item_data["name"],
                socket_type=item_data["socket_type"],
                in_out=item_data["in_out"],
            )

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
    bl_idname = PACKAGE  # type: ignore

    # Cubemap转换设置
    cubemap_out_format: EnumProperty(
        name="Format",
        description="",
        items=[
            ("JPEG", "JPEG", ""),
            ("PNG", "PNG", ""),
            ("TARGA", "TARGA", ""),
            ("OPEN_EXR", "OPEN_EXR", ""),
            ("HDR", "HDR", ""),
        ],
        default="JPEG",
    )  # type: ignore
    cubemap_out_res: EnumProperty(
        name="Resolution",
        description="",
        items=[
            ("1K", "1K", ""),
            ("2K", "2K", ""),
            ("4K", "4K", ""),
            ("8K", "8K", ""),
        ],
        default="1K",
        update=lambda self, context: self.cubemap_res_enum_update(context),  # type: ignore
    )  # type: ignore
    cubemap_out_res_x: IntProperty(
        name="Resolution",
        description="",
        default=1024,
        step=1024,
        subtype="PIXEL",
    )  # type: ignore
    cubemap_out_res_y: IntProperty(
        name="Resolution",
        description="",
        default=512,
        step=512,
        subtype="PIXEL",
    )  # type: ignore

    # 用于保存面板的展开状态
    expand_state: BoolProperty(name="Expand State", default=True)  # type: ignore
    is_user_modified: BoolProperty(default=False)  # type: ignore

    ############################
    def cubemap_res_enum_update(self, context):
        F = int(self.cubemap_out_res[0])
        self.cubemap_out_res_x = F * 1024
        self.cubemap_out_res_y = F * 512

    ############################

    # def __init__(self):
    #     super().__init__()
    # self.expand_state = False

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
            "expand_state",
            text="",
            icon="TRIA_DOWN" if self.expand_state else "TRIA_RIGHT",
            emboss=False,
        )
        row.label(text="Keymap")
        # if self.is_user_modified:
        #     col = row.column()
        #     col.alignment = "RIGHT"
        #     col.operator("preferences.keymap_restore", text="Restore")

        if self.expand_state and keymap_items:
            box = layout.box()
            split = box.split()
            col = split.column()
            for kmi in keymap_items:
                col.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)


def register_shortcuts():
    global addon_keymaps
    # preferences = bpy.context.preferences.addons[PACKAGE].preferences  # type: ignore

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


############################
############################ Collection Props
############################


# 物体收集器
class ObjectCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    obj: PointerProperty(type=bpy.types.Object)  # type: ignore


# 整型收集器
class IntegerCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    value: IntProperty(default=0, update=lambda self, context: self.update_value(context))  # type: ignore

    def update_value(self, context):
        self.name = str(self.value)


# 字符串收集器
class StringCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore


# 扇区收集器
class SectorCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    obj: PointerProperty(type=bpy.types.Object, update=lambda self, context: self.update_obj(context))  # type: ignore

    def update_obj(self, context):
        if self.obj:
            self.name = str(self.obj.amagate_data.get_sector_data().id)


# 集合收集器
class CollCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    obj: PointerProperty(type=bpy.types.Collection)  # type: ignore


# 实体组收集器
class EntityGroupCollection(bpy.types.PropertyGroup):
    index: IntProperty(default=0)  # type: ignore
    value: BoolProperty(default=False, get=lambda self: self.get_value(), set=lambda self, value: self.set_value(value))  # type: ignore
    layer_name: StringProperty(default="")  # type: ignore

    def get_value(self):
        from . import ag_utils

        context = bpy.context
        if context.mode != "EDIT_MESH":
            return False
        #
        obj = context.object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        bm = bmesh.from_edit_mesh(mesh)
        face = next((f for f in bm.faces if f.select), None)
        if not face:
            return False
        #
        layer = bm.faces.layers.int.get(self.layer_name)
        group = ag_utils.int_to_uint(face[layer])  # type: ignore
        return (group >> self.index) & 1

    def set_value(self, value):
        from . import ag_utils

        mask_limit = 0xFFFFFFFF
        mask = 1 << self.index

        context = bpy.context
        obj = context.object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        bm = bmesh.from_edit_mesh(mesh)
        faces = [f for f in bm.faces if f.select]
        if not faces:
            return

        layer = bm.faces.layers.int.get(self.layer_name)
        if value:
            for face in faces:
                # 单选
                if self.layer_name == "amagate_group":
                    group = ag_utils.uint_to_int(mask)
                else:
                    group = ag_utils.uint_to_int(
                        face[layer] | mask  # type: ignore
                    )  # 设置为1
                face[layer] = group  # type: ignore
        else:
            for face in faces:
                group = ag_utils.uint_to_int(
                    face[layer] & (~mask & mask_limit)  # type: ignore
                )  # 设置为0
                face[layer] = group  # type: ignore


############################
############################ Operator Props
############################


# 进度条属性
class ProgressBarProperty(bpy.types.PropertyGroup):
    # py包安装进度条
    pyp_install_progress: FloatProperty(name="Progress", default=0.0, min=0, max=1, precision=6, update=lambda self, context: self.pyp_install_progress_update(context))  # type: ignore

    def pyp_install_progress_update(self, context):
        region_redraw("UI")


############################
from . import entity_data, sector_data, L3D_data

############################
############################ 主属性组
############################


# 图像属性
class ImageProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    mat_obj: PointerProperty(type=bpy.types.Material)  # type: ignore
    # Amagate内置纹理标识
    builtin: BoolProperty(name="Builtin", default=False)  # type: ignore


#
class WindowManagerProperty(bpy.types.PropertyGroup):
    ent_groups: CollectionProperty(type=EntityGroupCollection)  # type: ignore
    ent_mutilation_groups: CollectionProperty(type=EntityGroupCollection)  # type: ignore
    #
    ent_inter_name: StringProperty(default="", get=lambda self: self.get_ent_inter_name(), set=lambda self, value: None)  # type: ignore
    ent_enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_ent_enum,
        update=lambda self, context: self.update_ent_enum(context),
    )  # type: ignore
    equipment_enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_equipment,
        update=entity_data.add_equipment_pre,
    )  # type: ignore
    prop_enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_prop,
        update=entity_data.add_prop_pre,
    )  # type: ignore
    contained_item_enum: EnumProperty(
        translation_context="Entity",
        items=entity_data.get_ent_enum,
        update=entity_data.add_contained_item_pre,
    )  # type: ignore
    ent_preview: EnumProperty(
        translation_context="Entity", items=entity_data.get_ent_preview
    )  # type: ignore
    prefab_name: StringProperty(default="")  # type: ignore
    prefab_type: EnumProperty(
        name="",
        items=[
            ("99", "None", ""),
            ("0", "Equipment", ""),
            ("8", "Prop", ""),
            ("20", "Character", ""),
        ],
    )  # type: ignore
    active_equipment: IntProperty(default=0)  # type: ignore
    active_prop: IntProperty(default=0)  # type: ignore
    active_contained_item: IntProperty(default=0)  # type: ignore

    ############################

    def get_ent_inter_name(self):
        wm_data = bpy.context.window_manager.amagate_data
        return bpy.types.UILayout.enum_item_description(
            wm_data, "ent_enum", wm_data.ent_enum
        )

    @staticmethod
    def update_ent_enum(context: Context):
        from . import ag_utils

        wm_data = context.window_manager.amagate_data
        name = bpy.types.UILayout.enum_item_name(wm_data, "ent_enum", wm_data.ent_enum)
        wm_data.prefab_name = name
        ag_utils.simulate_keypress(ag_utils.K_ESC)


# 物体属性
class ObjectProperty(bpy.types.PropertyGroup):
    SectorData: CollectionProperty(type=sector_data.SectorProperty)  # type: ignore
    GhostSectorData: CollectionProperty(type=sector_data.GhostSectorProperty)  # type: ignore
    EntityData: CollectionProperty(type=entity_data.EntityProperty)  # type: ignore
    is_sector: BoolProperty(default=False)  # type: ignore
    is_gho_sector: BoolProperty(default=False)  # type: ignore
    is_entity: BoolProperty(default=False)  # type: ignore
    # 实体组件类型
    ent_comp_type: IntProperty(default=0)  # type: ignore

    ############################
    def get_sector_data(self) -> sector_data.SectorProperty:
        if len(self.SectorData) == 0:
            return None  # type: ignore
        return self.SectorData[0]

    def set_sector_data(self):
        if not self.SectorData:
            self.SectorData.add()
            # return self.SectorData[0]

    ############################
    def get_ghost_sector_data(self) -> sector_data.GhostSectorProperty:
        if len(self.GhostSectorData) == 0:
            return None  # type: ignore
        return self.GhostSectorData[0]

    def set_ghost_sector_data(self):
        if not self.GhostSectorData:
            self.GhostSectorData.add()
            self.is_gho_sector = True

    ############################
    def get_entity_data(self) -> entity_data.EntityProperty:
        if len(self.EntityData) == 0:
            return None  # type: ignore
        return self.EntityData[0]

    def set_entity_data(self):
        if not self.EntityData:
            self.EntityData.add()
            self.EntityData[0].target = "Object"
            self.EntityData[0].light_prop.target = "Object"
            self.is_entity = True


# 场景属性
class SceneProperty(L3D_data.SceneProperty):
    # Amagate版本
    version: StringProperty()  # type: ignore
    # 版本日期
    version_date: IntProperty()  # type: ignore

    EntityData: PointerProperty(type=entity_data.EntityProperty)  # type: ignore
    # 骨架
    # armature_obj: PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == "ARMATURE" and obj.library is None)  # type: ignore
    # 摄像机
    # camera_obj: PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == "CAMERA" and obj.library is None)  # type: ignore


############################


def register_timer():
    # global RENDER_ENGINES
    # RENDER_ENGINES = get_render_engines()
    L3D_data.load_post(None)


############################
############################
############################
main_classes = (ImageProperty, ObjectProperty, SceneProperty, WindowManagerProperty)
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type)
    and any(issubclass(cls, parent) for parent in class_tuple)
    and cls not in main_classes
]


def register():
    global ICONS

    ICONS = bpy.utils.previews.new()
    icons_dir = os.path.join(ADDON_PATH, "icons")
    for root, dirs, files in os.walk(icons_dir):
        for file in files:
            if file.endswith(".png"):
                ICONS.load(file[:-4], os.path.join(root, file), "IMAGE")
    #
    entity_data.load_ent_preview()
    #
    bpy.utils.register_class(AmagatePreferences)
    #
    for cls in classes:
        bpy.utils.register_class(cls)
    #
    # from . import entity_data, sector_data, L3D_data
    entity_data.register()
    sector_data.register()
    L3D_data.register()
    # XXX 仅用于热更新调用，直接从blend文件打开blender不会触发
    bpy.app.timers.register(register_timer, first_interval=0.5)  # type: ignore
    #
    for cls in main_classes:
        bpy.utils.register_class(cls)
    #
    bpy.types.WindowManager.amagate_data = PointerProperty(type=WindowManagerProperty, name="Amagate Data")  # type: ignore
    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty, name="Amagate Data")  # type: ignore
    bpy.types.Image.amagate_data = PointerProperty(type=ImageProperty, name="Amagate Data")  # type: ignore
    bpy.types.Object.amagate_data = PointerProperty(type=ObjectProperty, name="Amagate Data")  # type: ignore


def unregister():
    global ICONS, ENT_PREVIEWS

    # 关闭服务器
    from ..service import ag_service

    ag_service.stop_server()

    for cls in main_classes:
        bpy.utils.unregister_class(cls)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.utils.unregister_class(AmagatePreferences)
    #
    bpy.utils.previews.remove(ICONS)
    bpy.utils.previews.remove(ENT_PREVIEWS)
    ICONS = None
    ENT_PREVIEWS = None
    #
    # from . import entity_data, sector_data, L3D_data

    L3D_data.unregister()
    sector_data.unregister()
    entity_data.unregister()
    ############################
    handler = logger.handlers[0]
    logger.removeHandler(handler)
    handler.close()
    #
    del bpy.types.WindowManager.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    del bpy.types.Image.amagate_data  # type: ignore
    del bpy.types.Object.amagate_data  # type: ignore
