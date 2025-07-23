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
import locale
import requests
import tempfile
import json
import zlib
from pathlib import Path
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
from ..service import ag_service, protocol


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection


############################

epsilon: float = ag_utils.epsilon
epsilon2: float = ag_utils.epsilon2
logger = data.logger

# 面纹理属性储存
FACE_PROPS = {
    "amagate_flat_light": ["int", 0],
    "amagate_tex_id": ["int", 1],
    "amagate_tex_xpos": ["float", 0.0],
    "amagate_tex_ypos": ["float", 0.0],
    "amagate_tex_angle": ["float", 0.0],
    "amagate_tex_xzoom": ["float", 20],
    "amagate_tex_yzoom": ["float", 20],
}

############################
############################ 场景面板 -> 属性面板
############################


# class OT_Scene_Props_HUD(bpy.types.Operator):
#     bl_idname = "amagate.scene_props_hud"
#     bl_label = "Show HUD"
#     bl_options = {"INTERNAL"}

#     def execute(self, context: Context):
#         scene_data = context.scene.amagate_data
#         area_index = next(
#             i for i, a in enumerate(context.screen.areas) if a == context.area
#         )
#         item_index = scene_data.areas_show_hud.find(str(area_index))
#         # print(f"item_index: {item_index}")
#         if item_index != -1:
#             scene_data.areas_show_hud.remove(item_index)
#         else:
#             scene_data.areas_show_hud.add().value = area_index
#         data.region_redraw("WINDOW")
#         return {"FINISHED"}


############################
############################ 场景面板 -> 大气面板
############################
class OT_Scene_Atmo_Add(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_add"
    bl_label = "Add Atmosphere"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        self.add(context, self.undo)
        return {"FINISHED"}

    @staticmethod
    def add(context: Context, undo=False):
        # type: (bpy.types.Context, bool) -> L3D_data.AtmosphereProperty
        scene_data = context.scene.amagate_data

        # 获取可用 ID
        used_ids = tuple(int(i) for i in scene_data.atmospheres.keys())
        id_ = data.get_id(used_ids)
        # 获取可用名称
        used_names = tuple(a.item_name for a in scene_data.atmospheres)
        name = data.get_name(used_names, "atmo{}", id_)

        item = scene_data.atmospheres.add()
        item.name = f"{id_}"
        item["_item_name"] = name
        item["_color"] = (0.0, 0.0, 0.0, 0.002)

        # item.ensure_obj(scene)

        scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        if undo:
            bpy.ops.ed.undo_push(message="Add Atmosphere")

        return item


class OT_Scene_Atmo_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_remove"
    bl_label = "Remove Atmosphere"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        active_atmo = scene_data.active_atmosphere
        if active_atmo >= len(scene_data.atmospheres):
            return {"CANCELLED"}

        atmo = scene_data.atmospheres[active_atmo]
        # 不能删除默认大气
        if atmo.id == scene_data.defaults.atmo_id:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Cannot remove default atmosphere')}",
            )
            return {"CANCELLED"}

        # 不能删除正在使用的大气
        # if next((i for i in atmo.users_obj if i.obj), None):
        if len(atmo.users_obj) > 0:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Atmosphere is used by sectors')}",
            )
            return {"CANCELLED"}

        # bpy.data.objects.remove(atmo.obj)
        id_key = atmo.name
        scene_data.atmospheres.remove(active_atmo)
        if scene_data.atmo_id_key == id_key:
            scene_data.atmo_id_key = scene_data.atmospheres[0].name

        if active_atmo >= len(scene_data.atmospheres):
            scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        if self.undo:
            bpy.ops.ed.undo_push(message="Remove Atmosphere")
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Scene_Atmo_Default(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_default"
    bl_label = "Set as default atmosphere"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        active_atmo = scene_data.active_atmosphere
        if active_atmo >= len(scene_data.atmospheres):
            return {"CANCELLED"}

        scene_data.defaults.atmo_id = scene_data.atmospheres[active_atmo].id
        if self.undo:
            bpy.ops.ed.undo_push(message="Set as default atmosphere")
        return {"FINISHED"}


class OT_Atmo_Select(bpy.types.Operator):
    bl_idname = "amagate.atmo_select"
    bl_label = "Select Atmosphere"
    bl_description = "Select Atmosphere"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=L3D_data.Atmo_Select)  # type: ignore

    def draw(self, context: Context):
        scene_data = context.scene.amagate_data
        layout = self.layout
        col = layout.column()

        col.template_list(
            "AMAGATE_UI_UL_AtmoList",
            "atmosphere_list",
            scene_data,
            "atmospheres",
            self.prop,
            "index",
            maxrows=14,
        )

    def execute(self, context):
        # print(f"{self.__class__.__name__}.execute")
        # self.report({"INFO"}, "execute")
        # ag_utils.simulate_keypress(27)
        # bpy.context.window.cursor_warp(10,10)

        # move_back = lambda: bpy.context.window.cursor_warp(self.mouse[0], self.mouse[1])
        # bpy.app.timers.register(move_back, first_interval=0.01)
        return {"FINISHED"}

    def invoke(self, context, event):
        # self.mouse = event.mouse_x, event.mouse_y
        # print(self.mouse)
        return context.window_manager.invoke_popup(self, width=200)  # type: ignore


############################
############################ 场景面板 -> 外部光面板
############################
class OT_Scene_External_Add(bpy.types.Operator):
    bl_idname = "amagate.scene_external_add"
    bl_label = "Add External Light"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        self.add(context, self.undo)
        return {"FINISHED"}

    @staticmethod
    def add(context: Context, undo=False):
        scene_data = context.scene.amagate_data

        # 获取可用 ID
        used_ids = tuple(int(i) for i in scene_data.externals.keys())
        id_ = data.get_id(used_ids)
        # 获取可用名称
        used_names = tuple(a.item_name for a in scene_data.externals)

        item = scene_data.externals.add()
        item.name = f"{id_}"
        item["_item_name"] = data.get_name(used_names, "Sun{}", id_)
        item["_color"] = (0.784, 0.7, 0.22)
        item["_vector"] = (-1, 0, -1)
        item.update_obj()

        scene_data.active_external = len(scene_data.externals) - 1
        if undo:
            bpy.ops.ed.undo_push(message="Add External Light")
        return item


class OT_Scene_External_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_external_remove"
    bl_label = "Remove External Light"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        active_idx = scene_data.active_external
        externals = scene_data.externals
        if active_idx >= len(externals):
            return {"CANCELLED"}

        item = externals[active_idx]
        # 不能删除默认外部光
        if item.id == scene_data.defaults.external_id:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Cannot remove default external light')}",
            )
            return {"CANCELLED"}

        # 不能删除正在使用的外部光
        # if next((i for i in item.users_obj if i.obj), None):
        if len(item.users_obj) > 0:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('External light is used by objects')}",
            )
            return {"CANCELLED"}

        bpy.data.lights.remove(item.data)
        externals.remove(active_idx)

        if active_idx >= len(externals):
            scene_data.active_external = len(externals) - 1
        if self.undo:
            bpy.ops.ed.undo_push(message="Remove External Light")

        return {"FINISHED"}

    def invoke(self, context: Context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Scene_External_Default(bpy.types.Operator):
    bl_idname = "amagate.scene_external_default"
    bl_label = "Set as default external light"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        active_idx = scene_data.active_external
        if active_idx >= len(scene_data.externals):
            return {"CANCELLED"}

        scene_data.defaults.external_id = scene_data.externals[active_idx].id
        if self.undo:
            bpy.ops.ed.undo_push(message="Set as default external light")

        return {"FINISHED"}


class OT_Scene_External_Set(bpy.types.Operator):
    bl_idname = "amagate.scene_external_set"
    bl_label = "Set External Light"
    bl_options = {"INTERNAL"}

    id: IntProperty(name="ID")  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data

        return {"FINISHED"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data
        light = L3D_data.get_external_by_id(scene_data, self.id)[1]
        col = layout.column()
        col.prop(light, "vector", text="", slider=True)
        col.prop(light, "vector2", text="")

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=100)  # type: ignore


class OT_External_Select(bpy.types.Operator):
    bl_idname = "amagate.external_select"
    bl_label = "Select External Light"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=L3D_data.External_Select)  # type: ignore

    def draw(self, context: Context):
        scene_data = context.scene.amagate_data
        layout = self.layout
        col = layout.column()

        col.template_list(
            "AMAGATE_UI_UL_ExternalLight",
            "",
            scene_data,
            "externals",
            self.prop,
            "index",
            maxrows=14,
        )

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=200)  # type: ignore


############################
############################ 纹理面板
############################
class OT_Texture_Add(bpy.types.Operator):
    bl_idname = "amagate.texture_add"
    bl_label = "Add Texture"
    bl_description = "Hold shift to enable overlay"
    bl_options = {"INTERNAL", "UNDO"}

    # 过滤文件
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_image: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    # filter_glob: StringProperty(default="*.jpg;*.png;*.jpeg;*.bmp;*.tga", options={"HIDDEN"})  # type: ignore

    # 相对路径
    relative_path: BoolProperty(name="Relative Path", default=True)  # type: ignore
    # 覆盖模式
    override: BoolProperty(name="Override Mode", default=False)  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    @staticmethod
    def load_image(filepath, name=""):
        img = bpy.data.images.load(filepath)  # type: Image # type: ignore
        img_data = img.amagate_data
        img.preview_ensure()
        if name:
            img.name = name
        else:
            img.name = os.path.splitext(os.path.basename(filepath))[0]

        used_ids = tuple(i.amagate_data.id for i in bpy.data.images)  # type: ignore
        img_data.id = data.get_id(used_ids)
        L3D_data.ensure_material(img)
        if not img.use_fake_user:
            img.use_fake_user = True

        return img_data

    def execute(self, context: Context):
        scene_data = bpy.context.scene.amagate_data
        curr_dir = bpy.path.abspath("//")
        # 相同驱动器
        same_drive = (
            os.path.splitdrive(self.directory)[0] == os.path.splitdrive(curr_dir)[0]
        )
        files = [
            f.name
            for f in self.files
            if f.name
            and os.path.exists(
                os.path.join(self.directory, f.name)
                and f.name.lower().endswith(data.IMAGE_FILTER)
            )
        ]
        if not files:
            files = [
                f
                for f in os.listdir(self.directory)
                if f.lower().endswith(data.IMAGE_FILTER)
            ]

        for file in files:
            name = os.path.splitext(file)[0]
            if name.lower() == L3D_data.ensure_null_texture().name.lower():
                # 忽略与特殊纹理同名的纹理
                self.report(
                    {"WARNING"},
                    f"{pgettext('Warning')}: {pgettext('Ignore textures with the same name as the special texture')}",
                )
                continue

            filepath = os.path.join(self.directory, file)
            if same_drive and self.relative_path:
                filepath = f"//{os.path.relpath(filepath, curr_dir)}"

            img = bpy.data.images.get(name)  # type: Image # type: ignore
            if img:
                if self.override:
                    img.filepath = filepath
                    img.reload()
                    if not img.amagate_data.id:  # type: ignore
                        used_ids = tuple(i.amagate_data.id for i in bpy.data.images)  # type: ignore
                        img.amagate_data.id = data.get_id(used_ids)  # type: ignore
                        L3D_data.ensure_material(img)
                        if not img.use_fake_user:
                            img.use_fake_user = True
            else:
                self.load_image(filepath, name)
        return {"FINISHED"}

    def invoke(self, context, event):
        self.override = event.shift
        # 设为上次选择目录，文件名为空
        self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class OT_Texture_Remove(bpy.types.Operator):
    bl_idname = "amagate.texture_remove"
    bl_label = "Remove Texture"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        idx = scene_data.active_texture

        if idx >= len(bpy.data.images):
            return {"CANCELLED"}

        img: Image = bpy.data.images[idx]
        img_data = img.amagate_data

        # 不能删除没有ID的纹理或特殊纹理
        if not img_data.id or img == scene_data.ensure_null_tex:
            if img == scene_data.ensure_null_tex:
                self.report(
                    {"WARNING"},
                    f"{pgettext('Warning')}: {pgettext('Cannot remove special texture')}",
                )
            return {"CANCELLED"}

        # 不能删除正在使用的纹理
        mat = img_data.mat_obj  # type: bpy.types.Material
        if mat and mat.users - mat.use_fake_user > 1:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Texture is used by sectors')}",
            )
            return {"CANCELLED"}

        # 不能删除默认纹理
        has_default = next(
            (True for i in scene_data.defaults.textures if i.id == img_data.id),
            None,
        )
        if has_default:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Cannot remove default texture')}",
            )
            return {"CANCELLED"}

        # 删除纹理
        bpy.data.images.remove(img)
        if mat:
            bpy.data.materials.remove(mat)
        # 更新索引
        new_idx = next((i for i in range(idx, len(bpy.data.images)) if bpy.data.images[i].amagate_data.id != 0), None)  # type: ignore
        if new_idx is None:
            new_idx = next(i for i in range(idx - 1, -1, -1) if bpy.data.images[i].amagate_data.id != 0)  # type: ignore
        scene_data.active_texture = new_idx

        return {"FINISHED"}

    def invoke(self, context: Context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class Texture_Default_Prop(bpy.types.PropertyGroup):
    img_id: IntProperty()  # type: ignore
    floor: BoolProperty(get=lambda self: self.get_default("Floor"), set=lambda self, value: self.set_default(value, "Floor"))  # type: ignore
    ceiling: BoolProperty(get=lambda self: self.get_default("Ceiling"), set=lambda self, value: self.set_default(value, "Ceiling"))  # type: ignore
    wall: BoolProperty(get=lambda self: self.get_default("Wall"), set=lambda self, value: self.set_default(value, "Wall"))  # type: ignore

    def get_default(self, name):
        return self[name]

    def set_default(self, value, name):
        scene_data = bpy.context.scene.amagate_data
        if value:
            scene_data.defaults.textures[name].id = self.img_id
            data.region_redraw("UI")
            bpy.ops.ed.undo_push(message="Set as default texture")
        self[name] = True

    def init(self, context: Context):
        scene_data = context.scene.amagate_data
        idx = scene_data.active_texture

        if idx >= len(bpy.data.images):
            return {"CANCELLED"}

        img: Image = bpy.data.images[idx]
        img_data = img.amagate_data
        img_id = img_data.id

        if not img_id:
            return {"CANCELLED"}

        self.img_id = img_id
        for name in ("Floor", "Ceiling", "Wall"):
            self[name] = scene_data.defaults.textures[name].id == img_id


class OT_Texture_Default(bpy.types.Operator):
    bl_idname = "amagate.texture_default"
    bl_label = "Set as default texture"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=Texture_Default_Prop)  # type: ignore

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self.prop, "floor", text="Floor", text_ctxt="Property", toggle=True)
        col.prop(
            self.prop, "ceiling", text="Ceiling", text_ctxt="Property", toggle=True
        )
        col.prop(self.prop, "wall", text="Wall", text_ctxt="Property", toggle=True)

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        self.prop.init(context)
        return context.window_manager.invoke_popup(self, width=100)


class OT_Texture_Reload(bpy.types.Operator):
    bl_idname = "amagate.texture_reload"
    bl_label = "Reload Texture"
    bl_description = "Hold shift to reload all texture"
    bl_options = {"INTERNAL"}

    # reload_all: BoolProperty(name="Reload All", default=False)  # type: ignore

    @staticmethod
    def reload_all():
        for img in bpy.data.images:  # type: ignore
            if img.amagate_data.id:
                img.reload()
                img.preview_ensure()
                img.preview.reload()

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        idx = scene_data.active_texture
        if idx >= len(bpy.data.images):
            return {"CANCELLED"}

        img: Image = bpy.data.images[idx]
        if img and img.amagate_data.id:
            img.reload()
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        if event.shift:
            self.reload_all()
            return {"FINISHED"}
        return self.execute(context)


class Texture_Package_Prop(bpy.types.PropertyGroup):
    pack_all: BoolProperty(default=False, update=lambda self, context: self.update(context, "Pack All"))  # type: ignore
    unpack_all: BoolProperty(default=False, update=lambda self, context: self.update(context, "Unpack All"))  # type: ignore

    def update(self, context: Context, selected):
        scene_data = context.scene.amagate_data
        # 如果未打开blend文件，则使用原始路径
        m = "USE_LOCAL" if bpy.data.filepath else "USE_ORIGINAL"
        # selected = self.items[self.index].name
        for img in bpy.data.images:
            if img.amagate_data.id and img != scene_data.ensure_null_tex:  # type: ignore
                if selected == "Pack All":
                    if not img.packed_file:
                        img.pack()
                else:
                    if img.packed_file:
                        img.unpack(method=m)
        message = "Pack All" if selected == "Pack All" else "Unpack All"
        bpy.ops.ed.undo_push(message=message)
        # XXX 也许不起作用
        ag_utils.simulate_keypress(27)


class OT_Texture_Package(bpy.types.Operator):
    bl_idname = "amagate.texture_package"
    bl_label = "Pack/Unpack Texture"
    bl_description = "Hold shift to pack/unpack all textures"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=Texture_Package_Prop)  # type: ignore
    ############################

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self.prop, "pack_all", text="Pack All", toggle=True)
        col.prop(self.prop, "unpack_all", text="Unpack All", toggle=True)
        # row.template_list(
        #     "AMAGATE_UI_UL_StrList", "", self.prop, "items", self.prop, "index", rows=2
        # )

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        m = "USE_LOCAL" if bpy.data.filepath else "USE_ORIGINAL"
        idx = scene_data.active_texture
        if idx >= len(bpy.data.images):
            return {"CANCELLED"}

        img: Image = bpy.data.images[idx]
        if img and img.amagate_data.id and img != scene_data.ensure_null_tex:
            if img.packed_file:
                img.unpack(method=m)
                bpy.ops.ed.undo_push(message="Unpack Texture")
            else:
                img.pack()
                bpy.ops.ed.undo_push(message="Pack Texture")
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        if event.shift:
            return context.window_manager.invoke_popup(self, width=100)  # type: ignore
        return self.execute(context)


class OT_Texture_Select(bpy.types.Operator):
    bl_idname = "amagate.texture_select"
    bl_label = "Select Texture"
    bl_description = "Select NULL for sky"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=L3D_data.Texture_Select)  # type: ignore

    # @classmethod
    # def description(cls, context, properties):
    #     # 根据上下文或属性动态返回描述
    #     if properties.prop.target == "Sector":  # type: ignore
    #         # 选择NULL表示天空
    #         return pgettext("Select NULL for sky")
    #     return ""

    def draw(self, context: Context):
        scene_data = context.scene.amagate_data
        layout = self.layout
        col = layout.column()

        col.template_list(
            "AMAGATE_UI_UL_TextureList",
            "texture_list",
            bpy.data,
            "images",
            self.prop,
            "index",
            maxrows=14,
        )

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=200)  # type: ignore

    # XXX
    # def check(self, context: Context):
    #     return True


class OT_Texture_Preview(bpy.types.Operator):
    bl_idname = "amagate.texture_preview"
    bl_label = "Click to preview texture"
    # bl_description = "Click to preview texture"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=0)  # type: ignore

    @classmethod
    def description(cls, context, properties: OT_Texture_Preview):
        tex = bpy.data.images[properties.index]  # type: Image
        tex_data = tex.amagate_data
        if tex_data.mat_obj:
            return tex_data.mat_obj.name
        else:
            return ""

    def draw(self, context: Context):
        layout = self.layout
        row = layout.row()
        scene_data = context.scene.amagate_data
        # row.scale_y = 2
        row.template_ID_preview(scene_data, "tex_preview", hide_buttons=True)

    def execute(self, context: Context):
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        scene_data = context.scene.amagate_data
        tex = bpy.data.images[self.index]  # type: Image
        scene_data.tex_preview = tex

        return context.window_manager.invoke_popup(self, width=130)


# 打开全景图
class OT_SkyTexture_Open(bpy.types.Operator):
    bl_idname = "amagate.sky_texture_open"
    bl_label = "Open Panorama"
    bl_description = "Open panorama"
    bl_options = {"INTERNAL"}

    # 过滤文件
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_image: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore

    # 相对路径
    relative_path: BoolProperty(name="Relative Path", default=True)  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    def execute(self, context: Context):
        if not self.filepath.lower().endswith(data.IMAGE_FILTER):
            self.report({"ERROR"}, "No valid files selected")
            return {"CANCELLED"}

        curr_dir = bpy.path.abspath("//")
        # 相同驱动器
        same_drive = (
            os.path.splitdrive(self.directory)[0] == os.path.splitdrive(curr_dir)[0]
        )

        filepath = self.filepath
        # if same_drive and self.relative_path:
        #     filepath = f"//{os.path.relpath(filepath, curr_dir)}"
        img = L3D_data.ensure_null_texture()
        img.filepath = filepath
        img.reload()

        return {"FINISHED"}

    def invoke(self, context, event):
        # 设为上次选择目录，文件名为空
        self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# 下载全景图
class OT_SkyTexture_Download(bpy.types.Operator):
    bl_idname = "amagate.sky_texture_download"
    bl_label = "Download"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        if not context.preferences.system.use_online_access:
            self.report(
                {"ERROR"}, "Please enable online access in Preferences -> System"
            )
            return {"CANCELLED"}

        L3D_data.PANORAMA_LOCK.acquire()

        logger.info("Downloading panorama...")
        threading.Thread(target=self.download, args=()).start()

        return {"FINISHED"}

    @staticmethod
    def download():
        # if 0:
        #     direct_link = "https://q1080.webgetstore.com/2025/06/10/393cfc9cd5028772feff983c07c731c9.zip?sg=dd92aef7c869afc3f76e7445ee4be3c5&e=6847c748&fileName=panorama.zip"
        #     referer = "https://www.lanzoul.com/"
        # 中文系统的情况
        if locale.setlocale(locale.LC_ALL, "").startswith("Chinese"):
            link = "https://astra.lanzoul.com/iGctt2ygneni"
            name = "panorama.zip"
            api = (
                f"https://cn.apihz.cn/api/ziyuan/lanzou.php?id=88888888&key=88888888&url={link}&type=1",
                f"https://api.nxvav.cn/api/lanzou/?type=json&url={link}",
                f"https://api.mmp.cc/api/lanzou?type=json&url={link}",
            )

            for url in api:
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    response_json = response.json()
                    if response_json.get("name") != name:
                        continue

                    direct_link = next(
                        (
                            response_json[k]
                            for k in ("downurl", "downUrl")
                            if k in response_json
                        ),
                        None,
                    )
                    if direct_link:
                        # logger.debug(f"api: {url}, direct_link: {direct_link}")
                        referer = "https://www.lanzoul.com/"
                        break
                except Exception as e:
                    continue
            # 如果没有发生break，说明没有解析到直链
            else:
                direct_link = (
                    "https://gitee.com/sryml/file-hosting/raw/main/panorama.zip"
                )
                referer = "https://gitee.com/"
        else:
            direct_link = (
                "https://github.com/sryml9/FileHosting/raw/refs/heads/main/panorama.zip"
            )
            referer = "https://github.com/"

        with tempfile.NamedTemporaryFile(
            mode="wb+",
            suffix=".zip",
            delete=True,
            dir=os.path.join(data.ADDON_PATH, "textures/panorama"),
        ) as save_file:
            # logger.debug(f"tempfile: {save_file.name}")
            down_result = ag_utils.download_file(direct_link, save_file, referer)
            if down_result:
                save_file.flush()
                extract_result = ag_utils.extract_file(
                    save_file, os.path.join(data.ADDON_PATH, "textures/panorama")
                )
                if extract_result:
                    logger.info("Panorama downloaded and extracted")
        #
        L3D_data.PANORAMA_LOCK.release()


############################
############################ 扇区工具
############################


# 多线段路径
class OT_PolyPath(bpy.types.Operator):
    bl_idname = "amagate.poly_path"
    bl_label = "Poly Path"
    bl_description = "Create polyline path"

    def execute(self, context: Context):
        if "EDIT" in context.mode:
            bpy.ops.object.mode_set(mode="OBJECT")  # 物体模式

        curve_data = bpy.data.curves.new(
            "PolyPath", type="CURVE"
        )  # type: bpy.types.Curve
        curve_data.dimensions = "2D"
        curve_data.splines.new("POLY")

        curve = bpy.data.objects.new(
            "PolyPath", curve_data
        )  # type: Object # type: ignore
        data.link2coll(curve, context.scene.collection)
        ag_utils.select_active(context, curve)  # 单选并设为活跃

        # 移动到当前视图焦点
        rv3d = context.region_data
        curve.location = rv3d.view_location.to_tuple(0)
        # rv3d.view_distance = 10

        bpy.ops.object.mode_set(mode="EDIT")  # 编辑模式

        return {"FINISHED"}


# 选择连接的扇区
class OT_SelectConnected(bpy.types.Operator):
    bl_idname = "amagate.select_conn_sec"
    bl_label = "Select Connected"
    bl_description = ""
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context: Context):
        return (
            context.scene.amagate_data.is_blade
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
        )

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        selected_sectors = L3D_data.SELECTED_SECTORS.copy()

        for sec in selected_sectors:
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            for d in mesh.attributes["amagate_connected"].data:  # type: ignore
                conn_sid = d.value
                if conn_sid != 0:
                    conn_sec = scene_data["SectorManage"]["sectors"][str(conn_sid)][
                        "obj"
                    ]
                    conn_sec.select_set(True)

        return {"FINISHED"}


# 复制面纹理设置
class OT_CopyFaceTexture(bpy.types.Operator):
    bl_idname = "amagate.copy_face_texture"
    bl_label = "Copy Settings"
    bl_description = ""
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context: Context):
        return (
            context.scene.amagate_data.is_blade
            and context.area.type == "VIEW_3D"
            and context.mode == "EDIT_MESH"
        )

    def execute(self, context: Context):
        global FACE_PROPS
        selected_faces = L3D_data.SELECTED_FACES
        if not selected_faces:
            self.report({"WARNING"}, "No face selected")
            return {"CANCELLED"}

        item = selected_faces[0]
        bm = item[0]
        face = item[1][0]
        for k, v in FACE_PROPS.items():
            layer = getattr(bm.faces.layers, v[0])[k]
            v[1] = face[layer]

        return {"FINISHED"}


# 粘贴面纹理设置
class OT_PasteFaceTexture(bpy.types.Operator):
    bl_idname = "amagate.paste_face_texture"
    bl_label = "Paste Settings"
    bl_description = ""
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context: Context):
        return (
            context.scene.amagate_data.is_blade
            and context.area.type == "VIEW_3D"
            and context.mode == "EDIT_MESH"
        )

    def execute(self, context: Context):
        global FACE_PROPS
        selected_faces = L3D_data.SELECTED_FACES
        if not selected_faces:
            self.report({"WARNING"}, "No face selected")
            return {"CANCELLED"}

        tex_id = FACE_PROPS["amagate_tex_id"][1]
        idx, img = L3D_data.get_texture_by_id(tex_id)
        if img is None:
            self.report({"ERROR"}, "No texture found")
            return {"CANCELLED"}

        mat = L3D_data.ensure_material(img)
        for item in selected_faces:
            bm = item[0]
            sec = item[2]
            sec_data = sec.amagate_data.get_sector_data()
            faces = item[1]
            for face in faces:
                for k, v in FACE_PROPS.items():
                    layer = getattr(bm.faces.layers, v[0])[k]
                    face[layer] = v[1]
            sec_data.set_matslot(mat, faces, bm)
            sec.update_tag()
        #
        data.area_redraw("VIEW_3D")

        return {"FINISHED"}


############################
############################ 预制体面板
############################


# 实体搜索
class OT_Entity_Search(bpy.types.Operator):
    bl_idname = "amagate.entity_search"
    bl_label = "Search"
    bl_description = ""
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    enum: EnumProperty(
        translation_context="Entity",
        items=data.get_ent_enum2,
        update=lambda self, context: self.update_ent_enum(context),
    )  # type: ignore

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        wm_data.ent_enum = self.enum
        data.region_redraw("UI")
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        context.window_manager.invoke_search_popup(self)
        return {"FINISHED"}

    ############################
    def update_ent_enum(self, context: Context):
        data.WindowManagerProperty.update_ent_enum(context)


# 实体枚举
class OT_Entity_Enum(bpy.types.Operator):
    bl_idname = "amagate.entity_enum"
    bl_label = "Entity Enum"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def draw(self, context: Context):
        layout = self.layout
        wm_data = context.window_manager.amagate_data
        scene_data = context.scene.amagate_data
        ent_enum = data.get_ent_enum(None, None)
        row = layout.row(align=False)
        for item in ent_enum:
            if item[0] == "":
                col = row.column(align=True, heading=item[1], heading_ctxt="Entity")
            else:
                col.prop_enum(wm_data, "ent_enum", item[0])
        # grid = layout.grid_flow(row_major=False, columns=8)
        # grid.prop_tabs_enum(wm_data, "ent_enum",property_highlight=wm_data.ent_enum)

    def execute(self, context: Context):
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        return context.window_manager.invoke_popup(self, width=900)
        # return {"FINISHED"}


# 添加到场景
class OT_EntityAddToScene(bpy.types.Operator):
    bl_idname = "amagate.entity_add_to_scene"
    bl_label = "Add to Scene"
    bl_description = "Add to Scene"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        return context.scene.amagate_data.is_blade

    def execute(self, context: Context):
        from . import entity_operator as OP_ENTITY

        E_MANIFEST = data.E_MANIFEST
        wm_data = context.window_manager.amagate_data
        value = wm_data.ent_enum
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "ent_enum", value
        )
        #
        filepath = ""
        for cat in E_MANIFEST["Entities"]:
            item = E_MANIFEST["Entities"][cat].get(inter_name)
            if item:
                filepath = os.path.join(data.ADDON_PATH, "Models", item[1])
                break
        #
        if not (filepath and os.path.exists(filepath)):
            self.report({"ERROR"}, f"{pgettext('File not found')}: {item[1]}")
            return {"CANCELLED"}

        coll_name = f"Blade_Object_{inter_name}"
        coll = bpy.data.collections.get(coll_name)
        if coll is None:
            with bpy.data.libraries.load(filepath, link=True) as (data_from, data_to):
                from_coll = next(
                    (i for i in data_from.collections if i == coll_name), None
                )
                if not from_coll:
                    self.report({"ERROR"}, "Entity collection not found")
                    return {"CANCELLED"}

                data_to.collections = [coll_name]
            coll = bpy.data.collections.get(coll_name)

        ent_coll, entity_raw = OP_ENTITY.get_ent_data(coll, check_visible=False)
        if entity_raw is None:
            self.report({"ERROR"}, "No visible entity Mesh")
            return {"CANCELLED"}
        #
        scene_data = context.scene.amagate_data
        obj_name = self.get_name(context, f"{inter_name}_")
        entity = bpy.data.objects.new(
            obj_name, entity_raw.data
        )  # type: Object # type: ignore
        data.link2coll(entity, L3D_data.ensure_collection(L3D_data.E_COLL))
        entity.amagate_data.set_entity_data()
        ent_data = entity.amagate_data.get_entity_data()
        scene_data["EntityManage"][obj_name] = entity
        # 移动到当前视图焦点
        rv3d = context.region_data
        entity.location = rv3d.view_location.to_tuple(0)
        #
        ent_data.Name = obj_name
        ent_data.Kind = inter_name

        return {"FINISHED"}

    @staticmethod
    def get_name(context: Context, prefix: str, start_id=1):
        scene_data = context.scene.amagate_data
        while scene_data["EntityManage"].get(f"{prefix}{start_id}"):
            start_id += 1
        return f"{prefix}{start_id}"


# 从场景移除
# class OT_EntityRemoveFromScene(bpy.types.Operator):
#     bl_idname = "amagate.entity_remove_from_scene"
#     bl_label = "Remove from Scene"
#     bl_description = "Remove from Scene"
#     bl_options = {"INTERNAL"}

#     @classmethod
#     def poll(cls, context: Context):
#         return context.scene.amagate_data.is_blade

#     def execute(self, context: Context):
#         return {"FINISHED"}


# 打开预制体文件
class OT_OpenPrefab(bpy.types.Operator):
    bl_idname = "amagate.open_prefab"
    bl_label = "Open File"
    bl_description = ""
    bl_options = {"INTERNAL"}

    action: IntProperty(default=0)  # type: ignore

    @staticmethod
    def set_ent_enum(ent_enum, cat, prefab_type):
        context = bpy.context
        wm_data = context.window_manager.amagate_data
        wm_data.ent_enum = ent_enum
        if cat == "Custom":
            wm_data.prefab_type = prefab_type

    def execute(self, context: Context):
        E_MANIFEST = data.E_MANIFEST
        wm_data = context.window_manager.amagate_data
        ent_enum = wm_data.ent_enum
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "ent_enum", ent_enum
        )
        for cat in E_MANIFEST["Entities"]:
            item = E_MANIFEST["Entities"][cat].get(inter_name)
            if item:
                filepath = os.path.join(data.ADDON_PATH, "Models", item[1])
                if os.path.exists(filepath):
                    L3D_data.LOAD_POST_CALLBACK = (
                        self.set_ent_enum,
                        (ent_enum, cat, str(item[2])),
                    )
                    bpy.ops.wm.open_mainfile(filepath=filepath)
                else:
                    self.report({"ERROR"}, f"{pgettext('File not found')}: {item[1]}")

                break

        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        if self.action == 0:
            if bpy.data.is_dirty:
                return context.window_manager.invoke_popup(self, width=300)
        elif self.action == 1:  # Save
            ag_utils.simulate_keypress(27)
            ret = bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")  # type: ignore
            if ret != {"FINISHED"}:
                return ret
        elif self.action == 2:  # Don't Save
            pass
        elif self.action == 3:  # Cancel
            ag_utils.simulate_keypress(27)
            return {"CANCELLED"}

        return self.execute(context)

    def draw(self, context: Context):
        layout = self.layout

        layout.label(text="Save changes before closing?", icon="QUESTION")
        layout.separator(type="LINE")

        row = layout.row()
        op = row.operator(OT_OpenPrefab.bl_idname, text="Save").action = 1  # type: ignore
        row.operator(OT_OpenPrefab.bl_idname, text="Don't Save").action = 2  # type: ignore
        row.operator(OT_OpenPrefab.bl_idname, text="Cancel").action = 3  # type: ignore


# 设为预制体
class OT_SetAsPrefab(bpy.types.Operator):
    bl_idname = "amagate.set_as_prefab"
    bl_label = "Set as Prefab"
    bl_description = ""
    bl_options = {"INTERNAL"}

    builtin: BoolProperty(default=False)  # type: ignore
    action: EnumProperty(
        name="",
        description="",
        translation_context="AG_Prefab",
        items=[
            ("", "Select Preview View", ""),
            ("1", "Top", ""),
            ("2", "Front", ""),
            ("3", "Front 45°", ""),
            ("4", "Right", ""),
            ("5", "Right 45°", ""),
            ("8", "Bottom", ""),
            ("6", "Back", ""),
            ("7", "Left", ""),
        ],
    )  # type: ignore

    def execute(self, context: Context):
        from . import entity_operator as OP_ENTITY

        scene = context.scene

        # 检查是否为无标题文件
        if not self.builtin and (not bpy.data.filepath or bpy.data.is_dirty):
            self.report({"WARNING"}, "Please save the file first")
            return {"CANCELLED"}

        ent_coll, entity = OP_ENTITY.get_ent_data()
        if entity is None:
            self.report({"WARNING"}, "No visible entity Mesh")
            return {"CANCELLED"}

        inter_name = ent_coll.name[13:]
        models_path = os.path.join(data.ADDON_PATH, "Models")
        preview_dir = os.path.join(models_path, "Preview")
        if self.builtin:
            filename = Path(bpy.data.filepath).stem
        else:
            # 转crc32，避免文件名大小写冲突
            filename = format(
                zlib.crc32(inter_name.encode("utf-8")) & 0xFFFFFFFF, "08x"
            )
        # if Path(models_path, "3DChars", filename).exists() or Path(models_path, "3DObjs", filename).exists():
        #     # 文件名与内置实体相同
        #     self.report({"WARNING"}, "File name is the same as the built-in entity")
        #     return {"CANCELLED"}

        E_MANIFEST = data.E_MANIFEST
        if not self.builtin:
            for cat in E_MANIFEST["Entities"]:
                if cat == "Custom":
                    continue
                # 如果内部名称与内置实体相同，取消操作
                if E_MANIFEST["Entities"][cat].get(inter_name):
                    self.report(
                        {"WARNING"}, "Internal name is the same as the built-in entity"
                    )
                    return {"CANCELLED"}

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        ent_coll.name = f"Blade_Object_{inter_name}"
        wm_data = context.window_manager.amagate_data
        rv3d = context.region_data
        has_armature = next(
            (True for m in entity.modifiers if m.type == "ARMATURE"), False
        )

        # 创建摄像机
        if scene.camera is None:
            camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
            scene.collection.objects.link(camera)
            scene.camera = camera  # 设置活动摄像机

        camera = scene.camera
        rv3d.view_perspective = "CAMERA"
        camera.hide_set(True)
        fov = math.degrees(camera.data.angle)  # type: ignore

        # 计算视图
        view = bpy.types.UILayout.enum_item_name(self, "action", self.action)
        padding = 0.05

        verts = [entity.matrix_world @ Vector(v) for v in entity.bound_box]

        if view == "Top":
            look_at = Vector((0, 0, -1))
            u, v = Vector((1, 0, 0)), Vector((0, 1, 0))
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Front":
            look_at = Vector((0, 1, 0))
            u, v = Vector((1, 0, 0)), Vector((0, 0, 1))
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Front 45°":
            look_at = Vector((0, 1, -1)).normalized()
            u, v = Vector((1, 0, 0)), Vector((0, 1, 1)).normalized()
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Right":
            look_at = Vector((-1, 0, 0))
            u, v = Vector((0, 1, 0)), Vector((0, 0, 1))
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Right 45°":
            look_at = Vector((-1, 0, -1)).normalized()
            u, v = Vector((0, 1, 0)), Vector((-1, 0, 1)).normalized()
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Back":
            look_at = Vector((0, -1, 0))
            u, v = Vector((-1, 0, 0)), Vector((0, 0, 1))
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Left":
            look_at = Vector((1, 0, 0))
            u, v = Vector((0, -1, 0)), Vector((0, 0, 1))
            base_len = min(v.dot(look_at) for v in verts)
        elif view == "Bottom":
            look_at = Vector((0, 0, 1))
            u, v = Vector((1, 0, 0)), Vector((0, -1, 0))
            base_len = min(v.dot(look_at) for v in verts)

        verts = [Vector((vert.dot(u), vert.dot(v))) for vert in verts]
        min_x = min(v.x for v in verts)
        max_x = max(v.x for v in verts)
        min_y = min(v.y for v in verts)
        max_y = max(v.y for v in verts)
        width = max_x - min_x
        height = max_y - min_y
        max_dimension = max(width, height) + padding
        distance = (max_dimension / 2) / math.tan(math.radians(fov / 2))
        x = (min_x + max_x) * 0.5 * u
        y = (min_y + max_y) * 0.5 * v
        z = look_at * (base_len - distance)
        camera.rotation_euler = look_at.to_track_quat("-Z", "Y").to_euler()
        camera.location = x + y + z  # type: ignore

        # 渲染
        context.space_data.shading.type = "MATERIAL"  # type: ignore
        scene.eevee.taa_render_samples = 8
        scene.display.shading.light = "FLAT"
        scene.display.shading.color_type = "TEXTURE"
        if has_armature:
            scene.render.resolution_x = 1024
            scene.render.resolution_y = 1024
        else:
            scene.render.resolution_x = 512
            scene.render.resolution_y = 512
        scene.render.image_settings.file_format = "JPEG"
        scene.render.image_settings.quality = 90

        for mat in bpy.data.materials:
            mat.use_backface_culling = False

        scene.render.filepath = os.path.join(preview_dir, filename)
        bpy.ops.render.render(write_still=True)

        for mat in bpy.data.materials:
            mat.use_backface_culling = True

        # 写入清单列表
        if not self.builtin:
            prefab_name = wm_data.prefab_name.strip()
            prefab_name = prefab_name if prefab_name else inter_name
            E_MANIFEST["Entities"]["Custom"][inter_name] = [
                prefab_name,
                f"Custom\\{filename}.blend",
                int(wm_data.prefab_type),
            ]
            json.dump(
                E_MANIFEST,
                open(os.path.join(models_path, "manifest.json"), "w", encoding="utf-8"),
                indent=4,
                ensure_ascii=False,
                sort_keys=True,
            )

            save_version = context.preferences.filepaths.save_version
            context.preferences.filepaths.save_version = 0
            dest = os.path.join(models_path, "Custom", f"{filename}.blend")
            if Path(bpy.data.filepath) == Path(dest):
                filepath_origin = None
                bpy.ops.wm.save_mainfile()
            else:
                filepath_origin = bpy.data.filepath
                bpy.ops.wm.save_as_mainfile(filepath=dest)
                # shutil.copy(bpy.data.filepath, dest)
            context.preferences.filepaths.save_version = save_version

        # 加载预览
        if data.ENT_PREVIEWS.get(filename):
            data.ENT_PREVIEWS.pop(filename)
        data.ENT_PREVIEWS.load(
            filename,
            os.path.join(preview_dir, f"{filename}.jpg"),
            "IMAGE",
            force_reload=True,
        )
        data.gen_ent_enum()

        if not self.builtin and filepath_origin:
            L3D_data.LOAD_POST_CALLBACK = (self.set_ent_enum, (inter_name,))
            bpy.ops.wm.open_mainfile(filepath=filepath_origin)

        return {"FINISHED"}

    @staticmethod
    def set_ent_enum(value):
        context = bpy.context
        wm_data = context.window_manager.amagate_data
        wm_data.ent_enum = next(i[0] for i in data.ENT_ENUM if i[2] == value)


# 移除预制体
class OT_RemovePrefab(bpy.types.Operator):
    bl_idname = "amagate.remove_prefab"
    bl_label = "Remove Prefab"
    bl_description = "Remove Prefab"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        wm_data = context.window_manager.amagate_data
        E_MANIFEST = data.E_MANIFEST
        models_path = os.path.join(data.ADDON_PATH, "Models")
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "ent_enum", wm_data.ent_enum
        )

        item = E_MANIFEST["Entities"]["Custom"].pop(inter_name)
        json.dump(
            E_MANIFEST,
            open(os.path.join(models_path, "manifest.json"), "w", encoding="utf-8"),
            indent=4,
            ensure_ascii=False,
            sort_keys=True,
        )
        wm_data.ent_enum = "0"
        blend_path = os.path.join(models_path, item[1])
        preview_path = os.path.join(models_path, "Preview", f"{Path(item[1]).stem}.jpg")
        if Path(bpy.data.filepath) == Path(blend_path):
            bpy.ops.wm.read_homefile()
        if os.path.exists(blend_path):
            os.remove(blend_path)
        if os.path.exists(preview_path):
            os.remove(preview_path)
        idx = next((i for i, e in enumerate(data.ENT_ENUM) if e[2] == inter_name), -1)
        if idx != -1:
            data.ENT_ENUM.pop(idx)

        return {"FINISHED"}


############################
############################ 服务器
############################
class OT_Server_Start(bpy.types.Operator):
    bl_idname = "amagate.server_start"
    bl_label = "Start Server"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        ag_service.start_server()
        return {"FINISHED"}


class OT_Server_Stop(bpy.types.Operator):
    bl_idname = "amagate.server_stop"
    bl_label = "Stop Server"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        ag_service.stop_server()
        return {"FINISHED"}


# 对齐摄像机到客户端
class OT_Server_CamToClient(bpy.types.Operator):
    bl_idname = "amagate.server_cam_to_client"
    bl_label = "To Client"
    bl_description = "Align Camera to Client"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        scene = context.scene
        if not scene.camera:
            self.report({"ERROR"}, "No camera found")
            return {"CANCELLED"}

        ag_service.get_attr_send(
            protocol.T_ENTITY,
            "Camera",
            (protocol.A_POSITION, protocol.A_TPOS),
            self.response,
        )
        return {"FINISHED"}

    @staticmethod
    def response(attrs_dict):
        scene = bpy.context.scene
        if not scene.camera:
            return
        #
        cam = scene.camera
        pos = Vector(attrs_dict[protocol.A_POSITION]) / 1000
        pos = Vector((pos[0], pos[2], -pos[1]))
        tpos = Vector(attrs_dict[protocol.A_TPOS]) / 1000
        tpos = Vector((tpos[0], tpos[2], -tpos[1]))
        dir = (tpos - pos).normalized()
        #
        cam.matrix_world.translation = pos
        cam.rotation_euler = dir.to_track_quat("-Z", "Y").to_euler()


# 移动玩家到摄像机
class OT_Server_PlayerToCam(bpy.types.Operator):
    bl_idname = "amagate.server_player_to_cam"
    bl_label = "Player to Camera"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        ag_service.exec_script_send("player_to_camera()")
        return {"FINISHED"}


# 重载地图
class OT_Server_ReloadMap(bpy.types.Operator):
    bl_idname = "amagate.server_reload_map"
    bl_label = "Reload"
    bl_description = "Reload Level"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        ag_service.exec_script_send("reload_map()")
        return {"FINISHED"}


############################
############################ 工具面板
############################


# 新文件
class OT_New(bpy.types.Operator):
    bl_idname = "amagate.new"
    bl_label = "New"
    bl_description = ""
    bl_options = {"INTERNAL"}

    target: StringProperty(default="new")  # type: ignore
    execute_type: IntProperty(default=0)  # type: ignore

    @classmethod
    def description(cls, context, properties):
        if properties.execute_type != 0:  # type: ignore
            return ""
        if properties.target == "new":  # type: ignore
            return pgettext("New Blade Map")
        # elif properties.target == "import":  # type: ignore
        #     return pgettext("Import Blade scene from *.bw file")

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        layout.label(text="Save changes before closing?", icon="QUESTION")
        layout.separator(type="LINE")

        row = layout.row()
        row.operator(OT_New.bl_idname, text="Save").execute_type = 1  # type: ignore
        row.operator(OT_New.bl_idname, text="Don't Save").execute_type = 2  # type: ignore
        row.operator(OT_New.bl_idname, text="Cancel").execute_type = 3  # type: ignore

    # @staticmethod
    # def timer_func(target):
    #     def warp():
    #         operators = {"new": "initmap", "import": ""}
    #         getattr(bpy.ops.amagate, operators[target])()  # type: ignore

    #     return warp

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        if self.execute_type == 0:
            if bpy.data.is_dirty:
                return context.window_manager.invoke_popup(self)
        elif self.execute_type == 1:  # Save
            ag_utils.simulate_keypress(27)
            ret = bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")  # type: ignore
            if ret != {"FINISHED"}:
                return ret
        elif self.execute_type == 2:  # Don't Save
            pass
        elif self.execute_type == 3:  # Cancel
            ag_utils.simulate_keypress(27)
            return {"CANCELLED"}

        L3D_data.LOAD_POST_CALLBACK = (InitMap, ())
        bpy.ops.wm.read_homefile(app_template="")
        # bpy.app.timers.register(
        #     self.timer_func(self.target), first_interval=0.15
        # )  #
        return {"FINISHED"}


# 初始化地图
# class OT_InitMap(bpy.types.Operator):
#     bl_idname = "amagate.initmap"
#     bl_label = "Initialize Map"
#     bl_description = ""
#     bl_options = {"INTERNAL"}


def InitMap(imp_filepath=""):
    context = bpy.context
    is_import = imp_filepath != ""
    imp_filepath = Path(imp_filepath)
    # 清空场景
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for d in (
        bpy.data.meshes,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.collections,
        bpy.data.materials,
        bpy.data.worlds,
    ):
        for _ in range(len(d)):
            # 倒序删除，避免集合索引更新的开销
            d.remove(d[-1])  # type: ignore
    old_scene = context.window.scene

    # 创建新场景
    name = "Blade Scene"
    bpy.ops.scene.new(type="EMPTY")
    scene = context.window.scene  # type: Scene # type: ignore
    # scene = bpy.data.scenes.new("")  # type: Scene # type: ignore
    scene.rename(name, mode="ALWAYS")
    # context.window.scene = scene
    bpy.data.scenes.remove(old_scene)
    scene_data = scene.amagate_data

    # 初始化场景数据
    scene_data.id = 1
    ## 创建集合
    L3D_data.ensure_collection(L3D_data.C_COLL)
    L3D_data.ensure_collection(L3D_data.GS_COLL)
    L3D_data.ensure_collection(L3D_data.S_COLL)
    L3D_data.ensure_collection(L3D_data.E_COLL)
    L3D_data.ensure_collection(L3D_data.AG_COLL, hide_select=True)
    coll = bpy.data.collections.new(pgettext("Marked Collection"))
    scene.collection.children.link(coll)
    ## 创建标记对象
    player_pos = bpy.data.objects.new("Player", None)
    # player_pos.empty_display_size = 2
    player_pos.empty_display_type = "PLAIN_AXES"
    data.link2coll(player_pos, coll)
    ## 创建默认对象
    L3D_data.ensure_null_texture()
    L3D_data.ensure_null_object()
    L3D_data.ensure_render_camera()

    ## 创建节点
    L3D_data.ensure_node()
    ## 设置渲染引擎
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_samples = 2
    scene.eevee.use_shadows = True
    scene.view_settings.view_transform = "Standard"  # type: ignore
    ## 设置世界环境
    filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
    nodes_data = pickle.load(open(filepath, "rb"))
    world = bpy.data.worlds.new("")
    world.rename("BWorld", mode="ALWAYS")
    data.import_nodes(world, nodes_data["BWorld"])
    # world.use_nodes = True
    # Background = next(
    #     n for n in world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"
    # )
    # Background.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)  # type: ignore
    # Background.inputs[1].default_value = 0.0  # type: ignore
    scene.world = world
    ##
    scene.tool_settings.use_snap = True  # 吸附开关
    scene.tool_settings.snap_elements_base = {
        "EDGE",
        "VERTEX",
        "GRID",
        "FACE",
    }  # 吸附对象

    ## 分割编辑器
    main_area, render_area, front_area = split_editor(context, is_import)

    if not is_import:
        ## 加载纹理，用bmp格式兼容经典版
        for i in ("lisa.bmp", "long.bmp"):
            filepath = os.path.join(data.ADDON_PATH, "textures", i)
            OT_Texture_Add.load_image(filepath).builtin = True
        if data.DEBUG:
            filepath = os.path.join(data.ADDON_PATH, "textures", "test.bmp")
            OT_Texture_Add.load_image(filepath).builtin = True
        # 外部大气
        atmo = OT_Scene_Atmo_Add.add(context)
        atmo["_item_name"] = "ext"
        atmo["_color"] = (0.39, 0.45, 0.56, 0.015)
        # 内部大气
        atmo = OT_Scene_Atmo_Add.add(context)
        atmo["_item_name"] = "int"
        atmo["_color"] = (0.0, 0.0, 0.0, 0.018)
        #
        bpy.ops.amagate.scene_external_add(undo=False)  # type: ignore
    ##
    scene_data.init()
    scene_data.is_blade = True

    if is_import:
        from . import L3D_imp_operator as OP_L3D_IMP

        # 保存当前文件
        save_filepath = imp_filepath.with_suffix(".blend")
        if save_filepath.exists():
            stem = save_filepath.stem
            counter = 1

            while True:
                save_filepath = save_filepath.with_stem(f"{stem}_{counter}")
                if not save_filepath.exists():
                    break
                counter += 1

        #
        # bpy.ops.wm.save_mainfile(filepath=str(save_filepath))

        # logger.info("Start import map...")
        OP_L3D_IMP.import_map(str(imp_filepath))
        sec = scene_data["SectorManage"]["sectors"]["1"]["obj"]
        sec.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        sec.select_set(False)
        scene.camera.matrix_world.translation = sec.location
        with context.temp_override(
            area=main_area,
            region=next(r for r in main_area.regions if r.type == "WINDOW"),
        ):
            bpy.ops.view3d.view_all(center=True)
        # logger.info("Import Map Done")
        #
    scene_data.atmo_id_key = "1"
    L3D_data.load_post()

    if is_import:
        bpy.ops.ed.undo_push(message="Import Map")
        L3D_data.SAVE_POST_CALLBACK = (OT_Texture_Reload.reload_all, ())
        bpy.ops.wm.save_mainfile("INVOKE_DEFAULT", filepath=str(save_filepath))  # type: ignore
    else:
        bpy.ops.ed.undo_push(message="Initialize Scene")
    # 启动异步线程
    if not L3D_data.ASYNC_THREAD:
        L3D_data.ASYNC_THREAD = L3D_data.AsyncThread()
        L3D_data.ASYNC_THREAD.start()


def split_editor(context: Context, is_import):
    scene_data = context.scene.amagate_data
    area_index, main_area = next(
        ((i, a) for i, a in enumerate(context.screen.areas) if a.type == "VIEW_3D"),
        (-1, None),
    )
    # if not main_area:
    #     return

    scene_data.areas_show_hud.add().value = area_index

    region = next(r for r in main_area.regions if r.type == "WINDOW")
    rv3d = region.data  # type: bpy.types.RegionView3D
    rv3d.view_rotation = Euler((math.pi / 3, 0.0, 0.0)).to_quaternion()

    with context.temp_override(area=main_area):
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.4)
        # 调整工作区域属性
        main_area.spaces[0].overlay.normals_length = 0.5  # 法线长度 # type: ignore
        main_area.spaces[0].shading.type = "WIREFRAME" if is_import else "MATERIAL"  # type: ignore
        main_area.spaces[0].overlay.show_extra_edge_length = True  # 边长 # type: ignore
        # main_area.spaces[0].overlay.show_extra_edge_angle = True  # 边夹角 # type: ignore
        main_area.spaces[0].shading.render_pass = (  # type: ignore
            "EMISSION"  # "DIFFUSE_COLOR"  # 渲染通道
        )
        main_area.spaces[0].shading.studiolight_intensity = (  # type: ignore
            0.2  # 灯光强度
        )
        if is_import:
            bpy.app.timers.register(set_view(main_area, "TOP"), first_interval=0.08)
        else:
            with contextlib.redirect_stdout(StringIO()):
                bpy.ops.view3d.toggle_xray()  # 透视模式

    # 渲染区域
    render_area = next(
        a for a in context.screen.areas if a != main_area and a.type == "VIEW_3D"
    )

    """
    if data.DEBUG:
        # For DEBUG
        new_area.type = "CONSOLE"
        # window_region = next((r for r in new_area.regions if r.type == 'WINDOW'), None)
        # 第二次拆分
        with context.temp_override(area=new_area):  # , region=window_region
            bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.75)

        # 找到新创建的区域
        # new_area = next(a for a in context.screen.areas if a != new_area and a.type == 'CONSOLE')
        new_area.type = "VIEW_3D"
    """

    # 调整渲染区域属性
    render_area.spaces[0].shading.type = "WIREFRAME" if is_import else "RENDERED"  # type: ignore
    render_area.spaces[0].overlay.show_extras = False  # type: ignore
    render_area.spaces[0].overlay.show_floor = False  # type: ignore
    render_area.spaces[0].overlay.show_axis_x = False  # type: ignore
    render_area.spaces[0].overlay.show_axis_y = False  # type: ignore
    render_area.spaces[0].overlay.show_cursor = False  # type: ignore
    render_area.spaces[0].overlay.show_faces = False  # type: ignore
    render_area.spaces[0].lock_camera = False  # 锁定相机 # type: ignore
    # new_area.spaces[0].overlay.show_overlays = False  # 叠加层  # type: ignore
    render_area.spaces[0].show_region_toolbar = False  # 工具栏 # type: ignore
    render_area.spaces[0].show_region_tool_header = False  # 工具设置 # type: ignore
    render_area.spaces[0].overlay.show_relationship_lines = (  # type: ignore
        False  # 关系线
    )
    region = next(r for r in render_area.regions if r.type == "WINDOW")
    rv3d = region.data
    rv3d.view_perspective = "CAMERA"
    rv3d.view_camera_zoom = 27  # 9

    # 前视图
    with context.temp_override(area=render_area):
        bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.5)
    front_area = next(
        a
        for a in context.screen.areas
        if a not in (main_area, render_area) and a.type == "VIEW_3D"
    )
    front_area.spaces[0].shading.type = "WIREFRAME"  # type: ignore
    front_area.spaces[0].overlay.show_floor = True  # type: ignore
    front_area.spaces[0].overlay.show_axis_x = True  # type: ignore
    front_area.spaces[0].overlay.show_axis_y = True  # type: ignore
    # region = next(r for r in front_area.regions if r.type == "WINDOW")
    # rv3d = region.data
    # rv3d.view_rotation = Euler((math.pi / 2, 0.0, 0.0)).to_quaternion()
    # rv3d.view_perspective = "ORTHO" # 正交
    bpy.app.timers.register(set_view(front_area, "FRONT"), first_interval=0.08)
    # with context.temp_override(area=front_area):
    #     bpy.ops.view3d.view_persportho()
    #     bpy.ops.view3d.view_axis(type="FRONT")  # 前视图

    # 激活面板
    with context.temp_override(area=main_area, space_data=main_area.spaces[0]):
        bpy.ops.wm.context_toggle(data_path="space_data.show_region_ui")

    region = next(r for r in main_area.regions if r.type == "UI")
    bpy.app.timers.register(
        data.active_panel_category(region, "Amagate"), first_interval=0.05
    )
    return main_area, render_area, front_area


def set_view(area, view_type):
    def warp():
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.view3d.view_persportho()
            bpy.ops.view3d.view_axis(type=view_type)  # 前视图

    return warp


# 重置节点
class OT_Node_Reset(bpy.types.Operator):
    bl_idname = "amagate.node_reset"
    bl_label = "Reset Node"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        self.reset_node()
        return {"FINISHED"}

    @staticmethod
    def reset_node():
        context = bpy.context
        scene_data = context.scene.amagate_data
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))
        # 世界环境
        world = bpy.data.worlds.get("BWorld")
        if not world:
            world = bpy.data.worlds.new("")
            world.rename("BWorld", mode="ALWAYS")
        data.import_nodes(world, nodes_data["BWorld"])
        # 解算节点
        NodeTree = scene_data.eval_node
        data.import_nodes(NodeTree, nodes_data["Amagate Eval"])
        # 扇区节点
        NodeTree = scene_data.sec_node
        data.import_nodes(NodeTree, nodes_data["AG.SectorNodes"])
        # 材质节点
        for tex in bpy.data.images:
            tex_data = tex.amagate_data
            if tex_data.id == 0:
                continue
            #
            name = f"AG.Mat{tex_data.id}"
            mat = tex_data.mat_obj
            if not mat:
                mat = bpy.data.materials.new("")
                mat.rename(name, mode="ALWAYS")
                mat.use_fake_user = True
                mat.use_backface_culling = True
                tex_data.mat_obj = mat
            if tex_data.id == -1:
                data.import_nodes(mat, nodes_data["AG.Mat-1"])
                mat.node_tree.nodes["Environment Texture"].image = tex  # type: ignore
            else:
                data.import_nodes(mat, nodes_data["AG.Mat1"])
                mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore


# 合并地图
class OT_MergeMap(bpy.types.Operator):
    bl_idname = "amagate.mergemap"
    bl_label = "Merge Map"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        # TODO 合并地图
        return {"FINISHED"}


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
