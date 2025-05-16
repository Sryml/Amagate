# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations
from typing import Any, TYPE_CHECKING

import bpy
from bpy.app.translations import pgettext


from . import data
from . import operator as OP
from . import ag_utils

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


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

    from . import L3D_panel

    L3D_panel.register()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    from . import L3D_panel

    L3D_panel.unregister()
