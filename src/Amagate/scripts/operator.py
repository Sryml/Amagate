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
            return {"CANCELLED"}

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
            # ("2", "Export BOD as ...", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore

    def execute(self, context: Context):
        cb_dict = {"Batch Import BOD": self.import_bod}
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
        from . import entity_operator as OP_ENTITY

        models_path = os.path.join(data.ADDON_PATH, "Models")
        preview_dir = os.path.join(models_path, "Preview")
        manifest = json.load(
            open(os.path.join(models_path, "manifest.json"), encoding="utf-8")
        )
        ent_dir = ("3DChars", "3DObjs")[1]
        root = os.path.join(models_path, ent_dir)
        manifest_dict = manifest["Entities"]
        # key = sorted(manifest_dict.keys(), key=int)
        # if key:
        #     key = int(key[-1]) + 1
        # else:
        #     key = 1
        #
        DefaultSelectionData = {}
        exec(open(os.path.join(models_path, "EnglishUS.py")).read())

        count = 0
        # rv3d = context.region_data  # type: bpy.types.RegionView3D
        scene = context.scene  # type: Scene
        padding = 0.05
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

        for f_name in os.listdir(root):
            if not f_name.lower().endswith(".bod"):
                continue

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
            obj, lack_texture = OP_ENTITY.OT_ImportBOD.import_bod(context, filepath)

            skeleton = bpy.data.objects.get("Blade_Skeleton")
            view = "TOP"
            if skeleton:
                anchor = bpy.data.objects.get("Blade_Anchor_ViewPoint")
                if anchor:
                    if abs(anchor.matrix_world.col[1].xyz.dot(z_axis)) > 0.7:
                        view = "FRONT"
                # bone = skeleton.pose.bones.get("Center")
                # if bone:
                #     if abs(bone.matrix.col[1].xyz.dot(z_axis)) > 0.7:
                #         view = "FRONT"
            else:
                anchor = bpy.data.objects.get("Blade_Anchor_1H_R")
                if anchor and abs(anchor.matrix_world.col[2].xyz.dot(z_axis)) > 0.7:
                    view = "FRONT"

            bpy.ops.view3d.view_axis(type=view)

            #
            verts = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            min_x = min(v.x for v in verts)
            max_x = max(v.x for v in verts)
            min_z = min(v.z for v in verts)
            max_z = max(v.z for v in verts)
            min_y = min(v.y for v in verts)
            max_y = max(v.y for v in verts)

            camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
            scene.collection.objects.link(camera)
            scene.camera = camera  # 设置活动摄像机
            camera.hide_set(True)
            fov = math.degrees(camera.data.angle)  # type: ignore

            if view == "FRONT":
                width = max_x - min_x
                height = max_z - min_z
                max_dimension = max(width, height) + padding
                distance = (max_dimension / 2) / math.tan(math.radians(fov / 2))
                x = (min_x + max_x) / 2
                z = (min_z + max_z) / 2
                camera.rotation_euler = Euler((math.pi / 2, 0.0, 0.0))
                camera.location = (x, min_y - distance, z)
            else:
                width = max_x - min_x
                height = max_y - min_y
                max_dimension = max(width, height) + padding
                distance = (max_dimension / 2) / math.tan(math.radians(fov / 2))
                x = (min_x + max_x) / 2
                y = (min_y + max_y) / 2
                camera.rotation_euler = Euler((0.0, 0.0, 0.0))
                camera.location = (x, y, max_z + distance)

            #
            scene.render.filepath = "//tmp"
            context.space_data.shading.type = "MATERIAL"  # type: ignore
            save_name = f"{f_name[:-4]}.blend"
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, save_name))
            manifest_dict[obj.name] = [
                DefaultSelectionData.get(obj.name, (0, 0, obj.name))[2],
                os.path.join(ent_dir, save_name),
            ]
            # key += 1
            #

            # if lack_texture:
            #     context.space_data.shading.type = "SOLID"  # type: ignore
            # else:
            #     context.space_data.shading.type = "MATERIAL"  # type: ignore

            # 渲染
            for mat in bpy.data.materials:
                mat.use_backface_culling = False
            ag_utils.select_active(context, obj)  # type: ignore
            camera.select_set(True)
            bpy.ops.object.select_all(action="INVERT")
            bpy.ops.object.delete()

            scene.render.filepath = os.path.join(
                preview_dir, os.path.splitext(save_name)[0]
            )
            bpy.ops.render.render(write_still=True)

        #
        json.dump(
            manifest,
            open(os.path.join(models_path, "manifest.json"), "w", encoding="utf-8"),
            indent=4,
            ensure_ascii=False,
            sort_keys=True,
        )

    def test1(self, context: Context):
        from . import L3D_ext_operator as OP_L3D_EXT

        obj = context.object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        # bm = bmesh.from_edit_mesh(mesh)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        # edge = next(e for e in bm.edges if e.select)
        # bm.faces.ensure_lookup_table()
        face = next(e for e in bm.faces if e.select)
        # face = bm.faces[3]

        # bm = bmesh.new()
        # bm.from_mesh(mesh)
        # OP_L3D_EXT.hole_split(bm)

        result = bmesh.ops.bisect_plane(
            bm,
            geom=list(face.verts) + list(face.edges) + [face],  # type: ignore
            dist=1e-4,
            plane_no=Vector((0, 0, 1)),
            plane_co=Vector((0, 0, 1)),
            clear_inner=False,
            clear_outer=False,
        )
        # bm.verts.ensure_lookup_table()
        # for i in (8,9,10,11):
        #     bm.verts[i].select = True
        # bm.select_mode={"EDGE"}
        # bm.select_flush_mode()
        # bm.select_flush(True)
        # bmesh.update_edit_mesh(mesh)
        mesh_new = bpy.data.meshes.new("AG.test")
        bm.to_mesh(mesh_new)
        obj_new = bpy.data.objects.new("AG.test", mesh_new)
        bpy.context.scene.collection.objects.link(obj_new)
        bm.free()

        # cut_verts = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMVert)]
        # cut_edges = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
        # print(f"cut_edges: {[e.index for e in cut_edges]}")
        # print(f"link_faces :{len(cut_edges[0].link_faces)}")
        # bm.free()
        # face = edges[0].link_faces[0]
        # result = bmesh.ops.bisect_plane(
        #     bm,
        #     geom=list(face.verts) + list(face.edges) + [face],  # type: ignore
        #     dist=1e-4,
        #     plane_no=Vector((1, 0, 0)),
        #     plane_co=Vector((0.0, 0, 0)),
        #     clear_inner=False,
        #     clear_outer=False,
        # )
        # vert = [g for g in result["geom_cut"] if isinstance(g, bmesh.types.BMVert)]
        # print(f"edge: {[e.index for e in edge]}")
        # bmesh.update_edit_mesh(mesh)

        # 获取新生成的面
        # new_faces = [g for g in result["geom"] if isinstance(g, bmesh.types.BMFace)]
        # bm_new = bmesh.new()
        # for f in new_faces:
        #     for v in f.verts:
        #         bm_new.verts.new(v.co)
        #     bm_new.faces.new(bm_new.verts[-len(f.verts):])
        # bmesh.ops.remove_doubles(bm_new, verts=bm_new.verts, dist=0.0001)
        # mesh_new = bpy.data.meshes.new("AG.test")
        # bm_new.to_mesh(mesh_new)
        # obj_new = bpy.data.objects.new("AG.test", mesh_new)
        # bpy.context.scene.collection.objects.link(obj_new)
        # bm_new.free()

        # bpy.ops.ed.undo_push(message="test1")

    def test2(self, context: Context):
        obj = context.object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        bm = bmesh.new()
        bm.from_mesh(mesh)
        visited = set()
        for f in bm.faces:
            if f in visited:
                continue
            faces = ag_utils.get_linked_flat(f)
            visited.update(faces)
            # 使用前三个顶点定义平面
            v1, v2, v3 = faces[0].verts[0], faces[0].verts[1], faces[0].verts[2]
            plane_normal = (v2.co - v1.co).cross(v3.co - v1.co).normalized()

            # 计算平面方程 ax + by + cz + d = 0 中的d
            d = -plane_normal.dot(v1.co)

            for f in faces:
                for v in f.verts:
                    # 计算点到平面的距离
                    distance = abs(plane_normal.dot(v.co) + d)
                    if distance > 1e-5:
                        return True
        # layer = bm.faces.layers.int.get("amagate_connected")
        # faces = [f for f in bm.faces if f[layer] == 0]  # type: ignore
        # bmesh.ops.connect_verts_concave(bm, faces=faces)
        # #
        # bm_mesh = bpy.data.meshes.new(f"AG.split")
        # bm.to_mesh(bm_mesh)
        # bm_obj = bpy.data.objects.new(f"AG.split", bm_mesh)
        # data.link2coll(bm_obj, bpy.context.scene.collection)
        #

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
        nodes_data = pickle.load(open(filepath, "rb"))
        # nodes_data = {}
        # 材质节点
        for name in ("AG.Mat1", "AG.Mat-1", "AG.Cubemap"):
            mat = bpy.data.materials.get(name)
            if mat:
                nodes_data[name] = data.export_nodes(mat)
        # 几何节点
        for name in ("Amagate Eval", "AG.FrustumCulling", "AG.SectorNodes"):
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
            if mat.name.startswith("EXPORT."):
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
    )

    L3D_operator.register()
    L3D_ext_operator.register()
    L3D_imp_operator.register()
    sector_operator.register()
    entity_operator.register()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    from . import (
        L3D_operator,
        L3D_ext_operator,
        L3D_imp_operator,
        sector_operator,
        entity_operator,
    )

    L3D_operator.unregister()
    L3D_ext_operator.unregister()
    L3D_imp_operator.unregister()
    sector_operator.unregister()
    entity_operator.unregister()
