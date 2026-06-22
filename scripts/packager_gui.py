import sys
import subprocess
import os
import shutil
import time
from pathlib import Path
from packaging import version
from datetime import datetime
import uuid
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QRadioButton, QTextEdit, QFileDialog,
    QMessageBox, QDateEdit, QComboBox
)
from PyQt5.QtCore import QProcess, QEvent, QDate
from PyQt5.QtGui import QIntValidator
from debug_logger import debug_logger, LogLevel

try:
    from misc_func import get_app_base_path
except ImportError:
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))


class VersionLineEdit(QLineEdit):
    def __init__(self, max_value=9, next_widget=None, parent=None):
        super().__init__(parent)
        self.max_value = max_value
        self.next_widget = next_widget
        self.setMaxLength(2)
        self.setValidator(QIntValidator(0, max_value))
        
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        # 如果输入已经达到最大长度，自动跳转到下一个输入框
        if len(self.text()) >= self.maxLength() and self.next_widget:
            self.next_widget.setFocus()
            
    def focusInEvent(self, event):
        super().focusInEvent(event)
        # 全选当前内容以便输入
        self.selectAll()


class PackagerGUI(QWidget):
    def __init__(self):
        super().__init__()
        debug_logger.output("packager_gui.py", LogLevel.INFO, "正在初始化 PackagerGUI", fold_code="PKG_INIT")
        self.initUI()
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        self.package_queue = []
        self.current_package_version = ""
        self.temp_package_filename = ""
    
    def get_latest_version_from_backup(self):
        """从backup文件夹中查找最新版本号"""
        debug_logger.output("packager_gui.py", LogLevel.INFO, "正在从备份目录获取最新版本号", fold_code="PKG_VERSION")
        backup_dir = Path(get_app_base_path()) / "backup"
        if not backup_dir.exists():
            debug_logger.output("packager_gui.py", LogLevel.WARNING, "备份目录不存在", fold_code="PKG_VERSION")
            return None
            
        version_pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+)')
        
        valid_versions = []
        for item in backup_dir.iterdir():
            if item.is_dir():
                match = version_pattern.search(item.name)
                if match:
                    base_version_str = match.group(1)
                    try:
                        parsed_base_version = version.parse(base_version_str)
                        valid_versions.append((parsed_base_version, base_version_str))
                    except version.InvalidVersion:
                        debug_logger.output("packager_gui.py", LogLevel.WARNING, f"忽略无效的版本目录: {item.name}", fold_code="PKG_VERSION")
                        continue # Ignore if the extracted base version is invalid
        
        if not valid_versions:
            debug_logger.output("packager_gui.py", LogLevel.INFO, "未找到有效的历史版本", fold_code="PKG_VERSION")
            return None
            
        # 根据解析后的版本号排序，降序排列
        valid_versions.sort(key=lambda x: x[0], reverse=True)
        latest_v = valid_versions[0][1]
        debug_logger.output("packager_gui.py", LogLevel.INFO, f"检测到最新版本号: {latest_v}", fold_code="PKG_VERSION")
        
        # 返回最新版本的基本版本字符串
        return latest_v

    def initUI(self):
        debug_logger.output("packager_gui.py", LogLevel.INFO, "正在构建打包工具 UI", fold_code="PKG_INIT")
        self.setWindowTitle('打包工具')
        self.setGeometry(100, 100, 600, 500)

        layout = QVBoxLayout()

        # 版本号输入（四个独立输入框）
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel('版本号:'))
        
        self.version_part1 = VersionLineEdit(9)
        self.version_part2 = VersionLineEdit(19)
        self.version_part3 = VersionLineEdit(19)
        self.version_part4 = VersionLineEdit(9)
        
        # 设置焦点链
        self.version_part1.next_widget = self.version_part2
        self.version_part2.next_widget = self.version_part3
        self.version_part3.next_widget = self.version_part4
        
        # 获取最新版本号并设置默认值
        latest_version = self.get_latest_version_from_backup()
        if latest_version:
            version_parts = latest_version.split('.')
            if len(version_parts) >= 3:
                # 第一、二位与最新版本相同
                self.version_part1.setText(version_parts[0])
                self.version_part2.setText(version_parts[1])
                # 第三位为最新版本的第三位+1
                try:
                    third_part = int(version_parts[2]) + 1
                    # 确保不超过最大值19
                    third_part = min(third_part, 19)
                    self.version_part3.setText(str(third_part))
                except ValueError:
                    self.version_part3.setText('1')
                # 第四位默认为0
                self.version_part4.setText('0')
            else:
                # 如果版本号格式不符合预期，使用默认值
                self.version_part1.setText('0')
                self.version_part2.setText('')
                self.version_part3.setText('')
                self.version_part4.setText('0')
        else:
            # 如果没有找到最新版本，使用默认值
            self.version_part1.setText('0')
            self.version_part2.setText('')
            self.version_part3.setText('')
            self.version_part4.setText('0')
        
        version_layout.addWidget(self.version_part1)
        version_layout.addWidget(QLabel('.'))
        version_layout.addWidget(self.version_part2)
        version_layout.addWidget(QLabel('.'))
        version_layout.addWidget(self.version_part3)
        version_layout.addWidget(QLabel('.'))
        version_layout.addWidget(self.version_part4)
        
        layout.addLayout(version_layout)

        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel('入口文件:'))
        self.filename_input = QLineEdit('main_window.py')
        file_layout.addWidget(self.filename_input)
        file_browse_btn = QPushButton('浏览')
        file_browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(file_browse_btn)
        layout.addLayout(file_layout)

        # 图标选择
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel('图标文件:'))
        self.icon_input = QLineEdit('')
        icon_layout.addWidget(self.icon_input)
        icon_browse_btn = QPushButton('浏览')
        icon_browse_btn.clicked.connect(self.browse_icon)
        icon_layout.addWidget(icon_browse_btn)
        layout.addLayout(icon_layout)

        # 版本类型选择
        version_type_layout = QHBoxLayout()
        version_type_layout.addWidget(QLabel('版本类型:'))
        self.version_type_combo = QComboBox()
        self.version_type_combo.addItems(['公测', '广泛内测', '标准内测', '打包测试'])
        version_type_layout.addWidget(self.version_type_combo)
        version_type_layout.addStretch() # Add stretch to push the combo box to the left
        layout.addLayout(version_type_layout)

        # 打包选项组
        options_group = QGroupBox('打包选项')
        options_layout = QVBoxLayout()

        # 是否添加settings.ini
        self.add_settings_checkbox = QCheckBox('添加settings.ini')
        self.add_settings_checkbox.setChecked(False)
        options_layout.addWidget(self.add_settings_checkbox)

        # 其他文件添加
        other_files_layout = QHBoxLayout()
        other_files_layout.addWidget(QLabel('其他文件(用;分隔):'))
        self.other_files_input = QLineEdit()
        other_files_layout.addWidget(self.other_files_input)
        options_layout.addLayout(other_files_layout)

        # 编码选项
        self.encoding_checkbox = QCheckBox('设定UTF-8编码')
        self.encoding_checkbox.setChecked(True)
        options_layout.addWidget(self.encoding_checkbox)

        # 单文件选项
        self.single_file_checkbox = QCheckBox('打包为单文件')
        self.single_file_checkbox.setChecked(True)
        options_layout.addWidget(self.single_file_checkbox)

        # 标准程序选项
        self.standard_dir_checkbox = QCheckBox('打包为标准程序')
        self.standard_dir_checkbox.setChecked(False)
        options_layout.addWidget(self.standard_dir_checkbox)

        # 控制台选项
        self.no_console_checkbox = QCheckBox('隐藏控制台窗口')
        self.no_console_checkbox.setChecked(True)
        options_layout.addWidget(self.no_console_checkbox)

        # Win7/8 兼容性选项
        self.win7_compat_checkbox = QCheckBox('Win7/8 兼容性打包（包含 UCRT 运行时）')
        self.win7_compat_checkbox.setChecked(False)
        options_layout.addWidget(self.win7_compat_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 更新日期输入
        update_date_layout = QHBoxLayout()
        update_date_layout.addWidget(QLabel('更新日期:'))
        self.update_date_input = QDateEdit()
        self.update_date_input.setDate(QDate.currentDate())
        self.update_date_input.setCalendarPopup(True)
        self.update_date_input.setDisplayFormat("yyyy-MM-dd")
        update_date_layout.addWidget(self.update_date_input)
        update_date_layout.addStretch()
        layout.addLayout(update_date_layout)

        # 更新内容输入
        update_content_layout = QHBoxLayout()
        update_content_layout.addWidget(QLabel('更新内容:'))
        self.update_content_input = QTextEdit()
        self.update_content_input.setMaximumHeight(100)
        update_content_layout.addWidget(self.update_content_input)
        layout.addLayout(update_content_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        self.pack_btn = QPushButton('开始打包')
        self.pack_btn.clicked.connect(self.start_packaging)
        button_layout.addWidget(self.pack_btn)

        self.clear_btn = QPushButton('清空日志')
        self.clear_btn.clicked.connect(self.clear_log)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def browse_file(self):
        debug_logger.output("packager_gui.py", LogLevel.INFO, "打开文件浏览对话框 (入口文件)", fold_code="PKG_INIT")
        filename, _ = QFileDialog.getOpenFileName(self, '选择入口文件', '', 'Python Files (*.py)')
        if filename:
            debug_logger.output("packager_gui.py", LogLevel.INFO, f"已选择入口文件: {filename}", fold_code="PKG_INIT")
            self.filename_input.setText(filename)

    def browse_icon(self):
        debug_logger.output("packager_gui.py", LogLevel.INFO, "打开文件浏览对话框 (图标文件)", fold_code="PKG_INIT")
        filename, _ = QFileDialog.getOpenFileName(self, '选择图标文件', '', 'Icon Files (*.ico)')
        if filename:
            debug_logger.output("packager_gui.py", LogLevel.INFO, f"已选择图标文件: {filename}", fold_code="PKG_INIT")
            self.icon_input.setText(filename)

    def start_packaging(self):
        debug_logger.output("packager_gui.py", LogLevel.INFO, "用户触发打包流程", fold_code="PKG_MAIN")
        # 检查是否至少选择了一个打包选项
        if not self.single_file_checkbox.isChecked() and not self.standard_dir_checkbox.isChecked():
            debug_logger.output("packager_gui.py", LogLevel.WARNING, "未选择任何打包方式", fold_code="PKG_MAIN")
            QMessageBox.warning(self, "警告", "请至少选择一种打包方式（单文件或标准程序）！")
            return

        # 获取输入值
        version_parts = [
            self.version_part1.text(),
            self.version_part2.text(),
            self.version_part3.text(),
            self.version_part4.text()
        ]
        
        # 如果最后一位是0，则省略
        if version_parts[-1] == '0':
            version_parts = version_parts[:-1]
            
        version = '.'.join(version_parts)
        
        # 根据版本类型调整版本号
        version_type = self.version_type_combo.currentText()
        if version_type == '广泛内测':
            version = f"pre-release-{version}"
        elif version_type == '标准内测':
            current_time = datetime.now().strftime("%m%d-%H%M")
            version = f"{version}-Test[{current_time}]"
        elif version_type == '打包测试':
            version = str(uuid.uuid4()) # 使用随机字符串作为版本号

        self.current_package_version = version # Store the final version for process_finished
        debug_logger.output("packager_gui.py", LogLevel.INFO, f"设定打包版本号: {version} ({version_type})", fold_code="PKG_MAIN")

        filename = self.filename_input.text()
        if not filename:
            debug_logger.output("packager_gui.py", LogLevel.WARNING, "未指定入口文件", fold_code="PKG_MAIN")
            QMessageBox.warning(self, "警告", "请先选择入口文件！")
            return
        
        # 保存原始文件路径信息
        original_path = Path(filename)
        original_dir = original_path.parent
        original_name = original_path.stem
        original_ext = original_path.suffix
        
        try:
            # 创建备份目录
            backup_dir = Path(get_app_base_path()) / "backup" / version
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.log_output.append(f"创建备份目录: {backup_dir}")
            debug_logger.output("packager_gui.py", LogLevel.INFO, f"创建备份目录: {backup_dir}", fold_code="PKG_MAIN")
            
            # 重命名原文件为xxx_source
            source_filename = original_dir / f"{original_name}_source{original_ext}"
            if not source_filename.exists():
                original_path.rename(source_filename)
                self.log_output.append(f"原文件已重命名为: {source_filename.name}")
                debug_logger.output("packager_gui.py", LogLevel.INFO, f"原文件重命名为: {source_filename.name}", fold_code="PKG_MAIN")
            
            # 复制文件并重命名为xxx_package
            package_filename = original_dir / f"{original_name}_package{original_ext}"
            shutil.copy2(source_filename, package_filename)
            self.log_output.append(f"已创建打包文件: {package_filename.name}")
            debug_logger.output("packager_gui.py", LogLevel.INFO, f"已创建打包副本: {package_filename.name}", fold_code="PKG_MAIN")
            self.temp_package_filename = str(package_filename)
            
            # 内容替换：读取_package文件，替换指定标记
            try:
                debug_logger.output("packager_gui.py", LogLevel.INFO, "正在执行文件内容标记替换", fold_code="PKG_MAIN")
                with open(package_filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 获取更新内容
                update_content = self.update_content_input.toPlainText()
                
                # 获取用户指定的更新日期
                update_date = self.update_date_input.date().toString("yyyy-MM-dd")
                
                # 替换标记
                content = content.replace('☺packager-replace-version☺', version)
                content = content.replace('☺packager-replace-version-infos☺', update_content)
                content = content.replace('☺packager-replace-update-date☺', update_date)
                
                # 写回文件
                with open(package_filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                self.log_output.append(f"已完成内容替换: 版本号={version}, 日期={update_date}")
                debug_logger.output("packager_gui.py", LogLevel.INFO, "内容标记替换完成", fold_code="PKG_MAIN")
            except Exception as e:
                self.log_output.append(f"内容替换时出错: {str(e)}")
                debug_logger.output("packager_gui.py", LogLevel.ERROR, f"内容替换失败: {str(e)}", fold_code="PKG_MAIN")
            
            # 获取更新内容并写入文件（保留原有功能）
            update_content = self.update_content_input.toPlainText()
            if update_content.strip():
                update_file_path = original_dir / "update_log.txt"
                try:
                    debug_logger.output("packager_gui.py", LogLevel.INFO, f"正在生成更新日志: {update_file_path.name}", fold_code="PKG_MAIN")
                    with open(update_file_path, 'w', encoding='utf-8') as f:
                        f.write(update_content)
                    self.log_output.append(f"已写入更新内容到: {update_file_path.name}")
                    
                    # 将update_log.txt添加到打包文件中
                    other_files = self.other_files_input.text().strip()
                    if other_files:
                        self.other_files_input.setText(f"{other_files};{update_file_path};.")
                    else:
                        self.other_files_input.setText(f"{update_file_path};.")
                except Exception as e:
                    self.log_output.append(f"写入更新内容文件时出错: {str(e)}")
                    debug_logger.output("packager_gui.py", LogLevel.ERROR, f"写入更新日志失败: {str(e)}", fold_code="PKG_MAIN")
            
        except Exception as e:
            self.log_output.append(f"文件操作出错: {str(e)}")
            debug_logger.output("packager_gui.py", LogLevel.CRITICAL, f"打包前文件准备失败: {str(e)}", fold_code="PKG_MAIN")
            QMessageBox.critical(self, "错误", f"文件操作失败: {str(e)}")
            self.pack_btn.setEnabled(True)
            self.pack_btn.setText('开始打包')
            return
        
        # 准备任务队列
        self.package_queue = []
        if self.single_file_checkbox.isChecked():
            self.package_queue.append('--onefile')
        if self.standard_dir_checkbox.isChecked():
            self.package_queue.append('--onedir')
        
        debug_logger.output("packager_gui.py", LogLevel.INFO, f"任务队列已就绪: {self.package_queue}", fold_code="PKG_MAIN")
        
        # 禁用打包按钮
        self.pack_btn.setEnabled(False)
        self.pack_btn.setText('打包中...')
        
        # 执行第一个任务
        self.run_next_package()

    def run_next_package(self):
        if not self.package_queue:
            debug_logger.output("packager_gui.py", LogLevel.INFO, "任务队列为空，所有打包任务已启动", fold_code="PKG_MAIN")
            return

        mode = self.package_queue.pop(0)
        version = self.current_package_version
        filename = self.temp_package_filename
        icon_path = self.icon_input.text()
        
        # 构建命令参数
        args = ['pyinstaller']
        args.append(f'--name={version}')
        
        # 排除不需要的模块以减小打包体积
        exclude_modules = [
            'tkinter', 'tkinter.filedialog', 'tkinter.messagebox',
            'matplotlib', 'matplotlib.pyplot',
            'IPython', 'ipython', 'jupyter', 'notebook',
            'pytest', '_pytest', 'unittest', 'doctest',
            'sphinx', 'docutils',
            'pygments',
            'pip', 'setuptools', 'distutils', 'pkg_resources',
            'mypy', 'mypy.version', 'mypy.util', 'mypy.typevars',
            'mypy.types', 'mypy.server', 'mypy.semanal', 'mypy.plugins',
            'mypy.plugin', 'mypy.options', 'mypy.nodes',
            'hypothesis',
            'trio', 'trio.testing', 'trio.socket', 'trio.lowlevel', 'trio.to_thread', 'trio.from_thread',
            'curio',
            'rich', 'rich.pretty',
            'jinja2',
            'outcome',
            'uvloop',
            'pyodide', 'pyodide.ffi',
            'js',
            'bcrypt',
            'zstandard',
            'brotlicffi',
            'compression',
            'socks',
            'chardet',
            'OpenSSL', 'OpenSSL.crypto', 'OpenSSL.SSL',
            'cryptography.x509.UnsupportedExtension',
            'html5lib', 'html5lib.treebuilders',
            'BeautifulSoup', 'bs4',
            'lxml_html_clean',
            'cssselect',
            'cython', 'cython.cimports',
            'email_validator',
            'toml', 'tomli',
            'dotenv',
            'eval_type_backport',
            'annotationlib',
            'trove_classifiers',
            'simplejson',
            'dummy_threading',
            'termios', 'tty',
            'readline', 'rlcompleto',
            'org', 'org.python',
            'java', 'java.lang',
            'vms_lib',
            '_scproxy',
            'usercustomize', 'sitecustomize',
            '_typeshed',
            'websockets', 'websockets.exceptions',
            'OpenGL',
        ]
        for module in exclude_modules:
            args.append(f'--exclude-module={module}')
        
        # 添加文件选项
        if not self.add_settings_checkbox.isChecked():
            other_files = self.other_files_input.text().strip()
            if other_files:
                # 在Windows系统中使用分号作为分隔符
                if sys.platform.startswith("win"):
                    args.append(f'--add-data={other_files}')
                else:
                    args.append(f'--add-data={other_files}:.')
        
        # 编码选项
        if self.encoding_checkbox.isChecked():
            args.append('--hidden-import=encodings.utf_8')

        # Win7/8 兼容性选项
        if self.win7_compat_checkbox.isChecked():
            # 确保 win_compat.py 被打包进去
            args.append('--hidden-import=win_compat')
            # 使用私有程序集（让 UCRT 等运行时 DLL 随 exe 分发，Win7 可能缺少这些 DLL）
            args.append('--win-private-assemblies')
            # 添加 ucrt 的 hidden-import（Win7 需要的 Universal C Runtime）
            args.append('--hidden-import=ucrt')

        runtime_hook_path = Path(__file__).resolve().parent / 'runtime_hook_preload.py'
        if runtime_hook_path.exists():
            args.append(f'--runtime-hook={runtime_hook_path}')
        
        # 图标选项
        if icon_path:
            args.append(f'--icon={icon_path}')
        else:
            # 使用默认图标
            args.append('--icon=G:\\YuanyueTTS\\1.ico')
        
        # 模式选项
        args.append(mode)
        
        # 控制台选项
        if self.no_console_checkbox.isChecked():
            args.append('--windowed')
        
        # 添加入口文件
        args.append(filename)
        
        # 显示构建的命令
        cmd = 'pyinstaller ' + ' '.join(args[1:])
        mode_str = "单文件" if mode == '--onefile' else "标准程序"
        self.log_output.append(f'\n开始进行 [{mode_str}] 打包...')
        self.log_output.append(f'执行命令: {cmd}')
        debug_logger.output("packager_gui.py", LogLevel.INFO, f"启动 PyInstaller [{mode_str}] 打包", fold_code="PKG_MAIN")
        debug_logger.output("packager_gui.py", LogLevel.INFO, f"执行命令: {cmd}", fold_code="PKG_MAIN")
        
        # 启动进程
        self.process.start('pyinstaller', args[1:])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        try:
            stdout = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            stdout = bytes(data).decode("utf-8", errors="replace")
        self.log_output.append(stdout)
        # 将 PyInstaller 的输出也记录到调试日志中，但级别设为 INFO
        if stdout.strip():
            debug_logger.output("packager_gui.py", LogLevel.INFO, f"[PyInstaller STDOUT] {stdout.strip()}", fold_code="PKG_LOG")

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        try:
            stderr = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            stderr = bytes(data).decode("utf-8", errors="replace")
        self.log_output.append(stderr)
        # 错误输出设为 WARNING，因为 PyInstaller 经常在 stderr 输出非致命信息
        if stderr.strip():
            debug_logger.output("packager_gui.py", LogLevel.WARNING, f"[PyInstaller STDERR] {stderr.strip()}", fold_code="PKG_LOG")

    def process_finished(self):
        exit_code = self.process.exitCode()
        debug_logger.output("packager_gui.py", LogLevel.INFO, f"PyInstaller 进程结束，退出代码: {exit_code}", fold_code="PKG_MAIN")
        
        # 检查是否还有待执行的打包任务
        if self.package_queue:
            self.log_output.append("\n当前打包任务已完成，开始下一个任务...")
            debug_logger.output("packager_gui.py", LogLevel.INFO, "当前任务完成，准备启动队列中的下一个任务", fold_code="PKG_MAIN")
            self.run_next_package()
            return

        # 所有打包任务已完成，执行后续清理和备份
        debug_logger.output("packager_gui.py", LogLevel.INFO, "所有打包任务已执行完毕，开始后期处理", fold_code="PKG_CLEAN")
        self.pack_btn.setEnabled(True)
        self.pack_btn.setText('开始打包')
        
        # 使用打包时确定的版本号
        version = self.current_package_version
        filename = self.filename_input.text()
        
        # 保存原始文件路径信息
        original_path = Path(filename)
        original_dir = original_path.parent
        original_name = original_path.stem
        original_ext = original_path.suffix
        
        try:
            # 删除对应的.spec文件
            spec_filename = f"{version}.spec"
            spec_path = original_dir / spec_filename
            
            if spec_path.exists():
                try:
                    os.remove(spec_path)
                    self.log_output.append(f"已删除 {spec_filename} 文件")
                    debug_logger.output("packager_gui.py", LogLevel.INFO, f"删除 spec 文件: {spec_filename}", fold_code="PKG_CLEAN")
                except Exception as e:
                    self.log_output.append(f"删除 {spec_filename} 文件时出错: {str(e)}")
                    debug_logger.output("packager_gui.py", LogLevel.ERROR, f"删除 spec 文件失败: {str(e)}", fold_code="PKG_CLEAN")
            
            # 同时也尝试删除默认命名的 spec 文件（以防万一）
            old_spec_filename = f"{original_name}_package.spec"
            old_spec_path = original_dir / old_spec_filename
            if old_spec_path.exists():
                try:
                    os.remove(old_spec_path)
                    self.log_output.append(f"已删除 {old_spec_filename} 文件")
                    debug_logger.output("packager_gui.py", LogLevel.INFO, f"删除旧版 spec 文件: {old_spec_filename}", fold_code="PKG_CLEAN")
                except:
                    pass
            
            # 创建备份目录
            backup_dir = Path(get_app_base_path()) / "backup" / version
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制同目录下所有.py文件到备份目录（包括_source和_package）
            debug_logger.output("packager_gui.py", LogLevel.INFO, f"正在备份源代码到: {backup_dir}", fold_code="PKG_CLEAN")
            for py_file in original_dir.glob("*.py"):
                try:
                    shutil.copy2(py_file, backup_dir)
                    self.log_output.append(f"已备份文件: {py_file.name}")
                except Exception as e:
                    self.log_output.append(f"备份文件 {py_file.name} 时出错: {str(e)}")
                    debug_logger.output("packager_gui.py", LogLevel.ERROR, f"备份文件 {py_file.name} 失败: {str(e)}", fold_code="PKG_CLEAN")
            
            # 删除原目录下的_package程序
            package_filename = original_dir / f"{original_name}_package{original_ext}"
            if package_filename.exists():
                package_filename.unlink()
                self.log_output.append(f"已删除临时文件: {package_filename.name}")
                debug_logger.output("packager_gui.py", LogLevel.INFO, f"删除临时打包脚本: {package_filename.name}", fold_code="PKG_CLEAN")
            
            # 将_source文件改回原来的名字
            source_filename = original_dir / f"{original_name}_source{original_ext}"
            if source_filename.exists():
                source_filename.rename(original_path)
                self.log_output.append(f"已恢复原文件: {original_path.name}")
                debug_logger.output("packager_gui.py", LogLevel.INFO, f"恢复主入口文件名: {original_path.name}", fold_code="PKG_CLEAN")
                
        except Exception as e:
            self.log_output.append(f"打包完成后处理出错: {str(e)}")
            debug_logger.output("packager_gui.py", LogLevel.ERROR, f"后期处理过程出错: {str(e)}", fold_code="PKG_CLEAN")
        
        self.log_output.append("打包完成!")
        debug_logger.output("packager_gui.py", LogLevel.INFO, "所有打包流程圆满完成", fold_code="PKG_MAIN")
        
        # 显示消息框
        QMessageBox.information(self, "完成", "打包已完成！")

    def clear_log(self):
        debug_logger.output("packager_gui.py", LogLevel.INFO, "用户清空界面日志", fold_code="PKG_LOG")
        self.log_output.clear()


def main():
    app = QApplication(sys.argv)
    window = PackagerGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()