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
from datetime import datetime
from pathlib import Path
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

############################
############################ 动画/摄像机
############################


# 切换到IK
class OT_SwitchToIK(bpy.types.Operator):
    bl_idname = "amagate.switch_to_ik"
    bl_label = "Switch to IK"
    bl_description = "Switch to IK"
    bl_options = {"INTERNAL", "UNDO"}

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
        armature_obj = context.active_object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        try:
            if armature_obj.animation_data.action.library:
                armature_obj.animation_data.action.make_local()
        except:
            pass
        if armature_obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        IK_BONES = {
            "R_Forearm_IKC": armature_obj.pose.bones.get("R_Forearm_IKC"),
            "L_Forearm_IKC": armature_obj.pose.bones.get("L_Forearm_IKC"),
            "R_Boot_IKC": armature_obj.pose.bones.get("R_Boot_IKC"),
            "L_Boot_IKC": armature_obj.pose.bones.get("L_Boot_IKC"),
            "R_Forearm_IKT": armature_obj.pose.bones.get("R_Forearm_IKT"),
            "L_Forearm_IKT": armature_obj.pose.bones.get("L_Forearm_IKT"),
            "R_Boot_IKT": armature_obj.pose.bones.get("R_Boot_IKT"),
            "L_Boot_IKT": armature_obj.pose.bones.get("L_Boot_IKT"),
        }  # type: dict[str, bpy.types.PoseBone] # type: ignore
        update_key = []
        ik_bones_coll = armature.collections.get("IK_Bones")
        if not ik_bones_coll:
            ik_bones_coll = armature.collections.new("IK_Bones")
        ik_bones_coll.is_visible = True
        # 确保IK骨骼存在
        bpy.ops.object.mode_set(mode="EDIT")
        if not all(IK_BONES.values()):
            #
            for k, v in IK_BONES.items():
                if not v:
                    update_key.append(k)
                    bone = armature.edit_bones.new(k)
                    bone.length = 0.3
                    ik_bones_coll.assign(bone)
        bpy.ops.armature.select_all(action="DESELECT")
        for k in IK_BONES.keys():
            bone = armature.edit_bones.get(k)  # type: bpy.types.EditBone # type: ignore
            bone.select = True

        bpy.ops.object.mode_set(mode="POSE")
        for k in update_key:
            IK_BONES[k] = armature_obj.pose.bones.get(k)  # type: ignore
            IK_BONES[k].color.palette = "THEME14"
        # root_bone = armature_obj.pose.bones[0]
        # 调整IK骨骼位置
        for bone_name in [k for k in IK_BONES.keys() if k.endswith("IKC")]:
            con_bone = armature_obj.pose.bones.get(
                bone_name[:-4]
            )  # type: bpy.types.PoseBone # type: ignore
            if not con_bone:
                continue
            bone_ikc = IK_BONES[bone_name]
            bone_ikt = IK_BONES[bone_name[:-3] + "IKT"]
            ik_con = next((i for i in con_bone.constraints if i.type == "IK"), None)
            if not ik_con:
                ik_con = con_bone.constraints.new("IK")
            #
            ik_con.enabled = False
            context.view_layer.update()
            ik_con.chain_count = 3  # type: ignore
            con_bone_parent = con_bone
            for i in range(ik_con.chain_count - 1):  # type: ignore
                con_bone_parent = con_bone_parent.parent

            loc = con_bone.tail
            rot = Quaternion((1, 0, 0), math.pi * 0.5)
            matrix = Matrix.LocRotScale(loc, rot, Vector((1, 1, 1)))  # type: ignore
            # armature.bones[bone_ikc.name].matrix_local = matrix
            bone_ikc.matrix = matrix

            src_vec = Vector((0, 1, 0))
            des_vec = con_bone_parent.matrix.col[0].xyz  # type: ignore
            rot = Quaternion(src_vec.cross(des_vec).normalized(), math.acos(src_vec.dot(des_vec)))  # type: ignore
            loc = con_bone_parent.matrix.to_translation()
            loc += des_vec * 1.2  # type: ignore
            ikt_matrix = Matrix.LocRotScale(loc, Quaternion(), Vector((1, 1, 1)))  # type: ignore
            # # armature.bones[bone_ikt.name].matrix_local = matrix
            bone_ikt.matrix = ikt_matrix
            #
            ik_con.target = armature_obj  # type: ignore
            ik_con.subtarget = bone_ikc.name  # type: ignore
            ik_con.pole_target = armature_obj  # type: ignore
            ik_con.pole_subtarget = bone_ikt.name  # type: ignore
            ik_con.pole_angle = 0  # type: ignore
            ik_con.enabled = True
            #
            ik_con.keyframe_insert("enabled")

        # bpy.ops.pose.armature_apply(selected=True)
        # logger.debug(self.bl_label)
        return {"FINISHED"}


# 切换到FK
class OT_SwitchToFK(bpy.types.Operator):
    bl_idname = "amagate.switch_to_fk"
    bl_label = "Switch to FK"
    bl_description = "Switch to FK"
    bl_options = {"INTERNAL", "UNDO"}

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
        armature_obj = context.active_object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        try:
            if armature_obj.animation_data.action.library:
                armature_obj.animation_data.action.make_local()
        except:
            pass
        IK_BONES = {
            "R_Forearm_IKC": armature_obj.pose.bones.get("R_Forearm_IKC"),
            "L_Forearm_IKC": armature_obj.pose.bones.get("L_Forearm_IKC"),
            "R_Boot_IKC": armature_obj.pose.bones.get("R_Boot_IKC"),
            "L_Boot_IKC": armature_obj.pose.bones.get("L_Boot_IKC"),
            "R_Forearm_IKT": armature_obj.pose.bones.get("R_Forearm_IKT"),
            "L_Forearm_IKT": armature_obj.pose.bones.get("L_Forearm_IKT"),
            "R_Boot_IKT": armature_obj.pose.bones.get("R_Boot_IKT"),
            "L_Boot_IKT": armature_obj.pose.bones.get("L_Boot_IKT"),
        }  # type: dict[str, bpy.types.PoseBone] # type: ignore
        for bone_name in [k for k in IK_BONES.keys() if k.endswith("IKC")]:
            con_bone = armature_obj.pose.bones.get(
                bone_name[:-4]
            )  # type: bpy.types.PoseBone # type: ignore
            if not con_bone:
                continue
            ik_con = next((i for i in con_bone.constraints if i.type == "IK"), None)
            if ik_con:
                ik_con.enabled = False
                ik_con.keyframe_insert("enabled")

        ik_bones_coll = armature.collections.get("IK_Bones")
        if ik_bones_coll:
            ik_bones_coll.is_visible = False

        return {"FINISHED"}


# 链接物体
class OT_LinkObject(bpy.types.Operator):
    bl_idname = "amagate.link_object"
    bl_label = "Link"
    bl_description = "Link Object"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context: Context):
        scene_data = context.scene.amagate_data
        prop = scene_data.LinkObjectData
        return prop.obj and prop.obj_anchor and prop.to_anchor

    def execute(self, context: Context):
        scene_data = context.scene.amagate_data
        prop = scene_data.LinkObjectData
        obj = prop.obj  # type: Object
        obj_anchor = prop.obj_anchor  # type: Object
        to_anchor = prop.to_anchor  # type: Object
        #
        coll = obj.users_collection[0]
        # 去掉开头的Blade_以及结尾的.xxx
        name = re.sub(r"^Blade_|\.\d{1,}$", "", obj_anchor.name, flags=re.IGNORECASE)
        name = f"{name}.Link"
        #
        con = obj.constraints.get(name)
        if not con:
            con = obj.constraints.new("CHILD_OF")
            con.name = name
        else:
            con.target = None  # type: ignore
            con.set_inverse_pending = True
        for i in obj.constraints:
            if i.type == "CHILD_OF":
                i.enabled = False
        con.enabled = True
        #
        link_anchor = coll.objects.get(name)
        if not link_anchor:
            link_anchor = obj_anchor.copy()
            link_anchor.parent = None
            coll.objects.link(link_anchor)
            link_anchor.rename(name, mode="SAME_ROOT")

        link_anchor_con = next(
            (i for i in link_anchor.constraints if i.type == "COPY_TRANSFORMS"), None
        )
        if not link_anchor_con:
            link_anchor_con = link_anchor.constraints.new("COPY_TRANSFORMS")
        else:
            link_anchor_con.target = None  # type: ignore
        #
        context.view_layer.update()
        link_anchor.matrix_world = obj_anchor.matrix_world
        con.target = link_anchor  # type: ignore
        context.view_layer.update()
        link_anchor_con.target = to_anchor  # type: ignore

        return {"FINISHED"}


# 导出动画
class OT_ExportAnim(bpy.types.Operator, ExportHelper):
    bl_idname = "amagate.export_anim"
    bl_label = "Export Animation"
    bl_description = "Export Animation"
    bl_options = {"INTERNAL"}
    filename_ext = ".bmv"

    main: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    action: EnumProperty(
        items=[
            ("0", "Export Animation as ...", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore
    filter_glob: StringProperty(default="*.bmv", options={"HIDDEN"})  # type: ignore
    # directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    # filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

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

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
            # bpy.context.view_layer.update()

        armature_obj = context.active_object  # type: Object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        action = armature_obj.animation_data.action
        # has_slot = hasattr(action, "slots")
        fcurves_all = self.fcurves_all

        bones_name = []
        if "Blade_Bones" in armature.collections:
            bones_name = armature.collections["Blade_Bones"].bones.keys()
        if not bones_name:
            bones_name = armature.bones.keys()

        # 帧长度
        frame_len = max(
            *(int(fc.range()[1]) for fc in fcurves_all if fc.group.name in bones_name),
            1,
        )

        use_nla = armature_obj.animation_data.use_nla
        armature_obj.animation_data.use_nla = False
        # old_mode = armature_obj.mode
        # if old_mode != "POSE":
        #     bpy.ops.object.mode_set(mode="POSE")
        # bpy.ops.pose.select_all(action="DESELECT")
        # for bone_name in bones_name:
        #     bone = armature_obj.pose.bones[bone_name]
        #     bone.select = True
        bake_options = anim_utils.BakeOptions(
            only_selected=False,
            do_pose=True,
            do_object=False,
            do_visual_keying=True,
            do_constraint_clear=False,
            do_parents_clear=False,
            do_clean=False,
            do_location=True,
            do_rotation=True,
            do_scale=False,
            do_bbone=False,
            do_custom_props=False,
        )
        baked_action = anim_utils.bake_action(
            armature_obj,
            action=None,
            frames=range(1, frame_len + 1),
            bake_options=bake_options,
        )
        # if old_mode != "POSE":
        #     bpy.ops.object.mode_set(mode=old_mode)
        armature_obj.animation_data.use_nla = use_nla

        if not baked_action:
            self.report({"ERROR"}, "Baking action failed")
            return {"FINISHED"}
        # 恢复动作分配
        armature_obj.animation_data.action = action
        fcurves_all = ag_utils.get_fcurves(baked_action)

        # 目标坐标系
        target_space_inv = Quaternion((1, 0, 0), -math.pi / 2).inverted()  # type: ignore
        buffer = BytesIO()
        # 静态骨骼逆矩阵
        static_bones_matrix_inv = {}
        # 内部名称
        inter_name = action_name.encode("utf-8")
        buffer.write(struct.pack("I", len(inter_name)))
        buffer.write(inter_name)
        # 骨骼数量
        count = len(bones_name)
        buffer.write(struct.pack("I", count))
        # 所有骨骼的旋转姿态
        for bone_idx, bone_name in enumerate(bones_name):
            bone = armature.bones[bone_name]
            bone_quat = bone.matrix_local.to_quaternion()
            static_bones_matrix_inv[bone_name] = bone_quat.inverted()
            # 根骨骼的旋转数据是全局的
            if bone_idx == 0:
                parent_quat = target_space_inv
            elif bone.parent:
                # logger.debug(bone_name)
                parent_quat = static_bones_matrix_inv[bone.parent.name]
            else:
                parent_quat = Quaternion()
            data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
            fcurves = [
                item
                for i in range(4)
                if (item := fcurves_all.find(data_path, index=i)) is not None
            ]

            #
            buffer.write(struct.pack("I", frame_len))
            fcurves_len = len(fcurves)
            for frame in range(1, frame_len + 1):
                if fcurves_len != 4:
                    quat = Quaternion()
                else:
                    quat = Quaternion(fcurves[i].evaluate(frame) for i in range(4))  # type: ignore
                quat_local = bone_quat @ quat
                # if parent_bone:
                #     parent_quat = armature.bones[parent_bone.name].matrix_local.to_quaternion().inverted()  # type: ignore
                # else:
                #     parent_quat = target_space_inv

                # 相对于父旋转
                quat_rel = (parent_quat @ quat_local).normalized()
                buffer.write(struct.pack("ffff", *quat_rel))

        # 根骨骼位置姿态
        bone = armature.bones[bones_name[0]]
        # matrix = bone.matrix_local.copy()
        quat = bone.matrix_local.to_quaternion()
        # location = bone.matrix_local.translation
        data_path = f'pose.bones["{bone.name}"].location'
        fcurves = [
            item
            for i in range(3)
            if (item := fcurves_all.find(data_path, index=i)) is not None
        ]  # type: list[bpy.types.FCurve]

        #
        buffer.write(struct.pack("I", frame_len))
        fcurves_len = len(fcurves)
        for frame in range(1, frame_len + 1):
            if fcurves_len != 3:
                co = Vector()
            else:
                co = Vector(fcurves[i].evaluate(frame) for i in range(3))  # type: ignore
            # co_glob = matrix @ co
            # co_local = target_space_inv @ (co_glob - location)
            co_local = target_space_inv @ quat @ co
            co_local *= 1000
            buffer.write(struct.pack("ddd", *co_local))
        #
        with open(self.filepath, "wb") as f:
            f.write(buffer.getvalue())
        buffer.close()
        # 清理
        bpy.data.actions.remove(baked_action)

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
        channelbag = action
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
        if not channelbag or len(channelbag.fcurves) == 0:  # type: ignore
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}

        self.fcurves_all = channelbag.fcurves  # type: ignore

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

        bones_name = []
        if "Blade_Bones" in armature.collections:
            bones_name = armature.collections["Blade_Bones"].bones.keys()
        if not bones_name:
            bones_name = armature.bones.keys()

        pose_bones = armature_obj.pose.bones
        data_bones = armature.bones
        ag_utils.select_active(context, armature_obj)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")

        bone_count = len(bones_name)
        pose_bone_first = pose_bones[bones_name[0]]  # type: bpy.types.PoseBone
        bone_first = data_bones[bones_name[0]]  # type: bpy.types.Bone

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
                if action.library:
                    action.make_local()
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
                for bone_idx, bone_name in enumerate(bones_name):
                    bone = pose_bones[bone_name]
                    bone.keyframe_insert(
                        "rotation_quaternion", frame=1, group=bone_name
                    )
                    if bone_idx == 0:
                        loc_data_path = f'pose.bones["{bone_name}"].location'
                        bone.keyframe_insert("location", frame=1, group=bone_name)
                for fc in channelbag.fcurves:
                    fc.keyframe_points.clear()

                # start_time = time.time()
                for bone_idx, bone_name in enumerate(bones_name):
                    bone = pose_bones[bone_name]
                    # bone_quat_base = bone.matrix.to_quaternion().normalized()
                    #
                    parent_bone = None if bone_idx == 0 else bone.parent
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
                bone = bone_first
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

    undo: BoolProperty(default=True)  # type: ignore

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
                {"WARNING"}, "Please select the action to mirror in the Action Editor"
            )
            return {"CANCELLED"}

        if action.library:
            action.make_local()
            bpy.ops.ed.undo_push(message="Make Local")

        action_name = action.name
        channelbag = action
        has_slot = hasattr(armature_obj.animation_data, "action_slot")
        if has_slot:
            slot = armature_obj.animation_data.action_slot
            if not slot:
                self.report(
                    {"WARNING"},
                    "Please select the action slot to mirror in the Action Editor",
                )
                return {"CANCELLED"}
            action_name = slot.name_display
            channelbag = next((c for l in action.layers for s in l.strips for c in s.channelbags if c.slot == slot), None)  # type: ignore
        if not channelbag or len(channelbag.fcurves) == 0:  # type: ignore
            self.report({"ERROR"}, "Animation data not found")
            return {"CANCELLED"}
        #
        self.channelbag = channelbag
        self.execute2(context)
        if self.undo:
            bpy.ops.ed.undo_push(message=self.bl_label)

        return {"FINISHED"}

    def execute2(self, context: Context):
        scene = context.scene
        scene_data = context.scene.amagate_data
        armature_obj = context.active_object  # type: Object
        armature = armature_obj.data  # type: bpy.types.Armature # type: ignore
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        # bpy.ops.object.mode_set(mode="POSE")
        # bpy.ops.pose.select_all(action="SELECT")

        action = armature_obj.animation_data.action
        bones_name = armature.bones.keys()
        # has_slot = hasattr(armature_obj.animation_data, "action_slot")
        channelbag = self.channelbag
        # 帧长度
        frame_len = max(int(fc.range()[1]) for fc in channelbag.fcurves)

        static_bones_rot = {}
        glob_rot_lst = {}
        # 对称骨骼名称字典
        sym_names = {}
        for bone in armature.bones:
            bone_name = bone.name
            name = bone_name.lower()
            if name.startswith("l_"):
                find_name = f"r_{name[2:]}"
                sym_name = next(
                    (b.name for b in armature.bones if b.name.lower() == find_name),
                    None,
                )
                if sym_name:
                    sym_names[bone_name] = sym_name
                    sym_names[sym_name] = bone_name
            #
            q = bone.matrix_local.to_quaternion()
            static_bones_rot[bone_name] = (q, q.inverted())
            glob_rot_lst[bone_name] = q

        # scene.frame_set(frame_len + 1)
        ag_utils.select_active(context, armature_obj)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.transforms_clear()
        bpy.ops.object.mode_set(mode="OBJECT")

        cursor = scene.cursor
        # 复制骨架
        bpy.ops.object.duplicate()
        armature_child = context.active_object
        armature_child.rename("armature_child")
        bpy.ops.object.duplicate()
        armature_mirror = context.active_object
        armature_mirror.rename("armature_mirror")
        # 设置镜像骨架
        # scene.frame_set(frame_len + 1)
        # bpy.ops.object.mode_set(mode="POSE")
        # bpy.ops.pose.select_all(action="SELECT")
        # bpy.ops.pose.transforms_clear()
        # bpy.ops.anim.keyframe_insert_by_name(type="BUILTIN_KSI_LocRot")
        prev_cursor = cursor.location.copy()
        # prev_loc = armature_mirror.location.copy()
        cursor.location = (
            armature_obj.matrix_world @ armature.bones[0].matrix_local.translation
        )
        # bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        bpy.ops.transform.mirror(
            orient_type="GLOBAL", constraint_axis=(True, False, False)
        )
        # cursor.location = prev_loc
        # bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        cursor.location = prev_cursor
        # 设置子骨架
        bpy.data.actions.remove(armature_child.animation_data.action)  # type: ignore
        ag_utils.select_active(context, armature_child)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.armature.select_all(action="SELECT")
        bpy.ops.armature.parent_clear(type="CLEAR")
        # 设置父级
        bpy.ops.object.mode_set(mode="POSE")
        for bone in armature_child.pose.bones:
            constraint = bone.constraints.new(type="CHILD_OF")
            constraint.target = armature_mirror  # type: ignore
            sym_name = sym_names.get(bone.name, bone.name)
            constraint.subtarget = sym_name  # type: ignore
            # bpy.ops.constraint.childof_set_inverse()
        bpy.ops.object.mode_set(mode="OBJECT")

        bones_num = len(armature.bones)
        # 设置约束
        for bone_idx in range(bones_num):
            bone = armature_obj.pose.bones[bone_idx]
            bone_name = bone.name
            con_rot = bone.constraints.new(type="COPY_ROTATION")
            con_rot.target = armature_child
            con_rot.subtarget = bone_name
            con_rot.target_space = "WORLD"
            con_rot.owner_space = "WORLD"
            if bone_idx == 0:
                con_loc = bone.constraints.new(type="COPY_LOCATION")
                con_loc.target = armature_child
                con_loc.subtarget = bone_name
                con_loc.target_space = "WORLD"
                con_loc.owner_space = "WORLD"
        # 烘焙
        bake_options = anim_utils.BakeOptions(
            only_selected=False,
            do_pose=True,
            do_object=False,
            do_visual_keying=True,
            do_constraint_clear=True,
            do_parents_clear=False,
            do_clean=False,
            do_location=True,
            do_rotation=True,
            do_scale=False,
            do_bbone=False,
            do_custom_props=False,
        )
        baked_action = anim_utils.bake_action(
            armature_obj,
            action=None,
            frames=range(1, frame_len + 1),
            bake_options=bake_options,
        )
        baked_action.rename(f"{action.name}_mirror")
        if hasattr(armature_obj.animation_data, "action_slot"):
            armature_obj.animation_data.action_slot.name_display = baked_action.name

        ag_utils.select_active(context, armature_obj)
        # scene.frame_set(1)
        # 清理
        bpy.data.actions.remove(armature_mirror.animation_data.action)  # type: ignore
        bpy.data.armatures.remove(armature_mirror.data)  # type: ignore
        bpy.data.armatures.remove(armature_child.data)  # type: ignore

        return

        # 曲线字典
        def get_fcurves(fcurves_all, clear=True):
            fcurves_rot = {}  # type: dict[str, list[bpy.types.FCurve]]
            fcurves_loc = []  # type: list[bpy.types.FCurve]
            for bone_idx in range(bones_num):
                bone = armature.bones[bone_idx]
                bone_name = bone.name
                fcurves = []
                data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
                for i in range(4):
                    fc = fcurves_all.find(data_path, index=i)
                    if fc is None:
                        fc = fcurves_all.new(data_path, index=i)
                    elif clear:
                        fc.keyframe_points.clear()
                    fcurves.append(fc)
                fcurves_rot[bone_name] = fcurves
                #
                if bone_idx == 0:
                    data_path = f'pose.bones["{bone_name}"].location'
                    for i in range(3):
                        fc = fcurves_all.find(data_path, index=i)
                        if fc is None:
                            fc = fcurves_all.new(data_path, index=i)
                        elif clear:
                            fc.keyframe_points.clear()
                        fcurves_loc.append(fc)

            return fcurves_rot, fcurves_loc

        # 烘焙动作
        bake_options = anim_utils.BakeOptions(
            only_selected=False,
            do_pose=True,
            do_object=False,
            do_visual_keying=True,
            do_constraint_clear=True,
            do_parents_clear=False,
            do_clean=False,
            do_location=True,
            do_rotation=True,
            do_scale=False,
            do_bbone=False,
            do_custom_props=False,
        )
        baked_action = anim_utils.bake_action(
            armature_child,
            action=None,
            frames=range(1, frame_len + 1),
            bake_options=bake_options,
        )
        # 烘焙到主骨架
        fcurves_rot, fcurves_loc = get_fcurves(channelbag.fcurves)
        fcurves_rot_ref, fcurves_loc_ref = get_fcurves(
            ag_utils.get_fcurves(baked_action), clear=False
        )
        for frame in range(1, frame_len + 1):
            for bone_idx in range(bones_num):
                bone = armature_obj.pose.bones[bone_idx]
                bone_name = bone.name
                fcurves = fcurves_rot[bone_name]
                fcurves_ref = fcurves_rot_ref[bone_name]
                #
                quat_curr = glob_rot_lst[bone_name]
                quat_target = Quaternion(fcurves_ref[i].evaluate(frame) for i in range(4))  # type: ignore
                quat_target = (
                    static_bones_rot[bone_name][0] @ quat_target
                ).normalized()
                if quat_target.dot(quat_curr) > epsilon2:
                    quat = Quaternion()
                    quat_local = Quaternion()
                else:
                    quat = quat_target @ quat_curr.inverted()
                    quat_local = static_bones_rot[bone_name][1] @ quat

                # bone_ref = armature_child.pose.bones[bone_name]
                # quat_curr_inv = quat_curr.inverted()
                # quat_pose = bone_ref.matrix.to_quaternion()
                # quat_glob = quat_pose @ quat_curr_inv

                # quat = quat_curr_inv @ quat_glob @ quat_curr  # 世界转局部
                # quat2 = (bone.rotation_quaternion @ quat).normalized()

                for idx in range(4):
                    fcurves[idx].keyframe_points.insert(frame, quat_local[idx])
                if bone_idx == 0:
                    # loc_pose = bone_ref.matrix.to_translation()
                    # loc = matrix_root_inv @ loc_pose
                    for idx in range(3):
                        fcurves_loc[idx].keyframe_points.insert(
                            frame, fcurves_loc_ref[idx].evaluate(frame)
                        )
                #
                # glob_rot_lst[bone_name] = (quat @ glob_rot_lst[bone_name]).normalized()
                for b in bone.children_recursive:
                    glob_rot_lst[b.name] = (quat @ glob_rot_lst[b.name]).normalized()


# 设置动画
class OT_SetAnim(bpy.types.Operator):
    bl_idname = "amagate.set_anim"
    bl_label = "Set Animation"
    bl_description = "Set Animation"
    bl_options = {"INTERNAL"}
    bl_property = "enum"

    undo: BoolProperty(default=True)  # type: ignore

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
        # armature_data = armature.data  # type: bpy.types.Armature # type: ignore
        return self.execute_static(self, context, armature, action_name, filename)  # type: ignore

    @staticmethod
    def execute_static(
        this, context: Context, armature: Object, action_name: str, filename: str
    ):
        is_operator = isinstance(this, OT_SetAnim)

        action = bpy.data.actions.get(action_name)  # type: ignore
        if not action:
            filepath = os.path.join(data.ADDON_PATH, "Models", "Anm", filename)
            if not os.path.exists(filepath):
                if is_operator:
                    this.report({"ERROR"}, f"{pgettext('File not found')}: {filename}")
                else:
                    logger.error(f"{pgettext('File not found')}: {filename}")
                return {"CANCELLED"}

            with bpy.data.libraries.load(filepath, link=True) as (data_from, data_to):
                action_from = next(
                    (i for i in data_from.actions if i == action_name), None
                )
                if not action_from:
                    if is_operator:
                        this.report(
                            {"ERROR"}, f"Action {action_name} not found in {filename}"
                        )
                    else:
                        logger.error(f"Action {action_name} not found in {filename}")
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

        if is_operator and this.undo:
            bpy.ops.ed.undo_push(message=this.bl_description)

        return {"FINISHED"}

    def invoke(self, context: Context, event: bpy.types.Event):
        context.window_manager.invoke_search_popup(self)
        return {"FINISHED"}


############################
# 摄像机导出
class OT_ExportCamera(bpy.types.Operator, ExportHelper):
    bl_idname = "amagate.export_camera"
    bl_label = "Export Camera"
    bl_description = "Export Camera"
    bl_options = {"INTERNAL"}
    filename_ext = ".cam"

    main: BoolProperty(default=False, options={"HIDDEN"})  # type: ignore
    action: EnumProperty(
        items=[
            ("0", "Export Camera as ...", ""),
        ],
        options={"HIDDEN"},
    )  # type: ignore
    filter_glob: StringProperty(default="*.cam", options={"HIDDEN"})  # type: ignore
    # directory: StringProperty(subtype="DIR_PATH")  # type: ignore
    # filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

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
        if action.library:
            action.make_local()
        channelbag = action  # type: bpy.types.Action
        action.use_fake_user = True

        action_name_data = f"{action_name}.fov"
        action_data = bpy.data.actions.get(action_name_data)
        if not action_data:
            action_data = bpy.data.actions.new(name=action_name_data)
        if action_data.library:
            action_data.make_local()
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
############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.Operator)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and issubclass(cls, class_tuple)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
