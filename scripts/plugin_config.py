"""
插件系统配置管理

提供插件系统的配置选项，包括插件目录、启用/禁用开关、安全和权限设置。

需求：8.8, 16.12
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import json


@dataclass
class PluginSystemConfig:
    """
    插件系统配置
    
    需求：8.8, 16.12
    """
    
    # 插件目录配置
    plugin_directory: str = "plugins/"
    
    # 插件系统启用/禁用开关
    enabled: bool = True
    
    # 插件自动加载开关
    auto_load_plugins: bool = True
    
    # 插件自动启用开关（新安装的插件是否默认启用）
    auto_enable_new_plugins: bool = True
    
    # 安全设置
    allow_unverified_plugins: bool = False  # 是否允许未经审核的插件
    require_signature: bool = False  # 是否要求插件签名
    
    # 权限设置
    allowed_permissions: List[str] = field(default_factory=lambda: [
        "tab_registration",  # 允许注册选项卡
        "tts_engine",  # 允许注册TTS引擎
        "event_subscription",  # 允许订阅事件
        "config_access",  # 允许访问配置
        "resource_access",  # 允许访问资源文件
    ])
    
    # 禁止的权限（黑名单）
    forbidden_permissions: List[str] = field(default_factory=lambda: [
        "system_config_write",  # 禁止写入系统配置
        "file_system_write",  # 禁止写入文件系统（插件目录外）
        "network_unrestricted",  # 禁止无限制网络访问
    ])
    
    # 插件更新设置
    check_updates_on_startup: bool = False  # 启动时检查更新
    auto_update_plugins: bool = False  # 自动更新插件
    
    # 性能设置
    max_concurrent_plugins: int = 50  # 最大并发插件数
    plugin_load_timeout: int = 30  # 插件加载超时（秒）
    plugin_init_timeout: int = 10  # 插件初始化超时（秒）
    
    # 日志设置
    log_plugin_events: bool = True  # 记录插件事件
    log_level: str = "INFO"  # 日志级别
    
    # 开发者模式
    developer_mode: bool = False  # 开发者模式（允许加载未签名插件等）
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "plugin_directory": self.plugin_directory,
            "enabled": self.enabled,
            "auto_load_plugins": self.auto_load_plugins,
            "auto_enable_new_plugins": self.auto_enable_new_plugins,
            "allow_unverified_plugins": self.allow_unverified_plugins,
            "require_signature": self.require_signature,
            "allowed_permissions": self.allowed_permissions,
            "forbidden_permissions": self.forbidden_permissions,
            "check_updates_on_startup": self.check_updates_on_startup,
            "auto_update_plugins": self.auto_update_plugins,
            "max_concurrent_plugins": self.max_concurrent_plugins,
            "plugin_load_timeout": self.plugin_load_timeout,
            "plugin_init_timeout": self.plugin_init_timeout,
            "log_plugin_events": self.log_plugin_events,
            "log_level": self.log_level,
            "developer_mode": self.developer_mode,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PluginSystemConfig":
        """从字典创建配置"""
        return cls(
            plugin_directory=data.get("plugin_directory", "plugins/"),
            enabled=data.get("enabled", True),
            auto_load_plugins=data.get("auto_load_plugins", True),
            auto_enable_new_plugins=data.get("auto_enable_new_plugins", True),
            allow_unverified_plugins=data.get("allow_unverified_plugins", False),
            require_signature=data.get("require_signature", False),
            allowed_permissions=data.get("allowed_permissions", [
                "tab_registration",
                "tts_engine",
                "event_subscription",
                "config_access",
                "resource_access",
            ]),
            forbidden_permissions=data.get("forbidden_permissions", [
                "system_config_write",
                "file_system_write",
                "network_unrestricted",
            ]),
            check_updates_on_startup=data.get("check_updates_on_startup", False),
            auto_update_plugins=data.get("auto_update_plugins", False),
            max_concurrent_plugins=data.get("max_concurrent_plugins", 50),
            plugin_load_timeout=data.get("plugin_load_timeout", 30),
            plugin_init_timeout=data.get("plugin_init_timeout", 10),
            log_plugin_events=data.get("log_plugin_events", True),
            log_level=data.get("log_level", "INFO"),
            developer_mode=data.get("developer_mode", False),
        )
    
    def save_to_file(self, file_path: Path) -> bool:
        """保存配置到文件"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving plugin config: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, file_path: Path) -> Optional["PluginSystemConfig"]:
        """从文件加载配置"""
        try:
            if not file_path.exists():
                return None
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return cls.from_dict(data)
        except Exception as e:
            print(f"Error loading plugin config: {e}")
            return None
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        验证配置有效性
        
        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []
        
        # 验证插件目录
        if not self.plugin_directory:
            errors.append("Plugin directory cannot be empty")
        
        # 验证超时设置
        if self.plugin_load_timeout <= 0:
            errors.append("Plugin load timeout must be positive")
        
        if self.plugin_init_timeout <= 0:
            errors.append("Plugin init timeout must be positive")
        
        # 验证最大并发插件数
        if self.max_concurrent_plugins <= 0:
            errors.append("Max concurrent plugins must be positive")
        
        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            errors.append(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")
        
        return (len(errors) == 0, errors)


class PluginConfigManager:
    """
    插件配置管理器
    
    负责加载、保存和管理插件系统配置。
    """
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
        """
        if config_file is None:
            config_file = Path("config") / "plugin_system.json"
        
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> PluginSystemConfig:
        """
        加载配置
        
        如果配置文件不存在，返回默认配置。
        """
        config = PluginSystemConfig.load_from_file(self.config_file)
        
        if config is None:
            # 使用默认配置
            config = PluginSystemConfig()
            # 尝试保存默认配置
            self.save_config(config)
        
        return config
    
    def save_config(self, config: Optional[PluginSystemConfig] = None) -> bool:
        """
        保存配置
        
        Args:
            config: 要保存的配置，如果为None则保存当前配置
        """
        if config is None:
            config = self.config
        
        # 确保配置目录存在
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        return config.save_to_file(self.config_file)
    
    def update_config(self, **kwargs) -> bool:
        """
        更新配置
        
        Args:
            **kwargs: 要更新的配置项
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.save_config()
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        self.config = PluginSystemConfig()
        return self.save_config()
    
    def get_config(self) -> PluginSystemConfig:
        """获取当前配置"""
        return self.config


# 全局配置管理器实例
_config_manager: Optional[PluginConfigManager] = None


def get_plugin_config_manager() -> PluginConfigManager:
    """获取全局插件配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = PluginConfigManager()
    return _config_manager


def get_plugin_config() -> PluginSystemConfig:
    """获取插件系统配置"""
    return get_plugin_config_manager().get_config()
