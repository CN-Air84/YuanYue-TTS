"""
插件元数据模型

定义插件清单（plugin.json）的数据结构。
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import re
from datetime import datetime


@dataclass
class AuthorInfo:
    """作者信息"""
    github: str = ""            # GitHub仓库链接
    bilibili: str = ""          # Bilibili账号
    
    def is_valid(self) -> bool:
        """
        验证作者信息是否有效（至少填写一项）
        
        Returns:
            作者信息是否有效
        """
        return bool(self.github or self.bilibili)
    
    def validate(self) -> Tuple[bool, str]:
        """
        验证作者信息的完整性和格式
        
        Returns:
            (是否有效, 错误信息)
        """
        if not self.is_valid():
            return False, "Author must have at least github or bilibili filled"
        
        # 验证 GitHub 链接格式（如果提供）
        if self.github:
            if not isinstance(self.github, str):
                return False, "GitHub must be a string"
            # 简单验证 URL 格式
            if self.github and not (self.github.startswith("http://") or 
                                   self.github.startswith("https://")):
                return False, "GitHub must be a valid URL starting with http:// or https://"
        
        # 验证 Bilibili 账号格式（如果提供）
        if self.bilibili:
            if not isinstance(self.bilibili, str):
                return False, "Bilibili must be a string"
        
        return True, ""
    
    def __str__(self) -> str:
        """返回作者信息的字符串表示"""
        parts = []
        if self.github:
            parts.append(f"GitHub: {self.github}")
        if self.bilibili:
            parts.append(f"Bilibili: {self.bilibili}")
        return ", ".join(parts) if parts else "Unknown Author"


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str                    # 插件名称（必填）
    version: str                 # 版本号（必填）
    entry_point: str            # 入口模块路径（必填）
    author: AuthorInfo          # 作者信息（必填）
    description: str = ""       # 插件描述（选填）
    update_date: str = ""       # 更新日期（选填，YYYY-MM-DD格式）
    github_repo: str = ""       # GitHub仓库链接（选填，用于更新检查）
    dependencies: List[str] = field(default_factory=list)  # 依赖项（选填）
    permissions: List[str] = field(default_factory=list)   # 权限列表（选填）
    verifier: List[str] = field(default_factory=list)      # 审核员署名（选填）
    lang: List[str] = field(default_factory=list)          # 多语言支持（选填）
    
    def validate(self) -> Tuple[bool, str]:
        """
        验证插件元数据的完整性
        
        Returns:
            (是否有效, 错误信息)
        """
        # 验证必填字段
        if not self.name:
            return False, "Plugin name is required"
        
        if not isinstance(self.name, str):
            return False, "Plugin name must be a string"
        
        if not self.version:
            return False, "Plugin version is required"
        
        if not isinstance(self.version, str):
            return False, "Plugin version must be a string"
        
        # 验证版本号格式（语义化版本）
        if not self._is_valid_version(self.version):
            return False, f"Plugin version '{self.version}' is not a valid semantic version (e.g., 1.0.0)"
        
        if not self.entry_point:
            return False, "Plugin entry_point is required"
        
        if not isinstance(self.entry_point, str):
            return False, "Plugin entry_point must be a string"
        
        if not isinstance(self.author, AuthorInfo):
            return False, "Plugin author must be an AuthorInfo object"
        
        # 验证作者信息
        author_valid, author_error = self.author.validate()
        if not author_valid:
            return False, f"Author validation failed: {author_error}"
        
        # 验证选填字段的类型
        if self.description and not isinstance(self.description, str):
            return False, "Plugin description must be a string"
        
        if self.update_date:
            if not isinstance(self.update_date, str):
                return False, "Plugin update_date must be a string"
            if not self._is_valid_date(self.update_date):
                return False, f"Plugin update_date '{self.update_date}' is not in YYYY-MM-DD format"
        
        if self.github_repo:
            if not isinstance(self.github_repo, str):
                return False, "Plugin github_repo must be a string"
            if not (self.github_repo.startswith("http://") or 
                   self.github_repo.startswith("https://")):
                return False, "Plugin github_repo must be a valid URL"
        
        if not isinstance(self.dependencies, list):
            return False, "Plugin dependencies must be a list"
        
        if not isinstance(self.permissions, list):
            return False, "Plugin permissions must be a list"
        
        if not isinstance(self.verifier, list):
            return False, "Plugin verifier must be a list"
        
        if not isinstance(self.lang, list):
            return False, "Plugin lang must be a list"
        
        return True, ""
    
    def _is_valid_version(self, version: str) -> bool:
        """
        验证版本号是否符合语义化版本格式
        
        Args:
            version: 版本号字符串
            
        Returns:
            是否有效
        """
        # 语义化版本格式：major.minor.patch[-prerelease][+build]
        pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?(?:\+[a-zA-Z0-9.-]+)?$'
        return bool(re.match(pattern, version))
    
    def _is_valid_date(self, date_str: str) -> bool:
        """
        验证日期字符串是否符合 YYYY-MM-DD 格式
        
        Args:
            date_str: 日期字符串
            
        Returns:
            是否有效
        """
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def get_version_tuple(self) -> Optional[Tuple[int, int, int]]:
        """
        将版本号解析为元组（用于版本比较）
        
        Returns:
            (major, minor, patch) 或 None（如果解析失败）
        """
        try:
            # 移除预发布和构建元数据
            version_core = self.version.split('-')[0].split('+')[0]
            parts = version_core.split('.')
            if len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass
        return None
    
    def __str__(self) -> str:
        """返回插件元数据的字符串表示"""
        return f"{self.name} v{self.version} by {self.author}"
