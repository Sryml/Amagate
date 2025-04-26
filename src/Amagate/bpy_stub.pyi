from .scripts import data as ag_data

import bpy
from bpy import *  # type: ignore

class __Image(bpy.types.Image):
    amagate_data: ag_data.ImageProperty

class __Object(bpy.types.Object):
    amagate_data: ag_data.ObjectProperty

class __Scene(bpy.types.Scene):
    amagate_data: ag_data.SceneProperty

class __Context(bpy.types.Context):
    scene: __Scene
    selected_objects: list[__Object]
    active_object: __Object

class __BlendDataImages(bpy.types.BlendDataImages):
    def __getitem__(self, key: str | int | slice) -> __Image | list[__Image]: ...

class __BlendDataObjects(bpy.types.BlendDataObjects):
    def __getitem__(self, key: str | int | slice) -> __Object | list[__Object]: ...

class __BlendDataScenes(bpy.types.BlendDataScenes):
    def __getitem__(self, key: str | int | slice) -> __Scene | list[__Scene]: ...

class __BlendData(bpy.types.BlendData):
    images: __BlendDataImages
    objects: __BlendDataObjects
    scenes: __BlendDataScenes

context: __Context
data: __BlendData
