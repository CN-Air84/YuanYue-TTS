import re
import os
import traceback
import subprocess
import tempfile
import shutil
from typing import Callable, Optional, Tuple
from dataclasses import dataclass

import edge_tts


@dataclass
class GenerationConfig:
    """音频生成配置数据类"""
    content: str
    voice: str
    speed: int
    pitch: int
    volume: int
    save_path: str
    stretch_factor: float = 1.0
    stretch_enabled: bool = False


class AudioParameterFormatter:
    """音频参数格式化器"""
    
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
    """文件路径管理器"""
    
    @staticmethod
    def ensure_save_directory_exists(save_path: str) -> bool:
        """确保保存目录存在"""
        save_dir = os.path.dirname(save_path)
        if not os.path.exists(save_dir):
            print(f"创建保存目录: {save_dir}")
            try:
                os.makedirs(save_dir)
                return True
            except Exception as e:
                print(f"创建目录失败: {e}")
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
    """音频拉伸处理器"""
    
    @staticmethod
    def apply_audio_stretch(input_path: str, stretch_factor: float) -> str:
        """应用音频拉伸（变速不变调）- 使用FFmpeg"""
        try:
            print(f"应用音频拉伸: {stretch_factor}倍")
            
            # 创建输出文件路径
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_stretched{ext}"
            
            # 构建FFmpeg命令
            cmd = AudioStretcher._build_ffmpeg_command(input_path, output_path, stretch_factor)
            
            # 执行命令
            print(f"执行FFmpeg命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"FFmpeg拉伸失败: {result.stderr}")
                print(f"FFmpeg标准输出: {result.stdout}")
                return input_path
            
            print(f"音频拉伸成功: {input_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            # 如果拉伸失败，返回原文件
            print(f"音频拉伸失败: {e}")
            traceback.print_exc()
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
    """输入验证器"""
    
    @staticmethod
    def validate_inputs(config: GenerationConfig) -> Tuple[bool, str]:
        """验证输入参数"""
        empty_fields = []
        
        if not config.save_path.strip():
            empty_fields.append("保存路径")
        if config.voice == "选项1":
            empty_fields.append("语音选项")

        if empty_fields:
            print("没有指定路径")
            return False, "没有指定路径"
        
        if "（" in config.voice:
            print("音色选择错误")
            return False, "音色选择错误"
            
        return True, ""
    
    @staticmethod
    def validate_preview_inputs(config: GenerationConfig) -> Tuple[bool, str]:
        """验证预览输入参数"""
        if "（" in config.voice:
            print("音色选择错误")
            return False, "音色选择错误"
        
        if not config.content.strip():
            print("没有输入文本")
            return False, "没有输入文本"
            
        return True, ""


class EdgeTTSGenerator:
    """Edge-TTS 生成器"""
    
    def __init__(self):
        self.parameter_formatter = AudioParameterFormatter()
    
    def generate_audio(self, config: GenerationConfig, temp_path: str) -> bool:
        """生成音频文件"""
        try:
            #预处理文本和参数
            text = self.parameter_formatter.preprocess_text(config.content)
            rate = self.parameter_formatter.format_speed(config.speed)
            pitch = self.parameter_formatter.format_pitch(config.pitch)
            volume = self.parameter_formatter.format_volume(config.volume)
            
            print(f"开始生成音频... 参数: 语速={rate}, 音调={pitch}, 音量={volume}")
            print(f"音频拉伸设置: 启用={config.stretch_enabled}, 拉伸因子={config.stretch_factor}")
            
            #生成音频
            communicate = edge_tts.Communicate(
                text=text, 
                voice=config.voice + "Neural", 
                rate=rate, 
                pitch=pitch, 
                volume=volume
            )
            
            communicate.save_sync(temp_path)
            print("音频生成成功")
            return True
            
        except Exception as e:
            print(f"Edge-TTS生成音频失败: {e}")
            traceback.print_exc()
            return False


class AudioGenerator:
    """音频生成器，负责数值合规性检测和音频生成"""
    
    def __init__(self):
        self.validator = InputValidator()
        self.file_manager = FilePathManager()
        self.stretcher = AudioStretcher()
        self.tts_generator = EdgeTTSGenerator()
        
    def generate_audio(self, config: GenerationConfig, callback: Optional[Callable] = None) -> bool:
        """生成音频文件 - 支持回调版本"""
        print("开始生成音频")
    
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
            error_msg = f"生成音频时发生错误: {str(e)}"
            print(error_msg)
            traceback.print_exc()
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
                
            #临时文件名
            temp_filename = self.file_manager.generate_preview_filename()
            program_dir = os.path.dirname(os.path.abspath(__file__))
            temp_path = os.path.join(program_dir, temp_filename)
            
            #预处理文本
            text = AudioParameterFormatter.preprocess_text(config.content)
            rate = AudioParameterFormatter.format_speed(config.speed)
            pitch = AudioParameterFormatter.format_pitch(config.pitch)
            volume = AudioParameterFormatter.format_volume(config.volume)
            
            print("开始生成预览音频...")
            print(f"音频拉伸设置: 启用={config.stretch_enabled}, 拉伸因子={config.stretch_factor}")
            
            #生成预览
            communicate = edge_tts.Communicate(
                text=text, 
                voice=config.voice + "Neural", 
                rate=rate, 
                pitch=pitch, 
                volume=volume
            )
            
            communicate.save_sync(temp_path)
            print(f"预览音频已生成: {temp_path}")
            
            #应用音频拉伸
            if (hasattr(config, 'stretch_enabled') and config.stretch_enabled and 
                hasattr(config, 'stretch_factor') and config.stretch_factor != 1.0):
                print(f"应用音频拉伸到预览音频: 拉伸因子={config.stretch_factor}")
                stretched_path = self.stretcher.apply_audio_stretch(temp_path, config.stretch_factor)
                
                #拉伸成功
                if stretched_path != temp_path and os.path.exists(stretched_path):
                    # 删除原始文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    temp_path = stretched_path
                    print(f"使用拉伸后的预览音频: {temp_path}")
                else:
                    print("音频拉伸失败或未生成新文件，使用原始音频")
            else:
                print("音频拉伸未启用或拉伸因子为1.0，跳过拉伸")
            
            print("预览音频处理完成")
            
            success_callback(temp_path)
            
        except Exception as e:
            print(f"生成预览音频时发生错误: {e}")
            traceback.print_exc()
            error_callback(str(e))

    def _prepare_and_generate_audio(self, config: GenerationConfig):
        """准备并生成音频"""
        print(f"音色: {config.voice}")
        print(f"参数: 语速={config.speed}, 音调={config.pitch}, "
              f"音量={config.volume}, 语音={config.voice}, "
              f"保存路径={config.save_path}")
        print(f"音频拉伸设置: 启用={config.stretch_enabled}, 拉伸因子={config.stretch_factor}")
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
            print(f"应用音频拉伸到最终音频: 拉伸因子={config.stretch_factor}")
            stretched_path = self.stretcher.apply_audio_stretch(temp_path, config.stretch_factor)
            
            # 拉伸成功
            if stretched_path != temp_path and os.path.exists(stretched_path):
                # 删除临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                final_path = stretched_path
                print(f"使用拉伸后的最终音频: {final_path}")
            else:
                print("音频拉伸失败或未生成新文件，使用原始音频")
        else:
            print("音频拉伸未启用或拉伸因子为1.0，跳过拉伸")
        
        # 重命名
        if final_path != config.save_path:
            shutil.move(final_path, config.save_path)
        
        print(f"音频已生成并保存到: {config.save_path}")

    def _handle_generation_error(self, error: Exception):
        """处理生成错误"""
        print(f"生成音频时发生错误: {error}")
        traceback.print_exc()