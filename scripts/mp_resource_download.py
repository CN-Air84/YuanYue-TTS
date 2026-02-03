# coding=utf-8
import os
import zipfile
import subprocess
import urllib.parse
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QCheckBox, 
    QTableWidgetItem, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

try:
    from misc_func import SettingsManager, get_app_base_path
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    # 如果导入失败，定义一个后备方案
    def get_app_base_path():
        return os.getcwd()

try:
    from multi_thread_downloader import download
except ImportError:
    download = None

class ResourceDownloadDialog(QDialog):
    """资源下载对话框"""

    def __init__(self, parent=None, resource_info=None):
        super().__init__(parent)
        self.parent_window = parent
        self.resource_info = resource_info or []
        self.setWindowTitle("资源下载")
        self.resize(600, 400)

        if SETTINGS_AVAILABLE:
            self.global_font = SettingsManager().get_Custom_value('global_font', '微软雅黑')
            self.min_font_size = int(SettingsManager().get_Custom_value('min_font_size', '22'))
            self.max_font_size = int(SettingsManager().get_Custom_value('max_font_size', '42'))
        else:
            self.global_font = '微软雅黑'
            self.min_font_size = 22
            self.max_font_size = 42

        self.default_width = 1080
        self.default_height = 1080

        self._init_ui()
        self._update_fonts()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("""
            QDialog {
                background-color: #F0F0F0;
            }
            QTableWidget {
                background-color: white;
                border: 2px solid #CCCCCC;
                gridline-color: #DDDDDD;
            }
            QTableWidget QHeaderView::section {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                padding: 4px;
            }
        """)

        row_count = len(self.resource_info)
        self.table_widget = QTableWidget(row_count, 3)
        self.table_widget.setHorizontalHeaderLabels(["选择", "组件名称", "组件简介"])
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setShowGrid(True)
        self.table_widget.setColumnWidth(0, 60)
        self.table_widget.setColumnWidth(1, 150)

        self.checkboxes = []
        for row, resource in enumerate(self.resource_info):
            checkbox = QCheckBox()
            checkbox.setStyleSheet("QCheckBox { margin-left: 20px; }")
            self.checkboxes.append(checkbox)
            self.table_widget.setCellWidget(row, 0, checkbox)

            name_item = QTableWidgetItem(resource.get('name', ''))
            name_item.setFlags(Qt.ItemIsEnabled)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 1, name_item)

            desc_item = QTableWidgetItem(resource.get('desc', ''))
            desc_item.setFlags(Qt.ItemIsEnabled)
            desc_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 2, desc_item)

        layout.addWidget(self.table_widget)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.deploy_button = QPushButton("开始部署")
        self.deploy_button.clicked.connect(self._on_deploy)
        button_layout.addWidget(self.deploy_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)

    def _calculate_font_sizes(self):
        """计算字体大小"""
        current_width = self.width()
        current_height = self.height()
        width_ratio = current_width / self.default_width
        height_ratio = current_height / self.default_height
        ratio = (width_ratio + height_ratio) / 2
        base_font_size = (self.min_font_size +
                         (self.max_font_size - self.min_font_size) * (ratio - 1))
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        base_font_size = int(base_font_size)
        header_font_size = int(base_font_size * 0.8 * (2/3))
        return base_font_size, header_font_size

    def _update_fonts(self):
        """更新字体"""
        try:
            base_font_size, header_font_size = self._calculate_font_sizes()

            header_font = QFont(self.global_font, header_font_size)
            header_font.setBold(True)

            self.table_widget.horizontalHeader().setFont(header_font)

            for row in range(self.table_widget.rowCount()):
                for col in range(1, 3):
                    item = self.table_widget.item(row, col)
                    if item:
                        item.setFont(QFont(self.global_font, base_font_size * 0.7))

            self.deploy_button.setFont(QFont(self.global_font, base_font_size * 0.8))

        except Exception:
            pass

    def _extract_7z(self, file_path: str, target_path: str) -> bool:
        """
        使用 7z 命令行工具解压文件

        Args:
            file_path: 压缩包路径
            target_path: 解压目标路径

        Returns:
            bool: 解压是否成功
        """
        try:
            # 使用 subprocess 调用 7z 命令行工具
            # x: 带路径解压
            # -o: 指定输出目录
            # -y: 自动回答 yes（覆盖）
            result = subprocess.run(
                ['7z', 'x', file_path, f'-o{target_path}', '-y'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return True
            
            print(f"[DEBUG] 7z extraction failed with return code {result.returncode}: {result.stderr}")
            return False

        except FileNotFoundError:
            print("[DEBUG] 7z command not found. Please install 7-Zip and add it to PATH.")
            return False
        except Exception as e:
            print(f"[DEBUG] 7z extraction error: {str(e)}")
            return False

    def _safe_remove(self, file_path: str) -> None:
        """
        安全地删除文件，忽略可能的错误

        Args:
            file_path: 要删除的文件路径
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[DEBUG] Successfully removed: {file_path}")
        except Exception as e:
            print(f"[DEBUG] Failed to remove {file_path}: {str(e)}")

    def _on_deploy(self):
        """
        开始部署按钮点击事件
        
        处理流程：
        1. 获取选中的资源
        2. 获取下载 URL 并加速（如果可用）
        3. 调用多线程下载器下载资源
        4. 根据资源定义的任务类型进行解压
        5. 解压成功后自动删除原始压缩包
        """
        selected_resources = []
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                selected_resources.append(self.resource_info[i])

        if not selected_resources:
            QMessageBox.information(self, "提示", "请先选择要部署的资源")
            return

        # 使用 get_app_base_path 获取程序实际所在目录，避免 PyInstaller 打包后的路径偏移问题
        save_dir = get_app_base_path()

        for resource in selected_resources:
            try:
                if download is None:
                    raise ImportError("multi_thread_downloader 模块未找到，请确保已安装依赖。")

                # 处理 GitHub 加速 URL
                accelerated_url = self.parent_window._get_github_accelerated_url(resource['url']) \
                    if hasattr(self.parent_window, '_get_github_accelerated_url') \
                    else resource['url']

                # 解析文件名
                url_path = urllib.parse.urlparse(accelerated_url).path
                filename = os.path.basename(url_path)

                # 获取下载线程数设置
                thread_num = 5
                if SETTINGS_AVAILABLE:
                    thread_num = SettingsManager().get_download_thread_num()

                # 执行下载任务
                download_result = download(
                    url=accelerated_url,
                    save_dir=save_dir,
                    filename=filename,
                    thread_num=thread_num,
                    verify_ssl=False
                )

                if not download_result:
                    QMessageBox.critical(self, "错误", f"下载 {resource['name']} 失败")
                    continue

                file_path = os.path.join(save_dir, filename)

                if not os.path.exists(file_path):
                    QMessageBox.critical(self, "错误", f"文件未找到: {file_path}")
                    continue

                # 处理后续任务（如解压）
                if resource.get('task'):
                    task = resource['task']
                    if task['type'] == 'UnzipTo':
                        target_path = task['path']

                        # 处理相对路径
                        if not os.path.isabs(target_path):
                            target_path = os.path.join(save_dir, target_path)

                        if not os.path.exists(target_path):
                            os.makedirs(target_path, exist_ok=True)

                        ext = os.path.splitext(filename)[1].lower()
                        extraction_success = False

                        if ext == '.zip':
                            try:
                                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                    zip_ref.extractall(target_path)
                                extraction_success = True
                                QMessageBox.information(self, "提示", f"已成功部署并解压: {resource['name']} -> {target_path}")
                            except zipfile.BadZipFile:
                                QMessageBox.warning(self, "警告", f"{resource['name']} 下载的文件不是有效的 ZIP 格式。")
                        
                        elif ext == '.7z':
                            if self._extract_7z(file_path, target_path):
                                extraction_success = True
                                QMessageBox.information(self, "提示", f"已成功部署并解压: {resource['name']} -> {target_path}")
                            else:
                                QMessageBox.warning(self, "提示", f"已成功下载: {resource['name']}\n但 7z 解压失败。文件位置: {file_path}")
                        
                        else:
                            QMessageBox.information(self, "提示", f"已成功下载: {resource['name']}\n注意: {ext} 格式不支持自动解压，请手动处理。")

                        # 解压成功后删除压缩包
                        if extraction_success:
                            self._safe_remove(file_path)

                    else:
                        QMessageBox.information(self, "提示", f"已成功部署: {resource['name']}")
                else:
                    QMessageBox.information(self, "提示", f"已成功部署: {resource['name']}")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"部署 {resource['name']} 失败: {str(e)}")
