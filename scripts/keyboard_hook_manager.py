# coding=utf-8
"""
底层键盘钩子管理器
直接捕获键盘按键的物理按下/抬起事件，不依赖窗口焦点
"""
import sys
import platform
from typing import Optional, Callable, Dict
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from debug_logger import debug_logger, LogLevel

# 尝试导入 pynput 库
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    debug_logger.output("keyboard_hook_manager.py", LogLevel.WARNING, 
                       "pynput 库未安装，底层键盘监听功能不可用。请运行: pip install pynput", 
                       fold_code="KEYBOARD_HOOK")


class KeyboardHookManager(QObject):
    """
    底层键盘钩子管理器
    使用系统级钩子捕获键盘事件，不受窗口焦点影响
    """
    # 按键按下信号 (key_code)
    key_pressed = pyqtSignal(int)
    # 按键抬起信号 (key_code)
    key_released = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.listener: Optional[keyboard.Listener] = None
        self.is_running = False
        self.key_mapping: Dict[keyboard.Key, int] = {}
        self._init_key_mapping()
        
    def _init_key_mapping(self):
        """初始化 pynput 按键到 Qt 按键码的映射"""
        from PyQt5.QtCore import Qt
        
        # 特殊键映射
        self.key_mapping = {
            keyboard.Key.space: Qt.Key_Space,
            keyboard.Key.left: Qt.Key_Left,
            keyboard.Key.right: Qt.Key_Right,
            keyboard.Key.up: Qt.Key_Up,
            keyboard.Key.down: Qt.Key_Down,
            keyboard.Key.ctrl_l: Qt.Key_Control,
            keyboard.Key.ctrl_r: Qt.Key_Control,
            keyboard.Key.shift_l: Qt.Key_Shift,
            keyboard.Key.shift_r: Qt.Key_Shift,
            keyboard.Key.alt_l: Qt.Key_Alt,
            keyboard.Key.alt_r: Qt.Key_Alt,
            keyboard.Key.enter: Qt.Key_Return,
            keyboard.Key.esc: Qt.Key_Escape,
            keyboard.Key.tab: Qt.Key_Tab,
            keyboard.Key.backspace: Qt.Key_Backspace,
            keyboard.Key.delete: Qt.Key_Delete,
            keyboard.Key.home: Qt.Key_Home,
            keyboard.Key.end: Qt.Key_End,
            keyboard.Key.page_up: Qt.Key_PageUp,
            keyboard.Key.page_down: Qt.Key_PageDown,
        }
        
        # F1-F12 键
        for i in range(1, 13):
            f_key = getattr(keyboard.Key, f'f{i}', None)
            if f_key:
                self.key_mapping[f_key] = getattr(Qt, f'Key_F{i}')
    
    def _convert_key_to_qt(self, key) -> Optional[int]:
        """将 pynput 按键转换为 Qt 按键码"""
        from PyQt5.QtCore import Qt
        
        # 检查是否是特殊键
        if isinstance(key, keyboard.Key):
            return self.key_mapping.get(key)
        
        # 字符键
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                # 转换为大写字母对应的 Qt 键码
                char = key.char.upper()
                if len(char) == 1:
                    # A-Z
                    if 'A' <= char <= 'Z':
                        return getattr(Qt, f'Key_{char}', None)
                    # 0-9
                    elif '0' <= char <= '9':
                        return getattr(Qt, f'Key_{char}', None)
            # 使用 vk 码作为备选
            elif key.vk:
                # Windows 虚拟键码可以直接映射
                if platform.system() == 'Windows':
                    # A-Z: VK 65-90
                    if 65 <= key.vk <= 90:
                        return getattr(Qt, f'Key_{chr(key.vk)}', None)
                    # 0-9: VK 48-57
                    elif 48 <= key.vk <= 57:
                        return getattr(Qt, f'Key_{chr(key.vk)}', None)
        
        return None
    
    def _on_press(self, key):
        """按键按下回调"""
        try:
            qt_key = self._convert_key_to_qt(key)
            if qt_key is not None:
                debug_logger.output("keyboard_hook_manager.py", LogLevel.DEBUG, 
                                   f"键盘按下: {key} -> Qt Key: {qt_key}", 
                                   fold_code="KEYBOARD_HOOK")
                self.key_pressed.emit(qt_key)
        except Exception as e:
            debug_logger.output("keyboard_hook_manager.py", LogLevel.ERROR, 
                               f"处理按键按下事件时出错: {e}", 
                               fold_code="KEYBOARD_HOOK")
    
    def _on_release(self, key):
        """按键抬起回调"""
        try:
            qt_key = self._convert_key_to_qt(key)
            if qt_key is not None:
                debug_logger.output("keyboard_hook_manager.py", LogLevel.DEBUG, 
                                   f"键盘抬起: {key} -> Qt Key: {qt_key}", 
                                   fold_code="KEYBOARD_HOOK")
                self.key_released.emit(qt_key)
        except Exception as e:
            debug_logger.output("keyboard_hook_manager.py", LogLevel.ERROR, 
                               f"处理按键抬起事件时出错: {e}", 
                               fold_code="KEYBOARD_HOOK")
    
    def start(self) -> bool:
        """启动键盘钩子监听"""
        if not PYNPUT_AVAILABLE:
            debug_logger.output("keyboard_hook_manager.py", LogLevel.ERROR, 
                               "无法启动键盘钩子：pynput 库未安装", 
                               fold_code="KEYBOARD_HOOK")
            return False
        
        if self.is_running:
            debug_logger.output("keyboard_hook_manager.py", LogLevel.WARNING, 
                               "键盘钩子已在运行中", 
                               fold_code="KEYBOARD_HOOK")
            return True
        
        try:
            # 创建并启动监听器
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self.listener.start()
            self.is_running = True
            
            debug_logger.output("keyboard_hook_manager.py", LogLevel.INFO, 
                               "键盘钩子监听已启动（底层模式）", 
                               fold_code="KEYBOARD_HOOK")
            return True
            
        except Exception as e:
            debug_logger.output("keyboard_hook_manager.py", LogLevel.ERROR, 
                               f"启动键盘钩子失败: {e}", 
                               fold_code="KEYBOARD_HOOK")
            return False
    
    def stop(self):
        """停止键盘钩子监听"""
        if not self.is_running:
            return
        
        try:
            if self.listener:
                self.listener.stop()
                self.listener = None
            
            self.is_running = False
            debug_logger.output("keyboard_hook_manager.py", LogLevel.INFO, 
                               "键盘钩子监听已停止", 
                               fold_code="KEYBOARD_HOOK")
        except Exception as e:
            debug_logger.output("keyboard_hook_manager.py", LogLevel.ERROR, 
                               f"停止键盘钩子时出错: {e}", 
                               fold_code="KEYBOARD_HOOK")
    
    def is_available(self) -> bool:
        """检查键盘钩子功能是否可用"""
        return PYNPUT_AVAILABLE
