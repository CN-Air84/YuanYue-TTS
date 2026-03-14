# coding=utf-8
import os
import hashlib
import datetime
from typing import Optional, Dict, Any, List, Tuple  # 新增Tuple导入
import configparser
import sys # 导入sys模块
from debug_logger import debug_logger, LogLevel

'''
本段代码在SimeonTest Re1时使用 DeepSeek 重构
This code uses DeepSeek refactoring at Simeontest RE1
'''

def get_app_base_path():
    """
    获取应用程序的根目录。
    在PyInstaller打包后，此函数将返回exe文件所在的目录。
    在开发环境中，此函数将返回脚本文件所在的目录。
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的路径
        return os.path.dirname(sys.executable)
    else:
        # 开发环境中的路径
        return os.path.dirname(os.path.abspath(__file__))

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
        if not voice:
            return False
            
        # 预处理：去除首尾空格
        voice = voice.strip()
        
        # 1. 检查是否在硬编码列表中（排除分类标题）
        if voice in cls.EDGE_VOICES and not (voice.startswith("（") or voice.endswith("）")):
            return True
            
        # 2. 检查是否为带 "Neural" 后缀的有效格式
        if voice.endswith("Neural"):
            base_voice = voice[:-6]  # 移除 "Neural"
            return base_voice in cls.EDGE_VOICES and not (base_voice.startswith("（") or base_voice.endswith("）"))
            
        return False
    
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
    """个性化配置常量"""
    
    
    # 默认颜色配置
    DEFAULT_COLORS = {
        "background": "#E5E8EF",
        "card_background": "#F5F8FF",
        "component_background": "#FFFFFF",
        "highlight_button": "#4682D6",
        "notification_info": "#D4E1FF",
        "notification_warning": "#FFE8D4",
        "notification_error": "#FFD4D4",
        "text_color": "#000000"
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
    
    # 默认指示器配置
    DEFAULT_INDICATOR = {
        "indicator_animation_speed": "0.03",
        "indicator_x_offset": "0",
        "indicator_y_offset": "0",
        "indicator_width_adjust": "0",
        "indicator_height_adjust": "0"
    }
    
    # GitHub下载加速选项
    GITHUB_ACCELERATION_OPTIONS = [
        "直接从github服务器获取（海外首选）",
        "ghfast（中国大陆首选）",
        "ghproxy 主站（CloudFlare CDN，大陆备用）",
        "ghproxy HK（港澳台首选）",
        "ghproxy edgeone（备用）"
    ]
    
    # 精简的窗口尺寸预设 - 只保留常用尺寸
    WINDOW_SIZES = [
        "1024x720",    # 默认
        "1024x768",    # 标准
        "1280x720",    # HD
        "1280x800",    # 宽屏
        "1366x768",    # 笔记本常见
        "1440x900",    # 19寸宽屏
        "1600x900",    # 20寸宽屏
        "1920x1080",   # Full HD
        "1920x1200"    # WUXGA
    ]
    
    @classmethod
    def get_window_sizes(cls) -> List[str]:
        """获取窗口尺寸列表"""
        return cls.WINDOW_SIZES
    
    @classmethod
    def validate_window_size(cls, size: str) -> bool:
        """验证窗口尺寸是否有效"""
        return size in cls.WINDOW_SIZES
    
    # 主题预设配置
    THEME_PRESETS = {
        "晶瓷白": {
            "background": "#DFDFDF",
            "card_background": "#FFFFFF",
            "component_background": "#F5F5F5",
            "highlight_button": "#4682B4",
            "notification_info": "#C8D4DF",
            "notification_warning": "#DFD8C6",
            "notification_error": "#DFCCC8",
            "text_color": "#000000"
        },
        "水墨黑": {
            "background": "#363636",
            "card_background": "#4A4A4A",
            "component_background": "#3D3D3D",
            "highlight_button": "#5CAEFF",
            "notification_info": "#1E3A5F",
            "notification_warning": "#4A3520",
            "notification_error": "#4B2420",
            "text_color": "#E0E0E0"
        },
        "爱眼绿": {
            "background": "#C5C9C5",
            "card_background": "#E8EFE8",
            "component_background": "#DDE8DD",
            "highlight_button": "#46A4B4",
            "notification_info": "#D4E7D4",
            "notification_warning": "#F2E8D9",
            "notification_error": "#F2D9D9",
            "text_color": "#000000"
        },
        "绮彩红": {
            "background": "#CFC9C9",
            "card_background": "#F9F4F4",
            "component_background": "#FFF0F0",
            "highlight_button": "#FF6B6B",
            "notification_info": "#FFE0E6",
            "notification_warning": "#FFE8CC",
            "notification_error": "#FFCCCC",
            "text_color": "#000000"
        },
        "仁物蓝": {
            "background": "#E5E8EF",
            "card_background": "#F5F8FF",
            "component_background": "#FFFFFF",
            "highlight_button": "#4682D6",
            "notification_info": "#D4E1FF",
            "notification_warning": "#FFE8D4",
            "notification_error": "#FFD4D4",
            "text_color": "#000000"
        }
    }
    
    @classmethod
    def get_theme_presets(cls) -> Dict[str, Dict[str, str]]:
        """获取主题预设"""
        return cls.THEME_PRESETS
    
    @classmethod
    def get_theme_names(cls) -> List[str]:
        """获取主题名称列表"""
        return list(cls.THEME_PRESETS.keys())
    
    @classmethod
    def get_theme_colors(cls, theme_name: str) -> Dict[str, str]:
        """获取指定主题的颜色配置"""
        return cls.THEME_PRESETS.get(theme_name, cls.DEFAULT_COLORS)
    
    @classmethod
    def should_use_white_text(cls, background_color: str) -> bool:
        """判断背景颜色是否需要白色文字
        
        Args:
            background_color: 背景颜色（HEX格式，如#121212）
            
        Returns:
            True: 需要使用白色文字
            False: 使用默认黑色文字
        """
        # 移除#号并转换为RGB
        hex_color = background_color.lstrip('#')
        if len(hex_color) != 6:
            return False
            
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # 如果RGB三项均小于96，使用白色文字
            return r < 96 and g < 96 and b < 96
        except (ValueError, IndexError):
            return False
class AudioConfig:
    """音频配置数据类"""
    
    def __init__(self):
        self._init_default_config()
        
    def _init_default_config(self):
        """初始化默认配置"""
        debug_logger.output("misc_func.py", LogLevel.INFO, "初始化 AudioConfig 默认配置", fold_code="AC_INIT")
        now = datetime.datetime.now()

        try:
            settings_manager = SettingsManager()
            self.speed = settings_manager.get_default_speed()
            debug_logger.output("misc_func.py", LogLevel.DEBUG, f"加载默认语速: {self.speed}", fold_code="AC_INIT")
        except Exception as e:
            self.speed = 0
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"从设置加载默认语速失败: {str(e)}，已回退至0", fold_code="AC_INIT")
            
        self.pitch = 0
        self.volume = 0

        self.content = self._generate_default_content(now)
        self.save_path = ""
        self.voice = "（以下为英语音色）"
        self.stretch_factor = 1.0
        self.stretch_enabled = False
        debug_logger.output("misc_func.py", LogLevel.DEBUG, "AudioConfig 默认状态初始化完毕", fold_code="AC_INIT")
        
    def _generate_default_content(self, now: datetime.datetime) -> str:
        """生成默认文本内容"""
        debug_logger.output("misc_func.py", LogLevel.INFO, "生成默认文本内容", fold_code="AC_CONTENT")
        return ''
    
    def update_timestamp(self):
        """更新时间戳"""
        now = datetime.datetime.now()
        if "用户没有输入文本" in '123':
            debug_logger.output("misc_func.py", LogLevel.INFO, "用户未输入文本，更新时间戳内容", fold_code="AC_TIMESTAMP")
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
        debug_logger.output("misc_func.py", LogLevel.INFO, f"从字典加载配置: {len(config_dict)} 个项", fold_code="AC_LOAD")
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
                val = self.settings_manager.config[self.section_name].get(key, default)
                #debug_logger.output("misc_func.py", LogLevel.DEBUG, f"获取配置值: [{self.section_name}] {key} = {val}", fold_code="CFG_GET")
                return val
            return default
        except Exception as e:
            # 静默处理配置读取错误，返回默认值
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"获取字符串配置失败 [{self.section_name}] {key}: {e}", fold_code="CFG_ERR")
            return default
    
    def set_value(self, key: str, value: str) -> bool:
        """设置字符串配置值"""
        try:
            self.settings_manager._load_config()
            if self.section_name not in self.settings_manager.config:
                self.settings_manager.config[self.section_name] = {}
            self.settings_manager.config[self.section_name][key] = str(value)
            debug_logger.output("misc_func.py", LogLevel.INFO, f"Set string config: [{self.section_name}] {key}={value}", fold_code="CFG_SET")
            return self.settings_manager._save_config()
        except Exception as e:
            # 静默处理配置设置错误
            debug_logger.output("misc_func.py", LogLevel.ERROR, f"设置字符串配置失败 [{self.section_name}] {key}: {e}", fold_code="CFG_ERR")
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
    """设置管理器 - 使用ini文件保存配置 (单例模式)"""
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    
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
        if not hasattr(self, '_initialized'): # Ensure __init__ runs only once for singleton
            self.config_file = os.path.join(get_app_base_path(), self.CONFIG_FILE)
            self.config = configparser.ConfigParser()
            
            # 初始化配置段落管理器
            self._init_config_sections()
            
            # 确保配置文件存在
            self._ensure_config_file()
            self._initialized = True
    
    def _init_config_sections(self):
        """初始化配置段落管理器"""
        debug_logger.output("misc_func.py", LogLevel.INFO, "初始化配置段落管理器", fold_code="MF_INIT")
        self.api_keys = StringConfigSection(self, self.SECTION_API_KEYS)
        self.default_voices = StringConfigSection(self, self.SECTION_DEFAULT_VOICES)
        self.default_paths = StringConfigSection(self, self.SECTION_DEFAULT_PATHS)
        self.default_parameters = StringConfigSection(self, self.SECTION_DEFAULT_PARAMETERS)
        self.page_offsets = StringConfigSection(self, self.SECTION_PAGE_OFFSETS)
        self.Custom = StringConfigSection(self, self.SECTION_Custom)  # 新增
    
    def _ensure_config_file(self):
        """确保配置文件存在"""
        if not os.path.exists(self.config_file):
            debug_logger.output("misc_func.py", LogLevel.WARNING, "配置文件不存在，创建默认配置", fold_code="CFG_INIT")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        debug_logger.output("misc_func.py", LogLevel.INFO, "正在创建默认配置文件...", fold_code="CFG_CREATE")
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
            'github_acceleration': '0',  # 新增GitHub下载加速选项，默认0（直接从GitHub获取）
            'online_import_mode': 'False',  # 新增在线导入模式，默认False（GitHub导入模式）
            'current_theme': '仁物蓝',
            'highlight_button_color': CustomConfig.DEFAULT_COLORS['highlight_button'],
            'card_background_color': CustomConfig.DEFAULT_COLORS['card_background'],
            'component_background_color': CustomConfig.DEFAULT_COLORS['component_background'],
            'text_color': CustomConfig.DEFAULT_COLORS['text_color'],
            'tab_order': 'welcome,dictation,settings,personalization,misc',
            'tab_visibility': 'welcome,dictation,settings,personalization,misc',
            'initial_tab': 'welcome',
            # 默认热键设置 (Qt.Key 枚举值)
            'hk_toggle_pause': '32',      # Space
            'hk_seek_backward': '65',     # A
            'hk_seek_forward': '68',      # D
            'hk_volume_up': '87',         # W
            'hk_volume_down': '83',       # S
            'hk_next_sentence': '16777236',  # Right
            'hk_prev_sentence': '16777234',   # Left
            'is_first_run': 'True'
        }
        
        self._save_config()
    
    def _load_config(self):
        """从文件加载配置"""
        try:
            #debug_logger.output("misc_func.py", LogLevel.DEBUG, f"正在从文件加载配置: {self.config_file}", fold_code="CFG_LOAD")
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            debug_logger.output("misc_func.py", LogLevel.ERROR, f"读取配置文件失败: {e}", fold_code="CFG_ERR")
    
    def _save_config(self) -> bool:
        """保存配置到文件"""
        try:
            debug_logger.output("misc_func.py", LogLevel.INFO, f"正在保存配置到文件: {self.config_file}", fold_code="CFG_SAVE")
            with open(self.config_file, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            return True
        except Exception as e:
            debug_logger.output("misc_func.py", LogLevel.ERROR, f"保存配置文件失败: {e}", fold_code="CFG_ERR")
            return False
    
    # API Key 相关方法
    def get_api_key(self, key_name: str) -> str:
        """获取API Key"""
        val = self.api_keys.get_value(key_name, '')
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取 API Key: {key_name}", fold_code="CFG_API")
        return val
    
    def set_api_key(self, key_name: str, value: str) -> bool:
        """设置API Key"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置 API Key: {key_name}", fold_code="CFG_API")
        return self.api_keys.set_value(key_name, value)
    
    # 默认音色相关方法
    def get_default_voice(self, index: int) -> str:
        """获取默认音色"""
        key = f'default_voice_{index}'
        val = self.default_voices.get_value(key, 'abc')
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取默认音色 {index}: {val}", fold_code="CFG_VOICE")
        return val
    
    def set_default_voice(self, index: int, value: str) -> bool:
        """设置默认音色"""
        key = f'default_voice_{index}'
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置默认音色 {index}: {value}", fold_code="CFG_VOICE")
        return self.default_voices.set_value(key, value)
    
    # 默认保存路径相关方法
    def get_default_save_path(self) -> str:
        """获取默认保存路径"""
        val = self.default_paths.get_value('default_save_path', '')
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取默认保存路径: {val}", fold_code="CFG_PATH")
        return val
    
    def set_default_save_path(self, value: str) -> bool:
        """设置默认保存路径"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置默认保存路径: {value}", fold_code="CFG_PATH")
        return self.default_paths.set_value('default_save_path', value)
    
    # 默认参数相关方法
    def get_default_speed(self) -> int:
        """获取默认语速"""
        speed_str = self.default_parameters.get_value('default_speed', '0')
        try:
            speed = int(speed_str) if speed_str else 0
            debug_logger.output("misc_func.py", LogLevel.INFO, f"获取默认语速: {speed}", fold_code="CFG_PARAM")
            return speed
        except (ValueError, TypeError):
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"默认语速解析失败: {speed_str}", fold_code="CFG_ERR")
            return 0
    
    def set_default_speed(self, value: int) -> bool:
        """设置默认语速"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置默认语速: {value}", fold_code="CFG_PARAM")
        return self.default_parameters.set_value('default_speed', str(value))
    
    # 首次运行相关方法
    def get_is_first_run(self) -> bool:
        """获取是否首次运行"""
        val = self.Custom.get_value('is_first_run', 'True')
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取是否首次运行: {val}", fold_code="CFG_FIRSTRUN")
        return val.lower() == 'true'

    def set_is_first_run(self, value: bool) -> bool:
        """设置是否首次运行"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置是否首次运行: {value}", fold_code="CFG_FIRSTRUN")
        return self.Custom.set_value('is_first_run', str(value))

    def get_stretch_factor(self) -> float:
        """获取音频拉伸倍数"""
        stretch_str = self.default_parameters.get_value('stretch_factor', '1.0')
        try:
            factor = float(stretch_str) if stretch_str else 1.0
            debug_logger.output("misc_func.py", LogLevel.INFO, f"获取拉伸倍数: {factor}", fold_code="CFG_PARAM")
            return factor
        except (ValueError, TypeError):
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"拉伸倍数解析失败: {stretch_str}", fold_code="CFG_ERR")
            return 1.0
    
    def set_stretch_factor(self, value: float) -> bool:
        """设置音频拉伸倍数"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置拉伸倍数: {value}", fold_code="CFG_PARAM")
        return self.default_parameters.set_value('stretch_factor', str(value))
    
    def get_stretch_enabled(self) -> bool:
        """获取音频拉伸开关状态"""
        enabled_str = self.default_parameters.get_value('stretch_enabled', 'False')
        enabled = enabled_str.lower() == 'true'
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取拉伸启用状态: {enabled}", fold_code="CFG_PARAM")
        return enabled
    
    def set_stretch_enabled(self, value: bool) -> bool:
        """设置音频拉伸开关状态"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置拉伸启用状态: {value}", fold_code="CFG_PARAM")
        return self.default_parameters.set_value('stretch_enabled', str(value))
    
    # 页码偏移量相关方法
    def set_offset_value(self, key: str, value: str) -> bool:
        """设置页码偏移量"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置页码偏移量: {key}={value}", fold_code="CFG_OFFSET")
        return self.page_offsets.set_value(key, value)
    
    def get_offset_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取页码偏移量"""
        val = self.page_offsets.get_value(key, default)
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取页码偏移量: {key}={val}", fold_code="CFG_OFFSET")
        return val
    
    # 个性化设置相关方法（新增）
    def get_Custom_value(self, key: str, default: str = "") -> str:
        """获取个性化设置值"""
        val = self.Custom.get_value(key, default)
        # debug_logger.output("misc_func.py", LogLevel.INFO, f"获取个性化设置: {key}={val}", fold_code="CFG_CUSTOM")
        return val
    
    def set_Custom_value(self, key: str, value: str) -> bool:
        """设置个性化设置值"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置个性化设置: {key}={value}", fold_code="CFG_CUSTOM")
        return self.Custom.set_value(key, value)
    
    # GitHub下载加速相关方法（新增）
    def get_github_acceleration(self) -> int:
        """获取GitHub下载加速选项"""
        try:
            acceleration_str = self.Custom.get_value('github_acceleration', '0')
            acceleration = int(acceleration_str) if acceleration_str else 0
            debug_logger.output("misc_func.py", LogLevel.INFO, f"获取GitHub加速选项: {acceleration}", fold_code="CFG_NET")
            return acceleration
        except (ValueError, TypeError):
            debug_logger.output("misc_func.py", LogLevel.WARNING, "GitHub加速选项解析失败", fold_code="CFG_ERR")
            return 0
    
    def set_github_acceleration(self, value: int) -> bool:
        """设置GitHub下载加速选项"""
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置GitHub加速选项: {value}", fold_code="CFG_NET")
        return self.Custom.set_value('github_acceleration', str(value))
    
    # 下载线程数相关方法（新增）
    def get_download_thread_num(self) -> int:
        """获取下载线程数"""
        try:
            thread_num_str = self.Custom.get_value('download_thread_num', '5')
            thread_num = int(thread_num_str) if thread_num_str else 5
            # 确保线程数在合理范围内
            final_num = max(1, min(32, thread_num))
            debug_logger.output("misc_func.py", LogLevel.INFO, f"获取下载线程数: {final_num}", fold_code="CFG_NET")
            return final_num
        except (ValueError, TypeError):
            debug_logger.output("misc_func.py", LogLevel.WARNING, "下载线程数解析失败", fold_code="CFG_ERR")
            return 5
    
    def set_download_thread_num(self, value: int) -> bool:
        """设置下载线程数"""
        try:
            # 验证输入值
            thread_num = int(value)
            if not 0 < thread_num <= 32:
                debug_logger.output("misc_func.py", LogLevel.WARNING, f"设置无效的下载线程数: {thread_num}", fold_code="CFG_NET")
                return False
            debug_logger.output("misc_func.py", LogLevel.INFO, f"设置下载线程数: {thread_num}", fold_code="CFG_NET")
            return self.Custom.set_value('download_thread_num', str(thread_num))
        except (ValueError, TypeError):
            return False
    
    # 在线导入模式相关方法（新增）
    def get_online_import_mode(self) -> bool:
        """获取在线导入模式
        
        Returns:
            True: 智慧教育平台导入模式（新）
            False: GitHub导入模式（旧）
        """
        try:
            mode_str = self.Custom.get_value('online_import_mode', 'False')
            mode = mode_str.lower() == 'true'
            debug_logger.output("misc_func.py", LogLevel.INFO, f"获取在线导入模式: {mode}", fold_code="CFG_NET")
            return mode
        except Exception:
            return False
    
    def set_online_import_mode(self, value: bool) -> bool:
        """设置在线导入模式
        
        Args:
            value: True为智慧教育平台导入模式，False为GitHub导入模式
            
        Returns:
            bool: 设置是否成功
        """
        debug_logger.output("misc_func.py", LogLevel.INFO, f"设置在线导入模式: {value}", fold_code="CFG_NET")
        return self.Custom.set_value('online_import_mode', str(value))
    
    # 工具方法
    def get_all_settings(self) -> Dict[str, Dict[str, str]]:
        """获取所有设置"""
        debug_logger.output("misc_func.py", LogLevel.INFO, "获取所有配置项", fold_code="CFG_ALL")
        self._load_config()
        settings = {}
        for section in self.config.sections():
            settings[section] = dict(self.config[section])
        return settings
    
    def reset_to_defaults(self) -> bool:
        """重置为默认设置"""
        try:
            debug_logger.output("misc_func.py", LogLevel.WARNING, "正在重置所有配置为默认值", fold_code="CFG_RESET")
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            self._create_default_config()
            return True
        except Exception as e:
            debug_logger.output("misc_func.py", LogLevel.ERROR, f"重置设置失败: {e}", fold_code="CFG_ERR")
            return False
class ContentHasher:
    """内容哈希计算器"""
    
    @staticmethod
    def get_content_hash(config: AudioConfig) -> str:
        """获取配置内容的哈希值"""
        content = f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
        h = hashlib.md5(content.encode('utf-8')).hexdigest()
        debug_logger.output("misc_func.py", LogLevel.INFO, f"计算内容哈希: {h[:8]}...", fold_code="HASH_CALC")
        return h
    
    @staticmethod
    def get_cache_key(config: AudioConfig) -> str:
        """生成缓存键"""
        return f"{config.content}_{config.voice}_{config.speed}_{config.pitch}_{config.volume}_{config.stretch_factor}"
    
    @staticmethod
    def calculate_hash(*args) -> str:
        """计算任意参数的哈希值"""
        content = "_".join(str(arg) for arg in args)
        h = hashlib.md5(content.encode('utf-8')).hexdigest()
        debug_logger.output("misc_func.py", LogLevel.INFO, f"计算任意参数哈希: {h[:8]}...", fold_code="HASH_CALC")
        return h
class AudioFileManager:
    """音频文件管理器"""
    
    @staticmethod
    def generate_filename(prefix: str = "EdgeTTS", extension: str = ".mp3") -> str:
        """生成音频文件名"""
        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%H-%M-%S')
        filename = f"{prefix}{timestamp}{extension}"
        debug_logger.output("misc_func.py", LogLevel.INFO, f"生成音频文件名: {filename}", fold_code="FILE_GEN")
        return filename
    
    @staticmethod
    def get_default_save_path(config: AudioConfig, settings_manager: SettingsManager) -> Optional[str]:
        """获取默认保存路径"""
        default_save_path = settings_manager.get_default_save_path()
        if not default_save_path:
            debug_logger.output("misc_func.py", LogLevel.WARNING, "未设置默认保存路径", fold_code="FILE_PATH")
            return None
            
        filename = AudioFileManager.generate_filename()
        full_path = os.path.join(default_save_path, filename)
        debug_logger.output("misc_func.py", LogLevel.INFO, f"获取完整保存路径: {full_path}", fold_code="FILE_PATH")
        return full_path
    
    @staticmethod
    def ensure_directory_exists(file_path: str) -> bool:
        """确保文件所在目录存在"""
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                debug_logger.output("misc_func.py", LogLevel.INFO, f"创建目录: {directory}", fold_code="FILE_DIR")
                os.makedirs(directory)
            return True
        except Exception as e:
            debug_logger.output("misc_func.py", LogLevel.ERROR, f"创建目录失败: {e}", fold_code="FILE_ERR")
            return False
    
    @staticmethod
    def is_valid_audio_file(file_path: str) -> bool:
        """检查是否为有效的音频文件"""
        valid_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
        _, ext = os.path.splitext(file_path)
        exists = os.path.exists(file_path)
        is_valid = ext.lower() in valid_extensions and exists
        if not is_valid and exists:
             debug_logger.output("misc_func.py", LogLevel.WARNING, f"无效的音频文件扩展名: {ext}", fold_code="FILE_VAL")
        return is_valid
    
    @staticmethod
    def cleanup_old_files(directory: str, pattern: str, max_files: int = 50) -> int:
        """清理旧文件"""
        try:
            import glob
            debug_logger.output("misc_func.py", LogLevel.INFO, f"开始清理旧文件: {directory}/{pattern}, 最大保留: {max_files}", fold_code="FILE_CLEAN")
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
            
            if deleted_count > 0:
                debug_logger.output("misc_func.py", LogLevel.INFO, f"已清理 {deleted_count} 个旧文件", fold_code="FILE_CLEAN")
            return deleted_count
        except Exception as e:
            debug_logger.output("misc_func.py", LogLevel.ERROR, f"清理文件失败: {e}", fold_code="FILE_ERR")
            return 0
class InputValidator:
    """输入验证器"""
    
    @staticmethod
    def validate_preview_inputs(config: AudioConfig) -> Tuple[bool, str]:  # 改为Tuple
        """验证预览输入参数"""
        if not VoiceConfig.is_valid_voice(config.voice):
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"预览验证失败: 音色选择错误 ({config.voice})", fold_code="VAL_PREVIEW")
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
            msg = "请配置以下内容: " + ", ".join(empty_fields)
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"生成验证失败: {msg}", fold_code="VAL_GEN")
            return False, msg
        
        if "（" in config.voice:
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"生成验证失败: 音色选择错误 ({config.voice})", fold_code="VAL_GEN")
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
            debug_logger.output("misc_func.py", LogLevel.WARNING, "路径验证失败: 路径为空", fold_code="VAL_PATH")
            return False, "文件路径不能为空"
        
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            debug_logger.output("misc_func.py", LogLevel.WARNING, f"路径验证失败: 目录不存在 ({directory})", fold_code="VAL_PATH")
            return False, f"目录不存在: {directory}"
            
        return True, ""
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:  # 改为Tuple
        """验证API Key格式"""
        if not api_key:
            debug_logger.output("misc_func.py", LogLevel.WARNING, "API Key验证失败: 为空", fold_code="VAL_API")
            return False, "API Key不能为空"
        
        if len(api_key) < 10:
            debug_logger.output("misc_func.py", LogLevel.WARNING, "API Key验证失败: 长度不足", fold_code="VAL_API")
            return False, "API Key格式不正确"
            
        return True, ""
# 向后兼容的全局变量
EdgeVoices = VoiceConfig.EDGE_VOICES
