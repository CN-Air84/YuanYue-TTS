"""
在线资源链接管理器
集中管理所有在线资源链接（GitHub/Gitee/Custom），支持多源切换，便于迁移和维护

⚠️ 注意：此文件名为 resource_urls.py，避免与 Python 标准库 urllib 冲突

配置方式：
在 settings.ini 的 [Custom] 节中添加：
resource_source = github  # 或 gitee 或 custom

默认使用 github
"""

import os
import configparser


class ResourceURLManager:
    """在线资源链接管理类，支持 GitHub/Gitee 双源切换"""
    
    # 当前资源源（从配置文件读取，默认 github）
    _current_source = None
    
    # ==================== GitHub 资源配置 ====================
    GITHUB = {
        # 项目主仓库
        "repo_main": "https://github.com/CN-Air84/YuanYue-TTS",
        
        # GitHub 加速镜像
        "mirrors": {
            "ghfast": "https://ghfast.top/",
            "gh_proxy": "https://gh-proxy.org/",
            "hk_gh_proxy": "https://hk.gh-proxy.org/",
            "edgeone": "https://edgeone.gh-proxy.org/",
            "gh_proxy_com": "https://gh-proxy.com/"
        },
        
        # GitHub API
        "api_releases_latest": "https://api.github.com/repos/{owner}/{repo}/releases/latest",
        
        # 图标资源
        "icons": {
            "dictation": "https://CN-Air84.github.io/YuanYue-TTS/ico/Dictation.png",
            "settings": "https://CN-Air84.github.io/YuanYue-TTS/ico/Settings.png",
            "misc": "https://CN-Air84.github.io/YuanYue-TTS/ico/Misc.png",
            "icon": "https://cn-air84.github.io/YuanYue-TTS/ico/icon.png"
        },
        
        # 文档资源
        "docs": {
            "echo_zen": "https://CN-Air84.github.io/YuanYue-TTS/docs/echo_zen.html",
            "intro": "https://CN-Air84.github.io/YuanYue-TTS/docs/intro.html"
        },
        
        # Logo 图片
        "logo_banner": "https://github.com/CN-Air84/YuanYue-TTS/blob/main/docs/icon_full_1080%20_inside.png?raw=true",
        
        # 字体文件
        "fonts": {
            "OpenSymbol": "https://raw.githubusercontent.com/CN-Air84/CN-Air84.github.io/refs/heads/main/YuanYue-TTS/font/opens__.ttf",
            "HarmonyOS_Sans_SC_Black": "https://raw.githubusercontent.com/CN-Air84/CN-Air84.github.io/refs/heads/main/YuanYue-TTS/font/HarmonyOS_Sans_SC_Black.ttf",
            "HarmonyOS_Sans_SC": "https://raw.githubusercontent.com/CN-Air84/CN-Air84.github.io/refs/heads/main/YuanYue-TTS/font/HarmonyOS_Sans_SC_Regular.ttf",
            "HarmonyOS_Sans_SC_Medium": "https://raw.githubusercontent.com/CN-Air84/CN-Air84.github.io/refs/heads/main/YuanYue-TTS/font/HarmonyOS_Sans_SC_Medium.ttf",
            "HarmonyOS_Sans_SC_Thin": "https://raw.githubusercontent.com/CN-Air84/CN-Air84.github.io/refs/heads/main/YuanYue-TTS/font/HarmonyOS_Sans_SC_Thin.ttf"
        },
        
        # Releases 资源
        "releases": {
            "intro_video": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/intro.mov",
            "voicelist": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/voiceList.txt"
        },
        
        # 在线书本仓库
        "textbook_repo": {
            "owner": "TapXWorld",
            "repo": "ChinaTextbook",
            "branch": "main",
            "api_contents": "https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            "raw_base": "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
        },
        
        # 网络检测目标
        "network_test": ("github.com", 443)
    }
    
    # ==================== Gitee 资源配置 ====================
    GITEE = {
        # 项目主仓库（保持 GitHub，用于更新检查等）
        "repo_main": "https://github.com/CN-Air84/YuanYue-TTS",
        
        # Gitee 不需要镜像加速
        "mirrors": {},
        
        # API 保持 GitHub（不迁移）
        "api_releases_latest": "https://api.github.com/repos/{owner}/{repo}/releases/latest",
        
        # 图标资源（迁移到 Gitee）
        "icons": {
            "dictation": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/Dictation.png",
            "settings": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/Settings.png",
            "misc": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/Misc.png",
            "icon": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/icon.png"
        },
        
        # 文档资源（迁移到 Gitee）
        "docs": {
            "echo_zen": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/echo_zen.html",
            "intro": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/intro.html"
        },
        
        # Logo 图片（迁移到 Gitee）
        "logo_banner": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/icon_full_1080%20_inside.png",
        
        # 字体文件（迁移到 Gitee）
        "fonts": {
            "OpenSymbol": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/opens__.ttf",
            "HarmonyOS_Sans_SC_Black": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/HarmonyOS_Sans_SC_Black.ttf",
            "HarmonyOS_Sans_SC": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/HarmonyOS_Sans_SC_Regular.ttf",
            "HarmonyOS_Sans_SC_Medium": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/HarmonyOS_Sans_SC_Medium.ttf",
            "HarmonyOS_Sans_SC_Thin": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/HarmonyOS_Sans_SC_Thin.ttf"
        },
        
        # Releases 资源（迁移到 Gitee）
        "releases": {
            "intro_video": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/intro.mov",
            "voicelist": "https://gitee.com/air84/cn-air84.github.io-gitee-fork/releases/download/res/voiceList.txt"
        },
        
        # 在线书本仓库（保持 GitHub）
        "textbook_repo": {
            "owner": "TapXWorld",
            "repo": "ChinaTextbook",
            "branch": "main",
            "api_contents": "https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            "raw_base": "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
        },
        
        # 网络检测目标（保持 GitHub）
        "network_test": ("github.com", 443)
    }
    
    # ==================== 自建源配置（预留，待官网建设完成后填充）====================
    CUSTOM = {
        # 项目主仓库（待填充）
        "repo_main": "",
        
        # 自建源不需要镜像
        "mirrors": {},
        
        # API（待填充）
        "api_releases_latest": "",
        
        # 图标资源（待填充）
        "icons": {
            "dictation": "",
            "settings": "",
            "misc": "",
            "icon": ""
        },
        
        # 文档资源（待填充）
        "docs": {
            "echo_zen": "",
            "intro": ""
        },
        
        # Logo 图片（待填充）
        "logo_banner": "",
        
        # 字体文件（待填充）
        "fonts": {
            "OpenSymbol": "",
            "HarmonyOS_Sans_SC_Black": "",
            "HarmonyOS_Sans_SC": "",
            "HarmonyOS_Sans_SC_Medium": "",
            "HarmonyOS_Sans_SC_Thin": ""
        },
        
        # Releases 资源（待填充）
        "releases": {
            "intro_video": ""
        },
        
        # 在线书本仓库（待填充）
        "textbook_repo": {
            "owner": "",
            "repo": "",
            "branch": "",
            "api_contents": "",
            "raw_base": ""
        },
        
        # 网络检测目标（待填充）
        "network_test": ("", 0)
    }
    
    @classmethod
    def _load_source_config(cls):
        """从 settings.ini 加载资源源配置"""
        if cls._current_source is not None:
            return cls._current_source
        
        try:
            config = configparser.ConfigParser()
            settings_path = "settings.ini"
            
            if os.path.exists(settings_path):
                config.read(settings_path, encoding='utf-8')
                source = config.get('Custom', 'resource_source', fallback='gitee').lower()

                # 验证配置值
                if source in ['github', 'gitee', 'custom']:
                    cls._current_source = source
                else:
                    cls._current_source = 'gitee'
            else:
                cls._current_source = 'gitee'
        except Exception:
            cls._current_source = 'gitee'
        
        return cls._current_source
    
    @classmethod
    def _get_source_config(cls, source=None):
        """获取指定源的配置"""
        if source is None:
            source = cls._load_source_config()
        
        if source == 'gitee':
            return cls.GITEE
        elif source == 'custom':
            return cls.CUSTOM
        else:
            return cls.GITHUB
    
    @classmethod
    def get_current_source(cls):
        """获取当前资源源"""
        return cls._load_source_config()
    
    @classmethod
    def set_source(cls, source):
        """
        设置资源源（仅在内存中，不写入配置文件）
        
        Args:
            source: 'github', 'gitee' 或 'custom'
        """
        if source in ['github', 'gitee', 'custom']:
            cls._current_source = source
    
    @classmethod
    def get_repo_url(cls, source=None):
        """获取项目主仓库链接"""
        config = cls._get_source_config(source)
        return config["repo_main"]
    
    @classmethod
    def get_mirror(cls, mirror_name="gh_proxy", source=None):
        """
        获取镜像加速地址（仅 GitHub 有效）
        
        Args:
            mirror_name: 镜像名称，可选值: ghfast, gh_proxy, hk_gh_proxy, edgeone, gh_proxy_com
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 镜像地址
        """
        config = cls._get_source_config(source)
        mirrors = config.get("mirrors", {})
        return mirrors.get(mirror_name, mirrors.get("gh_proxy", ""))
    
    @classmethod
    def get_all_mirrors(cls, source=None):
        """获取所有镜像地址"""
        config = cls._get_source_config(source)
        return config.get("mirrors", {}).copy()
    
    @classmethod
    def get_mirror_by_index(cls, index, source=None):
        """
        根据索引获取镜像地址（兼容旧代码，仅 GitHub 有效）
        
        Args:
            index: 镜像索引 (1-4)
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 镜像地址
        """
        mirror_map = {
            1: "ghfast",
            2: "gh_proxy",
            3: "hk_gh_proxy",
            4: "edgeone"
        }
        mirror_name = mirror_map.get(index, "gh_proxy")
        return cls.get_mirror(mirror_name, source)
    
    @classmethod
    def get_api_releases_url(cls, owner, repo, source=None):
        """
        获取 API 最新版本链接
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            source: 指定源，默认使用配置的源
        
        Returns:
            str: API URL
        """
        config = cls._get_source_config(source)
        return config["api_releases_latest"].format(owner=owner, repo=repo)
    
    @classmethod
    def get_icon(cls, icon_name, source=None):
        """
        获取图标资源链接
        
        Args:
            icon_name: 图标名称，可选值: dictation, settings, misc, icon
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 图标 URL
        """
        config = cls._get_source_config(source)
        return config["icons"].get(icon_name, "")
    
    @classmethod
    def get_all_icons(cls, source=None):
        """获取所有图标链接"""
        config = cls._get_source_config(source)
        return config["icons"].copy()
    
    @classmethod
    def get_doc(cls, doc_name, source=None):
        """
        获取文档资源链接
        
        Args:
            doc_name: 文档名称，可选值: echo_zen, intro
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 文档 URL
        """
        config = cls._get_source_config(source)
        return config["docs"].get(doc_name, "")
    
    @classmethod
    def get_logo_banner(cls, source=None):
        """获取 Logo Banner 图片链接"""
        config = cls._get_source_config(source)
        return config["logo_banner"]
    
    @classmethod
    def get_font(cls, font_name, source=None):
        """
        获取字体文件链接
        
        Args:
            font_name: 字体名称，可选值: OpenSymbol, HarmonyOS_Sans_SC_Black, HarmonyOS_Sans_SC, 
                      HarmonyOS_Sans_SC_Medium, HarmonyOS_Sans_SC_Thin
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 字体文件 URL
        """
        config = cls._get_source_config(source)
        return config["fonts"].get(font_name, "")
    
    @classmethod
    def get_all_fonts(cls, source=None):
        """获取所有字体文件链接"""
        config = cls._get_source_config(source)
        return config["fonts"].copy()
    
    @classmethod
    def get_release(cls, release_name, source=None):
        """
        获取 Release 资源链接
        
        Args:
            release_name: Release 资源名称，可选值: intro_video
            source: 指定源，默认使用配置的源
        
        Returns:
            str: Release 资源 URL
        """
        config = cls._get_source_config(source)
        return config["releases"].get(release_name, "")
    
    @classmethod
    def get_network_test_target(cls, source=None):
        """
        获取网络检测目标
        
        Args:
            source: 指定源，默认使用配置的源
        
        Returns:
            tuple: (域名, 端口)
        """
        config = cls._get_source_config(source)
        return config["network_test"]
    
    @classmethod
    def get_textbook_repo_info(cls, source=None):
        """
        获取在线书本仓库信息
        
        Args:
            source: 指定源，默认使用配置的源
        
        Returns:
            dict: 包含 owner, repo, branch 的字典
        """
        config = cls._get_source_config(source)
        repo_config = config.get("textbook_repo", {})
        return {
            "owner": repo_config.get("owner", ""),
            "repo": repo_config.get("repo", ""),
            "branch": repo_config.get("branch", "main")
        }
    
    @classmethod
    def get_textbook_api_url(cls, path="", source=None):
        """
        获取书本仓库 GitHub API 地址（用于获取目录内容）
        
        Args:
            path: 仓库内的路径（如 "小学/语文/一年级上册"）
            source: 指定源，默认使用配置的源
        
        Returns:
            str: API URL
        """
        config = cls._get_source_config(source)
        repo_config = config.get("textbook_repo", {})
        api_template = repo_config.get("api_contents", "")
        
        if not api_template:
            return ""
        
        owner = repo_config.get("owner", "")
        repo = repo_config.get("repo", "")
        return api_template.format(owner=owner, repo=repo, path=path)
    
    @classmethod
    def get_textbook_raw_url(cls, file_path="", source=None):
        """
        获取书本仓库 Raw 文件地址（用于直接下载文件）
        
        Args:
            file_path: 仓库内文件的相对路径（如 "小学/语文/一年级上册/课本.pdf"）
            source: 指定源，默认使用配置的源
        
        Returns:
            str: Raw 文件 URL
        """
        config = cls._get_source_config(source)
        repo_config = config.get("textbook_repo", {})
        raw_base = repo_config.get("raw_base", "")
        
        if not raw_base:
            return ""
        
        return raw_base + file_path
    
    @classmethod
    def convert_to_raw_url(cls, url, source=None):
        """
        将 blob URL 转换为 raw URL
        
        Args:
            url: 原始 URL
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 转换后的 raw URL
        
        Examples:
            GitHub blob: https://github.com/user/repo/blob/main/file.txt
            -> https://raw.githubusercontent.com/user/repo/main/file.txt
            
            Gitee blob: https://gitee.com/user/repo/blob/main/file.txt
            -> https://gitee.com/user/repo/raw/main/file.txt
            
            Custom: 根据自建源的 URL 格式自行处理
        """
        current_source = source or cls._load_source_config()
        
        if current_source == 'github':
            # GitHub: github.com/user/repo/blob/branch/file -> raw.githubusercontent.com/user/repo/branch/file
            if "github.com" in url and "blob" in url:
                return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        elif current_source == 'gitee':
            # Gitee: gitee.com/user/repo/blob/branch/file -> gitee.com/user/repo/raw/branch/file
            if "gitee.com" in url and "blob" in url:
                return url.replace("/blob/", "/raw/")
        elif current_source == 'custom':
            # Custom: 自建源的 URL 转换逻辑（待实现）
            # 目前直接返回原 URL，等官网建好后根据实际情况修改
            pass
        
        return url
    
    @classmethod
    def apply_mirror(cls, url, mirror_index=None, mirror_name=None, source=None):
        """
        为 URL 应用镜像加速（仅 GitHub 有效）
        
        Args:
            url: 原始 URL
            mirror_index: 镜像索引 (1-4)，与 mirror_name 二选一
            mirror_name: 镜像名称，与 mirror_index 二选一
            source: 指定源，默认使用配置的源
        
        Returns:
            str: 应用镜像后的 URL
        """
        # Gitee 和 Custom 不需要镜像
        current_source = source or cls._load_source_config()
        if current_source in ['gitee', 'custom']:
            return url
        
        if mirror_index is not None:
            mirror_url = cls.get_mirror_by_index(mirror_index, source)
        elif mirror_name is not None:
            mirror_url = cls.get_mirror(mirror_name, source)
        else:
            return url
        
        # 如果镜像地址为空，返回原 URL
        if not mirror_url:
            return url
        
        return mirror_url + url


# 兼容旧代码的别名
GitHubURLManager = ResourceURLManager


# ==================== 便捷函数 ====================

def get_resource_url(resource_type, resource_name=None, **kwargs):
    """
    统一的资源获取接口（自动根据配置选择源）
    
    Args:
        resource_type: 资源类型，可选值: 
            - 'repo': 项目主仓库
            - 'mirror': 镜像加速（仅 GitHub）
            - 'api_releases': API 最新版本
            - 'icon': 图标资源
            - 'doc': 文档资源
            - 'logo': Logo Banner
            - 'font': 字体文件
            - 'release': Release 资源
            - 'network_test': 网络检测目标
            - 'textbook_repo': 在线书本仓库信息
            - 'textbook_api': 书本仓库 API 地址（需要 resource_name 作为路径）
            - 'textbook_raw': 书本仓库 Raw 文件地址（需要 resource_name 作为文件路径）
        resource_name: 资源名称（部分类型需要）
        **kwargs: 额外参数
    
    Returns:
        str or tuple: 资源 URL 或网络检测目标元组
    
    Examples:
        >>> get_resource_url('repo')
        'https://github.com/CN-Air84/YuanYue-TTS'  # 或 Gitee 链接
        
        >>> get_resource_url('icon', 'dictation')
        'https://CN-Air84.github.io/YuanYue-TTS/ico/Dictation.png'  # 或 Gitee 链接
        
        >>> get_resource_url('font', 'OpenSymbol')
        'https://raw.githubusercontent.com/...'  # 或 Gitee 链接
    """
    manager = ResourceURLManager
    source = kwargs.get('source')  # 允许临时指定源
    
    if resource_type == 'repo':
        return manager.get_repo_url(source)
    
    elif resource_type == 'mirror':
        mirror_name = kwargs.get('mirror_name')
        mirror_index = kwargs.get('mirror_index')
        if mirror_index is not None:
            return manager.get_mirror_by_index(mirror_index, source)
        return manager.get_mirror(mirror_name, source) if mirror_name else manager.get_mirror(source=source)
    
    elif resource_type == 'api_releases':
        owner = kwargs.get('owner', 'CN-Air84')
        repo = kwargs.get('repo', 'YuanYue-TTS')
        return manager.get_api_releases_url(owner, repo, source)
    
    elif resource_type == 'icon':
        return manager.get_icon(resource_name, source)
    
    elif resource_type == 'doc':
        return manager.get_doc(resource_name, source)
    
    elif resource_type == 'logo':
        return manager.get_logo_banner(source)
    
    elif resource_type == 'font':
        return manager.get_font(resource_name, source)
    
    elif resource_type == 'release':
        return manager.get_release(resource_name, source)
    
    elif resource_type == 'network_test':
        return manager.get_network_test_target(source)
    
    elif resource_type == 'textbook_repo':
        return manager.get_textbook_repo_info(source)
    
    elif resource_type == 'textbook_api':
        return manager.get_textbook_api_url(resource_name, source)
    
    elif resource_type == 'textbook_raw':
        return manager.get_textbook_raw_url(resource_name, source)
    
    else:
        raise ValueError(f"未知的资源类型: {resource_type}")


def apply_mirror(url, mirror_index=None, mirror_name=None, source=None):
    """
    为 URL 应用镜像加速（便捷函数，仅 GitHub 有效）
    
    Args:
        url: 原始 URL
        mirror_index: 镜像索引 (1-4)
        mirror_name: 镜像名称
        source: 指定源，默认使用配置的源
    
    Returns:
        str: 应用镜像后的 URL
    """
    return ResourceURLManager.apply_mirror(url, mirror_index, mirror_name, source)


def convert_to_raw_url(url, source=None):
    """
    将 blob URL 转换为 raw URL（便捷函数）
    
    Args:
        url: 原始 URL（可能包含 /blob/ 路径）
        source: 指定源，默认使用配置的源
    
    Returns:
        str: 转换后的 raw URL
    
    Examples:
        >>> convert_to_raw_url('https://github.com/user/repo/blob/main/file.txt')
        'https://raw.githubusercontent.com/user/repo/main/file.txt'
        
        >>> convert_to_raw_url('https://gitee.com/user/repo/blob/main/file.txt')
        'https://gitee.com/user/repo/raw/main/file.txt'
    """
    return ResourceURLManager.convert_to_raw_url(url, source)


# 兼容旧代码的函数别名
get_github_url = get_resource_url
apply_github_mirror = apply_mirror


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("在线资源链接管理器 - 使用示例")
    print("=" * 60)
    
    # 显示当前配置的源
    current_source = ResourceURLManager.get_current_source()
    print(f"\n当前资源源: {current_source.upper()}")
    print("(可在 settings.ini 的 [Custom] 节中修改 resource_source)")
    
    # 1. 获取项目主仓库
    print("\n1. 项目主仓库:")
    print(f"   {get_resource_url('repo')}")
    
    # 2. 获取镜像地址（仅 GitHub）
    if current_source == 'github':
        print("\n2. GitHub 镜像:")
        for name, url in ResourceURLManager.get_all_mirrors().items():
            print(f"   {name}: {url}")
    else:
        print("\n2. Gitee 不需要镜像加速")
    
    # 3. 获取图标
    print("\n3. 图标资源:")
    for name in ['dictation', 'settings', 'misc', 'icon']:
        print(f"   {name}: {get_resource_url('icon', name)}")
    
    # 4. 获取文档
    print("\n4. 文档资源:")
    print(f"   echo_zen: {get_resource_url('doc', 'echo_zen')}")
    print(f"   intro: {get_resource_url('doc', 'intro')}")
    
    # 5. 获取字体
    print("\n5. 字体文件:")
    for name in ['OpenSymbol', 'HarmonyOS_Sans_SC_Black', 'HarmonyOS_Sans_SC']:
        url = get_resource_url('font', name)
        print(f"   {name}: {url[:80]}...")
    
    # 6. 获取 Logo
    print("\n6. Logo Banner:")
    print(f"   {get_resource_url('logo')}")
    
    # 7. 获取 Release 资源
    print("\n7. Release 资源:")
    print(f"   intro_video: {get_resource_url('release', 'intro_video')}")
    
    # 8. 获取 API URL
    print("\n8. API:")
    print(f"   {get_resource_url('api_releases', owner='CN-Air84', repo='YuanYue-TTS')}")
    
    # 9. 应用镜像（仅 GitHub）
    if current_source == 'github':
        print("\n9. 应用镜像加速:")
        original_url = "https://github.com/CN-Air84/YuanYue-TTS/releases/download/v1.0.0/file.zip"
        print(f"   原始: {original_url}")
        print(f"   镜像1: {apply_mirror(original_url, mirror_index=1)}")
        print(f"   镜像2: {apply_mirror(original_url, mirror_name='gh_proxy')}")
    
    # 10. 网络检测目标
    print("\n10. 网络检测目标:")
    host, port = get_resource_url('network_test')
    print(f"   {host}:{port}")
    
    # 11. 演示切换源
    print("\n11. 演示切换源:")
    print(f"   当前源: {current_source}")
    other_source = 'gitee' if current_source == 'github' else 'github'
    print(f"   切换到 {other_source}:")
    print(f"   Logo: {get_resource_url('logo', source=other_source)}")
    
    print("\n" + "=" * 60)
    print("提示: 要切换资源源，请在 settings.ini 的 [Custom] 节添加:")
    print("resource_source = github  # 或 gitee")
    print("=" * 60)
