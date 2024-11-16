import bpy

translations_dict = {
    "zh_HANS": {
        (None, "Amagate"): "阿门",
        ("*", "Blade Scene"): "Blade 场景",

        ("*", "Atmosphere"): "大气",
        ("*", "Atmospheres"): "大气数量",
        ("*", "Select Atmosphere"): "选择大气",
        ("Operator", "Add Atmosphere"): "添加大气",
        ("Operator", "Remove Atmosphere"): "删除大气",
        ("*", "Hold shift to quickly delete"): "按住 Shift 可快速删除",
        ("Operator", "Set as default atmosphere"): "设为默认大气",

        ("Operator", "Add Texture"): "添加纹理",
        ("*", "Hold shift to enable overlay"): "按住 Shift 启用覆盖",
        ("*", "Override Mode"): "覆盖模式",
        ("Operator", "Remove Texture"): "删除纹理",
        ("Operator", "Reload Texture"): "重载纹理",
        ("*", "Hold shift to reload all texture"): "按住 Shift 重载所有纹理",
        ("Operator", "Package Texture"): "打包纹理",
        ("*", "Hold shift to pack all textures"): "按住 Shift 打包所有纹理",
        # ("*", "Duplicate Name"): "名称重复",
        ("*", "Non-Blade scene"): "非 Blade 场景",
        ("*", "Default Properties"): "默认属性",
        ("Operator", "Export Map"): "导出地图",
    },
}


def register():
    bpy.app.translations.register(__package__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__package__)
