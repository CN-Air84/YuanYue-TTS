# coding=utf-8
import atexit
import os
import sys
import threading
from datetime import datetime
from enum import Enum
from typing import Optional

try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
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
        priorities = {
            "debug": 10,
            "info": 20,
            "warning": 30,
            "error": 40,
            "critical": 50,
        }
        return priorities.get(self.value, 0)


class DebugLogger:
    _instance = None
    _log_file_handle = None
    _current_log_date = None
    _log_lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DebugLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._min_level = LogLevel.WARNING
        self._buffer_mode = True
        self._buffer = []
        self._log_file_path = None
        self._setup_encoding()
        self._setup_log_file()
        atexit.register(self._close_log_file)

    def set_level(self, level: LogLevel):
        """设置最低输出等级，低于此等级的日志将不会打印。"""
        self._min_level = level
        self.output("debug_logger.py", LogLevel.INFO, f"日志输出等级已设置为: {level.value.upper()}")

    def flush_buffer(self):
        """关闭缓冲模式并一次性落盘启动期日志。"""
        with self._log_lock:
            if not self._buffer_mode:
                return

            if self._log_file_handle is None:
                self._setup_log_file()

            if self._log_file_handle is None:
                return

            if self._buffer:
                self._log_file_handle.write("\n".join(self._buffer) + "\n")
                self._log_file_handle.flush()
                self._buffer.clear()

            self._buffer_mode = False

    def _setup_encoding(self):
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        if sys.platform.startswith('win'):
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')

    def _setup_log_file(self):
        """设置日志文件路径并打开文件。"""
        with self._log_lock:
            log_dir = os.path.join(get_app_base_path(), "cache", "log")
            os.makedirs(log_dir, exist_ok=True)

            today_str = datetime.now().strftime("%m%d")
            if self._current_log_date == today_str and self._log_file_handle is not None:
                return

            if self._log_file_handle:
                self._log_file_handle.close()
                self._log_file_handle = None

            log_filename = f"log_{datetime.now().strftime('%m%d%H%M%S')}.ytl"
            self._log_file_path = os.path.join(log_dir, log_filename)

            try:
                self._log_file_handle = open(self._log_file_path, 'a', encoding='utf-8')
                self._current_log_date = today_str
            except Exception as e:
                print(f"CRITICAL: 无法打开日志文件 {self._log_file_path}: {e}", file=sys.stderr)
                self._log_file_handle = None

    def _close_log_file(self):
        """关闭日志文件句柄。"""
        with self._log_lock:
            if self._buffer_mode:
                self.flush_buffer()

            if self._log_file_handle:
                self._log_file_handle.close()
                self._log_file_handle = None
                if self._log_file_path:
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
        if level.priority < self._min_level.priority:
            return

        today_str = datetime.now().strftime("%m%d")
        if self._current_log_date != today_str:
            self._setup_log_file()

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

        with self._log_lock:
            if self._buffer_mode:
                self._buffer.append(output_line)
                return

            if self._log_file_handle:
                try:
                    self._log_file_handle.write(output_line + "\n")
                    self._log_file_handle.flush()
                except Exception as e:
                    print(f"ERROR: 写入日志文件失败: {e}", file=sys.stderr)
                    self._log_file_handle = None

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
