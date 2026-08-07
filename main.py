# coding=utf-8
"""源悦TTS 启动入口。

所有程序源码位于 src/ 目录；本入口将其加入导入路径后启动主窗口。
"""

import os
import sys


_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from main_window import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
