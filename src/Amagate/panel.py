# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations
from typing import Any, TYPE_CHECKING

import bpy
from bpy.app.translations import pgettext

# from bpy.types import Context

from . import data
from . import operator as OP
from .scripts import ag_utils

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


class N_Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"

    @classmethod
    def poll(cls, context: Context):
        # 自定义条件，仅在blade场景中显示
        return context.scene.amagate_data.is_blade


############################
############################ 场景面板
############################
class AMAGATE_PT_Scene(N_Panel, bpy.types.Panel):
    bl_label = "Blade Scene"
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return True

    def __init__(self):
        super().__init__()
        data.ensure_null_texture()

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        # 场景状态
        if not scene_data.is_blade:
            row = layout.row(align=True)
            row.alignment = "LEFT"
            # row.enabled = False
            row.label(text=f"{pgettext('Status')}: {pgettext('Non-Blade scene')}")
            # col = row.column()
            # col.enabled = False
            # col.prop(scene_data, "is_blade", text="")
            # layout.operator(OP.OT_NewScene.bl_idname, icon="ADD")
            # return


# 场景面板 -> 新建面板
# class AMAGATE_PT_NewScene(N_Panel, bpy.types.Panel):
#     bl_label = "New"
#     bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
#     bl_options = {"HIDE_HEADER"}

#     @classmethod
#     def poll(cls, context):
#         return True
#         # return not context.scene.amagate_data.is_blade  # type: ignore

#     def draw(self, context):
#         layout = self.layout
#         layout.separator()
#         # 新建场景按钮
#         op = layout.operator(
#             OP.OT_NewScene.bl_idname, text="New Map", icon_value=data.ICONS["blade"].icon_id
#         )
#         op.target = "init"  # type: ignore
#         op.execute_type = 0  # type: ignore


# 场景面板 -> 大气面板
class AMAGATE_PT_Scene_Atmosphere(N_Panel, bpy.types.Panel):
    bl_label = "Atmosphere"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    # bl_options = {"HIDE_HEADER"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        # 显示大气列表
        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.label(text=f"{pgettext('Total')}: {len(scene_data.atmospheres)}")

        # 创建滚动区域来显示最多 3 个大气项
        row = layout.row(align=True)
        # row = row.split(factor=0.9)
        col = row.column()
        col.template_list(
            "AMAGATE_UI_UL_AtmoList",
            "atmosphere_list",
            scene_data,
            "atmospheres",
            scene_data,
            "active_atmosphere",
            rows=3,
            maxrows=3,
        )

        # 添加按钮放置在右侧
        col = row.column(align=True)
        col.operator(OP.OT_Scene_Atmo_Add.bl_idname, text="", icon="ADD")
        col.operator(OP.OT_Scene_Atmo_Remove.bl_idname, text="", icon="X")
        # col.separator(factor=3)
        col.label(icon="BLANK1")
        col.operator(
            OP.OT_Scene_Atmo_Default.bl_idname,
            text="",
            icon_value=data.ICONS["star"].icon_id,
        )


# 场景面板 -> 外部光面板
class AMAGATE_PT_Scene_ExternalLight(N_Panel, bpy.types.Panel):
    bl_label = "External Light"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data: data.SceneProperty = context.scene.amagate_data

        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.label(text=f"{pgettext('Total')}: {len(scene_data.externals)}")

        row = layout.row(align=True)
        col = row.column()
        col.template_list(
            "AMAGATE_UI_UL_ExternalLight",
            "",
            scene_data,
            "externals",
            scene_data,
            "active_external",
            rows=3,
            maxrows=3,
        )

        # 添加按钮放置在右侧
        col = row.column(align=True)
        col.operator(OP.OT_Scene_External_Add.bl_idname, text="", icon="ADD")
        col.operator(OP.OT_Scene_External_Remove.bl_idname, text="", icon="X")
        col.label(icon="BLANK1")
        col.operator(OP.OT_Scene_External_Default.bl_idname, text="", icon_value=data.ICONS["star"].icon_id)  # type: ignore


############################
############################ 纹理面板
############################
class AMAGATE_PT_Texture(N_Panel, bpy.types.Panel):
    bl_label = "Textures"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    def __init__(self):
        super().__init__()
        data.ensure_null_texture()

    def draw(self, context: Context):
        layout = self.layout
        scene_data: data.SceneProperty = context.scene.amagate_data
        images = bpy.data.images

        # 显示纹理列表
        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.label(
            text=f"{pgettext('Total')}: {[bool(i.amagate_data.id) for i in images].count(True)}"  # type: ignore
        )

        row = layout.row(align=True)
        col = row.column()
        col.template_list(
            "AMAGATE_UI_UL_TextureList",
            "texture_list",
            bpy.data,
            "images",
            scene_data,
            "active_texture",
            rows=5,
            maxrows=7,
        )

        # 添加按钮放置在右侧
        col = row.column(align=True)
        col.operator(OP.OT_Texture_Add.bl_idname, text="", icon="ADD")
        col.operator(OP.OT_Texture_Remove.bl_idname, text="", icon="X")
        col.separator()

        col.operator(
            OP.OT_Texture_Default.bl_idname,
            text="",
            icon_value=data.ICONS["star"].icon_id,
        )
        col.separator()

        col.operator(OP.OT_Texture_Reload.bl_idname, text="", icon="FILE_REFRESH")
        col.operator(OP.OT_Texture_Package.bl_idname, text="", icon="UGLYPACKAGE")


# 场景面板 -> 默认属性面板
class AMAGATE_PT_Scene_Default(N_Panel, bpy.types.Panel):
    bl_label = "Default Properties"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"DEFAULT_CLOSED"}  # 默认折叠

    def draw(self, context: Context):
        layout = self.layout
        # layout.use_property_split = True
        # layout.use_property_decorate = False
        scene_data: data.SceneProperty = context.scene.amagate_data

        # 大气
        # layout.prop_search(scene_data.defaults, "atmo", scene_data, "atmospheres", text="Atmosphere")
        atmo_idx, atmo = data.get_atmo_by_id(scene_data, scene_data.defaults.atmo_id)

        row = layout.row()
        split = row.split(factor=0.7)
        row = split.row()

        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Atmosphere')}:")

        col = row.column()
        name = "None" if not atmo else atmo.item_name
        op = col.operator(
            OP.OT_Atmo_Select.bl_idname,
            text=name,
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "Scene"  # type: ignore
        op.prop["_index"] = atmo_idx  # type: ignore

        if atmo:
            row = split.row()
            row.enabled = False
            row.prop(atmo, "color", text="")

        layout.separator()

        box = layout.box()
        # 地板 天花板 墙壁
        for i, prop in enumerate(scene_data.defaults.textures):
            name = prop.name

            tex_id = prop.id
            tex_idx, tex = data.get_texture_by_id(tex_id)

            column = box.column()
            #
            row = column.row()

            col = row.column()
            col.alignment = "LEFT"
            col.label(text=f"{pgettext(name, 'Property')}:")

            col = row.column()
            tex_name = "None" if not tex else tex.name
            op = col.operator(
                OP.OT_Texture_Select.bl_idname, text=tex_name, icon="DOWNARROW_HLT"
            )
            op.prop.target = prop.target  # type: ignore
            op.prop.name = prop.name  # type: ignore
            op.prop["_index"] = tex_idx  # type: ignore

            if tex and tex.preview:
                col = row.column()
                op = col.operator(
                    OP.OT_Texture_Preview.bl_idname,
                    text="",
                    icon_value=tex.preview.icon_id,
                    emboss=False,
                )
                op.index = bpy.data.images.find(tex.name)  # type: ignore
            #
            row = column.row(align=True)
            row.prop(prop, "xpos", text="X")
            row.prop(prop, "ypos", text="Y")
            # row.prop(scene_data.defaults.texture, "pos", index=-1, text="")
            # row.prop(prop, "pos", index=0, text="X")
            # row.separator()
            # row.prop(prop, "pos", index=1, text="Y")

            row = column.row()
            row.prop(prop, "angle", text="Angle")

            box2 = column.box()
            row = box2.row()
            col = row.column(align=True)
            col.prop(prop, "xzoom", text=f"X {pgettext('Zoom')}")
            col.prop(prop, "yzoom", text=f"Y {pgettext('Zoom')}")
            col = row.column()
            col.scale_y = 2
            col.prop(
                prop,
                "zoom_constraint",
                text="",
                icon="LINKED" if prop.zoom_constraint else "UNLINKED",
                emboss=False,
            )

            if i != len(scene_data.defaults.textures) - 1:
                box.separator(type="LINE")

        layout.separator()

        box = layout.box()
        column = box.column(align=True)
        # 外部光
        idx, item = data.get_external_by_id(scene_data, scene_data.defaults.external_id)

        row = column.row()
        split = row.split(factor=0.7)
        row = split.row()

        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('External Light')}:")

        col = row.column()
        name = "None" if not item else item.item_name
        op = col.operator(
            OP.OT_External_Select.bl_idname,
            text=name,
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "Scene"  # type: ignore
        op.prop["_index"] = idx  # type: ignore

        if item:
            row = split.row()
            row.prop(item, "color_readonly", text="")

        column.separator(factor=2, type="LINE")

        # 环境光
        row = column.row()
        split = row.split(factor=0.5)
        row = split.row()
        row.alignment = "LEFT"
        row.label(text=f"{pgettext('Ambient Light')}:")
        split.prop(scene_data.defaults, "ambient_color", text="")

        column.separator(factor=2, type="LINE")

        # 平面光
        row = column.row()
        split = row.split(factor=0.5)
        row = split.row()
        row.alignment = "LEFT"
        row.label(text=f"{pgettext('Flat Light')}:")
        split.prop(scene_data.defaults.flat_light, "color", text="")

        column.separator(type="SPACE")
        row = column.row()
        row.prop(scene_data.defaults.flat_light, "vector", text="")


############################
############################ 扇区面板
############################
"""
class AMAGATE_PT_Sector_E(N_Panel, bpy.types.Panel):
    bl_label = "Sector"

    @classmethod
    def poll(cls, context: Context):
        if not context.scene.amagate_data.is_blade:  # type: ignore
            return False

        for obj in context.selected_objects:
            if obj.amagate_data.is_sector:  # type: ignore
                return False
        return True

    def draw(self, context: Context):
        layout = self.layout

        col = layout.column(align=True)
        # 扇区数量
        col.label(
            text=f"{pgettext('Selected sector')}: 0 / {len(context.selected_objects)}"
        )

        col.operator(OP.OT_Sector_Convert.bl_idname, icon="MESH_CUBE")
"""


class AMAGATE_PT_Sector(N_Panel, bpy.types.Panel):
    bl_label = "Sector"
    # bl_options = {"DEFAULT_CLOSED"}

    def __init__(self):
        super().__init__()
        data.ensure_null_texture()

    def draw(self, context: Context):
        layout = self.layout
        scene_data: data.SceneProperty = context.scene.amagate_data

        selected_sectors = data.SELECTED_SECTORS

        col = layout.column()
        # 扇区数量
        col.label(
            text=f"{pgettext('Selected Sector')}: {len(selected_sectors)} / {len(context.selected_objects)}"
        )

        col.operator(OP.OT_Sector_Convert.bl_idname, icon="MESH_CUBE")
        col.operator(OP.OT_Sector_Connect.bl_idname, icon="AREA_JOIN").is_button = True  # type: ignore


class AMAGATE_PT_Sector_Props(N_Panel, bpy.types.Panel):
    bl_label = "Properties"
    bl_parent_id = "AMAGATE_PT_Sector"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context: Context):
        for obj in context.selected_objects:
            if obj.amagate_data.is_sector:  # type: ignore
                return True
        data.SELECTED_SECTORS = []
        data.ACTIVE_SECTOR = None
        return False

    def draw(self, context: Context):
        #
        selected_sectors, active_sector = ag_utils.get_selected_sectors()

        data.SELECTED_SECTORS = selected_sectors
        data.ACTIVE_SECTOR = active_sector
        #

        layout = self.layout
        scene_data = context.scene.amagate_data
        active_sec_data = active_sector.amagate_data.get_sector_data()

        # 大气
        atmo_id = active_sec_data.atmo_id
        is_uniform = True
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.atmo_id != atmo_id:
                atmo_id = None
                is_uniform = False
                break
        if is_uniform:
            atmo_idx, atmo = data.get_atmo_by_id(scene_data, atmo_id)
            name = "None" if not atmo else atmo.item_name
        else:
            atmo_idx, atmo = -1, None
            name = "*"

        row = layout.row()
        split = row.split(factor=0.7)
        row = split.row()

        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Atmosphere')}:")

        col = row.column()
        op = col.operator(
            OP.OT_Atmo_Select.bl_idname,
            text=name,
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "SectorPublic"  # type: ignore
        op.prop["_index"] = atmo_idx  # type: ignore

        if atmo:
            row = split.row()
            row.enabled = False
            row.prop(atmo, "color", text="")
        elif not is_uniform:
            row = split.row()
            row.alignment = "CENTER"
            row.label(text="non-uniform")

        layout.separator()

        box = layout.box()
        if active_sector.mode == "OBJECT":
            # 地板 天花板 墙壁
            for i, prop in enumerate(scene_data.sector_public.textures):
                name = prop.name

                tex_id = active_sec_data.textures[name].id
                xpos = active_sec_data.textures[name].xpos
                ypos = active_sec_data.textures[name].ypos
                angle = active_sec_data.textures[name].angle
                xzoom = active_sec_data.textures[name].xzoom
                yzoom = active_sec_data.textures[name].yzoom
                is_tex_uniform = True
                is_xpos_uniform = True
                is_ypos_uniform = True
                is_angle_uniform = True
                is_xzoom_uniform = True
                is_yzoom_uniform = True

                for sec in selected_sectors:
                    sec_data = sec.amagate_data.get_sector_data()
                    # 检查纹理是否一致
                    if is_tex_uniform and sec_data.textures[name].id != tex_id:
                        tex_id = None
                        is_tex_uniform = False
                    # 检查x位置是否一致
                    if is_xpos_uniform and sec_data.textures[name].xpos != xpos:
                        xpos = None
                        is_xpos_uniform = False
                    # 检查y位置是否一致
                    if is_ypos_uniform and sec_data.textures[name].ypos != ypos:
                        ypos = None
                        is_ypos_uniform = False
                    # 检查角度是否一致
                    if is_angle_uniform and sec_data.textures[name].angle != angle:
                        angle = None
                        is_angle_uniform = False
                    # 检查x缩放是否一致
                    if is_xzoom_uniform and sec_data.textures[name].xzoom != xzoom:
                        xzoom = None
                        is_xzoom_uniform = False
                    # 检查y缩放是否一致
                    if is_yzoom_uniform and sec_data.textures[name].yzoom != yzoom:
                        yzoom = None
                        is_yzoom_uniform = False

                if is_tex_uniform:
                    tex_idx, tex = data.get_texture_by_id(tex_id)
                    tex_name = "None" if not tex else tex.name
                else:
                    tex_idx, tex = -1, None
                    tex_name = "*"

                column = box.column()
                #
                row = column.row()

                col = row.column()
                col.alignment = "LEFT"
                col.label(text=f"{pgettext(name, 'Property')}:")

                col = row.column()
                op = col.operator(
                    OP.OT_Texture_Select.bl_idname, text=tex_name, icon="DOWNARROW_HLT"
                )
                op.prop.target = prop.target  # type: ignore
                op.prop.name = prop.name  # type: ignore
                op.prop["_index"] = tex_idx  # type: ignore

                if tex and tex.preview:
                    col = row.column()
                    op = col.operator(
                        OP.OT_Texture_Preview.bl_idname,
                        text="",
                        icon_value=tex.preview.icon_id,
                        emboss=False,
                    )
                    op.index = bpy.data.images.find(tex.name)  # type: ignore
                elif not is_tex_uniform:
                    col = row.column()
                    col.label(icon_value=1)
                #
                row = column.row(align=True)
                x_text = "X" if is_xpos_uniform else "X *"
                y_text = "Y" if is_ypos_uniform else "Y *"
                row.prop(prop, "xpos", text=x_text)
                row.prop(prop, "ypos", text=y_text)

                row = column.row()
                text = "Angle" if is_angle_uniform else f"{pgettext('Angle')} *"
                row.prop(prop, "angle", text=text)

                box2 = column.box()
                row = box2.row()
                col = row.column(align=True)
                x_text = f"X {pgettext('Zoom')}"
                if not is_xzoom_uniform:
                    x_text = f"{x_text} *"
                y_text = f"Y {pgettext('Zoom')}"
                if not is_yzoom_uniform:
                    y_text = f"{y_text} *"
                col.prop(prop, "xzoom", text=x_text)
                col.prop(prop, "yzoom", text=y_text)
                col = row.column()
                col.scale_y = 2
                col.prop(
                    prop,
                    "zoom_constraint",
                    text="",
                    icon="LINKED" if prop.zoom_constraint else "UNLINKED",
                    emboss=False,
                )

                if i != len(scene_data.sector_public.textures) - 1:
                    box.separator(type="LINE")

        else:
            ...

        layout.separator()

        box = layout.box()
        column = box.column(align=True)
        # 外部光
        # idx, item = data.get_external_by_id(scene_data, scene_data.defaults.external_id)

        # row = column.row()
        # split = row.split(factor=0.7)
        # row = split.row()

        # col = row.column()
        # col.alignment = "LEFT"
        # col.label(text=f"{pgettext('External Light')}:")

        # col = row.column()
        # name = "None" if not item else item.item_name
        # op = col.operator(
        #     OP.OT_External_Select.bl_idname,
        #     text=name,
        #     icon="DOWNARROW_HLT",
        # )  # COLLAPSEMENU
        # op.prop.target = "Scene"  # type: ignore
        # op.prop["_index"] = idx  # type: ignore

        # if item:
        #     row = split.row()
        #     row.prop(item, "color_readonly", text="")

        # column.separator(factor=2,type="LINE")

        # 环境光
        is_uniform = True
        ambient_color = active_sec_data.ambient_color
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.ambient_color != ambient_color:
                is_uniform = False
                break

        row = column.row()
        split = row.split(factor=0.5)
        row = split.row(align=True)
        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Ambient Light')}:")
        if not is_uniform:
            col = row.column()
            col.alignment = "RIGHT"
            col.label(text="*")
        split.prop(scene_data.sector_public, "ambient_color", text="")

        column.separator(factor=2, type="LINE")

        # 平面光
        # row = column.row()
        # split = row.split(factor=0.5)
        # row = split.row()
        # row.alignment = "LEFT"
        # row.label(text=f"{pgettext('Flat Light')}:")
        # split.prop(scene_data.defaults.flat_light, "color", text="")

        # column.separator(type="SPACE")
        # row = column.row()
        # row.prop(scene_data.defaults.flat_light, "vector", text="")


############################
############################ 工具面板
############################
class AMAGATE_PT_Tools(N_Panel, bpy.types.Panel):
    bl_label = "Tools"
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        row = layout.row(align=True)
        op = row.operator(
            OP.OT_New.bl_idname, text="New Map", icon_value=data.ICONS["blade"].icon_id
        )
        op.target = "new"  # type: ignore
        op.execute_type = 0  # type: ignore

        row = layout.row(align=True)
        row.enabled = scene_data.is_blade
        row.operator(OP.OT_ExportMap.bl_idname, icon="EXPORT")


############################
############################ 关于面板
############################
class AMAGATE_PT_About(N_Panel, bpy.types.Panel):
    bl_label = "About"
    bl_options = {"DEFAULT_CLOSED"}

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
class AMAGATE_PT_Debug(N_Panel, bpy.types.Panel):
    bl_label = "Debug"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return data.DEBUG

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator(OP.OT_ReloadAddon.bl_idname, icon="FILE_REFRESH")
        col.operator(OP.OT_ExportNode.bl_idname)
        col.operator(OP.OT_ImportNode.bl_idname)
        col.operator(OP.OT_Test.bl_idname)


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


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
