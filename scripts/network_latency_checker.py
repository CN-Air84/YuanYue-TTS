# coding=utf-8
"""
网络延迟检测模块
用于检测百度和Github的网络延迟
"""

import time
import socket
import threading
from PyQt5.QtCore import QObject, pyqtSignal
from debug_logger import debug_logger, LogLevel


class NetworkLatencyChecker(QObject):
    """网络延迟检测器"""
    # 信号：延迟更新 (服务器名称, 延迟ms, 是否成功, 状态描述)
    latency_updated = pyqtSignal(str, int, bool, str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.check_thread = None
        
        # 测试目标
        self.targets = {
            'baidu': ('www.baidu.com', 80),
            'github': ('github.com', 443)
        }
        
    def start_checking(self, interval=30):
        """开始定期检测
        
        Args:
            interval: 检测间隔（秒），默认30秒
        """
        if self.is_running:
            debug_logger.output("network_latency_checker.py", LogLevel.WARNING, 
                              "延迟检测已在运行中", fold_code="NET_CHECK")
            return
            
        self.is_running = True
        self.check_thread = threading.Thread(
            target=self._check_loop, 
            args=(interval,), 
            daemon=True
        )
        self.check_thread.start()
        debug_logger.output("network_latency_checker.py", LogLevel.INFO, 
                          f"开始网络延迟检测，间隔 {interval} 秒", fold_code="NET_CHECK")
    
    def stop_checking(self):
        """停止检测"""
        self.is_running = False
        if self.check_thread:
            self.check_thread.join(timeout=2)
        debug_logger.output("network_latency_checker.py", LogLevel.INFO, 
                          "停止网络延迟检测", fold_code="NET_CHECK")
    
    def check_once(self):
        """立即执行一次检测"""
        threading.Thread(target=self._perform_checks, daemon=True).start()
    
    def _check_loop(self, interval):
        """检测循环"""
        while self.is_running:
            self._perform_checks()
            # 分段睡眠，以便快速响应停止信号
            for _ in range(interval):
                if not self.is_running:
                    break
                time.sleep(1)
    
    def _perform_checks(self):
        """执行一次完整检测"""
        for name, (host, port) in self.targets.items():
            latency, success, status = self._check_latency(host, port)
            self.latency_updated.emit(name, latency, success, status)
            debug_logger.output("network_latency_checker.py", LogLevel.DEBUG, 
                              f"{name} 延迟: {latency}ms (成功: {success}, 状态: {status})", 
                              fold_code="NET_CHECK")
    
    def _check_latency(self, host, port, timeout=5):
        """检测单个目标的延迟
        
        Args:
            host: 主机名
            port: 端口号
            timeout: 超时时间（秒）
            
        Returns:
            (延迟ms, 是否成功, 状态描述)
        """
        try:
            start_time = time.time()
            
            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # 尝试连接
            sock.connect((host, port))
            
            # 计算延迟
            latency = int((time.time() - start_time) * 1000)
            
            sock.close()
            return latency, True, "正常"
            
        except socket.timeout:
            debug_logger.output("network_latency_checker.py", LogLevel.WARNING, 
                              f"连接 {host}:{port} 超时", fold_code="NET_CHECK")
            return 999, False, "超时"
            
        except socket.gaierror:
            debug_logger.output("network_latency_checker.py", LogLevel.ERROR, 
                              f"无法解析主机名 {host}", fold_code="NET_CHECK")
            return 999, False, "DNS错误"
            
        except Exception as e:
            debug_logger.output("network_latency_checker.py", LogLevel.ERROR, 
                              f"检测 {host}:{port} 时出错: {str(e)}", fold_code="NET_CHECK")
            return 999, False, f"错误"
