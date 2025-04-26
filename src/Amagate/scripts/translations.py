import os

import bpy
from . import data

translations_dict = {}

# 读取翻译文件
for root, dirs, files in os.walk(os.path.join(data.ADDON_PATH, "locale")):
    for f_name in files:
        if f_name.endswith(".py"):
            lang = f_name[:-3]
            with open(os.path.join(root, f_name), "r") as f:
                translations_dict[lang] = eval(f.read())


def register():
    bpy.app.translations.register(data.PACKAGE, translations_dict)


def unregister():
    bpy.app.translations.unregister(data.PACKAGE)
