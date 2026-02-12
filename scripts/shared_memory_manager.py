#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享内存管理器 - 用于跨页面信号广播
基于内存映射文件实现进程间通信
"""

import mmap
import json
import time
import threading
import sys
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import os
import tempfile
from debug_logger import debug_logger, LogLevel

try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))


class SharedMemoryManager(QObject):
    """共享内存管理器"""
    
    # 定义信号
    settings_changed = pyqtSignal(str, dict)  # 设置更改信号：页面名称, 更改的数据
    font_changed = pyqtSignal(dict)  # 字体更改信号
    theme_changed = pyqtSignal(dict)  # 主题更改信号
    window_size_changed = pyqtSignal(int, int)  # 窗口尺寸更改信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "正在初始化 SharedMemoryManager", fold_code="SHARED_INIT")
        self.memory_file = None
        self.memory_map = None
        self.memory_size = 65536  # 64KB 应该足够
        self.memory_lock = threading.Lock()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._check_memory_updates)
        self.update_interval = 100  # 100ms检查一次
        self.last_update_time = 0
        self.memory_file_path = None
        
        self._init_shared_memory()
        
    def _init_shared_memory(self):
        """初始化共享内存"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "正在尝试初始化共享内存映射", fold_code="SHARED_INIT")
        try:
            # 创建临时文件用于共享内存 - 使用绝对路径
            cache_dir = os.path.join(get_app_base_path(), 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            self.memory_file_path = os.path.join(cache_dir, 'YuanyueCaller.dat')
            
            # 创建或打开文件
            with open(self.memory_file_path, 'wb') as f:
                f.write(b'\x00' * self.memory_size)
            
            # 打开文件进行内存映射
            self.memory_file = open(self.memory_file_path, 'r+b')
            self.memory_map = mmap.mmap(self.memory_file.fileno(), self.memory_size)
            
            # 初始化内存区域
            self._clear_memory()
            
            # 启动定时器
            self.update_timer.start(self.update_interval)
            
            debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"共享内存初始化成功: {self.memory_file_path}", fold_code="SHARED_INIT")
            
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"共享内存初始化失败: {str(e)}", fold_code="SHARED_INIT")
            self._fallback_to_file_based_communication()
    
    def _clear_memory(self):
        """清空内存区域"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "正在清空共享内存区域", fold_code="SHARED_INIT")
        if self.memory_map:
            self.memory_map.seek(0)
            self.memory_map.write(b'\x00' * self.memory_size)
    
    def _fallback_to_file_based_communication(self):
        """降级到基于文件的通信"""
        debug_logger.output("shared_memory_manager.py", LogLevel.WARNING, "共享内存不可用，降级到基于文件的通信方案", fold_code="SHARED_INIT")
        cache_dir = os.path.join(get_app_base_path(), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        self.fallback_file = os.path.join(cache_dir, 'YuanyueFallback.json')
        self.update_timer.start(self.update_interval * 2)  # 降低检查频率
    
    def broadcast_settings_change(self, page_name, settings_data):
        """广播设置更改"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播设置更改: 来自页面 [{page_name}]", fold_code="SHARED_MSG")
        try:
            message = {
                'type': 'settings_change',
                'page': page_name,
                'data': settings_data,
                'timestamp': time.time()
            }
            self._write_message(message)
            
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播设置更改失败: {str(e)}", fold_code="SHARED_MSG")
    
    def broadcast_font_change(self, font_data):
        """广播字体更改"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播字体更改: {font_data.get('font_family', 'unknown')}", fold_code="SHARED_MSG")
        try:
            message = {
                'type': 'font_change',
                'data': font_data,
                'timestamp': time.time()
            }
            self._write_message(message)
            
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播字体更改失败: {str(e)}", fold_code="SHARED_MSG")
    
    def broadcast_theme_change(self, theme_data):
        """广播主题更改"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播主题更改: {theme_data.get('theme_name', 'unknown')}", fold_code="SHARED_MSG")
        try:
            message = {
                'type': 'theme_change',
                'data': theme_data,
                'timestamp': time.time()
            }
            self._write_message(message)
            
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播主题更改失败: {str(e)}", fold_code="SHARED_MSG")
    
    def broadcast_window_size_change(self, width, height):
        """广播窗口尺寸更改"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在广播窗口尺寸更改: {width}x{height}", fold_code="SHARED_MSG")
        try:
            message = {
                'type': 'window_size_change',
                'data': {'width': width, 'height': height},
                'timestamp': time.time()
            }
            self._write_message(message)
            
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"广播窗口尺寸更改失败: {str(e)}", fold_code="SHARED_MSG")
    
    def _write_message(self, message):
        """写入消息到共享内存"""
        with self.memory_lock:
            try:
                if self.memory_map:
                    # 序列化消息
                    message_json = json.dumps(message, ensure_ascii=False)
                    message_bytes = message_json.encode('utf-8')
                    
                    # 检查消息大小
                    if len(message_bytes) > self.memory_size - 8:  # 留8字节用于长度和状态
                        debug_logger.output("shared_memory_manager.py", LogLevel.WARNING, f"消息太大 ({len(message_bytes)} bytes)，无法写入共享内存", fold_code="SHARED_MSG")
                        return
                    
                    debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在向共享内存写入消息: {message['type']}", fold_code="SHARED_MSG")
                    # 清空内存
                    self.memory_map.seek(0)
                    
                    # 写入消息长度（4字节）
                    self.memory_map.write(len(message_bytes).to_bytes(4, 'big'))
                    
                    # 写入消息类型标识（1字节）
                    self.memory_map.write(b'\x01')  # 01表示有新消息
                    
                    # 写入消息数据
                    self.memory_map.write(message_bytes)
                    
                    # 填充剩余空间
                    remaining = self.memory_size - 5 - len(message_bytes)
                    if remaining > 0:
                        self.memory_map.write(b'\x00' * remaining)
                    
                else:
                    # 降级方案：写入文件
                    self._write_fallback_message(message)
                    
            except Exception as e:
                debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"写入共享内存失败: {str(e)}", fold_code="SHARED_MSG")
                self._write_fallback_message(message)
    
    def _write_fallback_message(self, message):
        """写入降级消息到文件"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"正在写入降级消息文件: {message['type']}", fold_code="SHARED_MSG")
        try:
            with open(self.fallback_file, 'w', encoding='utf-8') as f:
                json.dump(message, f, ensure_ascii=False)
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"写入降级文件失败: {str(e)}", fold_code="SHARED_MSG")
    
    def _check_memory_updates(self):
        """检查内存更新"""
        try:
            if self.memory_map:
                self._check_shared_memory()
            else:
                self._check_fallback_file()
                
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"检查更新失败: {str(e)}", fold_code="SHARED_MSG")
    
    def _check_shared_memory(self):
        """检查共享内存更新"""
        with self.memory_lock:
            try:
                # 移动到内存开始位置
                self.memory_map.seek(0)
                
                # 读取消息长度
                length_bytes = self.memory_map.read(4)
                if len(length_bytes) < 4:
                    return
                
                message_length = int.from_bytes(length_bytes, 'big')
                if message_length == 0 or message_length > self.memory_size - 8:
                    return
                
                # 读取消息类型标识
                type_byte = self.memory_map.read(1)
                if type_byte != b'\x01':  # 不是新消息标识
                    return
                
                # 读取消息数据
                message_bytes = self.memory_map.read(message_length)
                if len(message_bytes) != message_length:
                    return
                
                # 解析消息
                message_json = message_bytes.decode('utf-8')
                message = json.loads(message_json)
                
                # 检查时间戳，避免重复处理
                if message.get('timestamp', 0) <= self.last_update_time:
                    return
                
                self.last_update_time = message['timestamp']
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"检测到新的共享内存消息: {message['type']}", fold_code="SHARED_MSG")
                
                # 处理消息
                self._process_message(message)
                
                # 清空内存，标记消息已处理
                self.memory_map.seek(4)
                self.memory_map.write(b'\x00')  # 清除消息标识
                
            except Exception as e:
                debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"检查共享内存失败: {str(e)}", fold_code="SHARED_MSG")
    
    def _check_fallback_file(self):
        """检查降级文件更新"""
        try:
            if os.path.exists(self.fallback_file):
                with open(self.fallback_file, 'r', encoding='utf-8') as f:
                    message = json.load(f)
                
                # 检查时间戳
                if message.get('timestamp', 0) > self.last_update_time:
                    self.last_update_time = message['timestamp']
                    debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"检测到新的降级文件消息: {message['type']}", fold_code="SHARED_MSG")
                    self._process_message(message)
                    
                    # 删除已处理的消息文件
                    os.remove(self.fallback_file)
                    
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"检查降级文件失败: {str(e)}", fold_code="SHARED_MSG")
    
    def _process_message(self, message):
        """处理接收到的消息"""
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
        """清理资源"""
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "正在执行资源清理", fold_code="SHARED_CLEAN")
        try:
            if self.update_timer:
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "停止更新定时器", fold_code="SHARED_CLEAN")
                self.update_timer.stop()
            
            if self.memory_map:
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "关闭内存映射", fold_code="SHARED_CLEAN")
                self.memory_map.close()
            
            if self.memory_file:
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "关闭内存文件句柄", fold_code="SHARED_CLEAN")
                self.memory_file.close()
            
            # 删除临时文件
            if self.memory_file_path and os.path.exists(self.memory_file_path):
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"删除临时内存文件: {self.memory_file_path}", fold_code="SHARED_CLEAN")
                os.remove(self.memory_file_path)
                
            if hasattr(self, 'fallback_file') and os.path.exists(self.fallback_file):
                debug_logger.output("shared_memory_manager.py", LogLevel.INFO, f"删除降级通信文件: {self.fallback_file}", fold_code="SHARED_CLEAN")
                os.remove(self.fallback_file)
            
            debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "资源清理完成", fold_code="SHARED_CLEAN")
                
        except Exception as e:
            debug_logger.output("shared_memory_manager.py", LogLevel.ERROR, f"清理资源过程中出现错误: {str(e)}", fold_code="SHARED_CLEAN")


# 全局共享内存管理器实例
_shared_memory_manager = None

def get_shared_memory_manager():
    """获取全局共享内存管理器实例"""
    global _shared_memory_manager
    if _shared_memory_manager is None:
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "创建全局 SharedMemoryManager 实例", fold_code="SHARED_INIT")
        _shared_memory_manager = SharedMemoryManager()
    return _shared_memory_manager


def cleanup_shared_memory():
    """清理全局共享内存管理器"""
    global _shared_memory_manager
    if _shared_memory_manager:
        debug_logger.output("shared_memory_manager.py", LogLevel.INFO, "触发全局 SharedMemoryManager 清理", fold_code="SHARED_CLEAN")
        _shared_memory_manager.cleanup()
        _shared_memory_manager = None