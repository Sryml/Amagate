import bpy

translations_dict = {
    "zh_HANS": {
        (None, "Amagate"): "阿门",
        ("*", "Amagate Data"): "Amagate 数据",
        ("*", "Blade Scene"): "Blade 场景",
        ("*", "Non-Blade scene"): "非 Blade 场景",
        ("*", "Non-Sector"): "非扇区",
        ("*", "Hold shift to quickly delete"): "按住 Shift 可快速删除",
        ("*", "Amagate Auto Generated"): "Amagate 自动生成",
        ("*", "Sector Collection"): "扇区集合",
        ("*", "Ghost Sector Collection"): "虚拟扇区集合",
        ("*", "Entity Collection"): "实体集合",
        ("*", "Camera Collection"): "摄像机集合",
        ("*", "Sectors"): "扇区",
        # ("*", "non-uniform"): "不一致的",
        ("Operator", "Don't Save"): "不保存",
        ("Operator", "Cancel"): "取消",
        ("Operator", "Initialize Scene"): "初始化场景",
        ("Operator", "Delete Sector"): "删除扇区",
        ("Property", "Yes"): "是",
        ("Property", "No"): "否",
        # 大气面板
        ("*", "Atmosphere"): "大气",
        ("*", "Atmospheres"): "大气数量",
        ("*", "Select Atmosphere"): "选择大气",
        ("Operator", "Select Atmosphere"): "选择大气",
        ("Operator", "Add Atmosphere"): "添加大气",
        ("Operator", "Remove Atmosphere"): "删除大气",
        ("*", "Cannot remove default atmosphere"): "不能删除默认大气",
        ("*", "Atmosphere is used by sectors"): "该大气被扇区使用中",
        ("Operator", "Set as default atmosphere"): "设为默认大气",
        # 外部光面板
        ("Operator", "Select External Light"): "选择外部光",
        ("Operator", "Set External Light"): "设置外部光",
        ("Operator", "Add External Light"): "添加外部光",
        ("Operator", "Remove External Light"): "删除外部光",
        ("Operator", "Set as default external light"): "设为默认外部光",
        ("*", "Cannot remove default external light"): "不能删除默认外部光",
        ("*", "External light is used by objects"): "该外部光被物体使用中",
        # 默认面板
        ("*", "Default Properties"): "默认属性",
        ("Property", "Floor"): "地板",
        ("Property", "Ceiling"): "天花板",
        ("Property", "Wall"): "墙壁",
        ("*", "Ambient Light"): "环境光",
        ("*", "External Light"): "外部光",
        ("*", "Flat Light"): "平面光",
        # 纹理面板
        ("Operator", "Click to preview texture"): "点击预览纹理",
        ("Operator", "Select Texture"): "选择纹理",
        ("*", "Ignore textures with the same name as the special texture"): "忽略与特殊纹理同名的纹理",
        ("Operator", "Add Texture"): "添加纹理",
        ("*", "Hold shift to enable overlay"): "按住 Shift 启用覆盖",
        ("*", "Override Mode"): "覆盖模式",
        ("Operator", "Remove Texture"): "删除纹理",
        ("*", "Cannot remove default texture"): "不能删除默认纹理",
        ("*", "Cannot remove special texture"): "不能删除特殊纹理",
        ("*", "Texture is used by sectors"): "该纹理被扇区使用中",
        ("Operator", "Set as default texture"): "设为默认纹理",
        ("Operator", "Reload Texture"): "重载纹理",
        ("*", "Hold shift to reload all texture"): "按住 Shift 重载所有纹理",
        ("Operator", "Pack/Unpack Texture"): "打包/解包纹理",
        ("Operator", "Pack Texture"): "打包纹理",
        ("Operator", "Unpack Texture"): "解包纹理",
        ("*", "Hold shift to pack/unpack all textures"): "按住 Shift 打包/解包所有纹理",
        ("*", "Select Operation"): "选择操作",
        ("*", "Pack All"): "全部打包",
        ("*", "Unpack All"): "全部解包",
        ("Operator", "Pack All"): "全部打包",
        ("Operator", "Unpack All"): "全部解包",
        # 扇区面板
        ("*", "Select NULL for sky"): "选择 NULL 作为天空",
        ("*", "Sector"): "扇区",
        ("*", "Selected Sector"): "选中的扇区",
        ("*", "Convex Polyhedron"): "凸多面体",
        ("Operator", "Convert to Sector"): "转换为扇区",
        ("*", "Convert selected objects to sector"): "将所选物体转换为扇区",
        ("*", "No mesh objects selected"): "未选择网格物体",
        ("Operator", "Connect Sectors"): "连接扇区",
        # ("*", "No sectors selected"): "未选择扇区",
        ("*", "Select at least two sectors"): "至少选择两个扇区",
        #
        # 工具面板
        ("Operator", "New Map"): "新建地图",
        ("*", "New Blade Map"): "新建 Blade 地图",
        ("Operator", "Export Map"): "导出地图",
        ("*", "Export Map"): "导出地图",
        ("*", "Please save the file first"): "请先保存文件",
        ("*", "No visible sector found"): "未找到可见扇区",
    },
}


def register():
    bpy.app.translations.register(__package__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__package__)
