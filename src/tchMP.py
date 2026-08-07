# -*- coding: utf-8 -*-
"""YuanyueTTS adapter for tchMaterial-parser v4.0 parsing logic.

Upstream: https://github.com/happycola233/tchMaterial-parser
"""


import os, sys, platform
import re, json, requests
from debug_logger import debug_logger, LogLevel

# --- 全局状态初始化 ---

os_name = platform.system()

session = requests.Session()
session.proxies = {}  # 全局忽略代理

access_token = None
headers = {
    "Authorization": "Bearer 0",
    "X-ND-AUTH": 'MAC id="0",nonce="0",mac="0"',
}

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
                        headers["Authorization"] = f"Bearer {access_token}"
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
    headers["Authorization"] = f"Bearer {access_token}"
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


def get_download_headers() -> dict[str, str]:
    """Return the authentication headers required by private resource hosts."""
    return dict(headers)


def download_file(url: str, save_path: str, max_attempts: int = 3) -> str:
    """Download a private resource with the same session used by the parser."""
    temp_path = f"{save_path}.part"
    debug_logger.output(
        "tchMP.py", LogLevel.INFO, f"开始直接下载资源: {url}", fold_code="TCH_DOWNLOAD"
    )
    max_attempts = max(1, int(max_attempts))
    last_error = None

    for attempt in range(1, max_attempts + 1):
        response = None
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)

            response = session.get(url, headers=headers, stream=True, timeout=(15, 120))
            response.raise_for_status()
            response_headers = getattr(response, "headers", None) or {}
            expected_size = int(response_headers.get("Content-Length") or 0)

            downloaded_size = 0
            with open(temp_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=131072):
                    if not chunk:
                        continue
                    file.write(chunk)
                    downloaded_size += len(chunk)

            if downloaded_size <= 0:
                raise RuntimeError("服务器未返回有效的 PDF 数据")
            if expected_size > 0 and downloaded_size != expected_size:
                raise RuntimeError(
                    f"下载数据不完整：收到 {downloaded_size} 字节，应为 {expected_size} 字节"
                )

            os.replace(temp_path, save_path)
            debug_logger.output(
                "tchMP.py", LogLevel.INFO,
                f"资源直接下载完成: {save_path}, {downloaded_size} 字节",
                fold_code="TCH_DOWNLOAD",
            )
            return save_path
        except Exception as e:
            last_error = e
        finally:
            if response is not None:
                response.close()

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        status_code = getattr(response, "status_code", None)
        if attempt >= max_attempts or status_code in (401, 403):
            raise last_error

        debug_logger.output(
            "tchMP.py", LogLevel.WARNING,
            f"资源下载中断，将进行第 {attempt + 1}/{max_attempts} 次尝试: {last_error}",
            fold_code="TCH_DOWNLOAD",
        )
        import time
        time.sleep(attempt)

    raise last_error


def _storage_url(item: dict) -> str | None:
    """Resolve the current and legacy storage fields used by Smart Education."""
    resource_url = item.get("ti_storage")
    if resource_url:
        return str(resource_url).replace(
            "cs_path:${ref-path}",
            "https://r1-ndr-private.ykt.cbern.com.cn",
        )

    storages = item.get("ti_storages") or []
    return next((str(url) for url in storages if url), None)


def _source_resource_url(items: list) -> str | None:
    """Find a source document while retaining compatibility with the old API."""
    for item in items or []:
        if not isinstance(item, dict):
            continue
        file_format = str(item.get("ti_format") or item.get("lc_ti_format") or "").lower()
        if not item.get("ti_is_source_file") and file_format != "pdf":
            continue
        resource_url = _storage_url(item)
        if resource_url:
            return resource_url
    return None


def _parse_chapters(data: dict) -> list[dict]:
    """Build the chapter tree from ebook_mapping and national_lesson APIs."""
    mapping_url = None
    for item in data.get("ti_items") or []:
        if isinstance(item, dict) and item.get("ti_file_flag") == "ebook_mapping":
            mapping_url = _storage_url(item)
            break

    if not mapping_url:
        return []

    debug_logger.output(
        "tchMP.py", LogLevel.INFO, f"请求章节映射: {mapping_url}", fold_code="TCH_BOOKMARK"
    )
    mapping_response = session.get(mapping_url)
    mapping_response.raise_for_status()
    mapping_data = mapping_response.json()
    ebook_id = mapping_data.get("ebook_id")

    page_map = {
        mapping.get("node_id"): mapping.get("page_number", 1)
        for mapping in mapping_data.get("mappings") or []
        if isinstance(mapping, dict) and mapping.get("node_id")
    }

    chapters = []
    if ebook_id:
        tree_url = (
            "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/"
            f"national_lesson/trees/{ebook_id}.json"
        )
        debug_logger.output(
            "tchMP.py", LogLevel.INFO, f"请求章节目录: {tree_url}", fold_code="TCH_BOOKMARK"
        )
        tree_response = session.get(tree_url, headers=headers)
        tree_response.raise_for_status()
        tree_data = tree_response.json()

        def process_nodes(nodes: list) -> list[dict]:
            result = []
            for node in nodes or []:
                if not isinstance(node, dict):
                    continue
                chapter = {
                    "title": node.get("title", "未知章节"),
                    "page_index": page_map.get(node.get("id")),
                }
                children = process_nodes(node.get("child_nodes") or [])
                if children:
                    chapter["children"] = children
                result.append(chapter)
            return result

        if isinstance(tree_data, list):
            chapters = process_nodes(tree_data)
        elif isinstance(tree_data, dict):
            chapters = process_nodes(tree_data.get("child_nodes") or [])

    if not chapters:
        sorted_pages = sorted(page_map.items(), key=lambda item: item[1])
        chapters = [
            {"title": f"第 {index} 节 (P{page})", "page_index": page}
            for index, (_, page) in enumerate(sorted_pages, start=1)
        ]

    return chapters


def parse(url: str, bookmarks: bool = False) -> tuple[str, str, list[dict]] | tuple[None, None, None]:
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
        response.raise_for_status()
        data = response.json()
        title = data.get("title", "未知教材")
        debug_logger.output("tchMP.py", LogLevel.INFO, f"资源标题: {title}", fold_code="TCH_PARSE")

        # 3. 获取源文件下载链接。v4.0 起优先使用 ti_is_source_file + ti_storage。
        ti_items = data.get("ti_items", [])
        debug_logger.output("tchMP.py", LogLevel.INFO, f"找到 {len(ti_items)} 个 ti_items", fold_code="TCH_PARSE")
        resource_url = _source_resource_url(ti_items)

        # 4. 如果详情数据中没有源文件，尝试专题课程资源列表。
        if not resource_url and content_type == "thematic_course":
            list_api = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/thematic_course/{content_id}/resources/list.json"
            debug_logger.output("tchMP.py", LogLevel.INFO, f"ti_items 中未找到 PDF，尝试专题课程列表: {list_api}", fold_code="TCH_PARSE")
            resources_resp = session.get(list_api)
            resources_resp.raise_for_status()
            resources_data = resources_resp.json()
            for resource in resources_data or []:
                if resource.get("resource_type_code") != "assets_document":
                    continue
                resource_url = _source_resource_url(resource.get("ti_items") or [])
                if resource_url:
                    break

        if not resource_url:
            debug_logger.output("tchMP.py", LogLevel.WARNING, "未找到 PDF 下载链接", fold_code="TCH_PARSE")
            return None, None, None

        debug_logger.output("tchMP.py", LogLevel.INFO, f"找到源文件 URL: {resource_url}", fold_code="TCH_PARSE")

        # 5. 按需通过 ebook_mapping 与 tree 接口组合章节目录。
        chapters = []
        if bookmarks:
            try:
                chapters = _parse_chapters(data)
                debug_logger.output(
                    "tchMP.py", LogLevel.INFO, f"解析到 {len(chapters)} 个顶级章节", fold_code="TCH_BOOKMARK"
                )
            except Exception as e:
                debug_logger.output(
                    "tchMP.py", LogLevel.WARNING, f"章节目录解析失败，将继续返回下载链接: {e}",
                    fold_code="TCH_BOOKMARK",
                )

        debug_logger.output("tchMP.py", LogLevel.INFO, "解析成功", fold_code="TCH_PARSE")
        return resource_url, title, chapters

    except Exception as e:
        debug_logger.output("tchMP.py", LogLevel.ERROR, f"解析过程中发生异常: {str(e)}", fold_code="TCH_PARSE")
        return None, None, None

def get_download_link(url: str) -> str | None:
    """
    API 接口：解析并返回 PDF 下载链接。
    """
    debug_logger.output("tchMP.py", LogLevel.INFO, f"外部调用 get_download_link: {url}", fold_code="TCH_API")
    result = parse(url, bookmarks=False)
    if result and result[0]:
        debug_logger.output("tchMP.py", LogLevel.INFO, "成功获取下载链接", fold_code="TCH_API")
        return result[0]
    debug_logger.output("tchMP.py", LogLevel.WARNING, "无法获取下载链接", fold_code="TCH_API")
    return None



# --- 模块初始化 ---

# 自动加载本地 Token（如果有，Windows下读取注册表）
load_access_token()
