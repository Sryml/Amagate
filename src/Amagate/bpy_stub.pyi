from .scripts import data as ag_data

import bpy
from bpy import *

class __Image(bpy.types.Image):
    amagate_data: ag_data.ImageProperty

class __Object(bpy.types.Object):
    amagate_data: ag_data.ObjectProperty

class __Scene(bpy.types.Scene):
    amagate_data: ag_data.SceneProperty

class __Context(bpy.types.Context):
    scene: __Scene

context: __Context
