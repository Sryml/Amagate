import sys
import os
from typing import Any

import bpy
from bpy.app.translations import pgettext
from bpy.props import PointerProperty

from . import data

"""
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
"""


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

        # 已经使用的ID
        used_ids = set(a.id for a in scene_data.atmospheres)

        new_atmo = scene_data.atmospheres.add()
        id_ = 1
        while id_ in used_ids:
            id_ += 1
        new_atmo.id = id_

        # 创建空物体 用来判断引用
        obj = bpy.data.objects.new(f"{scene.name}_atmo_{id_}", None)
        obj["id"] = id_
        new_atmo.atmo_obj = obj

        # 给大气命名
        name = f"atmo{id_}"
        names = set(a.name for a in scene_data.atmospheres)
        while name in names:
            id_ += 1
            name = f"atmo{id_}"
        new_atmo.name = name

        scene_data.active_atmosphere = len(scene_data.atmospheres) - 1

    def execute(self, context: bpy.types.Context):
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


############################
############################ 纹理面板
############################
class OT_Texture_Add(bpy.types.Operator):
    bl_idname = "amagate.texture_add"
    bl_label = "Add Texture"
    bl_description = "Hold shift to enable overlay"
    bl_options = {"INTERNAL"}

    # 过滤文件
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_image: bpy.props.BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    # filter_glob: bpy.props.StringProperty(default="*.jpg;*.png;*.jpeg;*.bmp;*.tga", options={"HIDDEN"})  # type: ignore

    # 相对路径
    relative_path: bpy.props.BoolProperty(name="Relative Path", default=True)  # type: ignore
    # 覆盖模式
    override: bpy.props.BoolProperty(name="Override Mode", default=False)  # type: ignore
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: bpy.props.StringProperty()  # type: ignore
    directory: bpy.props.StringProperty()  # type: ignore
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    def get_id(self):
        # 已经使用的ID
        used_ids = set(i.amagate_data.id for i in bpy.data.images)  # type: ignore
        id_ = 1
        while id_ in used_ids:
            id_ += 1
        return id_

    def load_image(self, context, filepath, name=""):
        scene_data = context.scene.amagate_data  # type: ignore
        img = bpy.data.images.load(filepath)
        img_data = img.amagate_data  # type: ignore
        if name:
            img.name = name

        img_data.id = self.get_id()

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
                        img.amagate_data.id = self.get_id()  # type: ignore
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

    reload_all: bpy.props.BoolProperty(name="Reload All", default=False)  # type: ignore

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

    shift: bpy.props.BoolProperty(default=False)  # type: ignore
    select_operation: bpy.props.EnumProperty(  # type: ignore
        name="",
        description="Select Operation",
        items=[
            ("pack_all", "Pack All", ""),
            ("unpack_all", "Unpack All", ""),
        ],
        default="pack_all",  # 默认选项
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.alignment = "CENTER"
        row.prop(self, "select_operation", text="Select Operation")

    def execute(self, context):
        scene_data = context.scene.amagate_data  # type: ignore
        # 如果未打开blend文件，则使用原始路径
        m = "USE_LOCAL" if bpy.data.filepath else "USE_ORIGINAL"
        if self.shift:
            for img in bpy.data.images:
                if img.amagate_data.id and img.name != "NULL":  # type: ignore
                    if self.select_operation == "pack_all":
                        if not img.packed_file:
                            img.pack()
                    else:
                        if img.packed_file:
                            img.unpack(method=m)
        else:
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

    def invoke(self, context, event):
        self.shift = event.shift
        if event.shift:
            # TODO 批量打包弹窗改成弹出列表，点击列表项直接执行对应操作
            return context.window_manager.invoke_props_dialog(self)  # type: ignore
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
############################
############################


# 场景面板 -> 默认属性面板
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


# 场景面板 -> 新建场景
class OT_NewScene(bpy.types.Operator):
    bl_idname = "amagate.newscene"
    bl_label = "New Scene"
    bl_description = "Create a new Blade Scene"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        # 获取场景名
        name = "Blade Scene"
        num = 0
        names = set(s.name for s in bpy.data.scenes)
        while name in names:
            num += 1
            name = f"Blade Scene {num}"

        # 创建新场景
        # bpy.ops.scene.new()
        scene = bpy.data.scenes.new(name)

        # 初始化场景数据
        scene.amagate_data.is_blade = True  # type: ignore
        OT_Scene_Atmo_Add.new(scene)
        scene.amagate_data.init()  # type: ignore

        # TODO 添加默认摄像机 添加默认扇区 划分界面布局 调整视角

        context.window.scene = scene  # type: ignore
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
