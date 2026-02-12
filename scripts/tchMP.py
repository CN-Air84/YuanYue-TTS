# -*- coding: utf-8 -*-


import os, sys, platform
import re, json, requests
from debug_logger import debug_logger, LogLevel

# --- 全局状态初始化 ---

os_name = platform.system()

session = requests.Session()
session.proxies = {}  # 全局忽略代理

access_token = None
headers = {"X-ND-AUTH": 'MAC id="0",nonce="0",mac="0"'}

# --- 核心功能函数 ---

def load_access_token() -> None:
    """尝试从 Windows 注册表读取 Access Token"""
    debug_logger.output("tchMP.py", LogLevel.INFO, "尝试加载 Access Token", fold_code="TCH_TOKEN")
    global access_token
    try:
        if os_name == "Windows":
            try:
                import winreg
                debug_logger.output("tchMP.py", LogLevel.INFO, "已导入 winreg", fold_code="TCH_TOKEN")
            except ImportError:
                debug_logger.output("tchMP.py", LogLevel.WARNING, "无法导入 winreg", fold_code="TCH_TOKEN")
                return
            
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\tchMaterial-parser", 0, winreg.KEY_READ) as key:
                    token, _ = winreg.QueryValueEx(key, "AccessToken")
                    if token:
                        access_token = token
                        headers["X-ND-AUTH"] = f'MAC id="{access_token}",nonce="0",mac="0"'
                        debug_logger.output("tchMP.py", LogLevel.INFO, f"成功从注册表加载 Access Token: {token[:10]}...", fold_code="TCH_TOKEN")
                    else:
                        debug_logger.output("tchMP.py", LogLevel.INFO, "注册表中 Access Token 为空", fold_code="TCH_TOKEN")
            except Exception as e:
                debug_logger.output("tchMP.py", LogLevel.INFO, f"读取注册表失败 (可能未设置): {str(e)}", fold_code="TCH_TOKEN")
    except Exception as e:
        debug_logger.output("tchMP.py", LogLevel.ERROR, f"加载 Access Token 过程中发生异常: {str(e)}", fold_code="TCH_TOKEN")

def set_access_token(token: str) -> str:
    """设置 Access Token (写入 Windows 注册表)"""
    debug_logger.output("tchMP.py", LogLevel.INFO, f"开始设置 Access Token: {token[:10]}...", fold_code="TCH_TOKEN_SET")
    global access_token
    access_token = token
    headers["X-ND-AUTH"] = f'MAC id="{access_token}",nonce="0",mac="0"'
    
    # 尝试写入注册表
    try:
        if os_name == "Windows":
            try:
                import winreg
            except ImportError:
                debug_logger.output("tchMP.py", LogLevel.WARNING, "无法导入 winreg，Token 仅在内存中更新", fold_code="TCH_TOKEN_SET")
                return "Access Token 已更新 (仅内存)"

            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\tchMaterial-parser") as key:
                    winreg.SetValueEx(key, "AccessToken", 0, winreg.REG_SZ, token)
                debug_logger.output("tchMP.py", LogLevel.INFO, "Access Token 已成功保存到注册表", fold_code="TCH_TOKEN_SET")
                return "Access Token 已更新并保存"
            except Exception as e:
                debug_logger.output("tchMP.py", LogLevel.ERROR, f"写入注册表失败: {str(e)}", fold_code="TCH_TOKEN_SET")
                return "Access Token 已更新 (保存失败)"
    except Exception as e:
        debug_logger.output("tchMP.py", LogLevel.ERROR, f"设置 Access Token 过程中发生异常: {str(e)}", fold_code="TCH_TOKEN_SET")
        return "Access Token 已更新"
    return "Access Token 已更新"

def parse(url: str, bookmarks: bool = False) -> tuple[str, str, list] | tuple[None, None, None]:
    """
    解析资源链接
    :param url: 资源页面网址
    :param bookmarks: 是否解析书签信息（本 API 主要用于获取下载链接，通常传 False）
    :return: (下载链接, 标题, 书签列表) 或 (None, None, None)
    """
    debug_logger.output("tchMP.py", LogLevel.INFO, f"开始解析 URL: {url}", fold_code="TCH_PARSE")
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
        
        debug_logger.output("tchMP.py", LogLevel.INFO, f"提取到 contentId: {content_id}, contentType: {content_type}", fold_code="TCH_PARSE")
        
        if not content_id:
            debug_logger.output("tchMP.py", LogLevel.WARNING, "未找到 contentId，解析中止", fold_code="TCH_PARSE")
            return None, None, None
        if not content_type:
            content_type = "assets_document"
            debug_logger.output("tchMP.py", LogLevel.INFO, "未找到 contentType，使用默认值: assets_document", fold_code="TCH_PARSE")

        # 2. 获取资源信息
        if re.search(r"^https?://([^/]+)/syncClassroom/basicWork/detail", url):
            api_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/resources/details/{content_id}.json"
        else:
            if content_type == "thematic_course":
                api_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/resources/details/{content_id}.json"
            else:
                api_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{content_id}.json"

        debug_logger.output("tchMP.py", LogLevel.INFO, f"请求 API URL: {api_url}", fold_code="TCH_PARSE")
        response = session.get(api_url)
        debug_logger.output("tchMP.py", LogLevel.INFO, f"API 响应状态码: {response.status_code}", fold_code="TCH_PARSE")
        data = response.json()
        title = data.get("title", "未知教材")
        debug_logger.output("tchMP.py", LogLevel.INFO, f"资源标题: {title}", fold_code="TCH_PARSE")

        # 3. 获取章节目录 (本版本不解析书签，跳过)
        chapters = []

        # 4. 获取 PDF 下载链接
        ti_items = data.get("ti_items", [])
        debug_logger.output("tchMP.py", LogLevel.INFO, f"找到 {len(ti_items)} 个 ti_items", fold_code="TCH_PARSE")
        for item in list(ti_items):
            if item.get("lc_ti_format") == "pdf":
                resource_url = item.get("ti_storages", [None])[0]
                debug_logger.output("tchMP.py", LogLevel.INFO, f"找到 PDF 资源 URL: {resource_url}", fold_code="TCH_PARSE")
                if not resource_url:
                    continue
                if not access_token:
                    # 未登录时的构造链接逻辑
                    old_url = resource_url
                    resource_url = re.sub(r"^https?://(?:.+).ykt.cbern.com.cn/(.+)/([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}).pkg/(.+)\.pdf$", 
                                          r"https://c1.ykt.cbern.com.cn/\1/\2.pkg/\3.pdf", resource_url)
                    if old_url != resource_url:
                        debug_logger.output("tchMP.py", LogLevel.INFO, f"由于未登录，转换 URL: {resource_url}", fold_code="TCH_PARSE")
                break

        # 如果 ti_items 中没找到，尝试专题课程的特殊逻辑
        if not resource_url and content_type == "thematic_course":
            list_api = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/thematic_course/{content_id}/resources/list.json"
            debug_logger.output("tchMP.py", LogLevel.INFO, f"ti_items 中未找到 PDF，尝试专题课程列表: {list_api}", fold_code="TCH_PARSE")
            resources_resp = session.get(list_api)
            resources_data = resources_resp.json()
            for resource in list(resources_data):
                if resource.get("resource_type_code") == "assets_document":
                    for item in list(resource.get("ti_items", [])):
                        if item.get("lc_ti_format") == "pdf":
                            resource_url = item.get("ti_storages", [None])[0]
                            debug_logger.output("tchMP.py", LogLevel.INFO, f"从专题课程列表中找到 PDF URL: {resource_url}", fold_code="TCH_PARSE")
                            if not resource_url:
                                continue
                            if not access_token:
                                resource_url = re.sub(r"^https?://(?:.+).ykt.cbern.com.cn/(.+)/([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}).pkg/(.+)\.pdf$", 
                                                      r"https://c1.ykt.cbern.com.cn/\1/\2.pkg/\3.pdf", resource_url)
                            break

        if resource_url:
            debug_logger.output("tchMP.py", LogLevel.INFO, "解析成功", fold_code="TCH_PARSE")
            return resource_url, title, chapters
        else:
            debug_logger.output("tchMP.py", LogLevel.WARNING, "未找到 PDF 下载链接", fold_code="TCH_PARSE")
            return None, None, None

    except Exception as e:
        debug_logger.output("tchMP.py", LogLevel.ERROR, f"解析过程中发生异常: {str(e)}", fold_code="TCH_PARSE")
        return None, None, None

def get_download_link(url: str) -> str | None:
    """
    API 接口：解析并返回 PDF 下载链接。
    """
    debug_logger.output("tchMP.py", LogLevel.INFO, f"外部调用 get_download_link: {url}", fold_code="TCH_API")
    result = parse(url, bookmarks=False)
    if result:
        debug_logger.output("tchMP.py", LogLevel.INFO, "成功获取下载链接", fold_code="TCH_API")
        return result[0]
    debug_logger.output("tchMP.py", LogLevel.WARNING, "无法获取下载链接", fold_code="TCH_API")
    return None



# --- 模块初始化 ---

# 自动加载本地 Token（如果有，Windows下读取注册表）
load_access_token()
