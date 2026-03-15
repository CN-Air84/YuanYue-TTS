# coding=utf-8
import threading
import re
import time
import os
import hashlib
import random
from typing import Callable, List, Dict, Optional
from PyQt5.QtWidgets import (QWidget, QPushButton, QSlider, QTextEdit, QCheckBox, QComboBox, QLabel, 
                             QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QButtonGroup, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, pyqtSlot, QTimer
from PyQt5.QtGui import QFont

from misc_func import AudioConfig, VoiceConfig, ContentHasher, AudioFileManager, InputValidator
from iw_text_import import show_text_import_dialog
from shared_memory_manager import get_shared_memory_manager
from debug_logger import debug_logger, LogLevel


'''
本段代码负责“听写”选项卡。
若想修改“生成”选项卡请移步generation_page_。
'''

class GenerationSignals(QObject):
    """生成页面信号类"""
    
    generation_complete = pyqtSignal(bool, str)
    preview_generated = pyqtSignal(str)
    preview_error = pyqtSignal(str)
    update_button_state = pyqtSignal(bool, str)
    sentence_generated = pyqtSignal(int, str, float)  # 句子索引, 音频文件路径, 音频时长
    all_sentences_complete = pyqtSignal()  # 所有句子生成完成
    playback_ready = pyqtSignal()  # 可以开始播放


class SentenceSplitter:
    """文本分割器 - 按标点符号分割文本为小句"""
    
    # 默认停顿符号
    DEFAULT_PAUSE_MARKS = {
        '逗号': '，',
        '句号': '。',
        '句点': '.',
        '叹号': '！',
        '问号': '？',
        '省略号': '……',
        '换行': '\n',
        '斜杠': '/',
        '括号': '）',
        '波浪线': '～',
        '[S]': '[S]'
    }
    
    def __init__(self):
        self.pause_marks = self.DEFAULT_PAUSE_MARKS.copy()
        self.enabled_marks = set(self.DEFAULT_PAUSE_MARKS.keys())  # 默认全部启用
    
    def set_pause_marks(self, enabled_marks: set):
        """设置启用的停顿符号"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"更新启用的停顿符号，数量: {len(enabled_marks)}", fold_code="GEN_SPLIT")
        self.enabled_marks = enabled_marks
    
    def _clean_text(self, text: str) -> str:
        """清理文本，移除句子开头和结尾的空格、换行符等多余空白字符"""
        # 移除句子开头和结尾的空白字符（空格、换行符、制表符等）
        text = text.strip()
        
        # 将多个连续的空白字符替换为单个空格
        text = re.sub(r'\s+', ' ', text)
        
        # 移除句子开头的标点符号（保留在句子内部）
        text = re.sub(r'^[\s\.,;:!?，。；：！？]+', '', text)
        
        return text.strip()
    
    def split_text(self, text: str) -> List[str]:
        """将文本分割为小句 - 避免只含符号的句子"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"开始分割文本，原始长度: {len(text)}", fold_code="GEN_SPLIT")
        if not text.strip():
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "文本为空，放弃分割", fold_code="GEN_SPLIT")
            return []
        
        # 首先清理整个文本
        text = self._clean_text(text)
        if not text:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "清理后文本为空，放弃分割", fold_code="GEN_SPLIT")
            return []
        
        # 构建正则表达式模式
        pattern_parts = []
        for mark_name in self.enabled_marks:
            if mark_name in self.pause_marks:
                mark = self.pause_marks[mark_name]
                # 转义特殊字符
                if mark in ['.', '?', '*', '+', '^', '$', '[', ']', '(', ')', '{', '}']:
                    pattern_parts.append(re.escape(mark))
                else:
                    pattern_parts.append(mark)
        
        if not pattern_parts:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "未启用任何停顿符号，返回完整清理后文本", fold_code="GEN_SPLIT")
            return [text.strip()]  # 没有启用的停顿符号，返回整个文本
        
        # 构建正则表达式
        pattern = '|'.join(pattern_parts)
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"分割模式串: {pattern}", fold_code="GEN_SPLIT")
        
        # 分割文本
        sentences = []
        current_text = text
        
        while current_text.strip():
            # 查找下一个停顿符号
            match = re.search(pattern, current_text)
            
            if match:
                # 获取停顿符号前的文本
                start = match.start()
                if start > 0:
                    sentence = self._clean_text(current_text[:start])
                    if sentence and self._has_real_content(sentence):
                        sentences.append(sentence)
                
                # 检查停顿符号后的文本是否包含实际内容
                end = match.end()
                pause_text = self._clean_text(current_text[start:end])
                remaining_text = self._clean_text(current_text[end:])
                
                # 如果停顿符号后有实际内容，将停顿符号附加到前一个句子
                if remaining_text and self._has_real_content(remaining_text):
                    if sentences:
                        sentences[-1] += pause_text
                    else:
                        # 如果前面没有句子，创建一个包含停顿符号的句子
                        sentences.append(pause_text)
                
                # 更新剩余文本
                current_text = current_text[end:]
            else:
                # 没有更多停顿符号，剩余文本作为最后一个句子
                remaining = self._clean_text(current_text)
                if remaining and self._has_real_content(remaining):
                    sentences.append(remaining)
                break
        
        # 如果没有任何有效句子，返回整个文本（清理后）
        cleaned_text = self._clean_text(text)
        if not sentences and cleaned_text:
            sentences.append(cleaned_text)
        
        # 最终过滤：移除空句子或只有空白字符的句子
        valid_sentences = []
        for sentence in sentences:
            cleaned_sentence = self._clean_text(sentence)
            if cleaned_sentence and self._has_real_content(cleaned_sentence):
                valid_sentences.append(cleaned_sentence)
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"文本分割完成，产出句子数: {len(valid_sentences)}", fold_code="GEN_SPLIT")
        return valid_sentences
    
    def _has_real_content(self, text: str) -> bool:
        """检查文本是否包含实际内容（非符号）"""
        # 移除非中文字符、非字母数字、非空格
        content = re.sub(r'[^\u4e00-\u9fff\w\s]', '', text)
        return len(content.strip()) > 0


class SentenceAudioManager:
    """小句音频管理器"""
    
    def __init__(self):
        self.sentences: List[str] = []  # 分割后的小句
        self.audio_files: Dict[int, str] = {}  # 句子索引 -> 音频文件路径
        self.audio_durations: Dict[int, float] = {}  # 句子索引 -> 音频时长
        self.current_sentence_index = 0  # 当前播放的句子索引
        self.total_duration = 0.0  # 总音频时长
        self.is_generating = False  # 是否正在生成
        self.generation_threads = []  # 生成线程列表
        self.max_threads = 4  # 最大线程数
        self.generation_queue = []  # 待生成的句子队列
        self.lock = threading.Lock()  # 线程锁
        self.play_retry_count = {}  # 句子播放重试计数
    
    def set_sentences(self, sentences: List[str]):
        """设置句子列表"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"句子管理器已就绪，共接收 {len(sentences)} 句文本", fold_code="GEN_AUDIO_MGR")
        self.sentences = sentences
        self.audio_files.clear()
        self.audio_durations.clear()
        self.current_sentence_index = 0
        self.total_duration = 0.0
        self.play_retry_count.clear()  # 清除重试计数
    
    def get_next_sentence_to_generate(self) -> Optional[tuple]:
        """获取下一个要生成的句子（线程安全）"""
        with self.lock:
            if self.generation_queue:
                item = self.generation_queue.pop(0)
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"出队待生成句子: 索引={item[0]}, 文本长度={len(item[1])}", fold_code="GEN_AUDIO_MGR")
                return item
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "生成队列已清空", fold_code="GEN_AUDIO_MGR")
            return None
    
    def get_sentence_audio(self, index: int) -> Optional[str]:
        """获取指定句子的音频文件路径"""
        with self.lock:
            audio_path = self.audio_files.get(index)
            if audio_path:
                debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"获取句子 {index} 音频路径: {audio_path}", fold_code="GEN_AUDIO_MGR")
            return audio_path
    
    def add_generated_audio(self, sentence_index: int, audio_file: str, duration: float):
        """添加生成的音频（线程安全）"""
        with self.lock:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"注册已生成音频: 索引={sentence_index}, 时长={duration:.2f}s", fold_code="GEN_AUDIO_MGR")
            self.audio_files[sentence_index] = audio_file
            self.audio_durations[sentence_index] = duration
            self.total_duration += duration
    
    def get_total_duration(self) -> float:
        """获取总音频时长（线程安全）"""
        with self.lock:
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"查询总时长: {self.total_duration:.2f}s", fold_code="GEN_AUDIO_MGR")
            return self.total_duration
    
    def get_generated_count(self) -> int:
        """获取已生成的句子数量（线程安全）"""
        with self.lock:
            count = len(self.audio_files)
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"查询已生成数量: {count}", fold_code="GEN_AUDIO_MGR")
            return count
    
    def is_all_generated(self) -> bool:
        """检查是否所有句子都已生成"""
        all_done = len(self.audio_files) == len(self.sentences)
        if all_done and len(self.sentences) > 0:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"所有句子音频已生成完毕 (共 {len(self.sentences)} 句)", fold_code="GEN_AUDIO_MGR")
        return all_done
    
    def get_current_sentence_audio(self) -> Optional[str]:
        """获取当前句子的音频文件"""
        audio_path = self.audio_files.get(self.current_sentence_index)
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"获取当前索引 {self.current_sentence_index} 的音频: {audio_path}", fold_code="GEN_AUDIO_MGR")
        return audio_path
    
    def move_to_next_sentence(self) -> bool:
        """移动到下一句"""
        if self.current_sentence_index < len(self.sentences) - 1:
            self.current_sentence_index += 1
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"推进播放指针 -> {self.current_sentence_index}", fold_code="GEN_AUDIO_MGR")
            return True
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "播放指针已达末尾，无法继续推进", fold_code="GEN_AUDIO_MGR")
        return False
    
    def move_to_prev_sentence(self) -> bool:
        """移动到上一句"""
        if self.current_sentence_index > 0:
            self.current_sentence_index -= 1
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"回退播放指针 -> {self.current_sentence_index}", fold_code="GEN_AUDIO_MGR")
            return True
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "播放指针已在起始位置，无法回退", fold_code="GEN_AUDIO_MGR")
        return False
    
    def has_next_sentence(self) -> bool:
        """检查是否还有下一句"""
        has_next = self.current_sentence_index < len(self.sentences) - 1
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"检查后继句子: {'存在' if has_next else '不存在'}", fold_code="GEN_AUDIO_MGR")
        return has_next

    def has_prev_sentence(self) -> bool:
        """检查是否还有上一句"""
        has_prev = self.current_sentence_index > 0
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"检查前驱句子: {'存在' if has_prev else '不存在'}", fold_code="GEN_AUDIO_MGR")
        return has_prev
    
    def get_progress_text(self) -> str:
        """获取进度文本"""
        generated = self.get_generated_count()
        total = len(self.sentences)
        progress_text = f"{generated}/{total}"
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"生成进度: {progress_text}", fold_code="GEN_AUDIO_MGR")
        return progress_text


class PauseSettingsDialog(QDialog):
    """停顿设置对话框"""
    
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在打开停顿设置对话框", fold_code="GEN_PAUSE_DLG")
        self.setWindowTitle("停顿设置")
        self.setModal(True)
        self.setFixedSize(400, 500)
        
        # 当前设置
        self.current_settings = current_settings or set(SentenceSplitter.DEFAULT_PAUSE_MARKS.keys())
        
        self._init_ui()
        self._load_settings()
        self._update_fonts()
    
    def _init_ui(self):
        """初始化UI"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "初始化停顿设置UI组件", fold_code="GEN_PAUSE_DLG")
        # 获取用户设置的字体
        if hasattr(self.parent(), 'settings_manager'):
            global_font = self.parent().settings_manager.get_Custom_value("global_font", "微软雅黑")
        else:
            global_font = "微软雅黑"
        
        layout = QVBoxLayout()
        
        # 创建分组框
        group_box = QGroupBox("选择停顿符号")
        group_layout = QVBoxLayout()
        
        # 创建复选框
        self.checkboxes = {}
        for mark_name in SentenceSplitter.DEFAULT_PAUSE_MARKS.keys():
            checkbox = QCheckBox(mark_name)
            checkbox.setFont(QFont(global_font, 10))
            self.checkboxes[mark_name] = checkbox
            group_layout.addWidget(checkbox)
        
        group_box.setLayout(group_layout)
        group_box.setFont(QFont(global_font, 11))
        layout.addWidget(group_box)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存并应用")
        self.save_button.setFont(QFont(global_font, 10))
        self.save_button.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFont(QFont(global_font, 10))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _update_fonts(self):
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 8
        max_font_size = 16
        default_width = 400
        default_height = 500
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        # 获取用户设置的字体
        if hasattr(self.parent(), 'settings_manager'):
            global_font = self.parent().settings_manager.get_Custom_value("global_font", "微软雅黑")
        else:
            global_font = "微软雅黑"
        
        # 更新复选框字体
        for checkbox in self.checkboxes.values():
            checkbox.setFont(QFont(global_font, int(font_size)))
        
        # 更新按钮字体
        self.save_button.setFont(QFont(global_font, int(font_size)))
        self.cancel_button.setFont(QFont(global_font, int(font_size)))
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
    def _load_settings(self):
        """加载当前设置"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"加载当前停顿设置，共 {len(self.current_settings)} 个启用项", fold_code="GEN_PAUSE_DLG")
        for mark_name, checkbox in self.checkboxes.items():
            checkbox.setChecked(mark_name in self.current_settings)
    
    def _save_settings(self):
        """保存设置"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在应用停顿符号设置变更...", fold_code="GEN_PAUSE_DLG")
        enabled_marks = set()
        for mark_name, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                enabled_marks.add(mark_name)
        
        if not enabled_marks:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "未选择任何停顿符号，保存操作已中止", fold_code="GEN_PAUSE_DLG")
            QMessageBox.warning(self, "警告", "至少需要选择一个停顿符号！")
            return
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"停顿设置已更新，启用符号: {', '.join(enabled_marks)}", fold_code="GEN_PAUSE_DLG")
        self.current_settings = enabled_marks
        self.accept()
    
    def get_enabled_marks(self):
        """获取启用的停顿符号"""
        return self.current_settings


class ParamSettingsDialog(QDialog):
    """参数设置对话框 - 语速和语调控制"""
    
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在打开语音参数设置对话框", fold_code="GEN_PARAM_DLG")
        self.setWindowTitle("语音参数设置")
        self.setModal(True)
        self.setFixedSize(500, 400)
        
        # 当前配置
        self.current_config = current_config or type('Config', (), {
            'speed': 0
        })()
        
        # 保存原始配置用于比较
        self.original_config = type('Config', (), {
            'speed': self.current_config.speed
        })()
        
        self._init_ui()
        self._load_settings()
        self._update_fonts()
    
    def _init_ui(self):
        """初始化UI"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "初始化语音参数设置UI组件", fold_code="GEN_PARAM_DLG")
        # 获取用户设置的字体
        if hasattr(self.parent(), 'settings_manager'):
            global_font = self.parent().settings_manager.get_Custom_value("global_font", "微软雅黑")
        else:
            global_font = "微软雅黑"
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # 语速滑动条
        speed_layout = QHBoxLayout()
        self.speed_label = QLabel("语速:")
        self.speed_label.setFont(QFont(global_font, 11))
        speed_layout.addWidget(self.speed_label)
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(-50, 50)  # -50% 到 +50%
        self.speed_slider.setValue(-50)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(10)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.speed_slider.setStyleSheet(self._get_slider_style())  # 使用主页面相同的滑动条样式
        speed_layout.addWidget(self.speed_slider)
        
        self.speed_value_label = QLabel("-50%")
        self.speed_value_label.setFont(QFont(global_font, 10))
        self.speed_value_label.setMinimumWidth(50)
        speed_layout.addWidget(self.speed_value_label)
        
        layout.addLayout(speed_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存设置")
        self.save_button.setFont(QFont(global_font, 10))
        self.save_button.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFont(QFont(global_font, 10))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _update_fonts(self):
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 8
        max_font_size = 16
        default_width = 500
        default_height = 400
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        # 获取用户设置的字体
        if hasattr(self.parent(), 'settings_manager'):
            global_font = self.parent().settings_manager.get_Custom_value("global_font", "微软雅黑")
        else:
            global_font = "微软雅黑"
        
        # 更新标签字体
        self.speed_label.setFont(QFont(global_font, int(font_size * 1.1)))
        self.speed_value_label.setFont(QFont(global_font, int(font_size)))
        
        # 更新按钮字体
        self.save_button.setFont(QFont(global_font, int(font_size)))
        self.cancel_button.setFont(QFont(global_font, int(font_size)))
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
    def _load_settings(self):
        """加载当前设置"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"加载当前语音配置，语速: {self.current_config.speed}%", fold_code="GEN_PARAM_DLG")
        self.speed_slider.setValue(self.current_config.speed)
    
    def _on_speed_changed(self, value):
        """语速变化事件"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"语速调整 -> {value}%", fold_code="GEN_PARAM_DLG")
        self.speed_value_label.setText(f"{value}%")
        self.current_config.speed = value

    def _get_slider_style(self) -> str:
        """获取滑动条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
            height: 12px;
            background: #FFFFFF;
            border-radius: 6px;
        }
        
        QSlider::sub-page:horizontal {
            background: #44AADD;
            border-radius: 6px;
        }
        
        QSlider::add-page:horizontal {
            background: #FFFFFF;
            border-radius: 6px;
        }
        
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #44AADD;
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #F5F5F5;
        }
        
        QSlider::handle:horizontal:pressed {
            background: #E0E0E0;
        }
        """
    
    def _get_end_button_style(self):
        """获取结束按钮样式 - 红底白字"""
        return """
        QPushButton {
            background-color: #DC143C;
            color: white;
            border: 2px solid #B22222;
            border-radius: 5px;
            padding: 5px 10px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #FF1744;
            border-color: #DC143C;
        }
        QPushButton:pressed {
            background-color: #B71C1C;
            border-color: #8B0000;
        }
        """
    
    def _save_settings(self):
        """保存设置"""
        # 检查是否有变化
        has_changes = self.current_config.speed != self.original_config.speed
        
        if not has_changes:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "参数未发生变化，无需保存", fold_code="GEN_PARAM_DLG")
            QMessageBox.information(self, "提示", "参数没有变化，无需保存")
            return
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"成功保存语音参数设置，语速: {self.current_config.speed}%", fold_code="GEN_PARAM_DLG")
        self.accept()
    
    def get_config(self):
        """获取配置"""
        return self.current_config


class ParameterControl:
    """参数控制类"""
    
    def __init__(self, parent, name: str, display_name: str, min_val: int, max_val: int, 
                 callback: Callable, initial_value: int = 0):
        self.parent = parent
        self.name = name
        self.display_name = display_name
        self.min_val = min_val
        self.max_val = max_val
        self.callback = callback
        self.initial_value = initial_value
        
        self.slider = None
        self.label = None
        self.plus_button = None
        self.minus_button = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建控制组件"""
        # 创建标签
        self.label = QLabel(f"{self.display_name}: {self.initial_value}", self.parent)
        
        # 创建滑动条
        self.slider = QSlider(Qt.Horizontal, self.parent)
        self.slider.setRange(self.min_val, self.max_val)
        self.slider.setValue(self.initial_value)
        self.slider.valueChanged.connect(self.callback)
        self.slider.setStyleSheet(self._get_slider_style())
        
        # 创建+/-按钮
        self.plus_button = QPushButton('+', self.parent)
        self.plus_button.clicked.connect(lambda: self._adjust_value(1))
        self.plus_button.setStyleSheet(self._get_button_style())
        
        self.minus_button = QPushButton('-', self.parent)
        self.minus_button.clicked.connect(lambda: self._adjust_value(-1))
        self.minus_button.setStyleSheet(self._get_button_style())
    
    def _adjust_value(self, delta: int):
        """调整参数值"""
        current_value = self.slider.value()
        new_value = current_value + delta
        if self.min_val <= new_value <= self.max_val:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"通过按钮调整 {self.display_name}: {current_value} -> {new_value}", fold_code="GEN_PARAM_CTRL")
            self.slider.setValue(new_value)
    
    def update_display(self, value: int):
        """更新显示"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"更新 {self.display_name} 数值显示: {value}", fold_code="GEN_PARAM_CTRL")
        self.label.setText(f"{self.display_name}: {value}")
    
    def set_value(self, value: int):
        """设置参数值"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"手动设置 {self.display_name} 数值: {value}", fold_code="GEN_PARAM_CTRL")
        self.slider.setValue(value)
    
    def get_value(self) -> int:
        """获取参数值"""
        return self.slider.value()
    
    def _get_slider_style(self) -> str:
        """获取滑动条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
            height: 12px;
            background: #FFFFFF;
            border-radius: 6px;
        }
        
        QSlider::sub-page:horizontal {
            background: #44AADD;
            border-radius: 6px;
        }
        
        QSlider::add-page:horizontal {
            background: #FFFFFF;
            border-radius: 6px;
        }
        
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #44AADD;
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #F5F5F5;
        }
        
        QSlider::handle:horizontal:pressed {
            background: #E0E0E0;
        }
        """
    
    def _get_button_style(self) -> str:
        """获取按钮样式"""
        # 从父窗口获取全局字体设置
        global_font = self.parent.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        return f"""
            QPushButton {{
                font-family: "{global_font}"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #f0f0f0; }}
        """
    
    def update_font(self, font):
        """更新控件字体"""
        self.label.setFont(font)
        self.plus_button.setFont(font)
        self.minus_button.setFont(font)
        # 更新按钮样式以使用新字体
        self.plus_button.setStyleSheet(self._get_button_style())
        self.minus_button.setStyleSheet(self._get_button_style())


class VoiceSelection:
    """音色选择类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.combo_box = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建音色选择控件"""
        self.combo_box = QComboBox(self.parent)
        voices = VoiceConfig.get_voices()
        self.combo_box.addItems(voices)
        self.combo_box.setCurrentIndex(0)
        self.combo_box.currentIndexChanged.connect(self._update_voice)
        self.combo_box.setStyleSheet(self._get_combo_box_style())
    
    def _update_voice(self, index: int):
        """更新音色选择"""
        voice = self.combo_box.itemText(index)
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"音色选择已变更: {voice}", fold_code="GEN_VOICE_SEL")
        if hasattr(self.parent, 'config'):
            self.parent.config.voice = voice
        if hasattr(self.parent, '_check_inputs_and_update_button'):
            self.parent._check_inputs_and_update_button()
        if hasattr(self.parent, '_check_content_changed'):
            self.parent._check_content_changed()
        
        # 修复：音色改变时停止音频并重置状态
        if (hasattr(self.parent, 'parent_window') and 
            (self.parent.parent_window.is_playing or 
             self.parent.parent_window.audio_preview.is_paused)):
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "由于音色变更，强制停止当前播放任务", fold_code="GEN_VOICE_SEL")
            self.parent.parent_window.audio_preview.stop_audio()
            self.parent.parent_window.has_preview = False
            if hasattr(self.parent, 'preview_button'):
                self.parent.preview_button.setText("生成音频")
    
    def get_current_voice(self) -> str:
        """获取当前选中的音色"""
        return self.combo_box.currentText()
    
    def _get_combo_box_style(self) -> str:
        """获取下拉框样式"""
        global_font = self.parent.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        return """
            QComboBox {
                font-family: \""""+global_font+"""\"; background-color: white; color: black; 
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QComboBox::drop-down {
                border-left-width: 2px; border-left-color: gray; border-left-style: solid;
                border-top-right-radius: 10px; border-bottom-right-radius: 10px;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid black;
                width: 0px;
                height: 0px;
            }
            QComboBox:hover {
                background-color: #f0f0f0;
            }
        """
    
    def update_font(self, font):
        """更新控件字体"""
        self.combo_box.setFont(font)
        # 更新下拉框样式以使用新字体
        self.combo_box.setStyleSheet(self._get_combo_box_style())


class TextEditSection:
    """文本编辑区域类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.text_edit = None
        self.overlay_button = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建文本编辑控件"""
        self.text_edit = QTextEdit(self.parent)
        self.text_edit.textChanged.connect(self._update_content)
        self.text_edit.setStyleSheet("QTextEdit { background-color: white; color: black; border: 3px solid gray; border-radius: 10px; }")
        
        global_font = self.parent.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        text_edit_font = QFont(global_font, 9)
        self.text_edit.setFont(text_edit_font)
        
        # 创建缩窄的透明覆盖按钮（让开文本框滑动条）
        self.overlay_button = QPushButton(self.parent)
        self.overlay_button.setStyleSheet("QPushButton { background-color: transparent; border: none; }")
        self.overlay_button.clicked.connect(self._open_text_import_dialog)
    
    def _update_content(self):
        """更新文本内容"""
        content = self.text_edit.toPlainText()
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"主编辑框文本内容变更，新长度: {len(content)} 字符", fold_code="GEN_TEXT_EDIT")
        if hasattr(self.parent, 'config'):
            self.parent.config.content = content
        if hasattr(self.parent, '_check_inputs_and_update_button'):
            self.parent._check_inputs_and_update_button()
        if hasattr(self.parent, '_check_content_changed'):
            self.parent._check_content_changed()
    
    def _open_text_import_dialog(self):
        """打开文本导入对话框"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在通过覆盖层触发文本导入对话框", fold_code="GEN_TEXT_EDIT")
        # 获取主窗口的尺寸和位置
        main_window = self.parent.parent_window
        if main_window:
            # 创建窗口尺寸对象
            window_rect = main_window.geometry()
            
            # 获取当前文本框的内容
            current_text = self.text_edit.toPlainText()
            
            # 调用文本导入对话框，传入当前文本内容
            imported_text = show_text_import_dialog(self.parent, window_rect, current_text)
            
            # 如果用户确认了导入，更新文本框内容
            if imported_text is not None:  # 明确检查是否为None
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"已从对话框导入文本，长度: {len(imported_text)}", fold_code="GEN_TEXT_EDIT")
                self.text_edit.setPlainText(imported_text)
                self._update_content()  # 触发内容更新
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "取消文本导入操作", fold_code="GEN_TEXT_EDIT")
    
    def set_text(self, text: str):
        """设置文本内容"""
        self.text_edit.setPlainText(text)
    
    def get_text(self) -> str:
        """获取文本内容"""
        return self.text_edit.toPlainText()
    
    def update_font(self, font):
        """更新控件字体"""
        self.text_edit.setFont(font)


class PreviewControl:
    """音频控制类"""
    
    def __init__(self, parent):
        self.parent = parent
        
        self.preview_button = None
        self.preview_progress = None
        self.volume_slider = None  # 新增音量控制
        self.volume_label = None   # 新增音量显示
        self.volume_value_label = None  # 新增音量数值显示
        
        self.is_seeking = False
        
        self._create_controls()
    
    def _create_controls(self):
        """创建音频控制控件"""
        # 生成/播放音频按钮
        self.preview_button = QPushButton('生成音频', self.parent)
        self.preview_button.clicked.connect(self._handle_preview_button)
        self.preview_button.setStyleSheet(self._get_button_style("rgb(0, 100, 200)", "rgb(0, 120, 220)"))
        
        # 下一句和停止按钮已移除，功能整合到生成音频按钮中
        
        # 横向进度条
        self.preview_progress = QSlider(Qt.Horizontal, self.parent)
        self.preview_progress.setRange(0, 1000)
        self.preview_progress.setValue(0)
        self.preview_progress.sliderPressed.connect(self._on_progress_pressed)
        self.preview_progress.sliderReleased.connect(self._on_progress_released)
        self.preview_progress.valueChanged.connect(self._on_progress_changed)
        self.preview_progress.setStyleSheet(self._get_progress_style())
        
        # 新增：音量控制
        self._create_volume_controls()
    
    def _create_volume_controls(self):
        """创建音量控制控件"""
        # 结束本次听写按钮
        self.end_dictation_button = QPushButton("结束本次听写", self.parent)
        self.end_dictation_button.clicked.connect(self._end_dictation)
        self.end_dictation_button.setStyleSheet(self._get_end_button_style())
        
        # 音量标签
        self.volume_label = QLabel("音量", self.parent)
        self.volume_label.setAlignment(Qt.AlignCenter)
        
        # 音量滑动条
        self.volume_slider = QSlider(Qt.Horizontal, self.parent)
        self.volume_slider.setRange(0, 100)  # 0-100%
        self.volume_slider.setValue(100)     # 默认100%
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_slider.setStyleSheet(self._get_volume_slider_style())
        
        # 音量数值显示
        self.volume_value_label = QLabel("100%", self.parent)
        self.volume_value_label.setAlignment(Qt.AlignCenter)
    
    def _end_dictation(self):
        """结束本次听写 - 重置所有元素到初始状态"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在结束本次听写并重置状态...", fold_code="GEN_PREVIEW_CTRL")
        try:
            # 停止音频播放并断开信号连接
            if hasattr(self.parent, 'parent_window') and hasattr(self.parent.parent_window, 'audio_preview'):
                self.parent.parent_window.audio_preview.stop_audio()
                # 断开播放完成信号，防止结束后仍然触发回调
                try:
                    self.parent.parent_window.audio_preview.audio_signals.playback_finished.disconnect(self._on_sentence_playback_complete)
                except:
                    pass  # 如果连接不存在，忽略错误
            
            # 重置播放状态
            self.is_playing = False
            self.is_paused = False
            self.is_seeking = False
            self.current_audio_position = 0
            self.current_audio_length = 0
            self.current_audio_path = None
            
            # 重置进度条
            self.preview_progress.setValue(0)
            self.preview_progress.setEnabled(False)
            
            # 重置按钮状态
            self.preview_button.setText("生成音频")
            self.preview_button.setEnabled(True)
            
            # 重置音量到默认值
            self.volume_slider.setValue(100)
            
            # 重置句子管理器状态
            if hasattr(self.parent, 'sentence_manager'):
                self.parent.sentence_manager.current_sentence_index = 0
                self.parent.sentence_manager.audio_files.clear()
                self.parent.sentence_manager.audio_durations.clear()
                self.parent.sentence_manager.total_duration = 0.0
                self.parent.sentence_manager.is_generating = False
                self.parent.sentence_manager.generation_queue.clear()
                self.parent.sentence_manager.play_retry_count.clear()
            
            # 重置父窗口状态
            if hasattr(self.parent, 'parent_window'):
                self.parent.parent_window.has_preview = False
                self.parent.parent_window.is_playing = False
                self.parent.parent_window.is_paused = False
                self.parent.parent_window.current_audio_length = 0
                self.parent.parent_window.current_audio_position = 0
                self.parent.parent_window.current_audio_path = None
                self.parent.parent_window.audio_cache.clear()
            
            # 清空句子预览框
            if hasattr(self.parent, 'prev_sentence_label'):
                self.parent.prev_sentence_label.setText("")
                self.parent.current_sentence_label.setText("")
                self.parent.next_sentence_label.setText("")
                self.parent.next_next_sentence_label.setText("")
            
            # 重置文本内容（可选 - 保留当前文本但清除生成状态）
            # self.parent.text_edit.clear()  # 如果需要清空文本内容
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "听写已结束，所有元素已重置到初始状态", fold_code="GEN_PREVIEW_CTRL")
            
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"结束听写时发生错误: {str(e)}", fold_code="GEN_PREVIEW_CTRL")
    
    def _on_volume_changed(self, value: int):
        """音量改变事件"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"音量调整 -> {value}%", fold_code="GEN_AUDIO_VOL")
        if hasattr(self.parent, 'parent_window'):
            # 转换为 0.0-1.0 的范围
            volume = value / 100.0
            success = self.parent.parent_window.audio_preview.set_volume(volume)
            
            # 更新音量显示
            if success:
                debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"已成功设置音量为: {volume}", fold_code="GEN_AUDIO_VOL")
                self.volume_value_label.setText(f"{value}%")
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "音量设置失败", fold_code="GEN_AUDIO_VOL")
    
    def _handle_preview_button(self):
        """处理音频按钮点击"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"音频控制按钮被点击 - 当前文本: '{self.preview_button.text()}'", fold_code="GEN_PREVIEW_BTN")
        # 如果按钮被禁用或正在播放，不处理点击事件
        if not self.preview_button.isEnabled() or self.preview_button.text() == "正在播放这一句":
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "按钮状态无效或正处于播放锁定状态，忽略点击", fold_code="GEN_PREVIEW_BTN")
            return
            
        # 如果按钮显示为"播放这一句"，则执行这一句功能
        if self.preview_button.text() == "播放这一句":
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "执行 '播放这一句' 功能", fold_code="GEN_PREVIEW_BTN")
            if hasattr(self.parent, 'handle_next_sentence'):
                self.parent.handle_next_sentence()
        # 如果按钮显示为"播放下一句"，则执行下一句功能，然后变回"播放这一句"
        elif self.preview_button.text() == "播放下一句":
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "执行 '播放下一句' 功能", fold_code="GEN_PREVIEW_BTN")
            if hasattr(self.parent, 'handle_next_sentence'):
                self.parent.handle_next_sentence()
                # 执行完后变回"播放这一句"
                self.preview_button.setText("播放这一句")
        elif (hasattr(self.parent, 'parent_window') and 
              self.parent.parent_window.has_preview and 
              self.parent._is_content_unchanged()):
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "内容未变化且已有音频，直接开始播放预览", fold_code="GEN_PREVIEW_BTN")
            self.parent.parent_window.audio_preview.play_preview()
        else:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "条件满足，开始生成新音频流", fold_code="GEN_PREVIEW_BTN")
            self.parent._generate_preview_audio()
    
    def _handle_next_sentence(self):
        """处理下一句按钮点击"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "用户点击 '下一句' 按钮", fold_code="GEN_PREVIEW_BTN")
        if hasattr(self.parent, 'handle_next_sentence'):
            self.parent.handle_next_sentence()
    
    def _stop_audio(self):
        """停止音频播放"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "用户点击 '停止' 按钮", fold_code="GEN_PREVIEW_BTN")
        if hasattr(self.parent, 'parent_window'):
            self.parent.parent_window.audio_preview.stop_audio()
    
    def _on_progress_pressed(self):
        """进度条按下事件"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "音频进度条被按下，开始跳转操作", fold_code="GEN_AUDIO_SEEK")
        if hasattr(self.parent, 'parent_window'):
            self.parent.parent_window.audio_preview.set_seeking(True)
    
    def _on_progress_released(self):
        """进度条释放事件"""
        if (hasattr(self.parent, 'parent_window') and 
            self.parent.parent_window.is_playing):
            
            # 获取进度百分比
            percentage = self.preview_progress.value() / 1000.0
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"进度条已释放，跳转至: {percentage*100:.2f}%", fold_code="GEN_AUDIO_SEEK")
            self.parent.parent_window.audio_preview.seek_to_percentage(percentage)
        else:
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "非播放状态下释放进度条，不执行跳转动作", fold_code="GEN_AUDIO_SEEK")
    
    def _on_progress_changed(self, value: int):
        """进度条值改变事件"""
        if (hasattr(self.parent, 'parent_window') and 
            self.parent.parent_window.audio_preview.is_seeking and 
            self.parent.parent_window.is_playing):
            # 实时更新显示，但不实际跳转（等待释放）
            pass
    
    def update_preview_button_state(self, has_preview: bool, content_unchanged: bool):
        """更新音频按钮状态"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"更新音频按钮状态 (has_preview={has_preview}, unchanged={content_unchanged})", fold_code="GEN_PREVIEW_BTN")
        if has_preview and content_unchanged:
            self.preview_button.setText("开始听写！")
        else:
            self.preview_button.setText("生成音频")
    
    def set_playback_controls_enabled(self, playing: bool):
        """设置播放控制按钮状态"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"设置播放控制启用状态: {not playing}", fold_code="GEN_PREVIEW_BTN")
        self.preview_button.setEnabled(not playing)
        # 下一句和停止按钮已移除
    
    def _get_button_style(self, normal_color: str, hover_color: str) -> str:
        """获取按钮样式"""
        global_font = self.parent.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        return f"""
            QPushButton {{
                font-family: "{global_font}"; background-color: {normal_color}; color: white;
                border: 2px solid gray; border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """
    
    def _get_end_button_style(self):
        """获取结束按钮样式 - 红底白字"""
        global_font = self.parent.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        return f"""
        QPushButton {{
            font-family: "{global_font}"; background-color: #DC143C; color: white;
            border: 2px solid #B22222; border-radius: 5px; font-weight: bold;
            padding: 5px 10px;
        }}
        QPushButton:hover {{ background-color: #FF1744; border-color: #DC143C; }}
        QPushButton:pressed {{ background-color: #B71C1C; border-color: #8B0000; }}
        """
    
    def update_font(self, font):
        """更新控件字体"""
        self.preview_button.setFont(font)
        self.volume_label.setFont(font)
        self.volume_value_label.setFont(font)
        self.end_dictation_button.setFont(font)
        # 更新按钮样式以使用新字体
        self.preview_button.setStyleSheet(self._get_button_style("rgb(0, 100, 200)", "rgb(0, 120, 220)"))
        self.end_dictation_button.setStyleSheet(self._get_end_button_style())
    
    def _get_progress_style(self) -> str:
        """获取进度条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
            height: 18px;
            background: #FFFFFF;
            border-radius: 9px;
        }
        
        QSlider::sub-page:horizontal {
            background: #4CAF50;
            border-radius: 9px;
        }
        
        QSlider::add-page:horizontal {
            background: #FFFFFF;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #4CAF50;
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #F5F5F5;
        }
        
        QSlider::handle:horizontal:pressed {
            background: #E0E0E0;
        }
        """
    
    def _get_volume_slider_style(self):
        """获取音量滑动条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
            height: 12px;
            background: #FFFFFF;
            border-radius: 6px;
        }
        
        QSlider::sub-page:horizontal {
            background: #FFA500;
            border-radius: 6px;
        }
        
        QSlider::add-page:horizontal {
            background: #FFFFFF;
            border-radius: 6px;
        }
        
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #FFA500;
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #F5F5F5;
        }
        
        QSlider::handle:horizontal:pressed {
            background: #E0E0E0;
        }
        """


class GenerationControl:
    """生成控制类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.button = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建生成控制控件"""
        self.button = QPushButton('生成并保存音频', self.parent)
        self.button.clicked.connect(self._generate_audio)
        # 初始设置为红色
        self._set_button_style(is_error=True)
    
    def _generate_audio(self):
        """生成音频文件"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "点击'生成并保存音频'按钮", fold_code="GEN_AUDIO")
        if hasattr(self.parent, '_generate_audio'):
            self.parent._generate_audio()
    
    def set_button_state(self, is_error: bool, text: str = None):
        """设置按钮状态"""
        self._set_button_style(is_error)
        if text:
            self.button.setText(text)
    
    def set_enabled(self, enabled: bool):
        """设置按钮启用状态"""
        self.button.setEnabled(enabled)
    
    def _set_button_style(self, is_error: bool = False):
        """设置按钮样式"""
        # 获取全局字体设置
        global_font = self.parent.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        
        if is_error:
            style = f"""
                QPushButton {{
                    font-family: "{global_font}"; background-color: red; color: white;
                    border: 2px solid gray; border-radius: 10px;
                }}
                QPushButton:hover {{ background-color: darkred; }}
            """
        else:
            style = f"""
                QPushButton {{
                    font-family: "{global_font}"; background-color: rgb(0, 150, 0); color: white;
                    border: 2px solid gray; border-radius: 10px;
                }}
                QPushButton:hover {{ background-color: rgb(0, 180, 0); }}
            """
        self.button.setStyleSheet(style)
    
    def update_font(self, font):
        """更新控件字体"""
        self.button.setFont(font)
        # 更新按钮样式以使用新字体
        # 保持当前的错误状态
        self._set_button_style()


class GenerationPage(QWidget):
    """生成页面"""
    
    # 位置偏移常量，用于统一管理布局偏移值
    POSITION_OFFSET_N = 0.27  # 位置偏移值，单位为n
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = parent.config if parent else AudioConfig()
        self.signals = GenerationSignals()
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在初始化 GenerationPage (听写页面)...", fold_code="GEN_INIT")
        
        # 获取共享内存管理器
        self.shared_manager = get_shared_memory_manager()
        
        # 初始化文字颜色和背景颜色
        self.text_color = self.parent_window.settings_manager.get_Custom_value('text_color', '#333333')
        self.background_color = self.parent_window.settings_manager.get_Custom_value('background_color', '#E5E8EF')
        
        # 初始化组件
        self._init_components()
        self._connect_signals()
        self._connect_shared_memory_signals()
        
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "GenerationPage 初始化完成", fold_code="GEN_INIT")
    
    def _get_debug_prefix(self):
        """获取调试输出前缀 [GPN hh-mm-dd]"""
        current_time = time.strftime("%H-%M-%d")
        return f"[GPN {current_time}]"
    
    def _jump_to_sentence(self, offset):
        """跳转到指定偏移位置的句子"""
        if not hasattr(self, 'sentence_manager') or not self.sentence_manager.sentences:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "尝试跳转句子但没有句子数据", fold_code="GEN_NAV")
            return
        
        current_idx = self.sentence_manager.current_sentence_index
        target_idx = current_idx + offset
        
        # 检查目标索引是否有效
        if 0 <= target_idx < len(self.sentence_manager.sentences):
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"跳转句子: {target_idx} (当前: {current_idx}, 偏移: {offset})", fold_code="GEN_NAV")
            
            # 更新当前句子索引
            self.sentence_manager.current_sentence_index = target_idx
            
            # 更新句子预览
            self.update_sentence_preview()
            
            # 更新进度条 (范围0-1000)
            progress_percentage = ((target_idx + 1) / len(self.sentence_manager.sentences)) * 100
            progress_value = int(progress_percentage * 10)
            self.preview_control.preview_progress.setValue(progress_value)
            
            # 检查目标句子的音频是否已生成
            audio_file = self.sentence_manager.audio_files.get(target_idx)
            if audio_file and os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                # 如果音频已存在，直接播放
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"句子 {target_idx} 音频就绪，直接播放: {audio_file}", fold_code="GEN_NAV")
                self._play_current_sentence()
            else:
                # 如果音频不存在，提示用户
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"句子 {target_idx} 音频缺失或尚未生成", fold_code="GEN_NAV")
                QMessageBox.information(self, "提示", f"第 {target_idx + 1} 句音频尚未生成，请先生成音频")
        else:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"跳转越界: 目标索引 {target_idx} (范围: 0-{len(self.sentence_manager.sentences)-1})", fold_code="GEN_NAV")
        
    def _init_components(self):
        """初始化所有组件"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "正在初始化子组件...", fold_code="GEN_INIT")
        # 创建参数控制 - 移除语速、语调、音量控制
        self.parameter_controls = {}
        
        # 创建句子分割器和音频管理器
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "创建分割器与音频管理器", fold_code="GEN_INIT")
        self.sentence_splitter = SentenceSplitter()
        self.sentence_manager = SentenceAudioManager()

        # 创建提示控件 (必须在 resizeEvent 之前初始化，因为 resizeEvent 会在页面显示时被调用)
        self._create_hint_controls()

        # 创建其他组件
        self.voice_selection = VoiceSelection(self)
        self.text_edit_section = TextEditSection(self)
        self.preview_control = PreviewControl(self)
        
        # 创建句子内容预览控件
        self._create_sentence_preview_controls()
        
        # 创建停顿设置按钮
        self.pause_settings_button = QPushButton('停顿设置', self)
        self.pause_settings_button.clicked.connect(self._show_pause_settings)
        self.pause_settings_button.setStyleSheet(self._get_pause_settings_button_style())
        
        # 创建参数设置按钮
        self.param_settings_button = QPushButton('参数设置', self)
        self.param_settings_button.clicked.connect(self._show_param_settings)
        self.param_settings_button.setStyleSheet(self._get_param_settings_button_style())
        
    def _create_hint_controls(self):
        """创建提示控件"""
        self.checkbox = QCheckBox(self)
        self.hint_label = QLabel("提示1", self)

    def _connect_signals(self):
        """连接内部信号"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "建立内部信号槽连接", fold_code="GEN_INIT")
        self.signals.generation_complete.connect(self._on_generation_complete_safe)
        self.signals.update_button_state.connect(self._update_button_state_safe)
        self.signals.sentence_generated.connect(self._on_sentence_generated)
        self.signals.all_sentences_complete.connect(self._on_all_sentences_complete)
        self.signals.playback_ready.connect(self._on_playback_ready)

    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "建立共享内存信号连接", fold_code="GEN_INIT")
        if self.shared_manager:
            self.shared_manager.hotkey_triggered.connect(self._on_hotkey_triggered)
        
    def _create_sentence_preview_controls(self):
        """创建句子内容预览控件"""
        # 创建四个句子标签
        self.prev_sentence_label = QLabel("", self)
        self.current_sentence_label = QLabel("", self)
        self.next_sentence_label = QLabel("", self)
        self.next_next_sentence_label = QLabel("", self)
        
        # 创建四个跳转按钮
        self.prev_jump_button = QPushButton("播放", self)
        self.current_jump_button = QPushButton("播放", self)
        self.next_jump_button = QPushButton("播放", self)
        self.next_next_jump_button = QPushButton("播放", self)
        
        # 设置跳转按钮样式
        self._setup_jump_button_styles()
        
        # 连接跳转按钮信号
        self.prev_jump_button.clicked.connect(lambda: self._jump_to_sentence(-1))
        self.current_jump_button.clicked.connect(lambda: self._jump_to_sentence(0))
        self.next_jump_button.clicked.connect(lambda: self._jump_to_sentence(1))
        self.next_next_jump_button.clicked.connect(lambda: self._jump_to_sentence(2))
        
        # 设置样式
        self._setup_sentence_preview_styles()
        
    def update_sentence_preview(self):
        """更新句子内容预览"""
        if not hasattr(self, 'sentence_manager') or not self.sentence_manager.sentences:
            # 清空预览内容
            self.prev_sentence_label.setText("")
            self.current_sentence_label.setText("")
            self.next_sentence_label.setText("")
            self.next_next_sentence_label.setText("")
            return
        
        sentences = self.sentence_manager.sentences
        current_idx = self.sentence_manager.current_sentence_index
        
        # 获取上下文句子
        prev_text = sentences[current_idx - 1] if current_idx > 0 else ""
        current_text = sentences[current_idx] if current_idx < len(sentences) else ""
        next_text = sentences[current_idx + 1] if current_idx + 1 < len(sentences) else ""
        next_next_text = sentences[current_idx + 2] if current_idx + 2 < len(sentences) else ""
        
        # 更新标签内容
        self.prev_sentence_label.setText(prev_text)
        self.current_sentence_label.setText(current_text)
        self.next_sentence_label.setText(next_text)
        self.next_next_sentence_label.setText(next_next_text)
        
        # 调试输出
        debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"更新句子预览 -> 索引: {current_idx}, 文本: '{current_text[:20]}...'", fold_code="GEN_NAV")

    def _update_sentence_preview_fonts(self, font):
        """更新句子预览控件字体"""
        # 应用字体到所有句子预览标签
        self.prev_sentence_label.setFont(font)
        self.current_sentence_label.setFont(font)
        self.next_sentence_label.setFont(font)
        self.next_next_sentence_label.setFont(font)
        
        # 应用字体到跳转按钮
        self.prev_jump_button.setFont(font)
        self.current_jump_button.setFont(font)
        self.next_jump_button.setFont(font)
        self.next_next_jump_button.setFont(font)
        
        # 重新应用样式以确保字体设置生效
        self._setup_sentence_preview_styles()
        self._setup_jump_button_styles()
    
    def _setup_sentence_preview_styles(self):
        """设置句子预览样式"""
        # 获取用户设置的字体
        global_font = self.parent_window.settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        # 计算动态字体大小（使用与音量提示文本相同的算法）
        if self.parent_window:
            current_width = self.parent_window.width()
            current_height = self.parent_window.height()
            
            min_font_size = 22
            max_font_size = 42
            default_width = 1080
            default_height = 720
            
            width_ratio = current_width / default_width
            height_ratio = current_height / default_height
            ratio = (width_ratio + height_ratio) / 2
            
            base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
            preview_font_size = max(min_font_size, min(max_font_size, base_font_size))
            preview_font_size = int(preview_font_size * 0.8)  # 句子预览字体放大到原先的两倍（从0.4改为0.8）
        else:
            preview_font_size = 12  # 默认字体大小
        
        # 整体背景样式 - 暗白色圆角背景
        preview_bg_style = f"""
            QLabel {{
                font-family: "{global_font}";
                background-color: rgba(240, 240, 240, 200);
                border-radius: 8px;
                padding: 4px;
                font-size: {preview_font_size}px;
                color: {self.text_color};
            }}
        """
        
        # 当前句子样式 - 浅绿色圆角背景
        current_style = f"""
            QLabel {{
                font-family: "{global_font}";
                background-color: rgba(144, 238, 144, 180);
                border-radius: 6px;
                padding: 4px;
                font-size: {preview_font_size}px;
                color: {self.text_color};
                font-weight: bold;
            }}
        """
        
        # 分割线样式
        separator_style = """
            QLabel {
                background-color: rgba(200, 200, 200, 150);
                min-height: 1px;
                max-height: 1px;
            }
        """
        
        # 应用样式
        self.prev_sentence_label.setStyleSheet(preview_bg_style)
        self.current_sentence_label.setStyleSheet(current_style)
        self.next_sentence_label.setStyleSheet(preview_bg_style)
        self.next_next_sentence_label.setStyleSheet(preview_bg_style)
        
        # 设置文本对齐
        for label in [self.prev_sentence_label, self.current_sentence_label, 
                     self.next_sentence_label, self.next_next_sentence_label]:
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setWordWrap(True)
    
    def _setup_jump_button_styles(self):
        """设置跳转按钮样式"""
        # 获取用户设置的字体
        global_font = self.parent_window.settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        # 计算动态字体大小（与句子预览字体大小相同）
        if self.parent_window:
            current_width = self.parent_window.width()
            current_height = self.parent_window.height()
            
            min_font_size = 22
            max_font_size = 42
            default_width = 1080
            default_height = 720
            
            width_ratio = current_width / default_width
            height_ratio = current_height / default_height
            ratio = (width_ratio + height_ratio) / 2
            
            base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
            button_font_size = max(min_font_size, min(max_font_size, base_font_size))
            button_font_size = int(button_font_size * 0.8)  # 与句子预览字体大小一致
        else:
            button_font_size = 12
        
        # 跳转按钮样式
        jump_button_style = f"""
            QPushButton {{
                font-family: "{global_font}";
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: {button_font_size}px;
                font-weight: bold;
                min-width: 50px;
                max-width: 60px;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
            QPushButton:pressed {{
                background-color: #1565C0;
            }}
        """
        
        # 应用样式到所有跳转按钮
        for button in [self.prev_jump_button, self.current_jump_button, 
                      self.next_jump_button, self.next_next_jump_button]:
            button.setStyleSheet(jump_button_style)
    
    def _create_hint_controls(self):
        """创建提示控件"""
        self.checkbox = QCheckBox(self)
        self.hint_label = QLabel("提示1", self)
        
    def _connect_signals(self):
        """连接信号槽"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在连接 GenerationPage 信号...", fold_code="GEN_INIT")
        self.signals.generation_complete.connect(self._on_generation_complete_safe)
        self.signals.preview_generated.connect(self._on_preview_generated_safe)
        self.signals.preview_error.connect(self._handle_preview_error_safe)
        self.signals.update_button_state.connect(self._update_button_state_safe)
        
        # 连接新的信号
        self.signals.sentence_generated.connect(self._on_sentence_generated_safe)
        self.signals.all_sentences_complete.connect(self._on_all_sentences_complete_safe)
        self.signals.playback_ready.connect(self._on_playback_ready_safe)

        # 连接音频预览的热键信号
        if hasattr(self.parent_window, 'audio_preview'):
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "连接 audio_preview 热键信号", fold_code="GEN_INIT")
            self.parent_window.audio_preview.audio_signals.next_sentence_requested.connect(self._on_hotkey_next_sentence)
            self.parent_window.audio_preview.audio_signals.prev_sentence_requested.connect(self._on_hotkey_prev_sentence)
        else:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "parent_window 没有 audio_preview 属性，跳过热键连接", fold_code="GEN_INIT")

    def _on_hotkey_next_sentence(self):
        """响应热键：下一句"""
        # 仅当当前页面在活动状态时响应
        if self.isVisible():
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "热键触发: 下一句", fold_code="GEN_HOTKEY")
            self._play_next_sentence()

    def _on_hotkey_prev_sentence(self):
        """响应热键：上一句"""
        # 仅当当前页面在活动状态时响应
        if self.isVisible():
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "热键触发: 上一句", fold_code="GEN_HOTKEY")
            self._play_prev_sentence()
    
    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "连接共享内存信号", fold_code="GEN_INIT")
        # 连接字体更改信号
        self.shared_manager.font_changed.connect(self._on_font_changed_from_shared_memory)
        # 连接主题更改信号
        self.shared_manager.theme_changed.connect(self._on_theme_changed_from_shared_memory)
        # 连接窗口尺寸更改信号
        self.shared_manager.window_size_changed.connect(self._on_window_size_changed_from_shared_memory)
        # 连接设置更改信号
        self.shared_manager.settings_changed.connect(self._on_settings_changed_from_shared_memory)
        
    def resizeEvent(self, event):
        """处理页面大小变化事件"""
        width = self.width()
        height = self.height()
        
        # 计算渲染区宽度（选项卡栏右边界到窗口右边界）
        # 选项卡栏宽度为窗口宽度的10%
        tab_bar_width = int((width + 10) / 0.9 * 0.1)  # 根据content_width反推tab_bar_width
        render_area_width = width
        
        # 计算 n 和 m 值（以渲染区为参考）
        n = render_area_width / 16
        m = height / 16
        offset_m = m

        # 布局开关和提示文本
        checkbox_size = 20
        self.checkbox.setGeometry(int(GenerationPage.POSITION_OFFSET_N * n), int(0 * m - offset_m), checkbox_size, checkbox_size)
        self.hint_label.setGeometry(int((GenerationPage.POSITION_OFFSET_N + 1) * n), int(0 * m - offset_m), int(2 * n), int(m))

        # 布局水平滑动条及±按钮 - 右半侧元素左边界向右移动0.25n，并缩窄以让出右侧10px
        slider_height = int(0.8 * m)
        button_size = int(0.8 * m)
        
        # 右半侧元素左边界偏移量
        right_offset = int(0.25 * n)
        
        # 计算缩放因子，让出右侧10px空间
        scale_factor = (width - 10) / width
        
        # 移除语速、音调控件布局
        # 音量控件保留（音频控制中的音量）
        volume_y = int(6 * m - offset_m)
        # self._layout_parameter_control('volume', volume_y, right_offset, scale_factor, n, m, button_size, slider_height)

        # 布局文本编辑框 - 左边界向左移动2n，并缩窄
        text_edit_x = int(GenerationPage.POSITION_OFFSET_N * n)  # 从2*n改为0*n
        text_edit_y = int(2 * m - offset_m)
        text_edit_width = int(8 * n * scale_factor)  # 宽度增加2n以保持右边界不变，并缩窄
        text_edit_height = int(11 * m)  # 高度减小，为底部控件让出空间
        self.text_edit_section.text_edit.setGeometry(text_edit_x, text_edit_y, text_edit_width, text_edit_height)
        
        # 布局缩窄的透明覆盖按钮，让开文本框滑动条
        # 宽度减少20像素以让开滑动条，位置向右偏移
        overlay_width = text_edit_width - 20  # 缩窄宽度
        self.text_edit_section.overlay_button.setGeometry(text_edit_x, text_edit_y, overlay_width, text_edit_height)

        # 计算生成音频按钮位置 - 使其下边界与文本框持平
        # 文本框下边界: text_edit_y + text_edit_height
        # 按钮高度保持3*m
        button_height = int(3 * m)
        # 按钮下边界 = 文本框下边界
        buttons_bottom = text_edit_y + text_edit_height
        # 按钮y位置 = 下边界 - 按钮高度
        buttons_y = buttons_bottom - button_height
        
        # 布局"生成音频"按钮 - 现在占据整个按钮区域
        buttons_left = int((8.1 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset
        buttons_right = int(14.9 * n * scale_factor) + button_size + right_offset
        button_width = buttons_right - buttons_left
        
        self.preview_control.preview_button.setGeometry(buttons_left, buttons_y, button_width, button_height)

        # 音色选择栏位置 - 放在生成音频按钮上方，间隔0.5n
        # 可以修改这一行的间隔值：0.5n 是间隔，voice_combo_height是选择框高度
        voice_combo_height = int(m)
        voice_combo_y = buttons_y - voice_combo_height - int(0.35 * n)  # 0.5n间隔
        
        # 布局下拉框 - 使用与其他元素相同的布局方式
        voice_combo_x = int((8.1 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset
        voice_combo_width = buttons_right - voice_combo_x  # 宽度与按钮区域一致
        self.voice_selection.combo_box.setGeometry(voice_combo_x, voice_combo_y, voice_combo_width, voice_combo_height)
        
        # 句子内容预览 - 放在停顿设置按钮上方，整体高度约4行文本
        preview_height = int(4 * m)  # 四行文本高度
        pause_settings_height = int(m)
        pause_settings_y = voice_combo_y - pause_settings_height - int(0.6 * n)  # 停顿设置按钮位置，上方空出0.5n间隔
        preview_y = pause_settings_y - preview_height - int(0.6 * n)  # 在停顿设置按钮上方0.5n处
        preview_x = voice_combo_x
        
        # 计算预览区域宽度：原宽度减去跳转按钮区域（拉宽到约120px）
        jump_button_width = 90  # 每个跳转按钮宽度拉宽到90px
        jump_button_spacing = 5  # 按钮间距
        total_jump_width = jump_button_width + jump_button_spacing  # 总跳转区域宽度
        preview_width = voice_combo_width - total_jump_width  # 句子预览新宽度
        
        # 布局四个句子标签 - 第二行（当前句）高度为1.5倍
        normal_line_height = preview_height // 4
        current_line_height = int(normal_line_height * 1.5)  # 当前句高度为1.5倍
        separator_height = 1
        
        # 上一句（正常高度）
        self.prev_sentence_label.setGeometry(preview_x, preview_y, preview_width, normal_line_height - separator_height)
        
        # 这一句（浅绿色背景，1.5倍高度）
        current_y = preview_y + normal_line_height
        self.current_sentence_label.setGeometry(preview_x, current_y, preview_width, current_line_height - separator_height)
        
        # 下一句（正常高度）
        next_y = current_y + current_line_height
        self.next_sentence_label.setGeometry(preview_x, next_y, preview_width, normal_line_height - separator_height)
        
        # 下下一句（正常高度，调整位置以补偿当前句的额外高度）
        next_next_y = next_y + normal_line_height
        self.next_next_sentence_label.setGeometry(preview_x, next_next_y, preview_width, normal_line_height)
        
        # 布局跳转按钮 - 在句子预览右侧
        jump_button_x = preview_x + preview_width + jump_button_spacing
        jump_button_height = normal_line_height - separator_height
        
        # 上一句跳转按钮
        self.prev_jump_button.setGeometry(jump_button_x, preview_y, jump_button_width, jump_button_height)
        
        # 当前句跳转按钮（1.5倍高度）
        self.current_jump_button.setGeometry(jump_button_x, current_y, jump_button_width, current_line_height - separator_height)
        
        # 下一句跳转按钮
        self.next_jump_button.setGeometry(jump_button_x, next_y, jump_button_width, jump_button_height)
        
        # 下下一句跳转按钮
        self.next_next_jump_button.setGeometry(jump_button_x, next_next_y, jump_button_width, normal_line_height)
        
        # 布局停顿设置按钮 - 宽度减半，保持左边界不变
        pause_settings_width = voice_combo_width // 2  # 宽度减半
        self.pause_settings_button.setGeometry(voice_combo_x, pause_settings_y, pause_settings_width, pause_settings_height)
        
        # 布局参数设置按钮 - 在停顿设置按钮右侧
        param_settings_x = voice_combo_x + pause_settings_width + int(0.5 * n)  # 右侧添加间距
        param_settings_width = voice_combo_width - pause_settings_width - int(0.5 * n)  # 剩余宽度
        self.param_settings_button.setGeometry(param_settings_x, pause_settings_y, param_settings_width, pause_settings_height)

        # 播放进度条和下一句停止键下移至播放进度条下边界距离窗口下边界0.25m
        # 窗口下边界: 16*m - offset_m
        # 播放进度条下边界: (16*m - offset_m) - 0.25*m = 15.75*m - offset_m
        progress_bottom = int(15.75 * m - offset_m)
        progress_height = int(m)
        progress_y = progress_bottom - progress_height
        
        # 进度条 - 左边界向左移动2n，与文本框对齐，并缩窄
        progress_x = int(GenerationPage.POSITION_OFFSET_N * n)  # 从2*n改为0*n
        # 进度条右边界与生成按钮右边界对齐
        progress_right = buttons_right
        progress_width = progress_right - progress_x
        self.preview_control.preview_progress.setGeometry(progress_x, progress_y, progress_width, progress_height)
        
        # 下一句和停止按钮 - 在进度条上方，高度缩窄为原先的2/3
        control_button_height = int(1.0 * m)  # 从1.5*m改为1.0*m (2/3)
        control_button_width = int(2 * n * scale_factor)
        
        # 计算居中位置
        total_control_buttons_width = 2 * control_button_width
        control_buttons_start_x = progress_x + (progress_width - total_control_buttons_width) // 2
        control_buttons_y = progress_y - control_button_height
        
        # 下一句和停止按钮布局已移除
        
        # 新增：布局音量控制 - 移动到进度条上方居中位置
        self._layout_volume_controls(width, height, n, m, scale_factor, right_offset, progress_y, control_buttons_y, control_button_height)

        # 更新字体
        self._update_fonts()
        
        # 更新跳转按钮样式（响应窗口大小变化）
        self._setup_jump_button_styles()
    
    def _on_font_changed_from_shared_memory(self, font_data):
        """从共享内存接收字体更改"""
        try:
            # 更新字体设置
            if hasattr(self, '_update_fonts'):
                self._update_fonts()
            # 字体更新成功
        except Exception as e:
            # 字体更新失败处理
            pass
    
    def _on_theme_changed_from_shared_memory(self, theme_data):
        """从共享内存接收主题更改"""
        try:
            # 应用背景颜色
            bg_color = theme_data.get('background_color', '#E5E8EF')
            self.setStyleSheet(f"""
                QWidget {{ background-color: {bg_color}; }}
                QLabel {{ background-color: transparent; }}
            """)
            # 主题更新成功
        except Exception as e:
            # 主题更新失败处理
            pass
    
    def _on_window_size_changed_from_shared_memory(self, width, height):
        """从共享内存接收窗口尺寸更改"""
        try:
            # 重新布局控件
            if hasattr(self, 'resizeEvent'):
                # 触发重新布局
                self.resize(self.width(), self.height())
            # 窗口尺寸更新成功
        except Exception as e:
            # 窗口尺寸更新失败处理
            pass
    
    def _on_sentence_generated_safe(self, sentence_index: int, audio_file: str, duration: float):
        """安全处理句子生成完成信号"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"接收到句子 {sentence_index} 生成完成信号 -> 文件: {audio_file}, 时长: {duration:.2f}s", fold_code="GEN_GEN")
            self.sentence_manager.add_generated_audio(sentence_index, audio_file, duration)
            
            # 显示当前进度
            generated_count = self.sentence_manager.get_generated_count()
            total_count = len(self.sentence_manager.sentences)
            debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"当前生成进度: {generated_count}/{total_count}", fold_code="GEN_GEN")
            
            # 检查是否是第一个音频生成完成，且还有未播放的分句
            if (sentence_index == 0 and 
                self.sentence_manager.has_next_sentence() and 
                generated_count < total_count):
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "首句音频就绪，切换按钮至'播放这一句'状态", fold_code="GEN_GEN")
                self.preview_control.preview_button.setText("播放这一句")
                self.preview_control.preview_button.setEnabled(True)
            
            # 检查是否所有句子都生成完成
            elif self.sentence_manager.is_all_generated():
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "所有分句音频均已生成完成", fold_code="GEN_GEN")
                self.signals.all_sentences_complete.emit()
                
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"处理句子生成完成信号失败: {str(e)}", fold_code="GEN_GEN")
    
    def _on_all_sentences_complete_safe(self):
        """安全处理所有句子生成完成信号"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "处理所有句子生成完成逻辑", fold_code="GEN_GEN")
            # 检查是否还有未播放且已生成的句子
            current_idx = self.sentence_manager.current_sentence_index
            generated_count = self.sentence_manager.get_generated_count()
            
            # 如果当前索引小于已生成的数量，说明还有未播放的句子
            if current_idx < generated_count - 1:
                # 如果还有未播放的句子，保持"播放这一句"状态
                self.preview_control.preview_button.setText("播放这一句")
            else:
                # 如果所有句子都已播放，显示"开始听写"
                self.preview_control.preview_button.setText("开始听写")
            self.preview_control.preview_button.setEnabled(True)
            
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"处理全句生成完成逻辑失败: {str(e)}", fold_code="GEN_GEN")
    
    def _on_playback_ready_safe(self):
        """安全处理可以开始播放信号"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "接收到播放就绪信号，切换到抄写状态", fold_code="GEN_AUDIO_PLAY")
            
            # 检查是否还有下一句
            if self.sentence_manager.has_next_sentence():
                # 如果还有下一句，按钮显示为"播放这一句"
                self.preview_control.preview_button.setText("播放这一句")
            else:
                # 如果没有下一句了，按钮显示为"开始听写"
                self.preview_control.preview_button.setText("开始听写")
            self.preview_control.preview_button.setEnabled(True)
            
            # 启用播放控制按钮
            self.preview_control.set_playback_controls_enabled(True)
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "准备自动播放首句音频", fold_code="GEN_AUDIO_PLAY")
            # 自动开始播放第一句
            self._play_current_sentence()
            
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"处理播放就绪信号失败: {str(e)}", fold_code="GEN_AUDIO_PLAY")
    
    def _play_current_sentence(self):
        """播放当前句子"""
        try:
            # 检查是否有有效的句子管理器
            if not hasattr(self, 'sentence_manager') or not self.sentence_manager.sentences:
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "无有效句子数据，放弃播放", fold_code="GEN_AUDIO_PLAY")
                return
                
            current_index = self.sentence_manager.current_sentence_index
            if current_index < 0 or current_index >= len(self.sentence_manager.sentences):
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"句子索引越界 ({current_index})，放弃播放", fold_code="GEN_AUDIO_PLAY")
                return
            
            # 更新句子预览
            self.update_sentence_preview()
            
            audio_file = self.sentence_manager.get_current_sentence_audio()
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"准备播放句子 {current_index} -> {audio_file}", fold_code="GEN_AUDIO_PLAY")
            
            # 获取当前句子的重试计数
            retry_count = self.sentence_manager.play_retry_count.get(current_index, 0)
            max_retries = 5  # 最大重试次数
            
            if audio_file and os.path.exists(audio_file):
                # 检查文件大小，确保文件已完全写入
                file_size = os.path.getsize(audio_file)
                debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, f"音频文件检查: {file_size} bytes", fold_code="GEN_AUDIO_PLAY")
                
                if file_size > 0:
                    # 重置重试计数
                    self.sentence_manager.play_retry_count[current_index] = 0
                else:
                    debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"音频文件为空，重试中 ({retry_count + 1}/{max_retries})", fold_code="GEN_AUDIO_PLAY")
                    if retry_count < max_retries:
                        # 增加重试计数
                        self.sentence_manager.play_retry_count[current_index] = retry_count + 1
                        # 文件大小为0，可能是正在写入，稍后重试
                        QTimer.singleShot(200, self._play_current_sentence)
                        return
                    else:
                        debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"达到最大重试次数，文件仍为空: {audio_file}", fold_code="GEN_AUDIO_PLAY")
                        QMessageBox.warning(self, "警告", f"音频文件无效（大小为0），已达到最大重试次数 {max_retries} 次")
                        self.preview_control.preview_button.setEnabled(True)
                        return
                    
                # 播放开始时禁用按钮，防止重复点击，并更新按钮文本
                self.preview_control.preview_button.setEnabled(False)
                self.preview_control.preview_button.setText("正在播放这一句")
                # 播放音频文件 - 调用父窗口的音频预览功能
                if hasattr(self, 'parent_window') and hasattr(self.parent_window, 'audio_preview'):
                    debug_logger.output("generation_page_neo.py", LogLevel.DEBUG, "调用 audio_preview 组件执行播放", fold_code="GEN_AUDIO_PLAY")
                    # 连接到播放完成信号
                    self.parent_window.audio_preview.audio_signals.playback_finished.connect(self._on_sentence_playback_complete)
                    self.parent_window.audio_preview._play_audio_file(audio_file)
                else:
                    debug_logger.output("generation_page_neo.py", LogLevel.ERROR, "未找到音频预览组件，无法播放", fold_code="GEN_AUDIO_PLAY")
                    # 如果未找到音频预览组件，恢复按钮状态
                    self._restore_button_state_after_error()
            else:
                # 音频文件不存在，显示提示
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"音频文件尚未就绪: {audio_file}", fold_code="GEN_AUDIO_PLAY")
                QMessageBox.information(self, "提示", "当前句子的音频尚未生成完成，请稍等...")
                # 恢复按钮状态
                self._restore_button_state_after_error()
                
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"播放当前句子异常: {str(e)}", fold_code="GEN_AUDIO_PLAY")
            QMessageBox.critical(self, "错误", f"播放音频时出错: {str(e)}")
            # 播放异常时恢复按钮状态
            self._restore_button_state_after_error()
    
    def _restore_button_state_after_error(self):
        """播放异常时恢复按钮状态"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在恢复按钮状态...", fold_code="GEN_AUDIO_PLAY")
            # 根据当前状态恢复按钮文本
            if hasattr(self, 'sentence_manager') and self.sentence_manager.sentences:
                current_idx = self.sentence_manager.current_sentence_index
                if current_idx == 0 and self.sentence_manager.has_next_sentence():
                    # 如果是第一句且还有下一句，显示"播放这一句"
                    self.preview_control.preview_button.setText("播放这一句")
                elif self.sentence_manager.has_next_sentence():
                    # 如果还有下一句，显示"播放下一句"
                    self.preview_control.preview_button.setText("播放下一句")
                else:
                    # 如果没有下一句了，显示"开始听写"
                    self.preview_control.preview_button.setText("开始听写")
            else:
                # 默认状态
                self.preview_control.preview_button.setText("开始听写")
            
            # 重新启用按钮
            self.preview_control.preview_button.setEnabled(True)
            
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"恢复按钮状态失败: {str(e)}", fold_code="GEN_AUDIO_PLAY")
            # 如果恢复失败，至少启用按钮
            self.preview_control.preview_button.setEnabled(True)
    
    def _on_sentence_playback_complete(self):
        """句子播放完成回调"""
        try:
            # 检查是否还有有效的句子管理器
            if not hasattr(self, 'sentence_manager') or not self.sentence_manager.sentences:
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "播放完成回调：没有有效的句子，忽略", fold_code="GEN_AUDIO_PLAY")
                return
                
            # 检查当前索引是否有效
            current_idx = self.sentence_manager.current_sentence_index
            if current_idx < 0 or current_idx >= len(self.sentence_manager.sentences):
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"播放完成回调：当前索引 {current_idx} 无效，忽略", fold_code="GEN_AUDIO_PLAY")
                return
            
            # 播放完成后，更新进度条到相应位置
            total_sentences = len(self.sentence_manager.sentences)
            current_sentence = current_idx + 1  # 当前播放完成的句子
            
            # 检查是否是空句子或无效播放
            audio_file = self.sentence_manager.get_current_sentence_audio()
            if not audio_file or not os.path.exists(audio_file):
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "播放完成回调：当前句子没有有效音频文件，忽略", fold_code="GEN_AUDIO_PLAY")
                return
                
            # 计算进度百分比 (当前句子位置 / 总句子数) * 100%
            progress_percentage = (current_sentence / total_sentences) * 100
            
            # 将进度条设置到相应位置 (范围是0-1000)
            progress_value = int(progress_percentage * 10)
            self.preview_control.preview_progress.setValue(progress_value)
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"句子 {current_sentence-1} 播放完成，进度更新到 {progress_percentage:.1f}%", fold_code="GEN_AUDIO_PLAY")
            
            # 播放完成后，更新按钮状态
            if self.sentence_manager.has_next_sentence():
                # 如果还有下一句，按钮显示为"播放下一句"
                self.preview_control.preview_button.setText("播放下一句")
                self.preview_control.preview_button.setEnabled(True)
            else:
                # 如果没有下一句了，按钮显示为"开始听写"
                self.preview_control.preview_button.setText("开始听写")
                self.preview_control.preview_button.setEnabled(True)
            
            # 播放完成后，等待用户操作（下一句按钮或快捷键）
            # 不需要自动播放下一句，等待用户手动触发
            
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"播放完成回调出错: {str(e)}", fold_code="GEN_AUDIO_PLAY")
    
    def _play_next_sentence(self):
        """播放下一句"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "尝试切换到下一句", fold_code="GEN_NAV")
            # 检查下一句是否已生成
            if not self._check_next_sentence_ready():
                debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "下一句音频尚未准备好", fold_code="GEN_NAV")
                QMessageBox.information(self, "提示", "下一句音频尚未生成完成，请稍等...")
                return
            
            if self.sentence_manager.move_to_next_sentence():
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"切换到下一句: 索引 {self.sentence_manager.current_sentence_index}", fold_code="GEN_NAV")
                # 更新句子预览
                self.update_sentence_preview()
                
                # 立即更新进度条状态
                total_sentences = len(self.sentence_manager.sentences)
                current_sentence = self.sentence_manager.current_sentence_index + 1
                progress_percentage = (current_sentence / total_sentences) * 100
                progress_value = int(progress_percentage * 10)
                self.preview_control.preview_progress.setValue(progress_value)
                
                self._play_current_sentence()
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "已经是最后一句", fold_code="GEN_NAV")
                QMessageBox.information(self, "提示", "已经是最后一句了")
                
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"切换到下一句时出错: {str(e)}", fold_code="GEN_NAV")
            QMessageBox.critical(self, "错误", f"切换到下一句时出错: {str(e)}")

    def _play_prev_sentence(self):
        """播放上一句"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "尝试切换到上一句", fold_code="GEN_NAV")
            if self.sentence_manager.move_to_prev_sentence():
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"切换到上一句: 索引 {self.sentence_manager.current_sentence_index}", fold_code="GEN_NAV")
                # 更新句子预览
                self.update_sentence_preview()
                
                # 立即更新进度条状态
                total_sentences = len(self.sentence_manager.sentences)
                current_sentence = self.sentence_manager.current_sentence_index + 1
                progress_percentage = (current_sentence / total_sentences) * 100
                progress_value = int(progress_percentage * 10)
                self.preview_control.preview_progress.setValue(progress_value)
                
                self._play_current_sentence()
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "已经是第一句", fold_code="GEN_NAV")
                QMessageBox.information(self, "提示", "已经是第一句了")
                
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"切换到上一句时出错: {str(e)}", fold_code="GEN_NAV")
            QMessageBox.critical(self, "错误", f"切换到上一句时出错: {str(e)}")
    
    def _check_next_sentence_ready(self) -> bool:
        """检查下一句是否已生成"""
        try:
            next_index = self.sentence_manager.current_sentence_index + 1
            if next_index < len(self.sentence_manager.sentences):
                audio_file = self.sentence_manager.get_sentence_audio(next_index)
                return audio_file is not None and os.path.exists(audio_file)
            return False
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"检查下一句状态时出错: {str(e)}", fold_code="GEN_NAV")
            return False
    
    def handle_next_sentence(self):
        """处理下一句请求（供外部调用）"""
        self._play_next_sentence()
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        # 统一由 main_window -> audio_preview -> hotkey_manager 处理
        # 如果需要在此页面处理特定的非全局热键，可以在此添加
        super().keyPressEvent(event)
    
    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置更改"""
        try:
            if page_name in ['custom', 'custom_page']:
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"接收到个性化页面设置更改: {page_name}", fold_code="GEN_INIT")
                # 如果是来自个性化页面的设置更改，更新相关设置
                # 重新加载页面以应用新设置
                self._reload_page(settings_data)
        except Exception as e:
            # 设置更新失败处理
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"处理共享内存设置更改时出错: {str(e)}", fold_code="GEN_INIT")
            pass

    def _show_pause_settings(self):
        """显示停顿设置对话框"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "打开停顿设置对话框", fold_code="GEN_INIT")
            # 获取当前设置
            current_settings = self.sentence_splitter.enabled_marks

            # 创建对话框
            dialog = PauseSettingsDialog(self, current_settings)

            # 显示对话框并获取结果
            if dialog.exec_() == QDialog.Accepted:
                # 获取用户选择的设置
                new_settings = dialog.get_enabled_marks()
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"更新停顿设置: {new_settings}", fold_code="GEN_INIT")

                # 更新句子分割器设置
                self.sentence_splitter.set_pause_marks(new_settings)

                # 如果已经有文本，重新分割
                if hasattr(self, 'current_text') and self.current_text:
                    sentences = self.sentence_splitter.split_text(self.current_text)
                    self.sentence_manager.set_sentences(sentences)

                    # 更新句子预览
                    self.update_sentence_preview()

                    # 显示提示信息
                    QMessageBox.information(self, "设置已更新", f"停顿设置已更新，文本已重新分割为{len(sentences)}个小句")

        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"显示停顿设置对话框时出错: {str(e)}", fold_code="GEN_INIT")
            QMessageBox.critical(self, "错误", f"设置停顿符号时出错：{str(e)}")

    def _show_param_settings(self):
        """显示参数设置对话框"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "打开参数设置对话框", fold_code="GEN_INIT")
            # 创建参数设置对话框
            dialog = ParamSettingsDialog(self, self.config)

            # 显示对话框并获取结果
            if dialog.exec_() == QDialog.Accepted:
                # 获取用户设置的新参数
                new_config = dialog.get_config()
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"更新语音参数: {new_config}", fold_code="GEN_INIT")

                # 更新配置
                self.config = new_config

                # 显示提示信息
                QMessageBox.information(self, "设置已更新", "语音参数设置已更新")

        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"显示参数设置对话框时出错: {str(e)}", fold_code="GEN_INIT")
            QMessageBox.critical(self, "错误", f"设置参数时出错：{str(e)}")
    
    def _get_pause_settings_button_style(self):
        """获取停顿设置按钮的样式"""
        # 获取用户设置的字体
        global_font = self.parent_window.settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        # 计算动态字体大小（使用与音量提示文本相同的算法）
        if self.parent_window:
            current_width = self.parent_window.width()
            current_height = self.parent_window.height()
            
            min_font_size = 22
            max_font_size = 42
            default_width = 1080
            default_height = 720
            
            width_ratio = current_width / default_width
            height_ratio = current_height / default_height
            ratio = (width_ratio + height_ratio) / 2
            
            base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
            button_font_size = max(min_font_size, min(max_font_size, base_font_size))
            button_font_size = int(button_font_size * 1.0)  # 按钮字体放大到原先的两倍（从0.5改为1.0）
        else:
            button_font_size = 14  # 默认字体大小
        
        return f"""
            QPushButton {{
                font-family: "{global_font}";
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: {button_font_size}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
            QPushButton:pressed {{
                background-color: #3d8b40;
            }}
        """
    
    def _get_param_settings_button_style(self):
        """获取参数设置按钮的样式"""
        # 获取用户设置的字体
        global_font = self.parent_window.settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        # 计算动态字体大小（使用与音量提示文本相同的算法）
        if self.parent_window:
            current_width = self.parent_window.width()
            current_height = self.parent_window.height()
            
            min_font_size = 22
            max_font_size = 42
            default_width = 1080
            default_height = 720
            
            width_ratio = current_width / default_width
            height_ratio = current_height / default_height
            ratio = (width_ratio + height_ratio) / 2
            
            base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
            button_font_size = max(min_font_size, min(max_font_size, base_font_size))
            button_font_size = int(button_font_size * 1.0)  # 按钮字体放大到原先的两倍（从0.5改为1.0）
        else:
            button_font_size = 14  # 默认字体大小
        
        return f"""
            QPushButton {{
                font-family: "{global_font}";
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: {button_font_size}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
            QPushButton:pressed {{
                background-color: #1565C0;
            }}
        """
    
    def _reload_page(self, settings_data=None):
        """重新加载页面以应用最新设置"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "正在重载页面设置...", fold_code="GEN_INIT")
        try:
            # 更新字体
            self._update_fonts()
            
            # 更新颜色设置
            if settings_data:
                bg_color = settings_data.get('background_color')
                text_color = settings_data.get('text_color')
                
                if bg_color:
                    self.background_color = bg_color
                if text_color:
                    self.text_color = text_color
                
                # 应用样式表到主页面
                self.setStyleSheet(f"QWidget {{ background-color: {self.background_color}; color: {self.text_color}; }}")
                
                # 更新句子预览样式（包含文字颜色）
                self._setup_sentence_preview_styles()
                
                # 如果有特定的按钮样式需要更新，也可以在这里添加
                # 例如停顿设置和参数设置按钮
                self.pause_settings_button.setStyleSheet(self._get_pause_settings_button_style())
                self.param_settings_button.setStyleSheet(self._get_param_settings_button_style())
            
            # 重新布局控件（触发resize事件）
            if hasattr(self, 'resizeEvent'):
                self.resize(self.width(), self.height())
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "页面重载完成", fold_code="GEN_INIT")
            # 页面重新加载成功
        except Exception as e:
            # 页面重新加载失败处理
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"页面重新加载失败: {str(e)}", fold_code="GEN_INIT")
            pass

    def _layout_volume_controls(self, width, height, n, m, scale_factor, right_offset, progress_y, control_buttons_y, control_button_height):
        """布局音量控制控件"""
        
        # 首先布局结束按钮（在音量控制左侧）- 再往左移动避免超出边界
        end_button_width = int(3.5 * n * scale_factor)  # 进一步减小按钮宽度
        end_button_x = int((6 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset  # 再往左移动
        end_button_y = control_buttons_y
        
        self.preview_control.end_dictation_button.setGeometry(
            end_button_x, end_button_y, end_button_width, control_button_height
        )
        
        # 音量控制布局（在结束按钮右侧）- 紧凑布局避免超出窗口
        volume_x = end_button_x + end_button_width + int(1.5 * n * scale_factor)  # 减小间距
        volume_y = control_buttons_y 
        
        # 音量标签 - 减小宽度
        label_width = int(1.2 * n * scale_factor)
        self.preview_control.volume_label.setGeometry(
            volume_x, volume_y, label_width, control_button_height
        )
        
        # 音量滑动条 - 减小宽度
        slider_width = int(2.0 * n * scale_factor)
        self.preview_control.volume_slider.setGeometry(
            volume_x + label_width, volume_y, slider_width, control_button_height
        )
        
        # 音量数值显示 - 减小宽度
        value_width = int(1.5 * n * scale_factor)
        self.preview_control.volume_value_label.setGeometry(
            volume_x + label_width + slider_width, volume_y, value_width, control_button_height
        )

    def _layout_parameter_control(self, param_name: str, y_pos: int, right_offset: int, 
                                 scale_factor: float, n: float, m: float, 
                                 button_size: int, slider_height: int):
        """布局参数控制组件"""
        control = self.parameter_controls[param_name]
        
        control.label.setGeometry(int((8.1 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset, y_pos, int(2 * n * scale_factor), int(m))
        control.minus_button.setGeometry(int((10.1 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset, y_pos, button_size, button_size)  
        control.slider.setGeometry(int((10.8 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset, y_pos, int(4 * n * scale_factor), slider_height)  
        control.plus_button.setGeometry(int((14.9 + GenerationPage.POSITION_OFFSET_N) * n * scale_factor) + right_offset, y_pos, button_size, button_size)

    def _update_fonts(self):
        """更新字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        # 使用与主界面相同的算法
        min_font_size = 22
        max_font_size = 42
        default_width = 1080
        default_height = 720
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        base_font_size = max(min_font_size, min(max_font_size, base_font_size))
        
        # 转换为整数
        base_font_size = int(base_font_size)
        
        # 计算其他字体大小
        other_font_size = int(base_font_size * 0.5)
        small_font_size = int(base_font_size * 0.4)
        
        # 获取全局字体设置
        global_font = self.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑")
        base_font = QFont(global_font, base_font_size)
        other_font = QFont(global_font, other_font_size)
        small_font = QFont(global_font, small_font_size)
        
        # 应用字体到所有ParameterControl控件
        for control in self.parameter_controls.values():
            control.update_font(other_font)
        
        # 应用字体到VoiceSelection控件
        self.voice_selection.update_font(other_font)
        
        # 应用字体到TextEditSection控件
        self.text_edit_section.update_font(other_font)
        
        # 应用字体到PreviewControl控件
        self.preview_control.update_font(other_font)
        
        # 移除GenerationControl控件字体更新
        
        # 应用字体到GenerationPage控件
        self.checkbox.setFont(small_font)
        self.hint_label.setFont(small_font)
        
        # 应用字体到句子预览控件
        self._update_sentence_preview_fonts(other_font)
        
        # 应用字体到停顿设置按钮
        self.pause_settings_button.setFont(other_font)
        # 重新应用按钮样式以使用新字体
        self.pause_settings_button.setStyleSheet(self._get_pause_settings_button_style())

    # 参数更新方法
    # 移除语速、音调、音量更新方法

    def _update_parameter(self, param: str, value: int, display_name: str):
        """更新参数"""
        setattr(self.config, param, value)
        self.parameter_controls[param].update_display(value)
        self._check_inputs_and_update_button()
        self._check_content_changed()

    # 音频音频相关方法
    def _generate_preview_audio(self):
        """生成音频 - 使用多线程句子生成"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "开始生成听写音频...", fold_code="SENT_GEN")
        # 获取文本内容
        text_content = self.text_edit_section.get_text()
        if not text_content.strip():
            # 使用默认文本
            default_config = AudioConfig()
            text_content = default_config.content
            self.text_edit_section.set_text(text_content)
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "文本内容为空，使用默认文本", fold_code="SENT_GEN")
        
        # 保存当前文本
        self.current_text = text_content
        
        if not self._validate_preview_inputs():
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, "输入验证失败，取消生成", fold_code="SENT_GEN")
            return
            
        # 分割文本为句子
        sentences = self.sentence_splitter.split_text(text_content)
        if not sentences:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, "文本分割失败，未获取到有效句子", fold_code="SENT_GEN")
            QMessageBox.warning(self, "警告", "文本分割失败，请检查停顿符号设置")
            return
        
        # 设置句子到管理器
        self.sentence_manager.set_sentences(sentences)
        
        # 更新句子预览
        self.update_sentence_preview()
        
        # 更新UI状态
        self.preview_control.preview_button.setEnabled(False)
        self.preview_control.preview_button.setText("生成中...")
        
        # 重置播放状态
        if hasattr(self, '_playback_started'):
            delattr(self, '_playback_started')
        
        # 启动多线程生成
        self._start_multi_threaded_generation(sentences)

    def _on_preview_generated_thread(self, file_path: str):
        """音频音频生成完成处理 - 线程版本"""
        self.signals.preview_generated.emit(file_path)

    @pyqtSlot(str)
    def _on_preview_generated_safe(self, file_path: str):
        """音频音频生成完成处理 - 线程安全版本"""
        self.preview_control.preview_button.setEnabled(True)
        self.preview_control.update_preview_button_state(True, True)
        
        cache_key = ContentHasher.get_cache_key(self.config)
        self.parent_window.audio_cache[cache_key] = file_path
        self.parent_window.current_audio_path = file_path
        
        self.parent_window.last_content_hash = ContentHasher.get_content_hash(self.config)
        self.parent_window.has_preview = True
        
        # 使用新的消息系统
        self.parent_window.notification_manager.show_message("音频生成完成", "I", 3000)
        
        # 音频音频生成完成

    def _handle_preview_error_thread(self, error: str):
        """处理音频错误 - 线程版本"""
        self.signals.preview_error.emit(error)

    @pyqtSlot(str)
    def _handle_preview_error_safe(self, error: str):
        """处理音频错误 - 线程安全版本"""
        # 生成音频音频时发生错误
        self.preview_control.preview_button.setEnabled(True)
        self.preview_control.update_preview_button_state(False, False)
        self.parent_window.has_preview = False
        
        # 使用新的消息系统
        self.parent_window.notification_manager.show_message(f"生成音频失败: {error}", "E", 5000)

    # 音频生成相关方法
    def _generate_audio(self):
        """生成音频文件 - 异步版本"""
        # 开始生成音频
        
        if not self._validate_inputs():
            return
        
        # 设置默认保存路径
        self.config.save_path = AudioFileManager.get_default_save_path(self.config, self.parent_window.settings_manager)
        if not self.config.save_path:
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message("请先在设置中配置默认保存路径", "W", 5000)
            return
            
        # 移除生成控制按钮状态更新
        
        threading.Thread(
            target=self.parent_window.audio_generator.generate_audio,
            args=(self.config, self._on_generation_complete_thread),
            daemon=True
        ).start()

    def _start_multi_threaded_generation(self, sentences: List[str]):
        """启动单线程句子生成 - 第一段音频完成后切换到开始抄写状态"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"启动单线程生成，句子数量: {len(sentences)}", fold_code="GEN_GEN")
            
            # 设置生成状态
            self.sentence_manager.is_generating = True
            self.sentence_manager.generation_queue = list(enumerate(sentences))
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"生成队列创建完成，包含 {len(self.sentence_manager.generation_queue)} 个句子", fold_code="GEN_GEN")
            
            # 创建单一生成线程
            self.sentence_manager.generation_threads = []
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "创建单线程生成器", fold_code="GEN_GEN")
            thread = threading.Thread(
                target=self._single_thread_generation_worker,
                daemon=True
            )
            self.sentence_manager.generation_threads.append(thread)
            thread.start()
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "单线程生成器已启动", fold_code="GEN_GEN")
                
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"启动单线程生成失败: {str(e)}", fold_code="GEN_GEN")
            QMessageBox.critical(self, "错误", f"启动单线程生成失败: {str(e)}")
            self._on_generation_complete(False, str(e))
    
    def _single_thread_generation_worker(self):
        """单线程句子生成工作器 - 第一段音频完成后切换到开始抄写状态"""
        try:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "[单线程] 开始生成句子", fold_code="GEN_GEN")
            first_sentence_generated = False
            
            while self.sentence_manager.is_generating:
                # 获取下一个要生成的句子
                sentence_info = self.sentence_manager.get_next_sentence_to_generate()
                if sentence_info is None:
                    debug_logger.output("generation_page_neo.py", LogLevel.INFO, "[单线程] 没有更多句子要生成，结束", fold_code="GEN_GEN")
                    break
                
                sentence_index, sentence_text = sentence_info
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[单线程] 开始处理句子 {sentence_index}: {sentence_text[:30]}...", fold_code="GEN_GEN")
                
                # 生成单个句子的音频
                try:
                    audio_file, duration = self._generate_single_sentence_audio(sentence_text, sentence_index)
                    
                    if audio_file:
                        debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[单线程] 句子 {sentence_index} 生成成功，时长: {duration:.2f}s", fold_code="GEN_GEN")
                        self.signals.sentence_generated.emit(sentence_index, audio_file, duration)
                        
                        # 如果是第一个句子生成完成，切换到开始抄写状态
                        if not first_sentence_generated:
                            first_sentence_generated = True
                            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "[单线程] 第一个句子生成完成，切换到开始抄写状态", fold_code="GEN_GEN")
                            # 添加短暂延迟确保文件完全写入
                            import time
                            time.sleep(0.1)
                            # 发送信号切换到开始抄写状态
                            self.signals.playback_ready.emit()
                            
                    else:
                        debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"[单线程] 句子 {sentence_index} 生成失败", fold_code="GEN_GEN")
                        
                except Exception as e:
                    debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"[单线程] 句子 {sentence_index} 处理异常: {str(e)}", fold_code="GEN_GEN")
                    continue
                    
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"[单线程] 工作器出错: {str(e)}", fold_code="GEN_GEN")
        finally:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "[单线程] 工作器结束", fold_code="GEN_GEN")
    
    def _generate_single_sentence_audio(self, sentence_text: str, sentence_index: int) -> tuple:
        """生成单个句子的音频"""
        try:
            # 获取当前线程ID
            current_thread_id = threading.get_ident()
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 开始生成句子 {sentence_index} 音频", fold_code="GEN_AUDIO")
            
            # 创建临时配置
            temp_config = AudioConfig()
            temp_config.content = sentence_text
            temp_config.voice = self.config.voice
            temp_config.speed = self.config.speed
            temp_config.pitch = self.config.pitch
            temp_config.volume = self.config.volume
            
            # 使用FilePathManager创建临时文件
            from edge_audio_generator import FilePathManager
            file_manager = FilePathManager()
            audio_file = file_manager.create_temp_file('.wav')
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 句子 {sentence_index} 临时文件: {audio_file}", fold_code="GEN_AUDIO")
            
            # 使用实际的音频生成器
            from edge_audio_generator import GenerationConfig
            
            # 创建生成配置
            gen_config = GenerationConfig(
                content=sentence_text,
                voice=self.config.voice,
                speed=self.config.speed,
                pitch=self.config.pitch,
                volume=self.config.volume,
                save_path=audio_file,
                stretch_factor=getattr(self.config, 'stretch_factor', 1.0),
                stretch_enabled=getattr(self.config, 'stretch_enabled', False)
            )
            
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 句子 {sentence_index} 生成配置 - 文本: {sentence_text[:30]}..., 语音: {self.config.voice}, 速度: {self.config.speed}, 音调: {self.config.pitch}, 音量: {self.config.volume}", fold_code="GEN_AUDIO")
            
            # 检查语音配置
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 句子 {sentence_index} 语音配置检查 - voice: '{self.config.voice}', save_path: '{audio_file}'", fold_code="GEN_AUDIO")
            
            # 生成音频 - 添加超时保护
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 句子 {sentence_index} 开始调用音频生成器...", fold_code="GEN_AUDIO")
            
            # 创建带有超时的生成任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.parent_window.audio_generator.generate_audio, gen_config)
                try:
                    success = future.result(timeout=30)  # 30秒超时
                    debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 句子 {sentence_index} 音频生成结果: {success}", fold_code="GEN_AUDIO")
                except concurrent.futures.TimeoutError:
                    debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"[线程{current_thread_id}] 句子 {sentence_index} 音频生成超时（30秒）", fold_code="GEN_AUDIO")
                    return None, 0.0
                except Exception as e:
                    debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"[线程{current_thread_id}] 句子 {sentence_index} 音频生成异常: {e}", fold_code="GEN_AUDIO")
                    return None, 0.0

            if success:
                # 获取音频时长
                duration = self._get_audio_duration(audio_file)
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"[线程{current_thread_id}] 句子 {sentence_index} 音频时长: {duration:.2f}s", fold_code="GEN_AUDIO")
                return audio_file, duration
            else:
                debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"[线程{current_thread_id}] 句子 {sentence_index} 音频生成失败: 音频生成器返回失败", fold_code="GEN_AUDIO")
                return None, 0.0
            
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"[线程{threading.get_ident()}] 句子 {sentence_index} 音频生成失败: {e}", fold_code="GEN_AUDIO")
            return None, 0.0

    def _on_generation_complete_thread(self, success: bool, message: str):
        """音频生成完成回调 - 线程版本"""
        self.signals.generation_complete.emit(success, message)

    @pyqtSlot(bool, str)
    def _get_audio_duration(self, audio_file_path: str) -> float:
        """获取音频文件时长（秒）"""
        try:
            import wave
            with wave.open(audio_file_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
                return duration
        except Exception as e:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"获取音频时长失败: {str(e)}", fold_code="GEN_AUDIO")
            return 0.0
    
    def _on_generation_complete_safe(self, success: bool, message: str):
        """音频生成完成回调 - 线程安全版本"""
        # 移除生成控制按钮状态更新
        
        if success:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, "音频生成成功并保存", fold_code="GEN_STATE")
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message("音频成功生成并保存", "I", 3000)
            # 音频生成成功
        else:
            debug_logger.output("generation_page_neo.py", LogLevel.ERROR, f"音频生成失败: {message}", fold_code="GEN_STATE")
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message(f"音频生成失败: {message}", "E", 5000)
            # 音频生成失败

    # 验证方法
    def _validate_preview_inputs(self) -> bool:
        """验证音频输入"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "验证音频预览输入参数", fold_code="GEN_STATE")
        success, message = InputValidator.validate_preview_inputs(self.config)
        if not success:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"预览输入验证失败: {message}", fold_code="GEN_STATE")
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message(message, "W", 5000)
            # 验证失败
            return False
        return True

    def _validate_inputs(self) -> bool:
        """验证输入参数"""
        debug_logger.output("generation_page_neo.py", LogLevel.INFO, "验证完整音频生成输入参数", fold_code="GEN_STATE")
        success, message = InputValidator.validate_generation_inputs(self.config, self.parent_window.settings_manager)
        if not success:
            debug_logger.output("generation_page_neo.py", LogLevel.WARNING, f"生成输入验证失败: {message}", fold_code="GEN_STATE")
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message(message, "W", 5000)
            # 验证失败
            return False
        return True

    # 状态检查方法
    def _check_inputs_and_update_button(self):
        """检查输入并更新按钮状态"""
        has_error, empty_fields = InputValidator.check_inputs_for_button(self.config, self.parent_window.settings_manager)
        if has_error:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"输入检查发现空字段: {', '.join(empty_fields)}", fold_code="GEN_STATE")
        # 使用信号安全地更新UI
        self.signals.update_button_state.emit(has_error, ", ".join(empty_fields))

    @pyqtSlot(bool, str)
    def _update_button_state_safe(self, has_error: bool, empty_fields_text: str):
        """线程安全地更新按钮状态"""
        # 移除生成控制按钮状态更新

    def _check_content_changed(self):
        """检查内容是否改变"""
        current_hash = ContentHasher.get_content_hash(self.config)
        content_changed = (self.parent_window.last_content_hash is None or 
                          current_hash != self.parent_window.last_content_hash)
        
        if content_changed:
            debug_logger.output("generation_page_neo.py", LogLevel.INFO, f"检测到内容变化 - 旧哈希: {self.parent_window.last_content_hash}, 新哈希: {current_hash}", fold_code="GEN_STATE")
            if self.parent_window.has_preview:
                debug_logger.output("generation_page_neo.py", LogLevel.INFO, "内容变化，重置预览状态并停止播放", fold_code="GEN_STATE")
                self.preview_control.update_preview_button_state(False, False)
                self.parent_window.has_preview = False
                # 修复：内容改变时停止音频播放
                if self.parent_window.is_playing or self.parent_window.audio_preview.is_paused:
                    self.parent_window.audio_preview.stop_audio()

    def _is_content_unchanged(self) -> bool:
        """检查内容是否未改变"""
        current_hash = ContentHasher.get_content_hash(self.config)
        return (self.parent_window.last_content_hash is not None and 
                current_hash == self.parent_window.last_content_hash)

    # 工具方法
    def _get_content_hash(self) -> str:
        """获取内容哈希值"""
        return ContentHasher.get_content_hash(self.config)

    def _get_cache_key(self) -> str:
        """获取缓存键"""
        return ContentHasher.get_cache_key(self.config)

if __name__ == "__main__":
    pass