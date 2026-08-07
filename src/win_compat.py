# coding=utf-8
"""
Windows 7 SP1 / Windows 8 兼容性模块

提供以下兼容性支持：
1. 真实系统版本检测（RtlGetVersion 绕过 manifest shim）
2. TLS 1.2 启用（Win7 SP1 默认只启用 TLS 1.0）
3. Qt 渲染引擎降级（Win7 的 DirectWrite 支持不完整）
4. DPI 感知兼容处理
5. subprocess 兼容性辅助
6. 运行时兼容性警告

最低要求：Windows 7 SP1 (Build 7601)
"""

import sys
import os
import platform
import logging
from typing import Optional, Tuple, List

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

WIN7_SP1_BUILD = 7601
WIN8_BUILD = 9200
WIN8_1_BUILD = 9600
WIN10_BUILD = 10240


class CompatLevel:
    UNSUPPORTED = 0
    LEGACY = 1
    PARTIAL = 2
    NATIVE = 3


# ---------------------------------------------------------------------------
# 版本检测
# ---------------------------------------------------------------------------

def get_windows_version() -> Tuple[int, int, int]:
    """
    获取 Windows 真实版本号 (major, minor, build)。

    Windows 8.1 以上系统，Python 通过 GetVersionEx 获取的版本号
    可能被 manifest shim 篡改为 6.2（Win8）。
    改用 RtlGetVersion 或注册表读取真实版本号。

    Returns:
        (major, minor, build)，非 Windows 系统返回 (0, 0, 0)
    """
    if not sys.platform.startswith('win'):
        return (0, 0, 0)

    try:
        import ctypes

        class OSVERSIONINFOEXW(ctypes.Structure):
            _fields_ = [
                ('dwOSVersionInfoSize', ctypes.c_ulong),
                ('dwMajorVersion', ctypes.c_ulong),
                ('dwMinorVersion', ctypes.c_ulong),
                ('dwBuildNumber', ctypes.c_ulong),
                ('dwPlatformId', ctypes.c_ulong),
                ('szCSDVersion', ctypes.c_wchar * 128),
                ('wServicePackMajor', ctypes.c_ushort),
                ('wServicePackMinor', ctypes.c_ushort),
                ('wSuiteMask', ctypes.c_ushort),
                ('wProductType', ctypes.c_byte),
                ('wReserved', ctypes.c_byte),
            ]

        osvi = OSVERSIONINFOEXW()
        osvi.dwOSVersionInfoSize = ctypes.sizeof(OSVERSIONINFOEXW)

        ntdll = ctypes.windll.ntdll
        result = ntdll.RtlGetVersion(ctypes.byref(osvi))

        if result == 0:
            return (osvi.dwMajorVersion, osvi.dwMinorVersion, osvi.dwBuildNumber)
    except Exception:
        pass

    try:
        win_ver = sys.getwindowsversion()
        return (win_ver.major, win_ver.minor, win_ver.build)
    except Exception:
        pass

    try:
        ver_str = platform.version()
        parts = ver_str.split('.')
        if len(parts) >= 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        pass

    return (0, 0, 0)


def get_compat_level() -> Tuple[int, str]:
    """
    判断当前的兼容性等级。

    Returns:
        (level, description) 元组
    """
    if not sys.platform.startswith('win'):
        return (CompatLevel.NATIVE, "非 Windows 系统")

    major, minor, build = get_windows_version()

    if major == 0:
        return (CompatLevel.PARTIAL, "无法确定 Windows 版本，尝试兼容模式")

    if major < 6:
        return (CompatLevel.UNSUPPORTED, f"Windows {major}.{minor} (Build {build}) - 不支持")

    if major == 6 and minor == 0:
        return (CompatLevel.UNSUPPORTED, f"Windows Vista (Build {build}) - 不支持")

    if major == 6 and minor == 1:
        if build >= WIN7_SP1_BUILD:
            return (CompatLevel.LEGACY, f"Windows 7 SP1 (Build {build}) - 旧版兼容模式")
        else:
            return (CompatLevel.UNSUPPORTED, f"Windows 7 (Build {build}, 需要 SP1) - 不支持")

    if major == 6 and minor == 2:
        return (CompatLevel.LEGACY, f"Windows 8 (Build {build}) - 旧版兼容模式")

    if major == 6 and minor == 3:
        return (CompatLevel.PARTIAL, f"Windows 8.1 (Build {build}) - 部分兼容")

    return (CompatLevel.NATIVE, f"Windows 10+ (Build {build}) - 原生支持")


def is_legacy_windows() -> bool:
    level, _ = get_compat_level()
    return level == CompatLevel.LEGACY


def is_windows_7() -> bool:
    if not sys.platform.startswith('win'):
        return False
    major, minor, _ = get_windows_version()
    return major == 6 and minor == 1


def is_windows_8() -> bool:
    if not sys.platform.startswith('win'):
        return False
    major, minor, _ = get_windows_version()
    return major == 6 and minor == 2


def is_windows_8_1() -> bool:
    if not sys.platform.startswith('win'):
        return False
    major, minor, _ = get_windows_version()
    return major == 6 and minor == 3


# ---------------------------------------------------------------------------
# TLS 1.2 补丁
# ---------------------------------------------------------------------------

def patch_tls_12() -> bool:
    """
    为 Windows 7 SP1 / Windows 8 启用 TLS 1.2 支持。

    Win7 SP1 默认只启用 SSL 3.0 和 TLS 1.0，
    而 Edge-TTS 和 GitHub API 等现代服务要求 TLS 1.2+。

    通过以下方式启用 TLS 1.2：
    1. Python ssl 模块级确保 TLS 1.2 可用
    2. 设置环境变量通知 requests/urllib3 使用系统证书
    3. 尝试设置 Windows 注册表启用 TLS 1.2（非管理员失败不报错）

    Returns:
        True 表示补丁成功应用，False 表示无法完全应用
    """
    if not sys.platform.startswith('win'):
        return True

    level, _ = get_compat_level()
    if level >= CompatLevel.PARTIAL:
        return True

    success = True

    try:
        import ssl
        if not (hasattr(ssl, 'PROTOCOL_TLSv1_2') or hasattr(ssl, 'PROTOCOL_TLS_CLIENT')):
            success = False
    except Exception:
        success = False

    os.environ.setdefault('CURL_SSL_BACKEND', 'schannel')
    os.environ.setdefault('REQUESTS_CA_BUNDLE', '')

    try:
        import winreg
        key_path = r"SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client"
        try:
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "DisabledByDefault", 0, winreg.REG_DWORD, 0)
        except PermissionError:
            try:
                cu_key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cu_key_path, 0,
                                    winreg.KEY_READ | winreg.KEY_WRITE) as key:
                    secure_protocols = winreg.QueryValueEx(key, "SecureProtocols")
                    new_value = secure_protocols[0] | 0x800 | 0x200 | 0x80
                    winreg.SetValueEx(key, "SecureProtocols", 0,
                                     winreg.REG_DWORD, new_value)
            except Exception:
                pass
    except ImportError:
        pass

    return success


# ---------------------------------------------------------------------------
# Qt 渲染引擎降级
# ---------------------------------------------------------------------------

def patch_qt_rendering() -> None:
    """
    为 Windows 7 SP1 / Windows 8 设置 Qt 渲染引擎降级。

    Win7 的 DirectWrite 实现存在缺陷，可能导致：
    - 字体渲染模糊
    - 字形缺失
    - 界面闪烁

    通过环境变量强制 Qt 使用软件渲染和 FreeType 字体引擎：
    - QT_OPENGL=software  避免 GPU 驱动兼容性问题
    - QT_QPA_PLATFORM=windows:fontengine=freetype  使用 FreeType 替代 DirectWrite

    **必须在 import PyQt5 之前调用！**
    """
    if not sys.platform.startswith('win'):
        return

    level, _ = get_compat_level()
    if level >= CompatLevel.PARTIAL:
        return

    os.environ.setdefault('QT_OPENGL', 'software')
    os.environ.setdefault('QT_QPA_PLATFORM', 'windows:fontengine=freetype')


# ---------------------------------------------------------------------------
# DPI 感知补丁
# ---------------------------------------------------------------------------

def patch_dpi_awareness() -> None:
    """
    为 Windows 7 SP1 / Windows 8 设置 DPI 感知。

    Win7 仅支持系统级 DPI 感知 (System DPI Awareness)，
    不支持 Win10 的 Per-Monitor DPI Awareness v2。

    在 Win7/8 上将应用程序标记为 System DPI Aware，防止界面模糊缩放。

    **必须在创建 QApplication 之前调用！**
    """
    if not sys.platform.startswith('win'):
        return

    level, _ = get_compat_level()

    if level <= CompatLevel.LEGACY:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# subprocess 辅助
# ---------------------------------------------------------------------------

def get_subprocess_startupinfo():
    """
    获取适用于 Win7+ 的 subprocess.STARTUPINFO 实例。

    用于隐藏子进程的命令行窗口。

    Returns:
        subprocess.STARTUPINFO 实例，非 Windows 返回 None
    """
    if not sys.platform.startswith('win'):
        return None

    import subprocess
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return startupinfo


# ---------------------------------------------------------------------------
# 兼容性警告
# ---------------------------------------------------------------------------

def check_compat_warnings() -> List[str]:
    """
    检测兼容性问题并返回警告列表。

    Returns:
        警告字符串列表，空列表表示无警告
    """
    warnings = []

    if not sys.platform.startswith('win'):
        return warnings

    level, desc = get_compat_level()

    if level == CompatLevel.UNSUPPORTED:
        warnings.append(f"不支持的旧版操作系统：{desc}，程序可能无法正常运行。")
        return warnings

    if level == CompatLevel.LEGACY:
        py_ver = sys.version_info
        if py_ver >= (3, 9):
            warnings.append(
                f"当前 Python {py_ver.major}.{py_ver.minor} 已不再官方支持 Windows 7/8，"
                f"建议使用 Python 3.8.x 以获得最佳兼容性。"
            )

        try:
            import ctypes
            ctypes.CDLL('ucrtbase.dll')
        except OSError:
            warnings.append(
                "检测到系统可能缺少 Universal C Runtime (UCRT)，"
                "请安装 KB2999226 更新，否则程序可能无法启动。"
            )

        warnings.append(
            f"当前处于旧版兼容模式：{desc}，"
            f"已自动启用 TLS 1.2 和 Qt 渲染降级补丁。"
        )

    return warnings


# ---------------------------------------------------------------------------
# 一键初始化（推荐入口）
# ---------------------------------------------------------------------------

def apply_all_compat_patches() -> Tuple[int, List[str]]:
    """
    一键应用所有 Windows 兼容性补丁。

    调用顺序：
    1. patch_qt_rendering()  必须在 import PyQt5 之前
    2. patch_dpi_awareness() 必须在 QApplication 之前
    3. patch_tls_12()        在初始化网络之前
    4. check_compat_warnings() 收集警告

    Returns:
        (compat_level, warnings) 元组
    """
    patch_qt_rendering()
    patch_dpi_awareness()
    patch_tls_12()
    warnings = check_compat_warnings()
    level, desc = get_compat_level()
    return level, warnings
