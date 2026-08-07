"""
插件实例模型

定义插件运行时的实例数据结构。
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict
from enum import Enum
from datetime import datetime, timedelta
import threading
import time

from plugin_metadata import PluginMetadata


class PluginStatus(Enum):
    """插件状态"""
    NOT_LOADED = "not_loaded"   # 未加载
    LOADED = "loaded"           # 已加载
    ENABLED = "enabled"         # 已启用
    DISABLED = "disabled"       # 已禁用
    ERROR = "error"             # 错误状态
    
    def __str__(self) -> str:
        """返回状态的字符串表示"""
        status_names = {
            "not_loaded": "未加载",
            "loaded": "已加载",
            "enabled": "已启用",
            "disabled": "已禁用",
            "error": "错误"
        }
        return status_names.get(self.value, self.value)
    
    def is_active(self) -> bool:
        """检查插件是否处于活动状态"""
        return self in (PluginStatus.LOADED, PluginStatus.ENABLED)
    
    def can_enable(self) -> bool:
        """检查插件是否可以被启用"""
        return self in (PluginStatus.LOADED, PluginStatus.DISABLED)
    
    def can_disable(self) -> bool:
        """检查插件是否可以被禁用"""
        return self == PluginStatus.ENABLED


@dataclass
class PluginInstance:
    """插件实例"""
    metadata: PluginMetadata                                # 插件元数据
    module: Any                                             # 加载的Python模块
    status: PluginStatus                                    # 插件状态
    registered_tabs: List[str] = field(default_factory=list)        # 已注册的选项卡
    registered_engines: List[str] = field(default_factory=list)     # 已注册的TTS引擎
    event_subscriptions: List[str] = field(default_factory=list)    # 事件订阅ID列表
    ready_gates: List[str] = field(default_factory=list)            # 就绪状态列表
    error_message: str = ""                                 # 错误信息（如果状态为ERROR）
    crash_count: int = 0                                    # 崩溃计数器
    crash_times: List[datetime] = field(default_factory=list)       # 崩溃时间列表（用于时间窗口检测）
    last_crash_time: Optional[datetime] = None              # 最后一次崩溃时间
    load_time: Optional[datetime] = None                    # 加载时间
    config_namespace: str = ""                              # 配置命名空间
    _crash_lock: threading.Lock = field(default_factory=threading.Lock)  # 崩溃计数器锁（线程安全）
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.config_namespace:
            self.config_namespace = f"Plugin_{self.metadata.name}"
    
    def get_plugin_name(self) -> str:
        """获取插件名称"""
        return self.metadata.name
    
    def get_plugin_version(self) -> str:
        """获取插件版本"""
        return self.metadata.version
    
    def is_enabled(self) -> bool:
        """检查插件是否已启用"""
        return self.status == PluginStatus.ENABLED
    
    def is_error(self) -> bool:
        """检查插件是否处于错误状态"""
        return self.status == PluginStatus.ERROR
    
    def has_registered_tabs(self) -> bool:
        """检查插件是否注册了选项卡"""
        return len(self.registered_tabs) > 0
    
    def has_registered_engines(self) -> bool:
        """检查插件是否注册了TTS引擎"""
        return len(self.registered_engines) > 0
    
    def has_event_subscriptions(self) -> bool:
        """检查插件是否有事件订阅"""
        return len(self.event_subscriptions) > 0
    
    def record_crash(self) -> None:
        """
        记录插件崩溃（线程安全）
        
        更新崩溃计数器和崩溃时间列表，并设置插件状态为错误状态。
        """
        with self._crash_lock:
            current_time = datetime.now()
            self.crash_count += 1
            self.crash_times.append(current_time)
            self.last_crash_time = current_time
            self.status = PluginStatus.ERROR
    
    def reset_crash_counter(self) -> None:
        """
        重置崩溃计数器（线程安全）
        
        清空崩溃计数器和崩溃时间列表，用于插件重新加载时重置状态。
        """
        with self._crash_lock:
            self.crash_count = 0
            self.crash_times.clear()
            self.last_crash_time = None
    
    def should_auto_disable(self, time_window_minutes: int = 5, max_crashes: int = 3) -> bool:
        """
        检查插件是否应该被自动禁用（线程安全）
        
        检查在指定时间窗口内崩溃次数是否超过阈值。
        
        Args:
            time_window_minutes: 时间窗口（分钟），默认5分钟
            max_crashes: 最大崩溃次数，默认3次
            
        Returns:
            是否应该自动禁用
        """
        with self._crash_lock:
            if len(self.crash_times) < max_crashes:
                return False
            
            # 获取当前时间
            current_time = datetime.now()
            time_window = timedelta(minutes=time_window_minutes)
            
            # 计算时间窗口内的崩溃次数
            recent_crashes = [
                crash_time for crash_time in self.crash_times
                if current_time - crash_time <= time_window
            ]
            
            return len(recent_crashes) >= max_crashes
    
    def get_crash_summary(self) -> Dict[str, Any]:
        """
        获取崩溃摘要信息（线程安全）
        
        Returns:
            包含崩溃统计信息的字典
        """
        with self._crash_lock:
            return {
                "total_crashes": self.crash_count,
                "recent_crashes": len([
                    t for t in self.crash_times
                    if datetime.now() - t <= timedelta(minutes=5)
                ]),
                "last_crash_time": self.last_crash_time.isoformat() if self.last_crash_time else None,
                "crash_times": [t.isoformat() for t in self.crash_times[-10:]]  # 最近10次崩溃时间
            }
    
    def get_resource_summary(self) -> Dict[str, int]:
        """
        获取插件资源使用摘要
        
        Returns:
            资源使用统计字典
        """
        return {
            "tabs": len(self.registered_tabs),
            "engines": len(self.registered_engines),
            "events": len(self.event_subscriptions),
            "ready_gates": len(self.ready_gates)
        }
    
    def clear_registrations(self) -> None:
        """清除所有注册信息（用于卸载）"""
        self.registered_tabs.clear()
        self.registered_engines.clear()
        self.event_subscriptions.clear()
        self.ready_gates.clear()
    
    def __str__(self) -> str:
        """返回插件实例的字符串表示"""
        return f"{self.metadata.name} v{self.metadata.version} [{self.status}]"
