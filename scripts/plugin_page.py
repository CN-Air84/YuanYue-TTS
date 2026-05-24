"""
Plugin Management Page

This module provides the PluginPage class that implements the plugin management
interface using a tab-based architecture. It allows users to view, install,
uninstall, enable, and disable plugins.
"""

import os
import zipfile
import shutil
from pathlib import Path
from typing import Optional

try:
    from PyQt5.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, 
                                QHBoxLayout, QListWidget, QPushButton,
                                QLabel, QTextEdit, QSplitter, QListWidgetItem,
                                QFrame, QMessageBox, QFileDialog, QScrollArea,
                                QGridLayout)
    from PyQt5.QtCore import Qt, pyqtSignal, QSize
    from PyQt5.QtGui import QFont
except ImportError:
    # Fallback for development/testing without PyQt5
    class QWidget:
        def __init__(self, parent=None):
            pass
    
    class QTabWidget(QWidget):
        pass
    
    class QVBoxLayout:
        def __init__(self):
            pass
    
    class QHBoxLayout:
        pass
    
    class QListWidget(QWidget):
        pass
    
    class QPushButton(QWidget):
        pass
    
    class QLabel(QWidget):
        pass
    
    class QTextEdit(QWidget):
        pass
    
    class QSplitter(QWidget):
        pass
    
    class QListWidgetItem:
        pass
    
    class QFrame(QWidget):
        pass
    
    class QMessageBox:
        @staticmethod
        def information(*args, **kwargs):
            pass
        @staticmethod
        def warning(*args, **kwargs):
            pass
        @staticmethod
        def question(*args, **kwargs):
            return 0
        Yes = 1
        No = 0
    
    class QFileDialog:
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return ("", "")
    
    class QScrollArea(QWidget):
        pass
    
    class QGridLayout:
        pass
    
    class Qt:
        Horizontal = 1
        Vertical = 2
        UserRole = 256
    
    class pyqtSignal:
        def __init__(self, *args):
            pass
    
    class QSize:
        def __init__(self, w, h):
            pass
    
    class QFont:
        pass

from plugin_instance import PluginStatus
from resource_urls import get_resource_url


class PluginPage(QWidget):
    """
    Plugin management interface with tab-based architecture
    
    Provides a user interface for managing plugins including viewing
    installed plugins, installing new plugins, and configuring plugin settings.
    
    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    
    # Signals
    plugin_enabled = pyqtSignal(str)    # plugin_name
    plugin_disabled = pyqtSignal(str)   # plugin_name
    plugin_installed = pyqtSignal(str)  # plugin_path
    plugin_uninstalled = pyqtSignal(str) # plugin_name
    
    def __init__(self, parent=None):
        """
        Initialize the plugin management page
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.plugin_manager = None  # Set by main window
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface with tab architecture (需求 6.1, 6.2)"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #D0D0D0;
                border-radius: 5px;
                background-color: #FFFFFF;
            }
            QTabBar::tab {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border-bottom: 1px solid #FFFFFF;
            }
            QTabBar::tab:hover {
                background-color: #E0E0E0;
            }
        """)
        
        # Create tabs (需求 6.2)
        self.installed_tab = InstalledPluginsTab(self)
        self.tab_widget.addTab(self.installed_tab, "已安装插件")
        
        self.market_tab = PluginMarketTab(self)
        self.tab_widget.addTab(self.market_tab, "插件市场")
        
        self.settings_tab = PluginSettingsTab(self)
        self.tab_widget.addTab(self.settings_tab, "插件设置")
        
        layout.addWidget(self.tab_widget)
        
    def set_plugin_manager(self, plugin_manager):
        """
        Set the plugin manager reference
        
        Args:
            plugin_manager: PluginManager instance
        """
        self.plugin_manager = plugin_manager
        self.installed_tab.set_plugin_manager(plugin_manager)
        self.settings_tab.set_plugin_manager(plugin_manager)
        
        # Refresh plugin list after setting manager
        self.refresh_plugin_list()
        
    def refresh_plugin_list(self):
        """Refresh the list of installed plugins"""
        if self.plugin_manager:
            self.installed_tab.refresh_plugin_list()
        
    def on_plugin_selected(self, plugin_name: str):
        """
        Handle plugin selection in the list
        
        Args:
            plugin_name: Name of the selected plugin
        """
        self.installed_tab.on_plugin_selected(plugin_name)
        
    def on_enable_plugin(self):
        """Handle enable plugin button click"""
        self.installed_tab.on_enable_plugin()
        
    def on_disable_plugin(self):
        """Handle disable plugin button click"""
        self.installed_tab.on_disable_plugin()
        
    def on_uninstall_plugin(self):
        """Handle uninstall plugin button click"""
        self.installed_tab.on_uninstall_plugin()
        
    def on_install_plugin(self):
        """Handle install plugin button click"""
        self.installed_tab.on_install_plugin()
        
    def on_check_updates(self):
        """Handle check updates button click"""
        self.installed_tab.on_check_updates()


class StyledContainer(QFrame):
    """Styled container with rounded corners and border"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            StyledContainer {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 5px;
            }
        """)


class InstalledPluginsTab(QWidget):
    """
    Tab for managing installed plugins
    
    Displays list of installed plugins with name, version, author, status.
    Provides plugin details view and management controls.
    
    Requirements: 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 6.14
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_manager = None
        self.selected_plugin_name = None
        self._init_ui()
        
    def _init_ui(self):
        """Initialize UI with plugin list and details view (需求 6.3, 6.4)"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Left panel: Plugin list
        left_panel = StyledContainer()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title and install button
        title_layout = QHBoxLayout()
        title_label = QLabel("已安装插件")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # Install plugin button (需求 6.11, 6.12, 6.13)
        self.install_btn = QPushButton("安装插件")
        self.install_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        self.install_btn.clicked.connect(self.on_install_plugin)
        title_layout.addWidget(self.install_btn)
        
        left_layout.addLayout(title_layout)
        
        # Plugin list widget (需求 6.3)
        self.plugin_list = QListWidget()
        self.plugin_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                background-color: #FAFAFA;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #E0E0E0;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
                color: black;
            }
            QListWidget::item:hover {
                background-color: #F5F5F5;
            }
        """)
        self.plugin_list.itemClicked.connect(self._on_plugin_item_clicked)
        left_layout.addWidget(self.plugin_list)
        
        # Check updates button (需求 10.1, 10.2)
        self.check_updates_btn = QPushButton("检查更新")
        self.check_updates_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
            }
        """)
        self.check_updates_btn.clicked.connect(self.on_check_updates)
        left_layout.addWidget(self.check_updates_btn)
        
        layout.addWidget(left_panel, 1)
        
        # Right panel: Plugin details and controls
        right_panel = StyledContainer()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        # Plugin details (需求 6.4)
        details_label = QLabel("插件详情")
        details_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(details_label)
        
        # Scrollable details area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                background-color: #FAFAFA;
            }
        """)
        
        details_widget = QWidget()
        self.details_layout = QVBoxLayout(details_widget)
        self.details_layout.setAlignment(Qt.AlignTop)
        
        # Plugin info labels
        self.name_label = QLabel("名称: -")
        self.version_label = QLabel("版本: -")
        self.author_label = QLabel("作者: -")
        self.status_label = QLabel("状态: -")
        self.description_label = QLabel("描述: -")
        self.description_label.setWordWrap(True)
        self.update_date_label = QLabel("更新日期: -")
        self.github_label = QLabel("GitHub: -")
        self.github_label.setWordWrap(True)
        
        for label in [self.name_label, self.version_label, self.author_label,
                     self.status_label, self.description_label, 
                     self.update_date_label, self.github_label]:
            label.setStyleSheet("padding: 4px;")
            self.details_layout.addWidget(label)
        
        scroll_area.setWidget(details_widget)
        right_layout.addWidget(scroll_area)
        
        # Control buttons (需求 6.5, 6.6, 6.7, 6.8, 6.9, 6.10)
        button_layout = QHBoxLayout()
        
        self.enable_btn = QPushButton("启用")
        self.enable_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.enable_btn.clicked.connect(self.on_enable_plugin)
        self.enable_btn.setEnabled(False)
        
        self.disable_btn = QPushButton("禁用")
        self.disable_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E68900;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.disable_btn.clicked.connect(self.on_disable_plugin)
        self.disable_btn.setEnabled(False)
        
        self.uninstall_btn = QPushButton("卸载")
        self.uninstall_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.uninstall_btn.clicked.connect(self.on_uninstall_plugin)
        self.uninstall_btn.setEnabled(False)
        
        button_layout.addWidget(self.enable_btn)
        button_layout.addWidget(self.disable_btn)
        button_layout.addWidget(self.uninstall_btn)
        button_layout.addStretch()
        
        right_layout.addLayout(button_layout)
        
        layout.addWidget(right_panel, 2)
        
    def set_plugin_manager(self, plugin_manager):
        """Set plugin manager reference"""
        self.plugin_manager = plugin_manager
        self.refresh_plugin_list()
        
    def refresh_plugin_list(self):
        """Refresh the plugin list display (需求 6.3)"""
        if not self.plugin_manager:
            return
        
        self.plugin_list.clear()
        
        # Get all plugins from plugin manager
        for plugin_name, plugin_instance in self.plugin_manager.plugins.items():
            metadata = plugin_instance.metadata
            status = plugin_instance.status
            
            # Create list item with plugin info
            item_text = f"{metadata.name} v{metadata.version}\n"
            item_text += f"作者: {metadata.author.github or metadata.author.bilibili}\n"
            item_text += f"状态: {self._get_status_text(status)}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, plugin_name)
            item.setSizeHint(QSize(0, 70))
            
            self.plugin_list.addItem(item)
        
        # Show message if no plugins
        if self.plugin_list.count() == 0:
            item = QListWidgetItem("暂无已安装插件")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.plugin_list.addItem(item)
    
    def _get_status_text(self, status: PluginStatus) -> str:
        """Get localized status text"""
        status_map = {
            PluginStatus.NOT_LOADED: "未加载",
            PluginStatus.LOADED: "已加载",
            PluginStatus.ENABLED: "已启用",
            PluginStatus.DISABLED: "已禁用",
            PluginStatus.ERROR: "错误"
        }
        return status_map.get(status, "未知")
    
    def _on_plugin_item_clicked(self, item):
        """Handle plugin list item click"""
        plugin_name = item.data(Qt.UserRole)
        if plugin_name:
            self.on_plugin_selected(plugin_name)
    
    def on_plugin_selected(self, plugin_name: str):
        """Display plugin details when selected (需求 6.4)"""
        if not self.plugin_manager or plugin_name not in self.plugin_manager.plugins:
            return
        
        self.selected_plugin_name = plugin_name
        plugin_instance = self.plugin_manager.plugins[plugin_name]
        metadata = plugin_instance.metadata
        status = plugin_instance.status
        
        # Update details labels
        self.name_label.setText(f"名称: {metadata.name}")
        self.version_label.setText(f"版本: {metadata.version}")
        
        author_text = ""
        if metadata.author.github:
            author_text += f"GitHub: {metadata.author.github}"
        if metadata.author.bilibili:
            if author_text:
                author_text += " | "
            author_text += f"Bilibili: {metadata.author.bilibili}"
        self.author_label.setText(f"作者: {author_text}")
        
        self.status_label.setText(f"状态: {self._get_status_text(status)}")
        self.description_label.setText(f"描述: {metadata.description or '无'}")
        self.update_date_label.setText(f"更新日期: {metadata.update_date or '未知'}")
        self.github_label.setText(f"GitHub仓库: {metadata.github_repo or '无'}")
        
        # Update button states (需求 6.5, 6.6, 6.7)
        self.enable_btn.setEnabled(status.can_enable())
        self.disable_btn.setEnabled(status.can_disable())
        self.uninstall_btn.setEnabled(True)
    
    def on_enable_plugin(self):
        """Handle enable plugin button click (需求 6.5, 6.6)"""
        if not self.selected_plugin_name or not self.plugin_manager:
            return
        
        success = self.plugin_manager.enable_plugin(self.selected_plugin_name)
        
        if success:
            QMessageBox.information(self, "成功", f"插件 {self.selected_plugin_name} 已启用")
            self.refresh_plugin_list()
            self.on_plugin_selected(self.selected_plugin_name)
        else:
            QMessageBox.warning(self, "失败", f"无法启用插件 {self.selected_plugin_name}")
    
    def on_disable_plugin(self):
        """Handle disable plugin button click (需求 6.6, 6.7)"""
        if not self.selected_plugin_name or not self.plugin_manager:
            return
        
        success = self.plugin_manager.disable_plugin(self.selected_plugin_name)
        
        if success:
            QMessageBox.information(self, "成功", f"插件 {self.selected_plugin_name} 已禁用")
            self.refresh_plugin_list()
            self.on_plugin_selected(self.selected_plugin_name)
        else:
            QMessageBox.warning(self, "失败", f"无法禁用插件 {self.selected_plugin_name}")
    
    def on_uninstall_plugin(self):
        """Handle uninstall plugin button click (需求 6.8, 6.9, 6.10)"""
        if not self.selected_plugin_name or not self.plugin_manager:
            return
        
        # Show confirmation dialog (需求 6.9)
        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"确定要卸载插件 {self.selected_plugin_name} 吗？\n\n"
            "这将删除插件的所有文件，但保留配置数据。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Unload plugin first
        success = self.plugin_manager.unload_plugin(self.selected_plugin_name)
        
        if success:
            # Delete plugin directory (需求 6.10)
            plugin_dir = self.plugin_manager.plugin_directory / self.selected_plugin_name
            try:
                if plugin_dir.exists():
                    shutil.rmtree(plugin_dir)
                
                QMessageBox.information(self, "成功", f"插件 {self.selected_plugin_name} 已卸载")
                self.selected_plugin_name = None
                self.refresh_plugin_list()
                self._clear_details()
            except Exception as e:
                QMessageBox.warning(self, "失败", f"无法删除插件文件: {e}")
        else:
            QMessageBox.warning(self, "失败", f"无法卸载插件 {self.selected_plugin_name}")
    
    def on_install_plugin(self):
        """Handle install plugin button click (需求 6.11, 6.12, 6.13)"""
        if not self.plugin_manager:
            return
        
        # Open file dialog to select plugin ZIP file (需求 6.12)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择插件包",
            "",
            "ZIP Files (*.zip)"
        )
        
        if not file_path:
            return
        
        try:
            # Extract ZIP file to plugins directory (需求 6.13)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Get plugin name from ZIP (should be the root folder name)
                namelist = zip_ref.namelist()
                if not namelist:
                    raise ValueError("插件包为空")
                
                # Extract to plugins directory
                extract_path = self.plugin_manager.plugin_directory
                zip_ref.extractall(extract_path)
                
                # Find the extracted plugin directory
                plugin_name = namelist[0].split('/')[0]
                plugin_path = extract_path / plugin_name
                
                if not plugin_path.exists():
                    raise ValueError("无法找到解压后的插件目录")
                
                # Load the plugin
                success = self.plugin_manager.load_plugin(plugin_name)
                
                if success:
                    QMessageBox.information(self, "成功", f"插件 {plugin_name} 已安装")
                    self.refresh_plugin_list()
                else:
                    QMessageBox.warning(self, "失败", f"插件安装失败，请查看日志")
                    # Clean up failed installation
                    if plugin_path.exists():
                        shutil.rmtree(plugin_path)
        
        except Exception as e:
            QMessageBox.warning(self, "错误", f"安装插件时出错: {e}")
    
    def on_check_updates(self):
        """
        Handle check updates button click (需求 10.1, 10.2, 10.3, 10.4, 10.5)
        
        Checks for updates for all installed plugins that have a github_repo field.
        """
        if not self.plugin_manager:
            return
        
        # Disable button during check
        self.check_updates_btn.setEnabled(False)
        self.check_updates_btn.setText("检查中...")
        
        try:
            import requests
            import re
            from packaging import version as pkg_version
            
            updates_available = []
            errors = []
            
            # Check each plugin for updates
            for plugin_name, plugin_instance in self.plugin_manager.plugins.items():
                metadata = plugin_instance.metadata
                
                # Skip plugins without github_repo (需求 10.3)
                if not metadata.github_repo:
                    continue
                
                try:
                    # Parse GitHub repo URL (插件系统保持 GitHub)
                    # Expected format: https://github.com/owner/repo
                    match = re.match(r'https://github\.com/([^/]+)/([^/]+)', metadata.github_repo)
                    if not match:
                        errors.append(f"{plugin_name}: 无效的GitHub仓库URL")
                        continue
                    
                    owner, repo = match.groups()
                    
                    # Get latest release from GitHub API (保持 GitHub，不迁移)
                    api_url = get_resource_url('api_releases', owner=owner, repo=repo)
                    response = requests.get(api_url, timeout=10)
                    
                    if response.status_code == 404:
                        # No releases found
                        continue
                    elif response.status_code != 200:
                        errors.append(f"{plugin_name}: GitHub API请求失败 ({response.status_code})")
                        continue
                    
                    release_data = response.json()
                    latest_version = release_data.get('tag_name', '').lstrip('v')
                    
                    if not latest_version:
                        continue
                    
                    # Compare versions (需求 10.4)
                    try:
                        current_ver = pkg_version.parse(metadata.version)
                        latest_ver = pkg_version.parse(latest_version)
                        
                        if latest_ver > current_ver:
                            # Update available (需求 10.5)
                            download_url = None
                            for asset in release_data.get('assets', []):
                                if asset.get('name', '').endswith('.zip'):
                                    download_url = asset.get('browser_download_url')
                                    break
                            
                            updates_available.append({
                                'plugin_name': plugin_name,
                                'current_version': metadata.version,
                                'latest_version': latest_version,
                                'download_url': download_url,
                                'release_notes': release_data.get('body', '')
                            })
                    except Exception as e:
                        errors.append(f"{plugin_name}: 版本比较失败 ({e})")
                
                except requests.RequestException as e:
                    errors.append(f"{plugin_name}: 网络请求失败 ({e})")
                except Exception as e:
                    errors.append(f"{plugin_name}: 检查更新失败 ({e})")
            
            # Show results
            if updates_available:
                self._show_updates_dialog(updates_available)
            elif errors:
                error_msg = "检查更新时出现以下错误:\n\n" + "\n".join(errors)
                QMessageBox.warning(self, "检查更新", error_msg)
            else:
                QMessageBox.information(self, "检查更新", "所有插件都是最新版本")
        
        except ImportError:
            QMessageBox.warning(
                self,
                "缺少依赖",
                "更新检查功能需要安装 requests 和 packaging 库\n\n"
                "请运行: pip install requests packaging"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检查更新时出错: {e}")
        finally:
            # Re-enable button
            self.check_updates_btn.setEnabled(True)
            self.check_updates_btn.setText("检查更新")
    
    def _show_updates_dialog(self, updates):
        """
        Show dialog with available updates (需求 10.5, 10.6)
        
        Args:
            updates: List of update information dictionaries
        """
        dialog = QMessageBox(self)
        dialog.setWindowTitle("可用更新")
        dialog.setIcon(QMessageBox.Information)
        
        message = f"发现 {len(updates)} 个插件有可用更新:\n\n"
        for update in updates:
            message += f"• {update['plugin_name']}: "
            message += f"{update['current_version']} → {update['latest_version']}\n"
        
        message += "\n是否要更新这些插件?"
        
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setDefaultButton(QMessageBox.Yes)
        
        if dialog.exec_() == QMessageBox.Yes:
            self._install_updates(updates)
    
    def _install_updates(self, updates):
        """
        Install plugin updates (需求 10.6, 10.7, 10.8)
        
        Args:
            updates: List of update information dictionaries
        """
        import requests
        import tempfile
        
        success_count = 0
        failed_updates = []
        
        for update in updates:
            plugin_name = update['plugin_name']
            download_url = update.get('download_url')
            
            if not download_url:
                failed_updates.append(f"{plugin_name}: 无可用下载链接")
                continue
            
            try:
                # Download update (需求 10.7)
                response = requests.get(download_url, timeout=30)
                response.raise_for_status()
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                    temp_file.write(response.content)
                    temp_zip_path = temp_file.name
                
                # Unload current plugin
                if plugin_name in self.plugin_manager.plugins:
                    self.plugin_manager.unload_plugin(plugin_name)
                
                # Delete old plugin directory
                plugin_dir = self.plugin_manager.plugin_directory / plugin_name
                if plugin_dir.exists():
                    shutil.rmtree(plugin_dir)
                
                # Extract new version (需求 10.7)
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    extract_path = self.plugin_manager.plugin_directory
                    zip_ref.extractall(extract_path)
                
                # Clean up temp file
                os.unlink(temp_zip_path)
                
                # Reload plugin (需求 10.8)
                if self.plugin_manager.load_plugin(plugin_name):
                    # Re-enable if it was enabled before
                    if self.plugin_manager._load_plugin_state(plugin_name):
                        self.plugin_manager.enable_plugin(plugin_name)
                    success_count += 1
                else:
                    failed_updates.append(f"{plugin_name}: 重新加载失败")
            
            except Exception as e:
                failed_updates.append(f"{plugin_name}: {e}")
        
        # Show results
        result_msg = f"成功更新 {success_count} 个插件"
        if failed_updates:
            result_msg += f"\n\n失败:\n" + "\n".join(failed_updates)
        
        QMessageBox.information(self, "更新完成", result_msg)
        
        # Refresh plugin list
        self.refresh_plugin_list()
    
    def _clear_details(self):
        """Clear plugin details display"""
        self.name_label.setText("名称: -")
        self.version_label.setText("版本: -")
        self.author_label.setText("作者: -")
        self.status_label.setText("状态: -")
        self.description_label.setText("描述: -")
        self.update_date_label.setText("更新日期: -")
        self.github_label.setText("GitHub: -")
        
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)


class PluginMarketTab(QWidget):
    """
    Tab for plugin market (reserved for future implementation)
    
    Requirements: 6.2, 6.14
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI with placeholder message"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        container = StyledContainer()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        
        # Placeholder message
        message = QLabel(
            "插件市场功能预留\n\n"
            "未来版本将支持：\n"
            "• 在线浏览插件\n"
            "• 一键安装插件\n"
            "• 插件评分和评论\n"
            "• 插件推荐"
        )
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet("font-size: 14px; color: #666666;")
        container_layout.addWidget(message)
        
        layout.addWidget(container)


class PluginSettingsTab(QWidget):
    """
    Tab for plugin settings (optional)
    
    Displays plugin-specific configuration options.
    
    Requirements: 6.2
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_manager = None
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI with settings display"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_label = QLabel("插件设置")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # Settings container
        self.settings_container = StyledContainer()
        self.settings_layout = QVBoxLayout(self.settings_container)
        self.settings_layout.setContentsMargins(10, 10, 10, 10)
        
        # Placeholder message
        self.placeholder_label = QLabel(
            "选择一个插件以查看其设置选项\n\n"
            "插件可以在此处提供自定义配置界面"
        )
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #666666;")
        self.settings_layout.addWidget(self.placeholder_label)
        
        layout.addWidget(self.settings_container)
    
    def set_plugin_manager(self, plugin_manager):
        """Set plugin manager reference"""
        self.plugin_manager = plugin_manager
    
    def show_plugin_settings(self, plugin_name: str):
        """
        Display settings for a specific plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        # Clear existing settings
        while self.settings_layout.count():
            item = self.settings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.plugin_manager or plugin_name not in self.plugin_manager.plugins:
            self.settings_layout.addWidget(self.placeholder_label)
            return
        
        # Get plugin configuration
        plugin_instance = self.plugin_manager.plugins[plugin_name]
        
        # Display plugin name
        name_label = QLabel(f"插件: {plugin_instance.metadata.name}")
        name_label.setStyleSheet("font-weight: bold;")
        self.settings_layout.addWidget(name_label)
        
        # TODO: Add plugin-specific settings UI
        # This would require plugins to provide a settings widget or configuration schema
        
        info_label = QLabel("此插件暂无可配置选项")
        info_label.setStyleSheet("color: #666666;")
        self.settings_layout.addWidget(info_label)
        
        self.settings_layout.addStretch()