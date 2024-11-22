import sys
import os
from typing import Any

import bpy
from bpy.app.translations import pgettext
from bpy.types import Context
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
from mathutils import *

from . import data


import ctypes
import time


# 定义 Windows API 中的 keybd_event 函数
def simulate_keypress():
    # 0x1B 是 Esc 键的虚拟键码
    ESC_KEY_CODE = 0x1B

    # 定义 keybd_event 参数
    # 需要按下 ESC 键
    ctypes.windll.user32.keybd_event(ESC_KEY_CODE, 0, 0, 0)
    time.sleep(0.01)  # 按键按下后等待一段时间

    # 释放 ESC 键
    ctypes.windll.user32.keybd_event(ESC_KEY_CODE, 0, 2, 0)


############################
############################ 场景面板 -> 大气面板
############################
class OT_Scene_Atmo_Add(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_add"
    bl_label = "Add Atmosphere"
    bl_options = {"INTERNAL"}

    @staticmethod
    def new(scene):
        scene_data: data.SceneProperty = scene.amagate_data  # type: ignore

        # 获取可用 ID
        used_ids = tuple(a.id for a in scene_data.atmospheres)
        id_ = data.get_id(used_ids)
        # 获取可用名称
        used_names = tuple(a.name for a in scene_data.atmospheres)

        new_atmo = scene_data.atmospheres.add()
        new_atmo.id = id_
        new_atmo["_name"] = data.get_name(used_names, "atmo{}", id_)

        # 创建空物体 用来判断引用
        name = f"ATMO_{id_}{data.get_scene_suffix(scene)}"
        obj = bpy.data.objects.get(name)
        if not (obj and obj.type == "EMPTY"):
            obj = bpy.data.objects.new(name, None)
        obj["id"] = id_
        new_atmo.atmo_obj = obj

        scene_data.active_atmosphere = len(scene_data.atmospheres) - 1

    def execute(self, context: Context):
        self.new(context.scene)
        return {"FINISHED"}


class OT_Scene_Atmo_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_remove"
    bl_label = "Remove Atmosphere"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
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
        if atmo.atmo_obj.users > 1:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Atmosphere is used by sectors')}",
            )
            return {"CANCELLED"}

        bpy.data.objects.remove(atmo.atmo_obj)
        scene_data.atmospheres.remove(active_atmo)

        if active_atmo >= len(scene_data.atmospheres):
            scene_data.active_atmosphere = len(scene_data.atmospheres) - 1
        return {"FINISHED"}

    def invoke(self, context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Scene_Atmo_Default(bpy.types.Operator):
    bl_idname = "amagate.scene_atmo_default"
    bl_label = "Set as default atmosphere"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        active_atmo = scene_data.active_atmosphere
        if active_atmo >= len(scene_data.atmospheres):
            return {"CANCELLED"}

        scene_data.defaults.atmo_id = scene_data.atmospheres[active_atmo].id
        return {"FINISHED"}


class OT_Atmo_Select(bpy.types.Operator):
    bl_idname = "amagate.atmo_select"
    bl_label = "Select Atmosphere"
    bl_options = {"INTERNAL"}

    prop: PointerProperty(type=data.Atmo_Select)  # type: ignore

    def draw(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
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
        # simulate_keypress()
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

    @classmethod
    def new(cls, scene):
        scene_data: data.SceneProperty = scene.amagate_data  # type: ignore

        # 获取可用 ID
        used_ids = tuple(a.id for a in scene_data.externals)
        id_ = data.get_id(used_ids)
        # 获取可用名称
        used_names = tuple(a.name for a in scene_data.externals)

        new_item = scene_data.externals.add()
        new_item.id = id_
        new_item["_name"] = data.get_name(used_names, "Sun{}", id_)
        # new_item.sync_obj(scene)
        new_item["_color"] = (0.784, 0.784, 0.392)
        new_item["_vector"] = (-1, 0, -1)
        new_item.sync_obj(None, scene)

        scene_data.active_external = len(scene_data.externals) - 1

    def execute(self, context: Context):
        self.new(context.scene)
        return {"FINISHED"}


class OT_Scene_External_Remove(bpy.types.Operator):
    bl_idname = "amagate.scene_external_remove"
    bl_label = "Remove External Light"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data: data.SceneProperty = context.scene.amagate_data  # type: ignore
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
        if item.obj.users - len(item.obj.users_collection) > 1:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('External light is used by objects')}",
            )
            return {"CANCELLED"}

        bpy.data.objects.remove(item.obj)
        externals.remove(active_idx)

        if active_idx >= len(externals):
            scene_data.active_external = len(externals) - 1
        return {"FINISHED"}

    def invoke(self, context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Scene_External_Default(bpy.types.Operator):
    bl_idname = "amagate.scene_external_default"
    bl_label = "Set as default external light"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        active_idx = scene_data.active_external
        if active_idx >= len(scene_data.externals):
            return {"CANCELLED"}

        scene_data.defaults.external_id = scene_data.externals[active_idx].id
        return {"FINISHED"}


class OT_Scene_External_Set(bpy.types.Operator):
    bl_idname = "amagate.scene_external_set"
    bl_label = "Set External Light"
    bl_options = {"INTERNAL"}

    id: IntProperty(name="ID")  # type: ignore

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore

        return {"FINISHED"}

    # TODO
    def draw(self, context):
        layout = self.layout
        scene_data = context.scene.amagate_data  # type: ignore
        light = data.get_external_by_id(scene_data, self.id)[1]
        col = layout.column()
        col.prop(light, "vector", text="")
        col.prop(light, "vector2", text="")

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=100)  # type: ignore


# 场景面板 -> 新建场景
class OT_NewScene(bpy.types.Operator):
    bl_idname = "amagate.newscene"
    bl_label = "New Scene"
    bl_description = "Create a new Blade Scene"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        used_ids = tuple(i.amagate_data.id for i in bpy.data.scenes)  # type: ignore
        id_ = data.get_id(used_ids)
        used_names = tuple(i.name for i in bpy.data.scenes)
        name = data.get_name(used_names, "Blade Scene {}", id_)

        # 创建新场景
        # bpy.ops.scene.new()
        scene = bpy.data.scenes.new(name)
        scene_data: data.SceneProperty = scene.amagate_data  # type: ignore

        # 初始化场景数据
        scene_data.id = id_
        scene_data.is_blade = True  # type: ignore

        data.ensure_collection(data.AG_COLL, scene)
        data.ensure_collection(data.S_COLL, scene)
        data.ensure_collection(data.GS_COLL, scene)
        data.ensure_collection(data.E_COLL, scene)

        data.ensure_null_object()

        OT_Scene_Atmo_Add.new(scene)
        OT_Scene_External_Add.new(scene)
        scene_data.init()  # type: ignore

        # TODO 添加默认摄像机 添加默认扇区 划分界面布局 调整视角

        context.window.scene = scene  # type: ignore
        bpy.ops.ed.undo_push(message="Create Blade Scene")
        return {"FINISHED"}


############################
############################ 纹理面板
############################
class OT_Texture_Add(bpy.types.Operator):
    bl_idname = "amagate.texture_add"
    bl_label = "Add Texture"
    bl_description = "Hold shift to enable overlay"
    bl_options = {"INTERNAL"}

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

    def load_image(self, context, filepath, name=""):
        scene_data = context.scene.amagate_data  # type: ignore
        img = bpy.data.images.load(filepath)
        img_data = img.amagate_data  # type: ignore
        if name:
            img.name = name

        used_ids = tuple(i.amagate_data.id for i in bpy.data.images)  # type: ignore
        img_data.id = data.get_id(used_ids)

    def execute(self, context):
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
            filepath = os.path.join(self.directory, file)
            if same_drive and self.relative_path:
                filepath = f"//{os.path.relpath(filepath, curr_dir)}"

            img = bpy.data.images.get(name)
            if img:
                if self.override:
                    img.filepath = filepath
                    img.reload()
                    if not img.amagate_data.id:  # type: ignore
                        used_ids = tuple(i.amagate_data.id for i in bpy.data.images)  # type: ignore
                        img.amagate_data.id = data.get_id(used_ids)  # type: ignore
            else:
                self.load_image(context, filepath, name)
        return {"FINISHED"}

    def invoke(self, context, event):
        self.override = event.shift
        # 这里通过文件选择器来选择文件或文件夹
        self.filepath = "//"
        context.window_manager.fileselect_add(self)  # type: ignore
        return {"RUNNING_MODAL"}


class OT_Texture_Remove(bpy.types.Operator):
    bl_idname = "amagate.texture_remove"
    bl_label = "Remove Texture"
    bl_description = "Hold shift to quickly delete"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        idx = scene_data.active_texture

        if idx >= len(bpy.data.images):
            return {"CANCELLED"}

        img: bpy.types.Image = bpy.data.images[idx]  # type: ignore
        img_data = img.amagate_data  # type: ignore

        if not img_data.id or img.name == "NULL":
            # 不能删除特殊纹理
            if img.name == "NULL":
                self.report(
                    {"WARNING"},
                    f"{pgettext('Warning')}: {pgettext('Cannot remove special texture')}",
                )
            return {"CANCELLED"}

        # 不能删除正在使用的纹理
        # TODO 也许检查材质的引用
        if img.users > 1:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Texture is used by sectors')}",
            )
            return {"CANCELLED"}

        # 不能删除默认纹理
        # FIXME 这里需要判断是否被其它场景使用
        default_id = [
            i["id"] for i in scene_data.defaults["Textures"].values() if i["id"] != 0
        ]
        if img_data.id in default_id:
            self.report(
                {"WARNING"},
                f"{pgettext('Warning')}: {pgettext('Cannot remove default texture')}",
            )
            return {"CANCELLED"}

        # 删除纹理
        bpy.data.images.remove(img)

        return {"FINISHED"}

    def invoke(self, context, event):
        if event.shift:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)  # type: ignore


class OT_Texture_Reload(bpy.types.Operator):
    bl_idname = "amagate.texture_reload"
    bl_label = "Reload Texture"
    bl_description = "Hold shift to reload all texture"
    bl_options = {"INTERNAL"}

    reload_all: BoolProperty(name="Reload All", default=False)  # type: ignore

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        if self.reload_all:
            for img in bpy.data.images:
                if img.amagate_data.id:  # type: ignore
                    img.reload()
        else:
            idx = scene_data.active_texture
            if idx >= len(bpy.data.images):
                return {"CANCELLED"}

            img: bpy.types.Image = bpy.data.images[idx]  # type: ignore
            if img and img.amagate_data.id:  # type: ignore
                img.reload()
        return {"FINISHED"}

    def invoke(self, context, event):
        self.reload_all = event.shift
        return self.execute(context)


class OT_Texture_Package(bpy.types.Operator):
    bl_idname = "amagate.texture_package"
    bl_label = "Pack/Unpack Texture"
    bl_description = "Hold shift to pack/unpack all textures"
    bl_options = {"INTERNAL"}

    items: CollectionProperty(type=data.StringCollection)  # type: ignore
    index: IntProperty(name="Select Operation", default=3, update=lambda self, context: OT_Texture_Package.execute2(self, context))  # type: ignore
    ############################

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.template_list(
            "AMAGATE_UI_UL_StrList", "", self, "items", self, "index", rows=2
        )

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        m = "USE_LOCAL" if bpy.data.filepath else "USE_ORIGINAL"
        idx = scene_data.active_texture
        if idx >= len(bpy.data.images):
            return {"CANCELLED"}

        img: bpy.types.Image = bpy.data.images[idx]  # type: ignore
        if img and img.amagate_data.id and img.name != "NULL":  # type: ignore
            if img.packed_file:
                img.unpack(method=m)
            else:
                img.pack()
        return {"FINISHED"}

    @staticmethod
    def execute2(this, context):
        # 如果未打开blend文件，则使用原始路径
        m = "USE_LOCAL" if bpy.data.filepath else "USE_ORIGINAL"
        selected = this.items[this.index].name
        for img in bpy.data.images:
            if img.amagate_data.id and img.name != "NULL":  # type: ignore
                if selected == "Pack All":
                    if not img.packed_file:
                        img.pack()
                else:
                    if img.packed_file:
                        img.unpack(method=m)
        # XXX 也许不起作用
        simulate_keypress()

    def invoke(self, context, event):
        if event.shift:
            for n in ("Pack All", "Unpack All"):
                self.items.add().name = n
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

    def draw(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
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


############################
############################ 扇区面板
############################


# 转换为扇区
class OT_Sector_Convert(bpy.types.Operator):
    bl_idname = "amagate.sector_convert"
    bl_label = "Convert to Sector"
    bl_description = "Convert selected objects to sector"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        original_selection = context.selected_objects
        if not original_selection:
            return {"CANCELLED"}

        mesh_objects = [obj for obj in original_selection if obj.type == "MESH"]
        if not mesh_objects:
            return {"CANCELLED"}

        # 选择所有 MESH 对象
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)  # 选择 MESH 对象

        bpy.ops.object.mode_set(mode="EDIT")
        # 全选所有面
        bpy.ops.mesh.select_all(action="SELECT")
        # 调整法线一致性
        bpy.ops.mesh.normals_make_consistent(inside=True)
        bpy.ops.object.mode_set(mode="OBJECT")

        # 恢复选择
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selection:
            obj.select_set(True)

        for obj in mesh_objects:
            if not obj.amagate_data.get_sector_data():  # type: ignore
                sector_data = obj.amagate_data.set_sector_data()  # type: ignore
                sector_data.init()
        return {"FINISHED"}


# 重载插件
class OT_ReloadAddon(bpy.types.Operator):
    bl_idname = "amagate.reloadaddon"
    bl_label = ""
    bl_description = "Reload Addon"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        base_package = sys.modules[__package__]  # type: ignore

        bpy.ops.preferences.addon_disable(module=__package__)  # type: ignore
        # base_package.unregister()
        bpy.ops.preferences.addon_enable(module=__package__)  # type: ignore
        # base_package.register(reload=True)
        print("插件已热更新！")
        return {"FINISHED"}


#  -> 导出地图
class OT_ExportMap(bpy.types.Operator):
    bl_idname = "amagate.exportmap"
    bl_label = "Export Map"
    bl_description = "Export Blade Map"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        # self.report({'WARNING'}, "Export Failed")
        self.report({"INFO"}, "Export Success")
        return {"FINISHED"}


############################
############################
############################

classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and issubclass(cls, bpy.types.Operator)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
