# coding=utf-8
"""PyInstaller runtime hook：在解释器启动后后台预热常用重型模块。"""

import importlib
import os
import threading

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

PRELOAD_SEQUENCE = [
    'pygame',
    'sdl2',
    'sdl2.ext',
    'requests',
    'PIL',
    'openai',
    'lxml',
]


def _safe_import(module_name: str):
    try:
        importlib.import_module(module_name)
    except Exception:
        pass


def _preload_modules():
    for module_name in PRELOAD_SEQUENCE:
        _safe_import(module_name)


threading.Thread(
    target=_preload_modules,
    name='yuanyue-runtime-preload',
    daemon=True,
).start()
