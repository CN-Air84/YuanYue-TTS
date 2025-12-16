import re
import os
import platform
import traceback
import subprocess
import tempfile
import shutil
from typing import Callable, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GenerationConfig:
    """音频生成配置"""
    content: str
    voice: str
    speed: int
    pitch: int
    volume: int
    save_path: str
    stretch_factor: float = 1.0
    stretch_enabled: bool = False


class AudioParameterFormatter:
    """音频参数格式化工具"""
    
    @staticmethod
    def format_parameter(value: int, unit: str) -> str:
        """格式化参数值"""
        formatted = f"{value}{unit}"
        if value >= 0:
            formatted = "+" + formatted
        return formatted
    
    @staticmethod
    def format_speed(speed: int) -> str:
        """格式化语速参数"""
        return AudioParameterFormatter.format_parameter(speed, "%")
    
    @staticmethod
    def format_pitch(pitch: int) -> str:
        """格式化音调参数"""
        return AudioParameterFormatter.format_parameter(pitch, "Hz")
    
    @staticmethod
    def format_volume(volume: int) -> str:
        """格式化音量参数"""
        return AudioParameterFormatter.format_parameter(volume, "%")
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """预处理文本"""
        return re.sub(r'\n', '，', text)


class FilePathManager:
    """文件路径管理工具"""
    
    @staticmethod
    def ensure_save_directory_exists(save_path: str) -> bool:
        """确保保存目录存在"""
        save_dir = os.path.dirname(save_path)
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
                return True
            except Exception as e:
                raise
        return True
    
    @staticmethod
    def create_temp_file(suffix: str = '.mp3') -> str:
        """创建临时文件"""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            return temp_file.name
    
    @staticmethod
    def generate_preview_filename() -> str:
        """生成预览文件名"""
        import datetime
        now = datetime.datetime.now()
        return f"tmp_{now.strftime('%m%d%H%M%S')}.mp3"


class AudioStretcher:
    """音频拉伸处理工具"""
    
    @staticmethod
    def apply_audio_stretch(input_path: str, stretch_factor: float) -> str:
        """应用音频拉伸（变速不变调）- 使用FFmpeg"""
        try:
            # 创建输出文件路径
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_stretched{ext}"
            
            # 构建FFmpeg命令
            cmd = AudioStretcher._build_ffmpeg_command(input_path, output_path, stretch_factor)
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return input_path
            
            return output_path
            
        except Exception as e:
            # 如果拉伸失败，返回原文件
            return input_path
    
    @staticmethod
    def _build_ffmpeg_command(input_path: str, output_path: str, stretch_factor: float) -> list:
        """构建FFmpeg命令"""
        if 0.5 <= stretch_factor <= 2.0:
            return ['ffmpeg', '-i', input_path,'-filter:a', f'atempo={stretch_factor}','-y',output_path]
        else:      
            factors = AudioStretcher._calculate_tempo_factors(stretch_factor)
            filter_chain = ''.join([f'atempo={f},' for f in factors])[:-1] 
            return ['ffmpeg', '-i', input_path,'-filter:a', filter_chain,'-y',output_path]
    
    @staticmethod
    def _calculate_tempo_factors(stretch_factor: float) -> list:
        """计算tempo因子"""
        factors = []
        remaining = stretch_factor
        
        while remaining < 0.5:
            factors.append(0.5)
            remaining /= 0.5
        
        while remaining > 2.0:
            factors.append(2.0)
            remaining /= 2.0
        
        factors.append(remaining)
        return factors


class InputValidator:
    """输入验证工具"""
    
    @staticmethod
    def validate_inputs(config: GenerationConfig) -> Tuple[bool, str]:
        """验证输入参数"""
        empty_fields = []
        
        if not config.save_path.strip():
            empty_fields.append("保存路径")
        if config.voice == "选项1":
            empty_fields.append("语音选项")

        if empty_fields:
            return False, "没有指定路径"
        
        if "（" in config.voice:
            return False, "音色选择错误"
            
        return True, ""
    
    @staticmethod
    def validate_preview_inputs(config: GenerationConfig) -> Tuple[bool, str]:
        """验证预览输入参数"""
        if "（" in config.voice:
            return False, "音色选择错误"
        
        if not config.content.strip():
            return False, "没有输入文本"
            
        return True, ""


class EdgeTTSGenerator:
    """Edge-TTS音频生成工具"""
    
    def __init__(self):
        self.parameter_formatter = AudioParameterFormatter()
    
    def generate_audio(self, config: GenerationConfig, temp_path: str) -> bool:
        """生成音频文件"""
        try:
            # 延迟导入Edge-TTS模块
            import edge_tts
            
            #预处理文本和参数
            text = self.parameter_formatter.preprocess_text(config.content)
            rate = self.parameter_formatter.format_speed(config.speed)
            pitch = self.parameter_formatter.format_pitch(config.pitch)
            volume = self.parameter_formatter.format_volume(config.volume)
            
            voice_id = config.voice
            voice_with_neural = voice_id + "Neural"
            
            # 尝试使用不同的语音ID格式以增强兼容性
            voice_formats = [
                voice_with_neural,  # 原始格式: ID + Neural
                voice_id,           # 不带Neural后缀
                voice_id.replace('-', '_') + "Neural",  # 使用下划线替代连字符
                voice_id.replace('-', '') + "Neural"   # 移除所有连字符
            ]
            
            # 去重处理
            voice_formats = list(dict.fromkeys(voice_formats))
            
            # 尝试不同的语音ID格式
            for i, voice_format in enumerate(voice_formats):
                try:
                    #生成音频
                    communicate = edge_tts.Communicate(
                        text=text, 
                        voice=voice_format, 
                        rate=rate, 
                        pitch=pitch, 
                        volume=volume
                    )
                    
                    communicate.save_sync(temp_path)
                    return True
                except Exception as inner_e:
                    # 如果是最后一次尝试仍然失败，则抛出原始异常
                    if i == len(voice_formats) - 1:
                        raise
            
        except Exception as e:
            return False


class AudioGenerator:
    """音频生成主控制器"""
    
    def __init__(self):
        self.validator = InputValidator()
        self.file_manager = FilePathManager()
        self.stretcher = AudioStretcher()
        self.tts_generator = EdgeTTSGenerator()
        
    def generate_audio(self, config: GenerationConfig, callback: Optional[Callable] = None) -> bool:
        """生成音频文件 - 支持回调版本"""
        success, message = self.validator.validate_inputs(config)
        if not success:
            if callback:
                callback(False, message)
            return False
        
        try:
            self._prepare_and_generate_audio(config)
            if callback:
                callback(True, "生成成功")
            return True
        except Exception as e:
            # 增强错误处理，提供更具体的错误信息
            error_type = type(e).__name__
            if "NoAudioReceived" in str(e):
                error_msg = "音频生成失败：无法从Edge TTS服务接收音频。请尝试以下解决方案：\n1. 检查网络连接\n2. 尝试使用其他语音\n3. 确保语音ID格式正确"
            elif "ConnectionError" in error_type or "Timeout" in error_type:
                error_msg = "网络错误：无法连接到Edge TTS服务。请检查您的网络连接并重试。"
            elif "ValueError" in error_type and "voice" in str(e).lower():
                error_msg = "语音错误：指定的语音ID无效。请尝试选择列表中的其他语音。"
            else:
                error_msg = f"生成音频时发生错误: {str(e)}"
                
            if callback:
                callback(False, error_msg)
            return False

    def generate_preview(self, config: GenerationConfig, 
                        success_callback: Callable, 
                        error_callback: Callable):
        """生成预览音频"""
        try:
            success, message = self.validator.validate_preview_inputs(config)
            if not success:
                error_callback(message)
                return
                
            # 额外的兼容性验证：检查语音ID是否包含非法字符
            if any(char in config.voice for char in ['(', ')', '（', '）', '[', ']', '{', '}', ' ', '\t', '\n']):
                clean_voice = ''.join(char for char in config.voice if char not in ['(', ')', '（', '）', '[', ']', '{', '}', ' ', '\t', '\n'])
                # 创建配置副本并使用清理后的语音ID
                config = GenerationConfig(
                    content=config.content,
                    voice=clean_voice,
                    speed=config.speed,
                    pitch=config.pitch,
                    volume=config.volume,
                    save_path=config.save_path,
                    stretch_factor=config.stretch_factor,
                    stretch_enabled=config.stretch_enabled
                )
                
            #临时文件名
            temp_filename = self.file_manager.generate_preview_filename()
            program_dir = os.path.dirname(os.path.abspath(__file__))
            temp_path = os.path.join(program_dir, temp_filename)
            
            #预处理文本
            text = AudioParameterFormatter.preprocess_text(config.content)
            rate = AudioParameterFormatter.format_speed(config.speed)
            pitch = AudioParameterFormatter.format_pitch(config.pitch)
            volume = AudioParameterFormatter.format_volume(config.volume)
            
            #延迟导入Edge-TTS模块
            import edge_tts
            
            #生成预览
            communicate = edge_tts.Communicate(
                text=text, 
                voice=config.voice + "Neural", 
                rate=rate, 
                pitch=pitch, 
                volume=volume
            )
            
            communicate.save_sync(temp_path)
            
            #应用音频拉伸
            if (hasattr(config, 'stretch_enabled') and config.stretch_enabled and 
                hasattr(config, 'stretch_factor') and config.stretch_factor != 1.0):
                stretched_path = self.stretcher.apply_audio_stretch(temp_path, config.stretch_factor)
                
                #拉伸成功
                if stretched_path != temp_path and os.path.exists(stretched_path):
                    # 删除原始文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    temp_path = stretched_path
                else:
                    pass  # 音频拉伸失败或未生成新文件，使用原始音频
            else:
                pass  # 音频拉伸未启用或拉伸因子为1.0，跳过拉伸
            
            success_callback(temp_path)
            
        except Exception as e:
            error_callback(str(e))

    def _prepare_and_generate_audio(self, config: GenerationConfig):
        """准备并生成音频"""
        # 生成临时文件     
        self.file_manager.ensure_save_directory_exists(config.save_path)
        
        
        temp_path = self.file_manager.create_temp_file()
        
        #生成音频
        if not self.tts_generator.generate_audio(config, temp_path):
            raise Exception("Edge-TTS生成音频失败")
        
        # 应用音频拉伸
        final_path = temp_path
        if (hasattr(config, 'stretch_enabled') and config.stretch_enabled and 
            hasattr(config, 'stretch_factor') and config.stretch_factor != 1.0):
            stretched_path = self.stretcher.apply_audio_stretch(temp_path, config.stretch_factor)
            
            # 拉伸成功
            if stretched_path != temp_path and os.path.exists(stretched_path):
                # 删除临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                final_path = stretched_path
            else:
                pass  # 音频拉伸失败或未生成新文件，使用原始音频
        else:
            pass  # 音频拉伸未启用或拉伸因子为1.0，跳过拉伸
        
        # 重命名
        if final_path != config.save_path:
            shutil.move(final_path, config.save_path)

    def _handle_generation_error(self, error: Exception):
        """处理生成错误"""
        pass