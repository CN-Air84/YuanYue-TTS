import sys
import os
from datetime import datetime
from enum import Enum
from typing import Optional


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
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DebugLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._min_level = LogLevel.INFO  # 默认筛选等级为 WARNING
        self._setup_encoding()
    
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
            
        timestamp = self._get_timestamp()
        source_file = self._get_source_file(source)
        level_str = level.value.upper()
        
        output_parts = [f"[{timestamp}][{level_str}][{source_file}]{message}"]
        
        if remark:
            output_parts.append(f"%{remark}%")
        
        if fold_code:
            output_parts.append(f"[{fold_code}]")
        
        output_line = "".join(output_parts)
        print(output_line)
    
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
