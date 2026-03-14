import re
import os
import sys
import platform
import traceback
import subprocess
import tempfile
import shutil
from typing import Callable, Optional, Tuple
from dataclasses import dataclass
from debug_logger import debug_logger, LogLevel

'''
本段代码在SimeonTest Re1时使用 DeepSeek 重构，
地破细可 vs 差特计屁蹄，拟盟知道吗？
'''
try:
    import miniaudio
    MINIAUDIO_AVAILABLE = True
except ImportError:
    MINIAUDIO_AVAILABLE = False
    debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, "miniaudio 库未安装，MP3转WAV将继续尝试使用 FFmpeg (如有)")

try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))


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
        # Edge-TTS 对于 0 值的处理可能因版本而异，通常 +0% 或 -0% 都是可以的
        # 但为了最大兼容性，我们确保格式一致
        if value >= 0:
            return f"+{value}{unit}"
        return f"{value}{unit}"
    
    @staticmethod
    def format_speed(speed: int) -> str:
        """格式化语速参数"""
        # Edge-TTS 语速范围通常是 -100% 到 +100%
        formatted = AudioParameterFormatter.format_parameter(speed, "%")
        return formatted
    
    @staticmethod
    def format_pitch(pitch: int) -> str:
        """格式化音调参数"""
        # Edge-TTS 音调通常使用 Hz 或 st (semitones)
        # 注意：某些版本可能不支持 Hz 格式的 0 值带正号，或者对单位敏感
        formatted = AudioParameterFormatter.format_parameter(pitch, "Hz")
        return formatted
    
    @staticmethod
    def format_volume(volume: int) -> str:
        """格式化音量参数"""
        # Edge-TTS 音量通常是 -100% 到 +100%
        formatted = AudioParameterFormatter.format_parameter(volume, "%")
        return formatted
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """预处理文本"""
        processed = re.sub(r'\n', '，', text)
        if text != processed:
             debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "预处理文本: 替换换行符", fold_code="PARAM_FMT")
        return processed


class FilePathManager:
    """文件路径管理工具"""
    
    @staticmethod
    def ensure_save_directory_exists(save_path: str) -> bool:
        """确保保存目录存在"""
        save_dir = os.path.dirname(save_path)
        if not os.path.exists(save_dir):
            try:
                debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Creating directory: {save_dir}", fold_code="AUDIO_FILE")
                os.makedirs(save_dir)
                return True
            except Exception as e:
                debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"Failed to create directory {save_dir}: {e}", fold_code="AUDIO_FILE")
                raise
        return True
    
    @staticmethod
    def create_temp_file(suffix: str = '.mp3') -> str:
        """创建临时文件"""
        # 确保cache/audios目录存在
        cache_dir = os.path.join(get_app_base_path(), 'cache', 'audios')
        os.makedirs(cache_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=suffix, delete=False) as temp_file:
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Created temp file: {temp_file.name}", fold_code="AUDIO_FILE")
            return temp_file.name
    
    @staticmethod
    def generate_preview_filename() -> str:
        """生成预览文件名"""
        import datetime
        now = datetime.datetime.now()
        cache_dir = os.path.join(get_app_base_path(), 'cache', 'audios')
        os.makedirs(cache_dir, exist_ok=True)
        filename = os.path.join(cache_dir, f"tmp_{now.strftime('%m%d%H%M%S')}.mp3")
        debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Generated preview filename: {filename}", fold_code="AUDIO_FILE")
        return filename


class AudioStretcher:
    """音频拉伸处理工具"""
    
    @staticmethod
    def apply_audio_stretch(input_path: str, stretch_factor: float) -> str:
        """应用音频拉伸（变速不变调）- 使用FFmpeg"""
        try:
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Starting audio stretch. Factor: {stretch_factor}, Input: {input_path}", fold_code="AUDIO_STRETCH")
            # 创建输出文件路径
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_stretched{ext}"
            
            # 构建FFmpeg命令
            cmd = AudioStretcher._build_ffmpeg_command(input_path, output_path, stretch_factor)
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"FFmpeg command: {cmd}", fold_code="AUDIO_STRETCH")
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"FFmpeg stretch failed: {result.stderr}", fold_code="AUDIO_STRETCH")
                return input_path
            
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Audio stretch successful. Output: {output_path}", fold_code="AUDIO_STRETCH")
            return output_path
            
        except Exception as e:
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"Exception during audio stretch: {e}", fold_code="AUDIO_STRETCH")
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
            msg = "没有指定路径"
            debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Input validation failed: {msg} (Fields: {empty_fields})", fold_code="AUDIO_VAL")
            return False, msg
        
        if "（" in config.voice:
            msg = "音色选择错误"
            debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Input validation failed: {msg} (Voice: {config.voice})", fold_code="AUDIO_VAL")
            return False, msg
            
        return True, ""
    
    @staticmethod
    def validate_preview_inputs(config: GenerationConfig) -> Tuple[bool, str]:
        """验证预览输入参数"""
        if "（" in config.voice:
            msg = "音色选择错误"
            debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Preview validation failed: {msg} (Voice: {config.voice})", fold_code="AUDIO_VAL")
            return False, msg
        
        if not config.content.strip():
            msg = "没有输入文本"
            debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Preview validation failed: {msg}", fold_code="AUDIO_VAL")
            return False, msg
            
        return True, ""


class EdgeTTSGenerator:
    """Edge-TTS音频生成工具"""
    
    def __init__(self):
        self.parameter_formatter = AudioParameterFormatter()
    
    def generate_audio(self, config: GenerationConfig, temp_path: str) -> bool:
        """生成音频文件"""
        try:
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Starting Edge-TTS generation. Voice: {config.voice}", fold_code="EDGE_TTS")
            # 延迟导入Edge-TTS模块
            import edge_tts
            
            #预处理文本和参数
            text = self.parameter_formatter.preprocess_text(config.content)
            rate = self.parameter_formatter.format_speed(config.speed)
            pitch = self.parameter_formatter.format_pitch(config.pitch)
            volume = self.parameter_formatter.format_volume(config.volume)
            
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Formatted params - Rate: {rate}, Pitch: {pitch}, Volume: {volume}", fold_code="EDGE_TTS")

            voice_id = config.voice
            
            # 统一音色 ID 格式：直接在基础 ID 后追加 "Neural"
            voice_format = voice_id + "Neural"
            
            # 尝试生成音频
            max_retries = 2
            retry_count = 0
            while retry_count <= max_retries:
                try:
                    debug_logger.output("edge_audio_generator.py", LogLevel.INFO, 
                                      f"Attempting generation with params - Voice: {voice_format}, Rate: {rate}, Pitch: {pitch}, Volume: {volume} (Retry {retry_count})", 
                                      fold_code="EDGE_TTS")
                    
                    #生成音频
                    communicate = edge_tts.Communicate(
                        text=text, 
                        voice=voice_format, 
                        rate=rate, 
                        pitch=pitch, 
                        volume=volume
                    )
                    
                    # 使用 asyncio 管理事件循环
                    import asyncio
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(communicate.save(temp_path))
                        loop.close()
                    except Exception as async_e:
                        debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Async save failed: {async_e}", fold_code="EDGE_TTS")
                        raise async_e
                        
                    debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Edge-TTS generation successful", fold_code="EDGE_TTS")
                    return True
                except Exception as inner_e:
                    error_msg = str(inner_e)
                    debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Failed with voice ID {voice_format} (retry {retry_count}): {error_msg}", fold_code="EDGE_TTS")
                    
                    # 特别处理日期解析错误
                    if "Failed to parse server date" in error_msg:
                        import time
                        time.sleep(1)
                        retry_count += 1
                        continue
                    
                    # 如果是 "No audio was received"
                    if "No audio was received" in error_msg:
                        import time
                        time.sleep(1.5)
                        retry_count += 1
                        continue
                        
                    # 其他错误重试
                    if retry_count < max_retries:
                        import time
                        time.sleep(0.5)
                        retry_count += 1
                    else:
                        raise Exception(f"Edge-TTS 生成失败。最后一次错误: {error_msg}")
            
        except Exception as e:
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"Edge-TTS generation failed: {e}", fold_code="EDGE_TTS")
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
        debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"开始验证音频生成输入 - 音色: '{config.voice}', 保存路径: '{config.save_path}', 文本长度: {len(config.content)}", fold_code="AUDIO_GEN")
        success, message = self.validator.validate_inputs(config)
        if not success:
            debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"音频生成输入验证失败: {message}", fold_code="AUDIO_GEN")
            if callback:
                callback(False, message)
            return False
        
        try:
            self._prepare_and_generate_audio(config)
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "音频生成流程全部完成", fold_code="AUDIO_GEN")
            if callback:
                callback(True, "生成成功")
            return True
        except Exception as e:
            # 增强错误处理，提供更具体的错误信息
            error_type = type(e).__name__
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"音频生成异常 ({error_type}): {e}", fold_code="AUDIO_GEN")
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
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Starting preview generation...", fold_code="AUDIO_PREVIEW")
            success, message = self.validator.validate_preview_inputs(config)
            if not success:
                debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"Preview validation failed: {message}", fold_code="AUDIO_PREVIEW")
                error_callback(message)
                return
                
            # 额外的兼容性验证：检查语音ID是否包含非法字符
            if any(char in config.voice for char in ['(', ')', '（', '）', '[', ']', '{', '}', ' ', '\t', '\n']):
                clean_voice = ''.join(char for char in config.voice if char not in ['(', ')', '（', '）', '[', ']', '{', '}', ' ', '\t', '\n'])
                debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Cleaned voice ID: {config.voice} -> {clean_voice}", fold_code="AUDIO_PREVIEW")
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
            temp_path = self.file_manager.generate_preview_filename()
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Preview temp path: {temp_path}", fold_code="AUDIO_PREVIEW")
            
            #预处理文本
            text = AudioParameterFormatter.preprocess_text(config.content)
            rate = AudioParameterFormatter.format_speed(config.speed)
            pitch = AudioParameterFormatter.format_pitch(config.pitch)
            volume = AudioParameterFormatter.format_volume(config.volume)
            
            #延迟导入Edge-TTS模块
            import edge_tts
            
            # 确保语音ID格式正确：直接追加 "Neural"
            preview_voice = config.voice + "Neural"
            
            #生成预览
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Generating preview with Edge-TTS (Voice: {preview_voice}, Rate: {rate}, Pitch: {pitch}, Volume: {volume})...", fold_code="AUDIO_PREVIEW")
            
            communicate = edge_tts.Communicate(
                text=text, 
                voice=preview_voice, 
                rate=rate, 
                pitch=pitch, 
                volume=volume
            )
            
            # 使用 asyncio.run 替代 save_sync
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(communicate.save(temp_path))
            loop.close()
            
            # 转换为WAV格式（如果目标路径是WAV格式）
            if config.save_path.lower().endswith('.wav'):
                debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Converting preview to WAV...", fold_code="AUDIO_PREVIEW")
                wav_path = self._convert_mp3_to_wav(temp_path)
                if wav_path and os.path.exists(wav_path):
                    # 删除MP3临时文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    temp_path = wav_path
            
            #应用音频拉伸
            if (hasattr(config, 'stretch_enabled') and config.stretch_enabled and 
                hasattr(config, 'stretch_factor') and config.stretch_factor != 1.0):
                debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Applying stretch to preview...", fold_code="AUDIO_PREVIEW")
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
                    debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, "Preview stretch failed, using original.", fold_code="AUDIO_PREVIEW")
                    pass  # 音频拉伸失败或未生成新文件，使用原始音频
            else:
                pass  # 音频拉伸未启用或拉伸因子为1.0，跳过拉伸
            
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Preview generation completed: {temp_path}", fold_code="AUDIO_PREVIEW")
            success_callback(temp_path)
            
        except Exception as e:
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"Preview generation failed: {e}", fold_code="AUDIO_PREVIEW")
            error_callback(str(e))

    def _prepare_and_generate_audio(self, config: GenerationConfig):
        """准备并生成音频"""
        # 生成临时文件     
        debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Ensuring save directory exists...", fold_code="AUDIO_GEN")
        self.file_manager.ensure_save_directory_exists(config.save_path)
        
        
        temp_path = self.file_manager.create_temp_file()
        debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Created temp file for generation: {temp_path}", fold_code="AUDIO_GEN")
        
        #生成音频
        if not self.tts_generator.generate_audio(config, temp_path):
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, "TTS generation failed.", fold_code="AUDIO_GEN")
            raise Exception("Edge-TTS生成音频失败")
        
        # 添加延迟确保文件完全写入
        import time
        mp3_size = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
        debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"音频生成完成，文件大小: {mp3_size} 字节", fold_code="AUDIO_GEN")
        
        if mp3_size > 0:
            # 等待一小段时间确保文件完全写入磁盘
            time.sleep(0.1)
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "等待文件写入完成，继续处理...", fold_code="AUDIO_GEN")
        
        # 转换为WAV格式（如果目标路径是WAV格式）
        if config.save_path.lower().endswith('.wav'):
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Converting to WAV...", fold_code="AUDIO_GEN")
            wav_path = self._convert_mp3_to_wav(temp_path)
            if wav_path and os.path.exists(wav_path):
                # 删除MP3临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                temp_path = wav_path
        
        # 应用音频拉伸
        final_path = temp_path
        if (hasattr(config, 'stretch_enabled') and config.stretch_enabled and 
            hasattr(config, 'stretch_factor') and config.stretch_factor != 1.0):
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Applying stretch (factor={config.stretch_factor})...", fold_code="AUDIO_GEN")
            stretched_path = self.stretcher.apply_audio_stretch(temp_path, config.stretch_factor)
            
            # 拉伸成功
            if stretched_path != temp_path and os.path.exists(stretched_path):
                # 删除临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                final_path = stretched_path
                debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Stretch applied successfully.", fold_code="AUDIO_GEN")
            else:
                debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, "Stretch failed or no change.", fold_code="AUDIO_GEN")
                pass  # 音频拉伸失败或未生成新文件，使用原始音频
        else:
            pass  # 音频拉伸未启用或拉伸因子为1.0，跳过拉伸
        
        # 重命名
        if final_path != config.save_path:
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"Moving result to final path: {config.save_path}", fold_code="AUDIO_GEN")
            shutil.move(final_path, config.save_path)
        else:
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, "Result already at final path.", fold_code="AUDIO_GEN")

    def _convert_mp3_to_wav(self, mp3_path: str) -> str:
        """将MP3文件转换为WAV格式 (使用 miniaudio，零依赖)"""
        try:
            import os
            import time
            
            # 生成WAV文件路径
            base_path = os.path.splitext(mp3_path)[0]
            wav_path = base_path + '.wav'
            
            # 首先检查MP3文件是否存在且大小大于0
            if not os.path.exists(mp3_path):
                debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"MP3转换终止: 源文件不存在 at {mp3_path}", fold_code="AUDIO_CONV")
                return None
                
            mp3_size = os.path.getsize(mp3_path)
            if mp3_size == 0:
                debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"MP3转换终止: 源文件为空 (0字节) at {mp3_path}", fold_code="AUDIO_CONV")
                return None

            # 优先使用 miniaudio 进行转换
            if MINIAUDIO_AVAILABLE:
                try:
                    debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"正在使用 miniaudio 将 MP3 转换为 WAV...", fold_code="AUDIO_CONV")
                    # 读取 MP3
                    audio = miniaudio.decode_file(mp3_path)
                    # 写入 WAV
                    miniaudio.wav_write_file(wav_path, audio)
                    
                    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                        debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"miniaudio 转换成功: {os.path.basename(wav_path)}", fold_code="AUDIO_CONV")
                        return wav_path
                except Exception as mae:
                    debug_logger.output("edge_audio_generator.py", LogLevel.WARNING, f"miniaudio 转换失败，尝试回退到 FFmpeg: {mae}", fold_code="AUDIO_CONV")
            
            # 如果 miniaudio 不可用或转换失败，回退到 FFmpeg (作为兜底)
            debug_logger.output("edge_audio_generator.py", LogLevel.INFO, f"准备使用 FFmpeg 将 MP3 转换为 WAV...", fold_code="AUDIO_CONV")
            
            # 重试机制 - 最多重试3次
            max_retries = 3
            for retry in range(max_retries):
                try:
                    if retry > 0:
                        time.sleep(0.5 * retry)
                    
                    # 使用FFmpeg转换格式
                    cmd = [
                        'ffmpeg', '-i', mp3_path, 
                        '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', '-y',
                        wav_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0 and os.path.exists(wav_path):
                        if os.path.getsize(wav_path) > 0:
                            return wav_path
                            
                except Exception:
                    continue
            
            return None
                
        except Exception as e:
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"MP3转WAV总体异常: {e}", fold_code="AUDIO_CONV")
            return None

    def _handle_generation_error(self, error: Exception):
        """处理生成错误"""
        try:
            error_msg = str(error)
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"处理音频生成错误: {error_msg}", fold_code="AUDIO_GEN")
            # 这里可以扩展更详细的错误处理逻辑，例如清理临时文件等
        except Exception as e:
            debug_logger.output("edge_audio_generator.py", LogLevel.ERROR, f"处理音频生成错误逻辑时出错: {str(e)}", fold_code="AUDIO_GEN")