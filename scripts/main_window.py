# coding=utf-8
import sys
import os

def _is_music_backend_mode():
    if "--music-backend" in sys.argv:
        return True
    if os.environ.get("YUANYUE_TTS_ROLE") == "music-backend":
        return True
    for arg in sys.argv[1:]:
        if os.path.basename(str(arg)).lower() == "music_backend.py":
            return True
    return False

if _is_music_backend_mode():
    from music_backend import MusicBackend
    backend = MusicBackend()
    for line in sys.stdin:
        backend.handle_command(line)
    sys.exit(0)

# Windows 下 PyInstaller / 等打包为 exe 后，multiprocessing 的工作进程会再次执行本入口文件。
# freeze_support 必须在「任何可能间接 import multiprocessing / 启动子进程」的模块导入之前调用，
# 否则子进程会一路执行到 if __name__ == '__main__' 里的 main()，再创建 QApplication + MainWindow，
# 表现为：主界面就绪后又弹出一个新的主窗口，并不断重复。
if __name__ == '__main__' and not _is_music_backend_mode():
    if sys.platform.startswith('win'):
        import multiprocessing

        multiprocessing.freeze_support()

from abc import update_abstractmethods
import uuid
import threading
import locale

# fcntl 只在 Unix/Linux 上可用，Windows 使用 msvcrt
if not sys.platform.startswith('win'):
    import fcntl

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QStackedWidget, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QPainter, QColor, QPainterPath

# 诊断：记录启动线程（使用print因为此时debug_logger还未导入）
_startup_thread_id = threading.current_thread().ident
print(f"[DIAGNOSTIC] 模块加载线程ID: {_startup_thread_id}")
print(f"[DIAGNOSTIC] sys.frozen={getattr(sys, 'frozen', False)}")

from audio_preview import AudioPreview
from hotkey_manager import HotkeyManager, HotkeyAction
from misc_func import AudioConfig, SettingsManager
from shared_memory_manager import get_shared_memory_manager
from debug_logger import debug_logger, LogLevel

# 导入GenerationPage用于属性检查
from generation_page import GenerationPage

# 全局变量：跟踪MainWindow实例数量
_main_window_instance_count = 0
_main_window_instances_lock = threading.Lock() 

class VersionInfos:
    """版本信息"""
    
    def __init__(self) -> None:
        self.this_version = '''☺packager-replace-version☺'''
        self.this_update_content = '''☺packager-replace-version-infos☺'''
        self.this_update_date = '''☺packager-replace-update-date☺'''
        # self.this_version = '''0.0'''
        # self.this_update_content = '''版本自述文本框每行最多十六个汉字
        # ABCDEFGHABCDEFGHABCDEFGA
        # 1234567890123245678901234567\n
        '''
        支持阿里百炼（千问）、Kimi、Minimax及Mimo（暂时归为其他）四家新的模型提供商
        支持文→文（普通对话）、图→文（图片识别、在线导入）两个场景下自选模型。
          注：文→音（TTS）场景仍待修改
    
        设置界面大改，采用更美观的界面结构与非常好动画，添加AI模型设置页，选项卡排序支持拖动
        '''
    def version(self):
        return self.this_version
    
    def update_content(self):
        return self.this_update_content
    
    def update_date(self):
        return self.this_update_date
version_info = VersionInfos()
if __name__ == '__main__':
    debug_logger.output(" ", LogLevel.ERROR, f"当前程序版本: {version_info.version()}", fold_code="MAIN_VERSION")
    debug_logger.output(" ", LogLevel.WARNING, f"更新日期: {version_info.update_date()}", fold_code="MAIN_VERSION")
    debug_logger.output(" ", LogLevel.INFO, f"更新内容摘要: {version_info.update_content()[:50]}...", fold_code="MAIN_VERSION")

# 在程序最开头添加编码设置
def setup_encoding():
    # 设置环境变量
    debug_logger.output("main_window.py", LogLevel.INFO, "正在设置系统编码环境", fold_code="MAIN_INIT")
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # 禁用 pygame 欢迎信息，缩短加载感知时间
    
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
            debug_logger.output("main_window.py", LogLevel.INFO, "Locale 设置为: chinese", fold_code="MAIN_INIT")
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
                debug_logger.output("main_window.py", LogLevel.INFO, "Locale 设置为: zh_CN.UTF-8", fold_code="MAIN_INIT")
            except:
                try:
                    locale.setlocale(locale.LC_ALL, '')
                    debug_logger.output("main_window.py", LogLevel.INFO, f"Locale 设置为默认值: {locale.getlocale()}", fold_code="MAIN_INIT")
                except Exception as e:
                    debug_logger.output("main_window.py", LogLevel.WARNING, f"Locale 设置失败: {str(e)}", fold_code="MAIN_INIT")
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
        debug_logger.output("main_window.py", LogLevel.INFO, "创建 AsyncInitializer 实例", fold_code="MAIN_INIT")
    
    def start(self):
        """开始异步初始化"""
        debug_logger.output("main_window.py", LogLevel.INFO, "开始异步初始化流程", fold_code="MAIN_INIT")
        self.timer.start(100)  # 100ms后开始第一个步骤
    
    def _process_initialization(self):
        """处理初始化步骤"""
        try:
            if self.current_step == 0:
                debug_logger.output("main_window.py", LogLevel.INFO, "执行异步初始化步骤 1: 创建标签页", fold_code="MAIN_INIT")
                self.parent_window._async_create_tab_pages()
                debug_logger.output("main_window.py", LogLevel.INFO, "步骤 1 完成：所有标签页已创建", fold_code="MAIN_INIT")
                self.current_step += 1
                self.timer.start(50)  # 50ms后开始下一个步骤
            elif self.current_step == 1:
                debug_logger.output("main_window.py", LogLevel.INFO, "执行异步初始化步骤 2: 初始化非关键组件", fold_code="MAIN_INIT")
                self.parent_window._async_init_non_critical_components()
                debug_logger.output("main_window.py", LogLevel.INFO, "步骤 2 完成：非关键组件初始化完毕", fold_code="MAIN_INIT")
                self.current_step += 1
                self.timer.stop()
                debug_logger.output("main_window.py", LogLevel.INFO, "异步初始化流程全部结束，触发收尾工作", fold_code="MAIN_INIT")
                self.parent_window._on_async_finished()
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"异步初始化过程中出错: {str(e)}", fold_code="MAIN_INIT")
            self.timer.stop()


class FontManager:
    """字体管理器"""
    
    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
        debug_logger.output("main_window.py", LogLevel.INFO, "初始化 FontManager", fold_code="MAIN_FONT")
    
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
        
        debug_logger.output("main_window.py", LogLevel.INFO, f"计算字体大小: 基础={base_font_size}, 其他={other_font_size}, 标签={tab_font_size} (比例={ratio:.2f})", fold_code="MAIN_FONT")
        return base_font_size, other_font_size, tab_font_size
    
    def update_all_fonts(self):
        """更新所有组件的字体"""
        debug_logger.output("main_window.py", LogLevel.INFO, "正在全局更新组件字体", fold_code="MAIN_FONT")
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
        
        # 更新听写页面字体
        if hasattr(self.parent_window, 'dictation_page') and self.parent_window.dictation_page:
            self._update_generation_page_fonts(other_font_size)
    
    def _update_generation_page_fonts(self, other_font_size: int):
        """更新生成页面各组件字体"""
        try:
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
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"更新页面字体失败: {str(e)}", fold_code="MAIN_FONT")
    
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
        debug_logger.output("main_window.py", LogLevel.INFO, "初始化 TabManager", fold_code="MAIN_TABS")
        
    def register_tab(self, name, display_name, widget_class):
        """注册新选项卡"""
        debug_logger.output("main_window.py", LogLevel.INFO, f"注册选项卡: {name} ({display_name})", fold_code="MAIN_TABS")
        self.tab_configs.append(TabConfig(name, display_name, widget_class))
        
    def setup_tabs(self):
        """设置选项卡"""
        debug_logger.output("main_window.py", LogLevel.INFO, "开始设置选项卡按钮和页面", fold_code="MAIN_TABS")
        self._create_tab_buttons()
        self._create_tab_pages()
        
    def _create_tab_buttons(self):
        """创建选项卡按钮"""
        debug_logger.output("main_window.py", LogLevel.DEBUG, f"准备创建 {len(self.tab_configs)} 个选项卡按钮", fold_code="MAIN_TABS")
        for i, tab_config in enumerate(self.tab_configs):
            btn = QPushButton(tab_config.display_name, self.parent_window)
            btn.setCheckable(True)
            btn.setChecked(i == self.current_tab_index)
            btn.clicked.connect(lambda checked, idx=i: self.switch_to_tab(idx))
            btn.setStyleSheet(self._get_tab_button_style())
            self.tab_buttons.append(btn)
        debug_logger.output("main_window.py", LogLevel.INFO, f"已成功创建 {len(self.tab_buttons)} 个选项卡按钮", fold_code="MAIN_TABS")

    def _create_tab_pages(self):
        """创建选项卡页面"""
        debug_logger.output("main_window.py", LogLevel.INFO, f"开始批量创建 {len(self.tab_configs)} 个选项卡页面", fold_code="MAIN_TABS")
        for tab_config in self.tab_configs:
            try:
                debug_logger.output("main_window.py", LogLevel.DEBUG, f"正在实例化页面: {tab_config.name}", fold_code="MAIN_TABS")
                page_widget = tab_config.widget_class(self.parent_window)
                self.parent_window.stacked_widget.addWidget(page_widget)
            except Exception as e:
                debug_logger.output("main_window.py", LogLevel.ERROR, f"创建页面 {tab_config.name} 失败: {str(e)}", fold_code="MAIN_TABS")

    def switch_to_tab(self, index):
        """切换到指定索引的选项卡"""
        if getattr(self.parent_window, "_is_onboarding", False):
            return
        if index == self.current_tab_index:
            return
        
        if index >= len(self.tab_configs):
            debug_logger.output("main_window.py", LogLevel.WARNING, f"尝试切换到无效的选项卡索引: {index}", fold_code="MAIN_TABS")
            return

        tab_name = self.tab_configs[index].name
        debug_logger.output("main_window.py", LogLevel.INFO, f"切换选项卡: 从 {self.current_tab_index} 切换到 {index} ({tab_name})", fold_code="MAIN_TABS")
        
        # 保存当前索引用于动画
        from_index = self.current_tab_index
        
        # 检查选项卡页面是否已创建
        if index >= self.parent_window.stacked_widget.count():
            debug_logger.output("main_window.py", LogLevel.INFO, f"页面 {index} 尚未创建，正在同步创建", fold_code="MAIN_TABS")
            # 页面尚未创建，需要同步创建
            try:
                self._create_tab_page(index)
            except Exception as e:
                debug_logger.output("main_window.py", LogLevel.ERROR, f"同步创建页面 {tab_name} 失败: {str(e)}", fold_code="MAIN_TABS")
                return
        
        # 更新按钮选中状态
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
            
        # 启动选项卡淡入淡出动画
        try:
            self.parent_window._start_tab_fade_animation(from_index, index)
            # 启动选项卡指示器动画
            self.parent_window._start_tab_indicator_animation(from_index, index)
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"启动切换动画失败: {str(e)}", fold_code="MAIN_ANIM")
            # 动画失败则直接切换
            self.parent_window.stacked_widget.setCurrentIndex(index)
        
        self.current_tab_index = index
        self._on_tab_switched(index)
    
    def _create_tab_page(self, index):
        """同步创建单个选项卡页面"""
        if index < len(self.tab_configs):
            tab_config = self.tab_configs[index]
            debug_logger.output("main_window.py", LogLevel.INFO, f"正在同步创建页面实例: {tab_config.name}", fold_code="MAIN_TABS")
            try:
                page_widget = tab_config.widget_class(self.parent_window)
                self.parent_window.stacked_widget.addWidget(page_widget)
                debug_logger.output("main_window.py", LogLevel.DEBUG, f"页面 {tab_config.name} 同步实例化成功", fold_code="MAIN_TABS")
            except Exception as e:
                debug_logger.output("main_window.py", LogLevel.ERROR, f"同步实例化页面 {tab_config.name} 失败: {str(e)}", fold_code="MAIN_TABS")
                raise

    def _on_tab_switched(self, index):
        """选项卡切换后处理"""
        # 获取当前页面的配置
        if index < len(self.tab_configs):
            tab_config = self.tab_configs[index]
            debug_logger.output("main_window.py", LogLevel.INFO, f"选项卡切换流程完成 -> {tab_config.name}", fold_code="MAIN_TABS")
            # 如果是生成页面，执行特殊处理
            if tab_config.name == 'generation' and hasattr(self.parent_window, 'generation_page'):
                debug_logger.output("main_window.py", LogLevel.DEBUG, "正在更新生成页面按钮状态", fold_code="MAIN_TABS")
                self.parent_window.generation_page._check_inputs_and_update_button()
            # 如果是听写页面，执行特殊处理
            elif tab_config.name == 'dictation' and hasattr(self.parent_window, 'dictation_page'):
                debug_logger.output("main_window.py", LogLevel.DEBUG, "正在更新听写页面按钮状态", fold_code="MAIN_TABS")
                self.parent_window.dictation_page._check_inputs_and_update_button()
        else:
            debug_logger.output("main_window.py", LogLevel.WARNING, f"选项卡切换回调收到无效索引: {index}", fold_code="MAIN_TABS")
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
    
    def get_active_tab_geometry(self):
        """获取当前激活选项卡按钮的位置和大小信息"""
        if not self.tab_buttons or self.current_tab_index >= len(self.tab_buttons):
            return None
        
        active_btn = self.tab_buttons[self.current_tab_index]
        return {
            'x': active_btn.x(),
            'y': active_btn.y(),
            'width': active_btn.width(),
            'height': active_btn.height()
        }
class MainWindow(QWidget):
    """主窗口类"""
    # 类变量：跟踪是否已经创建过MainWindow实例
    _instance_created = False
    _creation_thread_id = None
    
    def __init__(self):
        # 线程安全检查：确保只在主线程中创建MainWindow
        current_thread_id = threading.current_thread().ident
        
        # 全局实例计数
        global _main_window_instance_count
        with _main_window_instances_lock:
            _main_window_instance_count += 1
            instance_num = _main_window_instance_count
        
        debug_logger.output("main_window.py", LogLevel.INFO, f"[DIAGNOSTIC] MainWindow.__init__() 第 {instance_num} 次被调用", fold_code="MAIN_INIT")
        debug_logger.output("main_window.py", LogLevel.INFO, f"[DIAGNOSTIC] 调用线程ID: {current_thread_id}, 启动线程ID: {_startup_thread_id}", fold_code="MAIN_INIT")
        debug_logger.output("main_window.py", LogLevel.INFO, f"[DIAGNOSTIC] 是否在主线程中: {current_thread_id == _startup_thread_id}", fold_code="MAIN_INIT")
        
        # 防护：如果已经创建过MainWindow实例，记录警告但仍然创建（以便观察）
        if MainWindow._instance_created:
            debug_logger.output("main_window.py", LogLevel.WARNING, f"[DIAGNOSTIC] 警告：MainWindow实例已经存在！这是第 {instance_num} 个实例", fold_code="MAIN_INIT")
            debug_logger.output("main_window.py", LogLevel.WARNING, f"[DIAGNOSTIC] 首次创建在线程 {MainWindow._creation_thread_id}，当前在线程 {current_thread_id}", fold_code="MAIN_INIT")
            import traceback
            debug_logger.output("main_window.py", LogLevel.WARNING, f"[DIAGNOSTIC] 调用栈:\n{traceback.format_stack()}", fold_code="MAIN_INIT")
        else:
            MainWindow._instance_created = True
            MainWindow._creation_thread_id = current_thread_id
        
        super().__init__()
        debug_logger.output("main_window.py", LogLevel.INFO, "正在初始化主窗口...", fold_code="MAIN_INIT")
        self.version_info = version_info
        self._async_initializer = None
        self._init_core_components()
        self._load_settings()  # 优先加载设置
        self._init_ui()
        self._start_async_initialization()
        debug_logger.output("main_window.py", LogLevel.INFO, "主窗口同步初始化部分完成", fold_code="MAIN_INIT")
        
    def _init_core_components(self):
        """初始化核心组件"""
        debug_logger.output("main_window.py", LogLevel.INFO, "正在初始化核心组件...", fold_code="MAIN_INIT")
        try:
            self.config = AudioConfig()
            debug_logger.output("main_window.py", LogLevel.DEBUG, "已创建 AudioConfig 实例", fold_code="MAIN_INIT")
            
            self.settings_manager = SettingsManager()
            debug_logger.output("main_window.py", LogLevel.DEBUG, "已创建 SettingsManager 实例", fold_code="MAIN_INIT")
            
            self.hotkey_manager = HotkeyManager(self.settings_manager)
            debug_logger.output("main_window.py", LogLevel.DEBUG, "已创建 HotkeyManager 实例", fold_code="MAIN_INIT")
            
            self.audio_preview = AudioPreview(self, self.hotkey_manager)
            debug_logger.output("main_window.py", LogLevel.DEBUG, "已创建 AudioPreview 实例", fold_code="MAIN_INIT")
            
            self.font_manager = FontManager(self)
            debug_logger.output("main_window.py", LogLevel.DEBUG, "已创建 FontManager 实例", fold_code="MAIN_INIT")
            
            self.shared_manager = get_shared_memory_manager()  # 初始化共享内存管理器
            debug_logger.output("main_window.py", LogLevel.DEBUG, "已获取 SharedMemoryManager 实例", fold_code="MAIN_INIT")
            
            self._audio_generator = None  # 延迟加载
            self._notification_manager = None  # 延迟加载
            self._init_audio_state()
            self._init_ui_variables()
            debug_logger.output("main_window.py", LogLevel.INFO, "核心组件初始化完成", fold_code="MAIN_INIT")
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.CRITICAL, f"核心组件初始化失败: {str(e)}", fold_code="MAIN_INIT")
            raise

    def _init_audio_state(self):
        """初始化音频状态变量"""
        debug_logger.output("main_window.py", LogLevel.INFO, "正在重置音频状态变量", fold_code="MAIN_INIT")
        self.is_playing = False
        self.is_paused = False
        self.current_audio_length = 0
        self.current_audio_position = 0
        self.audio_cache = {}
        self.current_audio_path = None
        self.last_content_hash = None
        self.has_preview = False
        debug_logger.output("main_window.py", LogLevel.DEBUG, f"音频状态重置完毕: playing={self.is_playing}, paused={self.is_paused}", fold_code="MAIN_INIT")

    def _init_ui_variables(self):
        """初始化UI相关变量"""
        debug_logger.output("main_window.py", LogLevel.INFO, "初始化UI状态变量", fold_code="MAIN_INIT")
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
        self.tab_manager = TabManager(self)
        self.stacked_widget = QStackedWidget(self)
        debug_logger.output("main_window.py", LogLevel.DEBUG, "TabManager 和 StackedWidget 已准备就绪", fold_code="MAIN_INIT")
        self.tab_bar_background_color = None
        
        # 选项卡指示器动画相关属性
        self.tab_indicator_animation = None
        self.tab_indicator_start_pos = None
        self.tab_indicator_end_pos = None
        self.tab_indicator_animation_progress = 0.0
        
        # 选项卡切换淡入淡出动画相关属性
        self.tab_fade_animation = None
        self.tab_fade_animation_progress = 0.0
        self.tab_fade_out_complete = False
        self.pending_tab_index = None
        self._is_onboarding = False
        self._onboarding_page = None
        debug_logger.output("main_window.py", LogLevel.INFO, "UI状态变量初始化完成", fold_code="MAIN_INIT")

    def _init_ui(self):
        """初始化用户界面"""
        debug_logger.output("main_window.py", LogLevel.INFO, "开始构建UI布局...", fold_code="MAIN_INIT")
        self._setup_window_properties()
        self._setup_tabs()
        #self._setup_layout()
        if self.settings_manager.get_is_first_run():
            self.start_onboarding()
        self.font_manager.update_all_fonts()
        debug_logger.output("main_window.py", LogLevel.INFO, "UI布局构建完成", fold_code="MAIN_INIT")
    
    def _setup_window_properties(self):
        """设置窗口基本属性"""
        debug_logger.output("main_window.py", LogLevel.INFO, "配置窗口属性", fold_code="MAIN_INIT")
        self.setWindowTitle('源悦TTS')
        self.setGeometry(300, 300, self.default_width, self.default_height)
        self.setMinimumSize(1080, 720)
        
        # 使用设置中的背景色，如果没有设置则使用默认值
        background_color = self.settings_manager.get_Custom_value("background_color", "#E5E8EF")
        debug_logger.output("main_window.py", LogLevel.INFO, f"应用主题背景色: {background_color}", fold_code="MAIN_INIT")
        self.setStyleSheet(f"background-color: {background_color};")
        
        initial_font = QFont("微软雅黑", 26)
        self.setFont(initial_font)
        # 设置焦点策略
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 计算选项卡栏背景颜色（每个RGB值减48）
        self._calculate_tab_bar_background_color(background_color)
        
        # 广播初始窗口大小到共享内存
        debug_logger.output("main_window.py", LogLevel.INFO, f"向共享内存广播初始窗口大小: {self.default_width}x{self.default_height}", fold_code="MAIN_INIT")
        self.shared_manager.broadcast_window_size_change(self.default_width, self.default_height)

    def _setup_tabs(self):
        """设置选项卡系统"""
        debug_logger.output("main_window.py", LogLevel.INFO, "正在配置选项卡系统...", fold_code="MAIN_TABS")
        # 定义所有可能的选项卡及其类获取方法
        all_available_tabs = [
            ('welcome', '欢迎', self._get_welcome_page_class),
            ('dictation', '听写', self._get_generation_page_neo_class),
            ('settings', '设置', self._get_settings_page_class),
            ('personalization', '个性化', self._get_custom_page_class),
            ('misc', '杂项', self._get_misc_page_class),
            ('streaming', '流媒体', self._get_streaming_page_class)
        ]
        
        # 从设置中获取配置
        tab_order_str = self.settings_manager.get_Custom_value("tab_order", "welcome,dictation,settings,personalization,misc,streaming")
        debug_logger.output("main_window.py", LogLevel.INFO, f"读取选项卡排序配置: {tab_order_str}", fold_code="MAIN_TABS")
        tab_visibility_str = self.settings_manager.get_Custom_value("tab_visibility", "welcome,dictation,settings,personalization,misc,streaming")
        initial_tab_name = self.settings_manager.get_Custom_value("initial_tab", "welcome")
        
        tab_order = [t.strip() for t in tab_order_str.split(',') if t.strip()]
        tab_visibility = [t.strip() for t in tab_visibility_str.split(',') if t.strip()]
        
        # 强制 'settings' 必须可见
        if 'settings' not in tab_visibility:
            debug_logger.output("main_window.py", LogLevel.WARNING, "检测到设置页面被隐藏，已强制开启显示", fold_code="MAIN_TABS")
            tab_visibility.append('settings')
            
        # 针对新功能 'streaming'：如果它不在可见列表也不在排序列表中（可能是旧配置），则默认将其添加到最后
        if 'streaming' not in tab_visibility and 'streaming' not in tab_order:
            debug_logger.output("main_window.py", LogLevel.INFO, "检测到新功能 '流媒体' 未在配置中，正在自动注册", fold_code="MAIN_TABS")
            tab_visibility.append('streaming')
            tab_order.append('streaming')

        # 1. 过滤掉不显示的选项卡
        visible_tabs = [t for t in all_available_tabs if t[0] in tab_visibility]
        
        # 2. 根据用户定义的顺序进行排序
        # 创建一个名称到完整配置的映射
        name_to_config = {t[0]: t for t in visible_tabs}
        
        ordered_tabs = []
        # 首先按 order_list 中的顺序添加已在 visible_tabs 中的选项卡
        for name in tab_order:
            if name in name_to_config:
                ordered_tabs.append(name_to_config[name])
                del name_to_config[name] # 避免重复
        
        # 将剩余的可见选项卡（如果不在 order_list 中）按原始顺序添加到末尾
        for name, _, _ in all_available_tabs:
            if name in name_to_config:
                ordered_tabs.append(name_to_config[name])
        
        # 3. 注册选项卡
        for name, display_name, class_getter in ordered_tabs:
            debug_logger.output("main_window.py", LogLevel.INFO, f"注册选项卡: {name} -> {display_name}", fold_code="MAIN_TABS")
            self.tab_manager.register_tab(name, display_name, class_getter())
        
        # 4. 确定起始页索引
        start_index = 0
        # 检查初始页是否在可见列表中
        if initial_tab_name not in tab_visibility:
            debug_logger.output("main_window.py", LogLevel.WARNING, f"起始页 {initial_tab_name} 当前不可见，已自动回退至首个可见页", fold_code="MAIN_TABS")
            initial_tab_name = ordered_tabs[0][0] if ordered_tabs else 'welcome'
            
        for i, tab_config in enumerate(self.tab_manager.tab_configs):
            if tab_config.name == initial_tab_name:
                start_index = i
                debug_logger.output("main_window.py", LogLevel.INFO, f"确定程序启动页索引: {start_index} ({initial_tab_name})", fold_code="MAIN_TABS")
                break
        
        self.tab_manager.current_tab_index = start_index

        # 只创建选项卡按钮，页面将在异步中创建
        self.tab_manager._create_tab_buttons()
        debug_logger.output("main_window.py", LogLevel.INFO, f"选项卡系统配置完成，初始显示: {initial_tab_name}", fold_code="MAIN_TABS")

    def start_onboarding(self):
        if self._is_onboarding:
            return
        try:
            from onboarding_page import OnboardingPage
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"首次运行需要启动引导页，但导入 onboarding_page 失败: {str(e)}", fold_code="MAIN_ONBOARD")
            return

        debug_logger.output("main_window.py", LogLevel.INFO, "首次运行，启动新手引导", fold_code="MAIN_ONBOARD")
        self._is_onboarding = True

        self._onboarding_page = OnboardingPage(self)
        self._onboarding_page.tutorial_finished.connect(self.finish_onboarding)

        self.stacked_widget.addWidget(self._onboarding_page)
        self.stacked_widget.setCurrentWidget(self._onboarding_page)

        if hasattr(self, "tab_manager"):
            for btn in self.tab_manager.tab_buttons:
                btn.setEnabled(False)
                btn.hide()

        self.updateGeometry()
        self.resizeEvent(None)
        self.update()

    def finish_onboarding(self):
        if not self._is_onboarding and self._onboarding_page is None:
            return

        debug_logger.output("main_window.py", LogLevel.INFO, "新手引导结束，恢复常规界面", fold_code="MAIN_ONBOARD")
        self._is_onboarding = False

        if hasattr(self, "tab_manager"):
            for btn in self.tab_manager.tab_buttons:
                btn.setEnabled(True)
                btn.show()

        if self._onboarding_page is not None:
            self.stacked_widget.removeWidget(self._onboarding_page)
            self._onboarding_page.deleteLater()
            self._onboarding_page = None

        target_index = self.tab_manager.current_tab_index if hasattr(self, "tab_manager") else 0
        if target_index < self.stacked_widget.count():
            self.stacked_widget.setCurrentIndex(target_index)
            if hasattr(self, "tab_manager") and target_index < len(self.tab_manager.tab_buttons):
                for i, btn in enumerate(self.tab_manager.tab_buttons):
                    btn.setChecked(i == target_index)
        else:
            QTimer.singleShot(50, self.finish_onboarding)

        self.resizeEvent(None)
        self.update()

    def _start_async_initialization(self):
        """启动异步初始化"""
        debug_logger.output("main_window.py", LogLevel.INFO, "触发异步初始化流程", fold_code="MAIN_ASYNC")
        self._async_initializer = AsyncInitializer(self)
        self._async_initializer.start()
    
    def _on_async_finished(self):
        """异步初始化完成"""
        debug_logger.output("main_window.py", LogLevel.INFO, "异步初始化流程全部结束", fold_code="MAIN_ASYNC")
        self._async_initializer = None
    
    def _async_create_tab_pages(self):
        """异步创建选项卡页面"""
        debug_logger.output("main_window.py", LogLevel.INFO, "开始异步创建各页面实例...", fold_code="MAIN_ASYNC")
        onboarding_widget = getattr(self, "_onboarding_page", None)
        has_onboarding = onboarding_widget is not None and self.stacked_widget.indexOf(onboarding_widget) != -1
        # 延迟创建选项卡页面
        for i, tab_config in enumerate(self.tab_manager.tab_configs):
            try:
                debug_logger.output("main_window.py", LogLevel.INFO, f"正在实例化页面: {tab_config.name}", fold_code="MAIN_ASYNC")
                page_widget = tab_config.widget_class(self)
                if has_onboarding:
                    self.stacked_widget.insertWidget(i, page_widget)
                else:
                    self.stacked_widget.addWidget(page_widget)
                
                # 如果页面有共享内存信号连接方法，则调用它
                if hasattr(page_widget, '_connect_shared_memory_signals'):
                    debug_logger.output("main_window.py", LogLevel.DEBUG, f"正在连接页面 {tab_config.name} 的共享内存信号", fold_code="MAIN_ASYNC")
                    page_widget._connect_shared_memory_signals()
                
                debug_logger.output("main_window.py", LogLevel.DEBUG, f"页面 {tab_config.name} 实例化并添加成功", fold_code="MAIN_ASYNC")
            except Exception as e:
                debug_logger.output("main_window.py", LogLevel.ERROR, f"实例化页面 {tab_config.name} 时出错: {str(e)}", fold_code="MAIN_ASYNC")
        
        if getattr(self, "_is_onboarding", False) and onboarding_widget is not None and self.stacked_widget.indexOf(onboarding_widget) != -1:
            self.stacked_widget.setCurrentWidget(onboarding_widget)
            return

        # 设置初始显示的页面
        if self.tab_manager.current_tab_index < self.stacked_widget.count():
            debug_logger.output("main_window.py", LogLevel.INFO, f"切换至初始显示页面 (索引: {self.tab_manager.current_tab_index})", fold_code="MAIN_ASYNC")
            self.stacked_widget.setCurrentIndex(self.tab_manager.current_tab_index)
        else:
            debug_logger.output("main_window.py", LogLevel.WARNING, f"初始页面索引 {self.tab_manager.current_tab_index} 超出范围 (总数: {self.stacked_widget.count()})", fold_code="MAIN_ASYNC")
    
    def _async_init_non_critical_components(self):
        """异步初始化非关键组件"""
        try:
            debug_logger.output("main_window.py", LogLevel.INFO, "执行非关键组件异步初始化", fold_code="MAIN_ASYNC")
            # 延迟导入以加快启动
            from notification import NotificationManager
            self._notification_manager = NotificationManager(self)
            debug_logger.output("main_window.py", LogLevel.INFO, "NotificationManager 初始化成功", fold_code="MAIN_ASYNC")
            
            # 设置字体
            self.font_manager.update_all_fonts()
            debug_logger.output("main_window.py", LogLevel.INFO, "全局字体适配完成", fold_code="MAIN_ASYNC")
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"非关键组件异步初始化失败: {str(e)}", fold_code="MAIN_ASYNC")
    
    def _load_settings(self):
        """加载设置"""
        debug_logger.output("main_window.py", LogLevel.INFO, "正在加载全局设置...", fold_code="MAIN_INIT")
        self._load_stretch_setting()
        self._load_hotkeys()
        self._connect_shared_memory_signals()
        debug_logger.output("main_window.py", LogLevel.INFO, "全局设置加载完成", fold_code="MAIN_INIT")

    def _load_stretch_setting(self):
        """加载音频拉伸设置"""
        stretch_factor = self.settings_manager.get_stretch_factor()
        self.config.stretch_factor = stretch_factor
        
        stretch_enabled = self.settings_manager.get_stretch_enabled()
        self.config.stretch_enabled = stretch_enabled
        debug_logger.output("main_window.py", LogLevel.INFO, f"加载音频拉伸配置: 启用={stretch_enabled}, 系数={stretch_factor}", fold_code="MAIN_INIT")

    def _load_hotkeys(self):
        """加载热键设置"""
        if hasattr(self, 'hotkey_manager'):
            debug_logger.output("main_window.py", LogLevel.INFO, "正在加载全局热键配置", fold_code="MAIN_INIT")
            self.hotkey_manager.load_hotkeys()

    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        if hasattr(self, 'shared_manager') and self.shared_manager:
            debug_logger.output("main_window.py", LogLevel.INFO, "连接共享内存变更信号", fold_code="MAIN_SHARED")
            self.shared_manager.settings_changed.connect(self._on_settings_changed_from_shared_memory)

    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置更改"""
        try:
            debug_logger.output("main_window.py", LogLevel.DEBUG, f"收到共享内存同步请求: 页面={page_name}", fold_code="MAIN_SHARED")
            if page_name in ['custom', 'custom_page']:
                # 如果是个性化页面的设置更改，重新加载热键
                debug_logger.output("main_window.py", LogLevel.INFO, "检测到个性化设置变更，正在同步热键和UI主题", fold_code="MAIN_SHARED")
                self._load_hotkeys()
                
                # 如果有背景颜色更改，也在这里处理
                bg_color = settings_data.get('background_color')
                if bg_color:
                    debug_logger.output("main_window.py", LogLevel.INFO, f"同步背景色至: {bg_color}", fold_code="MAIN_SHARED")
                    self.setStyleSheet(f"background-color: {bg_color};")
                    self._calculate_tab_bar_background_color(bg_color)
                    self.update()
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"同步共享内存设置时出错: {str(e)}", fold_code="MAIN_SHARED")
    
    def _calculate_tab_bar_background_color(self, background_color):
        """计算选项卡栏背景颜色（每个RGB值减45）"""
        try:
            debug_logger.output("main_window.py", LogLevel.INFO, f"正在计算选项卡栏背景色，基色: {background_color}", fold_code="MAIN_UI")
            # 移除#号并转换为RGB
            hex_color = background_color.lstrip('#')
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                
                # 每个RGB值减45，确保不小于0
                r = max(0, r - 45)
                g = max(0, g - 45)
                b = max(0, b - 45)
                
                self.tab_bar_background_color = QColor(r, g, b)
                debug_logger.output("main_window.py", LogLevel.INFO, f"计算完成，选项卡栏背景色: RGB({r}, {g}, {b})", fold_code="MAIN_UI")
        except (ValueError, IndexError) as e:
            # 如果转换失败，使用默认颜色
            debug_logger.output("main_window.py", LogLevel.WARNING, f"背景色计算解析失败: {str(e)}，已使用默认兜底颜色", fold_code="MAIN_UI")
            self.tab_bar_background_color = QColor(200, 200, 200)

    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        width = self.width()
        height = self.height()
        debug_logger.output("main_window.py", LogLevel.INFO, f"触发窗口缩放事件: {width}x{height}", fold_code="MAIN_UI")
        
        if getattr(self, "_is_onboarding", False):
            tab_bar_width = 0
            content_width = width
        else:
            tab_bar_width = int(width * 0.1)
            content_width = width - tab_bar_width - 10  # 右侧间隔
            self.tab_manager.resize_tabs(width, height)
            
        self.stacked_widget.setGeometry(tab_bar_width, 0, content_width, height)
        self.font_manager.update_all_fonts()
        
        # 广播窗口大小变化到共享内存
        debug_logger.output("main_window.py", LogLevel.DEBUG, "正在向共享内存同步最新窗口尺寸", fold_code="MAIN_UI")
        self.shared_manager.broadcast_window_size_change(width, height)
        if event is not None:
            super().resizeEvent(event)

    def keyPressEvent(self, event):
        """处理键盘按键事件"""
        # 仅在调试级别较低时才记录所有按键
        # debug_logger.output("main_window.py", LogLevel.DEBUG, f"收到键盘事件: {event.key()}", fold_code="MAIN_EVENT")
        self.audio_preview.handle_key_event(event)
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        debug_logger.output("main_window.py", LogLevel.INFO, "正在安全退出应用程序...", fold_code="MAIN_EXIT")
        # 强制释放音频资源
        try:
            self.audio_preview.force_stop_audio()
            self.audio_preview.cleanup_preview_audio()
            debug_logger.output("main_window.py", LogLevel.INFO, "音频资源已成功释放", fold_code="MAIN_EXIT")
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"释放音频资源时出错: {str(e)}", fold_code="MAIN_EXIT")
            
        event.accept()
        super().closeEvent(event)
        debug_logger.output("main_window.py", LogLevel.INFO, "主窗口已安全关闭", fold_code="MAIN_EXIT")
    
    def paintEvent(self, event):
        """绘制选项卡栏背景和激活选项卡指示器"""
        if getattr(self, "_is_onboarding", False):
            super().paintEvent(event)
            return

        if self.tab_bar_background_color and self.tab_manager.tab_buttons:
            # debug_logger.output("main_window.py", LogLevel.DEBUG, "正在执行 paintEvent 绘制界面组件", fold_code="MAIN_UI")
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)  # 启用抗锯齿
            
            # 绘制选项卡栏背景
            painter.setBrush(self.tab_bar_background_color)
            painter.setPen(Qt.NoPen)
            
            # 计算背景渲染范围
            # x轴：选项卡栏宽度为窗口宽度的10%
            # y轴：背景与窗口高度相同
            width = self.width()
            tab_bar_width = int(width * 0.1)
            background_height = self.height()
            
            painter.drawRect(0, 0, tab_bar_width, background_height)
            
            # 绘制激活选项卡的指示器（支持动画）
            active_tab_geometry = self._get_animated_tab_indicator_geometry()
            if active_tab_geometry:
                # 在激活选项卡按钮下方绘制指示器，尺寸大于选项卡按钮
                indicator_rect_width = active_tab_geometry['width'] + 10  # 宽度增加10像素
                indicator_rect_height = active_tab_geometry['height'] + 10  # 高度增加10像素
                indicator_rect_x = active_tab_geometry['x'] - 5  # X位置左移5像素以居中
                indicator_rect_y = active_tab_geometry['y'] - 5  # Y位置上移5像素以包围按钮
                
                # 创建圆角矩形路径
                path = QPainterPath()
                radius = 8  # 圆角半径
                path.addRoundedRect(
                    indicator_rect_x, 
                    indicator_rect_y, 
                    indicator_rect_width, 
                    indicator_rect_height, 
                    radius, 
                    radius
                )
                
                # 从设置中获取高亮按钮颜色，默认为钢蓝色
                highlight_color_str = self.settings_manager.Custom.get_value("highlight_button_color", "#4682D6")
                # 解析颜色字符串
                highlight_color = QColor(highlight_color_str)
                
                # 设置指示器颜色（半透明的高亮色）
                indicator_color = QColor(highlight_color.red(), highlight_color.green(), highlight_color.blue(), 100)  # 50%透明度
                painter.setBrush(indicator_color)
                painter.setPen(highlight_color)  # 边框颜色
                painter.drawPath(path)
        
        super().paintEvent(event)
    
    def _start_tab_indicator_animation(self, from_index, to_index):
        """开始选项卡指示器动画"""
        debug_logger.output("main_window.py", LogLevel.DEBUG, f"启动选项卡指示器动画: {from_index} -> {to_index}", fold_code="MAIN_ANIM")
        # 如果已经有动画在运行，停止它
        if self.tab_indicator_animation and self.tab_indicator_animation.isActive():
            debug_logger.output("main_window.py", LogLevel.DEBUG, "停止正在运行的指示器动画", fold_code="MAIN_ANIM")
            self.tab_indicator_animation.stop()
        
        # 获取起始和结束位置
        if from_index < len(self.tab_manager.tab_buttons) and to_index < len(self.tab_manager.tab_buttons):
            from_btn = self.tab_manager.tab_buttons[from_index]
            to_btn = self.tab_manager.tab_buttons[to_index]
            
            self.tab_indicator_start_pos = {
                'x': from_btn.x(),
                'y': from_btn.y(),
                'width': from_btn.width(),
                'height': from_btn.height()
            }
            
            self.tab_indicator_end_pos = {
                'x': to_btn.x(),
                'y': to_btn.y(),
                'width': to_btn.width(),
                'height': to_btn.height()
            }
            
            # 重置动画进度
            self.tab_indicator_animation_progress = 0.0
            
            # 创建动画定时器
            from PyQt5.QtCore import QTimer
            self.tab_indicator_animation = QTimer(self)
            self.tab_indicator_animation.timeout.connect(self._update_tab_indicator_animation)
            self.tab_indicator_animation.start(16)  # 约60 FPS
            debug_logger.output("main_window.py", LogLevel.DEBUG, f"指示器动画定时器已启动 (从 y={self.tab_indicator_start_pos['y']} 到 y={self.tab_indicator_end_pos['y']})", fold_code="MAIN_ANIM")
        else:
            debug_logger.output("main_window.py", LogLevel.WARNING, f"指示器动画启动失败: 索引无效 ({from_index} -> {to_index})", fold_code="MAIN_ANIM")
    
    def _update_tab_indicator_animation(self):
        """更新选项卡指示器动画"""
        # 从设置中获取动画速度（现在以毫秒为单位，需要转换为秒）
        from misc_func import SettingsManager
        settings_manager = SettingsManager()
        animation_speed_ms = int(settings_manager.Custom.get_value("indicator_animation_speed", "50"))
        animation_speed = animation_speed_ms / 1000.0  # 转换为秒
        
        # 增加动画进度（调整动画速度以获得更平滑的效果）
        self.tab_indicator_animation_progress += animation_speed  # 使用设置中的动画速度
        
        if self.tab_indicator_animation_progress >= 1.0:
            # 动画完成
            debug_logger.output("main_window.py", LogLevel.DEBUG, "选项卡指示器动画播放完毕", fold_code="MAIN_ANIM")
            self.tab_indicator_animation_progress = 1.0
            self.tab_indicator_animation.stop()
            self.tab_indicator_animation = None
            self.tab_indicator_start_pos = None
            self.tab_indicator_end_pos = None
        
        # 触发重绘
        self.update()
    
    def _ease_out_cubic(self, t):
        """三次方缓出函数"""
        return 1.0 - pow(1.0 - t, 3)
    
    def _get_animated_tab_indicator_geometry(self):
        """获取动画中的选项卡指示器几何信息"""
        if (self.tab_indicator_start_pos is None or 
            self.tab_indicator_end_pos is None or
            self.tab_indicator_animation_progress <= 0.0):
            # 没有动画时返回当前激活选项卡的位置
            geometry = self.tab_manager.get_active_tab_geometry()
            # 应用设置中的偏移和调整
            return self._apply_indicator_settings(geometry)
        
        if self.tab_indicator_animation_progress >= 1.0:
            # 动画完成时返回目标位置
            # 应用设置中的偏移和调整
            return self._apply_indicator_settings(self.tab_indicator_end_pos)
        
        # 使用缓动函数计算当前位置
        start = self.tab_indicator_start_pos
        end = self.tab_indicator_end_pos
        # 应用三次方缓出函数
        eased_progress = self._ease_out_cubic(self.tab_indicator_animation_progress)
        
        geometry = {
            'x': start['x'] + (end['x'] - start['x']) * eased_progress,
            'y': start['y'] + (end['y'] - start['y']) * eased_progress,
            'width': start['width'] + (end['width'] - start['width']) * eased_progress,
            'height': start['height'] + (end['height'] - start['height']) * eased_progress
        }
        
        # 应用设置中的偏移和调整
        return self._apply_indicator_settings(geometry)
    
    def _apply_indicator_settings(self, geometry):
        """应用指示器设置（偏移和调整）"""
        from misc_func import SettingsManager
        settings_manager = SettingsManager()
        
        # 获取设置值
        x_offset = int(settings_manager.Custom.get_value("indicator_x_offset", "0"))
        y_offset = int(settings_manager.Custom.get_value("indicator_y_offset", "0"))
        width_adjust = int(settings_manager.Custom.get_value("indicator_width_adjust", "0"))
        height_adjust = int(settings_manager.Custom.get_value("indicator_height_adjust", "0"))
        
        # 应用偏移和调整
        adjusted_geometry = geometry.copy()
        adjusted_geometry['x'] += x_offset
        adjusted_geometry['y'] += y_offset
        adjusted_geometry['width'] += width_adjust
        adjusted_geometry['height'] += height_adjust
        
        return adjusted_geometry
    
    def _start_tab_fade_animation(self, from_index, to_index):
        """开始选项卡淡入淡出动画"""
        debug_logger.output("main_window.py", LogLevel.DEBUG, f"启动选项卡淡入淡出动画: {from_index} -> {to_index}", fold_code="MAIN_ANIM")
        # 如果已经有动画在运行，停止它
        if self.tab_fade_animation and self.tab_fade_animation.isActive():
            debug_logger.output("main_window.py", LogLevel.DEBUG, "停止正在运行的淡入淡出动画", fold_code="MAIN_ANIM")
            self.tab_fade_animation.stop()
        
        # 初始化动画属性
        self.tab_fade_animation_progress = 0.0
        self.tab_fade_out_complete = False
        self.pending_tab_index = to_index
        
        # 获取当前页面和目标页面
        if from_index < self.stacked_widget.count() and to_index < self.stacked_widget.count():
            try:
                from PyQt5.QtWidgets import QGraphicsOpacityEffect
                from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
                
                # 为当前页面添加透明度效果
                self.from_widget = self.stacked_widget.widget(from_index)
                self.from_opacity_effect = QGraphicsOpacityEffect()
                self.from_widget.setGraphicsEffect(self.from_opacity_effect)
                
                # 创建淡出动画
                self.fade_out_animation = QPropertyAnimation(self.from_opacity_effect, b"opacity")
                # 从设置获取动画时长 - 使用一半时间用于淡出
                animation_speed = int(self.settings_manager.Custom.get_value("tab_switch_speed", "300"))
                self.fade_out_animation.setDuration(animation_speed // 2)  # 使用一半时间
                self.fade_out_animation.setStartValue(1.0)
                self.fade_out_animation.setEndValue(0.0)
                self.fade_out_animation.setEasingCurve(QEasingCurve.OutCubic)  # 三次方缓出
                
                # 为目标页面添加透明度效果并隐藏
                self.to_widget = self.stacked_widget.widget(to_index)
                self.to_opacity_effect = QGraphicsOpacityEffect()
                self.to_opacity_effect.setOpacity(0.0)  # 初始透明
                self.to_widget.setGraphicsEffect(self.to_opacity_effect)
                self.to_widget.setVisible(True)  # 确保目标页面可见
                
                # 创建淡入动画
                self.fade_in_animation = QPropertyAnimation(self.to_opacity_effect, b"opacity")
                self.fade_in_animation.setDuration(animation_speed // 2)  # 使用一半时间
                self.fade_in_animation.setStartValue(0.0)
                self.fade_in_animation.setEndValue(1.0)
                self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)  # 三次方缓出
                
                # 连接淡出完成信号到淡入动画开始
                self.fade_out_animation.finished.connect(self._on_fade_out_finished)
                
                # 开始淡出动画
                self.fade_out_animation.start()
                debug_logger.output("main_window.py", LogLevel.DEBUG, f"淡出动画已开始 (时长: {animation_speed // 2}ms)", fold_code="MAIN_ANIM")
                
                # 创建一个定时器来管理整个动画流程
                from PyQt5.QtCore import QTimer
                self.tab_fade_animation = QTimer(self)
                self.tab_fade_animation.timeout.connect(self._update_tab_fade_animation)
                self.tab_fade_animation.start(16)  # 约60 FPS
            except Exception as e:
                debug_logger.output("main_window.py", LogLevel.ERROR, f"启动淡入淡出动画失败: {str(e)}", fold_code="MAIN_ANIM")
        else:
             debug_logger.output("main_window.py", LogLevel.WARNING, f"淡入淡出动画启动失败: 页面索引无效 ({from_index} -> {to_index})", fold_code="MAIN_ANIM")
    
    def _update_tab_fade_animation(self):
        """更新选项卡淡入淡出动画"""
        # 这个方法主要用于管理动画定时器，实际的动画由QPropertyAnimation处理
        pass
    
    def _on_fade_out_finished(self):
        """淡出动画完成后的处理"""
        debug_logger.output("main_window.py", LogLevel.DEBUG, f"淡出阶段结束，正在切换堆栈窗口索引至: {self.pending_tab_index}", fold_code="MAIN_ANIM")
        # 淡出完成后，切换到目标页面
        try:
            self.stacked_widget.setCurrentIndex(self.pending_tab_index)
            debug_logger.output("main_window.py", LogLevel.DEBUG, "堆栈窗口索引切换成功，开始淡入阶段", fold_code="MAIN_ANIM")
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.ERROR, f"切换堆栈窗口索引失败: {str(e)}", fold_code="MAIN_ANIM")
        
        # 开始淡入动画
        self.fade_in_animation.start()
        
        # 连接淡入完成信号到清理方法
        self.fade_in_animation.finished.connect(self._on_fade_in_finished)
    
    def _on_fade_in_finished(self):
        """淡入动画完成后的清理工作"""
        debug_logger.output("main_window.py", LogLevel.DEBUG, "淡入阶段结束，清理动画临时效果", fold_code="MAIN_ANIM")
        # 移除透明度效果
        try:
            if hasattr(self, 'from_widget') and self.from_widget:
                self.from_widget.setGraphicsEffect(None)
            if hasattr(self, 'to_widget') and self.to_widget:
                self.to_widget.setGraphicsEffect(None)
            debug_logger.output("main_window.py", LogLevel.DEBUG, "GraphicsEffect 清理完成", fold_code="MAIN_ANIM")
        except Exception as e:
            debug_logger.output("main_window.py", LogLevel.WARNING, f"清理 GraphicsEffect 时出错: {str(e)}", fold_code="MAIN_ANIM")
        
        # 停止并清理动画
        if self.tab_fade_animation:
            self.tab_fade_animation.stop()
            self.tab_fade_animation = None
        self.pending_tab_index = None
        self.tab_fade_out_complete = False
        debug_logger.output("main_window.py", LogLevel.INFO, "选项卡切换流程全部完成", fold_code="MAIN_ANIM")
    
    def _ease_out_cubic(self, t):
        """三次方缓出函数"""
        return 1.0 - pow(1.0 - t, 3)
    @property
    def audio_generator(self):
        """获取音频生成器（延迟加载）"""
        if self._audio_generator is None:
            debug_logger.output("main_window.py", LogLevel.INFO, "正在延迟加载音频生成器组件", fold_code="MAIN_LAZY")
            from edge_audio_generator import AudioGenerator
            self._audio_generator = AudioGenerator()
        return self._audio_generator
    
    @property
    def notification_manager(self):
        """获取通知管理器（延迟加载）"""
        if self._notification_manager is None:
            debug_logger.output("main_window.py", LogLevel.INFO, "正在延迟加载通知管理器组件", fold_code="MAIN_LAZY")
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
    
    def _get_welcome_page_class(self):
        """获取欢迎页面类"""
        from welcome_page import WelcomePage
        return WelcomePage

    def _get_generation_page_neo_class(self):
        """获取生成页面类"""
        from generation_page_neo import GenerationPage
        return GenerationPage

    def _get_settings_page_class(self):
        """获取设置页面类"""
        from settings_page import SettingsPage
        return SettingsPage

    def _get_custom_page_class(self):
        """获取个性化页面类"""
        from custom_page import CustomPage
        return CustomPage

    def _get_misc_page_class(self):
        """获取杂项页面类"""
        from misc_page import MiscPage
        return MiscPage

    def _get_streaming_page_class(self):
        """获取流媒体页面类"""
        from streaming_page import StreamingPage
        return StreamingPage

    def refresh_theme(self):
        """刷新主题显示"""
        # 重新加载背景颜色
        background_color = self.settings_manager.Custom.get_value("background_color", "#E5E8EF")
        debug_logger.output("main_window.py", LogLevel.INFO, f"刷新主题，背景色: {background_color}", fold_code="MAIN_UI")
        self.setStyleSheet(f"background-color: {background_color};")
        
        # 重新计算选项卡栏背景颜色
        self._calculate_tab_bar_background_color(background_color)
        
        # 触发重绘以更新选项卡指示器颜色
        self.update()

class SingleInstanceChecker:
    """单实例检查器，确保只有一个实例运行"""
    _instance_file = None
    _lock_file_path = None
    
    @classmethod
    def is_already_running(cls):
        """检查是否已有实例在运行"""
        # 在 PyInstaller 环境下使用临时目录
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            lock_dir = os.path.join(os.path.dirname(sys.executable), '.lock')
        else:
            # 开发环境
            lock_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.lock')
        
        try:
            os.makedirs(lock_dir, exist_ok=True)
            lock_file = os.path.join(lock_dir, 'app.lock')
            cls._lock_file_path = lock_file
            
            # 尝试锁定文件
            cls._instance_file = open(lock_file, 'w')
            
            # 根据平台选择锁定方式
            if sys.platform.startswith('win'):
                # Windows: 使用 msvcrt 进行文件锁定
                import msvcrt
                # Windows 下使用简单的文件存在性检查作为后备
                # msvcrt.locking 在某些情况下可能不工作
                # 这里使用文件独占访问作为锁
                try:
                    # 尝试以独占模式重新打开文件
                    cls._instance_file.close()
                    cls._instance_file = open(lock_file, 'r+')
                    # 写入当前进程ID
                    cls._instance_file.write(str(os.getpid()))
                    cls._instance_file.flush()
                    # 再次检查文件中的PID
                    cls._instance_file.seek(0)
                    content = cls._instance_file.read()
                    pid = int(content.strip()) if content.strip().isdigit() else 0
                    
                    # 检查进程是否存在（使用跨平台方法）
                    if pid != 0 and pid != os.getpid():
                        try:
                            import psutil
                            if psutil.pid_exists(pid):
                                cls._instance_file.close()
                                cls._instance_file = None
                                return True  # 已有实例在运行
                        except ImportError:
                            # 如果没有 psutil，使用其他方法检查
                            # Windows 下可以尝试打开进程
                            if sys.platform.startswith('win'):
                                import ctypes
                                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                                try:
                                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                                    if handle:
                                        ctypes.windll.kernel32.CloseHandle(handle)
                                        cls._instance_file.close()
                                        cls._instance_file = None
                                        return True
                                except:
                                    pass
                except:
                    # 如果文件被占用，说明已有实例在运行
                    cls._instance_file.close()
                    cls._instance_file = None
                    return True
            else:
                # Unix/Linux: 使用 fcntl
                fcntl.flock(cls._instance_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                cls._instance_file.write(str(uuid.uuid4()))
                cls._instance_file.flush()
            
            return False  # 没有其他实例在运行
        except (IOError, OSError) as e:
            # 文件被锁定或有其他I/O错误，说明已有实例在运行
            if cls._instance_file:
                try:
                    cls._instance_file.close()
                except:
                    pass
                cls._instance_file = None
            return True

def main():
    """应用程序入口点"""
    # 诊断：记录启动信息
    debug_logger.output("main_window.py", LogLevel.INFO, "[DIAGNOSTIC] main() 函数被调用", fold_code="MAIN_INIT")
    debug_logger.output("main_window.py", LogLevel.INFO, f"[DIAGNOSTIC] 当前线程ID: {threading.current_thread().ident}", fold_code="MAIN_INIT")
    debug_logger.output("main_window.py", LogLevel.INFO, f"[DIAGNOSTIC] sys.argv: {sys.argv}", fold_code="MAIN_INIT")
    debug_logger.output("main_window.py", LogLevel.INFO, f"[DIAGNOSTIC] sys.frozen: {getattr(sys, 'frozen', False)}", fold_code="MAIN_INIT")
    
    # multiprocessing.freeze_support() 已在文件最前部、本模块其余 import 之前调用（见文件开头注释）
    
    # 检查是否已有实例在运行
    if SingleInstanceChecker.is_already_running():
        debug_logger.output("main_window.py", LogLevel.WARNING, "检测到已有实例在运行，退出当前启动", fold_code="MAIN_INIT")
        return 1
    
    debug_logger.output("main_window.py", LogLevel.INFO, "[DIAGNOSTIC] 开始创建 QApplication 实例", fold_code="MAIN_INIT")
    app = QApplication(sys.argv)
    
    debug_logger.output("main_window.py", LogLevel.INFO, "[DIAGNOSTIC] 开始创建 MainWindow 实例", fold_code="MAIN_INIT")
    window = MainWindow()
    
    debug_logger.output("main_window.py", LogLevel.INFO, "[DIAGNOSTIC] 调用 window.show()", fold_code="MAIN_INIT")
    window.show()
    
    debug_logger.output("main_window.py", LogLevel.INFO, "[DIAGNOSTIC] 进入事件循环 app.exec_()", fold_code="MAIN_INIT")
    exit_code = app.exec_()
    
    # 清理文件锁
    if SingleInstanceChecker._instance_file:
        try:
            if sys.platform.startswith('win'):
                # Windows: 不需要解锁，只需要关闭文件
                SingleInstanceChecker._instance_file.close()
            else:
                # Unix/Linux: 使用 fcntl 解锁
                fcntl.flock(SingleInstanceChecker._instance_file.fileno(), fcntl.LOCK_UN)
                SingleInstanceChecker._instance_file.close()
        except:
            pass
    
    return exit_code


if __name__ == '__main__':
    exit_code = main()
    if exit_code:
        sys.exit(exit_code)
