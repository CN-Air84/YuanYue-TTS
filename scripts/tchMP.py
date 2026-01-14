# -*- coding: utf-8 -*-


import os, sys, platform
import re, json, requests

# --- 全局状态初始化 ---

os_name = platform.system()

session = requests.Session()
session.proxies = {}  # 全局忽略代理

access_token = None
headers = {"X-ND-AUTH": 'MAC id="0",nonce="0",mac="0"'}

# --- 核心功能函数 ---

def load_access_token() -> None:
    """尝试从 Windows 注册表读取 Access Token"""
    global access_token
    try:
        if os_name == "Windows":
            try:
                import winreg
            except ImportError:
                return
            
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\tchMaterial-parser", 0, winreg.KEY_READ) as key:
                    token, _ = winreg.QueryValueEx(key, "AccessToken")
                    if token:
                        access_token = token
                        headers["X-ND-AUTH"] = f'MAC id="{access_token}",nonce="0",mac="0"'
            except Exception:
                pass
    except Exception:
        pass

def set_access_token(token: str) -> str:
    """设置 Access Token (写入 Windows 注册表)"""
    global access_token
    access_token = token
    headers["X-ND-AUTH"] = f'MAC id="{access_token}",nonce="0",mac="0"'
    
    # 尝试写入注册表
    try:
        if os_name == "Windows":
            try:
                import winreg
            except ImportError:
                return "Access Token 已更新 (仅内存)"

            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\tchMaterial-parser") as key:
                    winreg.SetValueEx(key, "AccessToken", 0, winreg.REG_SZ, token)
                return "Access Token 已更新并保存"
            except Exception:
                return "Access Token 已更新 (保存失败)"
    except Exception:
        return "Access Token 已更新"

def parse(url: str, bookmarks: bool = False) -> tuple[str, str, list] | tuple[None, None, None]:
    """
    解析资源链接
    :param url: 资源页面网址
    :param bookmarks: 是否解析书签信息（本 API 主要用于获取下载链接，通常传 False）
    :return: (下载链接, 标题, 书签列表) 或 (None, None, None)
    """
    try:
        # 1. 提取 contentId 与 contentType
        content_id: str | None = None
        content_type: str | None = None
        resource_url: str | None = None

        query_str = url[url.find("?") + 1:]
        for q in query_str.split("&"):
            pair = q.split("=")
            if len(pair) == 2:
                if pair[0] == "contentId":
                    content_id = pair[1]
                elif pair[0] == "contentType":
                    content_type = pair[1]
        
        if not content_id:
            return None, None, None
        if not content_type:
            content_type = "assets_document"

        # 2. 获取资源信息
        if re.search(r"^https?://([^/]+)/syncClassroom/basicWork/detail", url):
            api_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/resources/details/{content_id}.json"
        else:
            if content_type == "thematic_course":
                api_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/resources/details/{content_id}.json"
            else:
                api_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{content_id}.json"

        response = session.get(api_url)
        data = response.json()
        title = data.get("title", "未知教材")

        # 3. 获取章节目录 (本版本不解析书签，跳过)
        chapters = []

        # 4. 获取 PDF 下载链接
        for item in list(data.get("ti_items", [])):
            if item.get("lc_ti_format") == "pdf":
                resource_url = item.get("ti_storages", [None])[0]
                if not resource_url:
                    continue
                if not access_token:
                    # 未登录时的构造链接逻辑
                    resource_url = re.sub(r"^https?://(?:.+).ykt.cbern.com.cn/(.+)/([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}).pkg/(.+)\.pdf$", 
                                          r"https://c1.ykt.cbern.com.cn/\1/\2.pkg/\3.pdf", resource_url)
                break

        # 如果 ti_items 中没找到，尝试专题课程的特殊逻辑
        if not resource_url and content_type == "thematic_course":
            resources_resp = session.get(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/thematic_course/{content_id}/resources/list.json")
            resources_data = resources_resp.json()
            for resource in list(resources_data):
                if resource.get("resource_type_code") == "assets_document":
                    for item in list(resource.get("ti_items", [])):
                        if item.get("lc_ti_format") == "pdf":
                            resource_url = item.get("ti_storages", [None])[0]
                            if not resource_url:
                                continue
                            if not access_token:
                                resource_url = re.sub(r"^https?://(?:.+).ykt.cbern.com.cn/(.+)/([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}).pkg/(.+)\.pdf$", 
                                                      r"https://c1.ykt.cbern.com.cn/\1/\2.pkg/\3.pdf", resource_url)
                            break

        if resource_url:
            return resource_url, title, chapters
        else:
            return None, None, None

    except Exception:
        return None, None, None

def get_download_link(url: str) -> str | None:
    """
    API 接口：解析并返回 PDF 下载链接。
    用法示例：
        import tchMaterialParser
        link = tchMaterialParser.get_download_link("https://...")
        # 或者使用别名
        link = tchMaterialParser.download("https://...")
    """
    result = parse(url, bookmarks=False)
    if result:
        return result[0]
    return None



# --- 模块初始化 ---

# 自动加载本地 Token（如果有，Windows下读取注册表）
load_access_token()
