# coding=utf-8
import threading
import re
import time
import os
import hashlib
import random
import json
from typing import Callable, List, Dict, Optional
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QSlider, QTextEdit, QCheckBox, QComboBox, QLabel, 
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QButtonGroup, QMessageBox,
    QStackedWidget, QGraphicsOpacityEffect,
    QFrame, QScrollArea, QGridLayout,
    QSizePolicy, QSpacerItem, QLayout, QFileDialog, QListWidget, QListWidgetItem,
    QAbstractItemView, QDoubleSpinBox, QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, pyqtSlot, QTimer, QPropertyAnimation, QEasingCurve, QVariantAnimation, QSize, QParallelAnimationGroup, QPoint, QEvent
from PyQt5.QtGui import QFont, QColor, QPainter, QFontMetrics

from misc_func import AudioConfig, VoiceConfig, ContentHasher, AudioFileManager, InputValidator
from iw_text_import import show_text_import_dialog
from shared_memory_manager import get_shared_memory_manager
from debug_logger import debug_logger, LogLevel
from settings_page import SettingsManager
from tts_engine_interface import TTSEngineError
from theme_page_adapter import (
    configure_independent_surface,
    configure_semantic_surface,
    configure_theme_card,
    configure_transparent_container,
    configure_transparent_root,
    set_transparent_scroll_content,
)


# =============================================================================
# 信号类
# =============================================================================
class GenerationSignals(QObject):
    """生成页面信号类"""
    generation_complete = pyqtSignal(bool, str)
    preview_generated = pyqtSignal(str)
    preview_error = pyqtSignal(str)
    update_button_state = pyqtSignal(bool, str)
    sentence_generated = pyqtSignal(int, str, float)  # 句子索引, 音频文件路径, 音频时长
    all_sentences_complete = pyqtSignal()  # 所有句子生成完成
    playback_ready = pyqtSignal()  # 可以开始播放
    tts_error = pyqtSignal(str)


# =============================================================================
# 文本分割器
# =============================================================================
class SentenceSplitter:
    """文本分割器 - 按标点符号分割文本为小句
    
    支持的分隔符：
    - 中文：，。！？；……（）/ ～
    - 英文：,.!?;()/
    - 其他：换行符、~（波浪线）、\\（反斜杠）
    """
    
    # 分隔符定义：名称 -> (符号, 显示符号)
    # 注意：符号必须是实际用于分割的字符
    PAUSE_MARKS = {
        '逗号': ('，', '，'),
        '句号': ('。', '。'),
        '叹号': ('！', '！'),
        '问号': ('？', '？'),
        '分号': ('；', '；'),
        '冒号': ('：', '：'),        # 中文冒号
        '省略号': ('……', '……'),
        '左括号': ('（', '（'),      # 中文左括号
        '右括号': ('）', '）'),      # 中文右括号
        '斜杠': ('/', '/'),
        '反斜杠': ('\\', '\\'),
        '波浪线': ('~', '~'),
        '句点': ('.', '.'),
        '英文逗号': (',', ','),
        '英文叹号': ('!', '!'),
        '英文问号': ('?', '?'),
        '英文分号': (';', ';'),
        '英文冒号': (':', ':'),      # 英文冒号
        '英文左括号': ('(', '('),    # 英文左括号
        '英文右括号': (')', ')'),    # 英文右括号
        '换行': ('\n', '↵'),
    }
    
    # 所有标点符号的映射表（包括分隔符和非分隔符）
    ALL_PUNCTUATION_MARKS = {
        # 中文标点
        '，': '逗号',
        '。': '句号',
        '！': '叹号',
        '？': '问号',
        '；': '分号',
        '：': '冒号',
        '……': '省略号',
        '—': '破折号',
        '–': '短破折号',
        '（': '左括号',
        '）': '右括号',
        '【': '左方括号',
        '】': '右方括号',
        '《': '左书名号',
        '》': '右书名号',
        '〈': '左单书名号',
        '〉': '右单书名号',
        '"': '左双引号',
        '"': '右双引号',
        ''': '左单引号',
        ''': '右单引号',
        '『': '左直角引号',
        '』': '右直角引号',
        '「': '左角引号',
        '」': '右角引号',
        '、': '顿号',
        '·': '间隔号',
        '～': '波浪号',
        '〜': '全角波浪号',
        
        # 英文标点
        ',': '英文逗号',
        '.': '句点',
        '!': '英文叹号',
        '?': '英文问号',
        ';': '英文分号',
        ':': '英文冒号',
        '-': '连字符',
        '—': '长破折号',
        '–': '短破折号',
        '(': '英文左括号',
        ')': '英文右括号',
        '[': '英文左方括号',
        ']': '英文右方括号',
        '{': '英文左花括号',
        '}': '英文右花括号',
        '<': '英文左尖括号',
        '>': '英文右尖括号',
        '"': '英文双引号',
        "'": '英文单引号',
        '`': '反引号',
        '´': '重音符',
        
        # 其他符号
        '/': '斜杠',
        '\\': '反斜杠',
        '|': '竖线',
        '~': '波浪线',
        '*': '星号',
        '&': '和号',
        '@': 'at符号',
        '#': '井号',
        '$': '美元符号',
        '%': '百分号',
        '^': '脱字符',
        '_': '下划线',
        '+': '加号',
        '=': '等号',
        '¥': '人民币符号',
        '€': '欧元符号',
        '£': '英镑符号',
        '°': '度数符号',
        '§': '章节符号',
        '¶': '段落符号',
        '†': '剑号',
        '‡': '双剑号',
        '•': '项目符号',
        '‰': '千分号',
        '′': '分符号',
        '″': '秒符号',
        '※': '参考符号',
        '→': '右箭头',
        '←': '左箭头',
        '↑': '上箭头',
        '↓': '下箭头',
        '⇒': '双线右箭头',
        '⇐': '双线左箭头',
        '×': '乘号',
        '÷': '除号',
        '±': '正负号',
        '≈': '约等于',
        '≠': '不等于',
        '≤': '小于等于',
        '≥': '大于等于',
        '∞': '无穷大',
        '∑': '求和符号',
        '∏': '连乘符号',
        '√': '根号',
        '∫': '积分符号',
        '∂': '偏微分符号',
        '∇': '梯度符号',
        '∈': '属于',
        '∉': '不属于',
        '⊂': '真子集',
        '⊃': '真超集',
        '⊆': '子集',
        '⊇': '超集',
        '∪': '并集',
        '∩': '交集',
        '∅': '空集',
        '∀': '任意',
        '∃': '存在',
        '¬': '非',
        '∧': '与',
        '∨': '或',
        '⊕': '异或',
        '⊗': '张量积',
        '℃': '摄氏度',
        '℉': '华氏度',
        '\n': '换行',
    }
    
    def __init__(self):
        # 默认所有分隔符都启用
        self.enabled_marks = set(self.PAUSE_MARKS.keys())
        # 标点提示开关，默认启用
        self.punctuation_hint_enabled = True
    
    def set_pause_marks(self, enabled_marks: set):
        """设置启用的停顿符号名称集合"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                           f"更新启用的停顿符号，数量: {len(enabled_marks)}", fold_code="GEN_SPLIT")
        self.enabled_marks = enabled_marks
    
    def set_punctuation_hint(self, enabled: bool):
        """设置标点提示开关"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                           f"标点提示开关: {'启用' if enabled else '禁用'}", fold_code="GEN_SPLIT")
        self.punctuation_hint_enabled = enabled
    
    def _get_enabled_separators(self) -> List[str]:
        """获取所有启用的分隔符字符列表"""
        separators = []
        for name in self.enabled_marks:
            if name in self.PAUSE_MARKS:
                separators.append(self.PAUSE_MARKS[name][0])
        # 按长度降序排列，确保多字符分隔符（如……）优先匹配
        separators.sort(key=len, reverse=True)
        return separators
    
    def split_text(self, text: str) -> List[str]:
        """将文本分割为小句
        
        Args:
            text: 待分割的文本
            
        Returns:
            分割后的句子列表（已去除空白和无效内容）
        """
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                           f"开始分割文本，原始长度: {len(text)}", fold_code="GEN_SPLIT")
        
        # 预处理：去除首尾空白
        text = text.strip()
        if not text:
            return []
        
        # 获取启用的分隔符
        separators = self._get_enabled_separators()
        if not separators:
            # 如果没有分隔符，整个文本作为一句
            if self._has_content(text):
                if self.punctuation_hint_enabled:
                    text = self._convert_non_separator_punctuation(text, [])
                return [text]
            return []
        
        # 构建分割模式：使用 re.split 一次性分割
        # 转义所有分隔符并组合成正则表达式
        escaped = [re.escape(sep) for sep in separators]
        pattern = '(' + '|'.join(escaped) + ')'
        
        # 执行分割，保留分隔符
        parts = re.split(pattern, text)
        
        # 合并结果：分隔符前的文本作为一个句子
        sentences = []
        current_sentence = ""
        current_separator = None
        
        for part in parts:
            if not part:
                continue
            # 检查是否是分隔符
            if part in separators:
                # 分隔符前的内容作为一个句子
                if current_sentence:
                    cleaned = self._clean_sentence(current_sentence)
                    # 检查是否包含实际内容（不只是符号）
                    if cleaned and self._has_content(cleaned):
                        # 如果启用了标点提示
                        if self.punctuation_hint_enabled:
                            # 1. 先转换句子内部的非分隔符标点
                            cleaned = self._convert_non_separator_punctuation(cleaned, separators)
                            # 2. 在句子末尾添加分隔符的名称
                            separator_name = self._get_separator_name(part)
                            if separator_name:
                                cleaned = cleaned + " " + separator_name
                        sentences.append(cleaned)
                    current_sentence = ""
                current_separator = part
            else:
                current_sentence += part
        
        # 处理最后剩余的内容（没有分隔符结尾的情况）
        if current_sentence:
            cleaned = self._clean_sentence(current_sentence)
            # 检查是否包含实际内容（不只是符号）
            if cleaned and self._has_content(cleaned):
                if self.punctuation_hint_enabled:
                    cleaned = self._convert_non_separator_punctuation(cleaned, separators)
                sentences.append(cleaned)
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                           f"文本分割完成，产出句子数: {len(sentences)}", fold_code="GEN_SPLIT")
        return sentences
    
    def _get_separator_name(self, separator: str) -> str:
        """根据分隔符获取其名称
        
        Args:
            separator: 分隔符字符
            
        Returns:
            分隔符的名称，如"逗号"、"句号"等
        """
        for name, (symbol, _) in self.PAUSE_MARKS.items():
            if symbol == separator:
                return name
        return ""
    
    def _convert_non_separator_punctuation(self, text: str, separators: List[str]) -> str:
        """将文本中的非分隔符标点符号转换为汉字提示
        
        Args:
            text: 原始文本
            separators: 分隔符列表（这些不转换）
            
        Returns:
            转换后的文本
        """
        # 按长度降序排列，确保多字符标点（如……）优先匹配
        sorted_puncts = sorted(self.ALL_PUNCTUATION_MARKS.keys(), key=len, reverse=True)
        
        result = text
        for punct in sorted_puncts:
            # 跳过分隔符（分隔符已经在句子末尾单独处理）
            if punct in separators:
                continue
            
            if punct in result:
                name = self.ALL_PUNCTUATION_MARKS[punct]
                # 将标点符号替换为 " 标点名称 "（前后加空格）
                result = result.replace(punct, f" {name} ")
        
        return result
    
    def _clean_sentence(self, text: str) -> str:
        """清理单个句子：去除首尾空白和多余空格"""
        text = text.strip()
        # 将多个连续空白字符替换为单个空格
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def _has_content(self, text: str) -> bool:
        """检查文本是否包含实际内容（中文、字母、数字）"""
        # 移除所有非内容字符后检查是否为空
        content = re.sub(r'[^\u4e00-\u9fff\w]', '', text)
        return len(content) > 0


# =============================================================================
# 句子音频管理器
# =============================================================================
class SentenceAudioManager:
    """小句音频管理器"""
    
    def __init__(self):
        self.sentences: List[str] = []
        self.audio_files: Dict[int, str] = {}
        self.audio_durations: Dict[int, float] = {}
        self.current_sentence_index = 0
        self.total_duration = 0.0
        self.is_generating = False
        self.generation_threads = []
        self.max_threads = 4
        self.generation_queue = []
        self.lock = threading.Lock()
        self.active_generation_workers = 0
        self.playback_ready_claimed = False
        self.tts_error_claimed = False
        self.generation_batch_id = 0
        self.play_retry_count = {}
    
    def set_sentences(self, sentences: List[str]):
        """设置句子列表"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"句子管理器已就绪，共接收 {len(sentences)} 句文本", fold_code="GEN_AUDIO_MGR")
        self.sentences = sentences
        self.audio_files.clear()
        self.audio_durations.clear()
        self.current_sentence_index = 0
        self.total_duration = 0.0
        self.play_retry_count.clear()
    
    def get_next_sentence_to_generate(self, batch_id: Optional[int] = None) -> Optional[tuple]:
        """获取下一个要生成的句子"""
        with self.lock:
            if batch_id is not None and batch_id != self.generation_batch_id:
                return None
            if self.generation_queue:
                item = self.generation_queue.pop(0)
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"出队待生成句子: 索引={item[0]}", fold_code="GEN_AUDIO_MGR")
                return item
            return None

    def prepare_generation(self, sentences: List[str], worker_count: int) -> int:
        """Prepare a generation batch shared by all sentence workers."""
        with self.lock:
            self.generation_batch_id += 1
            self.generation_queue = list(enumerate(sentences))
            self.active_generation_workers = worker_count
            self.playback_ready_claimed = False
            self.tts_error_claimed = False
            self.is_generating = True
            return self.generation_batch_id

    def is_generation_active(self, batch_id: int) -> bool:
        with self.lock:
            return self.is_generating and batch_id == self.generation_batch_id

    def claim_playback_ready(self, batch_id: int) -> bool:
        """Return True once for the first audio completed in this batch."""
        with self.lock:
            if batch_id != self.generation_batch_id or self.playback_ready_claimed:
                return False
            self.playback_ready_claimed = True
            return True

    def finish_generation_worker(self, batch_id: int) -> bool:
        """Return True only when the last worker in the batch exits."""
        with self.lock:
            if batch_id != self.generation_batch_id or self.active_generation_workers <= 0:
                return False
            self.active_generation_workers -= 1
            return self.active_generation_workers == 0

    def stop_for_tts_error(self, batch_id: int, sentence_index: int, sentence_text: str) -> bool:
        """Stop the current batch, preserve failed work, and claim its error once."""
        with self.lock:
            if batch_id != self.generation_batch_id:
                return False
            item = (sentence_index, sentence_text)
            if item not in self.generation_queue:
                self.generation_queue.append(item)
                self.generation_queue.sort(key=lambda queued: queued[0])
            self.is_generating = False
            if self.tts_error_claimed:
                return False
            self.tts_error_claimed = True
            return True

    def requeue_sentence(self, sentence_index: int, sentence_text: str):
        """Put a failed sentence back before the remaining generation work."""
        with self.lock:
            item = (sentence_index, sentence_text)
            if not self.generation_queue or self.generation_queue[0] != item:
                self.generation_queue.insert(0, item)
    
    def get_sentence_audio(self, index: int) -> Optional[str]:
        """获取指定句子的音频文件路径"""
        with self.lock:
            return self.audio_files.get(index)
    
    def add_generated_audio(self, sentence_index: int, audio_file: str, duration: float):
        """添加生成的音频"""
        with self.lock:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"注册已生成音频: 索引={sentence_index}, 时长={duration:.2f}s", fold_code="GEN_AUDIO_MGR")
            self.audio_files[sentence_index] = audio_file
            self.audio_durations[sentence_index] = duration
            self.total_duration += duration
    
    def get_total_duration(self) -> float:
        """获取总音频时长"""
        with self.lock:
            return self.total_duration
    
    def get_generated_count(self) -> int:
        """获取已生成的句子数量"""
        with self.lock:
            return len(self.audio_files)
    
    def is_all_generated(self) -> bool:
        """检查是否所有句子都已生成"""
        return len(self.audio_files) == len(self.sentences) and len(self.sentences) > 0
    
    def get_current_sentence_audio(self) -> Optional[str]:
        """获取当前句子的音频文件"""
        return self.audio_files.get(self.current_sentence_index)
    
    def move_to_next_sentence(self) -> bool:
        """移动到下一句"""
        if self.current_sentence_index < len(self.sentences) - 1:
            self.current_sentence_index += 1
            return True
        return False
    
    def move_to_prev_sentence(self) -> bool:
        """移动到上一句"""
        if self.current_sentence_index > 0:
            self.current_sentence_index -= 1
            return True
        return False
    
    def has_next_sentence(self) -> bool:
        """检查是否还有下一句"""
        return self.current_sentence_index < len(self.sentences) - 1

    def has_prev_sentence(self) -> bool:
        """检查是否还有上一句"""
        return self.current_sentence_index > 0
    
    def get_progress_text(self) -> str:
        """获取进度文本"""
        generated = self.get_generated_count()
        total = len(self.sentences)
        return f"{generated}/{total}"


# =============================================================================
# 平滑按钮 - 带颜色动画的按钮
# =============================================================================
class SmoothButton(QPushButton):
    """平滑变色动画按钮"""
    
    def __init__(self, text, btn_type="normal", parent=None):
        super().__init__(text, parent)
        self.btn_type = btn_type
        self.setCheckable(True)
        
        self.normal_bg = QColor(255, 255, 255)
        self.normal_color = QColor(0, 0, 0)
        self.normal_border = QColor("#D0D0D0")
        
        if btn_type == "tab":
            self.checked_bg = QColor(85, 85, 255)
            self.checked_color = QColor(255, 255, 255)
            self.checked_border = QColor("gray")
            self.radius = 5
        elif btn_type == "voice":
            self.checked_bg = QColor(0, 255, 0)
            self.checked_color = QColor(0, 0, 0)
            self.checked_border = QColor("#D0D0D0")
            self.radius = 4
        else:
            self.checked_bg = QColor(230, 230, 230)
            self.checked_color = QColor(0, 0, 0)
            self.checked_border = QColor("gray")
            self.radius = 5
        
        self._bg_color = self.normal_bg
        self._text_color = self.normal_color
        
        self.bg_anim = QVariantAnimation(self)
        self.bg_anim.setDuration(250)
        self.bg_anim.valueChanged.connect(self._on_bg_changed)
        
        self.color_anim = QVariantAnimation(self)
        self.color_anim.setDuration(250)
        self.color_anim.valueChanged.connect(self._on_color_changed)
        
        self.toggled.connect(self._on_toggled)
        self._update_stylesheet()
    
    def _on_toggled(self, checked):
        self.bg_anim.stop()
        self.color_anim.stop()
        
        self.bg_anim.setStartValue(self._bg_color)
        self.bg_anim.setEndValue(self.checked_bg if checked else self.normal_bg)
        
        self.color_anim.setStartValue(self._text_color)
        self.color_anim.setEndValue(self.checked_color if checked else self.normal_color)
        
        self.bg_anim.start()
        self.color_anim.start()

    def _on_bg_changed(self, color):
        self._bg_color = color
        self._update_stylesheet()
        
    def _on_color_changed(self, color):
        self._text_color = color
        self._update_stylesheet()
        
    def _update_stylesheet(self):
        border_color = self.checked_border.name() if self.isChecked() else self.normal_border.name()
        
        css = f"""
            QPushButton {{
                background-color: {self._bg_color.name()};
                color: {self._text_color.name()};
                border: 1px solid {border_color};
                border-radius: {self.radius}px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {self._mix_color(self._bg_color, QColor(240, 240, 240)).name()};
            }}
        """
        self.setStyleSheet(css)
    
    def _mix_color(self, c1, c2):
        """混合两种颜色"""
        return QColor(
            (c1.red() + c2.red()) // 2,
            (c1.green() + c2.green()) // 2,
            (c1.blue() + c2.blue()) // 2
        )
    
    def set_font(self, font):
        """设置字体"""
        self.setFont(font)


# =============================================================================
# 长按按钮 - 支持长按检测
# =============================================================================
class LongPressButton(QPushButton):
    """支持长按检测的按钮"""
    long_pressed = pyqtSignal()  # 长按信号
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.press_timer = QTimer()
        self.press_timer.setSingleShot(True)
        self.press_timer.timeout.connect(self._on_long_press)
        self.long_press_duration = 800  # 长按时长（毫秒）
        self.is_long_press = False
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.is_long_press = False
            self.press_timer.start(self.long_press_duration)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.press_timer.stop()
            if not self.is_long_press:
                super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)
    
    def _on_long_press(self):
        """长按触发"""
        self.is_long_press = True
        self.long_pressed.emit()


# =============================================================================
# 圆角容器
# =============================================================================
class StyledContainer(QFrame):
    """带圆角白底灰边的容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_theme_card(self)
        self.setStyleSheet("""
            StyledContainer {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
            }
            QLabel, QSlider, QProgressBar {
                background: transparent;
            }
        """)


# =============================================================================
# 选项卡内容组件 - 分句列表
# =============================================================================
class MarqueeLabel(QWidget):
    """长文本自动横向滚动的标签"""
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._text = text
        self._offset = 0
        self._speed = 1
        self._needs_scroll = False
        
        self._state = 0  # 0: 等待(开头), 1: 滚动, 2: 等待(结尾)
        self._wait_ticks = 0
        self._max_wait_ticks = 30  # 30 * 30ms = 0.9s
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setMinimumHeight(40)
    
    def setText(self, text: str) -> None:
        self._text = text
        self._reset_animation()
        self._update_scroll_state()
        self.update()

    def set_highlighted(self, highlighted: bool) -> None:
        """Keep custom-painted text in sync with the selected sentence row."""
        self.setStyleSheet("color: #FFFFFF;" if highlighted else "")
        self.update()
    
    def text(self) -> str:
        return self._text
        
    def _reset_animation(self):
        self._offset = 0
        self._state = 0
        self._wait_ticks = 0
    
    def _update_scroll_state(self):
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self._text)
        self._needs_scroll = text_width > (self.width() - 20)
        if self._needs_scroll:
            if not self._timer.isActive():
                self._timer.start(30)
        else:
            self._timer.stop()
            self._reset_animation()
    
    def _tick(self):
        if not self._needs_scroll:
            return
            
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self._text)
        max_scroll = text_width - (self.width() - 20)
        
        if self._state == 0:
            # 在开头等待
            self._wait_ticks += 1
            if self._wait_ticks >= self._max_wait_ticks:
                self._state = 1
                self._wait_ticks = 0
                
        elif self._state == 1:
            # 向左滚动
            self._offset -= self._speed
            if self._offset <= -max_scroll:
                self._offset = -max_scroll
                self._state = 2
                
        elif self._state == 2:
            # 在结尾等待
            self._wait_ticks += 1
            if self._wait_ticks >= self._max_wait_ticks:
                self._reset_animation()
                
        self.update()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scroll_state()
        if self._needs_scroll:
            metrics = QFontMetrics(self.font())
            text_width = metrics.horizontalAdvance(self._text)
            max_scroll = text_width - (self.width() - 20)
            if self._offset < -max_scroll:
                self._offset = -max_scroll
        else:
            self._reset_animation()
    
    def setFont(self, font):
        super().setFont(font)
        self._update_scroll_state()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setPen(self.palette().color(self.foregroundRole()))
        metrics = QFontMetrics(self.font())
        
        # 允许控件自行裁剪超出部分的绘制内容
        x = 10 + self._offset
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2
        painter.drawText(x, y, self._text)
    

class SentenceListWidget(QWidget):
    """分句列表选项卡内容 - 使用可滚动列表显示所有分句"""
    
    sentence_clicked = pyqtSignal(int)  # 点击句子信号，传递句子索引
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.sentences = []
        self.current_index = -1
        self.current_font = self.font()
        self.item_widgets = []
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        
        # 创建列表控件
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setSpacing(4)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: #FFFFFF;
                color: black;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                padding: 0px;
                min-height: 40px;
            }
            QListWidget::item:selected {
                background-color: #2E8B57;
                color: #FFFFFF;
                border: 1px solid #D0D0D0;
            }
            QListWidget::item:hover {
                background-color: #F0F0F0;
            }
            QListWidget::item:selected:hover {
                background-color: #27774A;
                color: #FFFFFF;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        
        layout.addWidget(self.list_widget)
    
    def _on_item_clicked(self, item):
        """处理列表项点击"""
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.sentence_clicked.emit(idx)
    
    def update_sentences(self, sentences: List[str], current_idx: int):
        """更新显示的句子列表"""
        if self.sentences == sentences and self.list_widget.count() == len(sentences):
            # 句子内容没有改变，只需更新当前索引和高亮，不重建列表和重新滚动
            if self.current_index != current_idx:
                self.current_index = current_idx
                self._highlight_current_item()
                if 0 <= current_idx < self.list_widget.count():
                    self.list_widget.scrollToItem(self.list_widget.item(current_idx), 
                                                  QAbstractItemView.PositionAtCenter)
            return

        self.sentences = sentences
        self.current_index = current_idx
        self.item_widgets = []
        
        # 清空列表
        self.list_widget.clear()
        
        # 添加所有句子到列表
        for i, text in enumerate(sentences):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, i)  # 存储句子索引
            item.setSizeHint(QSize(0, 50))
            self.list_widget.addItem(item)
            
            label = MarqueeLabel(text)
            label.setFont(self.current_font)
            label.setContentsMargins(10, 0, 10, 0)
            self.list_widget.setItemWidget(item, label)
            self.item_widgets.append(label)
        
        # 高亮当前句子
        self._highlight_current_item()
        
        # 滚动到当前句子
        if 0 <= current_idx < self.list_widget.count():
            self.list_widget.setCurrentRow(current_idx)
            self.list_widget.scrollToItem(self.list_widget.item(current_idx), 
                                          QAbstractItemView.PositionAtCenter)
    
    def _highlight_current_item(self):
        """高亮当前选中的句子"""
        for index, label in enumerate(self.item_widgets):
            label.set_highlighted(index == self.current_index)

        if 0 <= self.current_index < self.list_widget.count():
            self.list_widget.setCurrentRow(self.current_index)
        else:
            self.list_widget.setCurrentRow(-1)
    
    def set_current_index(self, index: int):
        """设置当前句子索引"""
        self.current_index = index
        self._highlight_current_item()
        if 0 <= index < self.list_widget.count():
            self.list_widget.setCurrentRow(index)
            self.list_widget.scrollToItem(self.list_widget.item(index),
                                          QAbstractItemView.PositionAtCenter)
    
    def set_font(self, font):
        """设置字体"""
        self.current_font = font
        self.list_widget.setFont(font)
        for label in self.item_widgets:
            label.setFont(font)


# =============================================================================
# 选项卡内容组件 - 停顿与参数
# =============================================================================
class PauseParamWidget(QWidget):
    """停顿与参数选项卡内容"""

    PAUSE_GRID_COLUMNS = 6
    
    pause_settings_changed = pyqtSignal(set)  # 停顿设置改变信号
    speed_changed = pyqtSignal(int)  # 语速改变信号
    volume_changed = pyqtSignal(int)  # 音量改变信号
    punctuation_hint_changed = pyqtSignal(bool)  # 标点提示开关改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pause_buttons = {}
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 停顿设置区域
        pause_container = StyledContainer()
        pause_layout = QVBoxLayout(pause_container)
        pause_layout.setContentsMargins(10, 10, 10, 10)
        
        self.pause_title = QLabel("停顿设置")
        self.pause_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        pause_layout.addWidget(self.pause_title)
        
        # 标点符号按钮网格
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)
        
        # 符号定义：(名称, 显示符号) - 与 SentenceSplitter.PAUSE_MARKS 保持一致
        marks = [
            ('逗号', '，'), ('句号', '。'), ('叹号', '！'), ('问号', '？'),
            ('分号', '；'), ('冒号', '：'), ('省略号', '……'), ('左括号', '（'),
            ('右括号', '）'), ('斜杠', '/'), ('反斜杠', '\\'), ('波浪线', '~'),
            ('句点', '.'), ('英文逗号', ','), ('英文叹号', '!'), ('英文问号', '?'),
            ('英文分号', ';'), ('英文冒号', ':'), ('英文左括号', '('), ('英文右括号', ')'),
            ('换行', '↵'), ('', ''), ('', ''), ('', '')
        ]
        
        for i, (name, symbol) in enumerate(marks):
            if name:
                btn = QPushButton(symbol)
                configure_semantic_surface(btn, preserve_text_color=True)
                btn.setCheckable(True)
                btn.setChecked(True)
                btn.setMinimumSize(40, 40)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        border: 1px solid #D0D0D0;
                        border-radius: 4px;
                        font-size: 14px;
                    }
                    QPushButton:checked {
                        background-color: rgb(85, 85, 255);
                        color: white;
                    }
                """)
                btn.clicked.connect(lambda checked, n=name: self._on_pause_toggled(n, checked))
                self.pause_buttons[name] = btn
                grid_layout.addWidget(
                    btn,
                    i // self.PAUSE_GRID_COLUMNS,
                    i % self.PAUSE_GRID_COLUMNS,
                )
        
        pause_layout.addLayout(grid_layout)
        
        # 标点提示开关
        hint_layout = QHBoxLayout()
        hint_layout.setContentsMargins(0, 5, 0, 0)
        self.punctuation_hint_checkbox = QCheckBox("启用标点提示")
        self.punctuation_hint_checkbox.setChecked(True)
        self.punctuation_hint_checkbox.setStyleSheet("""
            QCheckBox {
                border: none;
                background: transparent;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: rgb(85, 85, 255);
                border: 1px solid rgb(85, 85, 255);
            }
            QCheckBox::indicator:checked::after {
                content: "✓";
                color: white;
            }
        """)
        self.punctuation_hint_checkbox.stateChanged.connect(self._on_punctuation_hint_toggled)
        hint_layout.addWidget(self.punctuation_hint_checkbox)
        hint_layout.addStretch()
        pause_layout.addLayout(hint_layout)
        
        layout.addWidget(pause_container)
        
        # 生成参数设置区域。内容层与提示层分离，禁用时仅模糊控件。
        param_container = StyledContainer()
        param_layout = QVBoxLayout(param_container)
        param_layout.setContentsMargins(10, 10, 10, 10)
        
        self.param_title = QLabel("生成参数设置")
        self.param_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        param_layout.addWidget(self.param_title)
        
        # 语速滑动条
        speed_layout = QHBoxLayout()
        self.speed_label = QLabel("语速:")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(-50, 50)
        self.speed_slider.setValue(0)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.speed_slider.setStyleSheet(self._get_slider_style())
        self.speed_value_label = QLabel("0%")
        self.speed_value_label.setMinimumWidth(40)
        
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_value_label)
        param_layout.addLayout(speed_layout)
        
        # 生成音量滑动条（控制生成音频的音量）
        volume_layout = QHBoxLayout()
        self.volume_label = QLabel("音量:")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_slider.setStyleSheet(self._get_slider_style())
        self.volume_value_label = QLabel("100%")
        self.volume_value_label.setMinimumWidth(40)
        
        volume_layout.addWidget(self.volume_label)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_value_label)
        param_layout.addLayout(volume_layout)

        layout.addWidget(param_container)
        layout.addStretch()
    
    def _get_slider_style(self):
        """获取滑动条样式"""
        return """
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                background: #E0E0E0;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90E2;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
                border: 2px solid #4A90E2;
            }
            QSlider::handle:horizontal:hover {
                background: #F0F8FF;
                border: 2px solid #357ABD;
            }
        """
    
    def _on_pause_toggled(self, name, checked):
        """处理停顿按钮切换"""
        enabled = set()
        for n, btn in self.pause_buttons.items():
            if btn.isChecked():
                enabled.add(n)
        self.pause_settings_changed.emit(enabled)
    
    def _on_punctuation_hint_toggled(self, state):
        """处理标点提示开关切换"""
        enabled = (state == Qt.Checked)
        self.punctuation_hint_changed.emit(enabled)
    
    def _on_speed_changed(self, value):
        """处理语速改变"""
        self.speed_value_label.setText(f"{value}%")
        self.speed_changed.emit(value)
    
    def _on_volume_changed(self, value):
        """处理音量改变"""
        self.volume_value_label.setText(f"{value}%")
        self.volume_changed.emit(value)
    
    def get_enabled_pauses(self):
        """获取启用的停顿符号"""
        enabled = set()
        for name, btn in self.pause_buttons.items():
            if btn.isChecked():
                enabled.add(name)
        return enabled
    
    def set_speed(self, value):
        """设置语速值"""
        self.speed_slider.setValue(value)
    
    def set_volume(self, value):
        """设置音量值"""
        self.volume_slider.setValue(value)

    def set_font(self, font):
        """设置字体"""
        self.pause_title.setFont(font)
        self.param_title.setFont(font)
        self.speed_label.setFont(font)
        self.speed_value_label.setFont(font)
        self.volume_label.setFont(font)
        self.volume_value_label.setFont(font)
        self.punctuation_hint_checkbox.setFont(font)
        for btn in self.pause_buttons.values():
            btn.setFont(font)


# =============================================================================
# 选项卡内容组件 - 音色列表
# =============================================================================
class VoiceListWidget(QWidget):
    """音色列表选项卡内容"""
    
    voice_selected = pyqtSignal(str)  # 音色选择信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_container(self)
        self.voice_buttons = []
        self.selected_voice = None
        self.current_model = None  # 当前模型
        self.settings_manager = SettingsManager()  # 添加设置管理器
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll = QScrollArea()
        configure_transparent_container(scroll)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._get_scrollbar_style())
        scroll.setFrameShape(QFrame.NoFrame)
        
        # 创建内容容器
        self.content_widget = QWidget()
        configure_transparent_container(self.content_widget)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(Qt.AlignTop)
        
        set_transparent_scroll_content(scroll, self.content_widget)
        layout.addWidget(scroll)
    
    def _get_scrollbar_style(self):
        """获取滚动条样式"""
        return """
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #F5F5F5;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #C0C0C0;
                min-height: 30px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #A0A0A0;
            }
            QScrollBar::handle:vertical:pressed {
                background: #808080;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """
    
    def load_voices(
        self,
        model: str = "Microsoft/edge-tts",
        auto_select_default: bool = True,
        force_refresh: bool = False,
    ):
        """从voicelist.txt或TTSRouter加载音色列表

        Args:
            model: 模型名称
            auto_select_default: 是否自动选中默认音色
        """
        # 选项卡激活会反复触发刷新请求。模型和按钮都未变化时直接复用
        # 当前控件，避免在 GUI 线程中重复读文件、解析样式并重建布局。
        if not force_refresh and self.current_model == model and self.voice_buttons:
            return

        previous_voice = self.selected_voice if self.current_model == model else None
        self.current_model = model
        self.selected_voice = None
        voices = []

        # 使用 get_app_base_path 避免读取到 PyInstaller 的 MEI 临时目录
        from misc_func import get_app_base_path
        voicelist_path = os.path.join(get_app_base_path(), 'cache', 'voicelist.txt')

        try:
            if os.path.exists(voicelist_path):
                with open(voicelist_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                voice_data = json.loads(line)
                                if voice_data.get('belongingModel') == model:
                                    voices.append(voice_data)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"加载音色列表失败: {e}", fold_code="GEN_VOICE")

        # 内置模型的音色已由本地缓存提供，不需要在每次切换选项卡时
        # 初始化/查询 TTS 路由器；未知提供商仍交给插件引擎处理，即使
        # 本地文件里碰巧残留了同名音色。
        model_provider = model.split("/", 1)[0]
        builtin_providers = {
            "Microsoft", "ChatGLM", "Qwen", "KIMI", "Minimax", "Mimo"
        }
        if model_provider not in builtin_providers:
            try:
                from tts_router import get_tts_router
                router = get_tts_router()
                provider = router.get_selected_provider()
                if provider and provider.startswith("plugin:"):
                    engine_id = provider[7:]
                    engine_voices = router.get_voices(engine_id, use_cache=not force_refresh)
                    voices = [{
                        "voiceID": vi.voice_id,
                        "voiceName": vi.voice_name,
                        "belongingModel": model,
                        "language": vi.language,
                    } for vi in engine_voices]
            except Exception as e:
                debug_logger.output("generation_page_neo.py", LogLevel.ERROR,
                    f"获取插件TTS音色失败: {e}", fold_code="GEN_VOICE")
        
        self._create_voice_buttons(voices)
        if auto_select_default and voices:
            default_voice = self._load_default_voice_for_model(model)
            valid_voice_ids = {voice.get("voiceID", "") for voice in voices}
            if previous_voice in valid_voice_ids:
                self.select_voice(previous_voice)
            elif default_voice in valid_voice_ids:
                self.select_voice(default_voice)
            else:
                first_id = voices[0].get("voiceID", "")
                if first_id:
                    self.select_voice(first_id)

    def _load_default_voice_for_model(self, model: str):
        """从设置读取该模型的默认音色（与设置页 EdgeTTS 默认音色配置一致）。"""
        provider_mapping = {
            "Microsoft": "MS",
            "ChatGLM": "ChatGLM",
            "Qwen": "Qwen",
            "KIMI": "KIMI",
            "Minimax": "Minimax",
            "Mimo": "Mimo",
        }
        try:
            parts = model.split("/")
            if len(parts) >= 2:
                provider_id = provider_mapping.get(parts[0], parts[0])
                model_name = parts[1]
                key = f"default_voice_{provider_id}_{model_name}"
                return self.settings_manager.Custom.get_value(key, None) or None
        except Exception:
            pass
        return None
    
    def _create_voice_buttons(self, voices):
        """创建音色按钮"""
        # 清除旧按钮和旧的 stretch，避免反复刷新后布局累积空白项。
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.voice_buttons.clear()

        if not voices:
            empty_title = QLabel("当前模型暂无可用音色")
            empty_title.setAlignment(Qt.AlignCenter)
            empty_title.setStyleSheet(
                "color: #555; font-size: 15px; font-weight: bold; "
                "border: none; background: transparent; padding-top: 24px;"
            )
            self.content_layout.addWidget(empty_title)

            self.content_layout.addStretch()
            return
        
        # 创建新按钮
        for voice_data in voices:
            voice_id = voice_data.get('voiceID', '')
            voice_name = voice_data.get('voiceName', voice_id)
            
            btn = QPushButton(f"{voice_name} ({voice_id})")
            btn.setProperty("voice_id", voice_id)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    border: 1px solid #D0D0D0;
                    border-radius: 4px;
                    padding: 10px;
                    text-align: left;
                }
                QPushButton:checked {
                    background-color: rgb(0, 255, 0);
                    color: black;
                }
                QPushButton:hover {
                    background-color: #F0F0F0;
                }
            """)
            btn.clicked.connect(lambda checked, v=voice_id: self._on_voice_clicked(v))
            self.voice_buttons.append(btn)
            self.content_layout.addWidget(btn)
        
        # 添加弹性空间
        self.content_layout.addStretch()

    def _on_voice_clicked(self, voice_id):
        """处理音色按钮点击"""
        self.selected_voice = voice_id
        
        # 更新按钮状态
        for btn in self.voice_buttons:
            btn.setChecked(False)
        
        sender = self.sender()
        if sender:
            sender.setChecked(True)
        
        self.voice_selected.emit(voice_id)
    
    def select_voice(self, voice_id: str):
        """选中指定音色"""
        self.selected_voice = voice_id
        for i, btn in enumerate(self.voice_buttons):
            if voice_id in btn.text():
                btn.setChecked(True)
            else:
                btn.setChecked(False)
        self.voice_selected.emit(voice_id)
    
    def set_font(self, font):
        """设置字体"""
        for btn in self.voice_buttons:
            btn.setFont(font)


# =============================================================================
# 导入对话框包装类
# =============================================================================
class ImportButtonHandler:
    """导入按钮处理器 - 直接执行导入功能，跳过 iw_ 对话框中转"""
    
    def __init__(self, parent_page):
        self.parent_page = parent_page
        self.ocr_worker = None
        self.loading_dialog = None
        self.current_ocr_queue = []
        self.processed_count = 0
        self.failed_count = 0
    
    def clear_text(self):
        """清空文本"""
        if hasattr(self.parent_page, 'text_edit'):
            from iw_dialogs import ClearConfirmationDialog
            dialog = ClearConfirmationDialog(self.parent_page)
            if dialog.exec_() == QDialog.Accepted and dialog.result:
                self.parent_page.text_edit.clear()
    
    def import_from_doc(self):
        """从文档导入 - 直接打开文件选择器"""
        from docxfix import Document
        
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent_page, "选择文档", "",
            "文本文件 (*.txt);;Word文档 (*.docx);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.lower().endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif file_path.lower().endswith('.docx'):
                doc = Document(file_path)
                content = '\n'.join([p.text for p in doc.paragraphs])
            else:
                # 尝试作为文本文件读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            if content and hasattr(self.parent_page, 'text_edit'):
                self.parent_page.text_edit.setPlainText(content)
                if hasattr(self.parent_page, '_update_content'):
                    self.parent_page._update_content()
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"从文档导入成功: {len(content)} 字符", fold_code="GEN_IMPORT")
        except Exception as e:
            QMessageBox.critical(self.parent_page, "错误", f"读取失败: {str(e)}")
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"文档导入失败: {e}", fold_code="GEN_IMPORT")
    
    def import_from_image(self):
        """从图片导入 - 直接选择图片并进行OCR"""
        from iw_dialogs import MultiImageImportDialog, LoadingDialog
        from ai_manager import get_ai_manager, AIRequest, AIScene
        from PyQt5.QtCore import QThread, pyqtSignal
        from PIL import Image
        import io
        import base64
        
        # 检查AI配置
        ai_manager = get_ai_manager()
        default_model = ai_manager.get_default_model(AIScene.VISION)
        if not default_model:
            configured = ai_manager.get_configured_providers(AIScene.VISION)
            if configured:
                QMessageBox.warning(self.parent_page, "提示", f"请在设置中配置 {configured[0]} API Key")
            else:
                QMessageBox.warning(self.parent_page, "提示", "请在设置中配置 AI API Key")
            return
        
        # 选择图片
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.parent_page, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        
        if not file_paths:
            return
        
        if len(file_paths) > 5:
            QMessageBox.warning(self.parent_page, "提示", "最多只能选择5张图片")
            return
        
        # 打开多图导入对话框（用于排序和添加备注）
        multi_dialog = MultiImageImportDialog(self.parent_page, file_paths)
        if multi_dialog.exec_() != QDialog.Accepted:
            return
        
        sorted_paths = multi_dialog.result_image_paths
        if not sorted_paths:
            QMessageBox.warning(self.parent_page, "提示", "没有选择图片进行导入。")
            return
        
        # 开始OCR处理
        self.current_ocr_queue = list(sorted_paths)
        self.processed_count = 0
        self.failed_count = 0
        
        self.loading_dialog = LoadingDialog(self.parent_page)
        self.loading_dialog.show()
        self._process_next_ocr_image()
    
    def _process_next_ocr_image(self):
        """处理OCR队列中的下一张图片"""
        from ai_manager import get_ai_manager, AIRequest, AIScene
        from PyQt5.QtCore import QThread, pyqtSignal
        from PIL import Image
        import io
        import base64
        
        if not self.current_ocr_queue:
            # 全部处理完成
            if self.loading_dialog:
                self.loading_dialog.close()
            
            total = self.processed_count + self.failed_count
            if self.failed_count > 0:
                QMessageBox.information(
                    self.parent_page, "完成",
                    f"OCR处理完成\n成功: {self.processed_count}/{total}\n失败: {self.failed_count}"
                )
            else:
                QMessageBox.information(self.parent_page, "完成", f"成功处理 {self.processed_count} 张图片")
            return
        
        image_path = self.current_ocr_queue.pop(0)
        
        # 创建OCR工作线程
        class OCRWorker(QThread):
            finished_signal = pyqtSignal(str)
            error_signal = pyqtSignal(str)
            
            def __init__(self, image_path):
                super().__init__()
                self.image_path = image_path
            
            def run(self):
                try:
                    ai_manager = get_ai_manager()
                    
                    # 预处理图片
                    with Image.open(self.image_path) as img:
                        max_side = 1560
                        if img.width > max_side or img.height > max_side:
                            img.thumbnail((max_side, max_side), Image.LANCZOS)
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=80, optimize=True)
                        img_bytes = buffer.getvalue()
                        base64_image = base64.b64encode(img_bytes).decode('utf-8')
                    
                    request = AIRequest(
                        prompt="请识别图片中的文字内容，只返回识别到的文字，不要添加任何解释。",
                        scene=AIScene.VISION,
                        image_base64=base64_image
                    )
                    
                    response = ai_manager.chat(request)
                    
                    if response.success:
                        self.finished_signal.emit(response.text)
                    else:
                        raise Exception(response.error or "识别失败")
                        
                except Exception as e:
                    self.error_signal.emit(str(e))
        
        self.ocr_worker = OCRWorker(image_path)
        self.ocr_worker.finished_signal.connect(lambda text: self._on_ocr_success(text))
        self.ocr_worker.error_signal.connect(lambda err: self._on_ocr_error(err))
        self.ocr_worker.start()
    
    def _on_ocr_success(self, text):
        """OCR成功回调"""
        self.processed_count += 1
        if hasattr(self.parent_page, 'text_edit'):
            current = self.parent_page.text_edit.toPlainText()
            if current:
                new_text = current + "\n\n" + text
            else:
                new_text = text
            self.parent_page.text_edit.setPlainText(new_text)
            if hasattr(self.parent_page, '_update_content'):
                self.parent_page._update_content()
        self._process_next_ocr_image()
    
    def _on_ocr_error(self, error):
        """OCR失败回调"""
        self.failed_count += 1
        debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"OCR失败: {error}", fold_code="GEN_IMPORT")
        self._process_next_ocr_image()
    
    def import_online(self):
        """在线导入 - 直接打开在线导入对话框"""
        from iw_online_import import OnlineImportDialog
        
        # 传入 parent_window 而不是 self，以便对话框能访问 settings_manager
        parent_window = self.parent_page.parent_window if self.parent_page else None
        dialog = OnlineImportDialog(
            parent_window,
            parent_window.geometry() if parent_window else None
        )
        
        if dialog.exec_() == QDialog.Accepted and hasattr(dialog, 'result_text'):
            text = dialog.result_text
            if text and hasattr(self.parent_page, 'text_edit'):
                current = self.parent_page.text_edit.toPlainText()
                if current:
                    new_text = current + "\n\n" + text
                else:
                    new_text = text
                self.parent_page.text_edit.setPlainText(new_text)
                if hasattr(self.parent_page, '_update_content'):
                    self.parent_page._update_content()
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"在线导入成功: {len(text)} 字符", fold_code="GEN_IMPORT")


# =============================================================================
# 自动连播间隔调节悬浮窗
# =============================================================================
class AutoPlayIntervalPopup(QFrame):
    """自动连播间隔调节悬浮窗，支持输入框和滑条联动"""

    value_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        configure_independent_surface(self)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet("background: transparent;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)

        container = QFrame()
        container.setObjectName("popupContainer")
        container.setStyleSheet("""
            QFrame#popupContainer {
                background-color: #FFFFFF;
                border: 1px solid #D8D8D8;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("border: none; background: transparent; color: #555;")

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setDecimals(1)
        self.spinbox.setFixedWidth(72)
        self.spinbox.setAlignment(Qt.AlignCenter)
        self.spinbox.setStyleSheet("""
            QDoubleSpinBox {
                border: 1px solid #D0D0D0;
                border-radius: 5px;
                padding: 4px 0;
                background: #FFFFFF;
                color: #333;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #4A90E2;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 0;
                border: none;
            }
        """)

        top_row.addWidget(self.title_label)
        top_row.addStretch()
        top_row.addWidget(self.spinbox)
        layout.addLayout(top_row)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setFixedHeight(26)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #E8E8E8;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90E2;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
                border: 2px solid #4A90E2;
            }
            QSlider::handle:horizontal:hover {
                background: #F5F8FF;
                border: 2px solid #357ABD;
            }
        """)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)

        layout.addWidget(self.slider)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self.setFixedWidth(280)

    def configure(self, current_value, min_val, max_val, step, title, font):
        """配置数值范围和样式，准备显示"""
        self.title_label.setText(title)
        self.title_label.setFont(font)
        self.spinbox.setFont(font)
        self.spinbox.blockSignals(True)
        self.spinbox.setRange(min_val, max_val)
        self.spinbox.setSingleStep(step)
        self.spinbox.setValue(current_value)
        self.spinbox.blockSignals(False)
        int_min = int(min_val * 10)
        int_max = int(max_val * 10)
        self.slider.blockSignals(True)
        self.slider.setRange(int_min, int_max)
        self.slider.setValue(int(current_value * 10))
        self.slider.blockSignals(False)
        self.adjustSize()

    def show_at(self, px, py):
        """在全局坐标 (px, py) 处显示"""
        self.move(px, py)
        self.show()
        self.raise_()
        QApplication.instance().installEventFilter(self)
        if self.parent() and isinstance(self.parent(), QWidget):
            self.parent().installEventFilter(self)

    def _on_spinbox_changed(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(int(value * 10))
        self.slider.blockSignals(False)
        self.value_changed.emit(value)

    def _on_slider_changed(self, value):
        real_val = value / 10.0
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(real_val)
        self.spinbox.blockSignals(False)
        self.value_changed.emit(real_val)

    def eventFilter(self, obj, event):
        if not self.isVisible():
            return False
        if event.type() == QEvent.MouseButtonPress:
            if not self.rect().contains(self.mapFromGlobal(event.globalPos())):
                self.hide()
        elif event.type() == QEvent.Move and obj is self.parent():
            self.hide()
        return False

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        if self.parent() and isinstance(self.parent(), QWidget):
            try:
                self.parent().removeEventFilter(self)
            except RuntimeError:
                pass
        super().hideEvent(event)


# =============================================================================
# 主页面类 - 生成页面
# =============================================================================
class GenerationPage(QWidget):
    """生成页面（听写页面）- 新设计"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_root(self)
        self.parent_window = parent
        self.config = parent.config if parent else AudioConfig()
        self.signals = GenerationSignals()
        
        # 保护机制：页面销毁时标记 _destroyed = True
        # 防止后台生成线程 emit 信号到已销毁的 QObject 导致 C++ crash
        self._destroyed = False
        self.destroyed.connect(lambda: setattr(self, '_destroyed', True))
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "初始化 GenerationPage...", fold_code="GEN_INIT")
        
        # 获取共享内存管理器
        self.shared_manager = get_shared_memory_manager()
        
        # 获取设置管理器
        from misc_func import SettingsManager
        self.settings_manager = parent.settings_manager if parent and hasattr(parent, 'settings_manager') else SettingsManager()
        
        # 初始化颜色
        if parent:
            self.text_color = parent.settings_manager.get_Custom_value('text_color', '#333333')
            self.background_color = parent.settings_manager.get_Custom_value('background_color', '#E5E8EF')
            self.global_font = parent.settings_manager.get_Custom_value('global_font', '微软雅黑')
        else:
            self.text_color = '#333333'
            self.background_color = '#E5E8EF'
            self.global_font = '微软雅黑'
        
        # 初始化核心组件
        self.sentence_splitter = SentenceSplitter()
        self.sentence_manager = SentenceAudioManager()
        self.import_handler = ImportButtonHandler(self)
        
        # 从设置中加载默认配置
        self._load_default_settings()
        
        # 当前文本
        self.current_text = ""
        
        # Key Button 状态管理
        # 状态: "generate" - 生成音频, "generating" - 生成中, "next_sentence" - 下一句
        self.key_button_state = "generate"
        self.all_sentences_played = False  # 标记是否所有句子都已播放完毕
        self._pending_playback_index = None
        self._has_started_sentence_playback = False
        self._tts_error_emitted = False

        # 自动连播
        self.auto_play_enabled = True
        self.auto_play_interval_mode = 'fixed'
        self.auto_play_interval_fixed = 1.0
        self.auto_play_interval_dynamic = 1.0
        self.auto_play_timer = QTimer(self)
        self.auto_play_timer.setSingleShot(True)
        self.auto_play_timer.timeout.connect(self._on_auto_play_timeout)
        
        self._init_ui()
        self._connect_signals()
        self._connect_shared_memory_signals()
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "GenerationPage 初始化完成", fold_code="GEN_INIT")
    
    def _init_ui(self):
        """初始化UI"""
        # 设置背景色
        self.setStyleSheet(f"GenerationPage {{ background-color: {self.background_color}; }}")
        
        # 创建主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建左侧面板
        self.left_panel = self._create_left_panel()
        main_layout.addWidget(self.left_panel, 3)
        
        # 创建右侧面板
        self.right_panel = self._create_right_panel()
        main_layout.addWidget(self.right_panel, 2)
        
        # 创建底部控制栏
        self.bottom_bar = self._create_bottom_bar()
        
        # 使用垂直布局包装
        container = QVBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(15)
        
        # 添加主内容区域（左右布局）
        content_widget = QWidget()
        configure_transparent_container(content_widget)
        content_widget.setLayout(main_layout)
        container.addWidget(content_widget, 1)
        
        # 添加底部控制栏
        container.addWidget(self.bottom_bar)
        
        self.setLayout(container)
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = StyledContainer()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 文本编辑区
        self.text_edit = QTextEdit()
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: black;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        self.text_edit.textChanged.connect(self._update_content)
        layout.addWidget(self.text_edit, 1)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 四个导入按钮（不同宽度）
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setMinimumWidth(60)
        self.clear_btn.clicked.connect(self.import_handler.clear_text)
        
        self.doc_btn = QPushButton("从文档导入")
        self.doc_btn.setMinimumWidth(100)
        self.doc_btn.clicked.connect(self.import_handler.import_from_doc)
        
        self.img_btn = QPushButton("从图片导入")
        self.img_btn.setMinimumWidth(100)
        self.img_btn.clicked.connect(self.import_handler.import_from_image)
        
        self.online_btn = QPushButton("在线导入")
        self.online_btn.setMinimumWidth(90)
        self.online_btn.clicked.connect(self.import_handler.import_online)
        
        # 设置按钮样式
        for btn in [self.clear_btn, self.doc_btn, self.img_btn, self.online_btn]:
            btn.setStyleSheet(self._get_import_button_style())
        
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.doc_btn)
        button_layout.addWidget(self.img_btn)
        button_layout.addWidget(self.online_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return panel
    
    def _get_import_button_style(self):
        """获取导入按钮样式"""
        return f"""
            QPushButton {{
                font-family: "{self.global_font}";
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: #F0F0F0;
            }}
        """
    
    def _create_right_panel(self):
        """创建右侧面板"""
        panel = StyledContainer()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 选项卡按钮区域
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(8)
        
        self.tab_sentence_btn = SmoothButton("分句列表", "tab")
        self.tab_pause_btn = SmoothButton("停顿与参数", "tab")
        self.tab_voice_btn = SmoothButton("音色列表", "tab")
        
        self.tab_sentence_btn.setChecked(True)
        
        # 连接选项卡切换信号
        self.tab_sentence_btn.clicked.connect(lambda: self._switch_tab(0))
        self.tab_pause_btn.clicked.connect(lambda: self._switch_tab(1))
        self.tab_voice_btn.clicked.connect(lambda: self._switch_tab(2))
        
        tab_layout.addWidget(self.tab_sentence_btn)
        tab_layout.addWidget(self.tab_pause_btn)
        tab_layout.addWidget(self.tab_voice_btn)
        
        layout.addLayout(tab_layout)
        
        # 选项卡内容区域（带渐隐渐显动画）
        self.tab_content = QFrame()
        configure_transparent_container(self.tab_content)
        self.tab_content.setStyleSheet("QFrame { border: none; background: transparent; }")
        tab_content_layout = QVBoxLayout(self.tab_content)
        tab_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建堆叠部件
        self.stacked_widget = QStackedWidget()
        configure_transparent_container(self.stacked_widget)
        
        # 创建三个选项卡内容
        self.sentence_list_widget = SentenceListWidget(self)
        self.sentence_list_widget.sentence_clicked.connect(self._on_sentence_clicked_in_list)
        
        self.pause_param_widget = PauseParamWidget(self)
        self.pause_param_widget.pause_settings_changed.connect(self._on_pause_settings_changed)
        self.pause_param_widget.speed_changed.connect(self._on_speed_changed)
        self.pause_param_widget.volume_changed.connect(self._on_gen_volume_changed)
        self.pause_param_widget.punctuation_hint_changed.connect(self._on_punctuation_hint_changed)
        
        self.voice_list_widget = VoiceListWidget(self)
        self.voice_list_widget.voice_selected.connect(self._on_voice_selected)
        
        # 读取用户配置的TTS模型
        settings_manager = SettingsManager()
        tts_provider = settings_manager.Custom.get_value("ai_model_tts_provider", "MS")
        tts_model = settings_manager.Custom.get_value("ai_model_tts_model", "edge-tts")
        # 提供商ID到模型格式名称的映射
        provider_mapping = {
            "MS": "Microsoft",
            "ChatGLM": "ChatGLM",
            "Qwen": "Qwen",
            "KIMI": "KIMI",
            "Minimax": "Minimax",
            "Mimo": "Mimo",
        }
        
        # 构建模型格式字符串
        provider_name = provider_mapping.get(tts_provider, tts_provider)
        model_string = f"{provider_name}/{tts_model}"
        
        # 记录日志
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                           f"加载TTS模型: provider={tts_provider}, model={tts_model}, formatted={model_string}", 
                           fold_code="GEN_INIT")
        
        # 传递模型参数
        self.voice_list_widget.load_voices(model=model_string)  # 加载音色列表
        
        # 添加到堆叠部件
        self.stacked_widget.addWidget(self.sentence_list_widget)
        self.stacked_widget.addWidget(self.pause_param_widget)
        self.stacked_widget.addWidget(self.voice_list_widget)
        
        # 添加渐隐渐显动画效果
        self.stacked_opacity = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.stacked_opacity)
        self.stacked_opacity.setOpacity(1.0)
        
        self.fade_animation = QPropertyAnimation(self.stacked_opacity, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_animation.finished.connect(self._on_fade_finished)
        
        tab_content_layout.addWidget(self.stacked_widget)
        layout.addWidget(self.tab_content, 1)
        
        # 上一句/下一句按钮区域（位于Key Button上方）
        self.nav_widget = QWidget()
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)
        
        self.tab_prev_btn = QPushButton("上一句")
        self.tab_prev_btn.setMinimumHeight(35)
        self.tab_prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2868A8;
            }
        """)
        self.tab_prev_btn.clicked.connect(self._play_prev_sentence)
        
        self.tab_next_btn = QPushButton("重新分句")
        self.tab_next_btn.setMinimumHeight(35)
        self.tab_next_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2868A8;
            }
        """)
        self.tab_next_btn.clicked.connect(self._resplit_sentences)
        
        nav_layout.addWidget(self.tab_prev_btn)
        nav_layout.addWidget(self.tab_next_btn)
        
        # 为nav_widget添加透明度效果和动画
        
        self.nav_opacity = QGraphicsOpacityEffect(self.nav_widget)
        self.nav_widget.setGraphicsEffect(self.nav_opacity)
        self.nav_opacity.setOpacity(0.0)
        
        self.nav_pos_anim = QPropertyAnimation(self.nav_widget, b"pos")
        self.nav_pos_anim.setDuration(300)
        self.nav_pos_anim.setEasingCurve(QEasingCurve.OutQuad)
        
        self.nav_op_anim = QPropertyAnimation(self.nav_opacity, b"opacity")
        self.nav_op_anim.setDuration(300)
        self.nav_op_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.nav_anim_group = QParallelAnimationGroup()
        self.nav_anim_group.addAnimation(self.nav_pos_anim)
        self.nav_anim_group.addAnimation(self.nav_op_anim)
        
        self.nav_widget.hide()  # 初始隐藏
        layout.addWidget(self.nav_widget)
        
        # Key Button（关键按钮）- 生成音频
        # 注：此按钮功能多样，后续可能扩展为多种操作，故称为Key Button
        self.generate_btn = QPushButton("生成音频")
        configure_semantic_surface(
            self.generate_btn,
            preserve_text_color=True,
        )
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E8B57;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27774A;
            }
            QPushButton:pressed {
                background-color: #1E5C39;
            }
        """)
        self.generate_btn.clicked.connect(self._generate_preview_audio)
        layout.addWidget(self.generate_btn)

        self.converting_label = QLabel("转换中")
        configure_semantic_surface(self.converting_label)
        self.converting_label.setAlignment(Qt.AlignCenter)
        self.converting_label.setStyleSheet("""
            QLabel {
                color: #2E8B57;
                background-color: rgba(46, 139, 87, 20);
                border: 1px solid rgba(46, 139, 87, 70);
                border-radius: 7px;
                padding: 7px 12px;
                font-weight: bold;
            }
        """)
        self.converting_label.hide()
        layout.addWidget(self.converting_label)
        self._converting_frame = 0
        self._converting_timer = QTimer(self)
        self._converting_timer.setInterval(350)
        self._converting_timer.timeout.connect(self._advance_converting_animation)
        
        return panel
    
    def _switch_tab(self, index):
        """切换选项卡（带动画）"""
        # 更新按钮状态
        self.tab_sentence_btn.setChecked(index == 0)
        self.tab_pause_btn.setChecked(index == 1)
        self.tab_voice_btn.setChecked(index == 2)
        
        # 如果当前已经是目标选项卡，不执行动画
        if self.stacked_widget.currentIndex() == index:
            return
        
        # 保存目标索引
        self.target_tab_index = index
        
        # 开始淡出动画
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()
    
    def _on_fade_finished(self):
        """淡出动画完成"""
        if self.stacked_opacity.opacity() == 0.0:
            # 切换到目标选项卡
            self.stacked_widget.setCurrentIndex(self.target_tab_index)
            # 开始淡入动画
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.start()
    
    def _create_bottom_bar(self):
        """创建底部控制栏"""
        bar = StyledContainer()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # 结束听写按钮（支持长按）
        self.end_dictation_btn = LongPressButton("结束听写")
        self.end_dictation_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        self.end_dictation_btn.clicked.connect(self._end_dictation)
        self.end_dictation_btn.long_pressed.connect(self._end_dictation_with_clear_text)
        layout.addWidget(self.end_dictation_btn)
        
        # 进度条（不允许拖动）
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)  # 不允许拖动
        self.progress_slider.setStyleSheet(self._get_progress_style())
        layout.addWidget(self.progress_slider, 1)
        
        # 播放控制按钮组
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(40, 40)
        self.prev_btn.setStyleSheet(self._get_control_button_style())
        self.prev_btn.clicked.connect(self._play_prev_sentence)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(40, 40)
        self.next_btn.setStyleSheet(self._get_control_button_style())
        self.next_btn.clicked.connect(self._play_next_sentence)
        
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.next_btn)
        
        layout.addLayout(control_layout)
        
        # 音量控制（播放音量）
        volume_layout = QHBoxLayout()
        self.play_volume_label = QLabel("音量")
        self.play_volume_slider = QSlider(Qt.Horizontal)
        self.play_volume_slider.setRange(0, 100)
        self.play_volume_slider.setValue(100)
        self.play_volume_slider.setMaximumWidth(100)
        self.play_volume_slider.valueChanged.connect(self._on_play_volume_changed)
        self.play_volume_slider.setStyleSheet(self._get_slider_style())
        self.volume_value_label = QLabel("100%")
        
        volume_layout.addWidget(self.play_volume_label)
        volume_layout.addWidget(self.play_volume_slider)
        volume_layout.addWidget(self.volume_value_label)
        
        layout.addLayout(volume_layout)
        
        # 自动连播按钮
        self.auto_play_btn = LongPressButton("连播")
        self.auto_play_btn.long_press_duration = 500
        self.auto_play_btn.setFixedHeight(36)
        self.auto_play_btn.setMinimumWidth(60)
        self.auto_play_btn.clicked.connect(self._toggle_auto_play)
        self.auto_play_btn.long_pressed.connect(self._on_auto_play_long_press)
        self._update_auto_play_button_style()
        layout.addWidget(self.auto_play_btn)
        
        return bar
    
    def _get_control_button_style(self):
        """获取控制按钮样式"""
        return """
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2868A8;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
            }
        """
    
    def _get_slider_style(self):
        """获取滑动条样式"""
        return """
            QSlider::groove:horizontal {
                background: #E0E0E0;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90E2;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
                border: 2px solid #4A90E2;
            }
        """
    
    def _get_progress_style(self):
        """获取进度条样式"""
        return """
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                background: #E0E0E0;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #4A90E2;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4A90E2;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
        """

    def _get_auto_play_button_style(self):
        """获取自动连播按钮样式"""
        if self.auto_play_enabled:
            return """
                QPushButton {
                    background-color: #2E8B57;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #27774A;
                }
                QPushButton:pressed {
                    background-color: #1E5C39;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #FFFFFF;
                    color: #888888;
                    border: 1px solid #D0D0D0;
                    border-radius: 5px;
                    padding: 8px 10px;
                }
                QPushButton:hover {
                    background-color: #F0F0F0;
                }
            """

    def _update_auto_play_button_style(self):
        """更新自动连播按钮样式"""
        self.auto_play_btn.setStyleSheet(self._get_auto_play_button_style())

    def _toggle_auto_play(self):
        """切换自动连播开关"""
        self.auto_play_enabled = not self.auto_play_enabled
        self._update_auto_play_button_style()
        if not self.auto_play_enabled:
            self._stop_auto_play_timer()
        self.settings_manager.Custom.set_value('auto_play_enabled', str(self.auto_play_enabled))

    def _on_auto_play_long_press(self):
        """长按自动连播按钮 - 悬浮窗调节间隔时长"""
        if self.auto_play_interval_mode == 'dynamic':
            current = self.auto_play_interval_dynamic
            min_val, max_val, step = 0.1, 5.0, 0.1
            title = "连播倍率"
            attr = 'auto_play_interval_dynamic'
        else:
            current = self.auto_play_interval_fixed
            min_val, max_val, step = 0.1, 10.0, 0.1
            title = "连播间隔"
            attr = 'auto_play_interval_fixed'

        if not hasattr(self, '_auto_play_popup'):
            self._auto_play_popup = AutoPlayIntervalPopup(self.parent_window)
        popup = self._auto_play_popup

        try:
            popup.value_changed.disconnect()
        except TypeError:
            pass
        popup.value_changed.connect(lambda v: setattr(self, attr, v))
        popup.configure(current, min_val, max_val, step, title, QFont(self.global_font, 12))
        popup.adjustSize()

        btn = self.auto_play_btn
        gx = btn.mapToGlobal(QPoint(btn.width() // 2, 0)).x()
        gy = btn.mapToGlobal(QPoint(0, 0)).y()
        px = gx - popup.width() // 2
        py = gy - popup.height() - 4
        screen = QApplication.primaryScreen().geometry()
        if py < screen.top():
            py = btn.mapToGlobal(QPoint(0, btn.height())).y() + 4
        popup.show_at(px, py)

    def _start_auto_play_timer(self):
        """启动自动连播定时器"""
        if self.auto_play_interval_mode == 'dynamic':
            duration = self.sentence_manager.audio_durations.get(
                self.sentence_manager.current_sentence_index, 1.0
            )
            interval = duration * self.auto_play_interval_dynamic
        else:
            interval = self.auto_play_interval_fixed
        self.auto_play_timer.start(int(interval * 1000))

    def _stop_auto_play_timer(self):
        """停止自动连播定时器"""
        self.auto_play_timer.stop()

    def _on_auto_play_timeout(self):
        """自动连播定时器触发 - 播放下一个分句"""
        self._play_next_sentence()

    # =============================================================================
    # 信号连接
    # =============================================================================
    def _connect_signals(self):
        """连接内部信号"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "建立内部信号槽连接", fold_code="GEN_INIT")
        self.signals.generation_complete.connect(self._on_generation_complete_safe)
        self.signals.update_button_state.connect(self._update_button_state_safe)
        self.signals.sentence_generated.connect(self._on_sentence_generated)
        self.signals.all_sentences_complete.connect(self._on_all_sentences_complete)
        self.signals.playback_ready.connect(self._on_playback_ready)
        self.signals.tts_error.connect(self._on_tts_error)
        
        # 连接音频预览信号（延迟连接，因为 audio_preview 可能还未创建）
        if self.parent_window and hasattr(self.parent_window, 'audio_preview'):
            audio_preview = self.parent_window.audio_preview
            if audio_preview and hasattr(audio_preview, 'audio_signals') and audio_preview.audio_signals:
                audio_preview.audio_signals.next_sentence_requested.connect(self._on_hotkey_next_sentence)
                audio_preview.audio_signals.prev_sentence_requested.connect(self._on_hotkey_prev_sentence)
                debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "已连接音频预览热键信号", fold_code="GEN_INIT")
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "audio_preview 未完全初始化，将延迟连接热键信号", fold_code="GEN_INIT")
    
    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "建立共享内存信号连接", fold_code="GEN_INIT")
        if self.shared_manager:
            self.shared_manager.font_changed.connect(self._on_font_changed)
            self.shared_manager.theme_changed.connect(self._on_theme_changed)
            self.shared_manager.window_size_changed.connect(self._on_window_size_changed)
            self.shared_manager.settings_changed.connect(self._on_settings_changed_from_shared_memory)
    
    def connect_audio_preview_signals(self):
        """连接音频预览信号（由 main_window 在 audio_preview 创建后调用）"""
        if self.parent_window and hasattr(self.parent_window, 'audio_preview'):
            audio_preview = self.parent_window.audio_preview
            if audio_preview and hasattr(audio_preview, 'audio_signals') and audio_preview.audio_signals:
                try:
                    audio_preview.audio_signals.next_sentence_requested.connect(self._on_hotkey_next_sentence)
                    audio_preview.audio_signals.prev_sentence_requested.connect(self._on_hotkey_prev_sentence)
                    debug_logger.output("generation_page_neo.py", LogLevel.INFO, "延迟连接音频预览热键信号成功", fold_code="GEN_INIT")
                except Exception as e:
                    debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"连接音频预览信号失败: {e}", fold_code="GEN_INIT")
    
    # =============================================================================
    # 事件处理
    # =============================================================================
    def _update_content(self):
        """更新文本内容"""
        content = self.text_edit.toPlainText()
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"文本内容变更，新长度: {len(content)} 字符", fold_code="GEN_TEXT")
        self.config.content = content
        self.current_text = content
        
        # 用户修改文本后，Key Button 应回到"生成音频"状态
        if self.key_button_state != "generate":
            self._set_key_button_state("generate")
    
    def _on_pause_settings_changed(self, enabled_marks):
        """停顿设置改变"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"停顿设置变更: {enabled_marks}", fold_code="GEN_PAUSE")
        self.sentence_splitter.set_pause_marks(enabled_marks)
        # 重新分割文本
        if self.current_text:
            sentences = self.sentence_splitter.split_text(self.current_text)
            self.sentence_manager.set_sentences(sentences)
            self._pending_playback_index = None
            self._has_started_sentence_playback = False
            self._update_sentence_list()
    
    def _on_punctuation_hint_changed(self, enabled):
        """标点提示开关改变"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"标点提示开关变更: {enabled}", fold_code="GEN_PAUSE")
        self.sentence_splitter.set_punctuation_hint(enabled)
        # 重新分割文本
        if self.current_text:
            sentences = self.sentence_splitter.split_text(self.current_text)
            self.sentence_manager.set_sentences(sentences)
            self._pending_playback_index = None
            self._has_started_sentence_playback = False
            self._update_sentence_list()
    
    def _on_speed_changed(self, value):
        """语速改变"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"语速变更: {value}", fold_code="GEN_PARAM")
        self.config.speed = value
    
    def _on_gen_volume_changed(self, value):
        """生成音量改变"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"生成音量变更: {value}", fold_code="GEN_PARAM")
        self.config.volume = value

    def _on_voice_selected(self, voice_id):
        """音色选择"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"音色选择: {voice_id}", fold_code="GEN_VOICE")
        self.config.voice = voice_id
    
    def _load_default_settings(self):
        """从设置中加载默认配置"""
        import json
        
        try:
            # 加载标点提示开关
            hint_enabled = self.settings_manager.Custom.get_value('default_punctuation_hint', 'True')
            self.sentence_splitter.set_punctuation_hint(hint_enabled.lower() == 'true')
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                               f"加载默认标点提示设置: {hint_enabled}", fold_code="GEN_INIT")
            
            # 加载停顿符号配置
            marks_str = self.settings_manager.Custom.get_value('default_pause_marks', '')
            if marks_str:
                try:
                    pause_marks = json.loads(marks_str)
                    # 更新 PAUSE_MARKS
                    self.sentence_splitter.PAUSE_MARKS.clear()
                    for name, config in pause_marks.items():
                        symbol = config['symbol']
                        self.sentence_splitter.PAUSE_MARKS[name] = (symbol, symbol)
                    
                    # 更新启用的标记
                    enabled_marks = set()
                    for name, config in pause_marks.items():
                        if config.get('enabled', True):
                            enabled_marks.add(name)
                    self.sentence_splitter.set_pause_marks(enabled_marks)
                    
                    debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                                       f"加载自定义停顿符号配置，共{len(pause_marks)}个", fold_code="GEN_INIT")
                except Exception as e:
                    debug_logger.output("generation_page_neo.py", LogLevel.ERROR, 
                                       f"加载停顿符号配置失败: {str(e)}", fold_code="GEN_INIT")
            
            # 加载自动连播设置
            auto_play = self.settings_manager.Custom.get_value('auto_play_enabled', 'True')
            self.auto_play_enabled = (auto_play.lower() == 'true')
            self.auto_play_interval_mode = self.settings_manager.Custom.get_value('auto_play_interval_mode', 'fixed')
            self.auto_play_interval_fixed = float(self.settings_manager.Custom.get_value('auto_play_interval_fixed', '1.0'))
            self.auto_play_interval_dynamic = float(self.settings_manager.Custom.get_value('auto_play_interval_dynamic', '1.0'))
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, 
                               f"加载自动连播设置: enabled={self.auto_play_enabled}, mode={self.auto_play_interval_mode}, "
                               f"fixed={self.auto_play_interval_fixed}s, dynamic={self.auto_play_interval_dynamic}x", 
                               fold_code="GEN_INIT")
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, 
                               f"加载默认设置失败: {str(e)}", fold_code="GEN_INIT")
    
    def _on_sentence_clicked_in_list(self, idx):
        """句子列表中的句子被点击"""
        self._request_sentence_playback(idx)
    
    def _on_play_volume_changed(self, value):
        """播放音量改变"""
        self.volume_value_label.setText(f"{value}%")
        if self.parent_window and hasattr(self.parent_window, 'audio_preview'):
            self.parent_window.audio_preview.set_volume(value / 100.0)
    
    def _toggle_play_pause(self):
        """切换播放/暂停"""
        if self.parent_window and hasattr(self.parent_window, 'audio_preview'):
            if self.parent_window.is_playing:
                self.parent_window.audio_preview.pause_audio()
            elif hasattr(self.parent_window.audio_preview, 'is_paused') and self.parent_window.audio_preview.is_paused:
                self.parent_window.audio_preview.resume_audio()
            else:
                self._play_current_sentence()
    
    def _end_dictation(self):
        """结束听写 - 清空听写相关内容，保留输入文本"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "结束听写（保留文本）", fold_code="GEN_CTRL")
        
        self._stop_auto_play_timer()
        
        # 停止音频
        if self.parent_window and hasattr(self.parent_window, 'audio_preview'):
            self.parent_window.audio_preview.stop_audio()
        
        # 停止生成线程
        self.sentence_manager.is_generating = False
        self._pending_playback_index = None
        self._has_started_sentence_playback = False
        
        # 清空句子管理器
        self.sentence_manager.sentences.clear()
        self.sentence_manager.audio_files.clear()
        self.sentence_manager.audio_durations.clear()
        self.sentence_manager.current_sentence_index = 0
        self.sentence_manager.total_duration = 0.0
        
        # 重置UI状态
        self.progress_slider.setValue(0)
        
        # 清空分句列表显示
        self.sentence_list_widget.update_sentences([], 0)
        
        # 重置 Key Button 状态
        self._set_key_button_state("generate")
        self.all_sentences_played = False
        
        # 重置父窗口状态
        if self.parent_window:
            self.parent_window.has_preview = False
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "听写已结束，文本已保留", fold_code="GEN_CTRL")
    
    def _end_dictation_with_clear_text(self):
        """结束听写 - 清空所有内容（包括输入文本）"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "长按结束听写，准备清空所有内容", fold_code="GEN_CTRL")
        
        # 弹窗确认
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有内容（包括输入的文本）吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 先执行普通的结束听写
            self._end_dictation()
            
            # 清空文本编辑框
            self.text_edit.clear()
            self.current_text = ""
            self.config.content = ""
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "所有内容已清空", fold_code="GEN_CTRL")
        else:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "用户取消清空操作", fold_code="GEN_CTRL")
            self.parent_window.is_playing = False
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
    def _update_fonts(self):
        """更新字体"""
        if not self.parent_window:
            return
        
        # 计算动态字体大小
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        min_font_size = 10
        max_font_size = 16
        default_width = 1080
        default_height = 720
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        font = QFont(self.global_font, int(font_size))
        
        # 应用到控件
        self.text_edit.setFont(font)
        self.sentence_list_widget.set_font(font)
        self.pause_param_widget.set_font(font)
        self.voice_list_widget.set_font(font)
        
        # 按钮类
        for btn in [self.clear_btn, self.doc_btn, self.img_btn, self.online_btn,
                    self.tab_sentence_btn, self.tab_pause_btn, self.tab_voice_btn,
                    self.tab_prev_btn, self.tab_next_btn,
                    self.generate_btn, self.end_dictation_btn, self.prev_btn,
                    self.next_btn, self.auto_play_btn]:
            btn.setFont(font)
            
        # 标签类
        if hasattr(self, 'play_volume_label'):
            self.play_volume_label.setFont(font)
        if hasattr(self, 'volume_value_label'):
            self.volume_value_label.setFont(font)
    
    # =============================================================================
    # 播放控制
    # =============================================================================
    def _request_sentence_playback(self, sentence_index: int) -> bool:
        """立即播放已生成句子，或等待目标句子的生成信号。"""
        self._stop_auto_play_timer()
        manager = self.sentence_manager
        if not 0 <= sentence_index < len(manager.sentences):
            return False

        manager.current_sentence_index = sentence_index
        self._update_sentence_list()
        audio_file = manager.get_sentence_audio(sentence_index)
        if audio_file and os.path.exists(audio_file):
            self._pending_playback_index = None
            self._play_sentence_audio(audio_file)
            return True

        if manager.is_generating:
            self._pending_playback_index = sentence_index
            debug_logger.output(
                "generation_page_neo.py", LogLevel.INFO,
                f"句子音频尚未生成，等待TTS引擎: 索引={sentence_index}",
                fold_code="GEN_AUDIO_WAIT",
            )
        else:
            self._pending_playback_index = None
            debug_logger.output(
                "generation_page_neo.py", LogLevel.WARNING,
                f"句子音频不可用且TTS生成已停止: 索引={sentence_index}",
                fold_code="GEN_AUDIO_WAIT",
            )
        return False

    def _play_sentence_audio(self, audio_file: str):
        """播放指定的已生成音频文件。"""
        manager = self.sentence_manager
        if self.parent_window and hasattr(self.parent_window, 'audio_preview'):
            audio_preview = self.parent_window.audio_preview
            if audio_preview and hasattr(audio_preview, 'audio_signals') and audio_preview.audio_signals:
                try:
                    audio_preview.audio_signals.playback_finished.disconnect(
                        self._on_sentence_playback_complete
                    )
                except TypeError:
                    pass
                audio_preview.audio_signals.playback_finished.connect(
                    self._on_sentence_playback_complete
                )
                self._has_started_sentence_playback = True
                audio_preview._play_audio_file(audio_file)

                total = len(manager.sentences)
                current = manager.current_sentence_index + 1
                progress = int((current / total) * 1000)
                self.progress_slider.setValue(progress)
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "audio_preview 未完全初始化，无法播放音频", fold_code="GEN_AUDIO_PLAY")

    def _play_current_sentence(self):
        """播放当前句子"""
        manager = self.sentence_manager
        if not manager.sentences:
            return
        self._request_sentence_playback(manager.current_sentence_index)
    
    def _play_next_sentence(self):
        """播放下一句"""
        self._stop_auto_play_timer()
        manager = self.sentence_manager
        if manager.has_next_sentence():
            self._request_sentence_playback(manager.current_sentence_index + 1)
        else:
            QMessageBox.information(self, "提示", "已经是最后一句了")
    
    def _play_prev_sentence(self):
        """播放上一句"""
        self._stop_auto_play_timer()
        manager = self.sentence_manager
        if manager.has_prev_sentence():
            self._request_sentence_playback(manager.current_sentence_index - 1)
        else:
            QMessageBox.information(self, "提示", "已经是第一句了")
    
    def _on_sentence_playback_complete(self):
        """句子播放完成"""
        
        # 自动更新进度条
        manager = self.sentence_manager
        if manager.sentences:
            total = len(manager.sentences)
            current = manager.current_sentence_index + 1
            progress = int((current / total) * 1000)
            self.progress_slider.setValue(progress)
            
            # 检查是否所有句子都已播放完毕
            if current >= total:
                self.all_sentences_played = True
                self._set_key_button_state("generate")
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "所有句子播放完毕", fold_code="GEN_PLAY")
            elif self.auto_play_enabled:
                self._start_auto_play_timer()
    
    def _on_hotkey_next_sentence(self):
        """热键：下一句"""
        if self.isVisible():
            self._play_next_sentence()
    
    def _on_hotkey_prev_sentence(self):
        """热键：上一句"""
        if self.isVisible():
            self._play_prev_sentence()
    
    # =============================================================================
    # 音频生成
    # =============================================================================
    def _generate_preview_audio(self):
        """生成音频（听写模式）"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "开始生成听写音频...", fold_code="SENT_GEN")
        
        # 如果当前状态是"下一句"，则执行播放下一句的逻辑
        if self.key_button_state == "next_sentence":
            self._handle_key_button_next_sentence()
            return
        
        text_content = self.text_edit.toPlainText()
        if not text_content.strip():
            text_content = self.config.content
            self.text_edit.setPlainText(text_content)
        
        self.current_text = text_content
        
        # 分割文本
        sentences = self.sentence_splitter.split_text(text_content)
        if not sentences:
            QMessageBox.warning(self, "警告", "文本分割失败")
            return
        
        self.sentence_manager.set_sentences(sentences)
        self._pending_playback_index = None
        self._has_started_sentence_playback = False
        self._update_sentence_list()
        
        # 更新UI状态 - 切换到"生成中"状态
        self._set_key_button_state("generating")
        
        # 重置播放完成标记
        self.all_sentences_played = False
        
        # 启动生成
        self._start_generation(sentences)
    
    def _start_generation(self, sentences):
        """启动音频生成"""
        worker_count = self._get_generation_thread_count()
        debug_logger.output(
            "generation_page_neo.py", LogLevel.INFO,
            f"启动生成，句子数量: {len(sentences)}, 工作线程: {worker_count}",
            fold_code="GEN_GEN",
        )

        batch_id = self.sentence_manager.prepare_generation(sentences, worker_count)
        self._tts_error_emitted = False

        threads = [
            threading.Thread(target=self._generation_worker, args=(batch_id,), daemon=True)
            for _ in range(worker_count)
        ]
        self.sentence_manager.generation_threads = threads
        for thread in threads:
            thread.start()

    def _get_generation_thread_count(self) -> int:
        """EdgeTTS uses four sentence workers; every other engine stays serial."""
        try:
            from tts_router import get_tts_router

            if get_tts_router().get_selected_provider() == "EdgeTTS":
                return self.sentence_manager.max_threads
        except Exception as e:
            debug_logger.output(
                "generation_page_neo.py", LogLevel.WARNING,
                f"无法确定TTS生成线程数，回退到单线程: {e}",
                fold_code="GEN_GEN",
            )
        return 1
    
    def _generation_worker(self, batch_id: int):
        """
        生成工作线程（daemon 后台线程）。

        逐个取出句子队列中的句子，调用 _generate_single_sentence 生成音频，
        通过 Qt 信号将结果发送回主线程更新 UI。

        保护机制:
        - 检查 self._destroyed 标志，防止页面销毁后 emit 信号导致 crash
        - 所有异常在循环内捕获，不会中断其他句子生成
        """
        try:
            while self.sentence_manager.is_generation_active(batch_id):
                # 页面已销毁，停止生成
                if getattr(self, '_destroyed', False):
                    debug_logger.output("generation_page_neo.py", LogLevel.WARNING,
                        "页面已销毁，取消生成", fold_code="GEN_GEN")
                    return

                sentence_info = self.sentence_manager.get_next_sentence_to_generate(batch_id)
                if sentence_info is None:
                    break
                
                sentence_index, sentence_text = sentence_info
                
                try:
                    audio_file, duration = self._generate_single_sentence(sentence_text, sentence_index)
                    
                    if audio_file and self.sentence_manager.is_generation_active(batch_id):
                        # 发送前再次检查页面存活
                        if getattr(self, '_destroyed', False):
                            return
                        self.signals.sentence_generated.emit(sentence_index, audio_file, duration)
                        
                        if self.sentence_manager.claim_playback_ready(batch_id):
                            time.sleep(0.1)
                            if not getattr(self, '_destroyed', False):
                                self.signals.playback_ready.emit()
                
                except TTSEngineError as e:
                    should_emit_error = self.sentence_manager.stop_for_tts_error(
                        batch_id, sentence_index, sentence_text
                    )
                    debug_logger.output(
                        "generation_page_neo.py", LogLevel.ERROR,
                        f"TTS 引擎失败，保留句子重试状态: {e}",
                        fold_code="GEN_GEN",
                    )
                    if should_emit_error and not getattr(self, '_destroyed', False):
                        self._tts_error_emitted = True
                        action = getattr(e, "action", "检查 TTS 设置后重试")
                        self.signals.tts_error.emit(f"{e}\n\n{action}")
                    break
                except Exception as e:
                    debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"句子生成失败: {e}", fold_code="GEN_GEN")
                    continue
        
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"生成工作器出错: {e}", fold_code="GEN_GEN")
        finally:
            is_last_worker = self.sentence_manager.finish_generation_worker(batch_id)
            if is_last_worker and not getattr(self, '_destroyed', False):
                self.signals.all_sentences_complete.emit()
    
    def _generate_single_sentence(self, sentence_text: str, sentence_index: int) -> tuple:
        """
        生成单个句子的音频。
        
        调用链:
          TTSRouter.generate_audio(config)
            → EdgeTTS / AI Provider
        """
        try:
            from tts_router import get_tts_router, TTSGenerationConfig
            from edge_audio_generator import FilePathManager
            
            selected_voice = self.voice_list_widget.selected_voice
            if not selected_voice and self.voice_list_widget.voice_buttons:
                selected_voice = self.voice_list_widget.voice_buttons[0].property("voice_id")
            if not selected_voice:
                raise RuntimeError("当前TTS模型没有可用音色")

            temp_config = AudioConfig()
            temp_config.content = sentence_text
            temp_config.voice = selected_voice
            temp_config.speed = self.config.speed
            temp_config.volume = self.config.volume
            
            file_manager = FilePathManager()
            audio_file = file_manager.create_temp_file('.wav')
            
            gen_config = TTSGenerationConfig(
                content=sentence_text,
                voice=selected_voice,
                speed=self.config.speed,
                pitch=getattr(self.config, 'pitch', 0),
                volume=self.config.volume,
                save_path=audio_file
            )
            
            tts_router = get_tts_router()
            
            # This method already runs in the generation worker. The runtime bridge
            # owns request deadlines and maps them to TTSEngineTimeoutError.
            success = tts_router.generate_audio(gen_config)
            
            if success:
                duration = self._get_audio_duration(audio_file)
                return audio_file, duration
            
            return None, 0.0
        
        except TTSEngineError:
            raise
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"生成单句音频失败: {e}", fold_code="GEN_AUDIO")
            return None, 0.0
    
    def _get_audio_duration(self, audio_file_path: str) -> float:
        """获取音频时长"""
        try:
            import wave
            with wave.open(audio_file_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / float(rate)
        except Exception:
            try:
                import soundfile as sf
                info = sf.info(audio_file_path)
                return info.duration
            except Exception as e:
                debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"获取音频时长失败: {e}", fold_code="GEN_AUDIO")
                return 0.0
    
    # =============================================================================
    # 信号槽
    # =============================================================================
    @pyqtSlot(int, str, float)
    def _on_sentence_generated(self, index, audio_file, duration):
        """句子生成完成"""
        self.sentence_manager.add_generated_audio(index, audio_file, duration)
        
        # 更新句子列表（如果有进度显示）
        self._update_sentence_list()

        if self._pending_playback_index == index:
            debug_logger.output(
                "generation_page_neo.py", LogLevel.INFO,
                f"等待的句子已生成，开始播放: 索引={index}",
                fold_code="GEN_AUDIO_WAIT",
            )
            self._request_sentence_playback(index)
    
    @pyqtSlot()
    def _on_all_sentences_complete(self):
        """所有句子生成完成"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "所有句子生成完成", fold_code="GEN_GEN")
        self.sentence_manager.is_generating = False
        if self._pending_playback_index is not None:
            debug_logger.output(
                "generation_page_neo.py", LogLevel.WARNING,
                f"TTS生成结束，但等待的句子没有可用音频: 索引={self._pending_playback_index}",
                fold_code="GEN_AUDIO_WAIT",
            )
            self._pending_playback_index = None
        self._stop_converting_animation()
        # 注意：不在这里改变按钮状态，因为可能还在播放中

    @pyqtSlot(str)
    def _on_tts_error(self, message):
        """Show one actionable error for a failed generation batch."""
        self._set_key_button_state("generate")
        self._stop_converting_animation()
        QMessageBox.critical(self, "TTS 引擎不可用", message)
    
    @pyqtSlot()
    def _on_playback_ready(self):
        """可以开始播放"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "第一个句子就绪，可以开始播放", fold_code="GEN_GEN")
        # 切换到"下一句"状态
        self._set_key_button_state("next_sentence")
        if not self._has_started_sentence_playback and self._pending_playback_index is None:
            self._play_current_sentence()
    
    @pyqtSlot(bool, str)
    def _on_generation_complete_safe(self, success, message):
        """生成完成（线程安全）"""
        if success:
            QMessageBox.information(self, "完成", "音频生成完成")
        else:
            QMessageBox.critical(self, "错误", f"生成失败: {message}")
    
    @pyqtSlot(bool, str)
    def _update_button_state_safe(self, has_error, empty_fields_text):
        """更新按钮状态（线程安全）"""
        # Neo 页面沿用 Key Button 逻辑，这里只做兼容占位
        pass

    def _check_inputs_and_update_button(self):
        """兼容旧调用链：检查输入并触发按钮状态信号。"""
        try:
            has_error, empty_fields = InputValidator.check_inputs_for_button(self.config, self.parent_window.settings_manager)
            if has_error:
                debug_logger.output(
                    "generation_page_neo.py",
                    LogLevel.INFO,
                    f"输入检查发现空字段: {', '.join(empty_fields)}",
                    fold_code="GEN_STATE",
                )
            self.signals.update_button_state.emit(has_error, ", ".join(empty_fields))
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"输入检查失败: {e}", fold_code="GEN_STATE")

    def _check_content_changed(self):
        """兼容旧调用链：检测配置变化并重置预览状态。"""
        try:
            current_hash = ContentHasher.get_content_hash(self.config)
            last_hash = getattr(self.parent_window, "last_content_hash", None)
            content_changed = (last_hash is None or current_hash != last_hash)

            if content_changed and getattr(self.parent_window, "has_preview", False):
                if hasattr(self, "preview_control"):
                    self.preview_control.update_preview_button_state(False, False)
                self.parent_window.has_preview = False
                audio_preview = getattr(self.parent_window, "audio_preview", None)
                if audio_preview is not None and (
                    getattr(self.parent_window, "is_playing", False) or getattr(audio_preview, "is_paused", False)
                ):
                    audio_preview.stop_audio()
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"内容变化检查失败: {e}", fold_code="GEN_STATE")
    
    # =============================================================================
    # 更新UI
    # =============================================================================

    def _update_sentence_list(self):
        """更新句子列表显示"""
        manager = self.sentence_manager
        if manager.sentences:
            self.sentence_list_widget.update_sentences(
                manager.sentences,
                manager.current_sentence_index
            )
    
    # =============================================================================
    # 共享内存事件
    # =============================================================================
    def _on_font_changed(self, font_name):
        """字体改变"""
        self.global_font = font_name
        self._update_fonts()
    
    def _on_theme_changed(self, theme_data):
        """主题改变"""
        bg_color = theme_data.get('background_color')
        text_color = theme_data.get('text_color')
        
        if bg_color:
            self.background_color = bg_color
            if getattr(self, "theme_service", None) is None:
                self.setStyleSheet(
                    f"GenerationPage {{ background-color: {bg_color}; }}"
                )
        if text_color:
            self.text_color = text_color
    
    def _on_window_size_changed(self, width, height):
        """窗口大小改变"""
        self._update_fonts()
    
    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置变更"""
        try:
            # 处理TTS模型配置变更
            if page_name == 'ai_model_tts':
                provider = settings_data.get('provider', '')
                model = settings_data.get('model', '')
                debug_logger.output("generation_page_neo.py", LogLevel.INFO,
                    f"收到TTS模型配置变更: {provider} - {model}",
                    fold_code="GEN_SETTINGS")
                
                # 清除TTS路由器缓存，强制重新读取配置
                if self.parent_window and hasattr(self.parent_window, '_audio_generator'):
                    self.parent_window._audio_generator = None
                    debug_logger.output("generation_page_neo.py", LogLevel.INFO,
                        "已重置TTS路由器缓存",
                        fold_code="GEN_SETTINGS")
                
                # 重新加载音色列表
                provider_mapping = {
                    "MS": "Microsoft",
                    "ChatGLM": "ChatGLM",
                    "Qwen": "Qwen",
                    "KIMI": "KIMI",
                    "Minimax": "Minimax",
                    "Mimo": "Mimo",
                }
                provider_name = provider_mapping.get(provider, provider)
                model_string = f"{provider_name}/{model}"
                self.voice_list_widget.load_voices(
                    model=model_string,
                    auto_select_default=True,
                    force_refresh=True,
                )
                debug_logger.output("generation_page_neo.py", LogLevel.INFO,
                    f"已重载音色列表: {model_string}",
                    fold_code="GEN_SETTINGS")
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR,
                f"处理设置变更失败: {e}",
                fold_code="GEN_SETTINGS")

    def reload_current_voice_list(self):
        """Reload the active model's voices whenever the dictation tab is activated."""
        provider = self.settings_manager.Custom.get_value("ai_model_tts_provider", "MS")
        model = self.settings_manager.Custom.get_value("ai_model_tts_model", "edge-tts")
        provider_mapping = {
            "MS": "Microsoft",
            "ChatGLM": "ChatGLM",
            "Qwen": "Qwen",
            "KIMI": "KIMI",
            "Minimax": "Minimax",
            "Mimo": "Mimo",
        }
        model_string = f"{provider_mapping.get(provider, provider)}/{model}"
        self._voice_reload_token = getattr(self, "_voice_reload_token", 0) + 1
        self._reload_voice_list_attempt(model_string, self._voice_reload_token, 5)

    def _reload_voice_list_attempt(self, model_string, token, remaining):
        if token != getattr(self, "_voice_reload_token", None):
            return
        self.voice_list_widget.load_voices(
            model=model_string,
            auto_select_default=True,
            # 激活时只做轻量的就绪检查；设置变更入口仍然使用强制刷新。
            force_refresh=False,
        )
        debug_logger.output(
            "generation_page_neo.py",
            LogLevel.INFO,
            f"听写选项卡激活，已重新载入音色列表: {model_string}",
            fold_code="GEN_VOICE",
        )
        if not self.voice_list_widget.voice_buttons and remaining > 0:
            QTimer.singleShot(
                1500,
                lambda: self._reload_voice_list_attempt(model_string, token, remaining - 1),
            )
    
    # =============================================================================
    # 公共接口
    # =============================================================================
    def _set_key_button_state(self, state: str):
        """设置 Key Button 状态
        
        Args:
            state: "generate" - 生成音频, "generating" - 生成中, "next_sentence" - 下一句
        """
        old_state = getattr(self, "key_button_state", None)
        self.key_button_state = state
        
        if state == "generate":
            self._stop_converting_animation()
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("生成音频")
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "Key Button -> 生成音频", fold_code="GEN_BTN")
            
            # 只有当从非 generate (即真正有这两个按钮显示的状态) 回来时，才执行退场动画
            if old_state in ("generating", "next_sentence") and self.nav_widget.isVisible():
                self.nav_anim_group.stop()
                try: self.nav_anim_group.finished.disconnect()
                except: pass
                
                current_pos = self.nav_widget.pos()
                end_pos = QPoint(current_pos.x(), current_pos.y() + 40)
                
                self.nav_pos_anim.setStartValue(current_pos)
                self.nav_pos_anim.setEndValue(end_pos)
                self.nav_op_anim.setStartValue(self.nav_opacity.opacity())
                self.nav_op_anim.setEndValue(0.0)
                
                def on_hide_finished():
                    self.nav_widget.hide()
                    # 避免控件移动出原有布局，下一次获取pos时错乱。重置其位置（或依赖布局刷新）
                    # 实际上它被包裹在 layout 中，下一次 show() 的时候 layout 会自动将其排到正确的位置。
                
                self.nav_anim_group.finished.connect(on_hide_finished)
                self.nav_anim_group.start()
            else:
                self.nav_widget.hide()
                self.nav_opacity.setOpacity(0.0)
                
        elif state == "generating":
            self._start_converting_animation()
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("生成中...")
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "Key Button -> 生成中", fold_code="GEN_BTN")
            
            if old_state != "generating" and old_state != "next_sentence":
                self.nav_anim_group.stop()
                try: self.nav_anim_group.finished.disconnect()
                except: pass
                
                self.nav_widget.show()
                # 延时一帧，等待布局计算其真实位置
                def run_enter_anim():
                    if not self.nav_widget.isVisible() or self.key_button_state != "generating": return
                    target_pos = self.nav_widget.pos()
                    # 防止因为意外导致坐标依然为0的情况
                    if target_pos.y() <= 0: return
                    start_pos = QPoint(target_pos.x(), target_pos.y() + 40)
                    
                    self.nav_pos_anim.setStartValue(start_pos)
                    self.nav_pos_anim.setEndValue(target_pos)
                    self.nav_op_anim.setStartValue(self.nav_opacity.opacity())
                    self.nav_op_anim.setEndValue(1.0)
                    self.nav_anim_group.start()
                QTimer.singleShot(0, run_enter_anim)
                
        elif state == "next_sentence":
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("下一句")
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "Key Button -> 下一句", fold_code="GEN_BTN")
            
            if old_state == "generate":
                self.nav_anim_group.stop()
                try: self.nav_anim_group.finished.disconnect()
                except: pass
                
                self.nav_widget.show()
                def run_enter_anim_ns():
                    if not self.nav_widget.isVisible() or self.key_button_state != "next_sentence": return
                    target_pos = self.nav_widget.pos()
                    if target_pos.y() <= 0: return
                    start_pos = QPoint(target_pos.x(), target_pos.y() + 40)
                    
                    self.nav_pos_anim.setStartValue(start_pos)
                    self.nav_pos_anim.setEndValue(target_pos)
                    self.nav_op_anim.setStartValue(self.nav_opacity.opacity())
                    self.nav_op_anim.setEndValue(1.0)
                    self.nav_anim_group.start()
                QTimer.singleShot(0, run_enter_anim_ns)

    def _start_converting_animation(self):
        self._converting_frame = 0
        self.converting_label.setText("转换中")
        self.converting_label.show()
        if not self._converting_timer.isActive():
            self._converting_timer.start()

    def _advance_converting_animation(self):
        self._converting_frame = (self._converting_frame + 1) % 4
        self.converting_label.setText("转换中" + " ·" * self._converting_frame)

    def _stop_converting_animation(self):
        if hasattr(self, "_converting_timer"):
            self._converting_timer.stop()
        if hasattr(self, "converting_label"):
            self.converting_label.hide()
    
    def _handle_key_button_next_sentence(self):
        """处理 Key Button 在"下一句"状态下的点击"""
        manager = self.sentence_manager
        
        # 检查是否还有下一句
        if not manager.has_next_sentence():
            # 已经是最后一句，检查是否播放完毕
            if self.all_sentences_played:
                QMessageBox.information(self, "提示", "所有句子已播放完毕")
            else:
                QMessageBox.information(self, "提示", "已经是最后一句了")
            return
        
        next_index = manager.current_sentence_index + 1
        self._request_sentence_playback(next_index)
    
    def _resplit_sentences(self):
        """重新分句"""
        text_content = self.text_edit.toPlainText()
        if not text_content.strip():
            QMessageBox.warning(self, "警告", "文本内容为空，无法分句")
            return
        
        # 执行分句
        sentences = self.sentence_splitter.split_text(text_content)
        if not sentences:
            QMessageBox.warning(self, "警告", "文本分割失败")
            return
        
        # 构建分句结果文本
        result_text = f"共分为 {len(sentences)} 句：\n\n"
        for i, sentence in enumerate(sentences, 1):
            result_text += f"{i}. {sentence}\n"
        
        # 弹窗显示分句结果
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("分句结果")
        msg_box.setText("是否使用新的分句结果替换当前分句？")
        msg_box.setDetailedText(result_text)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)
        
        # 设置按钮文本为中文
        yes_btn = msg_box.button(QMessageBox.Yes)
        no_btn = msg_box.button(QMessageBox.No)
        yes_btn.setText("替换")
        no_btn.setText("取消")
        
        result = msg_box.exec_()
        
        if result == QMessageBox.Yes:
            # 用户确认替换
            self.sentence_manager.set_sentences(sentences)
            self._pending_playback_index = None
            self._has_started_sentence_playback = False
            self._update_sentence_list()
            self._set_key_button_state("generate")
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"重新分句完成，共 {len(sentences)} 句", fold_code="GEN_SPLIT")
    
    def handle_next_sentence(self):
        """处理下一句（供外部调用）"""
        self._play_next_sentence()


if __name__ == "__main__":
    pass
