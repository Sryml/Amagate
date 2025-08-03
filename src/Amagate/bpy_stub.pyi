from typing import Any, overload, TypeVar, Union

from .scripts import L3D_data, sector_data
from .scripts import data as ag_data

import bpy
from bpy import typing as bpy_typing
import collections.abc
from bpy import *  # type: ignore

class __Image(bpy.types.Image):
    amagate_data: ag_data.ImageProperty

class __Object(bpy.types.Object):
    amagate_data: ag_data.ObjectProperty

class __Scene(bpy.types.Scene):
    amagate_data: ag_data.SceneProperty

class __WindowManager(bpy.types.WindowManager):
    amagate_data: ag_data.WindowManagerProperty

class __Context(bpy.types.Context):
    scene: __Scene
    selected_objects: list[__Object]
    objects_in_mode: list[__Object]
    active_object: __Object
    window_manager: __WindowManager

class __Collection(bpy.types.Collection):
    objects: list[__Object]
    all_objects: list[__Object]
    collection_objects: list[__Object]

class __BlendDataImages(bpy.types.BlendDataImages):
    @overload
    def __getitem__(self, key: str | int) -> __Image: ...
    @overload
    def __getitem__(self, key: slice) -> list[__Image]: ...
    def __getitem__(self, key: str | int | slice) -> __Image | list[__Image]: ...
    def __iter__(self) -> collections.abc.Iterator[__Image]: ...

class __BlendDataObjects(bpy.types.BlendDataObjects):
    @overload
    def __getitem__(self, key: str | int) -> __Object: ...
    @overload
    def __getitem__(self, key: slice) -> list[__Object]: ...
    def __getitem__(self, key: str | int | slice) -> __Object | list[__Object]: ...
    def __iter__(self) -> collections.abc.Iterator[__Object]: ...

class __BlendDataScenes(bpy.types.BlendDataScenes):
    @overload
    def __getitem__(self, key: str | int) -> __Scene: ...
    @overload
    def __getitem__(self, key: slice) -> list[__Scene]: ...
    def __getitem__(self, key: str | int | slice) -> __Scene | list[__Scene]: ...
    def __iter__(self) -> collections.abc.Iterator[__Scene]: ...

class __BlendDataCollections(bpy.types.BlendDataCollections):
    @overload
    def __getitem__(self, key: str | int) -> __Collection: ...
    @overload
    def __getitem__(self, key: slice) -> list[__Collection]: ...
    def __getitem__(
        self, key: str | int | slice
    ) -> __Collection | list[__Collection]: ...
    def __iter__(self) -> collections.abc.Iterator[__Collection]: ...

class __BlendData(bpy.types.BlendData):
    images: __BlendDataImages
    objects: __BlendDataObjects
    scenes: __BlendDataScenes
    collections: __BlendDataCollections

context: __Context
data: __BlendData
