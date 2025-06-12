import os

import bpy

# 获取插件包名
PACKAGE = ".".join(__package__.split(".")[:-1])
# 获取插件根目录路径
ADDON_PATH = os.path.abspath(f"{os.path.dirname(__file__)}/..")

translations_dict = {}

# 读取翻译文件
for root, dirs, files in os.walk(os.path.join(ADDON_PATH, "locale")):
    for f_name in files:
        if f_name.endswith(".py"):
            lang = f_name[:-3]
            with open(os.path.join(root, f_name), "r") as f:
                translations_dict[lang] = eval(f.read())


def register():
    bpy.app.translations.register(PACKAGE, translations_dict)


def unregister():
    bpy.app.translations.unregister(PACKAGE)
