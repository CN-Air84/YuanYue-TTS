# coding=utf-8
"""
缓存清理对话框模块
提供选择性清除应用缓存的功能
"""
import os
import shutil
from pathlib import Path
from typing import Iterable
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QCheckBox, 
    QTableWidgetItem, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from debug_logger import debug_logger, LogLevel
from theme_assets import InvalidManagedAssetPath, ThemeAssetStore
from theme_manager import ThemeRepository

try:
    from misc_func import SettingsManager, get_app_base_path
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    def get_app_base_path():
        import sys
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ThemeAssetCleanupUnavailable(RuntimeError):
    """Raised when authoritative theme references cannot be read safely."""


def _load_theme_asset_references(theme_root=None):
    root = (
        Path(theme_root)
        if theme_root is not None
        else Path(get_app_base_path()) / "data" / "themes"
    )
    repository = ThemeRepository(root)
    if repository.read_only:
        raise ThemeAssetCleanupUnavailable(
            repository.read_only_reason or "theme repository is read-only"
        )
    store = ThemeAssetStore(root)
    references = store.referenced_paths(repository.list_themes())
    return store, references


def _safe_managed_asset_map(store: ThemeAssetStore):
    assets = {}
    for listed_path in store.list_assets():
        relative = f"assets/{listed_path.name}"
        try:
            resolved = store.resolve_managed_path(relative)
        except InvalidManagedAssetPath:
            continue
        if resolved != listed_path.resolve():
            continue
        assets[relative] = resolved
    return assets


def find_unreferenced_theme_assets(theme_root=None) -> tuple[Path, ...]:
    """List only unreferenced canonical UUID PNG files in the assets root."""
    store, references = _load_theme_asset_references(theme_root)
    assets = _safe_managed_asset_map(store)
    return tuple(
        assets[relative]
        for relative in sorted(assets)
        if relative not in references
    )


def delete_unreferenced_theme_assets(
    theme_root=None,
    candidates: Iterable[str] | None = None,
) -> tuple[Path, ...]:
    """Re-read authoritative references, then delete still-orphaned assets."""
    store, references = _load_theme_asset_references(theme_root)
    assets = _safe_managed_asset_map(store)
    if candidates is None:
        selected = set(assets)
    else:
        selected = set()
        for candidate in candidates:
            resolved = store.resolve_managed_path(str(candidate))
            relative = f"assets/{resolved.name}"
            if relative in assets:
                selected.add(relative)

    deleted = []
    for relative in sorted(selected):
        if relative in references:
            continue
        path = assets[relative]
        if store.delete_asset(relative, references):
            deleted.append(path)
    return tuple(deleted)


class CacheCleanerDialog(QDialog):
    """缓存清理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, "初始化缓存清理对话框", fold_code="MP_CC_INIT")
        self.parent_window = parent
        self.setWindowTitle("清除缓存")
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

        # 定义可清除的缓存项
        self.cache_items = self._get_cache_items()
        
        self._init_ui()
        self._update_fonts()
        self._update_cache_sizes()
        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, f"缓存清理对话框初始化完成, 缓存项数量: {len(self.cache_items)}", fold_code="MP_CC_INIT")

    def _get_cache_items(self):
        """获取可清除的缓存项列表"""
        base_path = get_app_base_path()
        
        cache_items = [
            {
                'name': '生成的音频',
                'desc': '清除所有生成的音频文件',
                'path': os.path.join(base_path, 'cache', 'audio'),
                'type': 'directory'
            },
            {
                'name': '运行日志',
                'desc': '清除应用运行日志文件',
                'path': os.path.join(base_path, 'cache', 'log'),
                'type': 'directory'
            },
            {
                'name': '介绍视频',
                'desc': '清除缓存的介绍视频',
                'path': os.path.join(base_path, 'cache', 'intro_1.mov'),
                'type': 'file'
            },
            {
                'name': '电子书下载链接',
                'desc': '清除电子书下载链接列表',
                'path': os.path.join(base_path, 'SEI', 'links.txt'),
                'type': 'file'
            },
            {
                'name': '未引用主题图片',
                'desc': '仅清除主题目录中未被任何主题引用的 UUID PNG',
                'path': os.path.join(base_path, 'data', 'themes', 'assets'),
                'theme_root': os.path.join(base_path, 'data', 'themes'),
                'type': 'theme_orphans'
            }
        ]
        
        return cache_items

    def _init_ui(self):
        """初始化UI"""
        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, "正在构建缓存清理UI", fold_code="MP_CC_INIT")
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

        # 创建表格
        row_count = len(self.cache_items)
        self.table_widget = QTableWidget(row_count, 4)
        self.table_widget.setHorizontalHeaderLabels(["选择", "缓存项", "说明", "大小"])
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setShowGrid(True)
        self.table_widget.setColumnWidth(0, 60)
        self.table_widget.setColumnWidth(1, 150)
        self.table_widget.setColumnWidth(2, 250)
        self.table_widget.setColumnWidth(3, 100)

        self.checkboxes = []
        for row, cache_item in enumerate(self.cache_items):
            # 复选框
            checkbox = QCheckBox()
            checkbox.setStyleSheet("QCheckBox { margin-left: 20px; }")
            self.checkboxes.append(checkbox)
            self.table_widget.setCellWidget(row, 0, checkbox)

            # 缓存项名称
            name_item = QTableWidgetItem(cache_item.get('name', ''))
            name_item.setFlags(Qt.ItemIsEnabled)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 1, name_item)

            # 说明
            desc_item = QTableWidgetItem(cache_item.get('desc', ''))
            desc_item.setFlags(Qt.ItemIsEnabled)
            desc_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 2, desc_item)

            # 大小（稍后更新）
            size_item = QTableWidgetItem("计算中...")
            size_item.setFlags(Qt.ItemIsEnabled)
            size_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row, 3, size_item)

        layout.addWidget(self.table_widget)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 全选按钮
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self._on_select_all)
        button_layout.addWidget(self.select_all_button)
        
        # 清除按钮
        self.clean_button = QPushButton("清除选中项")
        self.clean_button.clicked.connect(self._on_clean)
        button_layout.addWidget(self.clean_button)
        
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, f"缓存清理窗口大小调整: {self.width()}x{self.height()}", fold_code="MP_CC_INIT")
        self._update_fonts()
        super().resizeEvent(event)

    def _calculate_font_sizes(self):
        """计算字体大小"""
        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, "正在计算缓存清理窗口字体大小适配", fold_code="MP_CC_INIT")
        current_width = self.width()
        current_height = self.height()
        width_ratio = current_width / self.default_width
        height_ratio = current_height / self.default_height
        ratio = (width_ratio + height_ratio) / 2
        base_font_size = (self.min_font_size +
                         (self.max_font_size - self.min_font_size) * (ratio - 1))
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        
        # 调整为原先的75%
        base_font_size = base_font_size * 0.75
        
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
                for col in range(1, 4):
                    item = self.table_widget.item(row, col)
                    if item:
                        item.setFont(QFont(self.global_font, int(base_font_size * 0.7)))

            self.clean_button.setFont(QFont(self.global_font, int(base_font_size * 0.8)))
            self.select_all_button.setFont(QFont(self.global_font, int(base_font_size * 0.8)))

        except Exception as e:
            debug_logger.output("mp_cache_cleaner.py", LogLevel.ERROR, f"更新缓存清理对话框字体时出错: {e}", fold_code="MP_CC_INIT")

    def _update_cache_sizes(self):
        """更新缓存大小显示"""
        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, "正在计算缓存大小", fold_code="MP_CC_SIZE")
        for row, cache_item in enumerate(self.cache_items):
            path = cache_item['path']
            cache_type = cache_item['type']
            
            try:
                if cache_type == 'directory':
                    size = self._get_directory_size(path)
                elif cache_type == 'file':
                    size = self._get_file_size(path)
                elif cache_type == 'theme_orphans':
                    size = sum(
                        asset.stat().st_size
                        for asset in find_unreferenced_theme_assets(
                            cache_item.get('theme_root')
                        )
                    )
                else:
                    size = 0
                
                size_text = self._format_size(size)
                size_item = self.table_widget.item(row, 3)
                if size_item:
                    size_item.setText(size_text)
                    
            except Exception as e:
                debug_logger.output("mp_cache_cleaner.py", LogLevel.WARNING, f"计算缓存大小失败 {path}: {str(e)}", fold_code="MP_CC_SIZE")
                size_item = self.table_widget.item(row, 3)
                if size_item:
                    size_item.setText("不存在")

    def _get_directory_size(self, path):
        """获取目录大小（字节）"""
        if not os.path.exists(path):
            return 0
        
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            debug_logger.output("mp_cache_cleaner.py", LogLevel.WARNING, f"计算目录大小失败 {path}: {str(e)}", fold_code="MP_CC_SIZE")
        
        return total_size

    def _get_file_size(self, path):
        """获取文件大小（字节）"""
        if not os.path.exists(path):
            return 0
        
        try:
            return os.path.getsize(path)
        except Exception as e:
            debug_logger.output("mp_cache_cleaner.py", LogLevel.WARNING, f"计算文件大小失败 {path}: {str(e)}", fold_code="MP_CC_SIZE")
            return 0

    def _format_size(self, size_bytes):
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"

    def _on_select_all(self):
        """全选/取消全选"""
        # 检查是否已经全选
        all_checked = all(checkbox.isChecked() for checkbox in self.checkboxes)
        
        # 如果全选则取消全选，否则全选
        new_state = not all_checked
        
        for checkbox in self.checkboxes:
            checkbox.setChecked(new_state)
        
        # 更新按钮文本
        self.select_all_button.setText("取消全选" if new_state else "全选")

    def _on_clean(self):
        """清除选中的缓存项"""
        selected_items = []
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                selected_items.append(self.cache_items[i])

        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, f"开始清除选中的缓存, 选中数量: {len(selected_items)}", fold_code="MP_CC_CLEAN")
        
        if not selected_items:
            debug_logger.output("mp_cache_cleaner.py", LogLevel.WARNING, "未选中任何缓存项", fold_code="MP_CC_CLEAN")
            QMessageBox.information(self, "提示", "请先选择要清除的缓存项")
            return

        # 确认对话框
        confirmation_text = (
            f"确定要清除选中的 {len(selected_items)} 项缓存吗？\n此操作不可恢复！"
        )
        if any(item.get('type') == 'theme_orphans' for item in selected_items):
            confirmation_text += (
                "\n\n未引用主题图片将在删除前重新读取最新主题状态；"
                "仍被引用的图片不会删除。"
            )
        reply = QMessageBox.question(
            self, 
            "确认清除", 
            confirmation_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return

        # 执行清除操作
        success_count = 0
        fail_count = 0
        
        for item in selected_items:
            try:
                path = item['path']
                cache_type = item['type']
                
                debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, f"清除缓存: {item['name']} ({path})", fold_code="MP_CC_CLEAN")
                
                if cache_type == 'directory':
                    if os.path.exists(path):
                        shutil.rmtree(path)
                        # 重新创建空目录
                        os.makedirs(path, exist_ok=True)
                        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, f"成功清除目录: {path}", fold_code="MP_CC_CLEAN")
                        success_count += 1
                    else:
                        debug_logger.output("mp_cache_cleaner.py", LogLevel.WARNING, f"目录不存在: {path}", fold_code="MP_CC_CLEAN")
                        success_count += 1  # 不存在也算成功
                        
                elif cache_type == 'file':
                    if os.path.exists(path):
                        os.remove(path)
                        debug_logger.output("mp_cache_cleaner.py", LogLevel.INFO, f"成功删除文件: {path}", fold_code="MP_CC_CLEAN")
                        success_count += 1
                    else:
                        debug_logger.output("mp_cache_cleaner.py", LogLevel.WARNING, f"文件不存在: {path}", fold_code="MP_CC_CLEAN")
                        success_count += 1  # 不存在也算成功

                elif cache_type == 'theme_orphans':
                    deleted = delete_unreferenced_theme_assets(
                        item.get('theme_root')
                    )
                    debug_logger.output(
                        "mp_cache_cleaner.py",
                        LogLevel.INFO,
                        f"成功清除未引用主题图片 {len(deleted)} 个",
                        fold_code="MP_CC_CLEAN",
                    )
                    success_count += 1
                        
            except Exception as e:
                debug_logger.output("mp_cache_cleaner.py", LogLevel.ERROR, f"清除缓存失败 {item['name']}: {str(e)}", fold_code="MP_CC_CLEAN")
                fail_count += 1

        # 更新缓存大小显示
        self._update_cache_sizes()
        
        # 取消所有选中
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)
        self.select_all_button.setText("全选")

        # 显示结果
        if fail_count == 0:
            QMessageBox.information(self, "完成", f"成功清除 {success_count} 项缓存")
        else:
            QMessageBox.warning(self, "完成", f"成功清除 {success_count} 项缓存\n失败 {fail_count} 项")
