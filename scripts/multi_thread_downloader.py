import os
import sys
import threading
import time
import ssl
import requests
import math
from pathlib import Path
from typing import Optional, Callable, Dict, List
from datetime import datetime
import hashlib

from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QProgressBar, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QObject
from PyQt5.QtGui import QFont
from misc_func import SettingsManager
from debug_logger import debug_logger, LogLevel

#此程序负责多线程下载器具体实现
#杂项页面内的多线程下载器对话框详见带mp前缀的mp_multi_thread_download.py

# 禁用SSL验证警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==================== 下载工作线程 ====================

class DownloadWorker(QThread):
    """下载工作线程"""
    
    progress_updated = pyqtSignal(float)  # 总进度信号
    thread_progress_updated = pyqtSignal(int, float)  # 线程进度信号 (线程ID, 进度值)
    finished_signal = pyqtSignal(bool)    # 完成信号
    error_occurred = pyqtSignal(str)      # 错误信号
    file_info_updated = pyqtSignal(int)   # 文件大小信息信号
    def __init__(self, url: str, save_dir: str, filename: str, thread_num: int = 4,
                 user_agent: Optional[str] = None, verify_ssl: bool = True,
                 proxy: Optional[dict] = None, speed_monitor=None,
                 referer: Optional[str] = None):
        """初始化工作线程"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "初始化下载工作线程", fold_code="MT_INIT")
        super().__init__()
        self.setTerminationEnabled(False)
        # 对包含非ASCII字符的URL进行编码
        if any(ord(c) > 127 for c in url):
            from urllib.parse import quote, urlparse, urlunparse
            parsed = urlparse(url)
            path = quote(parsed.path)
            query = quote(parsed.query, safe='=&')
            url = urlunparse(parsed._replace(path=path, query=query))
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"URL已编码: {url}", fold_code="MT_INIT")
        
        self.url = url
        self.save_dir = save_dir
        self.filename = filename
        self.thread_num = max(1, thread_num)
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.referer = referer
        self.verify_ssl = verify_ssl
        self.proxy = proxy or {}
        self.speed_monitor = speed_monitor
        self.is_canceled = False
        self._is_running = False
        self._run_lock = threading.Lock()
        self._is_finished = False
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"下载参数: URL={url[:50]}..., 保存目录={save_dir}, 文件名={filename}, thread_num={self.thread_num}", fold_code="MT_INIT")
        # 文件信息
        self.file_size = 0
        self.support_range = False
        
        # 下载状态
        self.download_threads = []
        self.temp_files = []
        self.downloaded_size = 0
        self.lock = threading.Lock()
        
        # 创建保存目录（支持中文路径）
        self.save_path = Path(save_dir) / filename
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"保存路径已创建: {self.save_path}", fold_code="MT_INIT")
    
    def _get_file_info(self):
        """获取文件信息"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始获取文件信息", fold_code="MT_INFO")
        try:
            headers = {'User-Agent': self.user_agent}
            if self.referer:
                headers['Referer'] = self.referer
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"发送HEAD请求到: {self.url}", fold_code="MT_INFO")
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"验证SSL: {self.verify_ssl}", fold_code="MT_INFO")
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"代理配置: {self.proxy}", fold_code="MT_INFO")
            
            response = requests.head(
                self.url, 
                headers=headers, 
                verify=self.verify_ssl,
                timeout=10,
                allow_redirects=True,
                proxies=self.proxy
            )
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"HEAD请求状态码: {response.status_code}", fold_code="MT_INFO")
            response.raise_for_status()
            
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"HEAD请求响应头: {dict(response.headers)}", fold_code="MT_INFO")
            
            # 检查是否支持断点续传
            if 'accept-ranges' in response.headers and \
               response.headers['accept-ranges'].lower() == 'bytes':
                self.support_range = True
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "支持断点续传", fold_code="MT_INFO")
            else:
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "不支持断点续传", fold_code="MT_INFO")
                
            # 获取文件大小
            if 'content-length' in response.headers:
                self.file_size = int(response.headers['content-length'])
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"获取文件大小: {self.file_size} 字节", fold_code="MT_INFO")
            else:
                # 如果不支持获取大小，使用单线程下载
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "无法通过HEAD请求获取文件大小，尝试GET请求", fold_code="MT_INFO")
                response = requests.get(
                    self.url, 
                    headers=headers, 
                    verify=self.verify_ssl,
                    stream=True,
                    timeout=10,
                    allow_redirects=True,
                    proxies=self.proxy
                )
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"GET请求状态码: {response.status_code}", fold_code="MT_INFO")
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"GET请求响应头: {dict(response.headers)}", fold_code="MT_INFO")
                self.file_size = int(response.headers.get('content-length', 0))
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"获取文件大小: {self.file_size} 字节", fold_code="MT_INFO")
                response.close()
                
            if self.file_size == 0:
                self.support_range = False
                self.thread_num = 1
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "文件大小为0，使用单线程下载", fold_code="MT_INFO")
            
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "文件信息获取成功", fold_code="MT_INFO")
            # 发送文件大小信息
            self.file_info_updated.emit(self.file_size)
            return True
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求异常: {str(e)}"
            debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, error_msg, fold_code="MT_INFO")
            debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, f"异常类型: {type(e).__name__}", fold_code="MT_INFO")
            import traceback
            traceback.print_exc()
            
            self.error_occurred.emit(error_msg)
            return False
        except Exception as e:
            error_msg = f"无法获取文件信息: {str(e)}"
            debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, error_msg, fold_code="MT_INFO")
            debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, f"异常类型: {type(e).__name__}", fold_code="MT_INFO")
            import traceback
            traceback.print_exc()
            
            self.error_occurred.emit(error_msg)
            return False
    
    def _calculate_ranges(self):
        """计算每个线程的下载范围"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始计算下载范围", fold_code="MT_RANGE")
        if not self.support_range or self.thread_num <= 1:
            # 单线程下载整个文件
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "不支持Range或线程数为1，使用单线程下载", fold_code="MT_RANGE")
            return [(0, self.file_size - 1 if self.file_size > 0 else None)]
        
        chunk_size = math.ceil(self.file_size / self.thread_num)
        ranges = []
        
        for i in range(self.thread_num):
            start = i * chunk_size
            end = min(start + chunk_size - 1, self.file_size - 1)
            if start < self.file_size:
                ranges.append((start, end))
                
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"计算完成，共分为 {len(ranges)} 个块", fold_code="MT_RANGE")
        return ranges
    
    def _create_temp_filename(self, index: int) -> str:
        """创建临时文件名"""
        file_key = hashlib.md5(str(self.save_path).encode('utf-8')).hexdigest()
        temp_name = str(self.save_path.parent / f".{file_key}_part{index}.tmp")
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"创建临时文件名: {temp_name}", fold_code="MT_TMP")
        return temp_name
    
    def download_chunk(self, thread_id: int, start_pos: int, end_pos: int):
        """下载文件块"""
        temp_file = self._create_temp_filename(thread_id)
        self.temp_files.append(temp_file)
        
        headers = {'User-Agent': self.user_agent}
        if self.referer:
            headers['Referer'] = self.referer
        if end_pos is not None:
            headers['Range'] = f'bytes={start_pos}-{end_pos}'
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"线程{thread_id}: 开始下载文件块 {start_pos}-{end_pos}", fold_code="MT_DL")
            # 计算此线程负责的文件块大小
            chunk_size_total = end_pos - start_pos + 1
        else:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"线程{thread_id}: 开始下载整个文件", fold_code="MT_DL")
            chunk_size_total = self.file_size
        
        try:
            response = requests.get(
                self.url,
                headers=headers,
                verify=self.verify_ssl,
                stream=True,
                timeout=30,
                proxies=self.proxy
            )
            response.raise_for_status()
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"线程{thread_id}: 成功连接到服务器, 状态码: {response.status_code}", fold_code="MT_DL")
            
            with open(temp_file, 'wb') as f:
                total_written = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if self.is_canceled:
                        debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, f"线程{thread_id}: 收到取消信号，停止下载", fold_code="MT_DL")
                        break
                    
                    if chunk:
                        f.write(chunk)
                        chunk_size = len(chunk)
                        total_written += chunk_size
                        
                        # 更新下载量
                        with self.lock:
                            self.downloaded_size += chunk_size
                        
                        # 更新速度监控
                        if self.speed_monitor:
                            self.speed_monitor.update_thread(thread_id, chunk_size)
                        
                        # 发送总进度信号
                        if self.file_size > 0 and hasattr(self, 'progress_updated'):
                            progress = (self.downloaded_size / self.file_size) * 100
                            self.progress_updated.emit(progress)
                        
                        # 发送线程进度信号
                        if chunk_size_total > 0 and hasattr(self, 'thread_progress_updated'):
                            thread_progress = (total_written / chunk_size_total) * 100
                            self.thread_progress_updated.emit(thread_id, thread_progress)
            
            if not self.is_canceled:
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"线程{thread_id}: 完成下载文件块，共写入 {total_written} 字节", fold_code="MT_DL")
                return True
            
        except Exception as e:
            if not self.is_canceled:
                debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, f"线程{thread_id}: 下载失败 - {str(e)}", fold_code="MT_DL")
                if hasattr(self, 'error_occurred'):
                    self.error_occurred.emit(f"线程{thread_id}下载失败: {str(e)}")
            return False
            
        finally:
            if 'response' in locals():
                response.close()
        
        return False
    
    def _merge_files(self):
        """合并临时文件"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始合并临时文件", fold_code="MT_MERGE")
        try:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"打开输出文件: {self.save_path}", fold_code="MT_MERGE")
            with open(self.save_path, 'wb') as outfile:
                for i, temp_file in enumerate(self.temp_files):
                    if os.path.exists(temp_file):
                        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"合并第{i+1}/{len(self.temp_files)}个临时文件: {temp_file}", fold_code="MT_MERGE")
                        with open(temp_file, 'rb') as infile:
                            outfile.write(infile.read())
                        # 删除临时文件
                        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"删除临时文件: {temp_file}", fold_code="MT_MERGE")
                        os.remove(temp_file)
                    else:
                        debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, f"临时文件不存在: {temp_file}", fold_code="MT_MERGE")
            
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"文件合并完成，保存到: {self.save_path}", fold_code="MT_MERGE")
            return True
            
        except Exception as e:
            error_msg = f"合并文件失败: {str(e)}"
            debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, error_msg, fold_code="MT_MERGE")
            raise Exception(error_msg)
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始清理临时文件", fold_code="MT_CLEAN")
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"已清理临时文件: {temp_file}", fold_code="MT_CLEAN")
                except Exception as e:
                    debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, f"清理临时文件失败 {temp_file}: {str(e)}", fold_code="MT_CLEAN")
    
    def cancel_download(self):
        """取消下载"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "收到取消下载请求", fold_code="MT_CANCEL")
        self.is_canceled = True
        self._cleanup_temp_files()
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "取消下载完成", fold_code="MT_CANCEL")
    
    def is_running(self):
        """检查线程是否正在运行"""
        with self._run_lock:
            return self._is_running
    
    def is_finished(self):
        """检查线程是否已完成"""
        with self._run_lock:
            return self._is_finished
    
    def run(self):
        """线程执行函数"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "下载线程开始执行", fold_code="MT_RUN")
        
        with self._run_lock:
            self._is_running = True
            self._is_finished = False
        
        try:
            # 获取文件信息
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始获取文件信息", fold_code="MT_RUN")
            if not self._get_file_info():
                debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, "获取文件信息失败", fold_code="MT_RUN")
                if hasattr(self, 'finished_signal'):
                    self.finished_signal.emit(False)
                return
            
            # 计算下载范围
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始计算下载范围", fold_code="MT_RUN")
            ranges = self._calculate_ranges()
            self.thread_num = len(ranges)
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"计算完成，共分 {self.thread_num} 个文件块", fold_code="MT_RUN")
            
            # 创建下载线程
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始创建下载线程", fold_code="MT_RUN")
            self.download_threads = []
            for i, (start, end) in enumerate(ranges):
                thread_id = i + 1  # 线程ID从1开始
                thread = threading.Thread(
                    target=self.download_chunk,
                    args=(thread_id, start, end),
                    daemon=True
                )
                self.download_threads.append(thread)
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"完成创建 {len(self.download_threads)} 个下载线程", fold_code="MT_RUN")
            
            # 启动所有线程
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始启动所有下载线程", fold_code="MT_RUN")
            for thread in self.download_threads:
                thread.start()
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "所有下载线程已启动", fold_code="MT_RUN")
            
            # 等待所有线程完成
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始等待所有下载线程完成", fold_code="MT_RUN")
            for thread in self.download_threads:
                thread.join()
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "所有下载线程已完成", fold_code="MT_RUN")
            
            # 检查是否取消
            if self.is_canceled:
                debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "下载已被取消", fold_code="MT_RUN")
                self._cleanup_temp_files()
                if hasattr(self, 'finished_signal'):
                    self.finished_signal.emit(False)
                return
            
            # 合并文件
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始合并临时文件", fold_code="MT_RUN")
            self._merge_files()
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "文件合并完成", fold_code="MT_RUN")
            
            # 发送完成信号
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "下载完成，发送完成信号", fold_code="MT_RUN")
            if hasattr(self, 'finished_signal'):
                self.finished_signal.emit(True)
                
        except Exception as e:
            debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, f"下载过程中发生异常: {str(e)}", fold_code="MT_RUN")
            self._cleanup_temp_files()
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(f"下载异常: {str(e)}")
            if hasattr(self, 'finished_signal'):
                self.finished_signal.emit(False)
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "异常处理完成", fold_code="MT_RUN")
        finally:
            with self._run_lock:
                self._is_running = False
                self._is_finished = True
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"下载线程执行完成，状态: _is_running={self._is_running}, _is_finished={self._is_finished}", fold_code="MT_RUN")


# ==================== Qt界面部分 ====================

class SpeedMonitor(QObject):
        """速度监控类"""
        speed_updated = pyqtSignal(list, float)  # 线程速度列表, 总速度
        
        def __init__(self, thread_num: int, parent=None):
            super().__init__(parent)
            self.thread_num = thread_num
            self.thread_data = {i: [0, 0, datetime.now()] for i in range(1, thread_num + 1)}  # 线程ID从1开始，[当前下载量, 上一次下载量, 上一次时间]
            self.total_downloaded = 0
            self.last_total = 0
            self.last_time = datetime.now()
            self.lock = threading.Lock()
        
        def update_thread(self, thread_id: int, size: int):
            """更新线程下载数据"""
            with self.lock:
                self.thread_data[thread_id][0] += size
                self.total_downloaded += size
        
        def calculate_speed(self):
            """计算速度"""
            current_time = datetime.now()
            interval = (current_time - self.last_time).total_seconds()
            if interval < 0.1:
                self.speed_updated.emit([0.0] * self.thread_num, 0.0)
                return
            
            thread_speeds = []
            with self.lock:
                for tid in range(1, self.thread_num + 1):
                    current_size, last_size, last_time = self.thread_data[tid]
                    time_diff = (current_time - last_time).total_seconds() or 0.1
                    speed = (current_size - last_size) / (1024 * 1024) / time_diff
                    thread_speeds.append(round(speed, 2))
                    # 更新上一次下载量和时间
                    self.thread_data[tid][1] = current_size
                    self.thread_data[tid][2] = current_time
                
                total_speed = (self.total_downloaded - self.last_total) / (1024 * 1024) / interval
                total_speed = round(total_speed, 2)
                
                self.last_total = self.total_downloaded
                self.last_time = current_time
            
            self.speed_updated.emit(thread_speeds, total_speed)


class ProgressWindow(QWidget):
        """下载进度窗口"""
        cancel_clicked = pyqtSignal()
        
        def __init__(self, thread_num: int, parent=None):
            super().__init__(parent)
            self.thread_num = thread_num
            self.file_size = 0  # 文件大小
            
            # 设置窗口标志
            self.setWindowFlags(
                Qt.WindowStaysOnTopHint | 
                Qt.WindowCloseButtonHint |
                Qt.WindowSystemMenuHint |
                Qt.WindowTitleHint
            )
            
            # 加载设置
            self.settings_manager = SettingsManager()
            self.background_color = self._get_background_color()
            self.global_font = self._get_global_font()
            
            self.init_ui()
        
        def _get_background_color(self):
            """获取背景颜色"""
            if not self.settings_manager:
                return "#E5E8EF"  # 默认颜色
            return self.settings_manager.get_Custom_value('background_color', '#E5E8EF')
        
        def _get_global_font(self):
            """获取全局字体"""
            if not self.settings_manager:
                return QFont("微软雅黑", 11)
            font_family = self.settings_manager.get_Custom_value('global_font', '微软雅黑')
            return QFont(font_family, 11)
        
        def init_ui(self):
            """初始化UI"""
            self.setWindowTitle("下载进度")
            self.setFixedSize(450, 200)
            
            # 应用背景颜色
            self.setStyleSheet(f"""
                QDialog {{ background-color: {self.background_color}; }}
                QLabel {{ background-color: transparent; }}
            """)
            
            # 布局
            layout = QVBoxLayout()
            layout.setSpacing(10)
            layout.setContentsMargins(15, 20, 15, 20)
            
            # 总进度条
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("0.0%") 
            self.progress_bar.setAlignment(Qt.AlignCenter) 
            self.progress_bar.setFont(self.global_font)
            layout.addWidget(self.progress_bar)
            
            # 总速度
            self.total_speed_label = QLabel("总速度: 0.0 MB/s")
            self.total_speed_label.setFont(self.global_font)
            self.total_speed_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.total_speed_label)
            
            # 文件大小显示
            self.file_size_label = QLabel("文件大小: 0 MB")
            self.file_size_label.setFont(self.global_font)
            self.file_size_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.file_size_label)
            
            # 线程进度条总布局
            self.threads_container_layout = QVBoxLayout()
            self.threads_container_layout.setSpacing(5)
            layout.addLayout(self.threads_container_layout)

            # 取消下载按钮
            self.cancel_btn = QPushButton("取消下载")
            self.cancel_btn.setFont(self.global_font)
            self.cancel_btn.setMinimumHeight(35)
            self.cancel_btn.clicked.connect(self.on_cancel)
            layout.addWidget(self.cancel_btn, alignment=Qt.AlignCenter)
            
            self.setLayout(layout)
            
            # 居中显示
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.center() - self.rect().center())
            
        def set_file_size(self, size_bytes: int):
            """设置并显示文件大小"""
            self.file_size = size_bytes
            # 格式化文件大小显示
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            self.file_size_label.setText(f"文件大小: {size_str}")
        
        @pyqtSlot(float)
        def update_progress(self, progress: float):
            """更新总进度"""
            self.progress_bar.setValue(int(progress))
            self.progress_bar.setFormat(f"{progress:.1f}%")  # 更新进度条中的百分比
        
        @pyqtSlot(list, float)
        def update_speed(self, thread_speeds: list, total_speed: float):
            """更新速度"""
            self.total_speed_label.setText(f"总速度: {total_speed} MB/s")

        
        @pyqtSlot(int, float)
        def update_thread_progress(self, thread_id: int, progress: float):
            """更新线程进度"""
            pass
        
        def on_cancel(self):
            """取消下载"""
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "用户点击取消下载按钮", fold_code="UI_CANCEL")
            self.cancel_clicked.emit()
            self.close()


# ==================== 主要接口类 ====================

class MultiThreadDownloader:
    """对外接口类"""
    
    def __init__(self, url: str, save_dir: str, filename: str, thread_num: int = 4,
                 user_agent: Optional[str] = None, verify_ssl: bool = True,
                 progress_callback: Optional[Callable[[float], None]] = None,
                 proxy: Optional[dict] = None, referer: Optional[str] = None):
        """
        初始化下载器
        
        Args:
            url: 下载链接
            save_dir: 保存目录
            filename: 文件名
            thread_num: 线程数
            user_agent: 自定义User-Agent
            verify_ssl: SSL验证
            progress_callback: 进度回调函数
            proxy: 代理配置
            referer: 自定义Referer
        """
        self.url = url
        self.save_dir = save_dir
        self.filename = filename
        self.thread_num = thread_num
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl
        self.progress_callback = progress_callback
        self.proxy = proxy
        self.referer = referer
        
        # Qt相关
        self.app = None
        self.progress_window = None
        self.speed_monitor = None
        self.download_worker = None
        self.success = False
        self.is_finished = False  # 下载是否完成
    
    def _init_qt(self):
        """初始化Qt环境"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "初始化Qt环境", fold_code="MTD_INIT")
        if not QApplication.instance():
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "创建新的QApplication实例", fold_code="MTD_INIT")
            self.app = QApplication(sys.argv)
        else:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "使用现有的QApplication实例", fold_code="MTD_INIT")
            self.app = QApplication.instance()
        
        # 创建速度监控
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"创建速度监控，线程数={self.thread_num}", fold_code="MTD_INIT")
        self.speed_monitor = SpeedMonitor(self.thread_num)
        
        # 创建进度窗口
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "创建进度窗口", fold_code="MTD_INIT")
        self.progress_window = ProgressWindow(self.thread_num)
        
        # 创建下载工作线程
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "创建下载工作线程", fold_code="MTD_INIT")
        self.download_worker = DownloadWorker(
            url=self.url,
            save_dir=self.save_dir,
            filename=self.filename,
            thread_num=self.thread_num,
            user_agent=self.user_agent,
            verify_ssl=self.verify_ssl,
            proxy=self.proxy,
            speed_monitor=self.speed_monitor,
            referer=self.referer
        )
        # 不设置父对象，由MultiThreadDownloader直接管理生命周期
        
        # 连接信号槽
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "连接信号槽", fold_code="MTD_INIT")
        self.download_worker.progress_updated.connect(self.progress_window.update_progress)
        if self.progress_callback:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "连接外部进度回调", fold_code="MTD_INIT")
            self.download_worker.progress_updated.connect(self.progress_callback)
        
        # 连接文件大小信号
        if hasattr(self.download_worker, 'file_info_updated'):
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "连接文件大小更新信号", fold_code="MTD_INIT")
            self.download_worker.file_info_updated.connect(self.progress_window.set_file_size)
        
        # 连接线程进度信号
        if hasattr(self.download_worker, 'thread_progress_updated'):
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "连接线程进度更新信号", fold_code="MTD_INIT")
            self.download_worker.thread_progress_updated.connect(self.progress_window.update_thread_progress)
        
        self.speed_monitor.speed_updated.connect(self.progress_window.update_speed)
        self.progress_window.cancel_clicked.connect(self.download_worker.cancel_download)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.error_occurred.connect(self._on_error)
        
        # 定时计算速度
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "启动速度监控定时器", fold_code="MTD_INIT")
        self.speed_timer = QTimer()
        self.speed_timer.timeout.connect(self.speed_monitor.calculate_speed)
        self.speed_timer.start(1000)
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "Qt环境和信号连接完成", fold_code="MTD_INIT")
    
    def _on_download_finished(self, success: bool):
        """下载完成回调"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"收到下载完成信号，结果: {'成功' if success else '失败'}", fold_code="MTD_FIN")
        self.success = success
        self.is_finished = True  # 设置下载完成标志
        
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "停止速度监控计时器", fold_code="MTD_FIN")
        self.speed_timer.stop()
        
        # 确保线程完成后再清理资源和关闭窗口
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始清理资源", fold_code="MTD_FIN")
        
        # 先关闭进度窗口
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "立即关闭进度窗口", fold_code="MTD_FIN")
        if hasattr(self, 'progress_window') and self.progress_window:
            self.progress_window.close()
            self.progress_window = None
        
        if hasattr(self, 'download_worker') and self.download_worker:
            # 等待线程完成
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "等待下载线程完成", fold_code="MTD_FIN")
            # 设置最大等待时间为5秒，避免无限等待
            self.download_worker.wait(5000)
            
            # 额外检查线程状态
            if self.download_worker.is_running():
                debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, "线程仍在运行，尝试强制终止", fold_code="MTD_FIN")
                self.download_worker.terminate()
                self.download_worker.wait(2000)
            # 清理引用
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "清理下载线程引用", fold_code="MTD_FIN")
            self.download_worker = None
        
        # 最后显示消息框
        if success:
            filepath = os.path.join(self.save_dir, self.filename)
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"下载成功，文件路径: {filepath}", fold_code="MTD_FIN")

        else:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "下载失败或已取消", fold_code="MTD_FIN")
        
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "资源清理完成", fold_code="MTD_FIN")
    
    def _on_error(self, error_msg: str):
        """错误回调"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, f"收到错误信号: {error_msg}", fold_code="MTD_ERR")
        self.success = False
        self.is_finished = True  # 设置下载完成标志
        
        # 取消下载
        if hasattr(self, 'download_worker') and self.download_worker:
            self.download_worker.cancel_download()
        
        # 停止速度监控计时器
        if hasattr(self, 'speed_timer') and self.speed_timer:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "停止速度监控计时器", fold_code="MTD_ERR")
            self.speed_timer.stop()
        
        # 确保线程完成后再清理资源和关闭窗口
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始清理资源", fold_code="MTD_ERR")
        if hasattr(self, 'download_worker') and self.download_worker:
            # 等待线程完成
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "等待下载线程完成", fold_code="MTD_ERR")
            self.download_worker.wait(5000)
            
            # 额外检查线程状态
            if self.download_worker.is_running():
                debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, "线程仍在运行，尝试强制终止", fold_code="MTD_ERR")
                self.download_worker.terminate()
                self.download_worker.wait(2000)
            # 清理引用
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "清理下载线程引用", fold_code="MTD_ERR")
            self.download_worker = None
        
        # 关闭进度窗口
        if hasattr(self, 'progress_window') and self.progress_window:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "关闭进度窗口", fold_code="MTD_ERR")
            self.progress_window.close()
            self.progress_window = None
            
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "资源清理完成", fold_code="MTD_ERR")
    
    def start(self) -> bool:
        """启动下载（GUI模式）"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始启动下载", fold_code="MTD_START")
        
        # 初始化Qt
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "初始化Qt环境", fold_code="MTD_START")
        self._init_qt()
        
        # 显示进度窗口
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "显示下载进度窗口", fold_code="MTD_START")
        self.progress_window.show()
        
        # 启动下载线程
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "启动下载工作线程", fold_code="MTD_START")
        self.download_worker.start()
        
        # 等待下载完成，同时处理Qt事件保持GUI响应
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "开始等待下载完成", fold_code="MTD_START")
        while not self.is_finished:
            # 处理Qt事件，保持GUI响应
            if self.app:
                self.app.processEvents()
            # 短暂休眠，避免CPU占用过高
            time.sleep(0.1)
        
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"下载完成，返回结果: {self.success}", fold_code="MTD_START")
        return self.success
    
    def _start_cli(self) -> bool:
        """命令行模式下载"""
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"开始下载: {self.filename}")
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"URL: {self.url}")
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"保存到: {self.save_dir}")
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"线程数: {self.thread_num}")
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "-" * 50)
        
        # 创建下载工作线程
        downloader = DownloadWorker(
            url=self.url,
            save_dir=self.save_dir,
            filename=self.filename,
            thread_num=self.thread_num,
            user_agent=self.user_agent,
            verify_ssl=self.verify_ssl,
            proxy=self.proxy
        )
        
        # # 命令行进度回调
        # def cli_progress_callback(progress: float):
        #     print(f"\r进度: {progress:.1f}%", end="", flush=True)
        
        # if self.progress_callback:
        #     # 用户自定义回调
        #     downloader.progress_updated = self.progress_callback
        # else:
        #     # 使用默认命令行回调
        #     downloader.progress_updated = cli_progress_callback
        
        # # 运行下载
        # downloader.run()
        
        # # 等待完成
        # while downloader.is_alive() if hasattr(downloader, 'is_alive') else False:
        #     time.sleep(0.5)
        
        # return self.success


# ==================== 主要下载函数 ====================

def download(url: str, save_dir: str, filename: str, thread_num: int = 4,
             user_agent: Optional[str] = None, verify_ssl: bool = True,
             progress_callback: Optional[Callable[[float], None]] = None,
             proxy: Optional[dict] = None, referer: Optional[str] = None) -> bool:
    """
    供外部程序导入调用的下载函数（保持与旧代码相同的接口）
    
    Args:
        url: 下载链接
        save_dir: 保存目录（支持中文）
        filename: 保存文件名（支持中文）
        thread_num: 下载线程数
        user_agent: 自定义User-Agent
        verify_ssl: 是否验证SSL证书
        progress_callback: 进度回调函数（参数为进度百分比）
        proxy: 代理配置，例: {"http":"http://127.0.0.1:7890", "https":"http://127.0.0.1:7890"}
        referer: 自定义Referer
        
    Returns:
        bool: 下载是否成功
    """
    downloader = MultiThreadDownloader(
        url=url,
        save_dir=save_dir,
        filename=filename,
        thread_num=thread_num,
        user_agent=user_agent,
        verify_ssl=verify_ssl,
        progress_callback=progress_callback,
        proxy=proxy,
        referer=referer
    )
    return downloader.start()
    # # 自动选择模式：如果有回调函数则用CLI，否则用GUI
    # if progress_callback:
    #     return downloader._start_cli()
    # else:
    #     return downloader.start()


# ==================== 命令行入口 ====================

def main():
    """命令行入口函数"""
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "=" * 50)
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "          多线程下载工具")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "=" * 50)
    
    # 获取输入参数
    url = input("\n1. 请输入下载链接: ").strip()
    while not url:
        debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, "错误：下载链接不能为空！")
        url = input("1. 请输入下载链接: ").strip()
    
    save_dir = input("2. 请输入保存目录（默认：当前目录）: ").strip()
    if not save_dir:
        save_dir = "."
    
    # 创建目录（如果不存在）
    os.makedirs(save_dir, exist_ok=True)
    
    filename = input("3. 请输入保存文件名（默认：自动提取）: ").strip()
    if not filename:
        # 尝试从URL提取文件名
        filename = url.split('/')[-1].split('?')[0]
        if not filename:
            filename = f"download_{int(time.time())}"
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"自动提取文件名：{filename}")
    
    thread_num = input("4. 请输入下载线程数（默认：4）: ").strip()
    if not thread_num:
        thread_num = 4
    else:
        try:
            thread_num = int(thread_num)
            if thread_num < 1:
                debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, "警告：线程数必须大于0，使用默认值4")
                thread_num = 4
        except ValueError:
            debug_logger.output("multi_thread_downloader.py", LogLevel.WARNING, "警告：无效的线程数，使用默认值4")
            thread_num = 4
    
    user_agent = input("5. 请输入自定义User-Agent（留空使用默认）: ").strip() or None
    
    proxy = input("6. 请输入代理地址（格式：http://ip:port，留空为无代理）: ").strip()
    proxy_dict = {}
    if proxy:
        proxy_dict = {"http": proxy, "https": proxy}
    
    ssl_verify_input = input("7. 是否验证SSL证书？(y/n，默认：y): ").strip().lower()
    verify_ssl = ssl_verify_input not in ['n', 'no']
    
    # 确认信息
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "\n" + "=" * 50)
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "下载参数确认：")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"链接：{url}")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"保存目录：{save_dir}")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"文件名：{filename}")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"线程数：{thread_num}")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"代理：{proxy or '无'}")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"SSL验证：{verify_ssl}")
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "=" * 50)
    
    confirm = input("\n是否开始下载？(y/n): ").strip().lower()
    if confirm != 'y':
        debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "下载已取消！")
        return
    
    # 开始下载
    debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "\n开始下载...")
    try:
        success = download(
            url=url,
            save_dir=save_dir,
            filename=filename,
            thread_num=thread_num,
            user_agent=user_agent,
            verify_ssl=verify_ssl,
            proxy=proxy_dict
        )
        
        if success:
            filepath = os.path.join(save_dir, filename)
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, f"\n下载成功！文件路径：{filepath}")
        else:
            debug_logger.output("multi_thread_downloader.py", LogLevel.INFO, "\n下载失败或已取消！")
            
    except Exception as e:
        debug_logger.output("multi_thread_downloader.py", LogLevel.ERROR, f"\n下载过程中发生错误：{str(e)}")


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 安装依赖：pip install requests PyQt5
    main()