# coding=utf-8
import os
import glob
import threading
import time
import traceback
from typing import Optional, Dict, Callable
from dataclasses import dataclass

from PyQt5.QtCore import QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import Qt


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


class KeyboardControlScheme:
    SCHEME_1 = 1
    SCHEME_2 = 2
    SCHEME_3 = 3
    
    @staticmethod
    def get_scheme_name(scheme_id: int) -> str:
        names = {
            1: "方案① (WASD+空格)",
            2: "方案② (方向键+RShift)", 
            3: "方案③ (小键盘)"
        }
        return names.get(scheme_id, "未知方案")
    
    @staticmethod
    def get_all_schemes() -> Dict[int, str]:
        return {
            1: "方案① (WASD+空格)",
            2: "方案② (方向键+RShift)",
            3: "方案③ (小键盘)"
        }


class PygameManager:
    def __init__(self):
        self.pygame_initialized = False
        
    def _init_pygame(self) -> bool:
        if not self.pygame_initialized:
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.set_endevent(pygame.USEREVENT)
                self.pygame_initialized = True
                return True
            except Exception as e:
                return False
        return True
    
    def load_audio(self, file_path: str) -> bool:
        try:
            import pygame
            pygame.mixer.music.load(file_path)
            return True
        except Exception as e:
            return False
    
    def play_audio(self, start_position: float = 0.0) -> bool:
        try:
            import pygame
            pygame.mixer.music.play(start=start_position)
            return True
        except Exception as e:
            return False
    
    def pause_audio(self):
        try:
            import pygame
            pygame.mixer.music.pause()
        except Exception as e:
            pass
    
    def unpause_audio(self):
        try:
            import pygame
            pygame.mixer.music.unpause()
        except Exception as e:
            pass
    
    def stop_audio(self):
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception as e:
            pass
    
    def get_audio_length(self, file_path: str) -> float:
        try:
            import pygame
            sound = pygame.mixer.Sound(file_path)
            return sound.get_length()
        except Exception as e:
            return 0.0
    
    def get_current_position(self) -> float:
        try:
            import pygame
            return pygame.mixer.music.get_pos() / 1000.0
        except Exception as e:
            return 0.0
    
    def is_playing(self) -> bool:
        try:
            import pygame
            return pygame.mixer.music.get_busy()
        except Exception as e:
            return False
    
    def set_volume(self, volume: float) -> bool:
        try:
            import pygame
            volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(volume)
            return True
        except Exception as e:
            return False
    
    def get_volume(self) -> float:
        try:
            import pygame
            return pygame.mixer.music.get_volume()
        except Exception as e:
            return 1.0
    
    def cleanup(self):
        if self.pygame_initialized:
            try:
                import pygame
                pygame.mixer.music.stop()
                time.sleep(0.2)
                pygame.mixer.music.unload()
                pygame.mixer.quit()
                self.pygame_initialized = False
            except Exception as e:
                pass


class PlaybackMonitor(threading.Thread):
    def __init__(self, pygame_manager: PygameManager, state: AudioState, 
                 playback_finished_callback: Callable):
        super().__init__()
        self.pygame_manager = pygame_manager
        self.state = state
        self.playback_finished_callback = playback_finished_callback
        self.should_stop = False
        self.daemon = True
    
    def run(self):
        while not self.should_stop and self.state.is_playing:
            if (not self.pygame_manager.is_playing() and 
                not self.state.is_seeking and 
                not self.state.is_paused):
                self.playback_finished_callback()
                break
            time.sleep(0.1)
    
    def stop(self):
        self.should_stop = True


class AudioCacheManager:
    def __init__(self, parent_window):
        self.parent_window = parent_window
    
    def get_cache_key(self, config) -> str:
        return f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
    
    def get_content_hash(self, config) -> str:
        import hashlib
        content = f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def is_content_unchanged(self, config) -> bool:
        current_hash = self.get_content_hash(config)
        return (self.parent_window.last_content_hash is not None and 
                current_hash == self.parent_window.last_content_hash)
    
    def cache_audio(self, cache_key: str, file_path: str):
        self.parent_window.audio_cache[cache_key] = file_path
        self.parent_window.current_audio_path = file_path
        self.parent_window.last_content_hash = self.get_content_hash(self.parent_window.config)
        self.parent_window.has_preview = True


class AudioFileCleaner:
    @staticmethod
    def cleanup_preview_audio(program_dir: str) -> int:
        try:
            preview_files = glob.glob(os.path.join(program_dir, "tmp_*.mp3"))
            stretched_files = glob.glob(os.path.join(program_dir, "*_stretched.mp3"))
            preview_files.extend(stretched_files)
            
            deleted_count = 0
            for file_path in preview_files:
                try:
                    for attempt in range(3):
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                deleted_count += 1
                                break
                        except PermissionError:
                            if attempt < 2:
                                time.sleep(0.1)
                        except Exception as e:
                            break
                except Exception as e:
                    pass
                    
            return deleted_count
            
        except Exception as e:
            return 0


class AudioSignals(QObject):
    playback_finished = pyqtSignal()
    progress_updated = pyqtSignal(int)
    preview_generated = pyqtSignal(str)
    volume_changed = pyqtSignal(float)
    position_changed = pyqtSignal(float)


class AudioPreview:
    def __init__(self, parent_window):
        self.parent_window = parent_window
        
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
        
        self.keyboard_scheme = KeyboardControlScheme.SCHEME_1
        
        self.is_paused = False
        self.is_seeking = False

    @property
    def is_paused(self):
        return self.state.is_paused

    @is_paused.setter
    def is_paused(self, value):
        self.state.is_paused = value

    @property
    def is_seeking(self):
        return self.state.is_seeking

    @is_seeking.setter
    def is_seeking(self, value):
        self.state.is_seeking = value

    def set_keyboard_scheme(self, scheme: int):
        if scheme in [1, 2, 3]:
            self.keyboard_scheme = scheme

    def get_keyboard_scheme(self) -> int:
        return self.keyboard_scheme

    def handle_key_event(self, event: QKeyEvent):
        if not self.state.is_playing:
            return
            
        key = event.key()
        modifiers = event.modifiers()
        
        if self.keyboard_scheme == KeyboardControlScheme.SCHEME_1:
            self._handle_scheme_1(key)
        elif self.keyboard_scheme == KeyboardControlScheme.SCHEME_2:
            self._handle_scheme_2(key, modifiers)
        elif self.keyboard_scheme == KeyboardControlScheme.SCHEME_3:
            self._handle_scheme_3(key)

    def _handle_scheme_1(self, key: int):
        if key == Qt.Key_Space:
            self.toggle_pause()
        elif key == Qt.Key_A:
            self._seek_relative(-5)
        elif key == Qt.Key_W:
            self._adjust_volume(0.1)
        elif key == Qt.Key_S:
            self._adjust_volume(-0.1)

    def _handle_scheme_2(self, key: int, modifiers):
        if key == Qt.Key_Shift and modifiers & Qt.RightButton:
            self.toggle_pause()
        elif key == Qt.Key_Up:
            self._adjust_volume(0.1)
        elif key == Qt.Key_Down:
            self._adjust_volume(-0.1)
        elif key == Qt.Key_Left:
            self._seek_relative(-5)
        elif key == Qt.Key_Minus:
            self._seek_relative(-10)

    def _handle_scheme_3(self, key: int):
        if key == Qt.Key_0 or key == Qt.Key_5:
            self.toggle_pause()
        elif key == Qt.Key_8:
            self._adjust_volume(0.1)
        elif key == Qt.Key_2:
            self._adjust_volume(-0.1)
        elif key == Qt.Key_4:
            self._seek_relative(-5)

    def _perform_seek(self, target_position: float):
        """执行音频跳转操作，确保时间基准一致性"""
        if not self.state.is_playing or self.state.current_audio_length <= 0:
            return
        target_position = max(0.0, min(target_position, self.state.current_audio_length))
        
        # 添加调试信息
        print(f"Seeking to position: {target_position}")
        
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

    def _seek_relative(self, seconds: float = 5.0):
        """相对跳转 - 基于当前位置进行跳转"""
        if not self.state.is_playing or self.state.current_audio_length <= 0:
            return
            
        # 获取当前播放位置
        current_position = self.get_current_playback_position()
        
        # 计算目标位置
        target_position = current_position + seconds
        
        # 执行跳转
        self._perform_seek(target_position)
        
        # 显示跳转提示
        direction = "前进" if seconds > 0 else "回退"
        self.parent_window.notification_manager.show_message(
            f"已{direction} {abs(seconds)} 秒", "I", 1000
        )

    def _adjust_volume(self, delta: float):
        new_volume = max(0.0, min(1.0, self.state.volume + delta))
        if new_volume != self.state.volume:
            self.set_volume(new_volume)
            
            volume_percent = int(new_volume * 100)
            self.parent_window.notification_manager.show_message(
                f"音量: {volume_percent}%", "I", 1000
            )

    def play_preview(self):
        cache_key = self.cache_manager.get_cache_key(self.parent_window.config)
        if (cache_key not in self.parent_window.audio_cache or 
            not os.path.exists(self.parent_window.audio_cache[cache_key])):
            self.parent_window.notification_manager.show_message("没有可用的预览音频，请先生成预览", "W", 3000)
            return
            
        if not self.cache_manager.is_content_unchanged(self.parent_window.config):
            self.parent_window.generation_page.preview_control.preview_button.setText("生成预览")
            self.parent_window.has_preview = False
            self.parent_window.notification_manager.show_message("文本内容已改变，请重新生成预览", "W", 3000)
            return
            
        if self.state.is_playing:
            self.stop_audio()
            
        self.parent_window.generation_page.preview_control.preview_progress.setValue(0)
        
        self.parent_window.current_audio_path = self.parent_window.audio_cache[cache_key]
        self._play_audio_file(self.parent_window.current_audio_path)

    def _play_audio_file(self, file_path: str, start_position: float = 0.0):
        """播放音频文件并初始化时间基准点"""
        try:
            print(f"[AudioPreview] 开始播放音频文件: {file_path}, 起始位置: {start_position}")
            
            if not self.pygame_manager._init_pygame():
                print(f"[AudioPreview] pygame初始化失败")
                return
                
            print(f"[AudioPreview] pygame初始化成功")
            
            if not self.pygame_manager.load_audio(file_path):
                print(f"[AudioPreview] 音频文件加载失败: {file_path}")
                return
                
            print(f"[AudioPreview] 音频文件加载成功: {file_path}")
            
            self.pygame_manager.set_volume(self.state.volume)
            print(f"[AudioPreview] 音量设置为: {self.state.volume}")
                
            if not self.pygame_manager.play_audio(start_position):
                print(f"[AudioPreview] 音频播放启动失败")
                return
            
            print(f"[AudioPreview] 音频播放启动成功")
            
            self.state.current_audio_length = self.pygame_manager.get_audio_length(file_path)
            self.state.current_audio_position = start_position
            
            # 初始化时间基准点：当前时间 - 起始位置，为后续时间计算提供基准
            self.state.time_reference = time.time() - start_position
            
            self.state.is_playing = True
            self.state.is_paused = False
            self.state.is_seeking = False
            
            generation_page = self.parent_window.generation_page
            generation_page.preview_control.set_playback_controls_enabled(True)
            generation_page.preview_control.update_pause_button_text(False)
            
            generation_page.preview_control.preview_progress.setValue(0)
            
            self.progress_timer.start(100)
            
            self.playback_monitor = PlaybackMonitor(
                self.pygame_manager, 
                self.state, 
                self.audio_signals.playback_finished.emit
            )
            self.playback_monitor.start()
            
            print(f"[AudioPreview] 音频播放设置完成，开始监控播放状态")
            
        except Exception as e:
            print(f"[AudioPreview] 播放音频异常: {e}")
            self.parent_window.notification_manager.show_message(f"播放音频时发生错误: {str(e)}", "E", 5000)

    def _on_playback_finished(self):
        self.state.is_playing = False
        self.state.is_paused = False
        self.state.is_seeking = False
        
        if hasattr(self.parent_window, 'generation_page'):
            generation_page = self.parent_window.generation_page
            generation_page.preview_control.set_playback_controls_enabled(False)
            generation_page.preview_control.update_preview_button_state(True, True)
            generation_page.preview_control.preview_progress.setValue(1000)
            generation_page.preview_control.update_pause_button_text(False)
            
            self.parent_window.notification_manager.show_message("音频播放完毕", "I", 2000)
            
        self.progress_timer.stop()

    def stop_audio(self):
        self.pygame_manager.stop_audio()
        
        time.sleep(0.1)
        
        self.state.is_playing = False
        self.state.is_paused = False
        self.state.is_seeking = False
        
        generation_page = self.parent_window.generation_page
        generation_page.preview_control.set_playback_controls_enabled(False)
        generation_page.preview_control.update_preview_button_state(False, False)
        generation_page.preview_control.update_pause_button_text(False)
        
        self.progress_timer.stop()
        generation_page.preview_control.preview_progress.setValue(0)
        
        if self.playback_monitor:
            self.playback_monitor.stop()
            self.playback_monitor = None

    def toggle_pause(self):
        """暂停/继续播放 - 使用时间基准点确保状态一致性"""
        if not self.pygame_manager.pygame_initialized:
            return False
            
        if not self.state.is_playing:
            return False
            
        if not self.state.is_paused:
            # 暂停播放
            self.pygame_manager.pause_audio()
            self.state.is_paused = True
            # 记录暂停时的精确位置
            self.state.current_audio_position = self.get_current_playback_position()
            self.parent_window.generation_page.preview_control.update_pause_button_text(True)
            self.parent_window.notification_manager.show_message("音频已暂停", "I", 1500)
            return True
        else:
            # 继续播放：重新计算时间基准点，确保时间同步
            self.pygame_manager.unpause_audio()
            self.state.is_paused = False
            self.state.time_reference = time.time() - self.state.current_audio_position
            self.parent_window.generation_page.preview_control.update_pause_button_text(False)
            self.parent_window.notification_manager.show_message("音频已继续", "I", 1500)
            return True

    def _update_progress(self):
        """更新播放进度 - 显示当前句子的播放进度"""
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
                        print(f"[AudioPreview] 进度更新: 句子{current_sentence_index+1}/{total_sentences}, "
                              f"当前句子进度{sentence_progress*100:.1f}%, 总进度{total_progress:.1f}%")

    def set_seeking(self, seeking: bool):
        self.state.is_seeking = seeking

    def seek_to_position(self, position: float):
        """跳转到指定位置"""
        if (self.state.is_playing and 
            self.state.current_audio_length > 0 and 
            self.pygame_manager.pygame_initialized):
            
            # 执行跳转
            self._perform_seek(position)

    def seek_to_percentage(self, percentage: float):
        if (self.state.is_playing and 
            self.state.current_audio_length > 0 and 
            self.pygame_manager.pygame_initialized):
            
            percentage = max(0.0, min(1.0, percentage))
            
            position = percentage * self.state.current_audio_length
            self.seek_to_position(position)
            
            # 移除重复的进度条设置，由seek_to_position发出的信号来更新进度条

    def set_volume(self, volume: float):
        try:
            volume = max(0.0, min(1.0, volume))
            self.state.volume = volume
            
            if self.pygame_manager.pygame_initialized:
                success = self.pygame_manager.set_volume(volume)
                if success:
                    self.audio_signals.volume_changed.emit(volume)
                return success
            return False
        except Exception as e:
            return False

    def get_volume(self) -> float:
        return self.state.volume
    
    def get_current_playback_position(self) -> float:
        """获取当前播放位置 - 基于时间基准点计算"""
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

    def _on_volume_changed(self, volume: float):
        if hasattr(self.parent_window, 'generation_page'):
            volume_percent = int(volume * 100)
            self.parent_window.generation_page.preview_control.volume_value_label.setText(f"{volume_percent}%")
            self.parent_window.generation_page.preview_control.volume_slider.setValue(volume_percent)

    def _on_position_changed(self, position: float):
        """位置变化处理 - 避免重复更新导致的UI闪烁"""
        current_time = time.time()
        
        # 跳转冷却期：避免短时间内重复更新进度条
        if current_time < self.state.seek_cooldown_until:
            return
            
        if (self.state.is_playing and 
            self.state.current_audio_length > 0 and
            hasattr(self.parent_window, 'generation_page')):
            
            percentage = position / self.state.current_audio_length
            progress = int(percentage * 1000)
            
            self.parent_window.generation_page.preview_control.preview_progress.setValue(progress)

    def force_stop_audio(self):
        try:
            self.pygame_manager.cleanup()
        except Exception as e:
            self.parent_window.notification_manager.show_message("程序出现错误 请重启程序", "E", 5000)

    def cleanup_preview_audio(self):
        try:
            self.force_stop_audio()
            
            program_dir = os.path.dirname(os.path.abspath(__file__))
            
            deleted_count = self.file_cleaner.cleanup_preview_audio(program_dir)
            
            self.parent_window.audio_cache.clear()
            self.parent_window.current_audio_path = None
            self.parent_window.has_preview = False
            
            return deleted_count
            
        except Exception as e:
            self.parent_window.notification_manager.show_message("程序出现错误 请重启程序", "E", 5000)
            return 0