import bpy
from bpy.app.translations import pgettext


# 创建一个面板
class PT_Panel1(bpy.types.Panel):
    bl_label = "Blade Scene"
    bl_idname = "AMAGATE_PT_Panel1"
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
            layout.operator("amagate.newscene", icon="ADD")
            return

        # layout.separator()

        # 显示大气列表
        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.label(text=f"{pgettext('Atmospheres')}: {len(scene_data.atmospheres)}")

        # 创建滚动区域来显示最多 3 个大气项
        row = layout.row(align=True)
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
