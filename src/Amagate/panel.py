import bpy
from bpy.app.translations import pgettext

from . import data


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
            # layout.operator("amagate.newscene", icon="ADD")
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
            "AMAGATE_UI_UL_AtmosphereList",
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
        col.operator("amagate.scene_atmo_add", text="", icon="ADD")
        col.operator("amagate.scene_atmo_remove", text="", icon="X")
        col.separator(factor=3)
        col.operator("amagate.scene_atmo_default", text="", icon_value=data.ICONS["star"].icon_id)  # type: ignore


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
        layout.operator("amagate.newscene", icon="ADD")


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
        row.operator("amagate.reloadaddon", icon="FILE_REFRESH")  # 添加按钮
        # row = layout.row(align=True)
        # row.alignment = "CENTER"
        layout.operator("amagate.exportmap", icon="EXPORT")  # 添加按钮


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
