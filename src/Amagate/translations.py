import bpy

translations_dict = {
    "zh_HANS": {
        (None, "Amagate"): "阿门",
        ("*", "Reload Addon"): "重载插件",
        ("*", "Blade Scene"): "Blade 场景",
        ("*", "Atmosphere"): "大气",
        ("*", "Atmospheres"): "大气数量",
        ("Operator", "Add Atmosphere"): "添加大气",
        ("Operator", "Remove Atmosphere"): "删除大气",
        ("Operator", "Set as default atmosphere"): "设为默认大气",
        ("*", "Duplicate Name"): "名称重复",
        ("*", "Non-Blade scene"): "非 Blade 场景",
        ("*", "Default Properties"): "默认属性",
        ("Operator", "Export Map"): "导出地图",
    },
}


def register():
    bpy.app.translations.register(__package__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__package__)
