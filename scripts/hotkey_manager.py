# coding=utf-8
import os
import json
from typing import Dict, Optional, List, Tuple
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QKeyEvent
from debug_logger import debug_logger, LogLevel
from sdl_input_manager import SDLInputManager

class HotkeyAction:
    """热键动作常量"""
    TOGGLE_PAUSE = "toggle_pause"
    SEEK_BACKWARD = "seek_backward"
    SEEK_FORWARD = "seek_forward"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    NEXT_SENTENCE = "next_sentence"
    PREV_SENTENCE = "prev_sentence"

class HotkeyManager(QObject):
    """
    统一热键管理器
    负责热键的注册、存储、识别和分发
    支持 Qt 键盘事件和 SDL2 输入设备
    """
    # 当热键被触发时发出的信号
    hotkey_triggered = pyqtSignal(str)  # 参数为动作名称
    
    # SDL2 事件信号 (用于录制)
    # 参数: (device_guid, button_id, device_name)
    sdl_button_pressed = pyqtSignal(str, int, str)
    
    # SDL 设备列表更新信号
    sdl_devices_updated = pyqtSignal(list)

    def __init__(self, settings_manager=None):
        super().__init__()
        self.settings_manager = settings_manager
        # 动作到按键的映射 {action: key_code} (Qt Mode)
        self.hotkeys: Dict[str, int] = {}
        # 动作到 SDL 绑定的映射 {action: (device_guid, button_id)} (SDL Mode)
        self.sdl_bindings: Dict[str, Tuple[str, int]] = {}
        
        # 动作到辅助键的映射 {action: modifiers}
        self.modifiers: Dict[str, Qt.KeyboardModifiers] = {}
        
        # 默认热键配置 (参考原方案1)
        self.default_hotkeys = {
            HotkeyAction.TOGGLE_PAUSE: Qt.Key_Space,
            HotkeyAction.SEEK_BACKWARD: Qt.Key_A,
            HotkeyAction.SEEK_FORWARD: Qt.Key_D,
            HotkeyAction.VOLUME_UP: Qt.Key_W,
            HotkeyAction.VOLUME_DOWN: Qt.Key_S,
            HotkeyAction.NEXT_SENTENCE: Qt.Key_Right,
            HotkeyAction.PREV_SENTENCE: Qt.Key_Left
        }
        
        # SDL2 管理器
        self.sdl_manager = SDLInputManager()
        self.use_sdl_mode = False
        self.target_sdl_device_guid: Optional[str] = None # 目标 SDL 设备 GUID (None 表示响应所有)
        
        # SDL 轮询定时器 (16ms ~= 60fps)
        self.sdl_timer = QTimer(self)
        self.sdl_timer.timeout.connect(self._poll_sdl_inputs)
        
        # 按钮状态缓存，防止重复触发 (Key Repeat)
        # {action: is_pressed}
        self.sdl_button_states: Dict[str, bool] = {}
        
        self.load_hotkeys()
        
    def _poll_sdl_inputs(self):
        """轮询 SDL 输入事件"""
        if not self.use_sdl_mode:
            return
            
        try:
            events = self.sdl_manager.poll_events()
            
            # 如果事件中包含设备变更，通知 UI 更新设备列表
            for event in events:
                if event.get('type') in ('device_added', 'device_removed'):
                    device_info = event.get('device_name', 'Unknown Device')
                    debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"检测到 SDL 设备状态变更: {event.get('type')} - 设备: {device_info}", fold_code="HOTKEY_SDL")
                    self.sdl_devices_updated.emit(self.sdl_manager.get_connected_devices())

            for event in events:
                if event['type'] == 'button_down':
                    # 如果指定了目标设备且不匹配，则忽略（除非正在录制，录制时允许接收所有以便选择）
                    # 录制逻辑在 UI 层处理，这里我们只负责过滤触发信号
                    
                    # 发出信号供录制使用 (录制时不应过滤)
                    self.sdl_button_pressed.emit(
                        event['device_guid'], 
                        event['button_id'],
                        event.get('device_name', 'Unknown Device')
                    )
                    
                    # 检查是否触发了热键 (带设备过滤)
                    if not self.target_sdl_device_guid or self.target_sdl_device_guid == event['device_guid']:
                        self._check_sdl_trigger(event['device_guid'], event['button_id'], True)
                    else:
                        debug_logger.output("hotkey_manager.py", LogLevel.DEBUG, f"忽略来自非目标 SDL 设备的消息: {event['device_guid']}", fold_code="HOTKEY_SDL")
                    
                elif event['type'] == 'button_up':
                    # 检查释放 (用于重置状态)
                    if not self.target_sdl_device_guid or self.target_sdl_device_guid == event['device_guid']:
                        self._check_sdl_trigger(event['device_guid'], event['button_id'], False)
        except Exception as e:
            debug_logger.output("hotkey_manager.py", LogLevel.ERROR, f"轮询 SDL 输入时发生致命错误: {str(e)}", fold_code="HOTKEY_SDL")

    def _check_sdl_trigger(self, guid: str, button_id: int, is_pressed: bool):
        """检查 SDL 输入是否触发热键"""
        matched = False
        for action, binding in self.sdl_bindings.items():
            if not binding:
                continue
            
            b_guid, b_id = binding
            if b_guid == guid and b_id == button_id:
                matched = True
                # 状态防抖/重复触发控制
                was_pressed = self.sdl_button_states.get(action, False)
                
                if is_pressed and not was_pressed:
                    # 按下瞬间触发
                    debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"触发 SDL 热键: {action} (设备: {guid[:8]}..., 按钮 ID: {button_id})", fold_code="HOTKEY_SDL")
                    self.hotkey_triggered.emit(action)
                    self.sdl_button_states[action] = True
                elif not is_pressed:
                    # 释放
                    self.sdl_button_states[action] = False
        
        if is_pressed and not matched:
            debug_logger.output("hotkey_manager.py", LogLevel.DEBUG, f"SDL 按键未绑定任何动作: ButtonID={button_id}", fold_code="HOTKEY_SDL")
                    
    def set_sdl_mode(self, enabled: bool) -> bool:
        """启用或禁用 SDL 模式"""
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"正在切换 SDL 模式: {enabled}", fold_code="HOTKEY_CFG")
        if enabled:
            if self.sdl_manager.init_sdl():
                self.use_sdl_mode = True
                self.sdl_timer.start(16)
                debug_logger.output("hotkey_manager.py", LogLevel.INFO, "SDL 监听模式启动成功 (16ms 轮询)", fold_code="HOTKEY_CFG")
            else:
                self.use_sdl_mode = False
                debug_logger.output("hotkey_manager.py", LogLevel.ERROR, "SDL 监听模式启动失败，请检查驱动或设备连接", fold_code="HOTKEY_CFG")
        else:
            self.use_sdl_mode = False
            self.sdl_timer.stop()
            self.sdl_manager.quit_sdl()
            debug_logger.output("hotkey_manager.py", LogLevel.INFO, "SDL 监听模式已关闭", fold_code="HOTKEY_CFG")
            
        if self.settings_manager:
            self.settings_manager.Custom.set_value("use_sdl_input", self.use_sdl_mode)
            
        return self.use_sdl_mode

    def load_hotkeys(self):
        """从设置中加载热键配置"""
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, "正在从配置文件加载热键数据...", fold_code="HOTKEY_CFG")
        if not self.settings_manager:
            self.hotkeys = self.default_hotkeys.copy()
            debug_logger.output("hotkey_manager.py", LogLevel.WARNING, "未找到设置管理器，已加载默认 Qt 热键配置", fold_code="HOTKEY_CFG")
            return

        # 加载 SDL 模式开关
        use_sdl_raw = self.settings_manager.Custom.get_value("use_sdl_input", False)
        use_sdl = str(use_sdl_raw).lower() == 'true'
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"读取到 SDL 模式偏好: {use_sdl}", fold_code="HOTKEY_CFG")
        
        # 注意：这里不立即调用 set_sdl_mode，避免初始化时阻塞或依赖未就绪，
        # 但为了保持状态一致，可以在 UI 加载时读取此值
        if use_sdl:
             # 可以在这里延迟初始化，或者等待 UI 显式调用
             pass

        # 加载 Qt 热键
        loaded_count = 0
        for action in self.default_hotkeys.keys():
            # 从 Custom 段落读取，格式为 "hotkey_action_name"
            key_val = self.settings_manager.Custom.get_value(f"hk_{action}", "")
            if key_val:
                try:
                    self.hotkeys[action] = int(key_val)
                    loaded_count += 1
                except ValueError:
                    self.hotkeys[action] = self.default_hotkeys[action]
                    debug_logger.output("hotkey_manager.py", LogLevel.WARNING, f"动作 {action} 的热键值无效: {key_val}，已重置为默认", fold_code="HOTKEY_CFG")
            else:
                self.hotkeys[action] = self.default_hotkeys[action]
                
            # 加载 SDL 绑定
            sdl_val = self.settings_manager.Custom.get_value(f"sdl_hk_{action}", "")
            if sdl_val:
                try:
                    # 存储格式: "GUID|ButtonID"
                    parts = sdl_val.split('|')
                    if len(parts) == 2:
                        self.sdl_bindings[action] = (parts[0], int(parts[1]))
                        debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"已加载 {action} 的 SDL 绑定: {sdl_val}", fold_code="HOTKEY_CFG")
                except Exception as e:
                    debug_logger.output("hotkey_manager.py", LogLevel.ERROR, f"加载 {action} 的 SDL 绑定时出错: {str(e)}", fold_code="HOTKEY_CFG")

        debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"热键加载完毕: {loaded_count} 个 Qt 热键, {len(self.sdl_bindings)} 个 SDL 绑定", fold_code="HOTKEY_CFG")

    def save_hotkeys(self):
        """保存热键配置到设置"""
        if not self.settings_manager:
            return
        
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, "正在将热键配置保存至设置文件...", fold_code="HOTKEY_CFG")
        # 保存 Qt 热键
        for action, key_code in self.hotkeys.items():
            self.settings_manager.Custom.set_value(f"hk_{action}", str(key_code))
            
        # 保存 SDL 绑定
        for action, binding in self.sdl_bindings.items():
            if binding:
                val = f"{binding[0]}|{binding[1]}"
                self.settings_manager.Custom.set_value(f"sdl_hk_{action}", val)
            else:
                 # 清除不存在的绑定
                 self.settings_manager.Custom.set_value(f"sdl_hk_{action}", "")
        
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, "热键配置已成功持久化", fold_code="HOTKEY_CFG")

    def set_hotkey(self, action: str, key_code: int):
        """设置特定动作的热键 (Qt Mode)"""
        if action in self.default_hotkeys:
            self.hotkeys[action] = key_code
            debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"更新 Qt 热键 - 动作: {action}, 键码: {key_code}", fold_code="HOTKEY_CFG")
            self.save_hotkeys()
            
    def set_sdl_binding(self, action: str, device_guid: str, button_id: int):
        """设置特定动作的 SDL 绑定"""
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"更新 SDL 绑定 - 动作: {action}, 设备: {device_guid[:8]}..., 按钮: {button_id}", fold_code="HOTKEY_CFG")
        if not device_guid:
            if action in self.sdl_bindings:
                del self.sdl_bindings[action]
        else:
            self.sdl_bindings[action] = (device_guid, button_id)
        self.save_hotkeys()

    def reset_to_defaults(self):
        """重置为默认热键"""
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, "正在将所有热键重置为默认配置", fold_code="HOTKEY_CFG")
        self.hotkeys = self.default_hotkeys.copy()
        self.sdl_bindings.clear()
        self.save_hotkeys()
        debug_logger.output("hotkey_manager.py", LogLevel.INFO, "热键重置完成", fold_code="HOTKEY_CFG")

    def get_hotkey(self, action: str) -> int:
        """获取特定动作的热键代码 (Qt Mode)"""
        key = self.hotkeys.get(action, self.default_hotkeys.get(action, 0))
        # 仅在调试时记录获取操作，避免过多输出
        # debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"Get hotkey for {action}: {key}", fold_code="HOTKEY_INFO")
        return key
        
    def get_sdl_binding(self, action: str) -> Optional[Tuple[str, int]]:
        """获取特定动作的 SDL 绑定"""
        binding = self.sdl_bindings.get(action)
        # debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"Get SDL binding for {action}: {binding}", fold_code="HOTKEY_INFO")
        return binding

    def get_action_name(self, action: str) -> str:
        """获取动作的可读名称"""
        names = {
            HotkeyAction.TOGGLE_PAUSE: "播放/暂停",
            HotkeyAction.SEEK_BACKWARD: "后退",
            HotkeyAction.SEEK_FORWARD: "前进",
            HotkeyAction.VOLUME_UP: "音量 +",
            HotkeyAction.VOLUME_DOWN: "音量 -",
            HotkeyAction.NEXT_SENTENCE: "下一句",
            HotkeyAction.PREV_SENTENCE: "上一句"
        }
        return names.get(action, "未知动作")

    def handle_key_event(self, event: QKeyEvent) -> Optional[str]:
        """
        处理键盘事件，返回匹配的动作名称
        如果匹配成功，返回 action_name，否则返回 None
        """
        try:
            key = event.key()
            modifiers = event.modifiers()
            
            # 记录收到的按键事件（仅在DEBUG级别，避免冗余）
            debug_logger.output("hotkey_manager.py", LogLevel.DEBUG, f"正在处理键盘事件: key={key}, modifiers={modifiers}", fold_code="HOTKEY_KEY")
            
            # 目前主要处理单键，未来可以扩展支持组合键
            matched = False
            for action, target_key in self.hotkeys.items():
                if key == target_key:
                    # 检查修饰键是否匹配 (目前默认忽略修饰键，仅匹配主键)
                    debug_logger.output("hotkey_manager.py", LogLevel.INFO, f"检测到匹配 Qt 热键: {action} (Key: {key})", fold_code="HOTKEY_KEY")
                    self.hotkey_triggered.emit(action)
                    matched = True
                    return action
            
            if not matched:
                debug_logger.output("hotkey_manager.py", LogLevel.DEBUG, f"按键未匹配任何全局热键: {key}", fold_code="HOTKEY_KEY")
            
            return None
        except Exception as e:
            debug_logger.output("hotkey_manager.py", LogLevel.ERROR, f"处理键盘事件时出错: {str(e)}", fold_code="HOTKEY_KEY")
            return None

    @staticmethod
    def key_to_string(key_code: int) -> str:
        """将按键代码转换为可读字符串"""
        if key_code == Qt.Key_Space:
            return "空格"
        if key_code == Qt.Key_Control:
            return "Ctrl"
        if key_code == Qt.Key_Shift:
            return "Shift"
        if key_code == Qt.Key_Alt:
            return "Alt"
        if key_code == Qt.Key_Left:
            return "←"
        if key_code == Qt.Key_Right:
            return "→"
        if key_code == Qt.Key_Up:
            return "↑"
        if key_code == Qt.Key_Down:
            return "↓"
        
        # 尝试使用 QKeySequence 转换
        from PyQt5.QtGui import QKeySequence
        return QKeySequence(key_code).toString()
