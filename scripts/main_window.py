# coding=utf-8
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QStackedWidget
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from audio_preview import AudioPreview
from misc_func import AudioConfig, SettingsManager
from shared_memory_manager import get_shared_memory_manager
import os
import locale

# 导入GenerationPage用于属性检查
from generation_page import GenerationPage


# 在程序最开头添加编码设置
def setup_encoding():
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 针对Windows控制台的特殊处理
    if sys.platform.startswith('win'):
        # 设置标准输出编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        
        # 设置locale
        try:
            locale.setlocale(locale.LC_ALL, 'chinese')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
            except:
                try:
                    locale.setlocale(locale.LC_ALL, '')
                except:
                    pass

# 调用设置函数
setup_encoding()

class AsyncInitializer:
    """异步初始化管理器"""
    
    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_initialization)
        self.current_step = 0
        self.total_steps = 2  # 两个初始化步骤
    
    def start(self):
        """开始异步初始化"""
        self.timer.start(100)  # 100ms后开始第一个步骤
    
    def _process_initialization(self):
        """处理初始化步骤"""
        if self.current_step == 0:
            self.parent_window._async_create_tab_pages()
            self.current_step += 1
            self.timer.start(50)  # 50ms后开始下一个步骤
        elif self.current_step == 1:
            self.parent_window._async_init_non_critical_components()
            self.current_step += 1
            self.timer.stop()
            self.parent_window._on_async_finished()


class FontManager:
    """字体管理器"""
    
    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
    
    def calculate_font_sizes(self) -> tuple:
        """计算适应窗口大小的字体尺寸"""
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        width_ratio = current_width / self.default_width
        height_ratio = current_height / self.default_height
        ratio = (width_ratio + height_ratio) / 2
        base_font_size = (self.min_font_size +(self.max_font_size - self.min_font_size) * (ratio - 1))
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        tab_font_size = max(12, int(base_font_size * 0.4))
        return base_font_size, other_font_size, tab_font_size
    
    def update_all_fonts(self):
        """更新所有组件的字体"""
        base_font_size, other_font_size, tab_font_size = self.calculate_font_sizes()
        
        # 设置主窗口字体
        base_font = QFont("微软雅黑", base_font_size)
        self.parent_window.setFont(base_font)
        
        # 更新选项卡字体
        tab_font = QFont("微软雅黑", tab_font_size)
        if hasattr(self.parent_window, 'tab_manager'):
            self.parent_window.tab_manager.update_tab_fonts(tab_font)
            
        # 更新生成页面字体
        if hasattr(self.parent_window, 'generation_page') and self.parent_window.generation_page:
            self._update_generation_page_fonts(other_font_size)
    
    def _update_generation_page_fonts(self, other_font_size: int):
        """更新生成页面各组件字体"""
        page = self.parent_window.generation_page
        other_font = QFont("微软雅黑", other_font_size)
        
        # 更新按钮字体
        self._update_all_buttons_font(page, other_font)
        
        # 更新参数控制标签字体
        if hasattr(page, 'parameter_controls'):
            for control in page.parameter_controls.values():
                if hasattr(control, 'label'):
                    control.label.setFont(other_font)
                    
        # 更新参数控制加减按钮字体
        if hasattr(page, 'parameter_controls'):
            for control in page.parameter_controls.values():
                if hasattr(control, 'plus_button'):
                    control.plus_button.setFont(other_font)
                if hasattr(control, 'minus_button'):
                    control.minus_button.setFont(other_font)
                    
        # 更新其他控件字体
        other_widgets = ['combo_box', 'checkbox', 'hint_label']
        for widget_name in other_widgets:
            if hasattr(page, widget_name):
                widget = getattr(page, widget_name)
                widget.setFont(other_font)
        
        # 更新文本编辑框字体
        if hasattr(page, 'text_edit_section'):
            text_edit_font = QFont("微软雅黑", 14)
            page.text_edit_section.text_edit.setFont(text_edit_font)
    
    def _update_all_buttons_font(self, page, font):
        """更新页面中所有按钮的字体"""
        # 更新预览控制按钮字体
        if hasattr(page, 'preview_control'):
            preview_control = page.preview_control
            button_attrs = ['preview_button', 'pause_button', 'stop_button']
            for attr in button_attrs:
                if hasattr(preview_control, attr):
                    button = getattr(preview_control, attr)
                    button.setFont(font)
        
        # 更新生成控制按钮字体
        if hasattr(page, 'generation_control'):
            generation_control = page.generation_control
            if hasattr(generation_control, 'button'):
                generation_control.button.setFont(font)
        
        # 更新音色选择下拉框字体
        if hasattr(page, 'voice_selection'):
            voice_selection = page.voice_selection
            if hasattr(voice_selection, 'combo_box'):
                voice_selection.combo_box.setFont(font)
        
        # 更新参数控制加减按钮字体
        if hasattr(page, 'parameter_controls'):
            for control in page.parameter_controls.values():
                if hasattr(control, 'plus_button'):
                    control.plus_button.setFont(font)
                if hasattr(control, 'minus_button'):
                    control.minus_button.setFont(font)
class TabConfig:
    """选项卡配置数据类"""
    def __init__(self, name, display_name, widget_class):
        self.name = name
        self.display_name = display_name
        self.widget_class = widget_class


class TabManager:
    """选项卡管理器"""
    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.tab_buttons = []
        self.tab_configs = []
        self.current_tab_index = 0
        
    def register_tab(self, name, display_name, widget_class):
        """注册新选项卡"""
        self.tab_configs.append(TabConfig(name, display_name, widget_class))
        
    def setup_tabs(self):
        """设置选项卡"""
        self._create_tab_buttons()
        self._create_tab_pages()
        
    def _create_tab_buttons(self):
        """创建选项卡按钮"""
        for i, tab_config in enumerate(self.tab_configs):
            btn = QPushButton(tab_config.display_name, self.parent_window)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.clicked.connect(lambda checked, idx=i: self.switch_to_tab(idx))
            btn.setStyleSheet(self._get_tab_button_style())
            self.tab_buttons.append(btn)
    def _create_tab_pages(self):
        """创建选项卡页面"""
        for tab_config in self.tab_configs:
            page_widget = tab_config.widget_class(self.parent_window)
            self.parent_window.stacked_widget.addWidget(page_widget)
    def switch_to_tab(self, index):
        """切换到指定索引的选项卡"""
        if index == self.current_tab_index:
            return
        
        # 检查选项卡页面是否已创建
        if index >= self.parent_window.stacked_widget.count():
            # 页面尚未创建，需要同步创建
            self._create_tab_page(index)
        
        # 更新按钮选中状态
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
            
        # 切换页面
        self.parent_window.stacked_widget.setCurrentIndex(index)
        self.current_tab_index = index
        self._on_tab_switched(index)
    
    def _create_tab_page(self, index):
        """同步创建单个选项卡页面"""
        if index < len(self.tab_configs):
            tab_config = self.tab_configs[index]
            page_widget = tab_config.widget_class(self.parent_window)
            self.parent_window.stacked_widget.addWidget(page_widget)
    def _on_tab_switched(self, index):
        """选项卡切换后处理"""
        # 获取当前页面的配置
        if index < len(self.tab_configs):
            tab_config = self.tab_configs[index]
            # 如果是生成页面，执行特殊处理
            if tab_config.name == 'generation' and hasattr(self.parent_window, 'generation_page'):
                self.parent_window.generation_page._check_inputs_and_update_button()
    def _get_tab_button_style(self):
        """选项卡按钮样式"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: rgb(240, 240, 240); color: black;
                border: 2px solid gray; border-radius: 5px;
            }
            QPushButton:checked { background-color: rgb(200, 200, 200); border: 2px solid black; }
            QPushButton:hover { background-color: rgb(220, 220, 220); }
        """
    def resize_tabs(self, width, height):
        """调整选项卡按钮布局"""
        tab_bar_width = int(width * 0.1)
        tab_button_height = int(height * 0.08)
        tab_button_width = int(tab_bar_width * 0.8)
        tab_spacing = int(height * 0.02)
        total_tab_height = len(self.tab_buttons) * tab_button_height + (len(self.tab_buttons) - 1) * tab_spacing
        start_y = (height - total_tab_height) // 2
        for i, btn in enumerate(self.tab_buttons):
            btn_x = (tab_bar_width - tab_button_width) // 2
            btn_y = start_y + i * (tab_button_height + tab_spacing)
            btn.setGeometry(btn_x, btn_y, tab_button_width, tab_button_height)
    def update_tab_fonts(self, font):
        """更新选项卡按钮字体"""
        for btn in self.tab_buttons:
            btn.setFont(font)
class MainWindow(QWidget):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self._async_initializer = None
        self._init_core_components()
        self._load_settings()  # 优先加载设置
        self._init_ui()
        self._start_async_initialization()
        
    def _init_core_components(self):
        """初始化核心组件"""
        self.config = AudioConfig()
        self.settings_manager = SettingsManager()
        self.audio_preview = AudioPreview(self)
        self.font_manager = FontManager(self)
        self.shared_manager = get_shared_memory_manager()  # 初始化共享内存管理器
        self._audio_generator = None  # 延迟加载
        self._notification_manager = None  # 延迟加载
        self._init_audio_state()
        self._init_ui_variables()
    def _init_audio_state(self):
        """初始化音频状态变量"""
        self.is_playing = False
        self.is_paused = False
        self.current_audio_length = 0
        self.current_audio_position = 0
        self.audio_cache = {}
        self.current_audio_path = None
        self.last_content_hash = None
        self.has_preview = False
    def _init_ui_variables(self):
        """初始化UI相关变量"""
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
        self.tab_manager = TabManager(self)
        self.stacked_widget = QStackedWidget(self)
    def _init_ui(self):
        """初始化用户界面"""
        self._setup_window_properties()
        self._setup_tabs()
        #self._setup_layout()
        self.font_manager.update_all_fonts()
    
    def _setup_window_properties(self):
        """设置窗口基本属性"""
        self.setWindowTitle('文本转语音')
        self.setGeometry(300, 300, self.default_width, self.default_height)
        self.setMinimumSize(1080, 720)
        # 使用设置中的背景色，如果没有设置则使用默认值
        background_color = self.settings_manager.get_Custom_value("background_color", "#E5E8EF")
        self.setStyleSheet(f"background-color: {background_color};")
        initial_font = QFont("微软雅黑", 26)
        self.setFont(initial_font)
        # 设置焦点策略
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 广播初始窗口大小到共享内存
        self.shared_manager.broadcast_window_size_change(self.default_width, self.default_height)
    def _setup_tabs(self):
        """设置选项卡系统"""
        # 注册选项卡
        self.tab_manager.register_tab('welcome', '欢迎', self._get_welcome_page_class())
        self.tab_manager.register_tab('generation', '生成', self._get_generation_page_class())
        self.tab_manager.register_tab('settings', '设置', self._get_settings_page_class())
        self.tab_manager.register_tab('personalization', '个性化', self._get_personalization_page_class()) 
        self.tab_manager.register_tab('misc', '杂项', self._get_misc_page_class())

        # 只创建选项卡按钮，页面将在异步中创建
        self.tab_manager._create_tab_buttons()
    def _get_generation_page_class(self):
        from generation_page import GenerationPage
        return GenerationPage
    def _get_settings_page_class(self):
        from settings_page import SettingsPage
        return SettingsPage
    def _get_personalization_page_class(self):
        from custom_page import CustomPage
        return CustomPage
    def _get_welcome_page_class(self):
        from welcome_page import WelcomePage
        return WelcomePage
    
    def _get_misc_page_class(self):
        from misc_page import MiscPage
        return MiscPage

    def _start_async_initialization(self):
        """启动异步初始化"""
        self._async_initializer = AsyncInitializer(self)
        self._async_initializer.start()
    
    def _on_async_finished(self):
        """异步初始化完成"""
        pass
        self._async_initializer = None
    
    def _async_create_tab_pages(self):
        """异步创建选项卡页面"""
        # 延迟创建选项卡页面
        for tab_config in self.tab_manager.tab_configs:
            page_widget = tab_config.widget_class(self)
            self.stacked_widget.addWidget(page_widget)
            
            # 如果页面有共享内存信号连接方法，则调用它
            if hasattr(page_widget, '_connect_shared_memory_signals'):
                page_widget._connect_shared_memory_signals()
    
    def _async_init_non_critical_components(self):
        """异步初始化非关键组件"""
        # 这里可以添加其他非关键组件的异步初始化
        # 例如：预加载一些数据、初始化缓存等
        pass
    
    def _load_settings(self):
        """加载设置"""
        self._load_stretch_setting()
        self._load_keyboard_scheme()
    def _load_stretch_setting(self):
        """加载音频拉伸设置"""
        stretch_factor = self.settings_manager.get_stretch_factor()
        self.config.stretch_factor = stretch_factor
        
        stretch_enabled = self.settings_manager.get_stretch_enabled()
        self.config.stretch_enabled = stretch_enabled
    def _load_keyboard_scheme(self):
        """加载键盘控制方案"""
        keyboard_scheme = self.settings_manager.Custom.get_value("keyboard_scheme", "1")
        try:
            scheme_id = int(keyboard_scheme)
            self.audio_preview.set_keyboard_scheme(scheme_id)
        except (ValueError, TypeError):
            self.audio_preview.set_keyboard_scheme(1)
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        width = self.width()
        height = self.height()
        tab_bar_width = int(width * 0.1)
        content_width = width - tab_bar_width - 10  # 右侧间隔
        self.tab_manager.resize_tabs(width, height)
        self.stacked_widget.setGeometry(tab_bar_width, 0, content_width, height)
        self.font_manager.update_all_fonts()
        
        # 广播窗口大小变化到共享内存
        self.shared_manager.broadcast_window_size_change(width, height)
        super().resizeEvent(event)
    def keyPressEvent(self, event):
        """处理键盘按键事件"""
        self.audio_preview.handle_key_event(event)
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 强制释放音频资源
        self.audio_preview.force_stop_audio()
        self.audio_preview.cleanup_preview_audio()
        event.accept()
        super().closeEvent(event)
    @property
    def audio_generator(self):
        """获取音频生成器（延迟加载）"""
        if self._audio_generator is None:
            from edge_audio_generator import AudioGenerator
            self._audio_generator = AudioGenerator()
        return self._audio_generator
    
    @property
    def notification_manager(self):
        """获取通知管理器（延迟加载）"""
        if self._notification_manager is None:
            from notification import NotificationManager
            self._notification_manager = NotificationManager(self)
        return self._notification_manager
    
    @property
    def generation_page(self):
        """获取生成页面（便捷属性）"""
        # 找到生成页面的索引
        for i in range(self.stacked_widget.count()):
            widget = self.stacked_widget.widget(i)
            if isinstance(widget, GenerationPage):
                return widget
        return None
def main():
    """应用程序入口点"""  
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()