# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations
from typing import Any, TYPE_CHECKING

import bpy
import bmesh
from bpy.app.translations import pgettext


from . import data
from . import operator as OP
from . import entity_operator as OP_ENTITY
from . import ag_utils

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection


class AG_Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"


############################
############################ py包安装面板
############################
class AMAGATE_PT_PyPackages(AG_Panel, bpy.types.Panel):
    bl_label = "Python Packages"
    bl_order = -1
    # bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return not data.PY_PACKAGES_INSTALLED

    def draw(self, context: Context):
        scene_data = context.scene.amagate_data

        layout = self.layout
        col = layout.column()

        if data.PY_PACKAGES_INSTALLING:
            # col.alert = True
            col.label(text="Installing Python packages...", icon="CONSOLE")
            col.progress(
                factor=scene_data.progress_bar.pyp_install_progress, type="BAR"
            )
        else:
            col.alert = True
            col.label(text="Failed to install Python packages,", icon="ERROR")
            col.label(text="please try again!")
            col.alert = False
            col.operator(OP.OT_InstallPyPackages.bl_idname)


############################
############################ 实体编辑面板
############################


class AMAGATE_PT_EntityEdit(AG_Panel, bpy.types.Panel):
    bl_label = "Entity Editor"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 1

    def draw(self, context: Context):
        layout = self.layout
        wm_data = context.window_manager.amagate_data

        # 创建集合
        layout.operator(OP_ENTITY.OT_CreateColl.bl_idname, icon="COLLECTION_NEW")

        row = layout.row(align=True)
        # 添加锚点
        row.operator_menu_enum(OP_ENTITY.OT_AddAnchor.bl_idname, "action")
        # 添加组件
        row.operator_menu_enum(OP_ENTITY.OT_AddComponent.bl_idname, "action")

        # 组
        box = layout.box()
        box.enabled = context.mode == "EDIT_MESH"
        column = box.column(align=True)
        column.label(text=f"{pgettext('Groups')}:")
        col_flow = column.grid_flow(row_major=True, columns=8, align=True)
        if context.mode == "EDIT_MESH":
            obj = context.object
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            bm = bmesh.from_edit_mesh(mesh)
            layer_name = "amagate_group"
            layer = bm.faces.layers.int.get(layer_name)
            if layer is None:
                layer = bm.faces.layers.int.new(layer_name)
                bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
            faces = [f for f in bm.faces if f.select]
        else:
            faces = []
        for i in range(32):
            flag = ""
            col_flow.alert = False
            if faces:
                group = ag_utils.int_to_uint(faces[0][layer])  # type: ignore
                check = (group >> i) & 1  # 访问第i位
                for f in faces:
                    group = ag_utils.int_to_uint(f[layer])  # type: ignore
                    if (group >> i) & 1 != check:
                        flag = "*"
                        col_flow.alert = True
                        break
            #
            col_flow.prop(
                wm_data.ent_groups[i],
                "value",
                text=f"{i+1}{flag}",
                toggle=True,
            )
        # 按组选择
        box.operator_menu_enum(OP_ENTITY.OT_SelectByGroup.bl_idname, "action")

        # 肢解组
        box = layout.box()
        column = box.column(align=True)
        column.label(text=f"{pgettext('Mutilation Groups')}:")
        col_flow = column.grid_flow(row_major=True, columns=8, align=True)
        if context.mode == "EDIT_MESH":
            obj = context.object
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            box.enabled = next(
                (True for m in obj.modifiers if m.type == "ARMATURE"), False
            )

            bm = bmesh.from_edit_mesh(mesh)
            layer_name = "amagate_mutilation_group"
            layer = bm.faces.layers.int.get(layer_name)
            if layer is None:
                layer = bm.faces.layers.int.new(layer_name)
                bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
            faces = [f for f in bm.faces if f.select]
        else:
            box.enabled = False
            faces = []
        for i in range(32):
            flag = ""
            col_flow.alert = False
            if faces:
                group = ag_utils.int_to_uint(faces[0][layer])  # type: ignore
                check = (group >> i) & 1  # 访问第i位
                for f in faces:
                    group = ag_utils.int_to_uint(f[layer])  # type: ignore
                    if (group >> i) & 1 != check:
                        flag = "*"
                        col_flow.alert = True
                        break
            #
            col_flow.prop(
                wm_data.ent_mutilation_groups[i],
                "value",
                text=f"{i+1}{flag}",
                toggle=True,
            )
        # 按肢解组选择
        box.operator_menu_enum(OP_ENTITY.OT_SelectByMutilateGroup.bl_idname, "action")

        # 实体说明
        layout.operator(OP_ENTITY.OT_EntityNote.bl_idname, icon="INFO")

        layout.separator(type="LINE")

        # 导出
        row = layout.row(align=True)
        row.operator(OP_ENTITY.OT_ExportBOD.bl_idname, icon="EXPORT").main = True  # type: ignore
        row.operator_menu_enum(OP_ENTITY.OT_ExportBOD.bl_idname, "action", text="", icon="DOWNARROW_HLT").main = False  # type: ignore
        # 导入
        layout.operator(OP_ENTITY.OT_ImportBOD.bl_idname, icon="IMPORT")


############################
############################ 坐标转换面板
############################
class AMAGATE_PT_CoordConver(AG_Panel, bpy.types.Panel):
    bl_label = "Coord Conver"
    bl_order = 1

    def draw(self, context: Context):
        scene_data = context.scene.amagate_data
        layout = self.layout
        col = layout.column()

        col.label(text="Convert selected object/cursor", icon="FILE_REFRESH")
        col.prop(scene_data, "coord_conv_1", text=f"{pgettext('To')} Blade")
        col.prop(scene_data, "coord_conv_2", text=f"{pgettext('From')} Blade")


############################
############################ Cubemap转换面板
############################


class AMAGATE_PT_Cubemap(AG_Panel, bpy.types.Panel):
    bl_label = "Cubemap Conver"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 1

    def draw(self, context: Context):
        scene_data = context.scene.amagate_data
        preferences = context.preferences.addons[data.PACKAGE].preferences  # type: ignore
        layout = self.layout

        col = layout.column()
        col.label(text=f"{pgettext('Export as panorama')}:")
        col.prop(preferences, "cubemap_out_format", text="Format")
        col.prop(preferences, "cubemap_out_res", text="Resolution")
        col = layout.column(align=True)
        # col.use_property_split = True
        col.prop(preferences, "cubemap_out_res_x", text="X")
        col.prop(preferences, "cubemap_out_res_y", text="Y")
        col = layout.column()
        col.operator(OP.OT_Cubemap2Equirect.bl_idname, icon="EXPORT")


############################
############################ 工具面板
############################


# class AMAGATE_PT_Tools(AG_Panel, bpy.types.Panel):
#     bl_label = "Tools"
#     bl_order = 1

#     def draw(self, context: Context):
#         layout = self.layout
#         column = layout.column()


############################
############################ 关于面板
############################
class AMAGATE_PT_About(AG_Panel, bpy.types.Panel):
    bl_label = "About"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 99

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Version:", icon="INFO")
        col.label(text=f"{data.VERSION}")
        col.label(text=f"Amagate {data.Copyright}")
        col.operator("wm.url_open", text="Amagate on Github", icon="URL").url = "https://github.com/Sryml/Amagate"  # type: ignore


############################
############################ 调试面板
############################
class AMAGATE_PT_Debug(AG_Panel, bpy.types.Panel):
    bl_label = "Debug"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 99

    @classmethod
    def poll(cls, context):
        return data.DEBUG

    def draw(self, context):
        from . import L3D_operator as OP_L3D

        layout = self.layout

        col = layout.column()
        col.operator(OP.OT_ReloadAddon.bl_idname, icon="FILE_REFRESH")
        col.operator(OP.OT_ExportNode.bl_idname)
        col.operator(OP.OT_ExportEntComponent.bl_idname)
        # col.operator(OP.OT_ImportNode.bl_idname)
        # col.operator(OP.OT_Test.bl_idname)
        col.operator_menu_enum(OP.OT_Test.bl_idname, "action")
        col.operator_menu_enum(
            OP_L3D.OT_SetAsPrefab.bl_idname,
            "action",
        ).builtin = True  # type: ignore
        #
        # col.operator(OP.OT_Test.bl_idname, icon="EMPTY_SINGLE_ARROW")
        # col.operator(OP.OT_Test.bl_idname, icon="EMPTY_ARROWS")
        # col.operator(OP.OT_Test.bl_idname, icon="EVENT_LEFT_ARROW")
        # col.operator(OP.OT_Test.bl_idname, icon="EVENT_DOWN_ARROW")
        # col.operator(OP.OT_Test.bl_idname, icon="EVENT_DOWN_ARROW")
        # col.operator(OP.OT_Test.bl_idname, icon="EVENT_DOWN_ARROW")


############################
############################
############################

classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and issubclass(cls, bpy.types.Panel)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    from . import L3D_panel

    L3D_panel.register()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    from . import L3D_panel

    L3D_panel.unregister()
