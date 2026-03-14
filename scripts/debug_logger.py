import sys
import os
import struct
import mmap
import platform
import atexit
import re
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
        
        # 初始化文件日志和共享内存
        self._start_time = datetime.now()
        self._log_file = None
        self._shm_file = None
        self._shm_map = None
        self._shm_size = 1024 * 1024 # 1MB
        self._header_size = 16
        
        self._init_file_logging()
        self._init_shared_memory()
        
        atexit.register(self._cleanup)

    def _init_file_logging(self):
        try:
            # 创建日志文件名：log_月日时分秒.ytl
            timestamp = self._start_time.strftime("%m%d%H%M%S")
            
            # 没有目录就创建一个
            base_path = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base_path, 'cache', 'log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            self._log_filename = os.path.join(log_dir, f"log_{timestamp}.ytl")
            
            # 获取版本信息
            version = self._get_version_safe()
            
            # 获取系统信息
            sys_info = f"Windows {platform.version()} {platform.win32_edition()} {platform.win32_ver()[1]}"
            try:
                # 试着获取更详细的系统信息
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                product_name = winreg.QueryValueEx(key, "ProductName")[0]
                display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
                current_build = winreg.QueryValueEx(key, "CurrentBuild")[0]
                sys_info = f"Windows {product_name} {display_version} {current_build}"
            except:
                pass
                
            prog_path = os.path.abspath(sys.argv[0])
            
            self._log_file = open(self._log_filename, "w", encoding="utf-8")
            
            # 写日志头
            # 日志头格式：[YuanyueGeneralLogger {起始时间}-{结束时间}]
            # 退出时更新结束时间
            # 这块有点毛病 回头再改吧
            self._header_line = f"[YuanyueGeneralLogger {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}-...]"
            self._log_file.write(f"{self._header_line}\n")
            self._log_file.write(f"[YuanyueTTS {version}]\n")
            self._log_file.write(f"[{sys_info}]\n")
            self._log_file.write(f"[{prog_path}]\n")
            self._log_file.flush()
            
        except Exception as e:
            print(f"Failed to init file logging: {e}")

    def _get_version_safe(self):
        try:
            # 直接读取 main_window.py 避免循环导入
            base_path = os.path.dirname(os.path.abspath(__file__))
            main_window_path = os.path.join(base_path, "main_window.py")
            if os.path.exists(main_window_path):
                with open(main_window_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    match = re.search(r"self\.this_version\s*=\s*'''(.*?)'''", content)
                    if match:
                        return match.group(1)
        except:
            pass
        return "Unknown"

    def _init_shared_memory(self):
        try:
            base_path = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_path, 'cache')
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            shm_path = os.path.join(cache_dir, "YuanyueDebugLog.dat")
            if not os.path.exists(shm_path):
                with open(shm_path, "wb") as f:
                    f.write(b'\x00' * self._shm_size)
            
            self._shm_file = open(shm_path, "r+b")
            self._shm_map = mmap.mmap(self._shm_file.fileno(), self._shm_size)
            
            # 需要的话初始化头
            self._shm_map.seek(0)
            magic = self._shm_map.read(4)
            if magic != b'YLOG':
                self._shm_map.seek(0)
                self._shm_map.write(b'YLOG')  # 魔数
                self._shm_map.write(struct.pack('I', self._header_size))  # 写入位置（初始化为头大小）
                self._shm_map.write(b'\x00' * 8)  # 预留
                self._shm_map.flush()
                
        except Exception as e:
            print(f"Failed to init shared memory: {e}")

    def _cleanup(self):
        if self._log_file:
                # 想更新结束时间，但很难改第一行，算了直接关掉
                # 来来来都看一看嗷AI消极怠工了 哎呀回头再说
            try:
                self._log_file.close()
            except:
                pass
        
        if self._shm_map:
            try:
                self._shm_map.close()
            except:
                pass
        if self._shm_file:
            try:
                self._shm_file.close()
            except:
                pass

    def _write_shm(self, message: str):
        if not self._shm_map:
            return
            
        try:
            msg_bytes = message.encode('utf-8')
            msg_len = len(msg_bytes)
            
            # 读取当前写入位置
            self._shm_map.seek(4)
            write_pos = struct.unpack('I', self._shm_map.read(4))[0]
            
            # 检查边界
            if write_pos + 2 + msg_len > self._shm_size:
                write_pos = self._header_size  # 超过容量就回到开头
            
            # 写入长度
            self._shm_map.seek(write_pos)
            self._shm_map.write(struct.pack('H', msg_len))
            
            # 写入消息
            self._shm_map.write(msg_bytes)
            
            # 更新写入位置
            new_pos = write_pos + 2 + msg_len
            self._shm_map.seek(4)
            self._shm_map.write(struct.pack('I', new_pos))
            
        except Exception as e:
            pass
    
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
        
        timestamp = self._get_timestamp()
        source_file = self._get_source_file(source)
        level_str = level.value.upper()
        
        output_parts = [f"[{timestamp}][{level_str}][{source_file}]{message}"]
        
        if remark:
            output_parts.append(f"%{remark}%")
        
        if fold_code:
            output_parts.append(f"[{fold_code}]")
        
        output_line = "".join(output_parts)
        
        # 不管什么等级都写入文件和共享内存，监控工具需要所有日志
        # 控制台输出则遵守等级筛选
        
        if self._log_file:
            try:
                self._log_file.write(output_line + "\n")
                self._log_file.flush()
            except:
                pass
        
        self._write_shm(output_line)

        # 控制台输出遵守等级筛选
        if level.priority >= self._min_level.priority:
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
