# coding=utf-8
import os
import configparser
import tempfile
import threading
import time
from typing import Optional, Dict, Any, List, Callable, Mapping
from debug_logger import debug_logger, LogLevel


_NO_THEME_PROJECTION = object()


class ConfigSection:
    """配置段落基类 - 为不同类型的配置提供统一接口"""

    def __init__(self, settings_manager, section_name: str):
        self.settings_manager = settings_manager
        self.section_name = section_name

    def get_value(self, key: str, default: Any = None) -> Any:
        """获取配置值 - 子类必须实现具体类型转换"""
        raise NotImplementedError("子类必须实现get_value方法")

    def set_value(self, key: str, value: Any) -> bool:
        """设置配置值 - 子类必须实现"""
        raise NotImplementedError("子类必须实现set_value方法")


class StringConfigSection(ConfigSection):
    """字符串配置段落"""

    def get_value(self, key: str, default: str = "") -> str:
        """获取字符串配置值"""
        try:
            projected = self.settings_manager._get_authoritative_theme_value(
                self.section_name, key, _NO_THEME_PROJECTION
            )
            if projected is not _NO_THEME_PROJECTION:
                return str(projected)
            with self.settings_manager._config_lock:
                self.settings_manager._load_config()
                if self.section_name not in self.settings_manager.config:
                    return default
                val = self.settings_manager.config[self.section_name].get(key, default)
                return str(val) if val is not None else default
        except Exception as e:
            debug_logger.output("settings_manager", LogLevel.WARNING, f"获取字符串配置失败 [{self.section_name}] {key}: {e}", fold_code="CFG_ERR")
            return default

    def set_value(self, key: str, value: str) -> bool:
        """设置字符串配置值"""
        try:
            if self.settings_manager._is_theme_compatibility_write_blocked(
                self.section_name, key
            ):
                debug_logger.output(
                    "settings_manager",
                    LogLevel.WARNING,
                    f"权威主题状态已启用，拒绝旧主题写入口 [{self.section_name}] {key}",
                    fold_code="CFG_THEME",
                )
                return False
            with self.settings_manager._config_lock:
                loaded = self.settings_manager._load_config()
                if not loaded and not self.settings_manager._config_loaded:
                    debug_logger.output(
                        "settings_manager", LogLevel.ERROR,
                        f"配置尚未成功加载，拒绝写入 [{self.section_name}] {key}",
                        fold_code="CFG_ERR",
                    )
                    return False
                section_existed = self.section_name in self.settings_manager.config
                if not section_existed:
                    self.settings_manager.config[self.section_name] = {}
                option_existed = self.settings_manager.config.has_option(
                    self.section_name, key
                )
                previous_value = self.settings_manager.config.get(
                    self.section_name, key, raw=True, fallback=None
                )
                self.settings_manager.config[self.section_name][key] = str(value)
                debug_logger.output("settings_manager", LogLevel.INFO, f"Set string config: [{self.section_name}] {key}={value}", fold_code="CFG_SET")
                if self.settings_manager._save_config():
                    return True

                if option_existed:
                    self.settings_manager.config[self.section_name][key] = previous_value
                else:
                    self.settings_manager.config.remove_option(self.section_name, key)
                    if not section_existed:
                        self.settings_manager.config.remove_section(self.section_name)
                return False
        except Exception as e:
            debug_logger.output("settings_manager", LogLevel.ERROR, f"设置字符串配置失败 [{self.section_name}] {key}: {e}", fold_code="CFG_ERR")
            return False


class IntConfigSection(ConfigSection):
    """整数配置段落"""

    def get_value(self, key: str, default: int = 0) -> int:
        """获取整数配置值"""
        try:
            value_str = StringConfigSection(self.settings_manager, self.section_name).get_value(key, str(default))
            return int(value_str) if value_str else default
        except (ValueError, TypeError):
            return default

    def set_value(self, key: str, value: int) -> bool:
        """设置整数配置值"""
        return StringConfigSection(self.settings_manager, self.section_name).set_value(key, str(value))


class FloatConfigSection(ConfigSection):
    """浮点数配置段落"""

    def get_value(self, key: str, default: float = 0.0) -> float:
        """获取浮点数配置值"""
        try:
            value_str = StringConfigSection(self.settings_manager, self.section_name).get_value(key, str(default))
            return float(value_str) if value_str else default
        except (ValueError, TypeError):
            return default

    def set_value(self, key: str, value: float) -> bool:
        """设置浮点数配置值"""
        return StringConfigSection(self.settings_manager, self.section_name).set_value(key, str(value))


class BoolConfigSection(ConfigSection):
    """布尔值配置段落"""

    def get_value(self, key: str, default: bool = False) -> bool:
        """获取布尔值配置值"""
        try:
            value_str = StringConfigSection(self.settings_manager, self.section_name).get_value(key, str(default))
            return value_str.lower() == 'true'
        except Exception:
            return default

    def set_value(self, key: str, value: bool) -> bool:
        """设置布尔值配置值"""
        return StringConfigSection(self.settings_manager, self.section_name).set_value(key, str(value))


class CompatibilityConfigSection:
    """向后兼容的配置段落 - 将旧的 Custom 段落映射到新的分类段落"""

    KEY_MAPPING = {
        'window_size': 'Window',
        'is_first_run': 'Window',
        'current_theme': 'Theme',
        'background_color': 'Theme',
        'card_background_color': 'Theme',
        'component_background_color': 'Theme',
        'highlight_button_color': 'Theme',
        'text_color': 'Theme',
        'global_font': 'Font',
        'min_font_size': 'Font',
        'max_font_size': 'Font',
        'notification_info_color': 'Notification',
        'notification_warning_color': 'Notification',
        'notification_error_color': 'Notification',
        'animation_appear': 'Notification',
        'animation_disappear': 'Notification',
        'animation_move': 'Notification',
        'position_m': 'Notification',
        'position_n': 'Notification',
        'width_ratio': 'Notification',
        'height_ratio': 'Notification',
        'max_visible': 'Notification',
        'offset_n': 'Notification',
        'spacing_n': 'Notification',
        'auto_close_time': 'Notification',
        'tab_order': 'Tab',
        'tab_visibility': 'Tab',
        'initial_tab': 'Tab',
        'tab_switch_speed': 'Tab',
        'indicator_animation_speed': 'Tab',
        'indicator_x_offset': 'Tab',
        'indicator_y_offset': 'Tab',
        'indicator_width_adjust': 'Tab',
        'indicator_height_adjust': 'Tab',
        'hk_toggle_pause': 'Hotkeys',
        'hk_seek_backward': 'Hotkeys',
        'hk_seek_forward': 'Hotkeys',
        'hk_volume_up': 'Hotkeys',
        'hk_volume_down': 'Hotkeys',
        'hk_next_sentence': 'Hotkeys',
        'hk_prev_sentence': 'Hotkeys',
        'use_keyboard_hook': 'Hotkeys',
        'use_sdl_input': 'Hotkeys',
        'default_punctuation_hint': 'Dictation',
        'default_pause_marks': 'Dictation',
        'online_import_mode': 'Dictation',
        'auto_play_enabled': 'Dictation',
        'auto_play_interval': 'Dictation',
        'auto_play_interval_mode': 'Dictation',
        'auto_play_interval_fixed': 'Dictation',
        'auto_play_interval_dynamic': 'Dictation',
        'github_acceleration': 'Download',
        'download_threads': 'Download',
        'max_download_threads': 'Download',
        'github_mirror': 'Download',
        'ai_model_chat_provider': 'AI_Models',
        'ai_model_chat_model': 'AI_Models',
        'ai_model_vision_provider': 'AI_Models',
        'ai_model_vision_model': 'AI_Models',
        'ai_model_tts_provider': 'AI_Models',
        'ai_model_tts_model': 'AI_Models',
        'default_model_mimo': 'AI_Models',
        'default_model_qwen': 'AI_Models',
        'default_model_chatglm': 'AI_Models',
        'default_model_minimax': 'AI_Models',
        'default_model_ms': 'AI_Models',
        'music_playlists': 'Music',
        'music_queue_data': 'Music',
        'music_play_mode': 'Music',
    }

    def __init__(self, settings_manager):
        self.settings_manager = settings_manager

    def _get_section_for_key(self, key: str) -> str:
        return self.KEY_MAPPING.get(key, 'Custom')

    def get_value(self, key: str, default: str = "") -> str:
        section_name = self._get_section_for_key(key)
        section = StringConfigSection(self.settings_manager, section_name)
        value = section.get_value(key, None)
        if value is not None:
            return value
        if section_name != 'Custom':
            old_section = StringConfigSection(self.settings_manager, 'Custom')
            value = old_section.get_value(key, None)
            if value is not None:
                section.set_value(key, value)
                return value
        return default

    def set_value(self, key: str, value: str) -> bool:
        section_name = self._get_section_for_key(key)
        section = StringConfigSection(self.settings_manager, section_name)
        return section.set_value(key, value)


class SettingsManager:
    """设置管理器 - 使用ini文件保存配置 (单例模式)"""
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._config_lock = threading.RLock()
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    CONFIG_FILE = "config/settings.ini"
    CONFIG_REFRESH_INTERVAL_SECONDS = 15.0

    SECTION_API_KEYS = 'API_Keys'
    SECTION_DEFAULT_PATHS = 'Default_Paths'
    SECTION_DEFAULT_PARAMETERS = 'Default_Parameters'
    SECTION_PAGE_OFFSETS = 'Page_Offsets'
    SECTION_Custom = 'Custom'

    SECTION_WINDOW = 'Window'
    SECTION_THEME = 'Theme'
    SECTION_FONT = 'Font'
    SECTION_NOTIFICATION = 'Notification'
    SECTION_TAB = 'Tab'
    SECTION_HOTKEYS = 'Hotkeys'
    SECTION_DICTATION = 'Dictation'
    SECTION_DOWNLOAD = 'Download'
    SECTION_AI_MODELS = 'AI_Models'
    SECTION_MUSIC = 'Music'
    SECTION_STREAMING = 'Streaming'

    THEME_COMPATIBILITY_KEY_SECTIONS = {
        'current_theme': SECTION_THEME,
        'background_color': SECTION_THEME,
        'card_background_color': SECTION_THEME,
        'component_background_color': SECTION_THEME,
        'highlight_button_color': SECTION_THEME,
        'text_color': SECTION_THEME,
        'notification_info_color': SECTION_NOTIFICATION,
        'notification_warning_color': SECTION_NOTIFICATION,
        'notification_error_color': SECTION_NOTIFICATION,
    }

    def __init__(self):
        with self._config_lock:
            if self._initialized:
                return
            from misc_func import get_app_base_path
            self.config_file = os.path.join(get_app_base_path(), self.CONFIG_FILE)
            self.config = configparser.ConfigParser()
            self._config_loaded = False
            self._last_refresh_monotonic = None
            self._refresh_interval_seconds = self.CONFIG_REFRESH_INTERVAL_SECONDS
            self._theme_projection_provider = None
            self._theme_projection_reading = False
            self._theme_projection_write_depth = 0
            self._init_config_sections()
            self._ensure_config_file()
            self._initialized = True

    def _init_config_sections(self):
        """初始化配置段落管理器"""
        debug_logger.output("settings_manager", LogLevel.INFO, "初始化配置段落管理器", fold_code="SM_INIT")
        self.api_keys = StringConfigSection(self, self.SECTION_API_KEYS)
        self.default_paths = StringConfigSection(self, self.SECTION_DEFAULT_PATHS)
        self.default_parameters = StringConfigSection(self, self.SECTION_DEFAULT_PARAMETERS)
        self.page_offsets = StringConfigSection(self, self.SECTION_PAGE_OFFSETS)
        self.window = StringConfigSection(self, self.SECTION_WINDOW)
        self.theme = StringConfigSection(self, self.SECTION_THEME)
        self.font = StringConfigSection(self, self.SECTION_FONT)
        self.notification = StringConfigSection(self, self.SECTION_NOTIFICATION)
        self.tab = StringConfigSection(self, self.SECTION_TAB)
        self.hotkeys = StringConfigSection(self, self.SECTION_HOTKEYS)
        self.dictation = StringConfigSection(self, self.SECTION_DICTATION)
        self.download = StringConfigSection(self, self.SECTION_DOWNLOAD)
        self.ai_models = StringConfigSection(self, self.SECTION_AI_MODELS)
        self.music = StringConfigSection(self, self.SECTION_MUSIC)
        self.streaming = StringConfigSection(self, self.SECTION_STREAMING)
        self.Custom = CompatibilityConfigSection(self)

    def bind_theme_projection_provider(
        self, provider: Optional[Callable[[], Mapping[str, Any]]]
    ) -> None:
        """Bind authoritative theme projection reads to the new theme service."""
        if provider is not None and not callable(provider):
            raise TypeError("theme projection provider must be callable or None")
        with self._config_lock:
            self._theme_projection_provider = provider

    def _get_authoritative_theme_value(self, section: str, key: str, default):
        expected_section = self.THEME_COMPATIBILITY_KEY_SECTIONS.get(key)
        provider = getattr(self, '_theme_projection_provider', None)
        if expected_section != section or provider is None:
            return default
        with self._config_lock:
            if self._theme_projection_reading:
                return default
            self._theme_projection_reading = True
            try:
                projection = provider()
                if not isinstance(projection, Mapping):
                    return default
                return projection.get(key, default)
            except Exception as e:
                debug_logger.output(
                    "settings_manager", LogLevel.ERROR,
                    f"读取权威主题投影失败: {e}", fold_code="CFG_THEME",
                )
                return default
            finally:
                self._theme_projection_reading = False

    def _is_theme_compatibility_write_blocked(self, section: str, key: str) -> bool:
        return (
            self.THEME_COMPATIBILITY_KEY_SECTIONS.get(key) == section
            and getattr(self, '_theme_projection_provider', None) is not None
            and getattr(self, '_theme_projection_write_depth', 0) == 0
        )

    def project_theme_compatibility(self, projection: Mapping[str, Any]) -> bool:
        """Atomically repair the legacy INI projection from authoritative state."""
        missing = [
            key for key in self.THEME_COMPATIBILITY_KEY_SECTIONS if key not in projection
        ]
        if missing:
            raise ValueError(f"主题兼容投影缺少字段: {', '.join(missing)}")
        with self._config_lock:
            loaded = self._load_config()
            if not loaded and not self._config_loaded:
                return False
            affected_sections = set(self.THEME_COMPATIBILITY_KEY_SECTIONS.values())
            previous = {
                section: dict(self.config[section]) if section in self.config else None
                for section in affected_sections
            }
            self._theme_projection_write_depth += 1
            try:
                for key, section in self.THEME_COMPATIBILITY_KEY_SECTIONS.items():
                    if section not in self.config:
                        self.config[section] = {}
                    self.config[section][key] = str(projection[key])
                if self._save_config():
                    return True
                for section, values in previous.items():
                    if values is None:
                        self.config.remove_section(section)
                    else:
                        if section in self.config:
                            self.config.remove_section(section)
                        self.config[section] = values
                return False
            finally:
                self._theme_projection_write_depth -= 1

    def _ensure_config_file(self):
        if not os.path.exists(self.config_file):
            debug_logger.output("settings_manager", LogLevel.WARNING, "配置文件不存在，创建默认配置", fold_code="CFG_INIT")
            self._create_default_config()
        else:
            self._check_and_migrate_old_format()

    def _create_default_config(self):
        """创建默认配置文件"""
        from misc_func import CustomConfig
        debug_logger.output("settings_manager", LogLevel.INFO, "正在创建默认配置文件...", fold_code="CFG_CREATE")

        self.config[self.SECTION_API_KEYS] = {
            'api_key_ChatGLM': '',
            'api_key_Qwen': '',
            'api_key_KIMI': '',
            'api_key_Minimax': '',
            'api_key_Mimo': ''
        }

        self.config[self.SECTION_DEFAULT_PATHS] = {
            'default_save_path': ''
        }

        self.config[self.SECTION_DEFAULT_PARAMETERS] = {
            'default_speed': '0',
            'stretch_factor': '1.0',
            'stretch_enabled': 'False'
        }

        self.config[self.SECTION_PAGE_OFFSETS] = {}

        self.config[self.SECTION_WINDOW] = {
            'window_size': '1024x768',
            'is_first_run': 'True'
        }

        self.config[self.SECTION_THEME] = {
            'current_theme': '仁物蓝',
            'background_color': CustomConfig.DEFAULT_COLORS['background'],
            'card_background_color': CustomConfig.DEFAULT_COLORS['card_background'],
            'component_background_color': CustomConfig.DEFAULT_COLORS['component_background'],
            'highlight_button_color': CustomConfig.DEFAULT_COLORS['highlight_button'],
            'text_color': CustomConfig.DEFAULT_COLORS['text_color']
        }

        self.config[self.SECTION_FONT] = {
            'global_font': CustomConfig.DEFAULT_FONTS['global_font'],
            'min_font_size': CustomConfig.DEFAULT_FONTS['min_font_size'],
            'max_font_size': CustomConfig.DEFAULT_FONTS['max_font_size']
        }

        self.config[self.SECTION_NOTIFICATION] = {
            'notification_info_color': CustomConfig.DEFAULT_COLORS['notification_info'],
            'notification_warning_color': CustomConfig.DEFAULT_COLORS['notification_warning'],
            'notification_error_color': CustomConfig.DEFAULT_COLORS['notification_error'],
            'animation_appear': CustomConfig.DEFAULT_NOTIFICATIONS['animation_appear'],
            'animation_disappear': CustomConfig.DEFAULT_NOTIFICATIONS['animation_disappear'],
            'animation_move': CustomConfig.DEFAULT_NOTIFICATIONS['animation_move'],
            'position_m': CustomConfig.DEFAULT_NOTIFICATIONS['position_m'],
            'position_n': CustomConfig.DEFAULT_NOTIFICATIONS['position_n'],
            'width_ratio': CustomConfig.DEFAULT_NOTIFICATIONS['width_ratio'],
            'height_ratio': CustomConfig.DEFAULT_NOTIFICATIONS['height_ratio'],
            'max_visible': CustomConfig.DEFAULT_NOTIFICATIONS['max_visible'],
            'offset_n': CustomConfig.DEFAULT_NOTIFICATIONS['offset_n'],
            'spacing_n': CustomConfig.DEFAULT_NOTIFICATIONS['spacing_n'],
            'auto_close_time': CustomConfig.DEFAULT_NOTIFICATIONS['auto_close_time']
        }

        self.config[self.SECTION_TAB] = {
            'tab_order': 'welcome,dictation,settings,personalization,misc',
            'tab_visibility': 'welcome,dictation,settings,personalization,misc',
            'initial_tab': 'welcome',
            'tab_switch_speed': '300',
            'indicator_animation_speed': '50'
        }

        self.config[self.SECTION_HOTKEYS] = {
            'hk_toggle_pause': '32',
            'hk_seek_backward': '65',
            'hk_seek_forward': '68',
            'hk_volume_up': '87',
            'hk_volume_down': '83',
            'hk_next_sentence': '16777236',
            'hk_prev_sentence': '16777234',
            'use_keyboard_hook': 'True',
            'use_sdl_input': 'False'
        }

        self.config[self.SECTION_DICTATION] = {
            'default_punctuation_hint': 'True',
            'default_pause_marks': '',
            'online_import_mode': 'False',
            'auto_play_interval': '1.0',
            'auto_play_enabled': 'False',
            'auto_play_interval_mode': 'fixed',
            'auto_play_interval_fixed': '1.0',
            'auto_play_interval_dynamic': '1.0'
        }

        self.config[self.SECTION_DOWNLOAD] = {
            'github_acceleration': '0'
        }

        self.config[self.SECTION_AI_MODELS] = {
            'ai_model_chat_provider': 'ChatGLM',
            'ai_model_chat_model': 'GLM-4-Flash',
            'ai_model_vision_provider': 'ChatGLM',
            'ai_model_vision_model': 'GLM-4V-Flash',
            'ai_model_tts_provider': 'Microsoft',
            'ai_model_tts_model': 'edge-tts',
            'default_model_mimo': 'edge-tts',
            'default_model_qwen': 'qwen3-tts-flash',
            'default_model_chatglm': 'GLM-TTS',
            'default_model_minimax': 'speech-2.8-turbo',
            'default_model_ms': 'edge-tts'
        }

        self.config[self.SECTION_MUSIC] = {
            'music_playlists': '',
            'music_queue_data': '[]',
            'music_play_mode': '0'
        }

        self.config[self.SECTION_STREAMING] = {}

        self.config[self.SECTION_Custom] = {}

        self._save_config()

    def _load_config(self, force: bool = False) -> bool:
        """按需刷新内存配置快照；失败时保留上一份有效快照。"""
        with self._config_lock:
            now = time.monotonic()
            if (
                not force
                and self._last_refresh_monotonic is not None
                and now - self._last_refresh_monotonic
                < self._refresh_interval_seconds
            ):
                return self._config_loaded

            self._last_refresh_monotonic = now
            try:
                snapshot = configparser.ConfigParser()
                loaded_files = snapshot.read(self.config_file, encoding='utf-8')
                if not loaded_files:
                    raise FileNotFoundError(self.config_file)
            except Exception as e:
                debug_logger.output(
                    "settings_manager", LogLevel.ERROR,
                    f"读取配置文件失败，继续使用内存快照: {e}",
                    fold_code="CFG_ERR",
                )
                return False

            self.config = snapshot
            self._config_loaded = True
            return True

    def force_reload(self) -> bool:
        """立即从磁盘刷新配置，供未来的手动刷新入口调用。"""
        return self._load_config(force=True)

    def set_refresh_interval(self, seconds: float) -> None:
        """设置配置快照的刷新间隔，单位为秒。"""
        interval = float(seconds)
        if interval < 0:
            raise ValueError("配置刷新间隔不能小于 0")
        with self._config_lock:
            self._refresh_interval_seconds = interval

    def get_refresh_interval(self) -> float:
        with self._config_lock:
            return self._refresh_interval_seconds

    def _save_config(self) -> bool:
        """将当前内存快照原子写入磁盘。"""
        with self._config_lock:
            temp_path = None
            temp_fd = None
            try:
                debug_logger.output("settings_manager", LogLevel.INFO, f"正在保存配置到文件: {self.config_file}", fold_code="CFG_SAVE")
                config_dir = os.path.dirname(self.config_file) or os.curdir
                os.makedirs(config_dir, exist_ok=True)
                temp_fd, temp_path = tempfile.mkstemp(
                    prefix=f".{os.path.basename(self.config_file)}.",
                    suffix=".tmp",
                    dir=config_dir,
                )
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as configfile:
                    temp_fd = None
                    self.config.write(configfile)
                    configfile.flush()
                    os.fsync(configfile.fileno())
                os.replace(temp_path, self.config_file)
                temp_path = None
                self._config_loaded = True
                self._last_refresh_monotonic = time.monotonic()
                return True
            except Exception as e:
                debug_logger.output("settings_manager", LogLevel.ERROR, f"保存配置文件失败: {e}", fold_code="CFG_ERR")
                return False
            finally:
                if temp_fd is not None:
                    os.close(temp_fd)
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

    def _check_and_migrate_old_format(self):
        with self._config_lock:
            try:
                if not self._load_config(force=True):
                    return
                if 'Custom' not in self.config:
                    return
                custom_section = self.config['Custom']
                migration_needed = False
                key_indicators = ['window_size', 'current_theme', 'global_font', 'hk_toggle_pause',
                                'ai_model_chat_provider', 'music_play_mode']
                for key in key_indicators:
                    if key in custom_section:
                        migration_needed = True
                        break
                if not migration_needed:
                    debug_logger.output("settings_manager", LogLevel.INFO, "配置文件已是新格式，无需迁移", fold_code="CFG_MIGRATE")
                    return
                debug_logger.output("settings_manager", LogLevel.WARNING, "检测到旧格式配置文件，开始自动迁移...", fold_code="CFG_MIGRATE")
                self._backup_config_file()
                self._migrate_custom_section()
                debug_logger.output("settings_manager", LogLevel.INFO, "配置文件迁移完成", fold_code="CFG_MIGRATE")
            except Exception as e:
                debug_logger.output("settings_manager", LogLevel.ERROR, f"配置文件迁移失败: {e}", fold_code="CFG_ERR")

    def _backup_config_file(self):
        try:
            from datetime import datetime
            from misc_func import get_app_base_path
            backup_dir = os.path.join(get_app_base_path(), "cache", "backup")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"settings.ini.backup.{timestamp}"
            backup_path = os.path.join(backup_dir, backup_filename)
            import shutil
            shutil.copy2(self.config_file, backup_path)
            debug_logger.output("settings_manager", LogLevel.INFO, f"配置文件已备份到: {backup_path}", fold_code="CFG_BACKUP")
        except Exception as e:
            debug_logger.output("settings_manager", LogLevel.ERROR, f"备份配置文件失败: {e}", fold_code="CFG_ERR")

    def _migrate_custom_section(self):
        key_mapping = {
            'window_size': self.SECTION_WINDOW,
            'is_first_run': self.SECTION_WINDOW,
            'current_theme': self.SECTION_THEME,
            'background_color': self.SECTION_THEME,
            'card_background_color': self.SECTION_THEME,
            'component_background_color': self.SECTION_THEME,
            'highlight_button_color': self.SECTION_THEME,
            'text_color': self.SECTION_THEME,
            'global_font': self.SECTION_FONT,
            'min_font_size': self.SECTION_FONT,
            'max_font_size': self.SECTION_FONT,
            'notification_info_color': self.SECTION_NOTIFICATION,
            'notification_warning_color': self.SECTION_NOTIFICATION,
            'notification_error_color': self.SECTION_NOTIFICATION,
            'animation_appear': self.SECTION_NOTIFICATION,
            'animation_disappear': self.SECTION_NOTIFICATION,
            'animation_move': self.SECTION_NOTIFICATION,
            'position_m': self.SECTION_NOTIFICATION,
            'position_n': self.SECTION_NOTIFICATION,
            'width_ratio': self.SECTION_NOTIFICATION,
            'height_ratio': self.SECTION_NOTIFICATION,
            'max_visible': self.SECTION_NOTIFICATION,
            'offset_n': self.SECTION_NOTIFICATION,
            'spacing_n': self.SECTION_NOTIFICATION,
            'auto_close_time': self.SECTION_NOTIFICATION,
            'tab_order': self.SECTION_TAB,
            'tab_visibility': self.SECTION_TAB,
            'initial_tab': self.SECTION_TAB,
            'tab_switch_speed': self.SECTION_TAB,
            'indicator_animation_speed': self.SECTION_TAB,
            'indicator_x_offset': self.SECTION_TAB,
            'indicator_y_offset': self.SECTION_TAB,
            'indicator_width_adjust': self.SECTION_TAB,
            'indicator_height_adjust': self.SECTION_TAB,
            'hk_toggle_pause': self.SECTION_HOTKEYS,
            'hk_seek_backward': self.SECTION_HOTKEYS,
            'hk_seek_forward': self.SECTION_HOTKEYS,
            'hk_volume_up': self.SECTION_HOTKEYS,
            'hk_volume_down': self.SECTION_HOTKEYS,
            'hk_next_sentence': self.SECTION_HOTKEYS,
            'hk_prev_sentence': self.SECTION_HOTKEYS,
            'use_keyboard_hook': self.SECTION_HOTKEYS,
            'use_sdl_input': self.SECTION_HOTKEYS,
            'default_punctuation_hint': self.SECTION_DICTATION,
            'default_pause_marks': self.SECTION_DICTATION,
            'online_import_mode': self.SECTION_DICTATION,
            'github_acceleration': self.SECTION_DOWNLOAD,
            'download_threads': self.SECTION_DOWNLOAD,
            'max_download_threads': self.SECTION_DOWNLOAD,
            'github_mirror': self.SECTION_DOWNLOAD,
            'ai_model_chat_provider': self.SECTION_AI_MODELS,
            'ai_model_chat_model': self.SECTION_AI_MODELS,
            'ai_model_vision_provider': self.SECTION_AI_MODELS,
            'ai_model_vision_model': self.SECTION_AI_MODELS,
            'ai_model_tts_provider': self.SECTION_AI_MODELS,
            'ai_model_tts_model': self.SECTION_AI_MODELS,
            'default_model_mimo': self.SECTION_AI_MODELS,
            'default_model_qwen': self.SECTION_AI_MODELS,
            'default_model_chatglm': self.SECTION_AI_MODELS,
            'default_model_minimax': self.SECTION_AI_MODELS,
            'default_model_ms': self.SECTION_AI_MODELS,
            'music_playlists': self.SECTION_MUSIC,
            'music_queue_data': self.SECTION_MUSIC,
            'music_play_mode': self.SECTION_MUSIC,
        }
        custom_section = self.config['Custom']
        migrated_count = 0
        for key, value in list(custom_section.items()):
            target_section = key_mapping.get(key)
            if target_section:
                if target_section not in self.config:
                    self.config[target_section] = {}
                self.config[target_section][key] = value
                migrated_count += 1
                debug_logger.output("settings_manager", LogLevel.DEBUG, f"迁移配置项: {key} -> [{target_section}]", fold_code="CFG_MIGRATE")
        known_keys = set(key_mapping.keys())
        unknown_items = {k: v for k, v in custom_section.items() if k not in known_keys}
        self.config.remove_section('Custom')
        self.config['Custom'] = unknown_items
        self._save_config()
        debug_logger.output("settings_manager", LogLevel.INFO, f"成功迁移 {migrated_count} 个配置项", fold_code="CFG_MIGRATE")
        if unknown_items:
            debug_logger.output("settings_manager", LogLevel.INFO, f"保留 {len(unknown_items)} 个未知配置项在 [Custom] 段落", fold_code="CFG_MIGRATE")

    def get_api_key(self, key_name: str) -> str:
        val = self.api_keys.get_value(key_name, '')
        debug_logger.output("settings_manager", LogLevel.INFO, f"获取 API Key: {key_name}", fold_code="CFG_API")
        return val

    def set_api_key(self, key_name: str, value: str) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置 API Key: {key_name}", fold_code="CFG_API")
        return self.api_keys.set_value(key_name, value)

    def get_default_save_path(self) -> str:
        val = self.default_paths.get_value('default_save_path', '')
        debug_logger.output("settings_manager", LogLevel.INFO, f"获取默认保存路径: {val}", fold_code="CFG_PATH")
        return val

    def set_default_save_path(self, value: str) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置默认保存路径: {value}", fold_code="CFG_PATH")
        return self.default_paths.set_value('default_save_path', value)

    def get_default_speed(self) -> int:
        speed_str = self.default_parameters.get_value('default_speed', '0')
        try:
            speed = int(speed_str) if speed_str else 0
            debug_logger.output("settings_manager", LogLevel.INFO, f"获取默认语速: {speed}", fold_code="CFG_PARAM")
            return speed
        except (ValueError, TypeError):
            debug_logger.output("settings_manager", LogLevel.WARNING, f"默认语速解析失败: {speed_str}", fold_code="CFG_ERR")
            return 0

    def set_default_speed(self, value: int) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置默认语速: {value}", fold_code="CFG_PARAM")
        return self.default_parameters.set_value('default_speed', str(value))

    def get_is_first_run(self) -> bool:
        val = self.Custom.get_value('is_first_run', 'True')
        debug_logger.output("settings_manager", LogLevel.INFO, f"获取是否首次运行: {val}", fold_code="CFG_FIRSTRUN")
        return val.lower() == 'true'

    def set_is_first_run(self, value: bool) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置是否首次运行: {value}", fold_code="CFG_FIRSTRUN")
        return self.Custom.set_value('is_first_run', str(value))

    def get_stretch_factor(self) -> float:
        stretch_str = self.default_parameters.get_value('stretch_factor', '1.0')
        try:
            factor = float(stretch_str) if stretch_str else 1.0
            debug_logger.output("settings_manager", LogLevel.INFO, f"获取拉伸倍数: {factor}", fold_code="CFG_PARAM")
            return factor
        except (ValueError, TypeError):
            debug_logger.output("settings_manager", LogLevel.WARNING, f"拉伸倍数解析失败: {stretch_str}", fold_code="CFG_ERR")
            return 1.0

    def set_stretch_factor(self, value: float) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置拉伸倍数: {value}", fold_code="CFG_PARAM")
        return self.default_parameters.set_value('stretch_factor', str(value))

    def get_stretch_enabled(self) -> bool:
        enabled_str = self.default_parameters.get_value('stretch_enabled', 'False')
        enabled = enabled_str.lower() == 'true'
        debug_logger.output("settings_manager", LogLevel.INFO, f"获取拉伸启用状态: {enabled}", fold_code="CFG_PARAM")
        return enabled

    def set_stretch_enabled(self, value: bool) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置拉伸启用状态: {value}", fold_code="CFG_PARAM")
        return self.default_parameters.set_value('stretch_enabled', str(value))

    def set_offset_value(self, key: str, value: str) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置页码偏移量: {key}={value}", fold_code="CFG_OFFSET")
        return self.page_offsets.set_value(key, value)

    def get_offset_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.page_offsets.get_value(key, default)
        debug_logger.output("settings_manager", LogLevel.INFO, f"获取页码偏移量: {key}={val}", fold_code="CFG_OFFSET")
        return val

    def get_Custom_value(self, key: str, default: str = "") -> str:
        val = self.Custom.get_value(key, default)
        return val

    def set_Custom_value(self, key: str, value: str) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置个性化设置: {key}={value}", fold_code="CFG_CUSTOM")
        return self.Custom.set_value(key, value)

    def get_github_acceleration(self) -> int:
        try:
            acceleration_str = self.Custom.get_value('github_acceleration', '0')
            acceleration = int(acceleration_str) if acceleration_str else 0
            debug_logger.output("settings_manager", LogLevel.INFO, f"获取GitHub加速选项: {acceleration}", fold_code="CFG_NET")
            return acceleration
        except (ValueError, TypeError):
            debug_logger.output("settings_manager", LogLevel.WARNING, "GitHub加速选项解析失败", fold_code="CFG_ERR")
            return 0

    def set_github_acceleration(self, value: int) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置GitHub加速选项: {value}", fold_code="CFG_NET")
        return self.Custom.set_value('github_acceleration', str(value))

    def get_download_thread_num(self) -> int:
        try:
            thread_num_str = self.Custom.get_value('download_thread_num', '5')
            thread_num = int(thread_num_str) if thread_num_str else 5
            final_num = max(1, min(32, thread_num))
            debug_logger.output("settings_manager", LogLevel.INFO, f"获取下载线程数: {final_num}", fold_code="CFG_NET")
            return final_num
        except (ValueError, TypeError):
            debug_logger.output("settings_manager", LogLevel.WARNING, "下载线程数解析失败", fold_code="CFG_ERR")
            return 5

    def set_download_thread_num(self, value: int) -> bool:
        try:
            thread_num = int(value)
            if not 0 < thread_num <= 32:
                debug_logger.output("settings_manager", LogLevel.WARNING, f"设置无效的下载线程数: {thread_num}", fold_code="CFG_NET")
                return False
            debug_logger.output("settings_manager", LogLevel.INFO, f"设置下载线程数: {thread_num}", fold_code="CFG_NET")
            return self.Custom.set_value('download_thread_num', str(thread_num))
        except (ValueError, TypeError):
            return False

    def get_online_import_mode(self) -> bool:
        try:
            mode_str = self.Custom.get_value('online_import_mode', 'False')
            mode = mode_str.lower() == 'true'
            debug_logger.output("settings_manager", LogLevel.INFO, f"获取在线导入模式: {mode}", fold_code="CFG_NET")
            return mode
        except Exception:
            return False

    def set_online_import_mode(self, value: bool) -> bool:
        debug_logger.output("settings_manager", LogLevel.INFO, f"设置在线导入模式: {value}", fold_code="CFG_NET")
        return self.Custom.set_value('online_import_mode', str(value))

    def get_all_settings(self) -> Dict[str, Dict[str, str]]:
        debug_logger.output("settings_manager", LogLevel.INFO, "获取所有配置项", fold_code="CFG_ALL")
        with self._config_lock:
            self._load_config()
            settings = {}
            for section in self.config.sections():
                settings[section] = dict(self.config[section])
            return settings

    def reset_to_defaults(self) -> bool:
        with self._config_lock:
            try:
                debug_logger.output("settings_manager", LogLevel.WARNING, "正在重置所有配置为默认值", fold_code="CFG_RESET")
                self.config = configparser.ConfigParser()
                self._config_loaded = True
                self._create_default_config()
                return True
            except Exception as e:
                debug_logger.output("settings_manager", LogLevel.ERROR, f"重置设置失败: {e}", fold_code="CFG_ERR")
                return False
