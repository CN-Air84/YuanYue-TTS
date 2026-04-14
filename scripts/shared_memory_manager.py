#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享内存管理器 - 用于跨页面信号广播
基于内存映射文件实现进程间通信
"""

import json
import mmap
import os
import sys
import threading
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from debug_logger import debug_logger, LogLevel

try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))


class SharedMemoryManager(QObject):
    """共享内存管理器。"""

    settings_changed = pyqtSignal(str, dict)
    font_changed = pyqtSignal(dict)
    theme_changed = pyqtSignal(dict)
    window_size_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "创建 SharedMemoryManager（惰性模式）", fold_code="SHARED_INIT")
        self.memory_file = None
        self.memory_map = None
        self.memory_size = 65536
        self.memory_lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._initialized = False
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._check_memory_updates)
        self.update_interval = 100
        self.last_update_time = 0
        self.memory_file_path = None
        self.fallback_file = None

    def _ensure_initialized(self):
        """在首次真正使用时才初始化共享内存后端。"""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return
            self._init_shared_memory()

    def _init_shared_memory(self):
        """初始化共享内存。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "首次使用，开始初始化共享内存映射", fold_code="SHARED_INIT")
        try:
            cache_dir = os.path.join(get_app_base_path(), 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            self.memory_file_path = os.path.join(cache_dir, 'YuanyueCaller.dat')

            with open(self.memory_file_path, 'wb') as f:
                f.write(b'\x00' * self.memory_size)

            self.memory_file = open(self.memory_file_path, 'r+b')
            self.memory_map = mmap.mmap(self.memory_file.fileno(), self.memory_size)
            self._clear_memory()

            if not self.update_timer.isActive():
                self.update_timer.start(self.update_interval)

            self._initialized = True
            debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"共享内存初始化成功: {self.memory_file_path}", fold_code="SHARED_INIT")
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"共享内存初始化失败: {str(e)}", fold_code="SHARED_INIT")
            self._fallback_to_file_based_communication()

    def _clear_memory(self):
        """清空内存区域。"""
        if self.memory_map is None:
            return
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "正在清空共享内存区域", fold_code="SHARED_INIT")
        self.memory_map.seek(0)
        self.memory_map.write(b'\x00' * self.memory_size)

    def _fallback_to_file_based_communication(self):
        """降级到基于文件的通信。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.WARNING, "共享内存不可用，降级到基于文件的通信方案", fold_code="SHARED_INIT")
        cache_dir = os.path.join(get_app_base_path(), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        self.fallback_file = os.path.join(cache_dir, 'YuanyueFallback.json')
        if not self.update_timer.isActive():
            self.update_timer.start(self.update_interval * 2)
        self._initialized = True

    def broadcast_settings_change(self, page_name, settings_data):
        """广播设置更改。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播设置更改: 来自页面 [{page_name}]", fold_code="SHARED_MSG")
        try:
            self._ensure_initialized()
            message = {
                'type': 'settings_change',
                'page': page_name,
                'data': settings_data,
                'timestamp': time.time(),
            }
            self._write_message(message)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播设置更改失败: {str(e)}", fold_code="SHARED_MSG")

    def broadcast_font_change(self, font_data):
        """广播字体更改。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播字体更改: {font_data.get('font_family', 'unknown')}", fold_code="SHARED_MSG")
        try:
            self._ensure_initialized()
            message = {
                'type': 'font_change',
                'data': font_data,
                'timestamp': time.time(),
            }
            self._write_message(message)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播字体更改失败: {str(e)}", fold_code="SHARED_MSG")

    def broadcast_theme_change(self, theme_data):
        """广播主题更改。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播主题更改: {theme_data.get('theme_name', 'unknown')}", fold_code="SHARED_MSG")
        try:
            self._ensure_initialized()
            message = {
                'type': 'theme_change',
                'data': theme_data,
                'timestamp': time.time(),
            }
            self._write_message(message)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播主题更改失败: {str(e)}", fold_code="SHARED_MSG")

    def broadcast_window_size_change(self, width, height):
        """广播窗口尺寸更改。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播窗口尺寸更改: {width}x{height}", fold_code="SHARED_MSG")
        try:
            self._ensure_initialized()
            message = {
                'type': 'window_size_change',
                'data': {'width': width, 'height': height},
                'timestamp': time.time(),
            }
            self._write_message(message)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播窗口尺寸更改失败: {str(e)}", fold_code="SHARED_MSG")

    def _write_message(self, message):
        """写入消息到共享内存或降级文件。"""
        with self.memory_lock:
            try:
                if self.memory_map is not None:
                    message_json = json.dumps(message, ensure_ascii=False)
                    message_bytes = message_json.encode('utf-8')

                    if len(message_bytes) > self.memory_size - 8:
                        debug_logger.output("shared_memory_manager.py", LogLevel.WARNING, f"消息太大 ({len(message_bytes)} bytes)，无法写入共享内存", fold_code="SHARED_MSG")
                        return

                    debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在向共享内存写入消息: {message['type']}", fold_code="SHARED_MSG")
                    self.memory_map.seek(0)
                    self.memory_map.write(len(message_bytes).to_bytes(4, 'big'))
                    self.memory_map.write(b'\x01')
                    self.memory_map.write(message_bytes)

                    remaining = self.memory_size - 5 - len(message_bytes)
                    if remaining > 0:
                        self.memory_map.write(b'\x00' * remaining)
                else:
                    self._write_fallback_message(message)
            except Exception as e:
                debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"写入共享内存失败: {str(e)}", fold_code="SHARED_MSG")
                self._write_fallback_message(message)

    def _write_fallback_message(self, message):
        """写入降级消息到文件。"""
        if self.fallback_file is None:
            self._fallback_to_file_based_communication()

        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在写入降级消息文件: {message['type']}", fold_code="SHARED_MSG")
        try:
            with open(self.fallback_file, 'w', encoding='utf-8') as f:
                json.dump(message, f, ensure_ascii=False)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"写入降级文件失败: {str(e)}", fold_code="SHARED_MSG")

    def _check_memory_updates(self):
        """检查内存更新。"""
        if not self._initialized:
            return

        try:
            if self.memory_map is not None:
                self._check_shared_memory()
            else:
                self._check_fallback_file()
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"检查更新失败: {str(e)}", fold_code="SHARED_MSG")

    def _check_shared_memory(self):
        """检查共享内存更新。"""
        with self.memory_lock:
            try:
                self.memory_map.seek(0)
                length_bytes = self.memory_map.read(4)
                if len(length_bytes) < 4:
                    return

                message_length = int.from_bytes(length_bytes, 'big')
                if message_length == 0 or message_length > self.memory_size - 8:
                    return

                type_byte = self.memory_map.read(1)
                if type_byte != b'\x01':
                    return

                message_bytes = self.memory_map.read(message_length)
                if len(message_bytes) != message_length:
                    return

                message_json = message_bytes.decode('utf-8')
                message = json.loads(message_json)

                if message.get('timestamp', 0) <= self.last_update_time:
                    return

                self.last_update_time = message['timestamp']
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"检测到新的共享内存消息: {message['type']}", fold_code="SHARED_MSG")
                self._process_message(message)

                self.memory_map.seek(4)
                self.memory_map.write(b'\x00')
            except Exception as e:
                debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"检查共享内存失败: {str(e)}", fold_code="SHARED_MSG")

    def _check_fallback_file(self):
        """检查降级文件更新。"""
        if self.fallback_file is None:
            return

        try:
            if os.path.exists(self.fallback_file):
                with open(self.fallback_file, 'r', encoding='utf-8') as f:
                    message = json.load(f)

                if message.get('timestamp', 0) > self.last_update_time:
                    self.last_update_time = message['timestamp']
                    debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"检测到新的降级文件消息: {message['type']}", fold_code="SHARED_MSG")
                    self._process_message(message)
                    os.remove(self.fallback_file)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"检查降级文件失败: {str(e)}", fold_code="SHARED_MSG")

    def _process_message(self, message):
        """处理接收到的消息。"""
        try:
            msg_type = message.get('type')
            data = message.get('data', {})

            if msg_type == 'settings_change':
                page = message.get('page', 'unknown')
                self.settings_changed.emit(page, data)
            elif msg_type == 'font_change':
                self.font_changed.emit(data)
            elif msg_type == 'theme_change':
                self.theme_changed.emit(data)
            elif msg_type == 'window_size_change':
                width = data.get('width', 0)
                height = data.get('height', 0)
                if width > 0 and height > 0:
                    self.window_size_changed.emit(width, height)

            debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"处理消息: {msg_type}", fold_code="SHARED_MSG")
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"处理消息失败: {str(e)}", fold_code="SHARED_MSG")

    def cleanup(self):
        """清理资源。"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "正在执行资源清理", fold_code="SHARED_CLEAN")
        try:
            if self.update_timer.isActive():
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "停止更新定时器", fold_code="SHARED_CLEAN")
                self.update_timer.stop()

            if self.memory_map is not None:
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "关闭内存映射", fold_code="SHARED_CLEAN")
                self.memory_map.close()
                self.memory_map = None

            if self.memory_file is not None:
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "关闭内存文件句柄", fold_code="SHARED_CLEAN")
                self.memory_file.close()
                self.memory_file = None

            if self.memory_file_path and os.path.exists(self.memory_file_path):
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"删除临时内存文件: {self.memory_file_path}", fold_code="SHARED_CLEAN")
                os.remove(self.memory_file_path)

            if self.fallback_file and os.path.exists(self.fallback_file):
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"删除降级通信文件: {self.fallback_file}", fold_code="SHARED_CLEAN")
                os.remove(self.fallback_file)

            self._initialized = False
            debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "资源清理完成", fold_code="SHARED_CLEAN")
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"清理资源过程中出现错误: {str(e)}", fold_code="SHARED_CLEAN")


_shared_memory_manager = None


def get_shared_memory_manager():
    """获取全局共享内存管理器实例。"""
    global _shared_memory_manager
    if _shared_memory_manager is None:
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "创建全局 SharedMemoryManager 实例", fold_code="SHARED_INIT")
        _shared_memory_manager = SharedMemoryManager()
    return _shared_memory_manager


def cleanup_shared_memory():
    """清理全局共享内存管理器。"""
    global _shared_memory_manager
    if _shared_memory_manager:
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "触发全局 SharedMemoryManager 清理", fold_code="SHARED_CLEAN")
        _shared_memory_manager.cleanup()
        _shared_memory_manager = None
