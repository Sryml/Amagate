# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations
from typing import Any, TYPE_CHECKING

import importlib
import time
import os

import bpy

if TYPE_CHECKING:
    from .scripts import data, operator, panel, translations

module_list = ("data", "operator", "panel", "translations")
for module in module_list:
    globals()[module] = importlib.import_module(
        f".{module}", package=f"{__package__}.scripts"
    )

loaded = False


# 注册和取消注册函数
def register():
    global loaded
    if loaded:
        import sys

        # for module in ("data", "operator", "panel", "translations"):
        #     del sys.modules[f"{__package__}.{module}"]
        for sub_pack in ("scripts", "service"):
            del sys.modules[f"{__package__}.{sub_pack}"]
            for file in os.listdir(os.path.join(os.path.dirname(__file__), sub_pack)):
                m_name = f"{__package__}.{sub_pack}.{os.path.splitext(file)[0]}"
                if sys.modules.get(m_name):
                    del sys.modules[m_name]
        # from . import data, operator, panel, translations
        for module in module_list:
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
    operator.unregister()
    data.unregister()
    print("Amagate unregister")


if __name__ == "__main__":
    register()
    print("Amagate loaded")
