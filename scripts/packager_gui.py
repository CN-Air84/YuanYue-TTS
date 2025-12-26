import sys
import subprocess
import os
import shutil
import time
from pathlib import Path
from packaging import version
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QRadioButton, QTextEdit, QFileDialog,
    QMessageBox
)
from PyQt5.QtCore import QProcess, QEvent
from PyQt5.QtGui import QIntValidator


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
        self.initUI()
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
    
    def get_latest_version_from_backup(self):
        """从backup文件夹中查找最新版本号"""
        backup_dir = Path("./backup")
        if not backup_dir.exists():
            return None
            
        version_dirs = []
        for item in backup_dir.iterdir():
            if item.is_dir():
                try:
                    # 尝试将目录名解析为版本号
                    version.parse(item.name)
                    version_dirs.append(item.name)
                except version.InvalidVersion:
                    # 如果不是有效的版本号格式，忽略该目录
                    continue
        
        if not version_dirs:
            return None
            
        # 使用packaging.version来正确排序版本号
        version_dirs.sort(key=version.parse, reverse=True)
        return version_dirs[0]  # 返回最新版本

    def initUI(self):
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

        # 控制台选项
        self.no_console_checkbox = QCheckBox('隐藏控制台窗口')
        self.no_console_checkbox.setChecked(True)
        options_layout.addWidget(self.no_console_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

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
        filename, _ = QFileDialog.getOpenFileName(self, '选择入口文件', '', 'Python Files (*.py)')
        if filename:
            self.filename_input.setText(filename)

    def browse_icon(self):
        filename, _ = QFileDialog.getOpenFileName(self, '选择图标文件', '', 'Icon Files (*.ico)')
        if filename:
            self.icon_input.setText(filename)

    def start_packaging(self):
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
        filename = self.filename_input.text()
        
        # 保存原始文件路径信息
        original_path = Path(filename)
        original_dir = original_path.parent
        original_name = original_path.stem
        original_ext = original_path.suffix
        
        try:
            # 创建备份目录
            backup_dir = Path("./backup") / version
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.log_output.append(f"创建备份目录: {backup_dir}")
            
            # 重命名原文件为xxx_source
            source_filename = original_dir / f"{original_name}_source{original_ext}"
            if not source_filename.exists():
                original_path.rename(source_filename)
                self.log_output.append(f"原文件已重命名为: {source_filename.name}")
            
            # 复制文件并重命名为xxx_package
            package_filename = original_dir / f"{original_name}_package{original_ext}"
            shutil.copy2(source_filename, package_filename)
            self.log_output.append(f"已创建打包文件: {package_filename.name}")
            
            # 内容替换：读取_package文件，替换指定标记
            try:
                with open(package_filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 获取更新内容
                update_content = self.update_content_input.toPlainText()
                
                # 获取当前日期
                current_date = time.strftime("%Y-%m-%d")
                
                # 替换标记
                content = content.replace('☺packager-replace-version☺', version)
                content = content.replace('☺packager-replace-version-infos☺', update_content)
                content = content.replace('☺packager-replace-update-date☺', current_date)
                
                # 写回文件
                with open(package_filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                self.log_output.append(f"已完成内容替换: 版本号={version}, 日期={current_date}")
            except Exception as e:
                self.log_output.append(f"内容替换时出错: {str(e)}")
            
            # 获取更新内容并写入文件（保留原有功能）
            update_content = self.update_content_input.toPlainText()
            if update_content.strip():
                update_file_path = original_dir / "update_log.txt"
                try:
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
            
            # 更新filename为_package文件
            filename = str(package_filename)
            
        except Exception as e:
            self.log_output.append(f"文件操作出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"文件操作失败: {str(e)}")
            self.pack_btn.setEnabled(True)
            self.pack_btn.setText('开始打包')
            return
        
        icon_path = self.icon_input.text()
        
        # 构建命令参数
        args = ['pyinstaller']
        args.append(f'--name={version}')
        
        # 添加文件选项
        if self.add_settings_checkbox.isChecked():
            # 如果勾选了添加settings.ini，则不需要额外操作
            pass
        else:
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
        
        # 图标选项
        if icon_path:
            args.append(f'--icon={icon_path}')
        else:
            # 使用默认图标
            args.append('--icon=G:\\YanchaTTS\\1.ico')
        
        # 单文件选项
        if self.single_file_checkbox.isChecked():
            args.append('--onefile')
        
        # 控制台选项
        if self.no_console_checkbox.isChecked():
            args.append('--windowed')
        
        # 添加入口文件（使用_package文件）
        args.append(filename)
        
        # 显示构建的命令
        cmd = 'pyinstaller ' + ' '.join(args[1:])  # 移除args中的第一个元素'pyinstaller'
        self.log_output.append(f'执行命令: {cmd}')
        
        # 禁用打包按钮
        self.pack_btn.setEnabled(False)
        self.pack_btn.setText('打包中...')
        
        # 启动进程 - 使用-m参数运行pyinstaller模块
        self.process.start('pyinstaller', args[1:])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        try:
            stdout = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            stdout = bytes(data).decode("utf-8", errors="replace")
        self.log_output.append(stdout)

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        try:
            stderr = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            stderr = bytes(data).decode("utf-8", errors="replace")
        self.log_output.append(stderr)

    def process_finished(self):
        self.pack_btn.setEnabled(True)
        self.pack_btn.setText('开始打包')
        
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
        filename = self.filename_input.text()
        
        # 保存原始文件路径信息
        original_path = Path(filename)
        original_dir = original_path.parent
        original_name = original_path.stem
        original_ext = original_path.suffix
        
        try:
            # 删除对应的.spec文件
            spec_filename = f"{original_name}_package.spec"
            spec_path = original_dir / spec_filename
            
            if spec_path.exists():
                try:
                    os.remove(spec_path)
                    self.log_output.append(f"已删除 {spec_filename} 文件")
                except Exception as e:
                    self.log_output.append(f"删除 {spec_filename} 文件时出错: {str(e)}")
            
            # 创建备份目录
            backup_dir = Path("./backup") / version
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制同目录下所有.py文件到备份目录（包括_source和_package）
            for py_file in original_dir.glob("*.py"):
                try:
                    shutil.copy2(py_file, backup_dir)
                    self.log_output.append(f"已备份文件: {py_file.name}")
                except Exception as e:
                    self.log_output.append(f"备份文件 {py_file.name} 时出错: {str(e)}")
            
            # 删除原目录下的_package程序
            package_filename = original_dir / f"{original_name}_package{original_ext}"
            if package_filename.exists():
                package_filename.unlink()
                self.log_output.append(f"已删除临时文件: {package_filename.name}")
            
            # 将_source文件改回原来的名字
            source_filename = original_dir / f"{original_name}_source{original_ext}"
            if source_filename.exists():
                source_filename.rename(original_path)
                self.log_output.append(f"已恢复原文件: {original_path.name}")
                
        except Exception as e:
            self.log_output.append(f"打包完成后处理出错: {str(e)}")
        
        self.log_output.append("打包完成!")
        
        # 显示消息框
        QMessageBox.information(self, "完成", "打包已完成！")

    def clear_log(self):
        self.log_output.clear()


def main():
    app = QApplication(sys.argv)
    window = PackagerGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()