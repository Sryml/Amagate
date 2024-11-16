import bpy
from bpy.app.translations import pgettext
from bpy.props import BoolProperty

from . import data
from . import operator as OP


# 场景面板
class PT_Scene(bpy.types.Panel):
    bl_label = "Blade Scene"
    bl_idname = "AMAGATE_PT_Scene"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"

    def draw(self, context):
        layout = self.layout
        scene_data = context.scene.amagate_data  # type: ignore

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


# 场景面板 -> 大气面板
class PT_Scene_Atmosphere(bpy.types.Panel):
    bl_label = "Atmosphere"
    bl_idname = "AMAGATE_PT_Scene_Atmosphere"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        # 自定义条件，仅在blade场景中显示
        return context.scene.amagate_data.is_blade  # type: ignore

    def draw(self, context):
        layout = self.layout
        scene_data = context.scene.amagate_data  # type: ignore

        # 显示大气列表
        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.label(text=f"{pgettext('Atmospheres')}: {len(scene_data.atmospheres)}")

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
        col.separator(factor=3)
        col.operator(OP.OT_Scene_Atmo_Default.bl_idname, text="", icon_value=data.ICONS["star"].icon_id)  # type: ignore


# 场景面板 -> 默认属性面板
class PT_Scene_Default(bpy.types.Panel):
    bl_label = "Default Properties"
    bl_idname = "AMAGATE_PT_Scene_Default"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"DEFAULT_CLOSED"}  # 默认折叠

    @classmethod
    def poll(cls, context):
        # 自定义条件，仅在blade场景中显示
        return context.scene.amagate_data.is_blade  # type: ignore

    def draw(self, context):
        layout = self.layout
        # layout.use_property_split = True
        # layout.use_property_decorate = False
        scene_data = context.scene.amagate_data  # type: ignore

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
        op = col.operator(
            OP.OT_Scene_Default_Atmo.bl_idname,
            text=f"{atmo.name}",
            icon="DOWNARROW_HLT",
        )  # COLLAPSEMENU
        op.prop.is_sector = False  # type: ignore
        op.prop.index = atmo_idx  # type: ignore

        row = split.row()
        row.enabled = False
        row.prop(atmo, "color", text="")

        # 纹理


# 场景面板 -> 新建场景面板
class PT_Scene_New(bpy.types.Panel):
    bl_label = "New Scene"
    bl_idname = "AMAGATE_PT_Scene_New"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        layout.separator()
        # 新建场景按钮
        layout.operator(OP.OT_NewScene.bl_idname, icon="ADD")

        # test
        # layout.operator(OP.OT_NewScene.bl_idname, icon="RESTRICT_SELECT_ON")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="RESTRICT_SELECT_OFF")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="GP_ONLY_SELECTED")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="GP_SELECT_BETWEEN_STROKES")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="SELECT_SET")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="SELECT_EXTEND")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="SELECT_SUBTRACT")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="SELECT_INTERSECT")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="SELECT_DIFFERENCE")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="FILE_TICK")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="PREFERENCES")


# 纹理面板
class PT_Scene_Texture(bpy.types.Panel):
    bl_label = "Textures"
    bl_idname = "AMAGATE_PT_Scene_Texture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"
    # bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板

    @classmethod
    def poll(cls, context):
        # 自定义条件，仅在blade场景中显示
        return context.scene.amagate_data.is_blade  # type: ignore

    def draw(self, context):
        layout = self.layout
        scene_data: data.SceneProperty = context.scene.amagate_data  # type: ignore

        # 显示纹理列表
        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.label(
            text=f"{pgettext('Total')}: {[bool(i.amagate_data.id) for i in bpy.data.images].count(True)}"  # type: ignore
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
            rows=3,
            maxrows=7,
        )

        # 添加按钮放置在右侧
        col = row.column(align=True)
        col.operator(OP.OT_Scene_Texture_Add.bl_idname, text="", icon="ADD")
        col.operator(OP.OT_Scene_Texture_Remove.bl_idname, text="", icon="X")
        col.operator(OP.OT_Scene_Texture_Reload.bl_idname, text="", icon="FILE_REFRESH")
        col.operator(OP.OT_Scene_Texture_Package.bl_idname, text="", icon="UGLYPACKAGE")

        # TODO: 预览图像
        # row = layout.row(align=True)
        # row.template_preview()


class PT_PanelTest(bpy.types.Panel):
    bl_label = "Test"
    bl_idname = "AMAGATE_PT_PanelTest"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.alignment = "RIGHT"
        row.operator(OP.OT_ReloadAddon.bl_idname, icon="FILE_REFRESH")  # 添加按钮
        # row = layout.row(align=True)
        # row.alignment = "CENTER"
        layout.operator(OP.OT_ExportMap.bl_idname, icon="EXPORT")  # 添加按钮


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
