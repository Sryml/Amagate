# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import sys
import os
import math
import pickle
import struct
import contextlib
import shutil
import threading
import time
from pprint import pprint
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

import bpy
import bmesh
from bpy.app.translations import pgettext
from bpy.props import (
    PointerProperty,
    CollectionProperty,
    EnumProperty,
    BoolProperty,
    BoolVectorProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    IntVectorProperty,
    StringProperty,
)
from mathutils import *  # type: ignore

from . import data
from . import ag_utils


if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


############################
############################ 通用操作
############################


# 反馈消息
class OT_ReportMessage(bpy.types.Operator):
    bl_idname = "amagate.report_message"
    bl_label = "Report Message"
    bl_options = {"INTERNAL"}

    message: StringProperty(default="No message provided")  # type: ignore
    type: StringProperty(default="INFO")  # type: ignore

    def execute(self, context: Context):
        self.report({self.type}, self.message)
        return {"FINISHED"}


############################
############################ py包安装面板
############################
class OT_InstallPyPackages(bpy.types.Operator):
    bl_idname = "amagate.install_py_packages"
    bl_label = "Install Python Packages"
    bl_description = "Install Python packages"
    bl_options = {"INTERNAL"}

    def execute(self, context: Context):
        # 初始化进度条
        scene_data = bpy.context.scene.amagate_data
        scene_data.progress_bar.pyp_install_progress = 0.0
        ag_utils.install_packages()
        return {"FINISHED"}


############################
############################ 调试面板
############################


class OT_Test(bpy.types.Operator):
    bl_idname = "amagate.test"
    bl_label = "Test"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context: Context):
        # self.test1(context)
        # self.test2(context)
        # self.test3(context)

        # area = context.area
        # if area.type == "VIEW_3D":
        #     for region in area.regions:
        #         if region.type == "WINDOW":
        #             print(f"width: {region.width}, height: {region.height}")
        #             rv3d = region.data  # type: bpy.types.RegionView3D
        # # rv3d.view_perspective = "CAMERA"
        # context.scene.camera = bpy.data.objects["Camera"]
        # bpy.ops.mesh.knife_project()
        # 设置视图为顶部视图
        # rv3d.view_rotation = Euler((math.pi / 3, 0.0, 0.0)).to_quaternion()
        # rv3d.view_distance = 15.0
        # rv3d.view_location = (0.0, 0.0, 0.0)
        # print(f"view_rotation: {rv3d.view_rotation.to_euler()}")
        # print(f"view_distance: {rv3d.view_distance}")
        # print(f"view_location: {rv3d.view_location}")
        # rv3d.view_perspective="ORTHO"
        # print(f"view_camera_zoom: {rv3d.view_camera_zoom}")
        # break
        return {"FINISHED"}

    def test1(self, context: Context):
        # bpy.ops.ed.undo()
        # bpy.ops.ed.redo()
        #         print(context.area.type)
        #         print(context.region.type)
        #         with bpy.context.temp_override(
        #     # window=bpy.context.window_manager.windows[0],  # 使用主窗口
        #     area=context.area,  # 使用第一个区域（如 3D 视图）
        #     region=context.region,  # 使用第一个区域内的区域
        # ):
        bpy.ops.ed.undo_redo()

    def test2(self, context: Context):
        bm = bmesh.new()
        verts = [
            (0, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
        ]
        for v in verts:
            bm.verts.new(v)
        bm.faces.new(bm.verts[-3:])
        for v in verts:
            bm.verts.new(v)
        bm.faces.new(bm.verts[-3:])

        mesh = bpy.data.meshes.new("AG.test")
        bm.to_mesh(mesh)
        obj = bpy.data.objects.new("AG.test", mesh)
        bpy.context.scene.collection.objects.link(obj)

        bm.free()

    def test3(self, context: Context):
        mesh = context.object.data  # type: bpy.types.Mesh # type: ignore
        bm = bmesh.from_edit_mesh(mesh)
        # for v in bm.verts:
        #     if v.select:
        #         e = v.link_edges[0]
        #         dir = (e.verts[0].co - e.verts[1].co).normalized()
        #         ret,endpoint = ag_utils.get_sub_verts_along_line(v, dir)
        #         ag_utils.debugprint(f"verts ret: {ret}, endpoint: {endpoint}")
        #         break

        # for e in bm.edges:
        #     if e.select:
        #         ret = ag_utils.get_edges_along_line(e)
        #         ag_utils.debugprint(f"edges ret: {ret}")
        #         break

        # for f in bm.faces:
        #     if f.select:
        #         ret = ag_utils.get_linked_flat(f)
        #         ag_utils.debugprint(f"faces ret: {ret}")
        #         break


# 重载插件
class OT_ReloadAddon(bpy.types.Operator):
    bl_idname = "amagate.reloadaddon"
    bl_label = ""
    bl_description = "Reload Addon"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        base_package = sys.modules[data.PACKAGE]  # type: ignore

        bpy.ops.preferences.addon_disable(module=data.PACKAGE)  # type: ignore
        # base_package.unregister()
        bpy.app.timers.register(
            lambda: bpy.ops.preferences.addon_enable(module=data.PACKAGE) and None,  # type: ignore
            first_interval=0.5,
        )
        # bpy.ops.preferences.addon_enable(module=data.PACKAGE)  # type: ignore
        # base_package.register(reload=True)
        print("插件已热更新！")
        return {"FINISHED"}


# 导出节点
class OT_ExportNode(bpy.types.Operator):
    bl_idname = "amagate.exportnode"
    bl_label = "Export Node"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        # 导出节点
        nodes_data = {}
        nodes_data["AG.Mat1"] = data.export_nodes(bpy.data.materials["AG.Mat1"])
        nodes_data["AG.Mat-1"] = data.export_nodes(bpy.data.materials["AG.Mat-1"])
        nodes_data["Amagate Eval"] = data.export_nodes(
            bpy.data.node_groups["Amagate Eval"]
        )
        # nodes_data["AG.SectorNodes"] = data.export_nodes(
        #     bpy.data.node_groups["AG.SectorNodes"]
        # )
        pickle.dump(nodes_data, open(filepath, "wb"), protocol=pickle.HIGHEST_PROTOCOL)

        with open(filepath + ".tmp", "w", encoding="utf-8") as file:
            pprint(nodes_data, stream=file, indent=0, sort_dicts=False)
        return {"FINISHED"}


class OT_ImportNode(bpy.types.Operator):
    bl_idname = "amagate.importnode"
    bl_label = "Import Node"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))

        name = "AG.Mat1"
        mat = bpy.data.materials.new(name)
        data.import_nodes(mat, nodes_data[name])

        name = "Amagate Eval"
        group = bpy.data.node_groups.new(name, "GeometryNodeTree")  # type: ignore

        group.interface.new_socket(
            "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )
        input_node = group.nodes.new("NodeGroupInput")
        input_node.select = False
        input_node.location.x = -200 - input_node.width

        group.interface.new_socket(
            "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )
        output_node = group.nodes.new("NodeGroupOutput")
        output_node.is_active_output = True  # type: ignore
        output_node.select = False
        output_node.location.x = 200

        group.links.new(input_node.outputs[0], output_node.inputs[0])
        group.use_fake_user = True
        group.is_tool = True  # type: ignore
        group.is_type_mesh = True  # type: ignore
        data.import_nodes(group, nodes_data[name])

        # name = "AG.SectorNodes"
        # NodeTree = bpy.data.node_groups.new(name, "GeometryNodeTree")  # type: ignore
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        # )
        # NodeTree.interface.new_socket(
        #     "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        # )
        # NodeTree.is_modifier = True  # type: ignore
        # data.import_nodes(NodeTree, nodes_data[name])
        return {"FINISHED"}


############################
############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.Operator)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and any(issubclass(cls, parent) for parent in class_tuple)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    from . import L3D_operator, sector_operator

    L3D_operator.register()
    sector_operator.register()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    from . import L3D_operator, sector_operator

    L3D_operator.unregister()
    sector_operator.unregister()
