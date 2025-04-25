import importlib
import time
import os

import bpy

from .scripts import data, operator, operator_sector, panel, translations


loaded = False


# 注册和取消注册函数
def register():
    global loaded
    if loaded:
        import sys

        # for module in ("data", "operator", "panel", "translations"):
        #     del sys.modules[f"{__package__}.{module}"]
        del sys.modules[f"{__package__}.scripts"]
        for file in os.listdir(os.path.join(os.path.dirname(__file__), "scripts")):
            m_name = f"{__package__}.scripts.{os.path.splitext(file)[0]}"
            if sys.modules.get(m_name):
                del sys.modules[m_name]
        # from . import data, operator, panel, translations
        for module in ("data", "operator", "operator_sector", "panel", "translations"):
            globals()[module] = importlib.import_module(
                f".{module}", package=f"{__package__}.scripts"
            )
        # importlib.reload(data)
        # importlib.reload(operator)
        # importlib.reload(panel)
        # importlib.reload(translations)
        print("Amagate reload")

    data.register()
    operator.register()
    operator_sector.register()
    panel.register()
    translations.register()
    data.register_shortcuts()

    # 检查包是否已安装
    try:
        for m in data.PY_PACKAGES_REQUIRED:
            importlib.import_module(m)

        data.PY_PACKAGES_INSTALLED = True
    except ImportError:
        from .scripts import ag_utils

        # 如果未安装，显示N面板展示安装进度
        bpy.app.timers.register(
            data.show_region_ui,  # type: ignore
            first_interval=0.1,
        )
        # 安装包
        ag_utils.install_packages()

    loaded = True
    print("Amagate register")


def unregister():
    data.unregister_shortcuts()
    translations.unregister()
    panel.unregister()
    operator_sector.unregister()
    operator.unregister()
    data.unregister()
    print("Amagate unregister")


if __name__ == "__main__":
    register()
    print("Amagate loaded")
