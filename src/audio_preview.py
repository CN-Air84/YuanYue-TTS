# coding=utf-8
import os
import sys
import glob
import threading
import time
import traceback
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from hotkey_manager import HotkeyManager, HotkeyAction

from PyQt5.QtCore import QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import Qt
from debug_logger import debug_logger, LogLevel

try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class AudioState:
    is_playing: bool = False
    is_paused: bool = False
    is_seeking: bool = False
    current_audio_length: float = 0.0
    current_audio_position: float = 0.0
    volume: float = 1.0
    time_reference: float = 0.0
    seek_cooldown_until: float = 0.0 


class PygameManager:
    """
    pygame mixer 引擎管理器，负责底层音频播放控制。
    封装了 pygame.mixer.music 的常用操作，并提供异常处理和状态跟踪。
    """
    def __init__(self):
        """初始化 PygameManager 实例"""
        self.pygame_initialized = False
        self._init_lock = threading.Lock()
        self._init_thread = None
        debug_logger.output("audio_preview.py", LogLevel.INFO, "PygameManager 实例已创建", fold_code="AUDIO_INIT")
        
    def _init_pygame_task(self):
        """实际执行 pygame 初始化的任务函数，设计为可在线程中运行"""
        with self._init_lock:
            if self.pygame_initialized:
                return
            
            try:
                debug_logger.output("audio_preview.py", LogLevel.INFO, "正在执行 pygame mixer 引擎底层初始化...", fold_code="AUDIO_INIT")
                import pygame
                
                # 性能优化：通过 pre_init 预设参数，减少 init 时的自动探测开销
                # 使用 44100Hz, 16位有符号, 双声道, 1024字节缓冲区 (平衡性能与延迟)
                if not pygame.mixer.get_init():
                    pygame.mixer.pre_init(44100, -16, 2, 1024)
                    pygame.mixer.init()
                
                pygame.mixer.music.set_endevent(pygame.USEREVENT)
                self.pygame_initialized = True
                debug_logger.output("audio_preview.py", LogLevel.INFO, "pygame mixer 底层初始化成功", fold_code="AUDIO_INIT")
            except Exception as e:
                debug_logger.output("audio_preview.py", LogLevel.ERROR, f"pygame 底层初始化失败: {str(e)}", fold_code="AUDIO_INIT")

    def _init_pygame(self, async_init: bool = False) -> bool:
        """
        初始化 pygame mixer 引擎

        Args:
            async_init (bool): 是否使用异步线程初始化，避免阻塞主线程

        Returns:
            bool: 是否初始化成功（异步模式下返回是否成功启动线程）
        """
        if self.pygame_initialized:
            return True
            
        if async_init:
            if self._init_thread is None or not self._init_thread.is_alive():
                debug_logger.output("audio_preview.py", LogLevel.INFO, "启动异步线程初始化 pygame mixer", fold_code="AUDIO_INIT")
                self._init_thread = threading.Thread(target=self._init_pygame_task, name="PygameInitThread", daemon=True)
                self._init_thread.start()
            return True
        else:
            # 优化：即使是同步调用，如果初始化正在进行中，也应等待锁而不是重复触发
            # 注意：在 UI 线程同步调用此方法仍可能导致阻塞，但在播放前这是必须的
            self._init_pygame_task()
            return self.pygame_initialized
    
    def load_audio(self, file_path: str) -> bool:
        """
        加载音频文件

        Args:
            file_path (str): 音频文件路径

        Returns:
            bool: 是否加载成功
        """
        # 优化：不再在每个操作前同步调用 _init_pygame
        # 如果尚未初始化，load_audio 应该失败或等待
        if not self.pygame_initialized:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, "pygame 尚未初始化，尝试同步加载", fold_code="AUDIO_PLAY")
            if not self._init_pygame():
                return False

        try:
            import pygame
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"正在加载音频文件: {file_path}", fold_code="AUDIO_PLAY")
            pygame.mixer.music.load(file_path)
            return True
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"加载音频文件失败 {file_path}: {str(e)}", fold_code="AUDIO_PLAY")
            return False
    
    def play_audio(self, start_position: float = 0.0) -> bool:
        """
        开始播放音频

        Args:
            start_position (float): 播放起始位置 (秒)

        Returns:
            bool: 是否播放成功
        """
        if not self.pygame_initialized:
            if not self._init_pygame():
                return False

        try:
            import pygame
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"启动音频播放，位置: {start_position:.2f}s", fold_code="AUDIO_PLAY")
            pygame.mixer.music.play(start=start_position)
            return True
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"音频播放失败: {str(e)}", fold_code="AUDIO_PLAY")
            return False
    
    def pause_audio(self):
        """暂停音频播放"""
        if not self.pygame_initialized:
            return
            
        try:
            import pygame
            debug_logger.output("audio_preview.py", LogLevel.INFO, "暂停音频播放", fold_code="AUDIO_PLAY")
            pygame.mixer.music.pause()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"暂停音频失败: {str(e)}", fold_code="AUDIO_PLAY")
    
    def unpause_audio(self):
        """恢复音频播放"""
        if not self.pygame_initialized:
            return
            
        try:
            import pygame
            debug_logger.output("audio_preview.py", LogLevel.INFO, "恢复音频播放", fold_code="AUDIO_PLAY")
            pygame.mixer.music.unpause()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"恢复音频失败: {str(e)}", fold_code="AUDIO_PLAY")
    
    def stop_audio(self):
        """停止音频播放"""
        if not self.pygame_initialized:
            return
            
        try:
            import pygame
            debug_logger.output("audio_preview.py", LogLevel.INFO, "停止音频播放", fold_code="AUDIO_PLAY")
            pygame.mixer.music.stop()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"停止音频失败: {str(e)}", fold_code="AUDIO_PLAY")
    
    def get_audio_length(self, file_path: str) -> float:
        """
        获取音频文件长度（秒）

        Args:
            file_path (str): 音频文件路径

        Returns:
            float: 音频长度 (秒)，失败则返回 0.0
        """
        if not self.pygame_initialized:
            if not self._init_pygame():
                return 0.0

        try:
            import pygame
            sound = pygame.mixer.Sound(file_path)
            length = sound.get_length()
            debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"获取音频长度: {length:.2f}s", fold_code="AUDIO_INFO")
            return length
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"获取音频长度失败: {str(e)}", fold_code="AUDIO_INFO")
            return 0.0
    
    def get_current_position(self) -> float:
        """
        获取当前播放位置（秒）

        Returns:
            float: 当前播放位置 (秒)
        """
        try:
            import pygame
            pos = pygame.mixer.music.get_pos() / 1000.0
            return pos
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"获取当前播放位置失败: {str(e)}", fold_code="AUDIO_INFO")
            return 0.0
    
    def is_playing(self) -> bool:
        """
        检查是否正在播放

        Returns:
            bool: 是否正在播放
        """
        try:
            import pygame
            return pygame.mixer.music.get_busy()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"获取播放状态失败: {str(e)}", fold_code="AUDIO_INFO")
            return False
    
    def set_volume(self, volume: float) -> bool:
        """
        设置播放音量

        Args:
            volume (float): 音量值 (0.0 到 1.0)

        Returns:
            bool: 是否设置成功
        """
        try:
            import pygame
            volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(volume)
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"设置播放音量为: {volume:.2f}", fold_code="AUDIO_VOL")
            return True
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"设置音量失败: {str(e)}", fold_code="AUDIO_VOL")
            return False
    
    def get_volume(self) -> float:
        """
        获取当前音量

        Returns:
            float: 当前音量值
        """
        try:
            import pygame
            return pygame.mixer.music.get_volume()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"获取音量失败: {str(e)}", fold_code="AUDIO_VOL")
            return 1.0
    
    def cleanup(self):
        """清理 pygame 资源，释放音频设备"""
        if self.pygame_initialized:
            try:
                import pygame
                debug_logger.output("audio_preview.py", LogLevel.INFO, "正在清理 pygame mixer 资源...", fold_code="AUDIO_CLEANUP")
                pygame.mixer.music.stop()
                time.sleep(0.2)
                pygame.mixer.music.unload()
                pygame.mixer.quit()
                self.pygame_initialized = False
                debug_logger.output("audio_preview.py", LogLevel.INFO, "pygame mixer 资源已成功释放", fold_code="AUDIO_CLEANUP")
            except Exception as e:
                debug_logger.output("audio_preview.py", LogLevel.WARNING, f"清理 pygame 资源时出错: {str(e)}", fold_code="AUDIO_CLEANUP")


class PlaybackMonitor(threading.Thread):
    """
    音频播放监控线程，负责检测播放结束并触发回调。
    独立于 UI 线程运行，通过轮询播放器状态来判断是否播放完成。
    """
    def __init__(self, pygame_manager: PygameManager, state: AudioState, 
                 playback_finished_callback: Callable):
        """
        初始化 PlaybackMonitor

        Args:
            pygame_manager (PygameManager): 音频引擎管理器
            state (AudioState): 共享的音频状态
            playback_finished_callback (Callable): 播放完成时的回调函数
        """
        super().__init__()
        self.pygame_manager = pygame_manager
        self.state = state
        self.playback_finished_callback = playback_finished_callback
        self.should_stop = False
        self.daemon = True
        debug_logger.output("audio_preview.py", LogLevel.INFO, "初始化播放监控线程 (PlaybackMonitor)", fold_code="AUDIO_MONITOR")
    
    def run(self):
        """监控线程主循环，定期检查播放状态"""
        debug_logger.output("audio_preview.py", LogLevel.INFO, "播放监控线程已启动", fold_code="AUDIO_MONITOR")
        while not self.should_stop and self.state.is_playing:
            if (not self.pygame_manager.is_playing() and 
                not self.state.is_seeking and 
                not self.state.is_paused):
                debug_logger.output("audio_preview.py", LogLevel.INFO, "监控线程检测到音频播放结束", fold_code="AUDIO_MONITOR")
                self.playback_finished_callback()
                break
            time.sleep(0.1)
        debug_logger.output("audio_preview.py", LogLevel.INFO, "播放监控线程已停止", fold_code="AUDIO_MONITOR")
    
    def stop(self):
        """安全停止监控线程"""
        self.should_stop = True


class AudioCacheManager:
    """
    音频缓存管理器，负责处理音频缓存逻辑和一致性检查。
    通过配置哈希值判断是否需要重新生成音频。
    """
    def __init__(self, parent_window):
        """
        初始化 AudioCacheManager

        Args:
            parent_window: 父窗口对象 (MainWindow)
        """
        self.parent_window = parent_window
        debug_logger.output("audio_preview.py", LogLevel.INFO, "AudioCacheManager 实例已创建", fold_code="AUDIO_CACHE")
    
    def get_cache_key(self, config) -> str:
        """
        根据配置生成缓存键

        Args:
            config: 音频生成配置对象

        Returns:
            str: 缓存键
        """
        cache_key = f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
        debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"生成缓存键: {cache_key[:50]}...", fold_code="AUDIO_CACHE")
        return cache_key
    
    def get_content_hash(self, config) -> str:
        """
        生成内容哈希值，用于快速比对内容是否改变

        Args:
            config: 音频生成配置对象

        Returns:
            str: MD5 哈希值
        """
        import hashlib
        content = f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"生成内容哈希: {content_hash}", fold_code="AUDIO_CACHE")
        return content_hash
    
    def is_content_unchanged(self, config) -> bool:
        """
        检查当前配置对应的音频是否已缓存且内容未变

        Args:
            config: 音频生成配置对象

        Returns:
            bool: 内容是否未发生变化
        """
        try:
            current_hash = self.get_content_hash(config)
            is_unchanged = (self.parent_window.last_content_hash is not None and 
                    current_hash == self.parent_window.last_content_hash)
            if is_unchanged:
                debug_logger.output("audio_preview.py", LogLevel.INFO, "检测到内容未发生变化，将复用现有音频缓存", fold_code="AUDIO_CACHE")
            else:
                debug_logger.output("audio_preview.py", LogLevel.INFO, "检测到内容已改变或无缓存，需要重新生成音频", fold_code="AUDIO_CACHE")
            return is_unchanged
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"检查内容一致性时出错: {str(e)}", fold_code="AUDIO_CACHE")
            return False
    
    def cache_audio(self, cache_key: str, file_path: str):
        """
        将生成的音频路径存入缓存

        Args:
            cache_key (str): 缓存键
            file_path (str): 音频文件物理路径
        """
        try:
            self.parent_window.audio_cache[cache_key] = file_path
            self.parent_window.current_audio_path = file_path
            self.parent_window.last_content_hash = self.get_content_hash(self.parent_window.config)
            self.parent_window.has_preview = True
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"音频已成功加入缓存: {os.path.basename(file_path)}", fold_code="AUDIO_CACHE")
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"缓存音频文件失败: {str(e)}", fold_code="AUDIO_CACHE")


class AudioFileCleaner:
    """音频文件清理工具类，提供静态方法清理临时音频文件"""
    @staticmethod
    def cleanup_preview_audio(program_dir: str) -> int:
        """
        清理缓存目录中的临时预览音频文件

        Args:
            program_dir (str): 程序运行目录

        Returns:
            int: 成功删除的文件数量
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "正在启动预览音频文件清理任务...", fold_code="AUDIO_CLEANUP")
            cache_dir = os.path.join(get_app_base_path(), 'cache', 'audios')
            
            if not os.path.exists(cache_dir):
                debug_logger.output("audio_preview.py", LogLevel.INFO, f"缓存目录不存在，无需清理: {cache_dir}", fold_code="AUDIO_CLEANUP")
                return 0
                
            preview_files = glob.glob(os.path.join(cache_dir, "tmp_*.mp3"))
            stretched_files = glob.glob(os.path.join(cache_dir, "*_stretched.mp3"))
            preview_files.extend(stretched_files)
            
            total_found = len(preview_files)
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"共找到 {total_found} 个待处理的临时文件", fold_code="AUDIO_CLEANUP")
            
            deleted_count = 0
            for file_path in preview_files:
                try:
                    for attempt in range(3):
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                deleted_count += 1
                                debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"已成功删除文件: {os.path.basename(file_path)}", fold_code="AUDIO_CLEANUP")
                                break
                        except PermissionError:
                            if attempt < 2:
                                debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"文件 {os.path.basename(file_path)} 正被占用，等待重试 ({attempt+1}/3)...", fold_code="AUDIO_CLEANUP")
                                time.sleep(0.1)
                        except Exception as e:
                            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"删除文件 {os.path.basename(file_path)} 失败: {str(e)}", fold_code="AUDIO_CLEANUP")
                            break
                except Exception as e:
                    debug_logger.output("audio_preview.py", LogLevel.ERROR, f"清理文件项 {file_path} 时发生异常: {str(e)}", fold_code="AUDIO_CLEANUP")
                    pass
            
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"预览音频清理完成。成功删除 {deleted_count}/{total_found} 个文件。", fold_code="AUDIO_CLEANUP")
            return deleted_count
            
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"执行预览音频清理时发生致命错误: {str(e)}", fold_code="AUDIO_CLEANUP")
            return 0


class AudioSignals(QObject):
    """音频预览相关的 PyQt 信号定义"""
    playback_finished = pyqtSignal()
    progress_updated = pyqtSignal(int)
    preview_generated = pyqtSignal(str)
    volume_changed = pyqtSignal(float)
    position_changed = pyqtSignal(float)
    state_changed = pyqtSignal(object)
    next_sentence_requested = pyqtSignal()
    prev_sentence_requested = pyqtSignal()


class AudioPreview:
    """
    音频预览主类，协调播放引擎、缓存和 UI 交互。
    作为音频预览功能的核心控制器，处理热键、播放进度更新、缓存管理等。
    """
    def __init__(self, parent_window, hotkey_manager: HotkeyManager = None):
        """
        初始化 AudioPreview

        Args:
            parent_window: 父窗口对象 (MainWindow)
            hotkey_manager (HotkeyManager, optional): 热键管理器
        """
        self.parent_window = parent_window
        self.hotkey_manager = hotkey_manager
        
        debug_logger.output("audio_preview.py", LogLevel.INFO, "正在初始化 AudioPreview 核心组件...", fold_code="AUDIO_INIT")
        
        self.pygame_manager = PygameManager()
        self.cache_manager = AudioCacheManager(parent_window)
        self.file_cleaner = AudioFileCleaner()
        
        self.state = AudioState()
        
        self.playback_monitor = None
        
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)
        
        self.audio_signals = AudioSignals()
        self.audio_signals.playback_finished.connect(self._on_playback_finished)
        self.audio_signals.volume_changed.connect(self._on_volume_changed)
        self.audio_signals.position_changed.connect(self._on_position_changed)
        
        self.is_paused = False
        self.is_seeking = False
        
        # 异步加载优化：程序运行 500ms 后启动音频子系统初始化
        # 相比原先的 2000ms 显著提前，且采用非阻塞线程初始化，不影响 UI 响应
        self.init_timer = QTimer()
        self.init_timer.setSingleShot(True)
        self.init_timer.timeout.connect(self._async_audio_subsystem_init)
        self.init_timer.start(300)
        
        debug_logger.output("audio_preview.py", LogLevel.INFO, "AudioPreview 初始化完成，音频子系统将在 300ms 后异步启动", fold_code="AUDIO_INIT")

    def _async_audio_subsystem_init(self):
        """
        异步初始化音频子系统。
        在程序运行 300ms 后触发，启动后台线程初始化 pygame mixer，实现秒开感知。
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "正在执行异步音频子系统初始化...", fold_code="AUDIO_INIT")
            # 调用 PygameManager 的异步初始化接口
            self.pygame_manager._init_pygame(async_init=True)
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"异步初始化音频子系统时发生异常: {str(e)}", fold_code="AUDIO_INIT")

    @property
    def is_paused(self):
        """获取当前暂停状态"""
        return self.state.is_paused

    @is_paused.setter
    def is_paused(self, value):
        """设置暂停状态"""
        self.state.is_paused = value

    @property
    def is_seeking(self):
        """获取当前跳转状态"""
        return self.state.is_seeking

    @is_seeking.setter
    def is_seeking(self, value):
        """设置跳转状态"""
        self.state.is_seeking = value

    def handle_key_event(self, event: QKeyEvent):
        """
        处理键盘事件 - 使用统一热键管理器

        Args:
            event (QKeyEvent): 键盘事件对象
        """
        try:
            if not self.hotkey_manager:
                return
                
            action = self.hotkey_manager.handle_key_event(event)
            if not action:
                # 记录未匹配的热键事件，有助于调试
                debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"未匹配的热键事件: {event.key()}", fold_code="AUDIO_HOTKEY")
                return
            
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"正在处理热键动作: {action}", fold_code="AUDIO_HOTKEY")

            # 某些动作即使不在播放状态也可以执行
            if action == HotkeyAction.NEXT_SENTENCE:
                self.audio_signals.next_sentence_requested.emit()
                return
            elif action == HotkeyAction.PREV_SENTENCE:
                self.audio_signals.prev_sentence_requested.emit()
                return

            # 以下动作需要正在播放才能执行
            if not self.state.is_playing:
                return
                
            if action == HotkeyAction.TOGGLE_PAUSE:
                self.toggle_pause()
            elif action == HotkeyAction.SEEK_BACKWARD:
                self._seek_relative(-5)
            elif action == HotkeyAction.SEEK_FORWARD:
                self._seek_relative(5)
            elif action == HotkeyAction.VOLUME_UP:
                self._adjust_volume(0.1)
            elif action == HotkeyAction.VOLUME_DOWN:
                self._adjust_volume(-0.1)
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"处理热键事件时发生异常: {str(e)}", fold_code="AUDIO_HOTKEY")

    def _perform_seek(self, target_position: float):
        """
        执行音频跳转操作，确保时间基准一致性

        Args:
            target_position (float): 目标跳转位置 (秒)
        """
        try:
            if not self.state.is_playing or self.state.current_audio_length <= 0:
                debug_logger.output("audio_preview.py", LogLevel.WARNING, "当前未播放或音频长度无效，忽略跳转请求", fold_code="AUDIO_SEEK")
                return
            target_position = max(0.0, min(target_position, self.state.current_audio_length))
            
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"正在跳转至位置: {target_position:.2f}s", fold_code="AUDIO_SEEK")
            
            # 停止当前播放并重新定位
            self.pygame_manager.stop_audio()
            
            self.state.time_reference = time.time() - target_position
            self.state.current_audio_position = target_position
            
            # 从新位置开始播放
            self._play_audio_file(self.parent_window.current_audio_path, target_position)
            
            # 设置跳转冷却期以防止频繁更新
            current_time = time.time()
            self.state.seek_cooldown_until = current_time + 0.3
            
            # 发送位置变化信号
            self.audio_signals.position_changed.emit(target_position)
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"执行音频跳转时发生异常: {str(e)}", fold_code="AUDIO_SEEK")

    def _seek_relative(self, seconds: float = 5.0):
        """
        相对跳转 - 基于当前位置进行跳转

        Args:
            seconds (float): 跳转秒数，正数为快进，负数为后退
        """
        try:
            if not self.state.is_playing or self.state.current_audio_length <= 0:
                debug_logger.output("audio_preview.py", LogLevel.WARNING, "当前未播放或音频长度无效，忽略相对跳转请求", fold_code="AUDIO_SEEK")
                return
                
            # 获取当前播放位置
            current_position = self.get_current_playback_position()
            
            # 计算目标位置
            target_position = current_position + seconds
            
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"相对跳转: {seconds}s, 目标位置: {target_position:.2f}s", fold_code="AUDIO_SEEK")
            
            # 执行跳转
            self._perform_seek(target_position)
            
            # 显示跳转提示
            direction = "前进" if seconds > 0 else "回退"
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"执行相对跳转时发生异常: {str(e)}", fold_code="AUDIO_SEEK")
    def _adjust_volume(self, delta: float):
        """
        调整播放音量并显示通知

        Args:
            delta (float): 音量变化量 (例如 +0.1 或 -0.1)
        """
        try:
            new_volume = max(0.0, min(1.0, self.state.volume + delta))
            if new_volume != self.state.volume:
                debug_logger.output("audio_preview.py", LogLevel.INFO, f"正在调整音量: {delta:+.2f}, 新音量: {new_volume:.2f}", fold_code="AUDIO_VOL")
                self.set_volume(new_volume)
                
                volume_percent = int(new_volume * 100)

        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"调整音量时发生异常: {str(e)}", fold_code="AUDIO_VOL")

    def play_preview(self):
        """
        根据当前配置执行预览播放。
        如果文本内容已改变，会提示用户重新生成预览。
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "请求预览播放", fold_code="AUDIO_PLAY")
            
            # 检查配置
            if not hasattr(self.parent_window, 'config'):
                debug_logger.output("audio_preview.py", LogLevel.ERROR, "无法获取预览配置: parent_window.config 不存在", fold_code="AUDIO_PLAY")
                return

            cache_key = self.cache_manager.get_cache_key(self.parent_window.config)
            if (cache_key not in self.parent_window.audio_cache or 
                not os.path.exists(self.parent_window.audio_cache[cache_key])):
                debug_logger.output("audio_preview.py", LogLevel.WARNING, f"没有可用的音频缓存 (Key: {cache_key[:20]}...)", fold_code="AUDIO_PLAY")

                return
                
            if not self.cache_manager.is_content_unchanged(self.parent_window.config):
                debug_logger.output("audio_preview.py", LogLevel.WARNING, "文本内容已改变，现有缓存失效", fold_code="AUDIO_PLAY")
                if hasattr(self.parent_window, 'generation_page'):
                    self.parent_window.generation_page.preview_control.preview_button.setText("生成预览")
                self.parent_window.has_preview = False

                return
                
            if self.state.is_playing:
                debug_logger.output("audio_preview.py", LogLevel.INFO, "停止当前正在进行的播放以开始新预览", fold_code="AUDIO_PLAY")
                self.stop_audio()
                
            if hasattr(self.parent_window, 'generation_page'):
                self.parent_window.generation_page.preview_control.preview_progress.setValue(0)
            
            self.parent_window.current_audio_path = self.parent_window.audio_cache[cache_key]
            self._play_audio_file(self.parent_window.current_audio_path)
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"执行预览播放时发生异常: {str(e)}", fold_code="AUDIO_PLAY")

    def _play_audio_file(self, file_path: str, start_position: float = 0.0):
        """
        底层音频播放函数，初始化时间基准点并启动监控线程

        Args:
            file_path (str): 音频文件路径
            start_position (float): 起始播放位置 (秒)
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"开始播放音频文件: {os.path.basename(file_path)}, 起始位置: {start_position:.2f}s", fold_code="AUDIO_PLAY")
            
            if not self.pygame_manager._init_pygame():
                debug_logger.output("audio_preview.py", LogLevel.ERROR, "pygame mixer 初始化失败", fold_code="AUDIO_PLAY")
                return
                
            if not self.pygame_manager.load_audio(file_path):
                debug_logger.output("audio_preview.py", LogLevel.ERROR, f"音频文件加载失败: {file_path}", fold_code="AUDIO_PLAY")
                return
                
            self.pygame_manager.set_volume(self.state.volume)
                
            if not self.pygame_manager.play_audio(start_position):
                debug_logger.output("audio_preview.py", LogLevel.ERROR, "音频播放启动失败", fold_code="AUDIO_PLAY")
                return
            
            self.state.current_audio_length = self.pygame_manager.get_audio_length(file_path)
            self.state.current_audio_position = start_position
            
            # 初始化时间基准点：当前时间 - 起始位置，为后续时间计算提供基准
            self.state.time_reference = time.time() - start_position
            
            self.state.is_playing = True
            self.state.is_paused = False
            self.state.is_seeking = False
            
            if hasattr(self.parent_window, 'generation_page'):
                generation_page = self.parent_window.generation_page
                if hasattr(generation_page, 'preview_control'):
                    generation_page.preview_control.set_playback_controls_enabled(True)
                    generation_page.preview_control.update_pause_button_text(False)
                    generation_page.preview_control.preview_progress.setValue(0)
            
            self.progress_timer.start(100)
            
            # 停止旧的监控线程
            if self.playback_monitor:
                self.playback_monitor.stop()
                self.playback_monitor = None
                
            self.playback_monitor = PlaybackMonitor(
                self.pygame_manager, 
                self.state, 
                self.audio_signals.playback_finished.emit
            )
            self.playback_monitor.start()
            
            debug_logger.output("audio_preview.py", LogLevel.INFO, "音频播放设置完成，开始监控播放状态", fold_code="AUDIO_PLAY")
            
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"播放音频时发生异常: {str(e)}", fold_code="AUDIO_PLAY")


    def _on_playback_finished(self):
        """
        处理音频播放自然结束的回调
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "音频播放已自然结束", fold_code="AUDIO_PLAY")
            self.state.is_playing = False
            self.state.is_paused = False
            self.state.is_seeking = False
            
            if hasattr(self.parent_window, 'generation_page'):
                generation_page = self.parent_window.generation_page
                if hasattr(generation_page, 'preview_control'):
                    generation_page.preview_control.set_playback_controls_enabled(False)
                    generation_page.preview_control.update_preview_button_state(True, True)
                    generation_page.preview_control.preview_progress.setValue(1000)
                    generation_page.preview_control.update_pause_button_text(False)
                

                
            self.progress_timer.stop()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"处理播放完成回调时发生异常: {str(e)}", fold_code="AUDIO_PLAY")

    def stop_audio(self):
        """
        停止音频播放并清理播放状态
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "正在停止音频预览...", fold_code="AUDIO_PLAY")
            self.pygame_manager.stop_audio()
            
            # 给 pygame 一点时间处理停止
            time.sleep(0.05)
            
            self.state.is_playing = False
            self.state.is_paused = False
            self.state.is_seeking = False
            
            if hasattr(self.parent_window, 'generation_page'):
                generation_page = self.parent_window.generation_page
                if hasattr(generation_page, 'preview_control'):
                    generation_page.preview_control.set_playback_controls_enabled(False)
                    generation_page.preview_control.update_preview_button_state(False, False)
                    generation_page.preview_control.update_pause_button_text(False)
                    generation_page.preview_control.preview_progress.setValue(0)
            
            self.progress_timer.stop()
            
            if self.playback_monitor:
                self.playback_monitor.stop()
                self.playback_monitor = None
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"停止音频预览时发生异常: {str(e)}", fold_code="AUDIO_PLAY")

    def toggle_pause(self):
        """暂停/继续播放 - 使用时间基准点确保状态一致性"""
        try:
            if not self.pygame_manager.pygame_initialized:
                debug_logger.output("audio_preview.py", LogLevel.WARNING, "pygame mixer 未初始化，无法切换暂停状态", fold_code="AUDIO_PLAY")
                return False
                
            if not self.state.is_playing:
                debug_logger.output("audio_preview.py", LogLevel.DEBUG, "当前未处于播放状态，忽略暂停请求", fold_code="AUDIO_PLAY")
                return False
                
            if not self.state.is_paused:
                # 暂停播放
                debug_logger.output("audio_preview.py", LogLevel.INFO, "正在暂停播放...", fold_code="AUDIO_PLAY")
                self.pygame_manager.pause_audio()
                self.state.is_paused = True
                # 记录暂停时的精确位置
                self.state.current_audio_position = self.get_current_playback_position()
                if hasattr(self.parent_window, 'generation_page'):
                    generation_page = self.parent_window.generation_page
                    if hasattr(generation_page, 'preview_control'):
                        generation_page.preview_control.update_pause_button_text(True)

                return True
            else:
                # 继续播放：重新计算时间基准点，确保时间同步
                debug_logger.output("audio_preview.py", LogLevel.INFO, "正在恢复播放...", fold_code="AUDIO_PLAY")
                self.pygame_manager.unpause_audio()
                self.state.is_paused = False
                self.state.time_reference = time.time() - self.state.current_audio_position
                if hasattr(self.parent_window, 'generation_page'):
                    generation_page = self.parent_window.generation_page
                    if hasattr(generation_page, 'preview_control'):
                        generation_page.preview_control.update_pause_button_text(False)

                return True
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"切换暂停状态时发生异常: {str(e)}", fold_code="AUDIO_PLAY")
            return False

    def _update_progress(self):
        """更新播放进度 - 显示当前句子的播放进度"""
        try:
            current_time = time.time()
            
            # 跳转冷却期：避免频繁更新导致的UI闪烁
            if current_time < self.state.seek_cooldown_until:
                return
                
            if (self.state.is_playing and 
                not self.state.is_seeking and 
                not self.state.is_paused and 
                self.pygame_manager.pygame_initialized):
                
                pos = self.get_current_playback_position()
                
                if self.state.current_audio_length > 0:
                    # 计算当前句子的播放进度百分比
                    sentence_progress = pos / self.state.current_audio_length
                    
                    # 获取当前句子的索引和总句子数
                    generation_page = self.parent_window.generation_page
                    
                    # 检查是否是 generation_page_neo 的 GenerationPage 实例
                    # 通过检查模块名来区分不同的 GenerationPage 类
                    if (generation_page and 
                        hasattr(generation_page, 'sentence_manager') and
                        generation_page.__class__.__module__ == 'generation_page_neo'):
                        current_sentence_index = generation_page.sentence_manager.current_sentence_index
                        total_sentences = len(generation_page.sentence_manager.sentences)
                    else:
                        # 如果不是 generation_page_neo，使用传统方法获取进度信息
                        current_sentence_index = 0
                        total_sentences = 1
                    
                    if total_sentences > 0 and current_sentence_index >= 0:
                        # 计算基础进度（已完成句子的进度）
                        base_progress = (current_sentence_index / total_sentences) * 100
                        
                        # 加上当前句子的播放进度
                        current_sentence_progress = sentence_progress * (100 / total_sentences)
                        
                        # 总进度百分比
                        total_progress = base_progress + current_sentence_progress
                        
                        # 转换为进度条值（0-1000）
                        progress_value = int(total_progress * 10)
                        progress_value = max(0, min(progress_value, 1000))
                        
                        # 设置进度条值
                        if hasattr(generation_page, 'preview_control'):
                            generation_page.preview_control.preview_progress.setValue(progress_value)
                        elif hasattr(generation_page, 'progress_bar'):
                            generation_page.progress_bar.setValue(progress_value)
                        
                        # 每10%进度打印一次调试信息，避免输出过多
                        if int(total_progress * 10) % 100 == 0:
                            debug_logger.output("audio_preview.py", LogLevel.DEBUG, 
                                              f"进度更新: 句子{current_sentence_index+1}/{total_sentences}, "
                                              f"当前句子进度{sentence_progress*100:.1f}%, 总进度{total_progress:.1f}%", fold_code="AUDIO_PROGRESS")
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"更新播放进度时发生异常: {str(e)}", fold_code="AUDIO_PROGRESS")

    def set_seeking(self, seeking: bool):
        """
        设置跳转状态

        Args:
            seeking (bool): 是否处于跳转中状态
        """
        try:
            self.state.is_seeking = seeking
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"跳转状态已设置为: {seeking}", fold_code="AUDIO_SEEK")
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"设置跳转状态时发生异常: {str(e)}", fold_code="AUDIO_SEEK")

    def seek_to_position(self, position: float):
        """
        跳转到指定位置

        Args:
            position (float): 目标位置 (秒)
        """
        try:
            if (self.state.is_playing and 
                self.state.current_audio_length > 0 and 
                self.pygame_manager.pygame_initialized):
                
                # 执行跳转
                self._perform_seek(position)
            else:
                debug_logger.output("audio_preview.py", LogLevel.WARNING, "当前无法跳转：播放器未就绪或未处于播放状态", fold_code="AUDIO_SEEK")
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"跳转至指定位置时发生异常: {str(e)}", fold_code="AUDIO_SEEK")

    def seek_to_percentage(self, percentage: float):
        """
        跳转到指定百分比

        Args:
            percentage (float): 目标百分比 (0.0 到 1.0)
        """
        try:
            if (self.state.is_playing and 
                self.state.current_audio_length > 0 and 
                self.pygame_manager.pygame_initialized):
                
                percentage = max(0.0, min(1.0, percentage))
                
                position = percentage * self.state.current_audio_length
                debug_logger.output("audio_preview.py", LogLevel.INFO, f"正在按百分比跳转: {percentage*100:.1f}% -> {position:.2f}s", fold_code="AUDIO_SEEK")
                self.seek_to_position(position)
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"跳转至指定百分比时发生异常: {str(e)}", fold_code="AUDIO_SEEK")

    def set_volume(self, volume: float) -> bool:
        """
        设置音量

        Args:
            volume (float): 音量值 (0.0 到 1.0)

        Returns:
            bool: 是否设置成功
        """
        try:
            volume = max(0.0, min(1.0, volume))
            self.state.volume = volume
            
            if self.pygame_manager.pygame_initialized:
                success = self.pygame_manager.set_volume(volume)
                if success:
                    debug_logger.output("audio_preview.py", LogLevel.INFO, f"音量已设置为: {volume:.2f}", fold_code="AUDIO_VOL")
                    self.audio_signals.volume_changed.emit(volume)
                return success
            return False
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"设置音量时发生异常: {str(e)}", fold_code="AUDIO_VOL")
            return False

    def get_volume(self) -> float:
        """
        获取当前音量

        Returns:
            float: 当前音量值
        """
        return self.state.volume
    
    def get_current_playback_position(self) -> float:
        """
        获取当前播放位置 - 基于时间基准点计算

        Returns:
            float: 当前播放位置 (秒)
        """
        try:
            if not self.state.is_playing or self.state.current_audio_length <= 0:
                return self.state.current_audio_position
                
            current_time = time.time()
            
            # 暂停状态：返回记录的暂停位置，避免时间漂移
            if self.state.is_paused:
                return self.state.current_audio_position
                
            # 播放状态：基于时间基准点计算当前位置
            current_position = current_time - self.state.time_reference
            
            # 边界保护：确保位置在音频长度范围内
            bounded_position = max(0.0, min(current_position, self.state.current_audio_length))
                
            return bounded_position
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.WARNING, f"获取当前播放位置失败: {str(e)}", fold_code="AUDIO_INFO")
            return self.state.current_audio_position

    def _on_volume_changed(self, volume: float):
        """
        音量变化处理回调
        
        优化：增加对 generation_page 和 preview_control 的存在性及空值检查，
        防止在页面未初始化完成时访问导致的 NoneType 异常。
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"收到音量变化信号: {volume:.2f}", fold_code="AUDIO_VOL")
            
            # 安全检查：确保 parent_window 存在且 generation_page 已加载
            if not hasattr(self, 'parent_window') or self.parent_window is None:
                return
                
            # generation_page 是 MainWindow 的属性，可能返回 None (如果选项卡尚未初始化)
            generation_page = getattr(self.parent_window, 'generation_page', None)
            if generation_page is None:
                return

            # 检查 preview_control 是否已初始化
            preview_control = getattr(generation_page, 'preview_control', None)
            if preview_control is None:
                return

            # 更新 UI 状态
            volume_percent = int(volume * 100)
            
            # 更新音量文本标签
            volume_label = getattr(preview_control, 'volume_value_label', None)
            if volume_label is not None:
                volume_label.setText(f"{volume_percent}%")
                
            # 更新音量滑块
            volume_slider = getattr(preview_control, 'volume_slider', None)
            if volume_slider is not None:
                # 阻塞信号以避免递归调用（如果有关联）
                volume_slider.blockSignals(True)
                volume_slider.setValue(volume_percent)
                volume_slider.blockSignals(False)
                
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"处理音量变化信号时发生异常: {str(e)}", fold_code="AUDIO_VOL")

    def _on_position_changed(self, position: float):
        """
        位置变化处理回调 - 避免重复更新导致的 UI 闪烁

        Args:
            position (float): 新位置 (秒)
        """
        try:
            current_time = time.time()
            
            # 跳转冷却期：避免短时间内重复更新进度条
            if current_time < self.state.seek_cooldown_until:
                return
                
            debug_logger.output("audio_preview.py", LogLevel.DEBUG, f"收到位置变化信号: {position:.2f}s", fold_code="AUDIO_SEEK")
            if (self.state.is_playing and 
                self.state.current_audio_length > 0 and
                hasattr(self.parent_window, 'generation_page')):
                
                percentage = position / self.state.current_audio_length
                progress = int(percentage * 1000)
                
                if hasattr(self.parent_window.generation_page, 'preview_control'):
                    self.parent_window.generation_page.preview_control.preview_progress.setValue(progress)
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"处理位置变化信号时发生异常: {str(e)}", fold_code="AUDIO_SEEK")

    def force_stop_audio(self):
        """强制停止音频并清理资源"""
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "正在强制停止音频并释放资源...", fold_code="AUDIO_PLAY")
            self.pygame_manager.cleanup()
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"强制停止音频时发生异常: {str(e)}", fold_code="AUDIO_PLAY")
    def cleanup_preview_audio(self):
        """
        清理预览音频缓存文件及状态

        Returns:
            int: 成功删除的文件数量
        """
        try:
            debug_logger.output("audio_preview.py", LogLevel.INFO, "正在执行预览音频清理程序...", fold_code="AUDIO_CLEANUP")
            self.force_stop_audio()
            
            program_dir = get_app_base_path()
            
            deleted_count = self.file_cleaner.cleanup_preview_audio(program_dir)
            
            if hasattr(self.parent_window, 'audio_cache'):
                self.parent_window.audio_cache.clear()
            self.parent_window.current_audio_path = None
            self.parent_window.has_preview = False
            
            debug_logger.output("audio_preview.py", LogLevel.INFO, f"预览音频清理完成，共删除 {deleted_count} 个文件，缓存已清空", fold_code="AUDIO_CLEANUP")
            
            return deleted_count
            
        except Exception as e:
            debug_logger.output("audio_preview.py", LogLevel.ERROR, f"清理预览音频时发生异常: {str(e)}", fold_code="AUDIO_CLEANUP")
            return 0

