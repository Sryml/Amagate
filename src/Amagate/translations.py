import bpy

translations_dict = {
    "zh_HANS": {
        (None, "Amagate"): "阿门",
        ("*", "Blade Scene"): "Blade 场景",
        # ("*", "Duplicate Name"): "名称重复",
        ("*", "Non-Blade scene"): "非 Blade 场景",
        ("*", "Non-Sector"): "非扇区",
        ("*", "Hold shift to quickly delete"): "按住 Shift 可快速删除",
        # 大气面板
        ("*", "Atmosphere"): "大气",
        ("*", "Atmospheres"): "大气数量",
        ("*", "Select Atmosphere"): "选择大气",
        ("Operator", "Add Atmosphere"): "添加大气",
        ("Operator", "Remove Atmosphere"): "删除大气",
        ("*", "Cannot remove default atmosphere"): "不能删除默认大气",
        ("*", "Atmosphere is used by sectors"): "该大气被扇区使用中",
        ("Operator", "Set as default atmosphere"): "设为默认大气",
        # 默认面板
        ("*", "Default Properties"): "默认属性",
        ("Property", "Floor"): "地板",
        ("Property", "Ceiling"): "天花板",
        ("Property", "Wall"): "墙壁",
        # 纹理面板
        ("Operator", "Add Texture"): "添加纹理",
        ("*", "Hold shift to enable overlay"): "按住 Shift 启用覆盖",
        ("*", "Override Mode"): "覆盖模式",
        ("Operator", "Remove Texture"): "删除纹理",
        ("*", "Cannot remove default texture"): "不能删除默认纹理",
        ("*", "Cannot remove special texture"): "不能删除特殊纹理",
        ("*", "Texture is used by sectors"): "该纹理被扇区使用中",
        ("Operator", "Reload Texture"): "重载纹理",
        ("*", "Hold shift to reload all texture"): "按住 Shift 重载所有纹理",
        ("Operator", "Pack/Unpack Texture"): "打包/解包纹理",
        ("*", "Hold shift to pack/unpack all textures"): "按住 Shift 打包/解包所有纹理",
        ("*", "Select Operation"): "选择操作",
        ("*", "Pack All"): "全部打包",
        ("*", "Unpack All"): "全部解包",
        # 扇区面板
        ("*", "Select NULL for sky"): "选择 NULL 作为天空",
        #
        ("Operator", "Export Map"): "导出地图",
    },
}


def register():
    bpy.app.translations.register(__package__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__package__)
