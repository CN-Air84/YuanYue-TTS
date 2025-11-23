# coding=utf-8
import os
import hashlib
import datetime
from typing import Optional, Dict, Any, List, Tuple  # 新增Tuple导入
import configparser
'''
本段代码在SimeonTest Re1时使用 DeepSeek 重构，
DeepSeek送我的屎山，哎哟我，太香了👍👍👍
This code uses DeepSeek refactoring at Simeontest RE1,
deepseek sent me a shit mountain. Oh, my God, it smells so good.(lol)
'''
class VoiceConfig:
    """音色配置类 - 管理所有音色相关配置"""
    
    # 硬编码音色参数设置
    EDGE_VOICES = [
        '（以下为中文普通话音色）',
        'zh-CN-Yunyang', 'zh-CN-Yunxia', 'zh-CN-Yunxi',
        'zh-CN-Yunjian', 'zh-CN-Xiaoyi', 'zh-CN-Xiaoxiao',
        '（以下为英语音色）',
        'en-US-Ana', 'en-US-Andrew', 'en-US-Aria',
        'en-US-Ava', 'en-US-Brian', 'en-US-Christopher',
        'en-US-Emma', 'en-US-Eric', 'en-US-Guy',
        'en-US-Jenny', 'en-US-Michelle', 'en-US-Roger', 'en-US-Steffan',
        '（以下为中文方言音色）', 'zh-CN-liaoning-Xiaobei', 'zh-CN-shaanxi-Xiaoni',
        '（以下为日语音色）', 'ja-JP-Keita', 'ja-JP-Nanami',
        '（以下为韩语音色）', 'ko-KR-InJoon', 'ko-KR-SunHi',
        '（以下为俄语音色）', 'ru-RU-Dmitry', 'ru-RU-Svetlana',
        '（以下为中文港台音色）',
        'zh-HK-HiuGaai', 'zh-HK-HiuMaan', 'zh-HK-WanLung',
        'zh-TW-HsiaoChen', 'zh-TW-HsiaoYu', 'zh-TW-YunJhe'
    ]
    
    @classmethod
    def get_voices(cls) -> List[str]:
        """获取所有音色列表"""
        return cls.EDGE_VOICES
    
    @classmethod
    def is_valid_voice(cls, voice: str) -> bool:
        """检查音色是否有效"""
        return voice in cls.EDGE_VOICES and "（" not in voice
    
    @classmethod
    def get_voice_categories(cls) -> Dict[str, List[str]]:
        """按分类获取音色"""
        categories = {}
        current_category = "默认"
        #过滤提示
        for voice in cls.EDGE_VOICES:
            if voice.startswith('（') and voice.endswith('）'):
                current_category = voice.strip('（）')
                categories[current_category] = []
            else:
                categories.setdefault(current_category, []).append(voice)
                
        return categories
class CustomConfig:
    """个性化配置常量
        一坨屎山🤣"""
    
    
    # 默认颜色配置
    DEFAULT_COLORS = {
        "background": "#69E0A5",
        "notification_info": "#3498db",
        "notification_warning": "#f0da12",
        "notification_error": "#db3444"
    }
    
    # 默认字体配置
    DEFAULT_FONTS = {
        "global_font": "微软雅黑",
        "min_font_size": "22",
        "max_font_size": "42"
    }
    
    # 默认通知配置
    DEFAULT_NOTIFICATIONS = {
        "animation_appear": "400",
        "animation_disappear": "400", 
        "animation_move": "500",
        "position_m": "12",
        "position_n": "12.25",
        "width_ratio": "1",
        "height_ratio": "0.5",
        "max_visible": "5",
        "offset_n": "1",
        "spacing_n": "1.25",
        "auto_close_time": "3000"
    }
    
    # GitHub下载加速选项
    GITHUB_ACCELERATION_OPTIONS = [
        "直接从github服务器获取（海外首选）",
        "ghfast（国内首选）"
    ]
class AudioConfig:
    """音频配置数据类"""
    
    def __init__(self):
        self._init_default_config()
        
    def _init_default_config(self):
        """初始化默认配置"""
        now = datetime.datetime.now()
        
        # 基础参数
        self.speed = 0  # 语速
        self.pitch = 0  # 音调
        self.volume = 0  # 音量
        
        # 默认内容
        self.content = self._generate_default_content(now)
        
        # 路径和音色
        self.save_path = ""
        self.voice = "（以下为英语音色）"
        
        # 音频拉伸参数
        self.stretch_factor = 1.0
        self.stretch_enabled = False
        
    def _generate_default_content(self, now: datetime.datetime) -> str:
        """生成默认文本内容"""
        return (
            
            "欢迎使用源悦TTS。用户没有输入文本。"
            "源悦TTS 2025年11月13日编译"
        )
    
    def update_timestamp(self):
        """更新时间戳"""
        now = datetime.datetime.now()
        if "用户没有输入文本" in self.content:
            self.content = self._generate_default_content(now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'speed': self.speed,
            'pitch': self.pitch,
            'volume': self.volume,
            'content': self.content,
            'save_path': self.save_path,
            'voice': self.voice,
            'stretch_factor': self.stretch_factor,
            'stretch_enabled': self.stretch_enabled
        }
    
    def from_dict(self, config_dict: Dict[str, Any]):
        """从字典加载配置"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
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
            self.settings_manager._load_config()
            if self.section_name in self.settings_manager.config:
                return self.settings_manager.config[self.section_name].get(key, default)
            return default
        except Exception as e:
            print(f"读取配置失败 [{self.section_name}.{key}]: {e}")
            return default
    
    def set_value(self, key: str, value: str) -> bool:
        """设置字符串配置值"""
        try:
            self.settings_manager._load_config()
            if self.section_name not in self.settings_manager.config:
                self.settings_manager.config[self.section_name] = {}
            self.settings_manager.config[self.section_name][key] = str(value)
            return self.settings_manager._save_config()
        except Exception as e:
            print(f"设置配置失败 [{self.section_name}.{key}]: {e}")
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
class SettingsManager:
    """设置管理器 - 使用ini文件保存配置"""
    
    # 配置常量
    CONFIG_FILE = "settings.ini"
    
    # 段落名称常量
    SECTION_API_KEYS = 'API_Keys'
    SECTION_DEFAULT_VOICES = 'Default_Voices'
    SECTION_DEFAULT_PATHS = 'Default_Paths'
    SECTION_DEFAULT_PARAMETERS = 'Default_Parameters'
    SECTION_PAGE_OFFSETS = 'Page_Offsets'
    SECTION_Custom = 'Custom'  # 新增个性化设置段落
    
    def __init__(self):
        self.config_file = self.CONFIG_FILE
        self.config = configparser.ConfigParser()
        
        # 初始化配置段落管理器
        self._init_config_sections()
        
        # 确保配置文件存在
        self._ensure_config_file()
    
    def _init_config_sections(self):
        """初始化配置段落管理器"""
        self.api_keys = StringConfigSection(self, self.SECTION_API_KEYS)
        self.default_voices = StringConfigSection(self, self.SECTION_DEFAULT_VOICES)
        self.default_paths = StringConfigSection(self, self.SECTION_DEFAULT_PATHS)
        self.default_parameters = StringConfigSection(self, self.SECTION_DEFAULT_PARAMETERS)
        self.page_offsets = StringConfigSection(self, self.SECTION_PAGE_OFFSETS)
        self.Custom = StringConfigSection(self, self.SECTION_Custom)  # 新增
    
    def _ensure_config_file(self):
        """确保配置文件存在"""
        if not os.path.exists(self.config_file):
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        # API Keys 配置
        self.config[self.SECTION_API_KEYS] = {
            'api_key_ChatGLM': '',
            'api_key_Azure': '',
            'api_key_Gemini': '',
            'api_key_4': '',
            'api_key_5': ''
        }
        
        # 默认音色配置
        self.config[self.SECTION_DEFAULT_VOICES] = {
            'default_voice_1': 'abc',
            'default_voice_2': 'abc'
        }
        
        # 默认路径配置
        self.config[self.SECTION_DEFAULT_PATHS] = {
            'default_save_path': ''
        }
        
        # 默认参数配置
        self.config[self.SECTION_DEFAULT_PARAMETERS] = {
            'default_speed': '0',
            'stretch_factor': '1.0',
            'stretch_enabled': 'False'
        }
        
        # 页码偏移量配置
        self.config[self.SECTION_PAGE_OFFSETS] = {}
        
        # 个性化配置（新增）
        self.config[self.SECTION_Custom] = {
            'window_size': '1024x768',
            'background_color': CustomConfig.DEFAULT_COLORS['background'],
            'notification_info_color': CustomConfig.DEFAULT_COLORS['notification_info'],
            'notification_warning_color': CustomConfig.DEFAULT_COLORS['notification_warning'],
            'notification_error_color': CustomConfig.DEFAULT_COLORS['notification_error'],
            'global_font': CustomConfig.DEFAULT_FONTS['global_font'],
            'min_font_size': CustomConfig.DEFAULT_FONTS['min_font_size'],
            'max_font_size': CustomConfig.DEFAULT_FONTS['max_font_size'],
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
            'auto_close_time': CustomConfig.DEFAULT_NOTIFICATIONS['auto_close_time'],
            'github_acceleration': '0'  # 新增GitHub下载加速选项，默认0（直接从GitHub获取）
        }
        
        self._save_config()
    
    def _load_config(self):
        """从文件加载配置"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            print(f"读取配置文件失败: {e}")
    
    def _save_config(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    # API Key 相关方法
    def get_api_key(self, key_name: str) -> str:
        """获取API Key"""
        return self.api_keys.get_value(key_name, '')
    
    def set_api_key(self, key_name: str, value: str) -> bool:
        """设置API Key"""
        return self.api_keys.set_value(key_name, value)
    
    # 默认音色相关方法
    def get_default_voice(self, index: int) -> str:
        """获取默认音色"""
        key = f'default_voice_{index}'
        return self.default_voices.get_value(key, 'abc')
    
    def set_default_voice(self, index: int, value: str) -> bool:
        """设置默认音色"""
        key = f'default_voice_{index}'
        return self.default_voices.set_value(key, value)
    
    # 默认保存路径相关方法
    def get_default_save_path(self) -> str:
        """获取默认保存路径"""
        return self.default_paths.get_value('default_save_path', '')
    
    def set_default_save_path(self, value: str) -> bool:
        """设置默认保存路径"""
        return self.default_paths.set_value('default_save_path', value)
    
    # 默认参数相关方法
    def get_default_speed(self) -> int:
        """获取默认语速"""
        speed_str = self.default_parameters.get_value('default_speed', '0')
        try:
            return int(speed_str) if speed_str else 0
        except (ValueError, TypeError):
            return 0
    
    def set_default_speed(self, value: int) -> bool:
        """设置默认语速"""
        return self.default_parameters.set_value('default_speed', str(value))
    
    def get_stretch_factor(self) -> float:
        """获取音频拉伸倍数"""
        stretch_str = self.default_parameters.get_value('stretch_factor', '1.0')
        try:
            return float(stretch_str) if stretch_str else 1.0
        except (ValueError, TypeError):
            return 1.0
    
    def set_stretch_factor(self, value: float) -> bool:
        """设置音频拉伸倍数"""
        return self.default_parameters.set_value('stretch_factor', str(value))
    
    def get_stretch_enabled(self) -> bool:
        """获取音频拉伸开关状态"""
        enabled_str = self.default_parameters.get_value('stretch_enabled', 'False')
        return enabled_str.lower() == 'true'
    
    def set_stretch_enabled(self, value: bool) -> bool:
        """设置音频拉伸开关状态"""
        return self.default_parameters.set_value('stretch_enabled', str(value))
    
    # 页码偏移量相关方法
    def set_offset_value(self, key: str, value: str) -> bool:
        """设置页码偏移量"""
        return self.page_offsets.set_value(key, value)
    
    def get_offset_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取页码偏移量"""
        return self.page_offsets.get_value(key, default)
    
    # 个性化设置相关方法（新增）
    def get_Custom_value(self, key: str, default: str = "") -> str:
        """获取个性化设置值"""
        return self.Custom.get_value(key, default)
    
    def set_Custom_value(self, key: str, value: str) -> bool:
        """设置个性化设置值"""
        return self.Custom.set_value(key, value)
    
    # GitHub下载加速相关方法（新增）
    def get_github_acceleration(self) -> int:
        """获取GitHub下载加速选项"""
        try:
            acceleration_str = self.Custom.get_value('github_acceleration', '0')
            return int(acceleration_str) if acceleration_str else 0
        except (ValueError, TypeError):
            return 0
    
    def set_github_acceleration(self, value: int) -> bool:
        """设置GitHub下载加速选项"""
        return self.Custom.set_value('github_acceleration', str(value))
    
    # 工具方法
    def get_all_settings(self) -> Dict[str, Dict[str, str]]:
        """获取所有设置"""
        self._load_config()
        settings = {}
        for section in self.config.sections():
            settings[section] = dict(self.config[section])
        return settings
    
    def reset_to_defaults(self) -> bool:
        """重置为默认设置"""
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            self._create_default_config()
            return True
        except Exception as e:
            print(f"重置设置失败: {e}")
            return False
class ContentHasher:
    """内容哈希计算器"""
    
    @staticmethod
    def get_content_hash(config: AudioConfig) -> str:
        """获取配置内容的哈希值"""
        content = f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    @staticmethod
    def get_cache_key(config: AudioConfig) -> str:
        """生成缓存键"""
        return f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
    
    @staticmethod
    def calculate_hash(*args) -> str:
        """计算任意参数的哈希值"""
        content = "_".join(str(arg) for arg in args)
        return hashlib.md5(content.encode('utf-8')).hexdigest()
class AudioFileManager:
    """音频文件管理器"""
    
    @staticmethod
    def generate_filename(prefix: str = "EdgeTTS", extension: str = ".mp3") -> str:
        """生成音频文件名"""
        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%H-%M-%S')
        return f"{prefix}{timestamp}{extension}"
    
    @staticmethod
    def get_default_save_path(config: AudioConfig, settings_manager: SettingsManager) -> Optional[str]:
        """获取默认保存路径"""
        default_save_path = settings_manager.get_default_save_path()
        if not default_save_path:
            return None
            
        filename = AudioFileManager.generate_filename()
        return os.path.join(default_save_path, filename)
    
    @staticmethod
    def ensure_directory_exists(file_path: str) -> bool:
        """确保文件所在目录存在"""
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            return True
        except Exception as e:
            print(f"创建目录失败: {e}")
            return False
    
    @staticmethod
    def is_valid_audio_file(file_path: str) -> bool:
        """检查是否为有效的音频文件"""
        valid_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
        _, ext = os.path.splitext(file_path)
        return ext.lower() in valid_extensions and os.path.exists(file_path)
    
    @staticmethod
    def cleanup_old_files(directory: str, pattern: str, max_files: int = 50) -> int:
        """清理旧文件"""
        try:
            import glob
            files = glob.glob(os.path.join(directory, pattern))
            files.sort(key=os.path.getmtime)
            
            deleted_count = 0
            while len(files) > max_files:
                old_file = files.pop(0)
                try:
                    os.remove(old_file)
                    deleted_count += 1
                except OSError:
                    pass
                    
            return deleted_count
        except Exception as e:
            print(f"清理文件失败: {e}")
            return 0
class InputValidator:
    """输入验证器"""
    
    @staticmethod
    def validate_preview_inputs(config: AudioConfig) -> Tuple[bool, str]:  # 改为Tuple
        """验证预览输入参数"""
        if not VoiceConfig.is_valid_voice(config.voice):
            return False, "音色选择错误"
        return True, ""
    
    @staticmethod
    def validate_generation_inputs(config: AudioConfig, settings_manager: SettingsManager) -> Tuple[bool, str]:  # 改为Tuple
        """验证生成输入参数"""
        empty_fields = []
        
        # 检查默认保存路径是否设置
        default_save_path = settings_manager.get_default_save_path()
        if not default_save_path:
            empty_fields.append("默认保存路径")
            
        if config.voice == "选项1" or not VoiceConfig.is_valid_voice(config.voice):
            empty_fields.append("语音选项")
        if empty_fields:
            return False, "请配置以下内容: " + ", ".join(empty_fields)
        
        if "（" in config.voice:
            return False, f"音色选择错误"
            
        return True, ""
    
    @staticmethod
    def check_inputs_for_button(config: AudioConfig, settings_manager: SettingsManager) -> Tuple[bool, list]:  # 改为Tuple
        """检查输入以更新按钮状态"""
        empty_fields = []
        # 检查默认保存路径是否设置
        default_save_path = settings_manager.get_default_save_path()
        if not default_save_path:
            empty_fields.append("默认保存路径")
            
        if config.voice == "选项1" or not VoiceConfig.is_valid_voice(config.voice):
            empty_fields.append("语音选项")
        return bool(empty_fields), empty_fields
    
    @staticmethod
    def validate_file_path(file_path: str) -> Tuple[bool, str]:  # 改为Tuple
        """验证文件路径"""
        if not file_path:
            return False, "文件路径不能为空"
        
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            return False, f"目录不存在: {directory}"
            
        return True, ""
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:  # 改为Tuple
        """验证API Key格式"""
        if not api_key:
            return False, "API Key不能为空"
        
        if len(api_key) < 10:
            return False, "API Key格式不正确"
            
        return True, ""
# 向后兼容的全局变量
EdgeVoices = VoiceConfig.EDGE_VOICES
