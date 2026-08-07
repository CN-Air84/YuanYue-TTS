"""
插件错误处理系统

提供自定义异常类和错误日志记录功能。
"""

from typing import Optional, Dict, Any
from datetime import datetime
import traceback
import logging
from pathlib import Path


# ============================================================================
# 自定义异常类
# ============================================================================

class PluginError(Exception):
    """
    插件错误基类
    
    所有插件相关错误的基类，提供统一的错误信息格式和上下文。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        初始化插件错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称（可选）
            details: 错误详情字典（可选）
        """
        self.message = message
        self.plugin_name = plugin_name
        self.details = details or {}
        self.timestamp = datetime.now()
        
        # 构建完整错误消息
        full_message = message
        if plugin_name:
            full_message = f"[{plugin_name}] {message}"
        
        super().__init__(full_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将错误转换为字典格式
        
        Returns:
            错误信息字典
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "plugin_name": self.plugin_name,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class PluginLoadError(PluginError):
    """
    插件加载错误
    
    在插件加载过程中发生的错误，如模块导入失败、入口点不存在等。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 plugin_path: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        """
        初始化插件加载错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            plugin_path: 插件路径
            original_error: 原始异常
        """
        details = {}
        if plugin_path:
            details["plugin_path"] = plugin_path
        if original_error:
            details["original_error"] = str(original_error)
            details["original_error_type"] = type(original_error).__name__
        
        super().__init__(message, plugin_name, details)
        self.plugin_path = plugin_path
        self.original_error = original_error


class PluginValidationError(PluginError):
    """
    插件验证错误
    
    在插件清单验证、元数据验证等过程中发生的错误。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 validation_errors: Optional[list] = None):
        """
        初始化插件验证错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            validation_errors: 验证错误列表
        """
        details = {}
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        super().__init__(message, plugin_name, details)
        self.validation_errors = validation_errors or []


class PluginDependencyError(PluginError):
    """
    插件依赖错误
    
    在依赖检查过程中发生的错误，如依赖项不满足、版本冲突等。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 missing_dependencies: Optional[list] = None,
                 dependency_type: Optional[str] = None):
        """
        初始化插件依赖错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            missing_dependencies: 缺失的依赖项列表
            dependency_type: 依赖类型 (app_version, plugin, package)
        """
        details = {}
        if missing_dependencies:
            details["missing_dependencies"] = missing_dependencies
        if dependency_type:
            details["dependency_type"] = dependency_type
        
        super().__init__(message, plugin_name, details)
        self.missing_dependencies = missing_dependencies or []
        self.dependency_type = dependency_type


class PluginExecutionError(PluginError):
    """
    插件执行错误
    
    在插件运行时发生的错误，如钩子函数执行失败、API调用错误等。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 hook_name: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        """
        初始化插件执行错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            hook_name: 钩子函数名称
            original_error: 原始异常
        """
        details = {}
        if hook_name:
            details["hook_name"] = hook_name
        if original_error:
            details["original_error"] = str(original_error)
            details["original_error_type"] = type(original_error).__name__
            details["traceback"] = traceback.format_exception(
                type(original_error), original_error, original_error.__traceback__
            )
        
        super().__init__(message, plugin_name, details)
        self.hook_name = hook_name
        self.original_error = original_error


class PluginCrashError(PluginError):
    """
    插件崩溃错误
    
    插件崩溃时抛出的错误，包含崩溃计数和自动禁用信息。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 crash_count: int = 0, auto_disabled: bool = False,
                 crash_times: Optional[list] = None):
        """
        初始化插件崩溃错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            crash_count: 崩溃次数
            auto_disabled: 是否已自动禁用
            crash_times: 崩溃时间列表
        """
        details = {
            "crash_count": crash_count,
            "auto_disabled": auto_disabled
        }
        if crash_times:
            details["crash_times"] = [t.isoformat() if isinstance(t, datetime) else t 
                                       for t in crash_times]
        
        super().__init__(message, plugin_name, details)
        self.crash_count = crash_count
        self.auto_disabled = auto_disabled
        self.crash_times = crash_times or []


class PluginConfigError(PluginError):
    """
    插件配置错误
    
    在插件配置读写过程中发生的错误。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 config_key: Optional[str] = None,
                 config_value: Optional[Any] = None):
        """
        初始化插件配置错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            config_key: 配置键
            config_value: 配置值
        """
        details = {}
        if config_key:
            details["config_key"] = config_key
        if config_value is not None:
            details["config_value"] = str(config_value)
        
        super().__init__(message, plugin_name, details)
        self.config_key = config_key
        self.config_value = config_value


class PluginPermissionError(PluginError):
    """
    插件权限错误
    
    在插件尝试执行超出其权限范围的操作时抛出。
    """
    
    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 required_permission: Optional[str] = None):
        """
        初始化插件权限错误
        
        Args:
            message: 错误消息
            plugin_name: 插件名称
            required_permission: 所需权限
        """
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        
        super().__init__(message, plugin_name, details)
        self.required_permission = required_permission


# ============================================================================
# 插件日志系统
# ============================================================================

class PluginLogger:
    """
    插件日志记录器
    
    提供独立的插件日志文件记录功能，记录详细的错误信息、堆栈跟踪等。
    """
    
    _instance: Optional['PluginLogger'] = None
    _initialized: bool = False
    
    def __new__(cls, log_dir: str = "logs"):
        """
        单例模式：确保只有一个日志记录器实例
        
        Args:
            log_dir: 日志目录路径
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, log_dir: str = "logs"):
        """
        初始化插件日志记录器
        
        Args:
            log_dir: 日志目录路径
        """
        # 避免重复初始化
        if PluginLogger._initialized:
            return
        
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "plugins.log"
        
        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建专用日志记录器
        self.logger = logging.getLogger("plugin_system")
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            # 文件处理器
            file_handler = logging.FileHandler(
                self.log_file, 
                encoding='utf-8',
                mode='a'  # 追加模式
            )
            file_handler.setLevel(logging.DEBUG)
            
            # 日志格式
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
        
        PluginLogger._initialized = True
    
    def log_error(self, error: PluginError, exc_info: bool = True) -> None:
        """
        记录插件错误
        
        Args:
            error: 插件错误对象
            exc_info: 是否记录堆栈跟踪
        """
        error_dict = error.to_dict()
        
        # 构建日志消息
        log_message = f"{error_dict['error_type']}: {error_dict['message']}"
        if error.plugin_name:
            log_message = f"[{error.plugin_name}] {log_message}"
        
        # 记录详细信息
        if error.details:
            details_str = " | ".join(f"{k}={v}" for k, v in error.details.items())
            log_message = f"{log_message} | {details_str}"
        
        self.logger.error(log_message, exc_info=exc_info)
    
    def log_crash(self, plugin_name: str, crash_count: int, 
                  error: Optional[Exception] = None) -> None:
        """
        记录插件崩溃
        
        Args:
            plugin_name: 插件名称
            crash_count: 崩溃次数
            error: 崩溃异常（可选）
        """
        log_message = f"[{plugin_name}] Plugin crash detected (count: {crash_count})"
        self.logger.error(log_message, exc_info=error is not None)
        
        if error:
            self.logger.error(
                f"[{plugin_name}] Crash exception: {type(error).__name__}: {error}",
                exc_info=True
            )
    
    def log_auto_disable(self, plugin_name: str, reason: str) -> None:
        """
        记录插件自动禁用
        
        Args:
            plugin_name: 插件名称
            reason: 禁用原因
        """
        self.logger.warning(
            f"[{plugin_name}] Plugin auto-disabled: {reason}"
        )
    
    def log_reload(self, plugin_name: str, success: bool, 
                   error: Optional[Exception] = None) -> None:
        """
        记录插件重新加载
        
        Args:
            plugin_name: 插件名称
            success: 是否成功
            error: 错误异常（可选）
        """
        if success:
            self.logger.info(f"[{plugin_name}] Plugin reloaded successfully")
        else:
            self.logger.error(
                f"[{plugin_name}] Plugin reload failed: {error}",
                exc_info=error is not None
            )
    
    def info(self, message: str, plugin_name: Optional[str] = None) -> None:
        """
        记录信息级别日志
        
        Args:
            message: 日志消息
            plugin_name: 插件名称（可选）
        """
        if plugin_name:
            message = f"[{plugin_name}] {message}"
        self.logger.info(message)
    
    def warning(self, message: str, plugin_name: Optional[str] = None) -> None:
        """
        记录警告级别日志
        
        Args:
            message: 日志消息
            plugin_name: 插件名称（可选）
        """
        if plugin_name:
            message = f"[{plugin_name}] {message}"
        self.logger.warning(message)
    
    def error(self, message: str, plugin_name: Optional[str] = None,
              exc_info: bool = False) -> None:
        """
        记录错误级别日志
        
        Args:
            message: 日志消息
            plugin_name: 插件名称（可选）
            exc_info: 是否记录堆栈跟踪
        """
        if plugin_name:
            message = f"[{plugin_name}] {message}"
        self.logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str, plugin_name: Optional[str] = None) -> None:
        """
        记录调试级别日志
        
        Args:
            message: 日志消息
            plugin_name: 插件名称（可选）
        """
        if plugin_name:
            message = f"[{plugin_name}] {message}"
        self.logger.debug(message)
    
    def get_log_content(self, lines: int = 100) -> str:
        """
        获取日志文件内容
        
        Args:
            lines: 要读取的行数
            
        Returns:
            日志内容字符串
        """
        try:
            if not self.log_file.exists():
                return "Log file does not exist"
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading log file: {e}"


# 全局日志记录器实例
_plugin_logger: Optional[PluginLogger] = None


def get_plugin_logger() -> PluginLogger:
    """
    获取全局插件日志记录器实例
    
    Returns:
        PluginLogger 实例
    """
    global _plugin_logger
    if _plugin_logger is None:
        _plugin_logger = PluginLogger()
    return _plugin_logger
