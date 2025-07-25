# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations
from typing import Any, TYPE_CHECKING

import os

import bpy
import bmesh
from bpy.app.translations import pgettext


from . import data, L3D_data, entity_data
from . import L3D_operator as OP_L3D
from . import L3D_ext_operator as OP_L3D_EXT
from . import L3D_imp_operator as OP_L3D_IMP
from . import sector_operator as OP_SECTOR
from . import ag_utils
from ..service import ag_service

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection


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
        column = layout.column()

        # HUD开关
        # row = column.row(align=True)
        # row.alignment = "LEFT"
        # area_index = next(
        #     i for i, a in enumerate(context.screen.areas) if a == context.area
        # )
        # icon = (
        #     "CHECKBOX_HLT"
        #     if scene_data.areas_show_hud.get(str(area_index))
        #     else "CHECKBOX_DEHLT"
        # )
        # row.operator(OP_L3D.OT_Scene_Props_HUD.bl_idname, emboss=False, icon=icon)
        column.prop(scene_data, "hud_enable", text="Show HUD")
        # 体积开关
        column.prop(scene_data, "volume_enable", text="Volume")
        # 视锥裁剪
        column.prop(scene_data, "frustum_culling", text="Frustum Culling")


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
        # 打开文件浏览器
        col = row1.column()
        col.operator(OP_L3D.OT_SkyTexture_Open.bl_idname, text="", icon="FILEBROWSER")
        col.enabled = scene_data.sky_tex_enum == "-1"
        # 下载
        prop_rna = scene_data.bl_rna.properties["sky_tex_enum"]
        enum_items = prop_rna.enum_items  # type: ignore
        not_exists = next(
            (
                True
                for item in enum_items
                if item.description != "Custom"
                and not os.path.exists(
                    os.path.join(
                        data.ADDON_PATH, f"textures/panorama/{item.description}.jpg"
                    )
                )
            ),
            False,
        )
        col = row1.column()
        col.enabled = not_exists and (not L3D_data.PANORAMA_LOCK.locked())
        col.operator(
            OP_L3D.OT_SkyTexture_Download.bl_idname, text="", icon="EVENT_DOWN_ARROW"
        )
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
        # 选择连接扇区
        col.operator(OP_L3D.OT_SelectConnected.bl_idname)

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

        # 灯泡
        box = layout.box()
        column = box.column(align=True)

        enabled = len(selected_sectors) == 1
        num = len(active_sec_data.bulb_light) if enabled else ""
        column.label(text=f"{pgettext('Bulbs')}: {num}")

        row = column.row(align=True)

        col = row.column()
        col.template_list(
            "AMAGATE_UI_UL_SectorBulb",
            "",
            active_sec_data,
            "bulb_light",
            scene_data.bulb_operator,
            "active",
            rows=3,
            maxrows=3,
        )

        # 添加按钮放置在右侧
        col = row.column(align=True)
        col.enabled = enabled
        col.operator(OP_SECTOR.OT_Bulb_Add.bl_idname, text="", icon="ADD")
        col.operator(OP_SECTOR.OT_Bulb_Del.bl_idname, text="", icon="X")

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
        top_column = layout.column()
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
            top_column.label(text=f"{pgettext('Connected Sector')}: {connected_sector}")
            # 显示连接面
            top_column.prop(scene_data, "show_connected_sw", text="Show Connected Face")

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
            name = "Face"
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
            # 复制/粘贴设置
            column.separator(type="SPACE")
            row = column.row()
            row.operator(OP_L3D.OT_CopyFaceTexture.bl_idname)
            row.operator(OP_L3D.OT_PasteFaceTexture.bl_idname)
            # 平面光
        except:
            pass


############################
############################ 预制体面板
############################


class AMAGATE_PT_Prefab(L3D_Panel, bpy.types.Panel):
    bl_label = "Prefab"
    bl_parent_id = "AMAGATE_PT_L3D"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return data.PY_PACKAGES_INSTALLED

    def draw(self, context: Context):
        layout = self.layout


class AMAGATE_PT_PrefabEntity(L3D_Panel, bpy.types.Panel):
    bl_label = "Entity"
    bl_parent_id = "AMAGATE_PT_Prefab"

    @classmethod
    def poll(cls, context):
        return data.PY_PACKAGES_INSTALLED

    def draw(self, context: Context):
        layout = self.layout
        wm_data = context.window_manager.amagate_data

        #
        selected_entities = [
            obj for obj in context.selected_objects if obj.amagate_data.is_entity
        ]
        active_entity = selected_entities[0] if selected_entities else None
        if active_entity:
            ent_data = active_entity.amagate_data.get_entity_data()
        else:
            ent_data = None
        entity_data.SELECTED_ENTITIES = selected_entities
        #

        column = layout.column(align=True)
        row = column.row(align=True)
        # row.prop(wm_data, "ent_enum",text="")
        split = row.split(factor=0.9, align=True)
        split.operator(
            OP_L3D.OT_Entity_Enum.bl_idname, text="Select Entity", icon="DOWNARROW_HLT"
        )
        op = split.operator(OP_L3D.OT_Entity_Search.bl_idname, text="", icon="VIEWZOOM")
        # op.enum = wm_data.ent_enum  # type: ignore
        column.template_icon_view(
            wm_data, "ent_preview", show_labels=True, scale=5, scale_popup=10
        )

        row = layout.row(align=True)
        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Internal Name')}:")
        row.prop(wm_data, "ent_inter_name", text="")

        row = layout.row()
        row.operator(OP_L3D.OT_EntityAddToScene.bl_idname)
        row.operator(OP_L3D.OT_OpenPrefab.bl_idname).action = 0  # type: ignore
        # row.operator(OP_L3D.OT_EntityRemoveFromScene.bl_idname)

        layout.separator(type="LINE")
        #
        row = layout.row(align=True)
        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Prefab Name')}:")
        row.prop(wm_data, "prefab_name", text="")

        row = layout.row(align=True)
        col = row.column()
        col.alignment = "LEFT"
        col.label(text=f"{pgettext('Prefab Type')}:")
        row.prop(wm_data, "prefab_type", text="")

        row = layout.row()
        # col = row.column()
        # col.alignment = "LEFT"
        # col.label(text=f"{pgettext('Set as Prefab')}:")
        row.operator_menu_enum(
            OP_L3D.OT_SetAsPrefab.bl_idname,
            "action",
        )
        inter_name = bpy.types.UILayout.enum_item_description(
            wm_data, "ent_enum", wm_data.ent_enum
        )
        col = row.column()
        col.enabled = inter_name in data.E_MANIFEST["Entities"]["Custom"]
        col.operator(OP_L3D.OT_RemovePrefab.bl_idname)

        layout.separator(type="LINE")

        # 实体属性
        layout.label(text=f"{pgettext('Properties')}:")
        box = layout.box()
        box.enabled = len(selected_entities) != 0

        column = box.column()
        flag = "" if entity_data.is_uniform("Kind") else "*"
        column.prop(wm_data.EntityData, "Kind", text=f"{flag}Kind", text_ctxt="Keep")
        column.prop(wm_data.EntityData, "Name", text="Name")
        row = column.row()
        col = row.column()
        col.alignment = "LEFT"
        is_uniform_objtype = entity_data.is_uniform("ObjType")
        flag = "" if is_uniform_objtype else "*"
        col.label(text=f"{flag}{pgettext('Entity Type')}:")
        row.prop(wm_data.EntityData, "ObjType", text="")

        # box.separator(type="LINE")

        # 通用
        sub_box = box.box()
        column = sub_box.column()
        column.label(text=f"{pgettext('General')}:")
        grid = column.grid_flow(row_major=True, columns=2, align=True)

        flag = "" if entity_data.is_uniform("Alpha") else "*"
        grid.prop(
            wm_data.EntityData,
            "Alpha",
            slider=True,
            text=f"{flag}Alpha",
            text_ctxt="Keep",
        )

        flag = "" if entity_data.is_uniform("SelfIlum") else "*"
        grid.prop(
            wm_data.EntityData, "SelfIlum", text=f"{flag}SelfIlum", text_ctxt="Keep"
        )

        row = column.row()

        flag = "" if entity_data.is_uniform("Static") else "*"
        row.prop(wm_data.EntityData, "Static", text=f"{flag}Static", text_ctxt="Keep")

        flag = "" if entity_data.is_uniform("CastShadows") else "*"
        row.prop(
            wm_data.EntityData,
            "CastShadows",
            text=f"{flag}CastShadows",
            text_ctxt="Keep",
        )

        # box.separator(type="LINE")

        # 角色
        sub_box = box.box()
        if (
            is_uniform_objtype
            and ent_data
            and layout.enum_item_name(ent_data, "ObjType", ent_data.ObjType) == "Person"
        ):
            sub_box.enabled = True
        else:
            sub_box.enabled = False

        column = sub_box.column()
        column.label(text=f"{pgettext('Character')}:")
        grid = column.grid_flow(row_major=True, columns=2, align=True)
        flag = "" if entity_data.is_uniform("Life") else "*"
        grid.prop(wm_data.EntityData, "Life", text=f"{flag}Life", text_ctxt="Keep")
        flag = "" if entity_data.is_uniform("Level") else "*"
        grid.prop(wm_data.EntityData, "Level", text=f"{flag}Level", text_ctxt="Keep")
        flag = "" if entity_data.is_uniform("Angle") else "*"
        grid.prop(wm_data.EntityData, "Angle", text=f"{flag}Angle", text_ctxt="Keep")
        grid.label(text="")
        flag = "" if entity_data.is_uniform("SetOnFloor") else "*"
        grid.prop(
            wm_data.EntityData, "SetOnFloor", text=f"{flag}SetOnFloor", text_ctxt="Keep"
        )
        grid.label(text="")
        flag = "" if entity_data.is_uniform("Hide") else "*"
        grid.prop(wm_data.EntityData, "Hide", text=f"{flag}Hide", text_ctxt="Keep")
        flag = "" if entity_data.is_uniform("Freeze") else "*"
        grid.prop(wm_data.EntityData, "Freeze", text=f"{flag}Freeze", text_ctxt="Keep")
        flag = "" if entity_data.is_uniform("Blind") else "*"
        grid.prop(wm_data.EntityData, "Blind", text=f"{flag}Blind", text_ctxt="Keep")
        flag = "" if entity_data.is_uniform("Deaf") else "*"
        grid.prop(wm_data.EntityData, "Deaf", text=f"{flag}Deaf", text_ctxt="Keep")

        # box.separator(type="LINE")

        # 演员
        sub_box = box.box()
        if (
            is_uniform_objtype
            and ent_data
            and layout.enum_item_name(ent_data, "ObjType", ent_data.ObjType) == "Actor"
        ):
            sub_box.enabled = True
        else:
            sub_box.enabled = False

        column = sub_box.column()
        column.label(text=f"{pgettext('Actor')}:")
        row = column.row(align=True)
        col = row.column()
        col.alignment = "LEFT"
        flag = "" if entity_data.is_uniform("Animation") else "*"
        col.label(text=f"{flag}Animation:", text_ctxt="Keep")
        row.prop(wm_data.EntityData, "Animation", text="")

        # box.separator(type="LINE")

        # 灯光
        sub_box = box.box()

        column = sub_box.column()
        column.label(text=f"{pgettext('Light')}:")
        grid = column.grid_flow(row_major=True, columns=2, align=True)
        grid.prop(wm_data.EntityData.light_prop, "Color", text="")
        flag = "" if entity_data.is_uniform("light_prop.Intensity") else "*"
        grid.prop(
            wm_data.EntityData.light_prop,
            "Intensity",
            text=f"{flag}{pgettext('Intensity')}",
        )
        flag = "" if entity_data.is_uniform("FiresIntensity") else "*"
        grid.prop(
            wm_data.EntityData,
            "FiresIntensity",
            slider=True,
            text=f"{flag}{pgettext('FiresIntensity')}",
        )
        flag = "" if entity_data.is_uniform("light_prop.Precision") else "*"
        grid.prop(
            wm_data.EntityData.light_prop,
            "Precision",
            text=f"{flag}{pgettext('Precision')}",
        )
        flag = "" if entity_data.is_uniform("light_prop.Flick") else "*"
        grid.prop(
            wm_data.EntityData.light_prop,
            "Flick",
            text=f"{flag}Flick",
            text_ctxt="Keep",
        )
        flag = "" if entity_data.is_uniform("light_prop.Visible") else "*"
        grid.prop(
            wm_data.EntityData.light_prop,
            "Visible",
            text=f"{flag}Visible",
            text_ctxt="Keep",
        )
        flag = "" if entity_data.is_uniform("light_prop.CastShadows") else "*"
        grid.prop(
            wm_data.EntityData.light_prop,
            "CastShadows",
            text=f"{flag}CastShadows",
            text_ctxt="Keep",
        )

        # 装备库存
        sub_box = box.box()
        if (
            is_uniform_objtype
            and ent_data
            and layout.enum_item_name(ent_data, "ObjType", ent_data.ObjType) == "Person"
        ):
            sub_box.enabled = True
        else:
            sub_box.enabled = False

        column = sub_box.column()
        column.label(text=f"{pgettext('Equipments')}:")

        # 道具库存
        sub_box = box.box()
        if (
            is_uniform_objtype
            and ent_data
            and layout.enum_item_name(ent_data, "ObjType", ent_data.ObjType) == "Person"
        ):
            sub_box.enabled = True
        else:
            sub_box.enabled = False

        column = sub_box.column()
        column.label(text=f"{pgettext('Props')}:")


############################
############################ 服务器面板
############################
class AMAGATE_PT_Server(L3D_Panel, bpy.types.Panel):
    bl_label = "Server"
    bl_parent_id = "AMAGATE_PT_L3D"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data
        column = layout.column()

        # 状态
        row = column.row()
        split = row.split(factor=0.5)
        status = ag_service.get_status()
        text = f'{pgettext("Running")}...' if status else pgettext("Closed")
        row2 = split.row()
        row2.alert = not status
        row2.label(text=f"{pgettext('Status')}: {text}")

        split2 = split.split(factor=0.5, align=True)
        split2.operator(OP_L3D.OT_Server_Start.bl_idname, text="", icon="PLAY")
        split2.operator(OP_L3D.OT_Server_Stop.bl_idname, text="", icon="PAUSE")
        # 客户端状态
        row = column.row()
        client_status = ag_service.get_client_status()
        text = (
            pgettext("Connected", "Server")
            if client_status
            else pgettext("Not connected")
        )
        row.alert = not client_status
        row.label(text=f"{pgettext('Client')}: {text}")

        column.separator(type="LINE")

        # 同步功能
        server_thread = ag_service.server_thread

        box = column.box()
        box.enabled = client_status
        col = box.column()
        # 加载/重载地图
        row = col.row(align=True)
        col2 = row.column()
        col2.alignment = "LEFT"
        col2.label(text=f"{pgettext('Load Level')}:")
        row.prop(scene_data, "level_enum")
        row.separator(factor=1, type="SPACE")
        row.operator(OP_L3D.OT_Server_ReloadMap.bl_idname, text="", icon="FILE_REFRESH")
        col.separator(type="SPACE")
        # 摄像机
        row = col.row(align=True)
        row.label(text=f"{pgettext('Camera')}:")
        row.operator(OP_L3D.OT_Server_CamToClient.bl_idname)
        row.prop(scene_data.operator_props, "camera_sync", text="Sync", toggle=True)
        # col.separator(type="SPACE")
        # 玩家到摄像机
        col.operator(OP_L3D.OT_Server_PlayerToCam.bl_idname)


############################
############################ 工具面板
############################
class AMAGATE_PT_L3D_Tools(L3D_Panel, bpy.types.Panel):
    bl_label = "L3D Tools"
    bl_parent_id = "AMAGATE_PT_L3D"
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return data.PY_PACKAGES_INSTALLED

    def draw(self, context: Context):
        layout = self.layout
        scene_data = context.scene.amagate_data
        column = layout.column()

        row = column.row(align=True)
        op = row.operator(
            OP_L3D.OT_New.bl_idname,
            text="New Map",
            icon_value=data.ICONS["blade"].icon_id,
        )
        op.target = "new"  # type: ignore
        op.execute_type = 0  # type: ignore
        # 导出地图
        row = column.row(align=True)
        row.enabled = scene_data.is_blade
        row.operator(OP_L3D_EXT.OT_ExportMap.bl_idname, icon="EXPORT")
        op = row.operator(
            OP_L3D_EXT.OT_ExportMap.bl_idname, text="", icon="DOWNARROW_HLT"
        )
        op.more = True  # type: ignore
        # 导出虚拟扇区
        column.operator(OP_SECTOR.OT_GhostSectorExport.bl_idname, icon="EXPORT")

        column.separator(type="LINE")

        # 导入地图
        op = column.operator(
            OP_L3D_IMP.OT_ImportMap.bl_idname,
            # text="Import Map",
            icon_value=data.ICONS["blade"].icon_id,
        )
        op.execute_type = 0  # type: ignore

        column.separator(type="LINE")

        # 重置节点
        row = column.row()
        row.enabled = scene_data.is_blade
        row.operator(OP_L3D.OT_Node_Reset.bl_idname, icon="FILE_REFRESH")


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
