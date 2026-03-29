# coding=utf-8
import sys
import os
from datetime import datetime
from enum import Enum
from typing import Optional
import threading
import atexit # 用于在程序退出时关闭文件句柄

# 尝试从 misc_func 导入 get_app_base_path
# 如果导入失败（例如在某些测试环境下），则提供一个备用实现
try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False): # 打包环境
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def priority(self) -> int:
        """获取日志等级的数值优先级，用于筛选输出"""
        priorities = {
            "debug": 10,
            "info": 20,
            "warning": 30,
            "error": 40,
            "critical": 50
        }
        return priorities.get(self.value, 0)


class DebugLogger:
    _instance = None
    _log_file_handle = None
    _current_log_date = None
    _log_lock = threading.Lock() # 用于多线程写入日志文件时的同步

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DebugLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._min_level = LogLevel.WARNING # 默认筛选等级为 WARNING
        self._setup_encoding()
        self._setup_log_file()
        atexit.register(self._close_log_file) # 注册退出时的清理函数
    
    def set_level(self, level: LogLevel):
        """设置最低输出等级，低于此等级的日志将不会打印"""
        self._min_level = level
        self.output("debug_logger.py", LogLevel.INFO, f"日志输出等级已设置为: {level.value.upper()}")
    
    def _setup_encoding(self):
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        if sys.platform.startswith('win'):
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')

    def _setup_log_file(self):
        """设置日志文件路径并打开文件"""
        with self._log_lock:
            log_dir = os.path.join(get_app_base_path(), "cache", "log")
            os.makedirs(log_dir, exist_ok=True)
            
            today_str = datetime.now().strftime("%m%d")
            if self._current_log_date != today_str:
                # 日期变化或首次设置，关闭旧文件，打开新文件
                if self._log_file_handle:
                    self._log_file_handle.close()
                
                log_filename = f"log_{datetime.now().strftime('%m%d%H%M%S')}.ytl"
                self._log_file_path = os.path.join(log_dir, log_filename)
                
                try:
                    self._log_file_handle = open(self._log_file_path, 'a', encoding='utf-8')
                    self._current_log_date = today_str
                    # 首次打开或新文件时，记录一条启动信息
                    self.output("debug_logger.py", LogLevel.INFO, f"日志文件已切换/创建: {log_filename}", fold_code="LOG_INIT")
                except Exception as e:
                    print(f"CRITICAL: 无法打开日志文件 {self._log_file_path}: {e}", file=sys.stderr)
                    self._log_file_handle = None # 确保文件句柄为None，避免后续写入失败
            
    def _close_log_file(self):
        """关闭日志文件句柄"""
        with self._log_lock:
            if self._log_file_handle:
                self._log_file_handle.close()
                self._log_file_handle = None
                print(f"INFO: 日志文件已关闭: {self._log_file_path}")
    
    def _get_timestamp(self) -> str:
        now = datetime.now()
        return now.strftime("%m%d-%H:%M:%S")
    
    def _get_source_file(self, source: Optional[str] = None) -> str:
        if source:
            return source
        import inspect
        frame = inspect.currentframe()
        try:
            if frame and frame.f_back:
                filename = frame.f_back.f_code.co_filename
                return os.path.basename(filename)
        finally:
            del frame
        return "unknown"
    
    def output(self, source: str, level: LogLevel, message: str, 
               fold_code: Optional[str] = None, remark: Optional[str] = None):
        # 检查当前等级是否达到最低输出要求
        if level.priority < self._min_level.priority:
            return
        
        # 检查是否需要轮换日志文件
        today_str = datetime.now().strftime("%m%d")
        if self._current_log_date != today_str:
            self._setup_log_file() # 重新设置日志文件，实现每日轮换
            
        timestamp = self._get_timestamp()
        source_file = self._get_source_file(source)
        level_str = level.value.upper()
        
        output_parts = [f"[{timestamp}][{level_str}][{source_file}]{message}"]
        
        if remark:
            output_parts.append(f"%{remark}%")
        
        if fold_code:
            output_parts.append(f"[{fold_code}]")
        
        output_line = "".join(output_parts)
        
        # 打印到控制台
        print(output_line)

        # 写入日志文件
        with self._log_lock:
            if self._log_file_handle:
                try:
                    self._log_file_handle.write(output_line + "\n")
                    self._log_file_handle.flush() # 立即写入磁盘
                except Exception as e:
                    print(f"ERROR: 写入日志文件失败: {e}", file=sys.stderr)
                    self._log_file_handle = None # 避免重复报错
    
    def debug(self, source: str, message: str, fold_code: Optional[str] = None, remark: Optional[str] = None):
        self.output(source, LogLevel.DEBUG, message, fold_code, remark)
    
    def info(self, source: str, message: str, fold_code: Optional[str] = None, remark: Optional[str] = None):
        self.output(source, LogLevel.INFO, message, fold_code, remark)
    
    def warning(self, source: str, message: str, fold_code: Optional[str] = None, remark: Optional[str] = None):
        self.output(source, LogLevel.WARNING, message, fold_code, remark)
    
    def error(self, source: str, message: str, fold_code: Optional[str] = None, remark: Optional[str] = None):
        self.output(source, LogLevel.ERROR, message, fold_code, remark)
    
    def critical(self, source: str, message: str, fold_code: Optional[str] = None, remark: Optional[str] = None):
        self.output(source, LogLevel.CRITICAL, message, fold_code, remark)


debug_logger = DebugLogger()
