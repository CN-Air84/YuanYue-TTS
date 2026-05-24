# coding=utf-8
import sys
import os
import ctypes
from typing import Dict, Tuple, Optional, List

from debug_logger import debug_logger, LogLevel

# 设置 PySDL2 DLL 路径（优先使用 pygame 包中的 SDL2 库）
if 'PYSDL2_DLL_PATH' not in os.environ:
    # 使用 sys.executable 的目录避免 MEI 临时目录问题
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    pygame_sdl_path = os.path.join(base_path, '.venv', 'Lib', 'site-packages', 'pygame')
    if os.path.exists(pygame_sdl_path):
        os.environ['PYSDL2_DLL_PATH'] = pygame_sdl_path

# 尝试导入 sdl2，如果失败则静默处理（避免影响主程序启动，虽然理应已安装）
try:
    import sdl2
    import sdl2.ext
    SDL_AVAILABLE = True
except ImportError as e:
    SDL_AVAILABLE = False
    # 这里可能还无法使用 debug_logger，因为可能还没初始化好
    print(f"Warning: PySDL2 not found. SDL input mode will be disabled. Error: {e}")

class SDLInputManager:
    """
    SDL2 输入设备管理器
    负责设备枚举、事件轮询和状态检测
    """
    def __init__(self):
        self.initialized = False
        self.joysticks = {} # id -> SDL_Joystick
        self.controllers = {} # id -> SDL_GameController (优先使用 GameController)
        self.joystick_ids = {} # instance_id -> device_index
        
    def init_sdl(self) -> bool:
        """初始化 SDL2 子系统"""
        if not SDL_AVAILABLE:
            debug_logger.output("sdl_input_manager.py", LogLevel.WARNING, "SDL initialization skipped: PySDL2 not available", fold_code="SDL_INIT")
            return False
            
        if self.initialized:
            return True
            
        # 初始化 Joystick 和 GameController 子系统
        debug_logger.output("sdl_input_manager.py", LogLevel.INFO, "Initializing SDL2 subsystems...", fold_code="SDL_INIT")
        if sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER) != 0:
            err = sdl2.SDL_GetError()
            debug_logger.output("sdl_input_manager.py", LogLevel.ERROR, f"SDL_Init failed: {err}", fold_code="SDL_INIT")
            return False
            
        self.initialized = True
        debug_logger.output("sdl_input_manager.py", LogLevel.INFO, "SDL2 subsystems initialized successfully", fold_code="SDL_INIT")
        self.scan_devices()
        return True
        
    def quit_sdl(self):
        """清理 SDL2 资源"""
        if not self.initialized:
            return
            
        debug_logger.output("sdl_input_manager.py", LogLevel.INFO, "Closing SDL devices and quitting SDL...", fold_code="SDL_QUIT")
        for joy in self.joysticks.values():
            if joy:
                sdl2.SDL_JoystickClose(joy)
        self.joysticks.clear()
        
        sdl2.SDL_Quit()
        self.initialized = False
        debug_logger.output("sdl_input_manager.py", LogLevel.INFO, "SDL2 resources cleaned up", fold_code="SDL_QUIT")
        
    def scan_devices(self):
        """扫描并打开所有连接的输入设备"""
        if not self.initialized:
            return
            
        num_joysticks = sdl2.SDL_NumJoysticks()
        debug_logger.output("sdl_input_manager.py", LogLevel.INFO, f"Scanning SDL devices: {num_joysticks} found", fold_code="SDL_SCAN")
        
        for i in range(num_joysticks):
            # 尝试作为 GameController 打开 (更高级的抽象)
            if sdl2.SDL_IsGameController(i):
                ctrl = sdl2.SDL_GameControllerOpen(i)
                if ctrl:
                    joy = sdl2.SDL_GameControllerGetJoystick(ctrl)
                    instance_id = sdl2.SDL_JoystickInstanceID(joy)
                    self.joysticks[instance_id] = joy # 仍然需要 joystick 指针来读取某些原始信息
                    name = sdl2.SDL_GameControllerName(ctrl).decode('utf-8')
                    debug_logger.output("sdl_input_manager.py", LogLevel.INFO, f"Opened GameController {i}: {name}", fold_code="SDL_SCAN")
                    continue
            
            # 回退到普通 Joystick
            joy = sdl2.SDL_JoystickOpen(i)
            if joy:
                instance_id = sdl2.SDL_JoystickInstanceID(joy)
                self.joysticks[instance_id] = joy
                name = sdl2.SDL_JoystickName(joy).decode('utf-8')
                debug_logger.output("sdl_input_manager.py", LogLevel.INFO, f"Opened Joystick {i}: {name}", fold_code="SDL_SCAN")

    def poll_events(self) -> List[dict]:
        """
        轮询 SDL 事件
        返回事件列表，每个事件是一个字典：
        {
            'type': 'button_down' | 'button_up' | 'axis_motion',
            'device_guid': str,
            'button_id': int, (optional)
            'axis_id': int, (optional)
            'value': int, (optional)
            'device_name': str
        }
        """
        if not self.initialized:
            return []
            
        events = []
        event = sdl2.SDL_Event()
        
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_JOYDEVICEADDED:
                debug_logger.output("sdl_input_manager.py", LogLevel.INFO, "SDL device added", fold_code="SDL_EVENT")
                self.scan_devices()
                events.append({'type': 'device_added'})
            elif event.type == sdl2.SDL_JOYDEVICEREMOVED:
                # 简单处理：重新扫描（实际应用中应更精细管理）
                debug_logger.output("sdl_input_manager.py", LogLevel.INFO, "SDL device removed", fold_code="SDL_EVENT")
                self.scan_devices()
                events.append({'type': 'device_removed'})
                
            elif event.type == sdl2.SDL_JOYBUTTONDOWN or event.type == sdl2.SDL_JOYBUTTONUP:
                is_down = event.type == sdl2.SDL_JOYBUTTONDOWN
                instance_id = event.jbutton.which
                button_id = event.jbutton.button
                joy = self.joysticks.get(instance_id)
                if joy:
                    guid_str = self._get_guid_string(joy)
                    name = sdl2.SDL_JoystickName(joy).decode('utf-8')
                    events.append({
                        'type': 'button_down' if is_down else 'button_up',
                        'device_guid': guid_str,
                        'button_id': button_id,
                        'device_name': name
                    })
            
            elif event.type == sdl2.SDL_JOYHATMOTION:
                # 将 Hat (方向键) 映射为虚拟按钮，方便统一处理
                instance_id = event.jhat.which
                hat_id = event.jhat.hat
                value = event.jhat.value
                joy = self.joysticks.get(instance_id)
                if joy:
                    guid_str = self._get_guid_string(joy)
                    name = sdl2.SDL_JoystickName(joy).decode('utf-8')
                    
                    # 定义 Hat 方向的虚拟按钮 ID 偏移 (避免与普通按钮冲突)
                    # 假设普通按钮不会超过 1000 个
                    HAT_OFFSET = 1000 + hat_id * 10
                    
                    # SDL_HAT_UP, SDL_HAT_RIGHT, SDL_HAT_DOWN, SDL_HAT_LEFT
                    directions = [
                        (sdl2.SDL_HAT_UP, 1),
                        (sdl2.SDL_HAT_RIGHT, 2),
                        (sdl2.SDL_HAT_DOWN, 3),
                        (sdl2.SDL_HAT_LEFT, 4)
                    ]
                    
                    for dir_mask, dir_id in directions:
                        v_btn_id = HAT_OFFSET + dir_id
                        is_pressed = bool(value & dir_mask)
                        
                        events.append({
                            'type': 'button_down' if is_pressed else 'button_up',
                            'device_guid': guid_str,
                            'button_id': v_btn_id,
                            'device_name': name
                        })
                    
            # 可以在这里添加对 Axis (轴) 的支持，如果需要支持扳机键等
            # 但要注意轴通常会产生大量噪音事件，需要设定死区
            
        return events

    def get_button_state(self, device_guid: str, button_id: int) -> bool:
        """检查特定设备的特定按钮是否按下"""
        if not self.initialized:
            return False
            
        # 遍历所有已打开的设备，找到 GUID 匹配的
        target_joy = None
        for joy in self.joysticks.values():
            if self._get_guid_string(joy) == device_guid:
                target_joy = joy
                break
        
        if target_joy:
            # 处理虚拟 Hat 按钮
            if button_id >= 1000:
                hat_id = (button_id - 1000) // 10
                dir_id = (button_id - 1000) % 10
                
                value = sdl2.SDL_JoystickGetHat(target_joy, hat_id)
                
                mapping = {
                    1: sdl2.SDL_HAT_UP,
                    2: sdl2.SDL_HAT_RIGHT,
                    3: sdl2.SDL_HAT_DOWN,
                    4: sdl2.SDL_HAT_LEFT
                }
                
                dir_mask = mapping.get(dir_id, 0)
                return bool(value & dir_mask)
            
            # 处理普通按钮
            return sdl2.SDL_JoystickGetButton(target_joy, button_id) == 1
            
        return False

    def get_connected_devices(self) -> List[dict]:
        """获取所有已连接设备的列表 [{'guid': str, 'name': str}]"""
        devices = []
        if not self.initialized:
            return devices
            
        # 遍历当前已打开的 joysticks
        for joy in self.joysticks.values():
            guid = self._get_guid_string(joy)
            name = sdl2.SDL_JoystickName(joy).decode('utf-8')
            devices.append({'guid': guid, 'name': name})
        return devices

    def _get_guid_string(self, joystick) -> str:
        """获取设备的 GUID 字符串"""
        guid = sdl2.SDL_JoystickGetGUID(joystick)
        # SDL_JoystickGetGUIDString 需要一个缓冲区
        guid_str_buf = ctypes.create_string_buffer(33)
        sdl2.SDL_JoystickGetGUIDString(guid, guid_str_buf, 33)
        return guid_str_buf.value.decode('utf-8')

    @staticmethod
    def get_friendly_name(guid: str, button_id: int) -> str:
        """生成用户友好的按键名称"""
        if button_id >= 1000:
            hat_id = (button_id - 1000) // 10
            dir_id = (button_id - 1000) % 10
            
            directions = {1: "UP", 2: "RIGHT", 3: "DOWN", 4: "LEFT"}
            dir_name = directions.get(dir_id, "Unknown")
            
            return f"Hat {hat_id} {dir_name}"
            
        return f"JoyBtn {button_id}"
