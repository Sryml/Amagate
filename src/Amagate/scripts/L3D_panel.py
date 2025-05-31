# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations
from typing import Any, TYPE_CHECKING

import bpy
import bmesh
from bpy.app.translations import pgettext


from . import data, L3D_data
from . import L3D_operator as OP_L3D
from . import L3D_ext_operator as OP_L3D_EXT
from . import sector_operator as OP_SECTOR
from . import ag_utils

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


class L3D_Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"

    @classmethod
    def poll(cls, context: Context):
        # 自定义条件，仅在blade场景中显示
        return context.scene.amagate_data.is_blade


############################
############################ L3D面板
############################
class AMAGATE_PT_L3D(L3D_Panel, bpy.types.Panel):
    bl_label = "L3D"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return data.PY_PACKAGES_INSTALLED

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text="", icon_value=data.ICONS["L3D"].icon_id)  # 图标
        # row.label(text=self.bl_label)          # 文字

    def draw(self, context: Context):
        layout = self.layout


############################
############################ 场景面板
############################
class AMAGATE_PT_Scene(L3D_Panel, bpy.types.Panel):
    bl_label = "Scene"
    bl_parent_id = "AMAGATE_PT_L3D"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return data.PY_PACKAGES_INSTALLED

    # 在4.4版本中会出错，已用其它方案实现
    # def __init__(self):
    #     super().__init__()
    #     data.ensure_null_texture()

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


# 场景面板 -> 属性面板
class AMAGATE_PT_Scene_Properties(L3D_Panel, bpy.types.Panel):
    bl_label = "Properties"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"HIDE_HEADER"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data
        col = layout.column()

        row = col.row(align=True)
        row.alignment = "LEFT"
        area_index = next(
            i for i, a in enumerate(context.screen.areas) if a == context.area
        )
        icon = (
            "CHECKBOX_HLT"
            if scene_data.areas_show_hud.get(str(area_index))
            else "CHECKBOX_DEHLT"
        )
        row.operator(OP_L3D.OT_Scene_Props_HUD.bl_idname, emboss=False, icon=icon)


# 场景面板 -> 大气面板
class AMAGATE_PT_Scene_Atmosphere(L3D_Panel, bpy.types.Panel):
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
        col.operator(OP_L3D.OT_Scene_Atmo_Add.bl_idname, text="", icon="ADD")
        col.operator(OP_L3D.OT_Scene_Atmo_Remove.bl_idname, text="", icon="X")
        # col.separator(factor=3)
        col.label(icon="BLANK1")
        col.operator(
            OP_L3D.OT_Scene_Atmo_Default.bl_idname,
            text="",
            icon_value=data.ICONS["star"].icon_id,
        )


# 场景面板 -> 外部光面板
class AMAGATE_PT_Scene_ExternalLight(L3D_Panel, bpy.types.Panel):
    bl_label = "External Light"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

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
        col.operator(OP_L3D.OT_Scene_External_Add.bl_idname, text="", icon="ADD")
        col.operator(OP_L3D.OT_Scene_External_Remove.bl_idname, text="", icon="X")
        col.label(icon="BLANK1")
        col.operator(OP_L3D.OT_Scene_External_Default.bl_idname, text="", icon_value=data.ICONS["star"].icon_id)  # type: ignore


############################
############################ 纹理面板
############################
class AMAGATE_PT_Texture(L3D_Panel, bpy.types.Panel):
    bl_label = "Textures"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    # 在4.4版本中会出错，已用其它方案实现
    # def __init__(self):
    #     super().__init__()
    #     data.ensure_null_texture()

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data
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
        col.operator(OP_L3D.OT_Texture_Add.bl_idname, text="", icon="ADD")
        col.operator(OP_L3D.OT_Texture_Remove.bl_idname, text="", icon="X")
        col.separator()

        col.operator(
            OP_L3D.OT_Texture_Default.bl_idname,
            text="",
            icon_value=data.ICONS["star"].icon_id,
        )
        col.separator()

        col.operator(OP_L3D.OT_Texture_Reload.bl_idname, text="", icon="FILE_REFRESH")
        col.operator(OP_L3D.OT_Texture_Package.bl_idname, text="", icon="UGLYPACKAGE")


############################
############################ 天空纹理面板
############################
class AMAGATE_PT_SkyTexture(L3D_Panel, bpy.types.Panel):
    bl_label = "Sky Texture"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        row = layout.row()
        split = row.split(factor=0.7)
        #
        row1 = split.row(align=True)

        col = row1.column()
        col.prop(scene_data, "sky_tex_enum", text="")

        col = row1.column()
        col.operator(OP_L3D.OT_SkyTexture_Open.bl_idname, text="", icon="FILEBROWSER")
        col.enabled = scene_data.sky_tex_enum == "-1"
        #
        row2 = split.row()
        row2.prop(scene_data, "sky_color", text="")


# 场景面板 -> 默认属性面板
class AMAGATE_PT_Scene_Default(L3D_Panel, bpy.types.Panel):
    bl_label = "Default Properties"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"DEFAULT_CLOSED"}  # 默认折叠

    def draw(self, context: Context):
        layout = self.layout
        # layout.use_property_split = True
        # layout.use_property_decorate = False
        scene_data = context.scene.amagate_data

        # 大气
        # layout.prop_search(scene_data.defaults, "atmo", scene_data, "atmospheres", text="Atmosphere")
        atmo_idx, atmo = L3D_data.get_atmo_by_id(
            scene_data, scene_data.defaults.atmo_id
        )

        row = layout.row()
        split = row.split(factor=0.7)
        row = split.row()

        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Atmosphere')}:")

        col = row.column()
        name = "None" if not atmo else atmo.item_name
        op = col.operator(
            OP_L3D.OT_Atmo_Select.bl_idname,
            text=name,
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "Scene"  # type: ignore
        op.prop["_index"] = atmo_idx  # type: ignore

        if atmo:
            row = split.row()
            # row.enabled = False
            row.prop(atmo, "color", text="")

        layout.separator()

        box = layout.box()
        # 地板 天花板 墙壁
        for i, prop in enumerate(scene_data.defaults.textures):
            name = prop.name

            tex_id = prop.id
            tex_idx, tex = L3D_data.get_texture_by_id(tex_id)

            column = box.column()
            #
            row = column.row()

            col = row.column()
            col.alignment = "LEFT"
            col.label(text=f"{pgettext(name, 'Property')}:")

            col = row.column()
            tex_name = "None" if not tex else tex.name
            op = col.operator(
                OP_L3D.OT_Texture_Select.bl_idname, text=tex_name, icon="DOWNARROW_HLT"
            )
            op.prop.target = prop.target  # type: ignore
            op.prop.name = prop.name  # type: ignore
            op.prop["_index"] = tex_idx  # type: ignore

            if tex and tex.preview:
                col = row.column()
                op = col.operator(
                    OP_L3D.OT_Texture_Preview.bl_idname,
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
        idx, item = L3D_data.get_external_by_id(
            scene_data, scene_data.defaults.external_id
        )

        row = column.row()
        split = row.split(factor=0.7)
        row = split.row()

        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('External Light')}:")

        col = row.column()
        name = "None" if not item else item.item_name
        op = col.operator(
            OP_L3D.OT_External_Select.bl_idname,
            text=name,
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "Scene"  # type: ignore
        op.prop["_index"] = idx  # type: ignore

        if item:
            row = split.row()
            row.prop(item, "color", text="")

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

        # column.separator(type="SPACE")
        # row = column.row()
        # row.prop(scene_data.defaults.flat_light, "vector", text="")


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


class AMAGATE_PT_Sector(L3D_Panel, bpy.types.Panel):
    bl_label = "Sector"
    bl_parent_id = "AMAGATE_PT_L3D"
    # bl_options = {"DEFAULT_CLOSED"}

    # 在4.4版本中会出错，已用其它方案实现
    # def __init__(self):
    #     super().__init__()
    #     data.ensure_null_texture()

    def draw(self, context: Context):
        # 作为顶层的扇区面板，可以在这里缓存选中扇区数据，子面板可直接引用
        selected_sectors, active_sector = ag_utils.get_selected_sectors()
        L3D_data.SELECTED_SECTORS, L3D_data.ACTIVE_SECTOR = (
            selected_sectors,
            active_sector,
        )
        #
        layout = self.layout
        scene_data = context.scene.amagate_data

        col = layout.column(align=True)

        # 扇区 ID
        id_ = "*"
        if len(selected_sectors) == 1:
            id_ = selected_sectors[0].amagate_data.get_sector_data().id
        elif len(selected_sectors) == 0:
            id_ = pgettext("None")
        col.label(text=f"{pgettext('Sector ID')}: {id_}")
        # 扇区连接数量
        num = "*"
        if len(selected_sectors) == 1:
            num = selected_sectors[0].amagate_data.get_sector_data().connect_num
        elif len(selected_sectors) == 0:
            num = pgettext("None")
        col.label(text=f"{pgettext('Sector Connections')}: {num}")

        #
        box = layout.box()
        col = box.column()

        # 多线段路径 Poly Path
        col.operator(OP_L3D.OT_PolyPath.bl_idname, icon="CURVE_PATH")
        # 创建虚拟扇区
        col.operator(OP_SECTOR.OT_GhostSector_Create.bl_idname)

        #
        box = layout.box()
        col = box.column()
        # 扇区数量
        # col.label(
        #     text=f"{pgettext('Selected Sector')}: {len(selected_sectors)} / {len(context.selected_objects)}"
        # )

        # 转换为扇区
        col.operator(OP_SECTOR.OT_Sector_Convert.bl_idname, icon="MESH_CUBE")

        # 分离为凸部分
        row = col.row(align=True)
        op = row.operator(
            OP_SECTOR.OT_Sector_SeparateConvex.bl_idname,
            icon_value=data.ICONS["knife"].icon_id,
        )
        op.is_button = True  # type: ignore
        row.prop(
            scene_data.operator_props,
            "sec_separate_connect",
            icon="ADD",
            icon_only=True,
            toggle=True,
        )

        row = col.row()
        # split = row.split(factor=0.5)
        # 连接扇区
        row_1 = row.row(align=True)
        op = row_1.operator(
            OP_SECTOR.OT_Sector_Connect.bl_idname, text="Connect", icon="AREA_JOIN"
        )
        op.is_button = True  # type: ignore
        row_1.operator(
            OP_SECTOR.OT_Sector_Connect_More.bl_idname, text="", icon="DOWNARROW_HLT"
        )
        # row_1.prop(
        #     scene_data.operator_props,
        #     "sec_connect_sep_convex",
        #     icon="ADD",
        #     icon_only=True,
        #     toggle=True,
        # )
        # 断开连接
        row_2 = row.row(align=True)
        op = row_2.operator(OP_SECTOR.OT_Sector_Disconnect.bl_idname, icon="X")
        op.is_button = True  # type: ignore

        col.separator(type="LINE")

        # 设为默认扇区
        op = col.operator(OP_SECTOR.OT_SectorSetDefault.bl_idname)
        op.is_button = True  # type: ignore


class AMAGATE_PT_Sector_Props(L3D_Panel, bpy.types.Panel):
    bl_label = "Properties"
    bl_parent_id = "AMAGATE_PT_Sector"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context: Context):
        # 不在编辑模式且有选择扇区，显示面板
        if context.objects_in_mode == []:
            for obj in context.selected_objects:
                if obj.amagate_data.is_sector:  # type: ignore
                    return True
        return False

    def draw(self, context: Context):
        selected_sectors = L3D_data.SELECTED_SECTORS
        active_sector = L3D_data.ACTIVE_SECTOR
        #
        layout = self.layout
        scene_data = context.scene.amagate_data
        active_sec_data = active_sector.amagate_data.get_sector_data()

        # 陡峭
        box = layout.box()
        col = box.column(align=True)

        # split = row.split(factor=0.5, align=True)

        # row = split.row()
        is_uniform = True
        steep_check = active_sec_data.steep_check
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.steep_check != steep_check:
                is_uniform = False
                break

        text = ("Yes" if steep_check else "No") if is_uniform else "*"
        col.label(text=f"{pgettext('Is Too Steep')}: {text}")
        #
        # row = split.row()
        is_uniform = True
        steep = active_sec_data.steep
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.steep != steep:
                is_uniform = False
                break

        text = "" if is_uniform else "* "
        # row = col.row()
        # row.alignment = "LEFT"
        col.prop(
            scene_data.sector_public, "steep", text=f"{text}{pgettext('Override')}"
        )

        layout.separator()

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
            atmo_idx, atmo = L3D_data.get_atmo_by_id(scene_data, atmo_id)
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
            OP_L3D.OT_Atmo_Select.bl_idname,
            text=name,
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "SectorPublic"  # type: ignore
        op.prop["_index"] = atmo_idx  # type: ignore

        if atmo:
            row = split.row()
            # row.enabled = False
            row.prop(atmo, "color", text="")
        elif not is_uniform:
            row = split.row()
            row.alignment = "CENTER"
            row.label(text="non-uniform")

        layout.separator()

        box = layout.box()
        # 地板 天花板 墙壁
        for i, name in enumerate(("Floor", "Ceiling", "Wall")):
            prop = scene_data.sector_public.textures[name]
            # name = prop.name

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
                tex_idx, tex = L3D_data.get_texture_by_id(tex_id)
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
                OP_L3D.OT_Texture_Select.bl_idname,
                text=tex_name,
                icon="DOWNARROW_HLT",
            )
            op.prop.target = prop.target  # type: ignore
            op.prop.name = prop.name  # type: ignore
            op.prop["_index"] = tex_idx  # type: ignore

            if tex and tex.preview:
                col = row.column()
                op = col.operator(
                    OP_L3D.OT_Texture_Preview.bl_idname,
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

            if i != 2:
                box.separator(type="LINE")

        layout.separator()

        box = layout.box()
        column = box.column(align=True)
        # 外部光
        is_uniform = True
        external_id = active_sec_data.external_id
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.external_id != external_id:
                is_uniform = False
                break

        idx, item = L3D_data.get_external_by_id(scene_data, sec_data.external_id)

        row = column.row()
        split = row.split(factor=0.7)
        row = split.row()

        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('External Light')}:")

        col = row.column()
        name = "None" if not item else item.item_name
        op = col.operator(
            OP_L3D.OT_External_Select.bl_idname,
            text=name if is_uniform else "*",
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.target = "SectorPublic"  # type: ignore
        op.prop["_index"] = idx if is_uniform else -1  # type: ignore

        if item:
            row = split.row()
            row.prop(item, "color", text="")

        column.separator(factor=2, type="LINE")

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
        is_uniform = True
        flat_color = active_sec_data.flat_light.color
        for sec in selected_sectors:
            sec_data = sec.amagate_data.get_sector_data()
            if sec_data.flat_light.color != flat_color:
                is_uniform = False
                break

        row = column.row()
        split = row.split(factor=0.5)
        row = split.row(align=True)
        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Flat Light')}:")
        if not is_uniform:
            col = row.column()
            col.alignment = "RIGHT"
            col.label(text="*")
        split.prop(scene_data.sector_public.flat_light, "color", text="")

        layout.separator()

        # 组
        box = layout.box()
        column = box.column(align=True)
        column.label(text=f"{pgettext('Groups')}:")
        col_flow = column.grid_flow(row_major=True, columns=8, align=True)
        for i in range(32):
            flag = ""
            active_group = ag_utils.int_to_uint(active_sec_data.group)
            check = (active_group >> i) & 1  # 访问第i位
            for sec in selected_sectors:
                sec_data = sec.amagate_data.get_sector_data()
                group = ag_utils.int_to_uint(sec_data.group)
                if (group >> i) & 1 != check:
                    flag = "*"
                    break

            col_flow.prop(
                scene_data.sector_public.group_set[i],
                "value",
                text=f"{i+1}{flag}",
                toggle=True,
            )


class AMAGATE_PT_SectorFace_Props(L3D_Panel, bpy.types.Panel):
    bl_label = "Face Properties"
    bl_parent_id = "AMAGATE_PT_Sector"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context: Context):
        # 扇区在编辑模式中，显示面板
        if context.objects_in_mode != []:
            for obj in context.objects_in_mode:
                if obj.amagate_data.is_sector:  # type: ignore
                    return True
        return False

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data
        L3D_data.SELECTED_FACES = []
        edit_sectors = [
            obj for obj in context.objects_in_mode if obj.amagate_data.is_sector
        ]
        bmeshs_edit = [(bmesh.from_edit_mesh(sec.data), sec) for sec in edit_sectors]  # type: ignore
        selected_faces = [
            (bm, [f for f in bm.faces if f.select], sec) for bm, sec in bmeshs_edit
        ]  # type: list[tuple[bmesh.types.BMesh, list[bmesh.types.BMFace], Object]]
        for i in range(len(selected_faces) - 1, -1, -1):
            item = selected_faces[i]
            # select_faces = item[1]
            # for j in range(len(select_faces) - 1, -1, -1):
            #     if not select_faces[j].is_valid:
            #         select_faces.pop(j)
            if not item[1]:
                selected_faces.pop(i)
        L3D_data.SELECTED_FACES = selected_faces

        try:
            # 面连接的扇区
            connected_sector = ""
            if len(selected_faces) == 1:
                if len(selected_faces[0][1]) == 1:
                    layers = selected_faces[0][0].faces.layers.int.get(
                        "amagate_connected"
                    )
                    face = selected_faces[0][1][0]
                    sid = face[layers]  # type: ignore
                    if sid != 0:
                        sec = scene_data["SectorManage"]["sectors"][str(sid)]["obj"]
                        connected_sector = sec.name
            layout.label(text=f"{pgettext('Connected Sector')}: {connected_sector}")

            layout.separator(factor=1, type="LINE")

            # 平面光
            row = layout.row()
            if len(selected_faces) != 1 or len(selected_faces[0][1]) != 1:
                row.enabled = False
            row.prop(scene_data, "flat_light", text="Flat Light")

            # 面类型
            row = layout.row()
            row_1 = row.row()
            row_1.alignment = "LEFT"
            row_1.label(text=f"{pgettext('Texture type')}:")
            row_1 = row.row()
            row_1.prop(scene_data, "face_type", text="")

            # 面纹理
            name = "Floor"
            box = layout.box()
            prop = scene_data.sector_public.textures[name]

            attr_dict = {
                "tex": {
                    "attr_name": "amagate_tex_id",
                    "value": None,
                    "is_uniform": True,
                },
                "xpos": {
                    "attr_name": "amagate_tex_xpos",
                    "value": None,
                    "is_uniform": True,
                },
                "ypos": {
                    "attr_name": "amagate_tex_ypos",
                    "value": None,
                    "is_uniform": True,
                },
                "angle": {
                    "attr_name": "amagate_tex_angle",
                    "value": None,
                    "is_uniform": True,
                },
                "xzoom": {
                    "attr_name": "amagate_tex_xzoom",
                    "value": None,
                    "is_uniform": True,
                },
                "yzoom": {
                    "attr_name": "amagate_tex_yzoom",
                    "value": None,
                    "is_uniform": True,
                },
            }

            if selected_faces:
                item = selected_faces[0]
                bm = item[0]
                face = item[1][0]

                for k in attr_dict.keys():
                    attr_list = attr_dict[k]
                    if k == "tex":
                        layers = bm.faces.layers.int.get(attr_list["attr_name"])
                    else:
                        layers = bm.faces.layers.float.get(attr_list["attr_name"])
                    attr_list["value"] = face[layers]  # type: ignore
                #
                for item in selected_faces:
                    bm = item[0]
                    for face in item[1]:
                        for k in attr_dict.keys():
                            attr_list = attr_dict[k]
                            if not attr_list["is_uniform"]:
                                continue

                            if k == "tex":
                                layers = bm.faces.layers.int.get(attr_list["attr_name"])
                            else:
                                layers = bm.faces.layers.float.get(
                                    attr_list["attr_name"]
                                )

                            if face[layers] != attr_list["value"]:  # type: ignore
                                attr_list["is_uniform"] = False

            #
            if attr_dict["tex"]["is_uniform"]:
                tex_idx, tex = L3D_data.get_texture_by_id(attr_dict["tex"]["value"])
                tex_name = "None" if not tex else tex.name
            else:
                tex_idx, tex = -1, None
                tex_name = "*"

            column = box.column()
            #
            row = column.row()

            col = row.column()
            col.alignment = "LEFT"
            col.label(text=f"{pgettext('Texture')}:")

            col = row.column()
            op = col.operator(
                OP_L3D.OT_Texture_Select.bl_idname,
                text=tex_name,
                icon="DOWNARROW_HLT",
            )
            op.prop.target = prop.target  # type: ignore
            op.prop.name = prop.name  # type: ignore
            op.prop["_index"] = tex_idx  # type: ignore

            if tex and tex.preview:
                col = row.column()
                op = col.operator(
                    OP_L3D.OT_Texture_Preview.bl_idname,
                    text="",
                    icon_value=tex.preview.icon_id,
                    emboss=False,
                )
                op.index = bpy.data.images.find(tex.name)  # type: ignore
            elif not attr_dict["tex"]["is_uniform"]:
                col = row.column()
                col.label(icon_value=1)
            #
            row = column.row(align=True)
            if 1:
                x_text = "X" if attr_dict["xpos"]["is_uniform"] else "X *"
                y_text = "Y" if attr_dict["ypos"]["is_uniform"] else "Y *"
                row.prop(prop, "xpos", text=x_text)
                row.prop(prop, "ypos", text=y_text)

                row = column.row()
                text = (
                    "Angle"
                    if attr_dict["angle"]["is_uniform"]
                    else f"{pgettext('Angle')} *"
                )
                row.prop(prop, "angle", text=text)

                box2 = column.box()
                row = box2.row()
                col = row.column(align=True)
                x_text = f"X {pgettext('Zoom')}"
                if not attr_dict["xzoom"]["is_uniform"]:
                    x_text = f"{x_text} *"
                y_text = f"Y {pgettext('Zoom')}"
                if not attr_dict["yzoom"]["is_uniform"]:
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
            # 平面光
        except:
            pass


############################
############################ 工具面板
############################
class AMAGATE_PT_Tools(L3D_Panel, bpy.types.Panel):
    bl_label = "Tools"
    bl_parent_id = "AMAGATE_PT_L3D"
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return data.PY_PACKAGES_INSTALLED

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data

        row = layout.row(align=True)
        op = row.operator(
            OP_L3D.OT_New.bl_idname,
            text="New Map",
            icon_value=data.ICONS["blade"].icon_id,
        )
        op.target = "new"  # type: ignore
        op.execute_type = 0  # type: ignore
        # 导出地图
        row = layout.row(align=True)
        row.enabled = scene_data.is_blade
        row.operator(OP_L3D_EXT.OT_ExportMap.bl_idname, icon="EXPORT")
        op = row.operator(
            OP_L3D_EXT.OT_ExportMap.bl_idname, text="", icon="DOWNARROW_HLT"
        )
        op.more = True  # type: ignore
        # 导出虚拟扇区
        layout.operator(OP_SECTOR.OT_GhostSectorExport.bl_idname, icon="EXPORT")


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
