import importlib


from . import operator, panel, data, translations  # 导入插件其他模块


# 注册和取消注册函数
def register(reload=False):
    if reload:
        importlib.reload(data)
        importlib.reload(operator)
        importlib.reload(panel)
        importlib.reload(translations)
        print("Amagate reload")

    data.register()
    operator.register()
    panel.register()
    translations.register()
    print("Amagate register")


def unregister():
    translations.unregister()
    panel.unregister()
    operator.unregister()
    data.unregister()
    print("Amagate unregister")


if __name__ == "__main__":
    register()
    print("Amagate loaded")
