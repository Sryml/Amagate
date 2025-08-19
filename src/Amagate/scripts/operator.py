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

from . import data, entity_data
from . import ag_utils


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
############################ 动画/摄像机
############################


# 导出动画
class OT_ExportAnim(bpy.types.Operator):
    bl_idname = "amagate.export_anim"
    bl_label = "Export Animation"
    bl_description = "Export Animation"
    bl_options = {"INTERNAL"}

    main: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    action: EnumProperty(
        items=[
            ("0", "Export Animation as ...", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore
    filter_glob: StringProperty(default="*.bmv", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        armature_obj = context.active_object
        return (
            armature_obj
            and armature_obj.visible_get()
            and armature_obj.type == "ARMATURE"
            and armature_obj.library is None
        )

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        self.filepath = bpy.path.ensure_ext(self.filepath, ".bmv")
        action_name = Path(self.filepath).stem
        if action_name == "":
            self.report({"ERROR"}, "Invalid filename")
            return {"FINISHED"}

        armature_obj = context.active_object  # type: Object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        action = armature_obj.animation_data.action
        # has_slot = hasattr(action, "slots")
        channelbag = self.channelbag
        # 目标坐标系
        target_space_inv = Quaternion((1, 0, 0), -math.pi / 2).inverted()  # type: ignore
        buffer = BytesIO()
        # 内部名称
        inter_name = action_name.encode("utf-8")
        buffer.write(struct.pack("I", len(inter_name)))
        buffer.write(inter_name)
        # 骨骼数量
        count = len(armature.bones)
        buffer.write(struct.pack("I", count))
        # 帧长度
        frame_len = max(*(int(fc.range()[1]) for fc in channelbag.fcurves), 1)
        # 所有骨骼的旋转姿态
        for bone_idx in range(count):
            bone = armature.bones[bone_idx]
            bone_name = bone.name
            bone_quat = bone.matrix_local.to_quaternion()
            parent_bone = bone.parent
            data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
            fcurves = [
                item
                for i in range(4)
                if (item := channelbag.fcurves.find(data_path, index=i)) is not None
            ]

            #
            buffer.write(struct.pack("I", frame_len))
            fcurves_len = len(fcurves)
            for frame in range(1, frame_len + 1):
                if fcurves_len != 4:
                    quat = Quaternion()
                else:
                    quat = Quaternion(fcurves[i].evaluate(frame) for i in range(4))
                quat_glob = bone_quat @ quat
                if parent_bone:
                    parent_quat = armature.bones[parent_bone.name].matrix_local.to_quaternion().inverted()  # type: ignore
                # 根骨骼的旋转数据是全局的
                else:
                    parent_quat = target_space_inv
                # 相对于父旋转
                quat_rel = (parent_quat @ quat_glob).normalized()
                buffer.write(struct.pack("ffff", *quat_rel))

        # 根骨骼位置姿态
        bone = armature.bones[0]
        matrix = bone.matrix_local.copy()
        location = bone.matrix_local.translation
        data_path = f'pose.bones["{bone.name}"].location'
        fcurves = [
            item
            for i in range(3)
            if (item := channelbag.fcurves.find(data_path, index=i)) is not None
        ]

        #
        buffer.write(struct.pack("I", frame_len))
        fcurves_len = len(fcurves)
        for frame in range(1, frame_len + 1):
            if fcurves_len != 3:
                co = Vector()
            else:
                co = Vector(fcurves[i].evaluate(frame) for i in range(3))
            co_glob = matrix @ co
            co_local = target_space_inv @ (co_glob - location)
            co_local *= 1000
            buffer.write(struct.pack("ddd", *co_local))
        #
        with open(self.filepath, "wb") as f:
            f.write(buffer.getvalue())
        buffer.close()

        self.report(
            {"INFO"},
            f"{pgettext('Export successfully')}: {os.path.basename(self.filepath)}",
        )
        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        scene_data = context.scene.amagate_data
        armature_obj = context.active_object  # type: Object
        if not armature_obj:
            self.report({"WARNING"}, "Please select armature object first")
            return {"CANCELLED"}

        #
        if not armature_obj.animation_data:
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}
        action = armature_obj.animation_data.action
        if not action:
            self.report(
                {"WARNING"}, "Please select the action to export in the Action Editor"
            )
            return {"CANCELLED"}
        action_name = action.name
        channelbag = action  # type: bpy.types.Action
        has_slot = hasattr(armature_obj.animation_data, "action_slot")
        if has_slot:
            slot = armature_obj.animation_data.action_slot
            if not slot:
                self.report(
                    {"WARNING"},
                    "Please select the action slot to export in the Action Editor",
                )
                return {"CANCELLED"}
            action_name = slot.name_display
            channelbag = next((c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == slot), None)  # type: ignore
        if not channelbag or len(channelbag.fcurves) == 0:
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}

        self.channelbag = channelbag

        if not bpy.data.filepath or (not self.main and self.action == "0"):
            if not self.filepath:
                self.filepath = f"{action_name}.bmv"
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = str(Path(bpy.data.filepath).parent / f"{action_name}.bmv")
            return self.execute(context)


# 导入动画
class OT_ImportAnim(bpy.types.Operator):
    bl_idname = "amagate.import_anim"
    bl_label = "Import Animation"
    bl_description = "Import Animation"
    bl_options = {"INTERNAL"}

    # x_axis_correction: FloatProperty(name="X-Axis Correction", default=-math.pi / 2, subtype="ANGLE", step=100) # type: ignore

    filter_glob: StringProperty(default="*.bmv", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    # def draw(self, context: Context):
    #     layout = self.layout
    #     layout.prop(self, "x_axis_correction")

    @classmethod
    def poll(cls, context: Context):
        armature_obj = context.active_object
        return (
            armature_obj
            and armature_obj.visible_get()
            and armature_obj.type == "ARMATURE"
            and armature_obj.library is None
        )

    def execute(self, context: Context):
        directory = Path(self.directory)
        if len(self.files) == 1 and self.files[0].name == "":
            paths = [
                f
                for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() == ".bmv"
            ]
        else:
            paths = [
                f
                for i in self.files
                if (f := directory / i.name).is_file() and f.suffix.lower() == ".bmv"
            ]
        if len(paths) == 0:
            self.report({"INFO"}, "No valid files selected")
            return {"FINISHED"}
        #
        self.execute2(context, paths)

        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        scene_data = context.scene.amagate_data
        armature_obj = context.active_object  # type: Object
        if not armature_obj:
            self.report({"WARNING"}, "Please select armature object first")
            return {"CANCELLED"}
        if not armature_obj.visible_get():
            self.report({"WARNING"}, "Armature object is not visible")
            return {"CANCELLED"}

        # 设为上次选择目录，文件名为空
        if not self.filepath:
            self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute2(self, context: Context, paths):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        scene = context.scene
        scene_data = context.scene.amagate_data
        armature_obj = context.active_object  # type: Object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        pose_bones = armature_obj.pose.bones
        data_bones = armature.bones
        ag_utils.select_active(context, armature_obj)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")

        bone_count = len(pose_bones)
        pose_bone_first = pose_bones[0]
        bone_first = data_bones[0]

        # 目标坐标系
        target_space_q = Quaternion((1, 0, 0), -math.pi / 2)  # type: ignore
        fail_list = []

        for filepath in paths:
            # if not (filepath.is_file() and filepath.suffix.lower() == ".bmv"):
            #     continue
            filename = filepath.name
            logger.debug(filename)
            action_name = filename[:-4]
            with open(filepath, "rb") as f:
                # 内部名称
                length = unpack("I", f)[0]
                inter_name = unpack(f"{length}s", f)
                # 骨骼数量
                count = unpack("I", f)[0]
                max_skip = count - bone_count
                skip_num = 0
                if count != bone_count:
                    fail_list.append(f"{filename} - {count}")
                    continue
                # 创建动作
                action = bpy.data.actions.get(action_name)
                if not action:
                    action = bpy.data.actions.new(name=action_name)
                channelbag = action  # type: bpy.types.Action
                action.use_fake_user = True
                has_slot = hasattr(action, "slots")
                # 分配动作
                if not armature_obj.animation_data:
                    armature_obj.animation_data_create()
                armature_obj.animation_data.action = action
                #
                if has_slot:
                    slot = next(
                        (i for i in action.slots if i.name_display == action_name), None
                    )
                    if not slot:
                        slot = action.slots.new("OBJECT", action_name)  # type: ignore
                    armature_obj.animation_data.action_slot = slot
                    # 初始化层和轨道
                    pose_bone_first.keyframe_insert(
                        "location", frame=1, group=pose_bone_first.name
                    )

                    channelbag = next(c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == slot)  # type: ignore
                channelbag.fcurves.clear()
                for i in channelbag.groups:
                    channelbag.groups.remove(i)
                # 清空姿态变换
                bpy.ops.pose.transforms_clear()
                # 创建通道并清除帧
                for bone_idx in range(bone_count):
                    bone = pose_bones[bone_idx]
                    bone_name = bone.name
                    bone.keyframe_insert(
                        "rotation_quaternion", frame=1, group=bone_name
                    )
                    if bone_idx == 0:
                        loc_data_path = f'pose.bones["{bone_name}"].location'
                        bone.keyframe_insert("location", frame=1, group=bone_name)
                for fc in channelbag.fcurves:
                    fc.keyframe_points.clear()

                # start_time = time.time()
                for bone_idx in range(bone_count):
                    bone = pose_bones[bone_idx]
                    # bone_quat_base = bone.matrix.to_quaternion().normalized()
                    #
                    parent_bone = bone.parent
                    bone_name = bone.name
                    # for i in range(4):
                    #     channelbag.fcurves.new(
                    #         rot_data_path, index=i, action_group=bone_name
                    #     )
                    # if bone_idx == 0:
                    # for i in range(3):
                    #     channelbag.fcurves.new(
                    #         loc_data_path, index=i, action_group=bone_name
                    #     )
                    #
                    frame_len = unpack("I", f)[0]
                    if scene.frame_end < frame_len:
                        scene.frame_end = frame_len
                    for frame in range(1, frame_len + 1):
                        quat = Quaternion(unpack("ffff", f))
                        # if frame == 1:
                        #     print(quat.to_euler())
                        # 子骨骼的旋转数据是相对于父骨骼的
                        if parent_bone:
                            parent_quat = data_bones[
                                parent_bone.name
                            ].matrix_local.to_quaternion()
                            # parent_quat = parent_bone.matrix.to_quaternion()
                        # 根骨骼的旋转数据是全局的
                        else:
                            # q = data_bones[bone.name].matrix_local.to_quaternion()
                            parent_quat = target_space_q

                        loc, rot, scale = bone.matrix.decompose()
                        rot = (parent_quat @ quat).normalized()
                        matrix = Matrix.LocRotScale(loc, rot, scale)
                        # 检查旋转是否太大
                        # if frame == 1 and skip_num < max_skip:
                        #     diff = math.acos(bone.matrix.to_quaternion().dot(matrix.to_quaternion())) * 2
                        #     if math.degrees(diff) > 120:
                        #         skip_num += 1
                        #         f.seek((frame_len - 1) * 16, 1)
                        #         break

                        bone.matrix = matrix
                        bone.keyframe_insert(
                            "rotation_quaternion", frame=frame, group=bone_name
                        )
                # 根骨骼位置姿态
                bone = data_bones[0]
                matrix = bone.matrix_local.inverted()  # type: Matrix
                location = bone.matrix_local.translation
                frame_len = unpack("I", f)[0]
                for frame in range(1, frame_len + 1):
                    co = Vector(unpack("ddd", f)) / 1000
                    # 添加骨骼偏移
                    co_glob = (target_space_q @ co) + location
                    co_local = matrix @ co_glob
                    #
                    for idx in range(3):
                        channelbag.fcurves.find(
                            loc_data_path, index=idx
                        ).keyframe_points.insert(frame, co_local[idx])
                #
                # end = f.read()
                # logger.debug(len(end))
        #
        # print(time.time() - start_time)
        #
        scene.frame_current = 1
        bpy.ops.object.mode_set(mode="OBJECT")
        has_area = next(
            (True for area in bpy.context.screen.areas if area.ui_type == "DOPESHEET"),
            False,
        )
        if not has_area:
            for area in bpy.context.screen.areas:
                if area.ui_type == "TIMELINE":
                    area.ui_type = "DOPESHEET"
                    area.spaces[0].ui_mode = "ACTION"  # type: ignore
                    break
        #
        if fail_list:
            self.report(
                {"WARNING"},
                f"{pgettext('Inconsistent number of bones')}:\n{', '.join(fail_list)}",
            )


# 镜像动画
class OT_MirrorAnim(bpy.types.Operator):
    bl_idname = "amagate.mirror_anim"
    bl_label = "Mirror Animation"
    bl_description = "Mirror Animation"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        armature_obj = context.active_object
        return (
            armature_obj
            and armature_obj.visible_get()
            and armature_obj.type == "ARMATURE"
            and armature_obj.library is None
        )

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        armature_obj = context.active_object  # type: Object
        if not armature_obj:
            self.report({"WARNING"}, "Please select armature object first")
            return {"CANCELLED"}
        if not armature_obj.visible_get():
            self.report({"WARNING"}, "Armature object is not visible")
            return {"CANCELLED"}
        #
        if not armature_obj.animation_data:
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}
        action = armature_obj.animation_data.action
        if not action:
            self.report(
                {"WARNING"}, "Please select the action to export in the Action Editor"
            )
            return {"CANCELLED"}
        action_name = action.name
        channelbag = action  # type: bpy.types.Action
        has_slot = hasattr(armature_obj.animation_data, "action_slot")
        if has_slot:
            slot = armature_obj.animation_data.action_slot
            if not slot:
                self.report(
                    {"WARNING"},
                    "Please select the action slot to export in the Action Editor",
                )
                return {"CANCELLED"}
            action_name = slot.name_display
            channelbag = next((c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == slot), None)  # type: ignore
        if not channelbag or len(channelbag.fcurves) == 0:
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}
        #
        self.channelbag = channelbag
        self.execute2(context)
        return {"FINISHED"}

    def execute2(self, context: Context):
        scene = context.scene
        scene_data = context.scene.amagate_data
        armature_obj = context.active_object  # type: Object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        ag_utils.select_active(context, armature_obj)
        # bpy.ops.object.mode_set(mode="POSE")
        # bpy.ops.pose.select_all(action="SELECT")

        action = armature_obj.animation_data.action
        # has_slot = hasattr(armature_obj.animation_data, "action_slot")
        channelbag = self.channelbag
        # 帧长度
        frame_len = max(int(fc.range()[1]) for fc in channelbag.fcurves)

        # 对称骨骼名称字典
        sym_names = {}
        for bone in armature.bones:
            name = bone.name.lower()
            if name.startswith("l_"):
                find_name = f"r_{name[2:]}"
                sym_name = next(
                    (b.name for b in armature.bones if b.name.lower() == find_name),
                    None,
                )
                if sym_name:
                    sym_names[bone.name] = sym_name
                    sym_names[sym_name] = bone.name

        cursor = scene.cursor
        # 复制骨架
        bpy.ops.object.duplicate()
        armature_child = context.active_object
        armature_child.rename("armature_child")
        bpy.ops.object.duplicate()
        armature_mirror = context.active_object
        armature_mirror.rename("armature_mirror")
        # 设置镜像骨架
        scene.frame_set(frame_len + 1)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.transforms_clear()
        # bpy.ops.anim.keyframe_insert_by_name(type="BUILTIN_KSI_LocRot")
        prev_cursor = cursor.location.copy()
        cursor.location = armature.bones[0].matrix_local.translation
        bpy.ops.object.mode_set(mode="OBJECT")
        prev_loc = armature_mirror.location.copy()
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        bpy.ops.transform.mirror(
            orient_type="GLOBAL", constraint_axis=(True, False, False)
        )
        cursor.location = prev_loc
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        cursor.location = prev_cursor
        # 设置镜像骨架的正常子骨架
        bpy.data.actions.remove(armature_child.animation_data.action)  # type: ignore
        # armature_child.animation_data.action = None
        ag_utils.select_active(context, armature_child)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.transforms_clear()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.armature.select_all(action="SELECT")
        bpy.ops.armature.parent_clear(type="CLEAR")
        # 设置父级
        bpy.ops.object.mode_set(mode="POSE")
        for bone in armature_child.pose.bones:
            constraint = bone.constraints.new(type="CHILD_OF")
            constraint.target = armature_mirror  # type: ignore
            sym_name = sym_names.get(bone.name)
            if not sym_name:
                sym_name = bone.name
            constraint.subtarget = sym_name  # type: ignore
            # bpy.ops.constraint.childof_set_inverse()
        bpy.ops.object.mode_set(mode="OBJECT")

        bones_num = len(armature.bones)
        # 曲线字典
        fcurves_dict = {}  # type: dict[str, list[bpy.types.FCurve]]
        fcurves_loc = []  # type: list[bpy.types.FCurve]
        for bone_idx in range(bones_num):
            bone = armature.bones[bone_idx]
            bone_name = bone.name
            fcurves = []
            data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
            for i in range(4):
                fc = channelbag.fcurves.find(data_path, index=i)
                if fc is None:
                    fc = channelbag.fcurves.new(data_path, index=i)
                else:
                    fc.keyframe_points.clear()
                fcurves.append(fc)
            fcurves_dict[bone_name] = fcurves
            #
            if bone_idx == 0:
                data_path = f'pose.bones["{bone_name}"].location'
                for i in range(3):
                    fc = channelbag.fcurves.find(data_path, index=i)
                    if fc is None:
                        fc = channelbag.fcurves.new(data_path, index=i)
                    else:
                        fc.keyframe_points.clear()
                    fcurves_loc.append(fc)

        # 烘焙动作
        ag_utils.select_active(context, armature_obj)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.transforms_clear()
        matrix_root = armature.bones[0].matrix_local.copy()
        matrix_root_inv = matrix_root.inverted()
        for frame in range(1, frame_len + 1):
            scene.frame_set(frame)
            glob_rot_lst = {
                b.name: b.matrix.to_quaternion() for b in armature_obj.pose.bones
            }
            for bone_idx in range(bones_num):
                bone = armature_obj.pose.bones[bone_idx]
                bone_name = bone.name
                fcurves = fcurves_dict[bone_name]
                # 参考骨骼
                bone_ref = armature_child.pose.bones[bone_name]
                quat_curr = glob_rot_lst[bone_name]
                quat_curr_inv = quat_curr.inverted()
                quat_pose = bone_ref.matrix.to_quaternion()
                quat_glob = quat_pose @ quat_curr_inv

                quat = quat_curr_inv @ quat_glob @ quat_curr  # 世界转局部
                quat2 = (bone.rotation_quaternion @ quat).normalized()

                for idx in range(4):
                    fcurves[idx].keyframe_points.insert(frame, quat2[idx])
                if bone_idx == 0:
                    loc_pose = bone_ref.matrix.to_translation()
                    loc = matrix_root_inv @ loc_pose
                    for idx in range(3):
                        fcurves_loc[idx].keyframe_points.insert(frame, loc[idx])
                #
                glob_rot_lst[bone_name] = quat_pose
                for b in bone.children_recursive:
                    glob_rot_lst[b.name] = (
                        quat_glob @ glob_rot_lst[b.name]
                    ).normalized()

                # loc, rot, scale = bone.matrix.decompose()
                # rot = bone_ref.matrix.to_quaternion()
                # bone.matrix = Matrix.LocRotScale(loc, rot, scale)
                # bone.keyframe_insert(
                #     "rotation_quaternion", frame=frame, group=bone_name
                # )

        # 清理
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.actions.remove(armature_mirror.animation_data.action)  # type: ignore
        bpy.data.armatures.remove(armature_child.data)  # type: ignore
        bpy.data.armatures.remove(armature_mirror.data)  # type: ignore


# 设置动画
class OT_SetAnim(bpy.types.Operator):
    bl_idname = "amagate.set_anim"
    bl_label = "Set Animation"
    bl_description = "Set Animation"
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    enum: EnumProperty(
        items=entity_data.get_anm_enum_search,
    )  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        armature_obj = context.view_layer.objects.active
        return (
            armature_obj
            and armature_obj.type == "ARMATURE"
            and armature_obj.library is None
        )

    def execute(self, context: Context):
        action_name = bpy.types.UILayout.enum_item_name(self, "enum", self.enum)
        filename = bpy.types.UILayout.enum_item_description(self, "enum", self.enum)
        armature = context.view_layer.objects.active
        armature_data = armature.data  # type: bpy.types.Armature # type: ignore
        action = bpy.data.actions.get(action_name)  # type: ignore
        if not action:
            filepath = os.path.join(data.ADDON_PATH, "Models", "Anm", filename)
            if not os.path.exists(filepath):
                self.report({"ERROR"}, f"{pgettext('File not found')}: {filename}")
                return {"CANCELLED"}

            with bpy.data.libraries.load(filepath, link=True) as (data_from, data_to):
                action_from = next(
                    (i for i in data_from.actions if i == action_name), None
                )
                if not action_from:
                    self.report(
                        {"ERROR"}, f"Action {action_name} not found in {filename}"
                    )
                    return {"CANCELLED"}
                data_to.actions = [action_from]
            action = data_to.actions[0]  # type: bpy.types.Action
            action.use_fake_user = True
            action.library["AG.Library"] = True
        # 分配动作
        has_slot = hasattr(action, "slots")
        if not armature.animation_data:
            armature.animation_data_create()
        armature.animation_data.action = action
        if has_slot:
            slot = action.slots[0] if len(action.slots) != 0 else None
            if slot:
                armature.animation_data.action_slot = slot

        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        context.window_manager.invoke_search_popup(self)
        return {"FINISHED"}


############################
# 摄像机导出
class OT_ExportCamera(bpy.types.Operator):
    bl_idname = "amagate.export_camera"
    bl_label = "Export Camera"
    bl_description = "Export Camera"
    bl_options = {"INTERNAL"}

    main: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    action: EnumProperty(
        items=[
            ("0", "Export Camera as ...", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore
    filter_glob: StringProperty(default="*.cam", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        scene = context.scene
        return scene.camera

    def execute(self, context: Context):
        scene = context.scene
        scene_data = scene.amagate_data
        self.filepath = bpy.path.ensure_ext(self.filepath, ".cam")
        action_name = Path(self.filepath).stem
        if action_name == "":
            self.report({"ERROR"}, "Invalid filename")
            return {"FINISHED"}

        camera_obj = scene.camera
        camera = camera_obj.data  # type: bpy.types.Camera # type: ignore
        #
        channelbag = self.channelbag
        channelbag_data = self.channelbag_data
        buffer = BytesIO()
        # 曲线
        fcurves_loc = [
            channelbag.fcurves.find("location", index=i) for i in range(3)
        ]  # type: list[bpy.types.FCurve]
        fcurves_rot = [
            channelbag.fcurves.find("rotation_euler", index=i) for i in range(3)
        ]  # type: list[bpy.types.FCurve]
        fcurve_fov = (
            channelbag_data.fcurves.find("lens", index=0) if channelbag_data else None
        )

        sensor_factor = camera.sensor_width / 36  # 传感器缩放
        lens_init = camera.lens
        frame_start = 1

        # 帧长度
        frame_len = max(*(int(fc.range()[1]) for fc in channelbag.fcurves), 1)
        frame_len = int((frame_len - frame_start) * 3)
        logger.debug(f"frame_len: {frame_len}")

        # 动画时间放大3倍
        for fc in channelbag.fcurves:
            for kp in fc.keyframe_points:
                if kp.co[0] < 1:
                    continue
                kp.co[0] = (kp.co[0] - 1) * 3 + 1
        if fcurve_fov:
            for kp in fcurve_fov.keyframe_points:
                if kp.co[0] < 1:
                    continue
                kp.co[0] = (kp.co[0] - 1) * 3 + 1

        buffer.write(struct.pack("I", frame_len))
        buffer.write(bytes((0, 0, 64, 64)))
        for frame in range(frame_start, frame_len + frame_start + 1):
            rot = Euler(
                [fc.evaluate(frame) if fc else 0 for fc in fcurves_rot]
            ).to_quaternion()
            axis, angle = rot.to_axis_angle()
            axis = -axis.x, axis.z, -axis.y

            loc = Vector([fc.evaluate(frame) if fc else 0 for fc in fcurves_loc]) * 1000
            loc.yz = -loc.z, loc.y

            lens = fcurve_fov.evaluate(frame) if fcurve_fov else lens_init
            lens = lens / sensor_factor * 0.037
            # fov = 2 * math.atan(sensor_width / (lens * 2))
            # fov /= fov_factor
            #
            buffer.write(struct.pack("fff", *axis))
            buffer.write(struct.pack("f", angle))
            buffer.write(struct.pack("fff", *loc))
            buffer.write(struct.pack("f", lens))
        #
        with open(self.filepath, "wb") as f:
            f.write(buffer.getvalue())
        buffer.close()
        # 清理
        action = camera_obj.animation_data.action
        has_slot = hasattr(camera_obj.animation_data, "action_slot")
        if has_slot:
            action.slots.remove(self.action_dup)  # type: ignore
        else:
            bpy.data.actions.remove(self.action_dup)  # type: ignore

        if self.action_data_dup:
            if has_slot:
                action_data = camera.animation_data.action
                action_data.slots.remove(self.action_data_dup)  # type: ignore
            else:
                bpy.data.actions.remove(self.action_data_dup)  # type: ignore

        self.report(
            {"INFO"},
            f"{pgettext('Export successfully')}: {os.path.basename(self.filepath)}",
        )

        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        scene = context.scene
        scene_data = scene.amagate_data
        camera_obj = scene.camera
        camera = camera_obj.data  # type: bpy.types.Camera # type: ignore
        #
        if not camera_obj.animation_data:
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}
        action = camera_obj.animation_data.action
        if not action:
            self.report(
                {"WARNING"}, "Please select the action to export in the Action Editor"
            )
            return {"CANCELLED"}
        action_name = action.name
        channelbag = action
        has_slot = hasattr(camera_obj.animation_data, "action_slot")
        if has_slot:
            slot = camera_obj.animation_data.action_slot
            if not slot:
                self.report(
                    {"WARNING"},
                    "Please select the action slot to export in the Action Editor",
                )
                return {"CANCELLED"}
            channelbag = next((c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == slot), None)  # type: ignore
        if not channelbag or len(channelbag.fcurves) == 0:
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}

        # 创建动作副本
        if has_slot:
            action_dup = slot.duplicate()  # type: ignore
            channelbag = next(c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == action_dup)  # type: ignore
        else:
            action_dup = action.copy()
            channelbag = action_dup  # type: bpy.types.Action

        # 获取焦距动画
        action_data_dup = None  # type: bpy.types.Action # type: ignore
        channelbag_data = None  # type: bpy.types.Action # type: ignore
        if camera.animation_data and (action_data := camera.animation_data.action):
            if has_slot:
                slot = camera.animation_data.action_slot
                if slot:
                    channelbag_data = next((c for l in action_data.layers for s in l.strips for c in s.channelbags if c.slot == slot), None)  # type: ignore
                    if channelbag_data:
                        action_data_dup = slot.duplicate()  # type: ignore
                        channelbag_data = next(c for l in action_data.layers for s in l.strips for c in s.channelbags if c.slot == action_data_dup)  # type: ignore
            else:
                action_data_dup = action_data.copy()
                channelbag_data = action_data_dup
        #
        self.action_dup = action_dup
        self.action_data_dup = action_data_dup
        self.channelbag = channelbag
        self.channelbag_data = channelbag_data

        if not bpy.data.filepath or (not self.main and self.action == "0"):
            if not self.filepath:
                self.filepath = f"{action_name}.cam"
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = str(Path(bpy.data.filepath).parent / f"{action_name}.cam")
            return self.execute(context)


# 摄像机导入
class OT_ImportCamera(bpy.types.Operator):
    bl_idname = "amagate.import_camera"
    bl_label = "Import Camera"
    bl_description = "Import Camera"
    bl_options = {"INTERNAL"}

    filter_glob: StringProperty(default="*.cam", options={"HIDDEN"})  # type: ignore
    directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    # files: CollectionProperty(type=bpy.types.OperatorFileListElement)  # type: ignore

    @classmethod
    def poll(cls, context: Context):
        scene = context.scene
        return scene.camera

    def execute(self, context: Context):
        scene = context.scene
        scene_data = scene.amagate_data
        camera_obj = scene.camera
        camera = camera_obj.data  # type: bpy.types.Camera # type: ignore
        filepath = Path(self.filepath)
        if not (filepath.is_file() and filepath.suffix.lower() == ".cam"):
            self.report({"ERROR"}, f"{pgettext('Invalid file')}: {filepath.name}")
            return {"FINISHED"}
        # 目标坐标系
        # target_space_q = Quaternion((1, 0, 0), -math.pi / 2)  # type: ignore
        action_name = filepath.stem
        # 创建动作
        action = bpy.data.actions.get(action_name)
        if not action:
            action = bpy.data.actions.new(name=action_name)
        channelbag = action  # type: bpy.types.Action
        action.use_fake_user = True

        action_name_data = f"{action_name}.fov"
        action_data = bpy.data.actions.get(action_name_data)
        if not action_data:
            action_data = bpy.data.actions.new(name=action_name_data)
        channelbag_data = action_data  # type: bpy.types.Action
        action_data.use_fake_user = True

        has_slot = hasattr(action, "slots")
        # 分配动作
        if not camera_obj.animation_data:
            camera_obj.animation_data_create()
        if not camera.animation_data:
            camera.animation_data_create()
        camera_obj.animation_data.action = action
        camera.animation_data.action = action_data
        # 初始化层和轨道
        camera_obj.keyframe_insert("location")
        camera.keyframe_insert("lens")
        if has_slot:
            slot = camera_obj.animation_data.action_slot
            channelbag = next(c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == slot)  # type: ignore

            slot = camera.animation_data.action_slot
            channelbag_data = next(c for l in action_data.layers for s in l.strips for c in s.channelbags if c.slot == slot)  # type: ignore

        channelbag.fcurves.clear()
        channelbag_data.fcurves.clear()
        for i in channelbag.groups:
            channelbag.groups.remove(i)
        for i in channelbag_data.groups:
            channelbag_data.groups.remove(i)
        # 创建通道
        fcurves_loc = []  # type: list[bpy.types.FCurve]
        fcurves_rot = []  # type: list[bpy.types.FCurve]
        for i in range(3):
            fc = channelbag.fcurves.new("location", index=i)
            fcurves_loc.append(fc)
        for i in range(3):
            fc = channelbag.fcurves.new("rotation_euler", index=i)
            fcurves_rot.append(fc)
        fcurve_fov = channelbag_data.fcurves.new("lens", index=0)

        sensor_factor = camera.sensor_width / 36  # 传感器缩放
        camera_obj.rotation_mode = "XYZ"
        frame_start = 1

        with open(filepath, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size
            frame_len = int(unpack("I", f)[0] / 3 + frame_start)
            if scene.frame_end < frame_len:
                scene.frame_end = frame_len
            # 固定4字节 0 0 64 64
            mark = unpack("bbbb", f)
            # print(mark)
            for frame in range(frame_start, frame_len + 1):
                if f.tell() >= file_size:
                    logger.warning("End of file")
                    break
                # 轴角
                axis = unpack("fff", f)
                axis = -axis[0], -axis[2], axis[1]
                angle = unpack("f", f)[0]
                # 位置与fov
                location = Vector(unpack("fff", f)) / 1000
                location.yz = location.z, -location.y
                lens = unpack("f", f)[0] / 0.037 * sensor_factor
                #
                rot = (Quaternion(axis, angle)).to_euler()  # type: ignore
                for i in range(3):
                    fcurves_loc[i].keyframe_points.insert(frame, location[i])
                    fcurves_rot[i].keyframe_points.insert(frame, rot[i])
                # lens = sensor_width / (2 * math.tan(fov / 2))
                fcurve_fov.keyframe_points.insert(frame, lens)
                # 跳过缩放的2帧
                f.seek(64, 1)

        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        # 设为上次选择目录，文件名为空
        if not self.filepath:
            self.filepath = self.directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# 重置横滚角
class OT_ResetRoll(bpy.types.Operator):
    bl_idname = "amagate.reset_roll"
    bl_label = "Reset Roll"
    bl_description = "Reset Roll"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context: Context):
        scene = context.scene
        return scene.camera

    def execute(self, context: Context):
        camera = context.scene.camera
        current_forward = -camera.matrix_world.col[2].xyz  # type: Vector
        new_quat = current_forward.to_track_quat("-Z", "Y")
        camera.rotation_euler = new_quat.to_euler()

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
            ("3", "test1", ""),
            ("4", "test2", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore

    def execute(self, context: Context):
        cb_dict = {
            "Batch Import BOD": self.import_bod,
            "Batch Import BMV": self.import_bmv,
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
        from . import entity_operator as OP_ENTITY

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

        save_version = context.preferences.filepaths.save_version
        context.preferences.filepaths.save_version = 0
        lack_texture_lst = []
        dup_face_lst = []
        name_lst = []
        print(len(name_lst))
        # for f_name in os.listdir(root):
        #     if not f_name.lower().endswith(".bod"):
        #         continue
        for i in name_lst:
            f_name = i + ".bod"
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
            entity, lack_texture, dup_face = OP_ENTITY.OT_ImportBOD.import_bod(
                context, filepath
            )
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

        context.preferences.filepaths.save_version = save_version
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
        OT_ImportAnim.execute2(self, context, paths)  # type: ignore
        print(len(paths))
        for f in paths:
            os.remove(f)

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
        for dir in ("3DObjs", "3DChars"):
            root = models_path / dir
            for f_name in os.listdir(root):
                if f_name.lower().endswith(".blend"):
                    count += 1
                    filepath = root / f_name
                    changed = False
                    with contextlib.redirect_stdout(StringIO()):
                        bpy.ops.wm.open_mainfile(filepath=str(filepath))
                    for obj in bpy.data.objects:
                        if obj.name.lower().startswith("blade_anchor_"):
                            if obj.scale != scalc_init:
                                obj.scale = (1, 1, 1)
                                changed = True
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
                    # for img in bpy.data.images:
                    #     if img.name != "Render Result":
                    #         if not img.filepath.startswith("//textures"):
                    #             name_lst.append(f"{dir}/{f_name}")
                    #             break
                    if changed:
                        bpy.ops.wm.save_mainfile()
                        change_count += 1
        print(count, change_count)

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
        for filepath in root.iterdir():
            with contextlib.redirect_stdout(StringIO()):
                bpy.ops.wm.open_mainfile(filepath=str(filepath))
            anm_lst = [i.name for i in bpy.data.actions]
            count += len(anm_lst)
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
