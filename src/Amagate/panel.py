import bpy
from bpy.app.translations import pgettext
from bpy.props import BoolProperty
from bpy.types import Context

from . import data
from . import operator as OP


class N_Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Amagate"

    @classmethod
    def poll(cls, context):
        # 自定义条件，仅在blade场景中显示
        return context.scene.amagate_data.is_blade  # type: ignore


# 场景面板
class AMAGATE_PT_Scene(N_Panel, bpy.types.Panel):
    bl_label = "Blade Scene"
    # bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return True

    def __init__(self):
        super().__init__()
        data.ensure_null_texture()

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
class AMAGATE_PT_Scene_Atmosphere(N_Panel, bpy.types.Panel):
    bl_label = "Atmosphere"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    # bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        scene_data = context.scene.amagate_data  # type: ignore

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
        col.separator(factor=3)
        col.operator(OP.OT_Scene_Atmo_Default.bl_idname, text="", icon_value=data.ICONS["star"].icon_id)  # type: ignore


# 场景面板 -> 默认属性面板
class AMAGATE_PT_Scene_Default(N_Panel, bpy.types.Panel):
    bl_label = "Default Properties"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"DEFAULT_CLOSED"}  # 默认折叠

    def draw(self, context):
        layout = self.layout
        # layout.use_property_split = True
        # layout.use_property_decorate = False
        scene_data: data.SceneProperty = context.scene.amagate_data  # type: ignore

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
        name = "None" if not atmo else atmo.name
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

        # 地板 天花板 墙壁
        for prop in scene_data.default_tex:
            target = prop.target

            tex_id = scene_data.defaults["Textures"][target]["id"]
            tex_idx, tex = data.get_texture_by_id(tex_id)
            box = layout.box()

            row = box.row()

            col = row.column()
            col.alignment = "LEFT"
            col.label(text=f"{pgettext(target, 'Property')}:")

            col = row.column()
            name = "None" if not tex else tex.name
            op = col.operator(
                OP.OT_Texture_Select.bl_idname, text=name, icon="DOWNARROW_HLT"
            )
            op.prop.target = target  # type: ignore
            op.prop["_index"] = tex_idx  # type: ignore

            if tex and tex.preview:
                col = row.column()
                col.label(text="", icon_value=tex.preview.icon_id)

            row = box.row()
            # row.prop(scene_data.defaults.texture, "pos", index=-1, text="")
            row.prop(prop, "pos", index=0, text="X")
            # row.separator()
            row.prop(prop, "pos", index=1, text="Y")

            row = box.row()
            row.prop(prop, "zoom", text="Zoom")
            # row.separator()
            row.prop(prop, "angle", text="Angle")

            layout.separator()


# 场景面板 -> 默认属性面板 -> 地板
"""
class AMAGATE_PT_Scene_Default_Floor(N_Panel, bpy.types.Panel):
    bl_label = ""
    bl_parent_id = "AMAGATE_PT_Scene_Default"  # 设置父面板
    bl_options = {"HIDE_HEADER"}

    def __init__(self):
        super().__init__()
        # 为标题设置带上下文的翻译
        self.bl_label = pgettext("Floor", "Property")

    # def draw_header(self, context: Context | None):
    #     layout = self.layout
    #     layout.label(text="Floor", text_ctxt="Property")

    def draw(self, context):
        layout = self.layout
        scene_data = context.scene.amagate_data  # type: ignore
"""


# 场景面板 -> 默认属性面板 -> 天花板
# 场景面板 -> 默认属性面板 -> 墙壁
# 场景面板 -> 默认属性面板 -> 灯光


# 场景面板 -> 新建场景面板
class AMAGATE_PT_Scene_New(N_Panel, bpy.types.Panel):
    bl_label = "New Scene"
    bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return True

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
        # layout.operator(OP.OT_NewScene.bl_idname, icon="PACKAGE")
        # layout.operator(OP.OT_NewScene.bl_idname, icon="PACKAGE")


# 纹理面板
class AMAGATE_PT_Texture(N_Panel, bpy.types.Panel):
    bl_label = "Textures"
    # bl_parent_id = "AMAGATE_PT_Scene"  # 设置父面板
    # bl_options = {"DEFAULT_CLOSED"}

    def __init__(self):
        super().__init__()
        data.ensure_null_texture()

    def draw(self, context):
        layout = self.layout
        scene_data: data.SceneProperty = context.scene.amagate_data  # type: ignore
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
            rows=4,
            maxrows=7,
        )

        # 添加按钮放置在右侧
        col = row.column(align=True)
        col.operator(OP.OT_Texture_Add.bl_idname, text="", icon="ADD")
        col.operator(OP.OT_Texture_Remove.bl_idname, text="", icon="X")
        col.separator(factor=3)
        col.operator(OP.OT_Texture_Reload.bl_idname, text="", icon="FILE_REFRESH")
        col.operator(OP.OT_Texture_Package.bl_idname, text="", icon="UGLYPACKAGE")
        # TODO 设为默认按钮，点击弹出列表项

        # TODO: 预览图像
        # row = layout.row(align=True)
        # row.template_preview()


class AMAGATE_PT_Test(N_Panel, bpy.types.Panel):
    bl_label = "Test"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.alignment = "RIGHT"
        row.operator(OP.OT_ReloadAddon.bl_idname, icon="FILE_REFRESH")  # 添加按钮
        # row = layout.row(align=True)
        # row.alignment = "CENTER"
        layout.operator(OP.OT_ExportMap.bl_idname, icon="EXPORT")  # 添加按钮


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
