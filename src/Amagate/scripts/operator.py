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
import json
import re
from pprint import pprint
from pathlib import Path
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
from bpy_extras.io_utils import ExportHelper
from bpy_extras import anim_utils

from . import data, entity_data
from . import ag_utils
from .ag_utils import epsilon, epsilon2

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection


############################
logger = data.logger
unpack = ag_utils.unpack

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
############################ Cubemap转换
############################


class OT_Cubemap2Equirect(bpy.types.Operator):
    bl_idname = "amagate.cubemap2equirect"
    bl_label = "Select and export"
    bl_description = "Select and export"
    bl_options = {"INTERNAL"}

    # 过滤文件
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore
    filter_image: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
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
            if not f.name.lower().endswith(data.IMAGE_FILTER):
                continue
            name = os.path.splitext(f.name)[0]
            if name in name_set:
                name_set.discard(name)
                files.append(f.name)

        if len(files) != 6:
            self.report(
                {"ERROR"},
                f"{pgettext('Please select the six cubemap images')}: {name_set}",
            )
            return {"FINISHED"}

        scene = bpy.data.scenes.new("AG.Cubemap")
        prev_scene = context.window.scene
        # 保存当前场景的视角
        view_perspective = {}
        for area in context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next(r for r in area.regions if r.type == "WINDOW")
            rv3d = region.data
            view_perspective[rv3d] = rv3d.view_perspective

        context.window.scene = scene  # 切换场景
        cycles = scene.cycles
        pref = context.preferences.addons[
            data.PACKAGE
        ].preferences  # type: data.AmagatePreferences # type: ignore
        file_format = pref.cubemap_out_format

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
                return {"FINISHED"}

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
        # 还原视角
        for rv3d, perspective in view_perspective.items():
            rv3d.view_perspective = perspective

        return {"FINISHED"}

    def invoke(self, context, event):
        # 设为上次选择目录，文件名为空
        self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


############################
############################ PAK转换
############################


# PAK打包
class OT_PakPack(bpy.types.Operator):
    bl_idname = "amagate.pak_pack"
    bl_label = "Pack"
    bl_description = "Select a folder to package"
    bl_options = {"INTERNAL"}

    # 过滤文件
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})  # type: ignore

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    def execute(self, context: Context):
        directory = Path(self.directory)
        paths = [filepath for filepath in directory.rglob("*") if filepath.is_file()]
        if not paths:
            self.report({"INFO"}, "Folder is empty")
            return {"FINISHED"}
        pak_filepath = directory.parent / (directory.name + ".pak")
        try:
            pak_file = open(pak_filepath, "wb+")
        except IOError:
            self.report({"ERROR"}, f"Failed to open {pak_filepath}")
            return {"FINISHED"}

        physicalDirectoryPath = Path("Save") / pak_filepath.name
        b_physicalDirectoryPath = f"{physicalDirectoryPath.as_posix()}\x00".encode(
            "utf-8"
        )
        #
        pak_file.write(b"\x00" * 8)
        pak_file.write(b"\x04")
        pak_file.write(b"fileDescriptorTable\x00")
        pak_file.write(b"\xf0")  # 未知
        pak_file.write(struct.pack("H", len(paths) - 2))
        #
        data_offset = 0
        for idx, filepath in enumerate(paths):
            file_size = filepath.stat().st_size
            rel_path = filepath.relative_to(directory)

            pak_file.write(b"\x00\x03")
            pak_file.write(f"{idx}\x00".encode("ascii"))
            pak_file.write(b"\xf0")  # 未知
            pak_file.write(bytes.fromhex("00000010"))

            pak_file.write(b"byteCount\x00")
            pak_file.write(struct.pack("I", file_size))
            pak_file.write(b"\x10")

            pak_file.write(b"byteIndex\x00")
            pak_file.write(struct.pack("I", data_offset))
            data_offset += file_size
            pak_file.write(b"\x02")

            pak_file.write(b"compression\x00")
            pak_file.write(struct.pack("I", 5))

            pak_file.write(b"None\x00")
            pak_file.write(struct.pack("B", 8))

            pak_file.write(b"isReadOnly\x00")
            pak_file.write(struct.pack("B", 0))
            pak_file.write(b"\x08")

            pak_file.write(b"isVirtual\x00")
            pak_file.write(struct.pack("B", 1))
            pak_file.write(b"\x02")
            #
            pak_file.write(b"logicalDirectoryPath\x00")
            b_str = f"{rel_path.parent.as_posix()}/\x00".encode("utf-8")
            pak_file.write(struct.pack("I", len(b_str)))
            pak_file.write(b_str)
            pak_file.write(b"\x02")

            pak_file.write(b"logicalName\x00")
            b_str = f"{rel_path.name}\x00".encode("utf-8")
            pak_file.write(struct.pack("I", len(b_str)))
            pak_file.write(b_str)
            pak_file.write(b"\x02")

            pak_file.write(b"physicalDirectoryPath\x00")
            pak_file.write(struct.pack("I", len(b_physicalDirectoryPath)))
            pak_file.write(b_physicalDirectoryPath)
            pak_file.write(b"\x02")

            pak_file.write(b"physicalName\x00")
            pak_file.write(struct.pack("I", 1))
            pak_file.write(b"\x00")
            pak_file.write(b"\x02")
            #
            pak_file.write(b"type\x00")
            pak_file.write(struct.pack("I", 5))

            pak_file.write(b"File\x00")
            #
        pak_file.write(b"\x00" * 3)

        head_end_pos = pak_file.tell()
        head_size = head_end_pos - 4
        pak_file.seek(0, 0)
        pak_file.write(struct.pack("II", head_size, head_size))
        pak_file.seek(head_end_pos, 0)
        #
        for filepath in paths:
            with open(filepath, "rb") as f:
                pak_file.write(f.read())
        #
        self.report({"INFO"}, "Done")
        return {"FINISHED"}

    def invoke(self, context, event):
        # 设为上次选择目录，文件名为空
        # self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# PAK解包
class OT_PakUnpack(bpy.types.Operator):
    bl_idname = "amagate.pak_unpack"
    bl_label = "Unpack"
    bl_description = "Select pak files to unpack"
    bl_options = {"INTERNAL"}

    filter_glob: StringProperty(default="*.pak", options={"HIDDEN"})  # type: ignore

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # filename: StringProperty()  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    def execute(self, context: Context):
        directory = Path(self.directory)
        suffix = ".pak"
        if len(self.files) == 1 and self.files[0].name == "":
            paths = [
                f
                for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() == suffix
            ]
        else:
            paths = [
                f
                for i in self.files
                if (f := directory / i.name).is_file() and f.suffix.lower() == suffix
            ]
        if len(paths) == 0:
            self.report({"INFO"}, "No valid files selected")

        #
        for filepath in paths:
            folderpath = filepath.with_name(filepath.stem)
            folderpath.mkdir(parents=True, exist_ok=True)
            files_dict = {}
            #
            with open(filepath, "rb") as f:
                head_size = unpack("I", f)[0]
                f.seek(5, 1)  # 重复头大小 b'\x04'
                f.seek(20, 1)  # b"fileDescriptorTable\x00"
                flag1 = unpack("B", f)[0]  # 未知
                file_count = unpack("H", f)[0] + 2
                for index in range(file_count):
                    # print(index)
                    f.seek(2, 1)  # 跳过 b'\x00\x03'

                    buffer = f.read(1)
                    while (b_str := f.read(1)) != b"\x00":
                        buffer += b_str
                    idx = int(buffer.decode("ascii"))
                    if idx != index:
                        logger.debug(f"Invalid index: {idx} != {index}")
                    # f.seek(1, 1) # 跳过 b'\x00'

                    flag2 = unpack("B", f)[0]  # 未知
                    f.seek(4, 1)  # 跳过 00000010
                    f.seek(10, 1)  # byteCount\x00
                    file_size = unpack("I", f)[0]
                    f.seek(1, 1)  # 跳过 b'\x10'
                    f.seek(10, 1)  # byteIndex\x00
                    data_offset = unpack("I", f)[0]
                    f.seek(1, 1)  # 跳过 b'\x02'

                    f.seek(12, 1)  # compression\x00
                    compression = unpack("I", f)[0]  # 默认5
                    f.seek(5, 1)  # None\x00
                    none = unpack("B", f)[0]  # 默认8
                    f.seek(11, 1)  # isReadOnly\x00
                    isReadOnly = unpack("B", f)[0]  # 默认0
                    f.seek(1, 1)  # 跳过 b'\x08'
                    f.seek(10, 1)  # isVirtual\x00
                    f.seek(1, 1)  # 跳过 b'\x01'
                    f.seek(1, 1)  # 跳过 b'\x02'

                    f.seek(21, 1)  # logicalDirectoryPath\x00
                    length = unpack("I", f)[0]
                    logicalDirectoryPath = folderpath / f.read(length).decode(
                        "utf-8"
                    ).strip("\x00")
                    f.seek(1, 1)  # 跳过 b'\x02'

                    f.seek(12, 1)  # logicalName\x00
                    length = unpack("I", f)[0]
                    logicalName = f.read(length).decode("utf-8").strip("\x00")
                    f.seek(1, 1)  # 跳过 b'\x02'

                    f.seek(22, 1)  # physicalDirectoryPath\x00
                    length = unpack("I", f)[0]
                    physicalDirectoryPath = f.read(length).decode("utf-8").strip("\x00")
                    # f.seek(length, 1)
                    f.seek(1, 1)  # 跳过 b'\x02'

                    f.seek(13, 1)  # physicalName\x00
                    length = unpack("I", f)[0]
                    # physicalName = unpack("B", f)[0]
                    f.seek(1, 1)  # 跳过 b'\x00'
                    f.seek(1, 1)  # 跳过 b'\x02'

                    f.seek(5, 1)  # type\x00
                    f.seek(4, 1)  # 默认5
                    f.seek(5, 1)  # File\x00
                    #
                    files_dict[data_offset] = [
                        flag2,
                        file_size,
                        compression,
                        none,
                        isReadOnly,
                        logicalDirectoryPath,
                        logicalName,
                    ]
                #
                f.seek(3, 1)  # 000
                # pprint(files_dict)
                for k in sorted(files_dict.keys()):
                    (
                        flag2,
                        file_size,
                        compression,
                        none,
                        isReadOnly,
                        logicalDirectoryPath,
                        logicalName,
                    ) = files_dict[k]
                    logicalDirectoryPath.mkdir(parents=True, exist_ok=True)
                    try:
                        with open(logicalDirectoryPath / logicalName, "wb") as fw:
                            fw.write(f.read(file_size))
                    except:
                        pass

        self.report({"INFO"}, "Done")
        return {"FINISHED"}

    def invoke(self, context, event):
        # 设为上次选择目录，文件名为空
        # self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


############################
############################ 模型包
############################


# 在文件浏览器中打开
class OT_ModelPackOpen(bpy.types.Operator):
    bl_idname = "amagate.model_pack_open"
    bl_label = "Open in File Browser"
    bl_description = "Open in File Browser"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        return data.MODELPACKAGE_VERSION != "None"

    def execute(self, context: Context):
        filepath = Path(data.ADDON_PATH) / "Models"
        bpy.ops.wm.path_open(filepath=str(filepath))
        return {"FINISHED"}


# 导入
class OT_ModelPackImport(bpy.types.Operator):
    bl_idname = "amagate.model_pack_import"
    bl_label = "Import"
    bl_description = "Import"
    bl_options = {"INTERNAL"}

    filter_glob: StringProperty(default="*.zip", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context: Context):
        filepath = Path(self.filepath)
        if not (filepath.is_file() and filepath.suffix.lower() == ".zip"):
            self.report({"ERROR"}, f"{pgettext('Invalid file')}: {filepath.name}")
            return {"FINISHED"}
        # 解压
        ag_utils.extract_file(filepath, Path(data.ADDON_PATH), overwrite=True)
        # 更新版本变量
        filepath = Path(data.ADDON_PATH) / "Models/version"
        if filepath.exists():
            with open(filepath, "r") as f:
                data.MODELPACKAGE_VERSION = f.readline().strip()
        # 重载预览
        entity_data.load_ent_preview(reload=True)

        self.report({"INFO"}, f"Import completed")
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        # 设为上次选择目录，文件名为空
        if not self.filepath:
            self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


############################
############################ 调试面板
############################


class OT_Test(bpy.types.Operator):
    bl_idname = "amagate.test"
    bl_label = "功能集合"
    bl_options = {"INTERNAL", "UNDO"}

    action: EnumProperty(
        name="",
        description="",
        items=[
            ("1", "Batch Import BOD", ""),
            ("2", "Batch Import BMV", ""),
            ("3", "update_trail_spike", ""),
            ("4", "test1", ""),
            ("5", "test2", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore

    def execute(self, context: Context):
        cb_dict = {
            "Batch Import BOD": self.import_bod,
            "Batch Import BMV": self.import_bmv,
            "update_trail_spike": self.update_trail_spike,
            "test1": self.test1,
            "test2": self.test2,
        }
        name = bpy.types.UILayout.enum_item_name(self, "action", self.action)
        cb_dict[name](context)

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

    @staticmethod
    def import_bod(context: Context):
        # 基于4.3版本使用
        from . import entity_operator as OP_ENTITY

        update_existing = 1

        models_path = os.path.join(data.ADDON_PATH, "Models")
        preview_dir = os.path.join(models_path, "Preview")
        # manifest = json.load(
        #     open(os.path.join(models_path, "manifest.json"), encoding="utf-8")
        # )
        ent_dir = ("3DChars", "3DObjs")[1]
        root = os.path.join(models_path, ent_dir)
        # manifest_dict = manifest["Entities"]

        #
        DefaultSelectionData = {}
        # exec(open(os.path.join(models_path, "EnglishUS.py")).read())

        count = 0
        rv3d = context.region_data  # type: bpy.types.RegionView3D
        scene = context.scene  # type: Scene
        padding = 0.05
        x_axis = Vector((1, 0, 0))
        y_axis = Vector((0, 1, 0))
        z_axis = Vector((0, 0, 1))
        #
        scene.eevee.taa_render_samples = 8
        scene.display.shading.light = "FLAT"
        scene.display.shading.color_type = "TEXTURE"
        if ent_dir == "3DChars":
            scene.render.resolution_x = 1024
            scene.render.resolution_y = 1024
        else:
            scene.render.resolution_x = 512
            scene.render.resolution_y = 512
        scene.render.image_settings.file_format = "JPEG"
        scene.render.image_settings.quality = 90
        scene.render.film_transparent = True

        save_version = context.preferences.filepaths.save_version
        context.preferences.filepaths.save_version = 0
        lack_texture_lst = []
        dup_face_lst = []
        name_lst = []
        print(len(name_lst))
        for f_name in os.listdir(root):
            if f_name.lower().endswith(".bod"):
                name_lst.append(f_name)
        for f_name in name_lst:
            # f_name = f_name + ".bod"
            count += 1
            filepath = os.path.join(root, f_name)

            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            # 清空场景
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete(use_global=True)
            for d in (
                bpy.data.meshes,
                bpy.data.lights,
                bpy.data.cameras,
                bpy.data.collections,
                bpy.data.materials,
                bpy.data.images,
                bpy.data.armatures,
            ):
                for _ in range(len(d)):
                    # 倒序删除，避免集合索引更新的开销
                    d.remove(d[-1])  # type: ignore

            # 导入
            (
                entity,
                lack_texture,
                folded_faces,
                multiple_folded_face,
                zero_width_faces,
            ) = OP_ENTITY.OT_ImportBOD.import_bod(context, filepath)
            if folded_faces:
                print(f"Folded faces found in {f_name}: {folded_faces}")
            else:
                continue
            if multiple_folded_face:
                print(f"Abnormal faces found in {f_name}: {multiple_folded_face}")
            # if lack_texture:
            #     lack_texture_lst.append(Path(filepath).stem)
            # if dup_face:
            #     dup_face_lst.append(Path(filepath).stem)
            # continue

            skeleton = bpy.data.objects.get("Blade_Skeleton")
            view = "Top"
            if skeleton:
                pass
                # anchor = bpy.data.objects.get("Blade_Anchor_ViewPoint")
                # if anchor:
                #     if abs(anchor.matrix_world.col[1].xyz.dot(z_axis)) > 0.7:
                #         view = "FRONT"
            else:
                anchor = bpy.data.objects.get("Blade_Anchor_1H_R")
                if anchor:
                    dir_y = anchor.matrix_world.col[1].xyz
                    if abs(dir_y.dot(y_axis)) > 0.7:
                        view = "Front"
                    elif abs(dir_y.dot(x_axis)) > 0.7:
                        view = "Right"

            # bpy.ops.view3d.view_axis(type=view)

            #
            if update_existing:
                # bpy.ops.wm.open_mainfile(filepath=os.path.splitext(filepath)[0] + ".blend")
                with bpy.data.libraries.load(
                    os.path.splitext(filepath)[0] + ".blend", link=False
                ) as (
                    data_from,
                    data_to,
                ):
                    data_to.objects = ["Camera"]
                camera = data_to.objects[0]
                scene.collection.objects.link(camera)
                scene.camera = camera  # 设置活动摄像机
                rv3d.view_perspective = "CAMERA"
                camera.hide_set(True)
                bpy.data.libraries.remove(bpy.data.libraries[0])
            else:
                camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
                scene.collection.objects.link(camera)
                scene.camera = camera  # 设置活动摄像机
                rv3d.view_perspective = "CAMERA"
                camera.hide_set(True)
                fov = math.degrees(camera.data.angle)  # type: ignore

                verts = [entity.matrix_world @ Vector(v) for v in entity.bound_box]

                if view == "Top":
                    look_at = Vector((0, 0, -1))
                    u, v = Vector((1, 0, 0)), Vector((0, 1, 0))
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Front":
                    look_at = Vector((0, 1, 0))
                    u, v = Vector((1, 0, 0)), Vector((0, 0, 1))
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Front 45°":
                    look_at = Vector((0, 1, -1)).normalized()
                    u, v = Vector((1, 0, 0)), Vector((0, 1, 1)).normalized()
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Right":
                    look_at = Vector((-1, 0, 0))
                    u, v = Vector((0, 1, 0)), Vector((0, 0, 1))
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Right 45°":
                    look_at = Vector((-1, 0, -1)).normalized()
                    u, v = Vector((0, 1, 0)), Vector((-1, 0, 1)).normalized()
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Back":
                    look_at = Vector((0, -1, 0))
                    u, v = Vector((-1, 0, 0)), Vector((0, 0, 1))
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Left":
                    look_at = Vector((1, 0, 0))
                    u, v = Vector((0, -1, 0)), Vector((0, 0, 1))
                    base_len = min(v.dot(look_at) for v in verts)
                elif view == "Bottom":
                    look_at = Vector((0, 0, 1))
                    u, v = Vector((1, 0, 0)), Vector((0, -1, 0))
                    base_len = min(v.dot(look_at) for v in verts)

                verts = [Vector((vert.dot(u), vert.dot(v))) for vert in verts]
                min_x = min(v.x for v in verts)
                max_x = max(v.x for v in verts)
                min_y = min(v.y for v in verts)
                max_y = max(v.y for v in verts)
                width = max_x - min_x
                height = max_y - min_y
                max_dimension = max(width, height) + padding
                distance = (max_dimension / 2) / math.tan(math.radians(fov / 2))
                x = (min_x + max_x) * 0.5 * u
                y = (min_y + max_y) * 0.5 * v
                z = look_at * (base_len - distance)
                camera.rotation_euler = look_at.to_track_quat("-Z", "Y").to_euler()
                camera.location = x + y + z  # type: ignore

            #
            scene.render.filepath = "//tmp"
            context.space_data.shading.type = "MATERIAL"  # type: ignore
            save_name = f"{f_name[:-4]}.blend"
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, save_name))
            # manifest_dict[obj.name] = [
            #     DefaultSelectionData.get(obj.name, (0, 0, obj.name))[2],
            #     os.path.join(ent_dir, save_name),
            # ]
            # key += 1
            #

            # if lack_texture:
            #     context.space_data.shading.type = "SOLID"  # type: ignore
            # else:
            #     context.space_data.shading.type = "MATERIAL"  # type: ignore

            # 渲染
            if not update_existing:
                for mat in bpy.data.materials:
                    mat.use_backface_culling = False
                ag_utils.select_active(context, entity)  # type: ignore
                camera.select_set(True)
                bpy.ops.object.select_all(action="INVERT")
                bpy.ops.object.delete()

                scene.render.filepath = os.path.join(
                    preview_dir, os.path.splitext(save_name)[0]
                )
                bpy.ops.render.render(write_still=True)

        # context.preferences.filepaths.save_version = save_version
        # print(f"dup face: {dup_face_lst}")
        # print(f"lack texture: {lack_texture_lst}")
        #
        # json.dump(
        #     manifest,
        #     open(os.path.join(models_path, "manifest.json"), "w", encoding="utf-8"),
        #     indent=4,
        #     ensure_ascii=False,
        #     sort_keys=True,
        # )

    def import_bmv(self, context: Context):
        from . import anim_operator as OP_ANIM

        for img in bpy.data.images:
            if not img.filepath.startswith("//"):
                p = Path(img.filepath)
                img.filepath = "//../" + "/".join(p.parts[-3:])
        #
        # cam = context.scene.camera
        # cam.location = 0,-3,0
        # cam.rotation_euler = math.pi/2,0,0
        return
        #
        prefix = "ank2_"
        directory = Path("D:/BLADE/Work/Amagate/src/Amagate/Models/Anm/Anm")
        paths = [
            f
            for f in directory.iterdir()
            if f.is_file()
            and f.suffix.lower() == ".bmv"
            and f.stem.lower().startswith(prefix)
        ]
        # print(paths[0])
        OP_ANIM.OT_ImportAnim.execute2(self, context, paths)  # type: ignore
        print(len(paths))
        for f in paths:
            os.remove(f)

    # 更新Trail和Spike
    def update_trail_spike(self, context: Context):
        from . import entity_operator as OP_ENTITY

        models_path = Path(data.ADDON_PATH) / "Models"
        count = 0
        path = os.path.join(data.ADDON_PATH, "bin/ent_component.dat")
        mesh_dict = pickle.load(open(path, "rb"))
        target_space = Matrix.Rotation(-math.pi / 2, 4, "X")
        target_space_inv = Matrix.Rotation(
            -math.pi / 2, 4, "X"
        ).inverted()  # type: Matrix

        def final():
            pass

        def parse():
            with open(bod_file, "rb") as f:
                file_size = os.fstat(f.fileno()).st_size
                # 内部名称
                length = unpack("I", f)[0]
                inter_name = unpack(f"{length}s", f)
                # 顶点
                verts_num = unpack("I", f)[0]
                f.seek(48 * verts_num, 1)
                # 面
                faces_num = unpack("I", f)[0]
                for i in range(faces_num):
                    # vert_idx
                    f.seek(12, 1)
                    length = unpack("I", f)[0]
                    # img_name = unpack(f"{length}s", f)
                    f.seek(length, 1)
                    # uv_list
                    f.seek(24, 1)
                    # 跳过0
                    f.seek(4, 1)
                # 骨架
                bones_num = unpack("I", f)[0]
                for i in range(bones_num):
                    if bones_num != 1:
                        length = unpack("I", f)[0]
                        f.seek(length, 1)
                        # name = unpack(f"{length}s", f)
                    f.seek(140, 1)
                    num = unpack("I", f)[0]
                    for j in range(num):
                        f.seek(40, 1)
                # 几何中心
                f.seek(32, 1)
                # 火焰
                num = unpack("I", f)[0]
                for idx in range(num):
                    verts_num = unpack("I", f)[0]
                    for i in range(verts_num):
                        f.seek(28, 1)
                    f.seek(8, 1)
                # 灯光
                num = unpack("I", f)[0]
                for idx in range(num):
                    f.seek(36, 1)
                # 锚点
                num = unpack("I", f)[0]
                for idx in range(num):
                    length = unpack("I", f)[0]
                    f.seek(length, 1)
                    f.seek(132, 1)
                # 剩余数据种类
                data_num_remain = data_num = unpack("I", f)[0]
                if data_num == 0:
                    return final()

                # 边缘
                num = unpack("I", f)[0]
                for idx in range(num):
                    f.seek(80, 1)

                data_num -= 1
                if data_num == 0:
                    return final()

                # 尖刺
                num = unpack("I", f)[0]
                for idx in range(num):
                    mark = unpack("I", f)[0]  # 默认0
                    if mark != 0:
                        logger.debug(f"Spike - mark not 0: {mark}")
                    #
                    parent_idx = unpack("i", f)[0]  # type: int
                    pt1 = Vector(unpack("ddd", f)) / 1000
                    pt2 = pt1 + Vector(unpack("ddd", f)) / 1000
                    #
                    obj_name = data.get_object_name("Blade_Spike_")
                    mesh = bpy.data.meshes.new(obj_name)
                    obj = bpy.data.objects.new(
                        obj_name, mesh
                    )  # type: Object # type: ignore
                    obj.show_in_front = True
                    obj.amagate_data.ent_comp_type = 2
                    data.link2coll(obj, ent_coll)
                    #
                    parent_matrix = None
                    if parent_idx != -1:
                        if armature is not None:
                            bone_name = bones_name[parent_idx]
                            parent_matrix = bone_matrix[bone_name]
                            obj.parent = armature_obj  # type: ignore
                            obj.parent_type = "BONE"
                            obj.parent_bone = bone_name
                        else:
                            obj.parent = entity  # type: ignore
                    #
                    if parent_matrix:
                        pt1 = parent_matrix @ pt1
                        pt2 = parent_matrix @ pt2
                    #
                    mesh_data = mesh_dict["Blade_Spike_1"]
                    bm = bmesh.new()
                    verts = []
                    for co in mesh_data["vertices"]:
                        verts.append(bm.verts.new(co))
                    for idx in mesh_data["edges"]:
                        bm.edges.new([verts[i] for i in idx])
                    # 调整大小
                    move_y = (pt2 - pt1).length - 0.1
                    bmesh.ops.translate(bm, vec=(0, move_y, 0), verts=[verts[i] for i in range(1, 6)])  # type: ignore
                    # 调整朝向
                    quat = (pt2 - pt1).normalized().to_track_quat("Y", "Z")
                    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=quat.to_matrix(), verts=bm.verts)  # type: ignore

                    bm.to_mesh(mesh)
                    bm.free()
                    #
                    context.view_layer.update()
                    obj.matrix_world = target_space @ Matrix.Translation(pt1)

                data_num -= 1
                if data_num == 0:
                    return final()

                # 组
                num = unpack("I", f)[0]
                f.seek(num, 1)
                # 肢解组
                num = unpack("I", f)[0]
                f.seek(num * 4, 1)

                data_num -= 1
                if data_num == 0:
                    return final()

                # 轨迹
                num = unpack("I", f)[0]
                for idx in range(num):
                    mark = unpack("I", f)[0]  # 默认0
                    if mark != 0:
                        logger.debug(f"Track - mark not 0: {mark}")
                    parent_idx = unpack("i", f)[0]  # type: int
                    pt1 = Vector(unpack("ddd", f)) / 1000
                    pt2 = pt1 + Vector(unpack("ddd", f)) / 1000
                    #
                    obj_name = data.get_object_name("Blade_Trail_")
                    mesh = bpy.data.meshes.new(obj_name)
                    obj = bpy.data.objects.new(
                        obj_name, mesh
                    )  # type: Object # type: ignore
                    obj.show_in_front = True
                    obj.amagate_data.ent_comp_type = 3
                    data.link2coll(obj, ent_coll)
                    #
                    parent_matrix = None
                    if parent_idx != -1:
                        if armature is not None:
                            bone_name = bones_name[parent_idx]
                            parent_matrix = bone_matrix[bone_name]
                            obj.parent = armature_obj  # type: ignore
                            obj.parent_type = "BONE"
                            obj.parent_bone = bone_name
                        else:
                            obj.parent = entity  # type: ignore
                    #
                    if parent_matrix:
                        pt1 = parent_matrix @ pt1
                        pt2 = parent_matrix @ pt2
                    #
                    bm = bmesh.new()
                    bm.verts.new(pt1)
                    bm.verts.new(pt2)
                    bm.edges.new(bm.verts)

                    bm.to_mesh(mesh)
                    bm.free()

                    context.view_layer.update()
                    obj.matrix_world = target_space

                return final()

        for dir in ("3DObjs", "3DChars"):
            root = models_path / dir
            for filepath in root.glob("*.blend"):
                if 1:  # filepath.stem == "Sawsword":
                    count += 1
                    bpy.ops.wm.open_mainfile(filepath=str(filepath))
                    for idx in range(len(bpy.data.objects) - 1, -1, -1):
                        obj = bpy.data.objects[idx]
                        if obj.name.lower().startswith(
                            ("blade_spike_", "blade_trail_")
                        ):
                            bpy.data.objects.remove(obj)
                    ent_coll, entity, has_fire, has_light = OP_ENTITY.get_ent_data()
                    offset = entity.location.copy()
                    for obj in ent_coll.objects:
                        if not obj.parent:
                            obj.location -= offset
                    cam = bpy.context.scene.camera
                    if cam:
                        cam.location -= offset
                    armature_obj = next(
                        (m.object for m in entity.modifiers if m.type == "ARMATURE"),  # type: ignore
                        None,
                    )  # type: Object
                    armature = (
                        armature_obj.data if armature_obj else None
                    )  # type: bpy.types.Armature # type: ignore
                    if armature:
                        bones_name = {
                            i: bone.name for i, bone in enumerate(armature.bones)
                        }
                        bone_matrix = {
                            bone.name: target_space_inv @ bone.matrix
                            for i, bone in enumerate(armature_obj.pose.bones)
                        }

                    bod_file = (
                        Path("D:/GOG Galaxy/Games/Blade of Darkness V109 GOG/classic")
                        / dir
                        / f"{filepath.stem}.bod"
                    )
                    if bod_file.exists():
                        parse()
                        area = next(
                            a
                            for a in bpy.data.screens["Layout"].areas
                            if a.type == "VIEW_3D"
                        )
                        area.spaces[0].shading.type = "MATERIAL"  # type: ignore
                        bpy.ops.wm.save_mainfile()
                    else:
                        print(f"{bod_file.name} not found")

                    # break
            # break
        print(count)

    @staticmethod
    def test1(context: Context):
        from . import entity_operator as OP_ENTITY

        name_lst = []
        count = 0
        change_count = 0
        models_path = Path(os.path.join(data.ADDON_PATH, "Models"))
        # filepath = os.path.join(data.ADDON_PATH, "bin/nodes.dat")
        # nodes_data = pickle.load(open(filepath, "rb"))
        scalc_init = Vector((1, 1, 1))
        for dir in ["3DObjs", "3DChars"]:
            root = models_path / dir
            for f_name in os.listdir(root):
                if f_name.lower().endswith(".blend"):
                    count += 1
                    filepath = root / f_name
                    changed = False
                    with contextlib.redirect_stdout(StringIO()):
                        bpy.ops.wm.open_mainfile(filepath=str(filepath))
                    # for obj in bpy.data.objects:
                    #     if obj.name.lower().startswith("blade_anchor_"):
                    #         if obj.scale != scalc_init:
                    #             obj.scale = (1, 1, 1)
                    #             changed = True
                    # ent_coll, entity, _, _ = OP_ENTITY.get_ent_data()
                    # if entity.get("AG.ambient_color") is not None:
                    #     continue
                    # entity["AG.ambient_color"] = (1.0, 1.0, 1.0)  # type: ignore
                    # entity.id_properties_ui("AG.ambient_color").update(
                    #     subtype="COLOR", min=0.0, max=1.0, default=(1, 1, 1), step=0.1
                    # )
                    # for mat in bpy.data.materials:
                    # tex = mat.node_tree.nodes["Image Texture"].image  # type: ignore
                    # data.import_nodes(mat, nodes_data["Export.EntityTex"])
                    # mat.use_fake_user = False
                    # mat.node_tree.nodes["Image Texture"].image = tex  # type: ignore
                    # mat.use_backface_culling = True
                    # 图像路径
                    # for img in bpy.data.images:
                    #     if img.name != "Render Result":
                    #         if not img.filepath.startswith("//textures"):
                    #             # name_lst.append(f"{dir}/{f_name}")
                    #             # break
                    #             img.filepath = f"//textures/{bpy.path.basename(img.filepath)}"
                    #             changed = 1
                    # 骨骼组
                    armature = bpy.data.armatures.get("Blade_Skeleton")
                    if armature:
                        if "Blade_Bones" not in armature.collections:
                            armature.collections.new("Blade_Bones")
                            coll = armature.collections["Blade_Bones"]
                            for bone in armature.bones:
                                coll.assign(bone)
                            changed = 1
                    #

                    if changed:
                        bpy.ops.wm.save_mainfile()
                        change_count += 1
        print(f"count: {count}", f"change_count: {change_count}")

    def test2(self, context: Context):
        from . import entity_operator as OP_ENTITY

        # root = Path("D:/GOG Galaxy/Games/Blade of Darkness V109 GOG/classic/3DObjs")
        # count = 0
        # for filepath in root.iterdir():
        #     if filepath.suffix.lower() == ".bod":
        #         OP_ENTITY.parse_bod(filepath)
        #         count += 1
        # print(count)

        # manifest = json.load(
        #     open(os.path.join(data.ADDON_PATH, "Models", "manifest.json"), encoding="utf-8"))
        root = Path(data.ADDON_PATH, "Models", "Anm")
        count = 0
        for filepath in root.glob("*.blend"):
            count += 1
            with contextlib.redirect_stdout(StringIO()):
                bpy.ops.wm.open_mainfile(filepath=str(filepath))
            for idx in range(len(bpy.data.objects) - 1, -1, -1):
                obj = bpy.data.objects[idx]
                if obj.name.lower().startswith(("blade_spike_", "blade_trail_")):
                    bpy.data.objects.remove(obj)
            if filepath.stem != "Object":
                entity = bpy.data.objects.get(filepath.stem)
                offset = entity.location.copy()
                for obj in bpy.data.objects:
                    if not obj.parent:
                        obj.location -= offset
            else:
                entity = bpy.data.objects.get("Totem2")
                offset = entity.location.copy()
                cam = bpy.context.scene.camera
                if cam:
                    cam.location -= offset
                for obj in bpy.data.objects:
                    if not obj.parent and obj.name != "Camera":
                        obj.location = 0, 0, 0

            bpy.ops.wm.save_mainfile()

            # anm_lst = [i.name for i in bpy.data.actions]
            # count += len(anm_lst)
            # manifest["Animations"][filepath.name] = anm_lst
        # json.dump(
        #     manifest,
        #     open(os.path.join(data.ADDON_PATH, "Models", "manifest.json"), "w", encoding="utf-8"),
        #     indent=4,
        #     ensure_ascii=False,
        #     sort_keys=True,
        # )
        print(count)

    def test3(self, context: Context):
        # bpy.ops.wm.console_toggle()

        def export_with_progress():
            wm = bpy.context.window_manager
            wm.progress_begin(0, 252)  # 初始化进度条
            progress = 0
            while progress < 252:
                progress += 1
                # print(f"progress: {progress}")
                wm.progress_update(progress)  # 更新进度
                time.sleep(0.05)  # 替换为实际导出逻辑
            wm.progress_end()  # 结束
            # for i in range(5,0,-1):
            #     time.sleep(0.5)  # 替换为实际导出逻辑
            #     wm.progress_update(i)  # 更新进度
            # wm.progress_end()  # 结束

        export_with_progress()

        # mesh = context.object.data  # type: bpy.types.Mesh # type: ignore
        # bm = bmesh.from_edit_mesh(mesh)
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
            lambda: (bpy.ops.preferences.addon_enable(module=data.PACKAGE), None)[-1],  # type: ignore
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
        nodes_data = pickle.load(open(filepath, "rb"))
        # nodes_data = {}
        # 材质节点
        for name in ("AG.Mat1", "AG.Mat-1", "AG.Cubemap"):
            mat = bpy.data.materials.get(name)
            if mat:
                nodes_data[name] = data.export_nodes(mat)
        # 几何节点
        for name in (
            "Amagate Eval",
            "AG.FrustumCulling",
            "AG.SectorNodes",
            "AG.World Baking",  # 弃用
            "AG.World Baking.NodeGroup",  # 弃用
        ):
            node = bpy.data.node_groups.get(name)
            if node:
                nodes_data[name] = data.export_nodes(node)
        # nodes_data["Amagate Eval"] = data.export_nodes(
        #     bpy.data.node_groups["Amagate Eval"]
        # )
        # nodes_data["AG.FrustumCulling"] = data.export_nodes(
        #     bpy.data.node_groups["AG.FrustumCulling"]
        # )
        # nodes_data["AG.SectorNodes"] = data.export_nodes(
        #     bpy.data.node_groups["AG.SectorNodes"]
        # )
        # 世界节点
        node = bpy.data.worlds.get("BWorld")
        if node:
            nodes_data[node.name] = data.export_nodes(node)
        # nodes_data["AG.SectorNodes"] = data.export_nodes(
        #     bpy.data.node_groups["AG.SectorNodes"]
        # )
        # 标记为导出的材质
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue
            if mat.name.startswith("Export."):
                nodes_data[mat.name] = data.export_nodes(mat)
        #
        print(f"节点数量: {len(nodes_data)}")
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


# 导出实体组件
class OT_ExportEntComponent(bpy.types.Operator):
    bl_idname = "amagate.db_export_ent_component"
    bl_label = "Export Entity Component"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        filepath = os.path.join(data.ADDON_PATH, "bin/ent_component.dat")
        if os.path.exists(filepath):
            mesh_dict = pickle.load(open(filepath, "rb"))
        else:
            mesh_dict = {}
        #
        obj_name = ("Blade_Edge_1", "Blade_Spike_1", "Blade_Trail_1", "B_Fire_Fuego_1")
        for name in obj_name:
            obj = bpy.data.objects.get(name)
            if not obj:
                continue
            # matrix = obj.matrix_world.copy()
            mesh_data = {"vertices": [], "edges": [], "faces": []}
            mesh = obj.data  # type: bpy.types.Mesh # type: ignore
            for v in mesh.vertices:
                mesh_data["vertices"].append(v.co.to_tuple(4))
            for e in mesh.edges:
                mesh_data["edges"].append(tuple(e.vertices))
            for f in mesh.polygons:
                mesh_data["faces"].append(tuple(e.vertices))
            mesh_dict[name] = mesh_data
        print(f"网格数量: {len(mesh_dict)}")
        pickle.dump(mesh_dict, open(filepath, "wb"), protocol=0)
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

    from . import (
        L3D_operator,
        L3D_ext_operator,
        L3D_imp_operator,
        sector_operator,
        entity_operator,
        anim_operator,
    )

    L3D_operator.register()
    L3D_ext_operator.register()
    L3D_imp_operator.register()
    sector_operator.register()
    entity_operator.register()
    anim_operator.register()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    from . import (
        L3D_operator,
        L3D_ext_operator,
        L3D_imp_operator,
        sector_operator,
        entity_operator,
        anim_operator,
    )

    L3D_operator.unregister()
    L3D_ext_operator.unregister()
    L3D_imp_operator.unregister()
    sector_operator.unregister()
    entity_operator.unregister()
    anim_operator.unregister()
