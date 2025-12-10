from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt


class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()
    
    def init_ui(self):
        """初始化UI界面"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        # 创建欢迎标签
        welcome_label = QLabel("欢迎使用\n本程序还在测试\n\n该页面计划用于设置初始化和程序介绍\n但现在我熬不动了我想睡觉\n遇到问题请在github页面提交issue/pr\n感谢", self)
        welcome_label.setAlignment(Qt.AlignCenter)
        
        # 添加到布局
        layout.addWidget(welcome_label)
        self.setLayout(layout)
    
    def _reload_page(self, settings_data):
        """重新加载页面以应用最新设置"""
        try:
            # 这里可以添加具体的重新加载逻辑
            print("欢迎页面：已重新加载以应用最新设置")
        except Exception as e:
            print(f"欢迎页面重新加载失败: {e}")
    
    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置变化"""
        print(f"欢迎页面：设置已更新 - {page_name} - {settings_data}")
        if page_name == "custom_page":
            self._reload_page(settings_data)