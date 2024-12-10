from __future__ import annotations

import os
import pickle
import threading
from typing import Any, TYPE_CHECKING

# from collections import Counter

import bpy
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
from mathutils import *  # type: ignore


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image

############################ 全局变量
DEBUG = False

ICONS: Any = None

AG_COLL = "Amagate Auto Generated"
S_COLL = "Sector Collection"
GS_COLL = "Ghost Sector Collection"
E_COLL = "Entity Collection"
C_COLL = "Camera Collection"

AUTO_CLEAN_LOCK: threading.Lock = None  # type: ignore
############################


def region_redraw(target):
    for region in bpy.context.area.regions:  # type: ignore
        if region.type == target:
            region.tag_redraw()  # 刷新该区域


# XXX 弃用的
def get_scene_suffix(scene: bpy.types.Scene = None) -> str:  # type: ignore
    if not scene:
        scene = bpy.context.scene
    scene_data = scene.amagate_data  # type: ignore
    suffix = ""
    if scene_data.id != 1:
        suffix = f" (BS{scene_data.id})"
    return suffix


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
def ensure_null_texture():
    images = bpy.data.images
    img = images.get("NULL")
    if not img:
        img = images.new("NULL", width=256, height=256)
        img.amagate_data.id = -1  # type: ignore
    elif not img.amagate_data.id:  # type: ignore
        img.amagate_data.id = -1  # type: ignore
    if not img.use_fake_user:
        img.use_fake_user = True


# 确保NULL物体存在
def ensure_null_object() -> Object:
    null_obj = bpy.data.objects.get("NULL")  # type: Object # type: ignore
    if not null_obj:
        null_obj = bpy.data.objects.new("NULL", None)
        null_obj.use_fake_user = True
    return null_obj


# 确保集合
def ensure_collection(name, hide_select=False) -> bpy.types.Collection:
    scene = bpy.context.scene
    collections = bpy.data.collections
    name = f"{pgettext(name)}{get_scene_suffix(scene)}"
    coll = collections.get(name)
    if not coll:
        coll = collections.new(name)
        scene.collection.children.link(coll)
        coll.hide_select = hide_select
    return coll


# 确保材质
def ensure_material(tex: Image) -> bpy.types.Material:
    tex_data = tex.amagate_data
    name = f"AG.Mat{tex_data.id}"
    mat = tex_data.mat_obj
    if not mat:
        mat = bpy.data.materials.new("")
        mat.rename(name, mode="ALWAYS")
        filepath = os.path.join(os.path.dirname(__file__), "nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))
        import_nodes(mat, nodes_data["mat_nodes"])
        mat.use_fake_user = True
        mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
        mat.use_backface_culling = True
        tex_data.mat_obj = mat

    return mat


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
    # 处理输入
    inputs_data = []
    for i, input_socket in enumerate(node.inputs):
        if not input_socket.is_linked:
            if not hasattr(input_socket, "default_value"):
                continue
            value = to_primitive(input_socket.default_value)  # type: ignore
            if value is not None:
                if value != to_primitive(
                    temp_node.inputs[i].default_value
                ):  # 只存储非默认值
                    inputs_data.append(
                        {"idx": i, "name": input_socket.name, "value": value}
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
        input_socket = node.inputs.get(input_data["name"])
        input_socket.default_value = input_data["value"]

    node.location = node_data["location"]

    return node


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
        temp_node = temp_nodes.get(node.bl_idname)
        if not temp_node:
            temp_node = temp_nodes.setdefault(
                node.bl_idname, nodes.new(type=node.bl_idname)
            )

        node_data = serialize_node(node, temp_node)
        nodes_data["nodes"].append(node_data)

    for node in temp_nodes.values():
        nodes.remove(node)

    # 遍历连接
    for link in links:
        link_data = {
            "from_node": link.from_node.name,
            "from_socket": link.from_socket.name,
            "to_node": link.to_node.name,
            "to_socket": link.to_socket.name,
        }
        nodes_data["links"].append(link_data)

    # with open(filepath, "w", encoding="utf-8") as file:
    # file.write(f"{var_name} = ")
    # pprint(nodes_data, stream=file, indent=0, sort_dicts=False)

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
    for node in nodes:
        nodes.remove(node)

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
############################ 依赖图更新回调
############################


def auto_clean():
    scene_data = bpy.context.scene.amagate_data
    coll = ensure_collection(S_COLL)
    SectorManage = scene_data["SectorManage"]
    if len(SectorManage["sectors"]) != len(coll.all_objects):
        exist_ids = set(str(obj.amagate_data.get_sector_data().id) for obj in coll.all_objects if obj.amagate_data.get_sector_data())  # type: ignore
        all_ids = set(SectorManage["sectors"].keys())
        deleted_ids = sorted(all_ids - exist_ids, reverse=True)

        if deleted_ids:
            # 如果只是移动到其它集合，则撤销操作
            obj = SectorManage["sectors"][deleted_ids[0]]["obj"]
            if obj and bpy.context.scene in obj.users_scene:
                bpy.ops.ed.undo()
                AUTO_CLEAN_LOCK.release()
                return

            bpy.ops.ed.undo()
            scene_data = bpy.context.scene.amagate_data
            coll = ensure_collection(S_COLL)
            SectorManage = scene_data["SectorManage"]

            for id_key in deleted_ids:
                obj = SectorManage["sectors"][id_key]["obj"]
                bpy.data.meshes.remove(obj.data)
                # bpy.data.objects.remove(obj)
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

    AUTO_CLEAN_LOCK.release()


# def auto_clean_release():
#     AUTO_CLEAN_LOCK.release()


def depsgraph_update_post(scene, depsgraph: bpy.types.Depsgraph):
    if AUTO_CLEAN_LOCK.acquire(blocking=False):
        auto_clean()
        # bpy.app.timers.register(auto_clean_release, first_interval=0.2)


############################
############################ 保存前回调
############################


# 定义检查函数
def check_before_save(scene: bpy.types.Scene):
    img = bpy.data.images.get("NULL")
    if img:
        img.use_fake_user = True


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
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        scene_data = context.scene.amagate_data  # type: ignore
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        # row.alignment = "LEFT"
        split = row.split(factor=0.6)
        row = split.row()
        # split = row

        # col = split.column()
        # col.enabled = False
        # col.label(text=f"ID: {item.id}")
        i = ICONS["star"].icon_id if item.id == scene_data.defaults.atmo_id else 0
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
        scene_data = context.scene.amagate_data  # type: ignore
        light = item  # 获取大气数据
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()
        split = row.split(factor=0.6)
        row = split.row()

        i = ICONS["star"].icon_id if light.id == scene_data.defaults.external_id else 0
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
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = [0] * len(items)
        flt_neworder = []

        for idx, item in enumerate(items):
            if item.amagate_data.id != 0:
                flt_flags[idx] = self.bitflag_filter_item

        return flt_flags, flt_neworder

    def draw_item(
        self,
        context,
        layout,
        data,
        item: Image,
        icon,
        active_data,
        active_prop,
    ):
        scene_data = context.scene.amagate_data  # type: ignore
        tex = item
        tex_data = tex.amagate_data  # type: ignore
        enabled = not active_data.readonly if hasattr(active_data, "readonly") else True

        row = layout.row()

        i = tex.preview.icon_id if tex.preview else 0
        col = row.column()
        col.alignment = "LEFT"
        col.label(text="", icon_value=i)

        col = row.column()
        if enabled:
            col.prop(tex, "name", text="", emboss=False)
        else:
            col.label(text=tex.name)

        col = row.column()
        col.alignment = "RIGHT"
        default_id = [
            i["id"] for i in scene_data.defaults["Textures"].values() if i["id"] != 0
        ]
        i = ICONS["star"].icon_id if tex_data.id in default_id else 0
        col.label(text="", icon_value=i)

        col = row.column()
        col.alignment = "RIGHT"
        i = "UGLYPACKAGE" if tex.packed_file else "NONE"
        col.label(text="", icon=i)


############################
############################ Operator Props
############################


class StringCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore


# 选择大气
class Atmo_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data = bpy.context.scene.amagate_data
        if self.target == "Sector":
            sectors = [obj for obj in bpy.context.selected_objects if obj.amagate_data.get_sector_data()]  # type: ignore
            for s in sectors:
                sector_data = s.amagate_data.get_sector_data()  # type: ignore
                sector_data.atmo_id = scene_data.atmospheres[value].id
        elif self.target == "Scene":
            scene_data.defaults.atmo_id = scene_data.atmospheres[value].id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select Atmosphere")


# 选择外部光
class External_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data = bpy.context.scene.amagate_data
        if self.target == "Sector":
            sectors = [obj for obj in bpy.context.selected_objects if obj.amagate_data.get_sector_data()]  # type: ignore
            for s in sectors:
                sector_data = s.amagate_data.get_sector_data()  # type: ignore
                sector_data.external_id = scene_data.externals[value].id
        elif self.target == "Scene":
            scene_data.defaults.external_id = scene_data.externals[value].id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select External Light")


# 选择纹理
class Texture_Select(bpy.types.PropertyGroup):
    index: IntProperty(name="", default=0, get=lambda self: self.get_index(), set=lambda self, value: self.set_index(value))  # type: ignore
    target: StringProperty(default="Sector")  # type: ignore
    readonly: BoolProperty(default=True)  # type: ignore

    def get_index(self):
        return self.get("_index", 0)

    def set_index(self, value):
        if self["_index"] == value:
            return

        self["_index"] = value

        scene_data = bpy.context.scene.amagate_data
        if self.target != "Sector":
            scene_data.defaults["Textures"][self.target]["id"] = bpy.data.images[
                value
            ].amagate_data.id
        region_redraw("UI")

        bpy.ops.ed.undo_push(message="Select Texture")


############################
############################ Object Props
############################


class SectorCollection(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    obj: PointerProperty(type=bpy.types.Object, update=lambda self, context: self.update_obj(context))  # type: ignore

    def update_obj(self, context):
        if self.obj:
            self.name = str(self.obj.amagate_data.get_sector_data().id)


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
        default=(0.0, 0.0, 0.0, 0.02),
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
        return self.get("_color", (0.0, 0.0, 0.0, 0.02))

    def set_color(self, value):
        if value == tuple(self.color):
            return

        self["_color"] = value
        for user in self.users_obj:
            obj = user.obj  # type: Object
            if obj:
                obj.amagate_data.get_sector_data().update_atmo(self)

    def clean(self):
        lst = [i for i, item in enumerate(self.users_obj) if not item.obj]
        for i in reversed(lst):
            self.users_obj.remove(i)

    # 确保引用对象存在
    # def ensure_obj(self, scene: bpy.types.Scene, fix_link=False):
    #     if not self.obj:
    #         name = f"AG.atmo{self.id}{get_scene_suffix(scene)}"
    #         obj = bpy.data.objects.get(name)
    #         if not (obj and obj.type == "EMPTY"):
    #             obj = bpy.data.objects.new(name, None)
    #         obj["id"] = self.id
    #         self.obj = obj

    #         # 引用对象被意外删除，进行自动修复
    #         if fix_link:
    #             for i in bpy.context.scene.objects:
    #                 sec_data = i.amagate_data.get_sector_data() # type: ignore
    #                 if sec_data and sec_data.atmo_id == self.id:
    #                     sec_data.atmo_obj = obj
    #             print("Fixed atmo reference link")

    #     return self.obj


# 纹理属性
class TextureProperty(bpy.types.PropertyGroup):
    # id: IntProperty(name="ID", default=0)  # type: ignore
    # x: FloatProperty(name="X", default=0.0)  # type: ignore
    # y: FloatProperty(name="Y", default=0.0)  # type: ignore

    target: StringProperty(default="Sector")  # type: ignore
    pos: FloatVectorProperty(
        name="Position",
        description="Texture Position",
        subtype="XYZ",
        size=2,
        step=10,
        set=lambda self, value: self.set_pos(value),
        get=lambda self: self.get_pos(),
        # min=-1.0,
        # max=1.0,
    )  # type: ignore
    zoom: FloatVectorProperty(
        name="Zoom",
        description="Texture Zoom",
        subtype="XYZ",
        size=2,
        step=10,
        set=lambda self, value: self.set_zoom(value),
        get=lambda self: self.get_zoom(),
    )  # type: ignore
    zoom_constraint: BoolProperty(
        name="Constraint",
        # description="Zoom Constraint",
        default=True,
    )  # type: ignore
    angle: FloatProperty(name="Angle", default=0.0, set=lambda self, value: self.set_angle(value), get=lambda self: self.get_angle())  # type: ignore
    ############################

    def get_pos(self):
        if self.target != "Sector":
            scene_data = bpy.context.scene.amagate_data
            return scene_data.defaults["Textures"][self.target]["pos"]
        else:
            return self.get("_pos", (0.0, 0.0))

    def set_pos(self, value):
        if self.target != "Sector":
            scene_data = bpy.context.scene.amagate_data
            scene_data.defaults["Textures"][self.target]["pos"] = value
        else:
            self["_pos"] = value

    ############################
    def get_zoom(self):
        if self.target != "Sector":
            scene_data = bpy.context.scene.amagate_data
            return scene_data.defaults["Textures"][self.target]["zoom"]
        else:
            return self.get("_zoom", (10.0, 10.0))

    def set_zoom(self, value):
        if self.target != "Sector":
            scene_data = bpy.context.scene.amagate_data
            if self.zoom_constraint:
                value = list(value)
                old_value = scene_data.defaults["Textures"][self.target]["zoom"]
                idx = 0 if old_value[0] != value[0] else 1
                if old_value[0] == old_value[1]:
                    value[1 - idx] = value[idx]
                else:
                    factor = value[idx] / old_value[idx]
                    value[1 - idx] = old_value[1 - idx] * factor
            scene_data.defaults["Textures"][self.target]["zoom"] = value
        else:
            self["_zoom"] = value

    ############################
    def get_angle(self):
        if self.target != "Sector":
            scene_data = bpy.context.scene.amagate_data
            return scene_data.defaults["Textures"][self.target]["angle"]
        else:
            return self.get("_angle", 0.0)

    def set_angle(self, value):
        if self.target != "Sector":
            scene_data = bpy.context.scene.amagate_data
            scene_data.defaults["Textures"][self.target]["angle"] = value
        else:
            self["_angle"] = value


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

    # TODO 每删除10个扇区触发一次clean
    def clean(self, lst=None):
        if not lst:
            lst = [i for i, item in enumerate(self.users_obj) if not item.obj]
        for i in reversed(lst):
            self.users_obj.remove(i)

    def ensure_obj(self):
        if not self.obj:
            name = f"AG.Sun{self.id}"
            light_data = bpy.data.lights.get(name)
            if not (light_data and light_data.type == "SUN"):
                light_data = bpy.data.lights.new("", type="SUN")
                light_data.rename(name, mode="ALWAYS")
            self.obj = light_data

        return self.obj

    def sync_users(self, rotation_euler):
        items_to_remove = []
        for i, d in enumerate(self.users_obj):
            sec = d.obj
            if not sec:
                items_to_remove.append(i)
            else:
                sec.amagate_data.get_sector_data().update_external(self, rotation_euler)

        if items_to_remove:
            self.clean(items_to_remove)

    def update_obj(self, context=None):
        self.ensure_obj()
        self.obj.color = self.color  # 设置颜色
        rotation_euler = self.vector.to_track_quat("-Z", "Z").to_euler()
        self.sync_users(rotation_euler)
        # light_data.energy = self.energy  # 设置能量


# 环境光属性
class AmbientLightProperty(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
    )  # type: ignore


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
    # 可添加多个，保存数据块名称
    name: StringProperty(name="Name", default="")  # type: ignore
    # TODO


# 扇区属性
class SectorProperty(bpy.types.PropertyGroup):
    as_default: BoolProperty(default=False)  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore
    # is_sector: BoolProperty(default=False)  # type: ignore
    atmo_id: IntProperty(name="Atmosphere", description="", default=0, get=lambda self: self.get_atmo_id(), set=lambda self, value: self.set_atmo_id(value))  # type: ignore
    atmo_color: FloatVectorProperty(name="Color", description="", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0))  # type: ignore
    atmo_density: FloatProperty(name="Density", description="", default=0.02, min=0.0, soft_max=1.0)  # type: ignore
    # atmo_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    # floor_texture: CollectionProperty(type=TextureProperty)  # type: ignore
    # ceiling_texture: CollectionProperty(type=TextureProperty)  # type: ignore
    # wall_texture: CollectionProperty(type=TextureProperty)  # type: ignore

    ambient_light: PointerProperty(type=AmbientLightProperty)  # type: ignore # 环境光
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
        if self.as_default:
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

    def get_external_id(self):
        return self.get("_external_id", 0)

    def set_external_id(self, value):
        if self.as_default:
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

        if not self.external_obj:
            name = f"AG - Sector{self.id}.Sun{self.external_id}"
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

        return self.external_obj

    def set_matslot(self, mat, faces=[]):
        """设置材质槽位"""
        obj = self.id_data  # type: Object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore

        slot = obj.material_slots.get(mat.name)
        if not slot:
            slots = set(range(len(obj.material_slots)))
            for face in mesh.polygons:
                if face.index in faces:
                    continue
                slots.discard(face.material_index)
                if not slots:
                    break

            if slots:
                slot = obj.material_slots[slots.pop()]
            else:
                mesh.materials.append(None)
                slot = obj.material_slots[-1]

        if slot.link != "OBJECT":
            slot.link = "OBJECT"
        if not slot.material:
            slot.material = mat
        slot_index = slot.slot_index
        for i in faces:
            mesh.polygons[i].material_index = slot_index

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

    def init(self):
        scene = bpy.context.scene
        scene_data = scene.amagate_data

        id_ = self.get_id()
        self.id = id_

        obj = self.id_data  # type: Object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore

        scene_data["SectorManage"]["sectors"][str(id_)] = {
            "obj": obj,
            "light_objs": [],
            "atmo_id": 0,
            "external_id": 0,
        }

        # 在属性面板显示ID
        obj[f"AG - Sector ID"] = id_

        # 指定大气
        self.atmo_id = scene_data.defaults.atmo_id

        # self.ambient_light.color = scene_data.defaults.ambient_light.color
        # self.ambient_light.vector = scene_data.defaults.ambient_light.vector

        # 指定外部光
        self.external_id = scene_data.defaults.external_id

        # self.flat_light.color = scene_data.defaults.flat_light.color

        # 添加网格属性
        mesh.attributes.new(name="tex_id", type="INT", domain="FACE")
        mesh.attributes.new(name="tex_pos", type="FLOAT2", domain="FACE")
        mesh.attributes.new(name="tex_rotate", type="FLOAT", domain="FACE")
        mesh.attributes.new(name="tex_scale", type="FLOAT2", domain="FACE")

        # 指定材质
        for face in mesh.polygons:  # polygons 代表面
            face_index = face.index  # 面的索引
            face_normal = face.normal  # 面的法线方向（Vector）

            # 判断地板和天花板
            dp = face_normal.dot(Vector((0, 0, 1)))
            if dp > 0.999:  # 地板
                tex_id = scene_data.defaults["Textures"]["Floor"]["id"]
            elif dp < -0.999:  # 天花板
                tex_id = scene_data.defaults["Textures"]["Ceiling"]["id"]
            else:  # 墙壁
                tex_id = scene_data.defaults["Textures"]["Wall"]["id"]
            mesh.attributes["tex_id"].data[face_index].value = tex_id  # type: ignore
            mat = None
            tex = get_texture_by_id(tex_id)[1]
            if tex:
                mat = tex.amagate_data.mat_obj
            if mat:
                self.set_matslot(mat, [face_index])
            else:
                pass

        name = f"Sector{self.id}"
        obj.rename(name, mode="ALWAYS")
        obj.data.rename(name, mode="ALWAYS")
        coll = ensure_collection(S_COLL)
        if coll not in obj.users_collection:
            # 清除集合
            obj.users_collection[0].objects.unlink(obj)
            # 链接到集合
            link2coll(obj, coll)


# 图像属性
class ImageProperty(bpy.types.PropertyGroup):
    id: IntProperty(name="ID", default=0)  # type: ignore
    mat_obj: PointerProperty(type=bpy.types.Material)  # type: ignore


# 场景属性
class SceneProperty(bpy.types.PropertyGroup):
    is_blade: BoolProperty(name="", default=False, description="If checked, it means this is a Blade scene")  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore

    # sectors: CollectionProperty(type=SectorCollection)  # type: ignore
    # amagate_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore
    # sector_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore
    # ghostsector_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore
    # entity_coll: PointerProperty(type=bpy.types.Collection)  # type: ignore

    atmospheres: CollectionProperty(type=AtmosphereProperty)  # type: ignore
    active_atmosphere: IntProperty(name="Atmosphere", default=0)  # type: ignore

    # 外部光
    externals: CollectionProperty(type=ExternalLightProperty)  # type: ignore
    active_external: IntProperty(name="External Light", default=0)  # type: ignore

    active_texture: IntProperty(name="Texture", default=0, set=lambda self, value: self.set_active_texture(value), get=lambda self: self.get_active_texture())  # type: ignore

    defaults: PointerProperty(type=SectorProperty)  # type: ignore # 扇区默认属性

    # 布局属性
    default_tex: CollectionProperty(type=TextureProperty)  # type: ignore
    sector_tex: PointerProperty(type=TextureProperty)  # type: ignore
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
        self["SectorManage"] = {"deleted_id_count": 0, "max_id": 0, "sectors": {}}
        defaults = self.defaults

        defaults.as_default = True
        defaults.atmo_id = 1
        defaults.external_id = 1
        defaults["Textures"] = {
            "Floor": {"id": 0, "pos": (0.0, 0.0), "zoom": (10.0, 10.0), "angle": 0.0},
            "Ceiling": {"id": 0, "pos": (0.0, 0.0), "zoom": (10.0, 10.0), "angle": 0.0},
            "Wall": {"id": 0, "pos": (0.0, 0.0), "zoom": (10.0, 10.0), "angle": -90.0},
        }

        ############################
        for i in ("Floor", "Ceiling", "Wall"):
            prop = self.default_tex.add()
            prop.target = i


# 物体属性
class ObjectProperty(bpy.types.PropertyGroup):
    SectorData: CollectionProperty(type=SectorProperty)  # type: ignore

    def get_sector_data(self) -> SectorProperty:
        if len(self.SectorData) == 0:
            return None  # type: ignore
        return self.SectorData[0]

    def set_sector_data(self):
        if not self.SectorData:
            self.SectorData.add()
            # return self.SectorData[0]


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
    addon_directory = os.path.dirname(__file__)

    import bpy.utils.previews

    ICONS = bpy.utils.previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    ICONS.load("star", os.path.join(icons_dir, "star.png"), "IMAGE")
    ICONS.load("blade", os.path.join(icons_dir, "blade.png"), "IMAGE")

    bpy.utils.register_class(AmagatePreferences)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.amagate_data = PointerProperty(type=ObjectProperty, name="Amagate Data")  # type: ignore
    bpy.types.Scene.amagate_data = PointerProperty(type=SceneProperty, name="Amagate Data")  # type: ignore
    bpy.types.Image.amagate_data = PointerProperty(type=ImageProperty, name="Amagate Data")  # type: ignore

    # 注册保存前回调函数
    # bpy.app.handlers.save_pre.append(check_before_save)


def unregister():
    global ICONS
    del bpy.types.Object.amagate_data  # type: ignore
    del bpy.types.Scene.amagate_data  # type: ignore
    del bpy.types.Image.amagate_data  # type: ignore

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.utils.unregister_class(AmagatePreferences)

    bpy.utils.previews.remove(ICONS)
    ICONS = None

    # bpy.app.handlers.save_pre.remove(check_before_save)
