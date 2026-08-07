"""
插件模板生成工具

用于快速创建标准化的插件目录结构和样板代码。

使用方法:
    python plugin_template_generator.py <插件名称> [选项]

示例:
    python plugin_template_generator.py my-plugin
    python plugin_template_generator.py my-plugin --type tab
    python plugin_template_generator.py my-plugin --type tts --author "张三"
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List


class PluginTemplateGenerator:
    """插件模板生成器"""
    
    # 插件类型模板
    PLUGIN_TYPES = {
        'tab': '选项卡插件',
        'tts': 'TTS引擎插件',
        'text': '文本处理插件',
        'basic': '基础插件（空模板）'
    }
    
    def __init__(self, plugin_name: str, output_dir: str = "plugins"):
        """
        初始化生成器
        
        Args:
            plugin_name: 插件名称
            output_dir: 输出目录
        """
        self.plugin_name = self._validate_plugin_name(plugin_name)
        self.output_dir = Path(output_dir)
        self.plugin_dir = self.output_dir / self.plugin_name
        
    def _validate_plugin_name(self, name: str) -> str:
        """
        验证插件名称
        
        Args:
            name: 插件名称
            
        Returns:
            验证后的插件名称
        """
        # 转换为小写
        name = name.lower().strip()
        
        # 替换空格和下划线为连字符
        name = name.replace(' ', '-').replace('_', '-')
        
        # 移除非法字符
        import re
        name = re.sub(r'[^a-z0-9\-]', '', name)
        
        # 移除开头和结尾的连字符
        name = name.strip('-')
        
        if not name:
            raise ValueError("插件名称无效，请使用小写字母、数字和连字符")
        
        return name
    
    def generate(self, plugin_type: str = 'basic', author: str = "", 
                 description: str = "", github: str = "") -> bool:
        """
        生成插件模板
        
        Args:
            plugin_type: 插件类型 (tab, tts, text, basic)
            author: 作者名称
            description: 插件描述
            github: GitHub链接
            
        Returns:
            是否生成成功
        """
        try:
            # 检查插件目录是否已存在
            if self.plugin_dir.exists():
                print(f"错误: 插件目录已存在: {self.plugin_dir}")
                return False
            
            # 创建插件目录
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            print(f"创建插件目录: {self.plugin_dir}")
            
            # 生成清单文件
            self._generate_manifest(author, description, github, plugin_type)
            
            # 生成主程序文件
            self._generate_main_file(plugin_type)
            
            # 生成资源目录
            self._generate_resources()
            
            # 生成README文件
            self._generate_readme(plugin_type, author, description)
            
            print(f"\n✅ 插件模板生成成功!")
            print(f"   插件名称: {self.plugin_name}")
            print(f"   插件类型: {self.PLUGIN_TYPES.get(plugin_type, plugin_type)}")
            print(f"   插件目录: {self.plugin_dir}")
            print(f"\n下一步:")
            print(f"   1. 编辑 {self.plugin_dir / 'plugin.json'} 配置插件信息")
            print(f"   2. 编辑 {self.plugin_dir / 'main.py'} 实现插件功能")
            print(f"   3. 重启应用程序加载插件")
            
            return True
            
        except Exception as e:
            print(f"错误: 生成插件模板失败: {e}")
            return False
    
    def _generate_manifest(self, author: str, description: str, 
                          github: str, plugin_type: str) -> None:
        """生成插件清单文件"""
        manifest = {
            "name": self.plugin_name,
            "version": "1.0.0",
            "entry_point": "main.py",
            "author": {
                "github": github or f"https://github.com/{author or 'your-username'}",
                "bilibili": ""
            },
            "description": description or f"{self.PLUGIN_TYPES.get(plugin_type, '插件')} - {self.plugin_name}",
            "update_date": datetime.now().strftime("%Y-%m-%d"),
            "github_repo": "",
            "dependencies": [
                "app_version>=0.16.0"
            ],
            "permissions": [],
            "verifier": [],
            "lang": ["zh_CN"]
        }
        
        # 根据插件类型添加依赖
        if plugin_type == 'tts':
            manifest["dependencies"].append("package:requests>=2.28.0")
        
        manifest_path = self.plugin_dir / "plugin.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=4)
        
        print(f"   创建: {manifest_path}")
    
    def _generate_main_file(self, plugin_type: str) -> None:
        """生成主程序文件"""
        if plugin_type == 'tab':
            content = self._get_tab_template()
        elif plugin_type == 'tts':
            content = self._get_tts_template()
        elif plugin_type == 'text':
            content = self._get_text_template()
        else:
            content = self._get_basic_template()
        
        main_path = self.plugin_dir / "main.py"
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   创建: {main_path}")
    
    def _generate_resources(self) -> None:
        """生成资源目录"""
        # 创建 avatar.png（必需）
        avatar_path = self.plugin_dir / "avatar.png"
        self._create_placeholder_avatar(avatar_path)
        print(f"   创建: {avatar_path} (请替换为实际图标)")
        
        # 创建 resources 目录
        resources_dir = self.plugin_dir / "resources"
        resources_dir.mkdir(exist_ok=True)
        
        # 创建 .gitkeep 文件保持目录
        gitkeep = resources_dir / ".gitkeep"
        gitkeep.touch()
        
        print(f"   创建: {resources_dir}")
        
        # 创建 i18n 目录
        i18n_dir = self.plugin_dir / "resources" / "i18n"
        i18n_dir.mkdir(exist_ok=True)
        
        # 创建中文语言文件
        zh_cn = {
            "plugin_name": self.plugin_name,
            "description": "",
            "messages": {}
        }
        zh_cn_path = i18n_dir / "zh_CN.json"
        with open(zh_cn_path, 'w', encoding='utf-8') as f:
            json.dump(zh_cn, f, ensure_ascii=False, indent=4)
        
        print(f"   创建: {i18n_dir}")
    
    def _create_placeholder_avatar(self, avatar_path: Path) -> None:
        """
        创建占位符 avatar.png
        
        Args:
            avatar_path: 图标文件路径
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # 创建 256x256 的图像
            img = Image.new('RGB', (256, 256), color='#4CAF50')
            draw = ImageDraw.Draw(img)
            
            # 绘制插件名称首字母
            initial = self.plugin_name[0].upper() if self.plugin_name else 'P'
            
            # 绘制文字
            try:
                # 尝试使用系统字体
                font = ImageFont.truetype("arial.ttf", 120)
            except:
                # 使用默认字体
                font = ImageFont.load_default()
            
            # 计算文字位置（居中）
            bbox = draw.textbbox((0, 0), initial, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (256 - text_width) // 2
            y = (256 - text_height) // 2
            
            # 绘制文字
            draw.text((x, y), initial, fill='white', font=font)
            
            # 保存图像
            img.save(avatar_path, 'PNG')
            
        except ImportError:
            # 如果没有 PIL，创建一个简单的文本文件提示
            with open(avatar_path.with_suffix('.txt'), 'w', encoding='utf-8') as f:
                f.write(f"请创建 avatar.png 文件（256x256 PNG 图标）\n")
                f.write(f"提示：安装 Pillow 库可自动生成占位符图标\n")
                f.write(f"命令：pip install Pillow\n")
        except Exception as e:
            logger.warning(f"Failed to create placeholder avatar: {e}")
    
    def _generate_readme(self, plugin_type: str, author: str, 
                        description: str) -> None:
        """生成README文件"""
        readme_content = f"""# {self.plugin_name}

{description or self.PLUGIN_TYPES.get(plugin_type, '插件')}

## 信息

- **名称**: {self.plugin_name}
- **版本**: 1.0.0
- **作者**: {author or 'your-username'}
- **类型**: {self.PLUGIN_TYPES.get(plugin_type, plugin_type)}

## 功能

<!-- 描述插件的主要功能 -->

## 安装

将此目录放入 `plugins/` 文件夹中，重启应用程序即可。

## 使用

<!-- 描述如何使用插件 -->

## 更新日志

### v1.0.0 ({datetime.now().strftime("%Y-%m-%d")})
- 初始版本

## 许可证

MIT License
"""
        
        readme_path = self.plugin_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"   创建: {readme_path}")
    
    def _get_basic_template(self) -> str:
        """获取基础插件模板"""
        return f'''"""
{self.plugin_name} - 插件主模块

插件描述
"""

from plugin_page_base import PluginPageBase


def on_load():
    """插件加载时调用"""
    print(f"插件 {self.plugin_name} 已加载")


def on_enable(api, plugin_name):
    """插件启用时调用
    
    Args:
        api: PluginAPI 实例
        plugin_name: 插件名称
    """
    print(f"插件 {{plugin_name}} 已启用")
    
    # 在这里注册选项卡、TTS引擎等
    # api.register_tab(plugin_name, "tab_name", "显示名称", MyPage)


def on_disable():
    """插件禁用时调用"""
    print(f"插件 {self.plugin_name} 已禁用")


def on_unload():
    """插件卸载时调用"""
    print(f"插件 {self.plugin_name} 已卸载")
'''
    
    def _get_tab_template(self) -> str:
        """获取选项卡插件模板"""
        return f'''"""
{self.plugin_name} - 选项卡插件

提供一个自定义选项卡页面
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit
)
from plugin_page_base import PluginPageBase


class {self._get_class_name()}Page(PluginPageBase):
    """插件页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("{self.plugin_name}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # 内容区域
        self.content = QTextEdit()
        self.content.setPlaceholderText("在这里添加内容...")
        layout.addWidget(self.content)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)
        
        layout.addLayout(btn_layout)
    
    def on_page_created(self):
        """页面创建时调用"""
        # 加载保存的内容
        content = self.get_plugin_config("content", "")
        self.content.setPlainText(content)
    
    def on_page_shown(self):
        """页面显示时调用"""
        pass
    
    def on_page_hidden(self):
        """页面隐藏时调用"""
        # 自动保存
        self._on_save()
    
    def _on_save(self):
        """保存内容"""
        content = self.content.toPlainText()
        self.set_plugin_config("content", content)
        print("内容已保存")
    
    def _on_clear(self):
        """清空内容"""
        self.content.clear()


def on_load():
    """插件加载时调用"""
    print(f"插件 {self.plugin_name} 已加载")


def on_enable(api, plugin_name):
    """插件启用时调用"""
    api.register_tab(
        plugin_name=plugin_name,
        tab_name="{self.plugin_name}_tab",
        display_name="{self.plugin_name}",
        widget_class={self._get_class_name()}Page
    )


def on_disable():
    """插件禁用时调用"""
    pass


def on_unload():
    """插件卸载时调用"""
    pass
'''
    
    def _get_tts_template(self) -> str:
        """获取TTS引擎插件模板"""
        return f'''"""
{self.plugin_name} - TTS引擎插件

提供自定义的文本转语音引擎
"""

import os
from typing import List
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from plugin_page_base import PluginPageBase
from tts_engine_interface import TTSEngineInterface, VoiceInfo, EngineInfo


class {self._get_class_name()}Engine(TTSEngineInterface):
    """自定义TTS引擎"""
    
    def __init__(self):
        self._voices = [
            VoiceInfo(
                voice_id="voice_1",
                voice_name="默认音色",
                language="zh-CN",
                gender="female"
            ),
        ]
    
    def synthesize(self, text: str, voice: str, **kwargs) -> str:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            voice: 音色ID
            **kwargs: 其他参数（speed, pitch, volume等）
            
        Returns:
            生成的音频文件路径
        """
        # TODO: 实现语音合成逻辑
        # 示例：调用外部API或本地引擎
        
        # 创建输出目录
        output_dir = os.path.join("temp", "tts")
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件路径
        output_path = os.path.join(output_dir, f"{{voice}}_{{hash(text)}}.mp3")
        
        # 这里需要实现实际的语音合成
        # 示例代码（需要替换为实际实现）:
        # response = requests.post(api_url, json={{"text": text, "voice": voice}})
        # with open(output_path, 'wb') as f:
        #     f.write(response.content)
        
        return output_path
    
    def get_voices(self) -> List[VoiceInfo]:
        """获取可用音色列表"""
        return self._voices
    
    def get_engine_info(self) -> EngineInfo:
        """获取引擎信息"""
        return EngineInfo(
            engine_id="{self.plugin_name}_engine",
            engine_name="{self.plugin_name} TTS",
            version="1.0.0",
            provider="Your Company"
        )


class {self._get_class_name()}SettingsPage(PluginPageBase):
    """引擎设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("{self.plugin_name} TTS引擎设置")
        layout.addWidget(label)


def on_load():
    """插件加载时调用"""
    print(f"插件 {self.plugin_name} 已加载")


def on_enable(api, plugin_name):
    """插件启用时调用"""
    # 注册TTS引擎
    api.register_tts_engine(
        plugin_name=plugin_name,
        engine_id="{self.plugin_name}_engine",
        engine_class={self._get_class_name()}Engine
    )
    
    # 可选：注册设置页面
    # api.register_tab(
    #     plugin_name=plugin_name,
    #     tab_name="{self.plugin_name}_settings",
    #     display_name="{self.plugin_name}设置",
    #     widget_class={self._get_class_name()}SettingsPage
    # )


def on_disable():
    """插件禁用时调用"""
    pass


def on_unload():
    """插件卸载时调用"""
    pass
'''
    
    def _get_text_template(self) -> str:
        """获取文本处理插件模板"""
        return f'''"""
{self.plugin_name} - 文本处理插件

提供文本处理功能
"""

import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QComboBox
)
from plugin_page_base import PluginPageBase


class {self._get_class_name()}Page(PluginPageBase):
    """文本处理页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 操作选择
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("操作:"))
        
        self.operation_combo = QComboBox()
        self.operation_combo.addItems([
            "转大写",
            "转小写",
            "去除空白",
            "统计字数",
            "提取数字"
        ])
        op_layout.addWidget(self.operation_combo)
        
        self.process_btn = QPushButton("执行")
        self.process_btn.clicked.connect(self._process)
        op_layout.addWidget(self.process_btn)
        
        layout.addLayout(op_layout)
        
        # 输入文本
        layout.addWidget(QLabel("输入文本:"))
        self.input_text = QTextEdit()
        layout.addWidget(self.input_text)
        
        # 输出文本
        layout.addWidget(QLabel("输出结果:"))
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)
    
    def _process(self):
        """执行文本处理"""
        text = self.input_text.toPlainText()
        operation = self.operation_combo.currentText()
        
        if operation == "转大写":
            result = text.upper()
        elif operation == "转小写":
            result = text.lower()
        elif operation == "去除空白":
            result = re.sub(r'\\s+', '', text)
        elif operation == "统计字数":
            result = f"字符数: {{len(text)}}\\n单词数: {{len(text.split())}}\\n行数: {{len(text.splitlines())}}"
        elif operation == "提取数字":
            numbers = re.findall(r'\\d+', text)
            result = f"找到 {{len(numbers)}} 个数字:\\n" + "\\n".join(numbers)
        else:
            result = "未知操作"
        
        self.output_text.setPlainText(result)
        
        # 发送事件通知
        self.emit_plugin_event("text_processed", {{
            "operation": operation,
            "input_length": len(text),
            "output_length": len(result)
        }})


def on_load():
    """插件加载时调用"""
    print(f"插件 {self.plugin_name} 已加载")


def on_enable(api, plugin_name):
    """插件启用时调用"""
    api.register_tab(
        plugin_name=plugin_name,
        tab_name="{self.plugin_name}_text",
        display_name="{self.plugin_name}",
        widget_class={self._get_class_name()}Page
    )


def on_disable():
    """插件禁用时调用"""
    pass


def on_unload():
    """插件卸载时调用"""
    pass
'''
    
    def _get_class_name(self) -> str:
        """将插件名称转换为类名"""
        parts = self.plugin_name.split('-')
        return ''.join(word.capitalize() for word in parts)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='插件模板生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python plugin_template_generator.py my-plugin
  python plugin_template_generator.py my-plugin --type tab
  python plugin_template_generator.py my-plugin --type tts --author "张三"
  python plugin_template_generator.py my-plugin --type text --description "文本处理工具"

插件类型:
  basic  - 基础插件（空模板）
  tab    - 选项卡插件
  tts    - TTS引擎插件
  text   - 文本处理插件
        '''
    )
    
    parser.add_argument(
        'name',
        help='插件名称（小写字母、数字和连字符）'
    )
    
    parser.add_argument(
        '--type', '-t',
        choices=['basic', 'tab', 'tts', 'text'],
        default='basic',
        help='插件类型（默认: basic）'
    )
    
    parser.add_argument(
        '--author', '-a',
        default='',
        help='作者名称'
    )
    
    parser.add_argument(
        '--description', '-d',
        default='',
        help='插件描述'
    )
    
    parser.add_argument(
        '--github', '-g',
        default='',
        help='GitHub链接'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='plugins',
        help='输出目录（默认: plugins）'
    )
    
    args = parser.parse_args()
    
    # 创建生成器
    generator = PluginTemplateGenerator(args.name, args.output)
    
    # 生成模板
    success = generator.generate(
        plugin_type=args.type,
        author=args.author,
        description=args.description,
        github=args.github
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
