"""
插件打包工具

将插件目录打包为 .ytp 格式（YuanyueTTS Plugin）
使用 tar 格式（不压缩）打包成单文件

使用方法:
    python plugin_packager.py <插件目录> [输出文件]

示例:
    python plugin_packager.py plugins/my-plugin
    python plugin_packager.py plugins/my-plugin my-plugin.ytp
    python plugin_packager.py plugins/my-plugin -o output/
"""

import os
import sys
import json
import tarfile
import argparse
from pathlib import Path
from typing import Optional


class PluginPackager:
    """插件打包器"""
    
    REQUIRED_FILES = ['plugin.json', 'main.py', 'avatar.png']
    PACKAGE_EXTENSION = '.ytp'
    
    def __init__(self, plugin_dir: str):
        """
        初始化打包器
        
        Args:
            plugin_dir: 插件目录路径
        """
        self.plugin_dir = Path(plugin_dir)
        
        if not self.plugin_dir.exists():
            raise ValueError(f"插件目录不存在: {plugin_dir}")
        
        if not self.plugin_dir.is_dir():
            raise ValueError(f"不是有效的目录: {plugin_dir}")
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        验证插件目录结构
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 检查必需文件
        for required_file in self.REQUIRED_FILES:
            file_path = self.plugin_dir / required_file
            if not file_path.exists():
                errors.append(f"缺少必需文件: {required_file}")
        
        # 验证 plugin.json
        manifest_path = self.plugin_dir / 'plugin.json'
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                # 检查必填字段
                required_fields = ['name', 'version', 'entry_point', 'author']
                for field in required_fields:
                    if field not in manifest:
                        errors.append(f"plugin.json 缺少必填字段: {field}")
                
                # 验证作者信息
                if 'author' in manifest:
                    author = manifest['author']
                    if not isinstance(author, dict):
                        errors.append("author 字段必须是对象")
                    elif not author.get('github') and not author.get('bilibili'):
                        errors.append("author 必须包含 github 或 bilibili 至少一项")
                
            except json.JSONDecodeError as e:
                errors.append(f"plugin.json 格式错误: {e}")
            except Exception as e:
                errors.append(f"读取 plugin.json 失败: {e}")
        
        # 验证 avatar.png
        avatar_path = self.plugin_dir / 'avatar.png'
        if avatar_path.exists():
            # 检查文件大小（建议不超过 1MB）
            size_mb = avatar_path.stat().st_size / (1024 * 1024)
            if size_mb > 1:
                errors.append(f"avatar.png 文件过大: {size_mb:.2f}MB（建议不超过1MB）")
        
        return (len(errors) == 0, errors)
    
    def package(self, output_path: Optional[str] = None) -> str:
        """
        打包插件
        
        Args:
            output_path: 输出文件路径（可选）
            
        Returns:
            生成的包文件路径
        """
        # 验证插件
        is_valid, errors = self.validate()
        if not is_valid:
            raise ValueError(f"插件验证失败:\n" + "\n".join(f"  - {e}" for e in errors))
        
        # 读取插件名称
        manifest_path = self.plugin_dir / 'plugin.json'
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        plugin_name = manifest['name']
        plugin_version = manifest['version']
        
        # 确定输出路径
        if output_path is None:
            output_path = f"{plugin_name}-{plugin_version}{self.PACKAGE_EXTENSION}"
        elif os.path.isdir(output_path):
            output_path = os.path.join(output_path, f"{plugin_name}-{plugin_version}{self.PACKAGE_EXTENSION}")
        elif not output_path.endswith(self.PACKAGE_EXTENSION):
            output_path += self.PACKAGE_EXTENSION
        
        output_path = Path(output_path)
        
        # 创建输出目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 打包（使用 tar 格式，不压缩）
        print(f"正在打包插件: {plugin_name} v{plugin_version}")
        print(f"源目录: {self.plugin_dir}")
        print(f"输出文件: {output_path}")
        
        with tarfile.open(output_path, 'w') as tar:
            # 添加所有文件
            for item in self._get_files_to_pack():
                arcname = item.relative_to(self.plugin_dir)
                tar.add(item, arcname=arcname)
                print(f"  添加: {arcname}")
        
        # 获取文件大小
        size_mb = output_path.stat().st_size / (1024 * 1024)
        
        print(f"\n✅ 打包完成!")
        print(f"   包文件: {output_path}")
        print(f"   文件大小: {size_mb:.2f} MB")
        
        return str(output_path)
    
    def _get_files_to_pack(self) -> list[Path]:
        """
        获取需要打包的文件列表
        
        Returns:
            文件路径列表
        """
        files = []
        
        # 排除的目录和文件
        exclude_dirs = {'__pycache__', '.git', '.venv', 'venv', 'node_modules'}
        exclude_files = {'.DS_Store', 'Thumbs.db', '.gitignore'}
        exclude_extensions = {'.pyc', '.pyo', '.pyd'}
        
        for item in self.plugin_dir.rglob('*'):
            # 跳过目录
            if item.is_dir():
                continue
            
            # 检查是否在排除目录中
            if any(excluded in item.parts for excluded in exclude_dirs):
                continue
            
            # 检查是否是排除的文件
            if item.name in exclude_files:
                continue
            
            # 检查是否是排除的扩展名
            if item.suffix in exclude_extensions:
                continue
            
            files.append(item)
        
        return files


class PluginUnpacker:
    """插件解包器"""
    
    PACKAGE_EXTENSION = '.ytp'
    
    def __init__(self, package_path: str):
        """
        初始化解包器
        
        Args:
            package_path: 包文件路径
        """
        self.package_path = Path(package_path)
        
        if not self.package_path.exists():
            raise ValueError(f"包文件不存在: {package_path}")
        
        if not self.package_path.suffix == self.PACKAGE_EXTENSION:
            raise ValueError(f"不是有效的插件包文件（必须是 {self.PACKAGE_EXTENSION} 格式）")
    
    def unpack(self, output_dir: str = "plugins") -> str:
        """
        解包插件
        
        Args:
            output_dir: 输出目录（默认: plugins）
            
        Returns:
            解包后的插件目录路径
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"正在解包插件: {self.package_path.name}")
        print(f"输出目录: {output_dir}")
        
        # 解包
        with tarfile.open(self.package_path, 'r') as tar:
            # 读取 plugin.json 获取插件名称
            try:
                manifest_member = tar.getmember('plugin.json')
                manifest_file = tar.extractfile(manifest_member)
                manifest = json.load(manifest_file)
                plugin_name = manifest['name']
            except Exception as e:
                raise ValueError(f"无法读取插件清单: {e}")
            
            # 创建插件目录
            plugin_dir = output_dir / plugin_name
            
            # 检查目录是否已存在
            if plugin_dir.exists():
                print(f"警告: 插件目录已存在，将覆盖: {plugin_dir}")
            
            # 解压所有文件
            tar.extractall(plugin_dir)
            
            # 列出解压的文件
            for member in tar.getmembers():
                if member.isfile():
                    print(f"  解压: {member.name}")
        
        print(f"\n✅ 解包完成!")
        print(f"   插件目录: {plugin_dir}")
        
        return str(plugin_dir)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='插件打包/解包工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
打包示例:
  python plugin_packager.py plugins/my-plugin
  python plugin_packager.py plugins/my-plugin -o my-plugin.ytp
  python plugin_packager.py plugins/my-plugin -o output/

解包示例:
  python plugin_packager.py my-plugin.ytp --unpack
  python plugin_packager.py my-plugin.ytp --unpack -o plugins/
        '''
    )
    
    parser.add_argument(
        'path',
        help='插件目录路径（打包）或包文件路径（解包）'
    )
    
    parser.add_argument(
        '--unpack', '-u',
        action='store_true',
        help='解包模式（默认为打包模式）'
    )
    
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='输出路径（打包时为文件路径，解包时为目录路径）'
    )
    
    args = parser.parse_args()
    
    try:
        if args.unpack:
            # 解包模式
            unpacker = PluginUnpacker(args.path)
            output_dir = args.output or "plugins"
            plugin_dir = unpacker.unpack(output_dir)
            print(f"\n插件已解包到: {plugin_dir}")
        else:
            # 打包模式
            packager = PluginPackager(args.path)
            package_path = packager.package(args.output)
            print(f"\n插件包已创建: {package_path}")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
