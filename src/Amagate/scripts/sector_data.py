# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import re
import os
import math
import shutil
import pickle
import threading
import contextlib
from io import StringIO, BytesIO
from typing import Any, TYPE_CHECKING

# from collections import Counter
#
import bpy

import bmesh
from bpy.app.translations import pgettext

# from bpy.types import Context
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
import rna_keymap_ui
import blf
from mathutils import *  # type: ignore

#
from . import ag_utils, data

#

if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene


############################
############################ Collection Props
############################
# 布尔收集器
class BoolCollection(bpy.types.PropertyGroup):
    index: IntProperty(default=0)  # type: ignore
    value: BoolProperty(default=False, get=lambda self: self.get_value(), set=lambda self, value: self.set_value(value))  # type: ignore

    def get_value(self):
        from . import L3D_data

        active_sec_data = L3D_data.ACTIVE_SECTOR.amagate_data.get_sector_data()
        group = ag_utils.int_to_uint(active_sec_data.group)
        return (group >> self.index) & 1

    def set_value(self, value):
        from . import L3D_data

        mask_limit = 0xFFFFFFFF
        mask = 1 << self.index

        selected_sectors = L3D_data.SELECTED_SECTORS

        # 全部设置为代表扇区的相反值
        if value:
            for sec in selected_sectors:
                sec_data = sec.amagate_data.get_sector_data()
                group = ag_utils.uint_to_int(sec_data.group | mask)  # 设置为1
                sec_data.group = group
        else:
            for sec in selected_sectors:
                sec_data = sec.amagate_data.get_sector_data()
                group = ag_utils.uint_to_int(
                    sec_data.group & (~mask & mask_limit)
                )  # 设置为0
                sec_data.group = group


############################
############################ Object Props
############################


# 纹理属性
class TextureProperty(bpy.types.PropertyGroup):
    name: StringProperty(default="")  # type: ignore
    target: StringProperty(default="")  # type: ignore

    id: IntProperty(name="ID", default=0, get=lambda self: self.get_id(), set=lambda self, value: self.set_id(value))  # type: ignore

    pos: FloatVectorProperty(subtype="XYZ", size=2, get=lambda self: (self.xpos, self.ypos))  # type: ignore
    xpos: FloatProperty(description="X Position", step=10, default=0.0, get=lambda self: self.get_pos(0), set=lambda self, value: self.set_pos(value, 0))  # type: ignore
    ypos: FloatProperty(description="Y Position", step=10, default=0.0, get=lambda self: self.get_pos(1), set=lambda self, value: self.set_pos(value, 1))  # type: ignore

    zoom: FloatVectorProperty(subtype="XYZ", size=2, get=lambda self: (self.xzoom, self.yzoom))  # type: ignore
    xzoom: FloatProperty(description="X Zoom", step=10, default=0.0, get=lambda self: self.get_zoom(0), set=lambda self, value: self.set_zoom(value, 0))  # type: ignore
    yzoom: FloatProperty(description="Y Zoom", step=10, default=0.0, get=lambda self: self.get_zoom(1), set=lambda self, value: self.set_zoom(value, 1))  # type: ignore
    zoom_constraint: BoolProperty(
        name="Constraint",
        # description="Zoom Constraint",
        default=True,
    )  # type: ignore

    angle: FloatProperty(name="Angle", unit="ROTATION", subtype="ANGLE", default=0.0, step=10, precision=5, get=lambda self: self.get_angle(), set=lambda self, value: self.set_angle(value))  # type: ignore
    ############################

    def get_id(self):
        return self.get("id", 0)

    def set_id(self, value):
        from . import L3D_data

        context = bpy.context

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if "EDIT" in context.mode:
                tex = L3D_data.get_texture_by_id(value)[1]
                mat = L3D_data.ensure_material(tex)
                for item in L3D_data.SELECTED_FACES:
                    update = False
                    sec = item[2]
                    sec_data = sec.amagate_data.get_sector_data()
                    bm = item[0]
                    faces = []

                    layers = bm.faces.layers.int.get(f"amagate_tex_id")
                    amagate_flag = bm.faces.layers.int.get(f"amagate_flag")
                    selected_faces = item[1]
                    for face in selected_faces:
                        face[amagate_flag] = L3D_data.FACE_FLAG["Custom"]  # type: ignore
                        if face[layers] != value:  # type: ignore
                            face[layers] = value  # type: ignore
                            faces.append(face)
                            update = True
                    if faces:
                        sec_data.set_matslot(mat, faces, bm)
                    if update:
                        sec.update_tag()
            # 修改预设纹理的情况
            else:
                for sec in L3D_data.SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_id(value)
        else:
            if value == self.id:
                return

            self["id"] = value

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            sec_data = sec.amagate_data.get_sector_data()
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            tex = L3D_data.get_texture_by_id(value)[1]

            faces = []
            face_flag = L3D_data.FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes["amagate_tex_id"].data[i]  # type: ignore
                    if face_attr.value != value:
                        face_attr.value = value
                        update = True
                        faces.append(mesh.polygons[i])
            if faces:
                sec_data.set_matslot(L3D_data.ensure_material(tex), faces)
            # if update:
            #     sec.update_tag()

    ############################
    def get_pos(self, index=0):
        from . import L3D_data

        context = bpy.context

        attr = ("xpos", "ypos")[index]
        if self.target == "SectorPublic":
            # 单独访问面的情况
            if "EDIT" in context.mode:
                selected_faces = L3D_data.SELECTED_FACES
                if selected_faces:
                    item = selected_faces[0]
                    layers = item[0].faces.layers.float.get(f"amagate_tex_{attr}")
                    face = item[1][0]
                    return face[layers]  # type: ignore
                else:
                    return 0.0
            else:
                ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR
                sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
                return getattr(sec_data.textures[self.name], attr)
        else:
            return self.get(attr, -1.0)

    def set_pos(self, value, index=0):
        from . import L3D_data

        context = bpy.context

        attr = ("xpos", "ypos")[index]

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if "EDIT" in context.mode:
                for item in L3D_data.SELECTED_FACES:
                    update = False
                    sec = item[2]
                    sec_data = sec.amagate_data.get_sector_data()
                    bm = item[0]

                    layers = item[0].faces.layers.float.get(f"amagate_tex_{attr}")
                    amagate_flag = bm.faces.layers.int.get(f"amagate_flag")
                    # selected_faces = ag_utils.expand_conn(item[1], bm)
                    selected_faces = item[1]
                    for face in selected_faces:
                        face[amagate_flag] = L3D_data.FACE_FLAG["Custom"]  # type: ignore
                        if face[layers] != value:  # type: ignore
                            face[layers] = value  # type: ignore
                            update = True
                    if update:
                        sec.update_tag()
                data.area_redraw("VIEW_3D")
            # 修改预设纹理的情况
            else:
                SELECTED_SECTORS = L3D_data.SELECTED_SECTORS
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_pos(value, index)
        else:
            self[attr] = value

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            face_flag = L3D_data.FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes[f"amagate_tex_{attr}"].data[i]  # type: ignore
                    if face_attr.value != value:
                        face_attr.value = value
                        update = True
            # if update:
            #     sec.update_tag()

    ############################
    def get_zoom(self, index):
        from . import L3D_data

        context = bpy.context

        attr = ("xzoom", "yzoom")[index]
        if self.target == "SectorPublic":
            # 单独访问面的情况
            if "EDIT" in context.mode:
                selected_faces = L3D_data.SELECTED_FACES
                if selected_faces:
                    item = selected_faces[0]
                    layers = item[0].faces.layers.float.get(f"amagate_tex_{attr}")
                    face = item[1][0]
                    return face[layers]  # type: ignore
                else:
                    return 0.0
            else:
                ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR
                sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
                return getattr(sec_data.textures[self.name], attr)
        else:
            return self.get(attr, -1.0)

    def set_zoom(self, value, index, constraint=None):
        from . import L3D_data

        context = bpy.context

        attr = ("xzoom", "yzoom")[index]
        attr2 = ("xzoom", "yzoom")[1 - index]
        value2 = None
        if (constraint is None and self.zoom_constraint) or (
            constraint is not None and constraint
        ):
            old_value = getattr(self, attr)
            if old_value == 0:
                value2 = value
            else:
                factor = value / old_value
                value2 = getattr(self, attr2) * factor

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if "EDIT" in context.mode:
                for item in L3D_data.SELECTED_FACES:
                    update = False
                    sec = item[2]
                    sec_data = sec.amagate_data.get_sector_data()
                    bm = item[0]

                    layers = item[0].faces.layers.float.get(f"amagate_tex_{attr}")
                    layers2 = item[0].faces.layers.float.get(f"amagate_tex_{attr2}")
                    amagate_flag = bm.faces.layers.int.get(f"amagate_flag")
                    # selected_faces = ag_utils.expand_conn(item[1], bm)
                    selected_faces = item[1]
                    for face in selected_faces:
                        face[amagate_flag] = L3D_data.FACE_FLAG["Custom"]  # type: ignore
                        if face[layers] != value:  # type: ignore
                            face[layers] = value  # type: ignore
                            update = True
                        if value2 is not None and face[layers2] != value2:  # type: ignore
                            face[layers2] = value2  # type: ignore
                    if update:
                        sec.update_tag()
                data.area_redraw("VIEW_3D")
            # 修改预设纹理的情况
            else:
                SELECTED_SECTORS = L3D_data.SELECTED_SECTORS
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_zoom(
                        value, index, constraint=self.zoom_constraint
                    )
        else:
            self[attr] = value
            if value2 is not None:
                self[attr2] = value2

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            face_flag = L3D_data.FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr_1 = mesh.attributes[f"amagate_tex_{attr}"].data[i]  # type: ignore
                    if face_attr_1.value != self[attr]:
                        face_attr_1.value = self[attr]
                        update = True
                    face_attr_2 = mesh.attributes[f"amagate_tex_{attr2}"].data[i]  # type: ignore
                    if face_attr_2.value != self[attr2]:
                        face_attr_2.value = self[attr2]
            # if update:
            #     sec.update_tag()

    ############################
    def get_angle(self):
        from . import L3D_data

        context = bpy.context

        attr = "angle"
        if self.target == "SectorPublic":
            # 单独访问面的情况
            if "EDIT" in context.mode:
                selected_faces = L3D_data.SELECTED_FACES
                if selected_faces:
                    item = selected_faces[0]
                    layers = item[0].faces.layers.float.get(f"amagate_tex_{attr}")
                    face = item[1][0]
                    return face[layers]  # type: ignore
                else:
                    return 0.0
            else:
                ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR
                sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
                return getattr(sec_data.textures[self.name], attr)
        else:
            return self.get(attr, -1.0)

    def set_angle(self, value):
        from . import L3D_data

        context = bpy.context

        attr = "angle"

        if self.target == "SectorPublic":
            # 单独修改面的情况
            if "EDIT" in context.mode:
                for item in L3D_data.SELECTED_FACES:
                    update = False
                    sec = item[2]
                    sec_data = sec.amagate_data.get_sector_data()
                    bm = item[0]

                    layers = item[0].faces.layers.float.get(f"amagate_tex_{attr}")
                    amagate_flag = bm.faces.layers.int.get(f"amagate_flag")
                    # selected_faces = ag_utils.expand_conn(item[1], bm)
                    selected_faces = item[1]
                    for face in selected_faces:
                        face[amagate_flag] = L3D_data.FACE_FLAG["Custom"]  # type: ignore
                        if face[layers] != value:  # type: ignore
                            face[layers] = value  # type: ignore
                            update = True
                    if update:
                        sec.update_tag()
                data.area_redraw("VIEW_3D")
            # 修改预设纹理的情况
            else:
                SELECTED_SECTORS = L3D_data.SELECTED_SECTORS
                for sec in SELECTED_SECTORS:
                    sec_data = sec.amagate_data.get_sector_data()
                    sec_data.textures[self.name].set_angle(value)
        else:
            self[attr] = value

            if self.target != "Sector":
                return

            # 给对应标志的面应用预设属性
            sec = self.id_data  # type: Object
            mesh = sec.data  # type: bpy.types.Mesh # type: ignore
            face_flag = L3D_data.FACE_FLAG[self.name]
            update = False
            for i, d in enumerate(mesh.attributes["amagate_flag"].data):  # type: ignore
                if d.value == face_flag:
                    face_attr = mesh.attributes[f"amagate_tex_{attr}"].data[i]  # type: ignore
                    if face_attr.value != value:
                        face_attr.value = value
                        update = True
            # if update:
            #     sec.update_tag()


# 平面光属性
class FlatLightProperty(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.784, 0.784, 0.784),
    )  # type: ignore
    vector: FloatVectorProperty(
        name="Direction",
        subtype="XYZ",
        default=(0.0, 0.0, 0.0),
        size=3,
        min=-1.0,
        max=1.0,
    )  # type: ignore


class SectorFocoLightProperty(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="")  # type: ignore
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0, 0, 0),  # 0.784, 0.784, 0.392
    )  # type: ignore
    pos: FloatVectorProperty(
        name="Position",
        subtype="XYZ",
        default=(0.0, 0.0, 0.0),
        size=3,
    )  # type: ignore
    strength: FloatProperty(
        name="Strength",
        description="Strength of the light",  # 光照强度
        default=1.0,
    )  # type: ignore
    precision: FloatProperty(
        name="Precision",
        description="Precision of the light",  # 精度
        default=0.03125,
    )  # type: ignore
    # TODO


# 虚拟扇区属性
class GhostSectorProperty(bpy.types.PropertyGroup):
    height: FloatProperty(name="Height", default=2, min=0.01)  # type: ignore


# 扇区属性
class SectorProperty(bpy.types.PropertyGroup):
    target: StringProperty(name="Target", default="Sector")  # type: ignore
    id: IntProperty(name="ID", default=0)  # type: ignore
    has_sky: BoolProperty(default=False)  # type: ignore
    is_convex: BoolProperty(default=False)  # type: ignore
    is_2d_sphere: BoolProperty(default=False)  # type: ignore
    connect_num: IntProperty(default=0)  # type: ignore

    # 大气
    atmo_id: IntProperty(name="Atmosphere", description="", default=0, get=lambda self: self.get_atmo_id(), set=lambda self, value: self.set_atmo_id(value))  # type: ignore
    atmo_color: FloatVectorProperty(name="Color", description="", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.0, 0.0, 0.0))  # type: ignore
    atmo_density: FloatProperty(name="Density", description="", default=0.02, min=0.0, soft_max=1.0)  # type: ignore
    # 纹理
    textures: CollectionProperty(type=TextureProperty)  # type: ignore
    # 外部光
    # 环境光
    ambient_color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0, 0, 0),
        get=lambda self: self.get_ambient_color(),
        set=lambda self, value: self.set_ambient_color(value),
    )  # type: ignore
    # 外部光
    external_id: IntProperty(name="External Light", description="", default=0, get=lambda self: self.get_external_id(), set=lambda self, value: self.set_external_id(value))  # type: ignore
    external_obj: PointerProperty(type=bpy.types.Object)  # type: ignore
    flat_light: PointerProperty(type=FlatLightProperty)  # type: ignore # 平面光

    spot_light: CollectionProperty(type=SectorFocoLightProperty)  # type: ignore # 聚光灯

    comment: StringProperty(name="Comment", description="", default="")  # type: ignore
    group: IntProperty(
        name="Group",
        description="",
        default=0,  # 默认值为0
    )  # type: ignore
    group_set: CollectionProperty(type=BoolCollection)  # type: ignore

    # 陡峭设置
    steep_check: BoolProperty(default=False)  # type: ignore
    steep: EnumProperty(
        name="",
        description="",
        items=[
            ("0", "Auto", ""),
            ("1", "Yes", ""),
            ("2", "No", ""),
        ],
        default="0",
        get=lambda self: self.get_steep(),
        set=lambda self, value: self.set_steep(value),
    )  # type: ignore

    ############################
    def get_atmo_id(self):
        return self.get("_atmo_id", 0)

    def set_atmo_id(self, value):
        from . import L3D_data

        if self.target == "Scene":
            self["_atmo_id"] = value
            return

        scene_data = bpy.context.scene.amagate_data
        obj = self.id_data
        atmo = L3D_data.get_atmo_by_id(scene_data, value)[1]
        if not atmo:
            return

        if value != self.atmo_id:
            old_atmo = L3D_data.get_atmo_by_id(scene_data, self.atmo_id)[1]
            if old_atmo:
                old_atmo.users_obj.remove(old_atmo.users_obj.find(f"{self.id}"))

        if not atmo.users_obj.get(f"{self.id}"):
            atmo.users_obj.add().obj = obj

        self["_atmo_id"] = value
        scene_data["SectorManage"]["sectors"][str(self.id)]["atmo_id"] = value
        self.update_atmo(atmo)

    def update_atmo(self, atmo):
        self.atmo_color = atmo.color[:3]
        f = 1.0
        if tuple(self.atmo_color) == (0.0, 0.0, 0.0):
            f = 2.0
        self.atmo_density = atmo.color[-1] * f
        self.id_data.update_tag(refresh={"OBJECT"})

    ############################
    def get_external_id(self):
        return self.get("_external_id", 0)

    def set_external_id(self, value):
        from . import L3D_data

        if self.target == "Scene":
            self["_external_id"] = value
            return

        scene_data = bpy.context.scene.amagate_data
        obj = self.id_data
        external = L3D_data.get_external_by_id(scene_data, value)[1]
        if not external:
            return
        if not (external.data and external.obj):
            external.update_obj()

        if value != self.external_id:
            old_external_id = self.external_id
            old_external = L3D_data.get_external_by_id(scene_data, old_external_id)[1]
            if old_external:
                old_external.users_obj.remove(old_external.users_obj.find(f"{self.id}"))

        if not external.users_obj.get(f"{self.id}"):
            external.users_obj.add().obj = obj

        self["_external_id"] = value
        scene_data["SectorManage"]["sectors"][str(self.id)]["external_id"] = value
        # self.update_external(external)

    # def update_external(self, external, rotation_euler=None):
    #     if not rotation_euler:
    #         rotation_euler = external.vector.to_track_quat("-Z", "Z").to_euler()
    #     obj = self.ensure_external_obj(external)
    #     obj.rotation_euler = rotation_euler

    # def ensure_external_obj(self, external):
    #     light_data = external.obj

    #     light = self.external_obj
    #     if not light:
    #         name = f"AG.Sector{self.id}.Sun"
    #         light = bpy.data.objects.get(name)
    #         if not light:
    #             light = bpy.data.objects.new(name, object_data=light_data)
    #         else:
    #             light.data = light_data
    #         self.external_obj = light

    #         light.hide_select = True  # 不可选
    #         light.hide_viewport = True  # 不可见
    #         # self.id_data.users_collection[0].objects.link(light)
    #         # light.parent = self.id_data
    #         link2coll(light, ensure_collection(AG_COLL, hide_select=True))
    #         # 创建灯光链接集合
    #         collections = bpy.data.collections
    #         name = f"{name}.Linking"
    #         lightlink_coll = collections.get(name)
    #         if lightlink_coll:
    #             collections.remove(lightlink_coll)
    #         lightlink_coll = collections.new(name)
    #         # light.light_linking.receiver_collection = lightlink_coll
    #         # light.light_linking.blocker_collection = lightlink_coll
    #         # link2coll(ensure_null_object(), lightlink_coll)

    #         # 将外部光物体约束到扇区中心，如果为天空扇区则可见，否则不可见
    #     elif light.data != light_data:
    #         light.data = light_data

    #     return self.external_obj

    ############################
    def get_ambient_color(self):
        from . import L3D_data

        ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR

        attr = "ambient_color"
        if self.target == "SectorPublic":
            sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
            return getattr(sec_data, attr)
        else:
            return self.get(attr, (0.784, 0.784, 0.784))

    def set_ambient_color(self, value):
        from . import L3D_data

        ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR
        SELECTED_SECTORS = L3D_data.SELECTED_SECTORS

        attr = "ambient_color"

        if self.target == "SectorPublic":
            for sec in SELECTED_SECTORS:
                sec_data = sec.amagate_data.get_sector_data()
                setattr(sec_data, attr, value)
            data.area_redraw("VIEW_3D")
        else:
            # if value == tuple(getattr(self, attr)):
            #     return

            self[attr] = value

            if self.target == "Sector":
                self.id_data.update_tag(refresh={"OBJECT"})
                # light_data = self.ensure_ambient_light()
                # light_data.color = getattr(self, attr)

    # def ensure_ambient_light(self):
    #     scene_data = bpy.context.scene.amagate_data
    #     name = f"AG.Sector{self.id}.Ambient"
    #     light_data = bpy.data.lights.get(name)
    #     if not light_data:
    #         light_data = bpy.data.lights.new(name, type="SUN")
    #         light_data.volume_factor = 0.0
    #         light_data.use_shadow = False
    #         light_data.angle = math.pi  # type: ignore
    #         light_data.energy = 8.0  # type: ignore
    #         light_data.color = self.ambient_color
    #     # 创建灯光链接集合
    #     collections = bpy.data.collections
    #     name = f"{name}.Linking"
    #     lightlink_coll = collections.get(name)
    #     if not lightlink_coll:
    #         lightlink_coll = collections.new(name)
    #         # link2coll(ensure_null_object(), lightlink_coll)
    #     link2coll(self.id_data, lightlink_coll)

    #     for i in range(1, 3):  # 1 2
    #         name = f"{light_data.name}{i}"
    #         obj = bpy.data.objects.get(name)
    #         if not obj:
    #             obj = bpy.data.objects.new(name, object_data=light_data)
    #         elif obj.data != light_data:
    #             obj.data = light_data
    #         if i == 1:
    #             obj.rotation_euler = (0, 0, 0)
    #         else:
    #             obj.rotation_euler = (math.pi, 0, 0)
    #         link2coll(obj, ensure_collection(AG_COLL, hide_select=True))
    #         obj.light_linking.receiver_collection = lightlink_coll
    #         obj.light_linking.blocker_collection = lightlink_coll

    #     return light_data

    ############################

    def get_steep(self):
        from . import L3D_data

        ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR

        attr = "steep"
        if self.target == "SectorPublic":
            sec_data = ACTIVE_SECTOR.amagate_data.get_sector_data()
            return int(
                getattr(sec_data, attr)
            )  # 并不是get回调返回的索引，而是索引对应的ID字符串
        else:
            return self.get(attr, 0)

    def set_steep(self, value: int):
        from . import L3D_data

        ACTIVE_SECTOR = L3D_data.ACTIVE_SECTOR
        SELECTED_SECTORS = L3D_data.SELECTED_SECTORS

        attr = "steep"

        if self.target == "SectorPublic":
            for sec in SELECTED_SECTORS:
                sec_data = sec.amagate_data.get_sector_data()
                setattr(
                    sec_data, attr, str(value)
                )  # value是索引，需要转为对应的ID字符串
        else:
            self[attr] = value

    ############################
    def set_matslot(self, mat, set_faces=[], bm: bmesh.types.BMesh = None):  # type: ignore
        """设置材质槽位"""
        obj = self.id_data  # type: Object
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore

        slot = obj.material_slots.get(mat.name)
        if not slot:
            # 排除已使用的槽位
            slots = set(range(len(obj.material_slots)))
            faces = bm.faces if bm else mesh.polygons
            for face in faces:
                if face in set_faces:
                    continue
                slots.discard(face.material_index)
                if not slots:
                    break

            # 选择空槽位，如果没有的话则新建
            if slots:
                slot = obj.material_slots[slots.pop()]
                slot.material = mat  # 更改现有材质
            else:
                mesh.materials.append(mat)
                slot = obj.material_slots[-1]

        if slot.link != "DATA":
            slot.link = "DATA"
        if not slot.material:
            slot.material = mat
        slot_index = slot.slot_index

        if bm:
            bm.faces.ensure_lookup_table()
        for face in set_faces:
            face.material_index = slot_index

    ############################
    def get_id(self) -> int:
        scene_data = bpy.context.scene.amagate_data
        SectorManage = scene_data["SectorManage"]

        if SectorManage["deleted_id_count"]:
            SectorManage["deleted_id_count"] -= 1
            id_ = 1
            while f"{id_}" in SectorManage["sectors"]:
                id_ += 1
        else:
            SectorManage["max_id"] += 1
            id_ = SectorManage["max_id"]
        return id_

    ############################

    def mesh_unique(self):
        """确保网格数据为单用户的"""
        sec = self.id_data  # type: Object
        if sec.data.users > 1:
            sec.data = sec.data.copy()
            sec.data.rename(f"Sector{self.id}", mode="ALWAYS")

    ############################
    def reset_concave_data(self):
        self["ConcaveData"] = {
            "flat_ext": [],
            "faces_int_idx": [],
            "concave_type": ag_utils.CONCAVE_T_NONE,
        }

    def reset_connect_data(self):
        mesh = self.id_data.data  # type: bpy.types.Mesh # type: ignore
        self.connect_num = 0  # 重置连接数
        # 重置连接属性
        attributes = mesh.attributes.get("amagate_connected")
        if attributes:
            mesh.attributes.remove(attributes)
        mesh.attributes.new(name="amagate_connected", type="INT", domain="FACE")

    def init(self, post_copy=False):
        from . import L3D_data

        scene = bpy.context.scene
        scene_data = scene.amagate_data

        id_ = self.get_id()
        self.id = id_

        obj = self.id_data  # type: Object
        matrix_world = obj.matrix_world.copy()
        mesh = obj.data  # type: bpy.types.Mesh # type: ignore
        # 添加到扇区管理字典
        scene_data["SectorManage"]["sectors"][str(id_)] = {
            "obj": obj,
            "light_objs": [],
            "atmo_id": 0,
            "external_id": 0,
        }
        # 初始化连接管理器
        # self["ConnectManager"] = {"sec_ids": [], "faces": {}, "new_verts": []}

        # 在属性面板显示ID
        # obj[f"AG.Sector ID"] = id_

        # 凹多面体投影切割数据
        self.reset_concave_data()

        # 命名并链接到扇区集合
        name = f"Sector{self.id}"
        obj.rename(name, mode="ALWAYS")
        if not post_copy:
            obj.data.rename(name, mode="ALWAYS")
        elif obj.data.users == 1:
            obj.data.rename(name, mode="ALWAYS")
        coll = L3D_data.ensure_collection(L3D_data.S_COLL)
        if coll not in obj.users_collection:
            # 清除集合
            obj.users_collection[0].objects.unlink(obj)
            # 链接到集合
            data.link2coll(obj, coll)

        # self.flat_light.color = scene_data.defaults.flat_light.color

        # 判断是否为二维球面
        self.is_2d_sphere = ag_utils.is_2d_sphere(obj)
        # 判断是否为凸物体
        self.is_convex = ag_utils.is_convex(obj)

        # 非复制的情况
        if not post_copy:
            # 添加修改器
            modifier = obj.modifiers.new("", type="NODES")
            modifier.node_group = scene_data.sec_node  # type: ignore

            # 添加网格属性
            mesh.attributes.new(name="amagate_connected", type="INT", domain="FACE")
            mesh.attributes.new(name="amagate_flag", type="INT", domain="FACE")
            mesh.attributes.new(name="amagate_tex_id", type="INT", domain="FACE")
            mesh.attributes.new(name="amagate_tex_xpos", type="FLOAT", domain="FACE")
            mesh.attributes.new(name="amagate_tex_ypos", type="FLOAT", domain="FACE")
            mesh.attributes.new(name="amagate_tex_angle", type="FLOAT", domain="FACE")
            mesh.attributes.new(name="amagate_tex_xzoom", type="FLOAT", domain="FACE")
            mesh.attributes.new(name="amagate_tex_yzoom", type="FLOAT", domain="FACE")

            # 设置预设纹理
            for i in ("Floor", "Ceiling", "Wall"):
                def_prop = scene_data.defaults.textures[i]

                prop = self.textures.add()
                prop.target = "Sector"
                prop.name = i
                prop["id"] = def_prop.id
                prop["xpos"] = def_prop.xpos
                prop["ypos"] = def_prop.ypos
                prop["xzoom"] = def_prop.xzoom
                prop["yzoom"] = def_prop.yzoom
                prop["angle"] = def_prop.angle

            for face in mesh.polygons:  # polygons 代表面
                face_index = face.index  # 面的索引
                face_normal = (
                    matrix_world.to_quaternion() @ face.normal
                )  # 面的法线方向（Vector）

                # 设置纹理
                dp = face_normal.dot(Vector((0, 0, 1)))
                if dp > 0.99999:  # 地板
                    face_flag_name = "Floor"
                elif dp < -0.99999:  # 天花板
                    face_flag_name = "Ceiling"
                else:  # 墙壁
                    face_flag_name = "Wall"

                tex_prop = self.textures[face_flag_name]
                tex_id = tex_prop.id
                mesh.attributes["amagate_flag"].data[face_index].value = L3D_data.FACE_FLAG[face_flag_name]  # type: ignore
                mesh.attributes["amagate_tex_id"].data[face_index].value = tex_id  # type: ignore
                mat = None
                tex = L3D_data.get_texture_by_id(tex_id)[1]
                self.set_matslot(L3D_data.ensure_material(tex), [face])

                # 设置纹理参数
                mesh.attributes["amagate_tex_xpos"].data[face_index].value = tex_prop.xpos  # type: ignore
                mesh.attributes["amagate_tex_ypos"].data[face_index].value = tex_prop.ypos  # type: ignore
                mesh.attributes["amagate_tex_angle"].data[face_index].value = tex_prop.angle  # type: ignore
                mesh.attributes["amagate_tex_xzoom"].data[face_index].value = tex_prop.xzoom  # type: ignore
                mesh.attributes["amagate_tex_yzoom"].data[face_index].value = tex_prop.yzoom  # type: ignore

            # 指定大气
            self.atmo_id = scene_data.defaults.atmo_id
            # 指定外部光
            self.external_id = scene_data.defaults.external_id
            # 设置环境光
            self.ambient_color = scene_data.defaults.ambient_color
        # 复制的情况，仅需刷新数据
        else:
            self.atmo_id = self.atmo_id
            self.external_id = self.external_id
            self.ambient_color = self.ambient_color

        obj.amagate_data.is_sector = True


# 物体属性
class ObjectProperty(bpy.types.PropertyGroup):
    SectorData: CollectionProperty(type=SectorProperty)  # type: ignore
    GhostSectorData: CollectionProperty(type=GhostSectorProperty)  # type: ignore
    is_sector: BoolProperty(default=False)  # type: ignore
    is_gho_sector: BoolProperty(default=False)  # type: ignore

    ############################
    def get_sector_data(self) -> SectorProperty:
        if len(self.SectorData) == 0:
            return None  # type: ignore
        return self.SectorData[0]

    def set_sector_data(self):
        if not self.SectorData:
            self.SectorData.add()
            # return self.SectorData[0]

    ############################
    def get_ghost_sector_data(self) -> GhostSectorProperty:
        if len(self.GhostSectorData) == 0:
            return None  # type: ignore
        return self.GhostSectorData[0]

    def set_ghost_sector_data(self):
        if not self.GhostSectorData:
            self.GhostSectorData.add()
            self.is_gho_sector = True


############################


############################
############################
class_tuple = (bpy.types.PropertyGroup, bpy.types.UIList)
classes = [
    cls
    for cls in globals().values()
    if isinstance(cls, type) and any(issubclass(cls, parent) for parent in class_tuple)
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.amagate_data = PointerProperty(type=ObjectProperty, name="Amagate Data")  # type: ignore


def unregister():
    del bpy.types.Object.amagate_data  # type: ignore

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
