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
        for name in ("AG.Mat1", "AG.Mat-1", "AG.Cubemap"):
            mat = bpy.data.materials.get(name)
            if mat:
                nodes_data[name] = data.export_nodes(mat)
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
############################ Cubemap转换
############################


class OT_Cubemap2Equirect(bpy.types.Operator):
    bl_idname = "amagate.cubemap2equirect"
    bl_label = "Select and export"
    bl_options = {"INTERNAL"}

    # 过滤文件
    # filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    # filter_image: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore

    # 相对路径
    # relative_path: BoolProperty(name="Relative Path", default=True)  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty()  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    def execute(self, context: Context):
        name_set = {
            "DomeBack",
            "DomeDown",
            "DomeFront",
            "DomeLeft",
            "DomeRight",
            "DomeUp",
        }
        files = []
        for f in self.files:
            if not name_set:
                break
            name = os.path.splitext(f.name)[0]
            if name in name_set:
                name_set.discard(name)
                files.append(f.name)

        if len(files) != 6:
            self.report({"ERROR"}, f"Please select the six cubemap images: {name_set}")
            return {"CANCELLED"}

        scene = bpy.data.scenes.new("AG.Cubemap")
        prev_scene = context.window.scene
        context.window.scene = scene  # 切换场景
        cycles = scene.cycles
        pref = context.preferences.addons[
            data.PACKAGE
        ].preferences  # type: data.AmagatePreferences # type: ignore
        file_format = pref.cubemap_out_format

        # 保存设置
        # settings = {
        #     "scene.render.engine": scene.render.engine,
        #     "cycles.device": cycles.device,
        #     "cycles.use_adaptive_sampling": cycles.use_adaptive_sampling,
        #     "cycles.adaptive_threshold": cycles.adaptive_threshold,
        #     "cycles.samples": cycles.samples,
        #     "cycles.adaptive_min_samples": cycles.adaptive_min_samples,
        #     "cycles.time_limit": cycles.time_limit,
        #     "cycles.use_denoising": cycles.use_denoising,
        #     "cycles.denoiser": cycles.denoiser,
        #     "cycles.denoising_input_passes": cycles.denoising_input_passes,
        #     "cycles.denoising_prefilter": cycles.denoising_prefilter,
        #     "scene.view_settings.view_transform": scene.view_settings.view_transform,
        #     "scene.view_settings.look": scene.view_settings.look,
        #     "scene.view_settings.exposure": scene.view_settings.exposure,
        #     "scene.view_settings.gamma": scene.view_settings.gamma,
        #     "scene.render.use_border": scene.render.use_border,
        #     "scene.render.pixel_aspect_x": scene.render.pixel_aspect_x,
        #     "scene.render.pixel_aspect_y": scene.render.pixel_aspect_y,
        #     "scene.render.resolution_percentage": scene.render.resolution_percentage,
        #     "scene.render.resolution_x": scene.render.resolution_x,
        #     "scene.render.resolution_y": scene.render.resolution_y,
        #     "scene.render.image_settings.color_management": scene.render.image_settings.color_management,
        #     "scene.render.filepath": scene.render.filepath,
        #     "scene.render.image_settings.file_format": scene.render.image_settings.file_format,
        #     "scene.render.image_settings.quality": scene.render.image_settings.quality,
        #     "scene.render.image_settings.color_mode": scene.render.image_settings.color_mode,
        #     "scene.render.image_settings.compression": scene.render.image_settings.compression,
        #     "scene.render.image_settings.color_depth": scene.render.image_settings.color_depth,
        #     "scene.render.image_settings.exr_codec": scene.render.image_settings.exr_codec,
        #     "scene.render.use_file_extension": scene.render.use_file_extension,
        # }

        directory = self.directory.replace("\\", "/")
        if directory.endswith("/"):
            dir_name = directory.split("/")[-2]
        else:
            dir_name = directory.split("/")[-1]
        out_filepath = os.path.join(
            self.directory,
            f"{dir_name}_{pref.cubemap_out_res_x}x{pref.cubemap_out_res_y}",
        )

        # 设置
        scene.render.engine = "CYCLES"  # type: ignore
        # 渲染
        cycles.device = "GPU"
        cycles.use_adaptive_sampling = True
        cycles.adaptive_threshold = 0.01
        cycles.samples = 1  # 采样
        cycles.adaptive_min_samples = 0
        cycles.time_limit = 0.0
        cycles.use_denoising = False  # 降噪
        cycles.denoiser = "OPENIMAGEDENOISE"
        cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        cycles.denoising_prefilter = "ACCURATE"
        scene.view_settings.view_transform = "Standard"  # type: ignore
        scene.view_settings.look = "None"  # type: ignore
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0

        # 输出
        scene.render.use_border = False
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = 1.0
        scene.render.resolution_percentage = 100
        scene.render.resolution_x = pref.cubemap_out_res_x
        scene.render.resolution_y = pref.cubemap_out_res_y
        scene.render.image_settings.color_management = "FOLLOW_SCENE"
        scene.render.filepath = out_filepath
        scene.render.image_settings.file_format = file_format
        scene.render.image_settings.quality = 92
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.compression = 15
        if file_format == "OPEN_EXR":
            scene.render.image_settings.color_depth = "16"
        elif file_format == "HDR":
            scene.render.image_settings.color_depth = "32"
        else:
            scene.render.image_settings.color_depth = "8"
        scene.render.image_settings.exr_codec = "DWAA"
        scene.render.use_file_extension = True

        #
        normal_dict = {}
        for f_name in files:
            filepath = os.path.join(self.directory, f_name)
            if "Back" in f_name:
                normal_dict[(0, 1, 0)] = filepath
            elif "Down" in f_name:
                normal_dict[(0, 0, 1)] = filepath
            elif "Front" in f_name:
                normal_dict[(0, -1, 0)] = filepath
            elif "Left" in f_name:
                normal_dict[(1, 0, 0)] = filepath
            elif "Right" in f_name:
                normal_dict[(-1, 0, 0)] = filepath
            elif "Up" in f_name:
                normal_dict[(0, 0, -1)] = filepath
        # 添加摄像机
        bpy.ops.object.camera_add()
        cam_obj = context.object
        cam_obj.rotation_euler = Euler(
            (1.5707963705062866, 0.0, -1.5707963705062866), "XYZ"
        )
        scene.camera = cam_obj  # 设置活动摄像机
        cam = cam_obj.data  # type: bpy.types.Camera # type: ignore
        cam.type = "PANO"  # 全景
        cam.panorama_type = "EQUIRECTANGULAR"  # ERP
        # 添加立方体
        bpy.ops.mesh.primitive_cube_add(enter_editmode=True)  # 创建立方体
        # bpy.ops.view3d.localview()  # 局部视图
        obj = context.object
        bpy.ops.mesh.select_all(action="SELECT")  # 全选网格
        bpy.ops.mesh.normals_make_consistent(inside=True)  # 重新计算法向(内侧)
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        bpy.ops.object.editmode_toggle()  # 退出编辑模式
        # 设置材质
        filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        nodes_data = pickle.load(open(filepath, "rb"))
        tex_lst = []
        mat_lst = []
        for face in mesh.polygons:
            filepath = normal_dict.get(tuple(int(i) for i in face.normal))
            if not filepath:
                ag_utils.debugprint(f"No cubemap image for normal: {face.normal}")
                return {"CANCELLED"}

            tex = bpy.data.images.load(filepath)  # type: Image # type: ignore
            mat = bpy.data.materials.new(tex.name)
            data.import_nodes(mat, nodes_data["AG.Cubemap"])
            mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
            mat.use_backface_culling = True
            mesh.materials.append(mat)
            slot = obj.material_slots[-1]
            face.material_index = slot.slot_index
            #
            tex_lst.append(tex)
            mat_lst.append(mat)
        #
        bpy.ops.render.render(write_still=True)  # 渲染

        # 清理场景
        context.window.scene = prev_scene
        bpy.data.scenes.remove(scene)
        bpy.data.meshes.remove(mesh)
        bpy.data.cameras.remove(cam)
        for tex in tex_lst:
            bpy.data.images.remove(tex)
        for mat in mat_lst:
            bpy.data.materials.remove(mat)

        return {"FINISHED"}

    def invoke(self, context, event):
        self.filepath = "//"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


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
