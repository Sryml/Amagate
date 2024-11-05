import importlib


from . import operator, panel, data, translations  # 导入插件其他模块


# 注册和取消注册函数
def register(reload=False):
    if reload:
        importlib.reload(operator)
        importlib.reload(panel)
        importlib.reload(data)
        importlib.reload(translations)
        print("Amagate reload")

    operator.register()
    panel.register()
    data.register()
    translations.register()
    print("Amagate register")


def unregister():
    operator.unregister()
    panel.unregister()
    data.unregister()
    translations.unregister()
    print("Amagate unregister")


if __name__ == "__main__":
    register()
    print("Amagate loaded")
