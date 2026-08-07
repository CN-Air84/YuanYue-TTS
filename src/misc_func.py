# coding=utf-8
import os
import hashlib
import datetime
from typing import Optional, Dict, Any, List, Tuple  # 新增Tuple导入
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
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
class SettingsManager:
    """向后兼容的包装器 - 转发到独立的 settings_manager 模块"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            from settings_manager import SettingsManager as _RealSettingsManager
            cls._instance._impl = _RealSettingsManager()
        return cls._instance

    def __getattr__(self, name):
        return getattr(self._impl, name)

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
