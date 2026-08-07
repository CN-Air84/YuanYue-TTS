import sys
import os
import struct
import mmap
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QLineEdit, QCheckBox, QTableView, QHeaderView, 
    QAbstractItemView, QFileDialog, QColorDialog, QFrame, QMessageBox,
    QDialog, QProgressBar
)
from PyQt5.QtCore import (
    Qt, QTimer, QAbstractTableModel, QModelIndex, QVariant, 
    QSortFilterProxyModel, QThread, pyqtSignal, QMutex, QMutexLocker
)
from PyQt5.QtGui import QColor, QBrush, QDesktopServices, QIcon, QPainter
from PyQt5.QtCore import QUrl

# 共享内存常量
SHM_FILE_NAME = "YuanyueDebugLog.dat"
SHM_SIZE = 1024 * 1024  # 1MB
HEADER_SIZE = 16
MAGIC = b'YLOG'

def get_app_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class LogEntry:
    def __init__(self, timestamp, level, source, message, fold_code=None, remark=None):
        self.timestamp = timestamp
        self.level = level
        self.source = source
        self.message = message
        self.fold_code = fold_code
        self.remark = remark
        self.bg_color = None
        self.original_line = ""

class LogGroup:
    def __init__(self, header_entry):
        self.header = header_entry
        self.children = []
        self.is_expanded = False
        self.count = 1

    def add_child(self, entry):
        self.children.append(entry)
        self.count += 1

class LogTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_entries = []
        self.display_rows = [] 
        self.headers = ["时间", "等级", "来源", "折叠代码", "正文"]
        
        # 过滤器状态
        self.min_level = "INFO"
        self.ignore_fold_code = ""
        self.ignore_source = ""
        self.fold_enabled = False
        self.mark_mode = False
        self.mark_color = QColor(0, 255, 255)
        
        self._mutex = QMutex()

    def rowCount(self, parent=QModelIndex()):
        return len(self.display_rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.display_rows):
            return QVariant()
        
        item = self.display_rows[index.row()]
        # 条目可以是 LogEntry（叶子或子节点）或 LogGroup（分组头）
        
        entry = item.header if isinstance(item, LogGroup) else item
        
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return entry.timestamp
            elif index.column() == 1:
                return entry.level
            elif index.column() == 2:
                return entry.source
            elif index.column() == 3:
                return entry.fold_code or ""
            elif index.column() == 4:
                msg = entry.message
                if isinstance(item, LogGroup) and item.count > 1:
                    status = "[-]" if item.is_expanded else "[+]"
                    msg = f"{status} {msg} ({item.count} 条消息)"
                return msg
        
        elif role == Qt.BackgroundRole:
            if entry.bg_color:
                return QBrush(entry.bg_color)
            
            # 默认等级颜色
            if entry.level == "WARNING":
                return QBrush(QColor(255, 243, 205))  # 浅黄色
            elif entry.level == "ERROR":
                return QBrush(QColor(248, 215, 218))  # 浅红色
            elif entry.level == "CRITICAL":
                return QBrush(QColor(220, 53, 69))    # 红色
            elif entry.level == "DEBUG":
                return QBrush(QColor(240, 240, 240))  # 浅灰色
        
        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return QVariant()

    def add_entries(self, entries):
        if not entries:
            return
        # 简单起见，结构变化大时直接重置；不过滤时可以考虑优化
        # 但由于有过滤和分组，新条目可能合并到现有分组
        # 所以最安全的做法是重新计算
        self.beginResetModel()
        self.raw_entries.extend(entries)
        self._recalculate_internal()
        self.endResetModel()

    def set_filters(self, level, ignore_fold, ignore_source, fold_enabled):
        self.beginResetModel()
        self.min_level = level
        self.ignore_fold_code = ignore_fold
        self.ignore_source = ignore_source
        self.fold_enabled = fold_enabled
        self._recalculate_internal()
        self.endResetModel()

    def _recalculate_internal(self):
        self.display_rows = []
        
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        try:
            min_idx = levels.index(self.min_level)
        except:
            min_idx = 0

        # 1. 过滤
        filtered_entries = []
        for entry in self.raw_entries:
            # 等级过滤
            try:
                curr_idx = levels.index(entry.level)
                if curr_idx < min_idx:
                    continue
            except:
                pass
            
            # 忽略指定的折叠代码
            if self.ignore_fold_code and entry.fold_code == self.ignore_fold_code:
                continue
                
            # 忽略指定来源
            if self.ignore_source and entry.source == self.ignore_source:
                continue
                
            filtered_entries.append(entry)

        # 2. 分组/折叠
        if not self.fold_enabled:
            self.display_rows = filtered_entries
        else:
            groups = []
            current_group = None
            
            for entry in filtered_entries:
                if current_group:
                    if entry.fold_code and entry.fold_code == current_group.header.fold_code:
                        current_group.add_child(entry)
                    else:
                        groups.append(current_group)
                        current_group = LogGroup(entry)
                else:
                    current_group = LogGroup(entry)
            
            if current_group:
                groups.append(current_group)
            
            # 3. 展平用于显示
            for group in groups:
                self.display_rows.append(group)
                if group.is_expanded:
                    self.display_rows.extend(group.children)

    def toggle_group(self, index):
        if not index.isValid():
            return
        
        item = self.display_rows[index.row()]
        if isinstance(item, LogGroup):
            self.beginResetModel()
            item.is_expanded = not item.is_expanded
            self._recalculate_internal()  # 需要重新展平
            self.endResetModel()

    def mark_row(self, index, color):
        if not index.isValid():
            return
        item = self.display_rows[index.row()]
        entry = item.header if isinstance(item, LogGroup) else item
        entry.bg_color = color
        self.dataChanged.emit(index, index, [Qt.BackgroundRole])
        
    def clear(self):
        self.beginResetModel()
        self.raw_entries = []
        self.display_rows = []
        self.endResetModel()

class SHMWorker(QThread):
    new_logs = pyqtSignal(list)
    loading_started = pyqtSignal()
    loading_finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.shm_path = os.path.join(get_app_base_path(), 'cache', SHM_FILE_NAME)
        self.shm_file = None
        self.shm_map = None
        self.read_pos = HEADER_SIZE
        self.batch_size = 1000  # 每次最多读1000条

    def run(self):
        while self.running:
            try:
                if not self.shm_map:
                    if os.path.exists(self.shm_path):
                        try:
                            self.shm_file = open(self.shm_path, 'r+b')
                            self.shm_map = mmap.mmap(self.shm_file.fileno(), SHM_SIZE)
                            self.shm_map.seek(0)
                            magic = self.shm_map.read(4)
                            if magic != MAGIC:
                                self.shm_map.close()
                                self.shm_map = None
                                time.sleep(1)
                                continue
                            self.read_pos = HEADER_SIZE
                        except:
                            time.sleep(1)
                            continue
                    else:
                        time.sleep(1)
                        continue

                if not self.shm_map:
                    time.sleep(0.1)
                    continue

                self.shm_map.seek(4)
                write_pos_bytes = self.shm_map.read(4)
                write_pos = struct.unpack('I', write_pos_bytes)[0]
                
                if self.read_pos == write_pos:
                    time.sleep(0.1)
                    continue
                
                # 检查要读的数据是否过多
                data_to_read = False
                if write_pos > self.read_pos:
                    if write_pos - self.read_pos > 1000:  # 超过1000条就读
                        data_to_read = True
                elif write_pos < self.read_pos:  # 环形缓冲区 wrap 了
                    data_to_read = True
                
                if data_to_read:
                    self.loading_started.emit()
                
                batch = []
                loop_count = 0
                max_loop = 10000  # 安全上限
                
                while self.read_pos != write_pos and loop_count < max_loop:
                    loop_count += 1
                    
                    self.shm_map.seek(self.read_pos)
                    
                    if self.read_pos + 2 > SHM_SIZE:
                        self.read_pos = HEADER_SIZE
                        continue
                        
                    length_bytes = self.shm_map.read(2)
                    length = struct.unpack('H', length_bytes)[0]
                    
                    if length == 0:
                        self.read_pos = HEADER_SIZE
                        continue
                    
                    if self.read_pos + 2 + length > SHM_SIZE:
                        self.read_pos = HEADER_SIZE
                        continue
                        
                    data = self.shm_map.read(length)
                    try:
                        line = data.decode('utf-8')
                        entry = self.parse_log_line(line)
                        if entry:
                            batch.append(entry)
                    except:
                        pass
                    
                    self.read_pos += 2 + length
                    
                    if len(batch) >= self.batch_size:
                        self.new_logs.emit(batch)
                        batch = []
                        # 线程中不允许GUI更新，直接跳过
                        time.sleep(0.01) 
                
                if batch:
                    self.new_logs.emit(batch)
                
                if data_to_read:
                    self.loading_finished.emit()
                
                # 如果是因为超过 max_loop 而跳出的，下次会继续读
                if loop_count < max_loop:
                    time.sleep(0.1)

            except Exception as e:
                time.sleep(1)

    def parse_log_line(self, line):
        try:
            line = line.strip()
            if not line.startswith("["):
                return None
            
            parts = line.split("]", 3)
            if len(parts) < 4:
                return None
            
            timestamp = parts[0][1:]
            level = parts[1][1:]
            source = parts[2][1:]
            content_part = parts[3]
            
            fold_code = None
            remark = None
            message = content_part

            if message.endswith("]"):
                 r_idx = message.rfind("[")
                 if r_idx != -1:
                     possible_fold = message[r_idx+1:-1]
                     fold_code = possible_fold
                     message = message[:r_idx]

            if "%" in message:
                if message.endswith("%") and message.count("%") >= 2:
                    r_start = message.rfind("%", 0, len(message)-1)
                    if r_start != -1:
                        remark = message[r_start+1:-1]
                        message = message[:r_start]
            
            entry = LogEntry(timestamp, level, source, message, fold_code, remark)
            entry.original_line = line
            return entry
        except:
            return None
            
    def stop(self):
        self.running = False
        self.wait()

class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.hide()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "正在加载日志...")

class DebugMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("调试输出监控面板")
        self.resize(1200, 700)
        
        self.model = LogTableModel()
        
        self.setup_ui()
        
        self.mark_color = QColor(0, 255, 255)
        self.update_mark_preview()
        
        self.current_level = "INFO"
        self.update_level_buttons()
        
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.resize(self.size())
        
        self.start_shm_worker()

    def resizeEvent(self, event):
        self.loading_overlay.resize(self.size())
        super().resizeEvent(event)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 样式表
        self.setStyleSheet("""
            QWidget {
                font: 9pt "HarmonyOS Sans SC";
            }
            QPushButton {
                border-radius: 5px;
                border: 1px solid gray;
                padding: 5px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QLineEdit {
                border-radius: 5px;
                border: 1px solid gray;
                padding: 3px;
            }
            QTableView {
                border: 1px solid gray;
                border-radius: 5px;
            }
            QFrame {
                border: none;
            }
        """)

        # 顶部控制区
        top_layout = QHBoxLayout()
        
        # 导入/导出
        io_group = QFrame()
        io_group.setStyleSheet("QFrame { border: 1px solid gray; border-radius: 5px; }")
        io_layout = QHBoxLayout(io_group)
        self.btn_export = QPushButton("导出到......")
        self.btn_import = QPushButton("从......导入")
        io_layout.addWidget(self.btn_export)
        io_layout.addWidget(self.btn_import)
        top_layout.addWidget(io_group)
        
        self.btn_export.clicked.connect(self.export_logs)
        self.btn_import.clicked.connect(self.import_logs)

        # 筛选等级
        level_group = QFrame()
        level_group.setStyleSheet("QFrame { border: 1px solid gray; border-radius: 5px; }")
        level_layout = QHBoxLayout(level_group)
        level_layout.addWidget(QLabel("筛选等级:"))
        
        self.level_buttons = {}
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            btn = QPushButton(level)
            btn.clicked.connect(lambda checked, l=level: self.set_level(l))
            level_layout.addWidget(btn)
            self.level_buttons[level] = btn
            
        top_layout.addWidget(level_group)

        # 标记模式
        mark_group = QFrame()
        mark_group.setStyleSheet("QFrame { border: 1px solid gray; border-radius: 5px; }")
        mark_layout = QHBoxLayout(mark_group)
        self.chk_mark_mode = QCheckBox("标记模式:")
        self.btn_mark_color = QPushButton()
        self.btn_mark_color.setFixedSize(30, 20)
        self.btn_mark_color.clicked.connect(self.choose_color)
        
        mark_layout.addWidget(self.chk_mark_mode)
        mark_layout.addWidget(self.btn_mark_color)
        top_layout.addWidget(mark_group)
        
        main_layout.addLayout(top_layout)

        # 第二行控制区
        filter_layout = QHBoxLayout()
        filter_group = QFrame()
        filter_group.setStyleSheet("QFrame { border: 1px solid gray; border-radius: 5px; }")
        f_layout = QHBoxLayout(filter_group)
        
        self.chk_ignore_fold = QCheckBox("忽略折叠代码为")
        self.edit_ignore_fold = QLineEdit()
        self.edit_ignore_fold.setFixedWidth(150)
        self.edit_ignore_fold.textChanged.connect(self.apply_filters)
        self.chk_ignore_fold.stateChanged.connect(self.apply_filters)
        
        f_layout.addWidget(self.chk_ignore_fold)
        f_layout.addWidget(self.edit_ignore_fold)
        f_layout.addWidget(QLabel("的消息"))
        
        f_layout.addSpacing(20)
        
        self.chk_ignore_source = QCheckBox("忽略来自")
        self.edit_ignore_source = QLineEdit()
        self.edit_ignore_source.setFixedWidth(150)
        self.edit_ignore_source.textChanged.connect(self.apply_filters)
        self.chk_ignore_source.stateChanged.connect(self.apply_filters)

        f_layout.addWidget(self.chk_ignore_source)
        f_layout.addWidget(self.edit_ignore_source)
        f_layout.addWidget(QLabel("的消息"))
        
        f_layout.addSpacing(20)
        
        self.chk_fold_by_code = QCheckBox("按折叠代码折叠")
        self.chk_fold_by_code.stateChanged.connect(self.apply_filters)
        f_layout.addWidget(self.chk_fold_by_code)
        
        filter_layout.addWidget(filter_group)
        main_layout.addLayout(filter_layout)

        # 表格视图
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # 让"正文"列自动拉伸
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.clicked.connect(self.on_table_clicked)
        self.table_view.doubleClicked.connect(self.on_table_double_clicked)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setAlternatingRowColors(True)
        
        main_layout.addWidget(self.table_view)

    def start_shm_worker(self):
        self.shm_worker = SHMWorker()
        self.shm_worker.new_logs.connect(self.on_new_logs)
        self.shm_worker.loading_started.connect(self.show_loading)
        self.shm_worker.loading_finished.connect(self.hide_loading)
        self.shm_worker.start()

    def show_loading(self):
        self.loading_overlay.show()
        QApplication.processEvents()

    def hide_loading(self):
        self.loading_overlay.hide()

    def on_new_logs(self, entries):
        self.model.add_entries(entries)
        if self.table_view.verticalScrollBar().value() == self.table_view.verticalScrollBar().maximum():
             self.table_view.scrollToBottom()

    def apply_filters(self):
        level = self.current_level
        ignore_fold = self.edit_ignore_fold.text() if self.chk_ignore_fold.isChecked() else ""
        ignore_source = self.edit_ignore_source.text() if self.chk_ignore_source.isChecked() else ""
        fold_enabled = self.chk_fold_by_code.isChecked()
        
        self.model.set_filters(level, ignore_fold, ignore_source, fold_enabled)
        self.table_view.scrollToBottom()

    def set_level(self, level):
        self.current_level = level
        self.update_level_buttons()
        self.apply_filters()
    
    def update_level_buttons(self):
        style_active = """
            background-color: rgb(74, 144, 226);
            color: white;
            font: 9pt "HarmonyOS Sans SC";
            border-radius: 5px;
            border: 1px solid gray;
        """
        style_normal = """
            background-color: #f0f0f0;
            color: black;
            font: 9pt "HarmonyOS Sans SC";
            border-radius: 5px;
            border: 1px solid gray;
        """
        for level, btn in self.level_buttons.items():
            if level == self.current_level:
                btn.setStyleSheet(style_active)
            else:
                btn.setStyleSheet(style_normal)

    def choose_color(self):
        color = QColorDialog.getColor(self.mark_color, self, "Select Mark Color")
        if color.isValid():
            self.mark_color = color
            self.update_mark_preview()

    def update_mark_preview(self):
        self.btn_mark_color.setStyleSheet(f"background-color: {self.mark_color.name()}; border: 1px solid gray;")

    def on_table_clicked(self, index):
        if self.chk_mark_mode.isChecked():
            self.model.mark_row(index, self.mark_color)

    def on_table_double_clicked(self, index):
        self.model.toggle_group(index)

    def export_logs(self):
        cwd = get_app_base_path()
        QDesktopServices.openUrl(QUrl.fromLocalFile(cwd))

    def import_logs(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "YTL Files (*.ytl);;All Files (*)")
        if fname:
            self.show_loading()
            # 用 QTimer 稍等一下再加载，让界面先更新一下
            QTimer.singleShot(100, lambda: self.load_log_file(fname))

    def load_log_file(self, path):
        self.model.clear()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                entries = []
                for line in lines:
                    if line.startswith("[Yuanyue") or line.startswith("[程序路径"):
                        continue
                    entry = self.shm_worker.parse_log_line(line)
                    if entry:
                        entries.append(entry)
                self.model.add_entries(entries)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
        finally:
            self.hide_loading()

    def closeEvent(self, event):
        self.shm_worker.stop()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DebugMonitor()
    window.show()
    sys.exit(app.exec_())
