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
        self._init_pygame()
    
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

    def _seek_relative(self, seconds: float):
        if not self.state.is_playing or self.state.current_audio_length <= 0:
            return
            
        current_pos = self.pygame_manager.get_current_position()
        new_pos = max(0, min(current_pos + seconds, self.state.current_audio_length))
        
        self.seek_to_position(new_pos)
        
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

    def _play_audio_file(self, file_path: str):
        try:
            if not self.pygame_manager._init_pygame():
                return
                
            if not self.pygame_manager.load_audio(file_path):
                return
                
            self.pygame_manager.set_volume(self.state.volume)
                
            if not self.pygame_manager.play_audio():
                return
            
            self.state.current_audio_length = self.pygame_manager.get_audio_length(file_path)
            self.state.current_audio_position = 0
            
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
            
        except Exception as e:
            traceback.print_exc()
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
        if not self.pygame_manager.pygame_initialized:
            return
            
        if self.state.is_playing:
            if not self.state.is_paused:
                self.pygame_manager.pause_audio()
                self.state.is_paused = True
                self.parent_window.generation_page.preview_control.update_pause_button_text(True)
                self.parent_window.notification_manager.show_message("音频已暂停", "I", 1500)
            else:
                self.pygame_manager.unpause_audio()
                self.state.is_paused = False
                self.parent_window.generation_page.preview_control.update_pause_button_text(False)
                self.parent_window.notification_manager.show_message("音频已继续", "I", 1500)

    def _update_progress(self):
        if (self.state.is_playing and 
            not self.state.is_seeking and 
            not self.state.is_paused and 
            self.pygame_manager.pygame_initialized):
            
            pos = self.pygame_manager.get_current_position()
            
            if self.state.current_audio_length > 0:
                progress = int((pos / self.state.current_audio_length) * 1000)
                progress = max(0, min(progress, 1000))
                self.parent_window.generation_page.preview_control.preview_progress.setValue(progress)

    def set_seeking(self, seeking: bool):
        self.state.is_seeking = seeking

    def seek_to_position(self, position: float):
        if (self.state.is_playing and 
            self.state.current_audio_length > 0 and 
            self.pygame_manager.pygame_initialized):
            
            position = max(0, min(position, self.state.current_audio_length))
            
            self.pygame_manager.play_audio(position)
            self.state.current_audio_position = position
            self.state.is_paused = False
            self.state.is_seeking = False
            self.parent_window.generation_page.preview_control.update_pause_button_text(False)
            
            self.audio_signals.position_changed.emit(position)

    def seek_to_percentage(self, percentage: float):
        if (self.state.is_playing and 
            self.state.current_audio_length > 0 and 
            self.pygame_manager.pygame_initialized):
            
            percentage = max(0.0, min(1.0, percentage))
            
            position = percentage * self.state.current_audio_length
            self.seek_to_position(position)
            
            progress = int(percentage * 1000)
            self.parent_window.generation_page.preview_control.preview_progress.setValue(progress)

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

    def _on_volume_changed(self, volume: float):
        if hasattr(self.parent_window, 'generation_page'):
            volume_percent = int(volume * 100)
            self.parent_window.generation_page.preview_control.volume_value_label.setText(f"{volume_percent}%")
            self.parent_window.generation_page.preview_control.volume_slider.setValue(volume_percent)

    def _on_position_changed(self, position: float):
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