# coding=utf-8

import importlib
from concurrent.futures import ThreadPoolExecutor


class BackgroundImporter:
    """窗口显示后后台预热重型模块的导入器。"""

    PRELOAD_SEQUENCE = [
        "pygame",
        "sdl2",
        "sdl2.ext",
        "requests",
        "certifi",
        "openai",
        "PIL",
        "lxml",
        "edge_tts",
        "cv2",
        "fitz",
    ]

    def __init__(self, max_workers=2):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bg-import",
        )
        self._futures = {}
        self._started = False

    def start(self):
        """开始后台预热；重复调用时保持幂等。"""
        if self._started:
            return

        self._started = True
        for module_name in self.PRELOAD_SEQUENCE:
            self._futures[module_name] = self._executor.submit(
                self._safe_import, module_name
            )

    @staticmethod
    def _safe_import(module_name):
        try:
            return importlib.import_module(module_name)
        except Exception:
            return None

    def is_ready(self, module_name):
        future = self._futures.get(module_name)
        return future is not None and future.done()

    def wait_for(self, module_name, timeout=10.0):
        future = self._futures.get(module_name)
        if future is not None:
            return future.result(timeout=timeout)

        try:
            return importlib.import_module(module_name)
        except Exception:
            return None

    def shutdown(self):
        self._executor.shutdown(wait=False)
