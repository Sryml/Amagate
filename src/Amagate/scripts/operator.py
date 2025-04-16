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

from . import data
from . import ag_utils


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


############################
############################ 通用操作
############################


# 反馈消息
class OT_ReportMessage(bpy.types.Operator):
    bl_idname = "amagate.report_message"
    bl_label = "Report Message"
    bl_options = {"INTERNAL"}

    message: StringProperty(default="No message provided")  # type: ignore
    type: StringProperty(default="INFO")  # type: ignore

    def execute(self, context: Context):
        self.report({self.type}, self.message)
        return {"FINISHED"}


############################
############################ py包安装面板
############################
class OT_InstallPyPackages(bpy.types.Operator):
    bl_idname = "amagate.install_py_packages"
    bl_label = "Install Python Packages"
    bl_description = "Install Python packages"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        # 初始化进度条
        scene_data = bpy.context.scene.amagate_data
        scene_data.progress_bar.pyp_install_progress = 0.0
        ag_utils.install_packages(["cvxpy", "ecos"])
        return {"FINISHED"}


############################
############################ 场景面板 -> 属性面板
############################


class OT_Scene_Props_HUD(bpy.types.Operator):
    bl_idname = "amagate.scene_props_hud"
    bl_label = "Show HUD"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        area_index = next(
            i for i, a in enumerate(context.screen.areas) if a == context.area
        )
        item_index = scene_data.areas_show_hud.find(str(area_index))
        # print(f"item_index: {item_index}")
        if item_index != -1:
            scene_data.areas_show_hud.remove(item_index)
        else:
            scene_data.areas_show_hud.add().value = area_index
        data.region_redraw("WINDOW")
        return {"FINISHED"}


############################
############################ 场景面板 -> 大气面板
############################
class OT_Scene_Atmo_Add(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_add"
    bl_label = "Add Atmosphere"
    bl_options = {"INTERNAL"}

    undo: BoolProperty(default=True)  # type: ignore

    def execute(self, context: Context):
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

        # item.ensure_obj(scene)

        scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        if self.undo:
            bpy.ops.ed.undo_push(message="Add Atmosphere")

        return {"FINISHED"}


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
        scene_data.atmospheres.remove(active_atmo)

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

    prop: PointerProperty(type=data.Atmo_Select)  # type: ignore

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
        scene_data = context.scene.amagate_data

        # 获取可用 ID
        used_ids = tuple(int(i) for i in scene_data.externals.keys())
        id_ = data.get_id(used_ids)
        # 获取可用名称
        used_names = tuple(a.item_name for a in scene_data.externals)

        item = scene_data.externals.add()
        item.name = f"{id_}"
        item["_item_name"] = data.get_name(used_names, "Sun{}", id_)
        item["_color"] = (0.784, 0.784, 0.392)
        item["_vector"] = (-1, 0, -1)
        item.update_obj()

        scene_data.active_external = len(scene_data.externals) - 1
        if self.undo:
            bpy.ops.ed.undo_push(message="Add External Light")
        return {"FINISHED"}


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

        bpy.data.lights.remove(item.obj)
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
        light = data.get_external_by_id(scene_data, self.id)[1]
        col = layout.column()
        col.prop(light, "vector", text="", slider=True)
        col.prop(light, "vector2", text="")

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=100)  # type: ignore


class OT_External_Select(bpy.types.Operator):
    bl_idname = "amagate.external_select"
    bl_label = "Select External Light"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=data.External_Select)  # type: ignore

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
    directory: StringProperty()  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    @staticmethod
    def load_image(filepath, name=""):
        img = bpy.data.images.load(filepath)  # type: Image # type: ignore
        img_data = img.amagate_data
        if name:
            img.name = name
        else:
            img.name = os.path.splitext(os.path.basename(filepath))[0]

        used_ids = tuple(i.amagate_data.id for i in bpy.data.images)  # type: ignore
        img_data.id = data.get_id(used_ids)
        data.ensure_material(img)
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
            if f.name and os.path.exists(os.path.join(self.directory, f.name))
        ]
        if not files:
            files = [
                f
                for f in os.listdir(self.directory)
                if f.endswith((".jpg", ".png", ".jpeg", ".bmp", ".tga"))
            ]

        for file in files:
            name = os.path.splitext(file)[0]
            if name == data.ensure_null_texture().name:
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
                        data.ensure_material(img)
                        if not img.use_fake_user:
                            img.use_fake_user = True
            else:
                self.load_image(filepath, name)
        return {"FINISHED"}

    def invoke(self, context, event):
        self.override = event.shift
        # 这里通过文件选择器来选择文件或文件夹
        self.filepath = "//"
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

    reload_all: BoolProperty(name="Reload All", default=False)  # type: ignore

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        if self.reload_all:
            for img in bpy.data.images:  # type: ignore
                if img.amagate_data.id:
                    img.reload()
        else:
            idx = scene_data.active_texture
            if idx >= len(bpy.data.images):
                return {"CANCELLED"}

            img: Image = bpy.data.images[idx]
            if img and img.amagate_data.id:
                img.reload()
        return {"FINISHED"}

    def invoke(self, context: Context, event):
        self.reload_all = event.shift
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

    prop: PointerProperty(type=data.Texture_Select)  # type: ignore

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
        elif properties.target == "import":  # type: ignore
            return pgettext("Import Blade scene from *.bw file")

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        row = layout.row()
        row.label(text="Save changes before closing?")

        row = layout.row()
        row.operator(OT_New.bl_idname, text="Save").execute_type = 1  # type: ignore
        row.operator(OT_New.bl_idname, text="Don't Save").execute_type = 2  # type: ignore
        row.operator(OT_New.bl_idname, text="Cancel").execute_type = 3  # type: ignore

    @staticmethod
    def timer_func(target):
        def warp():
            operators = {"new": "initmap", "import": ""}
            getattr(bpy.ops.amagate, operators[target])()  # type: ignore

        return warp

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        if self.execute_type == 0:
            if bpy.data.is_dirty:
                return context.window_manager.invoke_popup(self)
        elif self.execute_type == 1:  # Save
            # ag_utils.simulate_keypress(27)
            ret = bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")  # type: ignore
            if ret != {"FINISHED"}:
                return ret
        elif self.execute_type == 2:  # Don't Save
            # ag_utils.simulate_keypress(27)
            pass
        elif self.execute_type == 3:  # Cancel
            ag_utils.simulate_keypress(27)
            return {"CANCELLED"}

        bpy.ops.wm.read_homefile(app_template="")
        bpy.app.timers.register(self.timer_func(self.target), first_interval=0.05)
        return {"FINISHED"}


# 初始化地图
class OT_InitMap(bpy.types.Operator):
    bl_idname = "amagate.initmap"
    bl_label = "Initialize Map"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
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
        data.ensure_collection(data.AG_COLL, hide_select=True)
        data.ensure_collection(data.S_COLL)
        data.ensure_collection(data.GS_COLL)
        data.ensure_collection(data.E_COLL)
        data.ensure_collection(data.C_COLL)
        ## 创建默认对象
        data.ensure_null_texture()
        data.ensure_null_object()
        data.ensure_render_camera()
        ## 加载纹理
        if data.DEBUG:
            filepath = os.path.join(data.ADDON_PATH, "textures", "test.bmp")
            OT_Texture_Add.load_image(filepath).builtin = True
        # for i in ("floor_01.jpg", "wall_01.jpg"):
        #     filepath = os.path.join(data.ADDON_PATH, "textures", i)
        #     OT_Texture_Add.load_image(filepath).builtin = True
        ## 创建默认数据
        bpy.ops.amagate.scene_atmo_add(undo=False)  # type: ignore
        bpy.ops.amagate.scene_external_add(undo=False)  # type: ignore
        ## 创建节点
        data.ensure_node()
        ## 设置渲染引擎
        scene.eevee.use_shadows = True
        ## 设置世界环境
        world = bpy.data.worlds.new("")
        world.rename("BWorld", mode="ALWAYS")
        world.use_nodes = True
        Background = next(
            n for n in world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"
        )
        Background.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)  # type: ignore
        Background.inputs[1].default_value = 0.02  # type: ignore
        scene.world = world
        ##
        scene.tool_settings.use_snap = True  # 吸附开关
        scene.tool_settings.snap_elements_base = {
            "EDGE",
            "VERTEX",
            "GRID",
            "FACE",
        }  # 吸附对象
        ##
        scene_data.init()

        # TODO 添加默认摄像机 添加默认扇区 调整视角

        ## 分割编辑器
        split_editor(context)
        scene_data.is_blade = True

        data.load_post()

        bpy.ops.ed.undo_push(message="Initialize Scene")
        return {"FINISHED"}


def split_editor(context: Context):
    scene_data = context.scene.amagate_data
    area_index, area = next(
        ((i, a) for i, a in enumerate(context.screen.areas) if a.type == "VIEW_3D"),
        (-1, None),
    )
    if not area:
        return

    scene_data.areas_show_hud.add().value = area_index

    region = next(r for r in area.regions if r.type == "WINDOW")
    rv3d = region.data  # type: bpy.types.RegionView3D
    rv3d.view_rotation = Euler((math.pi / 3, 0.0, 0.0)).to_quaternion()

    with context.temp_override(area=area):
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.4)
        # 调整工作区域属性
        area.spaces[0].shading.type = "MATERIAL"  # type: ignore
        area.spaces[0].overlay.show_extra_edge_length = True  # 边长 # type: ignore
        # area.spaces[0].overlay.show_extra_edge_angle = True  # 边夹角 # type: ignore
        area.spaces[0].shading.render_pass = "DIFFUSE_COLOR"  # 渲染通道 # type: ignore
        with contextlib.redirect_stdout(StringIO()):
            bpy.ops.view3d.toggle_xray()  # 透视模式

    # 找到新创建的区域
    new_area = next(
        a for a in context.screen.areas if a != area and a.type == "VIEW_3D"
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
    new_area.spaces[0].shading.type = "RENDERED"  # type: ignore
    new_area.spaces[0].overlay.show_extras = False  # type: ignore
    new_area.spaces[0].overlay.show_floor = False  # type: ignore
    new_area.spaces[0].overlay.show_axis_x = False  # type: ignore
    new_area.spaces[0].overlay.show_axis_y = False  # type: ignore
    new_area.spaces[0].overlay.show_cursor = False  # type: ignore
    new_area.spaces[0].overlay.show_faces = False  # type: ignore
    new_area.spaces[0].lock_camera = True  # 锁定相机 # type: ignore
    # new_area.spaces[0].overlay.show_overlays = False  # 叠加层  # type: ignore
    region = next(r for r in new_area.regions if r.type == "WINDOW")
    rv3d = region.data
    rv3d.view_perspective = "CAMERA"
    rv3d.view_camera_zoom = 9

    # 激活面板
    with context.temp_override(area=area, space_data=area.spaces[0]):
        bpy.ops.wm.context_toggle(data_path="space_data.show_region_ui")

    region = next(r for r in area.regions if r.type == "UI")
    bpy.app.timers.register(
        data.active_panel_category(region, "Amagate"), first_interval=0.05
    )


# 合并地图
class OT_MergeMap(bpy.types.Operator):
    bl_idname = "amagate.mergemap"
    bl_label = "Merge Map"
    bl_description = ""
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        # TODO 合并地图
        return {"FINISHED"}


# 导入地图
class OT_ImportMap(bpy.types.Operator):
    bl_idname = "amagate.importmap"
    bl_label = "Import Map"
    bl_description = "Import Blade Map"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        # TODO 导入地图
        return {"FINISHED"}


#  -> 导出地图
class OT_ExportMap(bpy.types.Operator):
    bl_idname = "amagate.exportmap"
    bl_label = "Export Map (with Script)"
    bl_description = "Export Blade Map"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        # 检查是否为无标题文件
        if not bpy.data.filepath:
            self.report({"WARNING"}, "Please save the file first")
            return {"CANCELLED"}
        # 收集可见扇区
        sectors_dict = scene_data["SectorManage"]["sectors"]
        sector_ids = [
            int(k) for k in sectors_dict if sectors_dict[k]["obj"].visible_get()
        ]
        sector_ids.sort()
        if not sector_ids:
            self.report({"WARNING"}, "No visible sector found")
            return {"CANCELLED"}

        # 导出扇区
        ## blender坐标转换到blade: x,-z,y
        if context.mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")

        bw_file = f"{os.path.splitext(bpy.data.filepath)[0]}.bw"
        global_face_count = 0
        global_vertex_count = 0
        global_vertex_map = {}  # {tuple(co): global_index}
        sector_vertex_indices = {}  # 每个扇区的全局顶点索引映射
        global_sector_map = {sid: i for i, sid in enumerate(sector_ids)}  # 全局扇区映射
        with open(bw_file, "wb") as f:
            # 写入大气数据
            f.write(struct.pack("<I", len(scene_data.atmospheres) + 1))
            for atm in scene_data.atmospheres:
                buffer = atm.item_name.encode("utf-8")
                f.write(struct.pack("<I", len(buffer)))
                f.write(buffer)
                f.write(
                    struct.pack(
                        "<BBB", *(math.ceil(atm.color[i] * 255) for i in range(3))
                    )
                )
                f.write(struct.pack("<f", atm.color[-1]))
            ## 写入Amagate元数据
            buffer = f"Metadata:\nAmagate-{data.VERSION} {data.Copyright}\nhttps://github.com/Sryml/Amagate".encode(
                "utf-8"
            )
            f.write(struct.pack("<I", len(buffer)))
            f.write(buffer)
            f.write(b"\x00" * 7)

            # 写入顶点数据
            number_pos = f.tell()
            f.write(struct.pack("<I", 0))  # 占位
            for i in sector_ids:
                sec = sectors_dict[str(i)]["obj"]  # type: Object
                sec_vertex_indices = []
                sec_data = sec.amagate_data.get_sector_data()
                mesh = sec.data  # type: bpy.types.Mesh # type: ignore
                matrix_world = sec.matrix_world
                for v in mesh.vertices:
                    # 变换顶点坐标并转换为毫米单位，保留一位小数
                    v_key = ((matrix_world @ v.co) * 1000).to_tuple(1)
                    if v_key not in global_vertex_map:
                        global_vertex_map[v_key] = global_vertex_count
                        global_vertex_count += 1
                        f.write(struct.pack("<ddd", v_key[0], -v_key[2], v_key[1]))
                    sec_vertex_indices.append(global_vertex_map[v_key])
                sector_vertex_indices[sec_data.id] = sec_vertex_indices
            # 暂存当前流位置并更正顶点数量
            stream_pos = f.tell()
            f.seek(number_pos)
            f.write(struct.pack("<I", global_vertex_count))
            f.seek(stream_pos)

            # 写入扇区数据
            v_factor = 0.86264  # 明度系数
            ambient_light_p = bytes.fromhex("0000803C")  # 0.015625 环境光精度
            ext_light_p = bytes.fromhex("0000003D")  # 0.03125 外部灯光精度
            spot_buffer = BytesIO()  # 缓存聚光灯数据
            spot_num = 0
            group_buffer = BytesIO()  # 缓存组数据
            sec_name_buffer = BytesIO()  # 缓存扇区名称数据
            f.write(struct.pack("<I", len(sector_ids)))
            for sector_id in sector_ids:
                sec = sectors_dict[str(sector_id)]["obj"]  # type: Object
                sec_data = sec.amagate_data.get_sector_data()
                matrix_world = sec.matrix_world

                # 聚光灯
                if sec_data.spot_light:
                    spot_num += len(sec_data.spot_light)
                    spot = None  # type: data.SectorFocoLightProperty # type: ignore
                    for spot in sec_data.spot_light:
                        spot_buffer.write(struct.pack("<I", 15001))
                        spot_buffer.write(
                            struct.pack(
                                "<BBB", *(math.ceil(c * 255) for c in spot.color)
                            )
                        )
                        spot_buffer.write(struct.pack("<f", spot.strength))
                        spot_buffer.write(struct.pack("<f", spot.precision))
                        pos = spot.pos * 1000
                        spot_buffer.write(struct.pack("<ddd", pos[0], -pos[2], pos[1]))
                        spot_buffer.write(
                            struct.pack("<f", global_sector_map[sector_id])
                        )

                # 组
                group_buffer.write(struct.pack("<I", sec_data.group))

                # 扇区名称
                buffer = sec.name.encode("utf-8")
                sec_name_buffer.write(struct.pack("<I", len(buffer)))
                sec_name_buffer.write(buffer)

                # 大气名称
                atm_name = data.get_atmo_by_id(scene_data, sec_data.atmo_id)[
                    1
                ].item_name
                buffer = atm_name.encode("utf-8")
                f.write(struct.pack("<I", len(buffer)))
                f.write(buffer)

                # 环境光
                color = sec_data.ambient_color
                f.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
                f.write(struct.pack("<f", color.v * v_factor))
                f.write(ambient_light_p)
                f.write(struct.pack("<ddd", 0, 0, 0))  # 未知用途 默认0
                f.write(bytes.fromhex("CD" * 8))
                f.write(struct.pack("<I", 0))

                # 平面光  # TODO
                f.write(struct.pack("<BBB", 0, 0, 0))
                f.write(struct.pack("<f", 0.0))
                f.write(ambient_light_p)
                f.write(struct.pack("<ddd", 0, 0, 0))  # # 未知用途 默认0
                f.write(bytes.fromhex("CD" * 8))
                f.write(struct.pack("<I", 0))
                ## 平面光向量
                f.write(struct.pack("<ddd", 0, 0, 0))

                # 面数据
                sec_vertex_indices = sector_vertex_indices[sec_data.id]
                depsgraph = bpy.context.evaluated_depsgraph_get()
                evaluated_obj = sec.evaluated_get(depsgraph)
                mesh = evaluated_obj.data  # type: bpy.types.Mesh # type: ignore
                global_face_count += len(mesh.polygons)
                f.write(struct.pack("<I", len(mesh.polygons)))
                for face_index, face in enumerate(mesh.polygons):
                    connected_sid = sec_data["ConnectManager"]["faces"].get(
                        str(face_index)
                    )
                    ## 面类型
                    if mesh.attributes["amagate_tex_id"].data[face_index].value == -1:  # type: ignore
                        face_type = 7005
                    elif connected_sid is not None:  # type: ignore
                        face_type = 7002
                    else:
                        face_type = 7001
                    f.write(struct.pack("<I", face_type))
                    ## 法向
                    normal = matrix_world.to_quaternion() @ face.normal
                    f.write(struct.pack("<ddd", normal[0], -normal[2], normal[1]))
                    f.write(struct.pack("<d", mesh.attributes["amagate_v_dist"].data[face_index].value))  # type: ignore

                    if face_type in (7002, 7005):
                        f.write(struct.pack("<I", len(face.vertices)))
                        for v_idx in face.vertices:
                            f.write(struct.pack("<I", sec_vertex_indices[v_idx]))
                        if face_type == 7005:
                            continue
                        f.write(struct.pack("<I", global_sector_map[connected_sid]))
                    ## 固定标识
                    f.write(struct.pack("<I", 3))
                    f.write(struct.pack("<I", 0))

                    buffer = data.get_texture_by_id(mesh.attributes["amagate_tex_id"].data[face_index].value)[1].name.encode("utf-8")  # type: ignore
                    f.write(struct.pack("<I", len(buffer)))
                    f.write(buffer)
                    tex_vx = mesh.attributes["amagate_tex_vx"].data[face_index].vector  # type: ignore
                    f.write(struct.pack("<ddd", tex_vx[0], -tex_vx[2], tex_vx[1]))
                    tex_vy = mesh.attributes["amagate_tex_vy"].data[face_index].vector  # type: ignore
                    f.write(struct.pack("<ddd", tex_vy[0], -tex_vy[2], tex_vy[1]))
                    tex_pos = mesh.attributes["amagate_tex_pos"].data[face_index].vector  # type: ignore
                    f.write(struct.pack("<ff", *tex_pos))

                    f.write(b"\x00" * 8)  # 0

                    if face_type == 7002:
                        continue

                    f.write(struct.pack("<I", len(face.vertices)))
                    for v_idx in face.vertices:
                        f.write(struct.pack("<I", sec_vertex_indices[v_idx]))

            # 写入外部光和聚光灯数据
            external_num = 0
            number_pos = f.tell()
            f.write(struct.pack("<I", 0))  # 占位
            ## 外部光
            for i in scene_data.externals:
                if not i.users_obj:
                    continue

                color = i.color
                vector = i.vector.normalized()
                f.write(struct.pack("<I", 15002))
                f.write(struct.pack("<BBB", *(math.ceil(c * 255) for c in color)))
                f.write(struct.pack("<f", color.v * v_factor))
                f.write(ext_light_p)
                f.write(struct.pack("<ddd", 0, 0, 0))
                f.write(bytes.fromhex("CD" * 8))
                f.write(struct.pack("<I", 0))
                f.write(struct.pack("<ddd", vector[0], -vector[2], vector[1]))
                ## 使用该外部光的扇区
                f.write(struct.pack("<I", len(i.users_obj)))
                for i in i.users_obj:
                    f.write(
                        struct.pack(
                            "<I",
                            global_sector_map[i.obj.amagate_data.get_sector_data().id],
                        )
                    )
                external_num += 1
            ## 聚光灯
            stream_pos = f.tell()
            f.seek(number_pos)
            f.write(struct.pack("<I", spot_num + external_num))
            f.seek(stream_pos)
            f.write(spot_buffer.getvalue())
            spot_buffer.close()

            ## 未知数据 地图边界？
            f.write(struct.pack("<ddd", 0, 0, 0))
            f.write(struct.pack("<ddd", 0, 0, 0))

            # 写入组数据
            f.write(group_buffer.getvalue())
            group_buffer.close()

            # 写入扇区名称数据
            f.write(struct.pack("<I", len(sector_ids)))
            f.write(sec_name_buffer.getvalue())
            sec_name_buffer.close()

        # 创建脚本
        map_dir = os.path.dirname(bpy.data.filepath)
        sec = sectors_dict[str(sector_ids[0])]["obj"]  # type: Object
        player_pos = (sec.location * 1000).to_tuple(1)
        player_pos = player_pos[0], -player_pos[2], player_pos[1]
        mapcfg = {
            "bw_file": os.path.basename(bw_file),
            "player_pos": player_pos,
        }
        with open(os.path.join(map_dir, "mapcfg.py"), "w", encoding="utf-8") as file:
            file.write("mapcfg = ")
            pprint(mapcfg, stream=file, indent=0, sort_dicts=False)
        scripts_dir = os.path.join(data.ADDON_PATH, "blade_scripts")
        for f in os.listdir(scripts_dir):
            shutil.copy(
                os.path.join(scripts_dir, f), os.path.join(os.path.dirname(bw_file), f)
            )

        # self.report({'WARNING'}, "Export Map Failed")
        self.report(
            {"INFO"},
            f"{pgettext('Export Map')} - {pgettext('Success')}:\n{global_vertex_count} {pgettext('Vertices')}, {global_face_count} {pgettext('Faces')}, {len(sector_ids)} {pgettext('Sectors')}",
        )
        return {"FINISHED"}


############################
############################ 调试面板
############################


class OT_Test(bpy.types.Operator):
    bl_idname = "amagate.test"
    bl_label = "Test"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context: Context):
        # area = context.area
        # if area.type == "VIEW_3D":
        #     for region in area.regions:
        #         if region.type == "WINDOW":
        #             print(f"width: {region.width}, height: {region.height}")
        #             rv3d = region.data  # type: bpy.types.RegionView3D
        # # rv3d.view_perspective = "CAMERA"
        # context.scene.camera = bpy.data.objects["Camera"]
        # bpy.ops.mesh.knife_project()
        # 设置视图为顶部视图
        # rv3d.view_rotation = Euler((math.pi / 3, 0.0, 0.0)).to_quaternion()
        # rv3d.view_distance = 15.0
        # rv3d.view_location = (0.0, 0.0, 0.0)
        # print(f"view_rotation: {rv3d.view_rotation.to_euler()}")
        # print(f"view_distance: {rv3d.view_distance}")
        # print(f"view_location: {rv3d.view_location}")
        # rv3d.view_perspective="ORTHO"
        # print(f"view_camera_zoom: {rv3d.view_camera_zoom}")
        # break
        return {"FINISHED"}


# 重载插件
class OT_ReloadAddon(bpy.types.Operator):
    bl_idname = "amagate.reloadaddon"
    bl_label = ""
    bl_description = "Reload Addon"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        base_package = sys.modules[data.PACKAGE]  # type: ignore

        bpy.ops.preferences.addon_disable(module=data.PACKAGE)  # type: ignore
        # base_package.unregister()
        bpy.app.timers.register(
            lambda: bpy.ops.preferences.addon_enable(module=data.PACKAGE) and None,  # type: ignore
            first_interval=0.5,
        )
        # bpy.ops.preferences.addon_enable(module=data.PACKAGE)  # type: ignore
        # base_package.register(reload=True)
        print("插件已热更新！")
        return {"FINISHED"}


# 导出节点
class OT_ExportNode(bpy.types.Operator):
    bl_idname = "amagate.exportnode"
    bl_label = "Export Node"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        # 导出节点
        nodes_data = {}
        nodes_data["AG.Mat1"] = data.export_nodes(bpy.data.materials["AG.Mat1"])
        nodes_data["Amagate Eval"] = data.export_nodes(
            bpy.data.node_groups["Amagate Eval"]
        )
        # nodes_data["AG.SectorNodes"] = data.export_nodes(
        #     bpy.data.node_groups["AG.SectorNodes"]
        # )
        pickle.dump(nodes_data, open(filepath, "wb"), protocol=pickle.HIGHEST_PROTOCOL)

        with open(filepath + ".tmp", "w", encoding="utf-8") as file:
            pprint(nodes_data, stream=file, indent=0, sort_dicts=False)
        return {"FINISHED"}


class OT_ImportNode(bpy.types.Operator):
    bl_idname = "amagate.importnode"
    bl_label = "Import Node"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))

        name = "AG.Mat1"
        mat = bpy.data.materials.new(name)
        data.import_nodes(mat, nodes_data[name])

        name = "Amagate Eval"
        group = bpy.data.node_groups.new(name, "GeometryNodeTree")  # type: ignore

        group.interface.new_socket(
            "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )
        input_node = group.nodes.new("NodeGroupInput")
        input_node.select = False
        input_node.location.x = -200 - input_node.width

        group.interface.new_socket(
            "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )
        output_node = group.nodes.new("NodeGroupOutput")
        output_node.is_active_output = True  # type: ignore
        output_node.select = False
        output_node.location.x = 200

        group.links.new(input_node.outputs[0], output_node.inputs[0])
        group.use_fake_user = True
        group.is_tool = True  # type: ignore
        group.is_type_mesh = True  # type: ignore
        data.import_nodes(group, nodes_data[name])

        # name = "AG.SectorNodes"
        # NodeTree = bpy.data.node_groups.new(name, "GeometryNodeTree")  # type: ignore
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        # )
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        # )
        # NodeTree.is_modifier = True  # type: ignore
        # data.import_nodes(NodeTree, nodes_data[name])
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
