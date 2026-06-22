# coding=utf-8
"""
Windows 7 SP1 / Windows 8 兼容性模块

提供以下兼容性支持：
1. 操作系统版本检测（RtlGetVersion 绕过兼容性 shim）
2. TLS 1.2 补丁（Win7 SP1 默认仅启用 TLS 1.0）
3. Qt 渲染引擎降级（Win7 对 DirectWrite 支持不完整）
4. DPI 感知兼容性处理
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

# Windows 版本号阈值
WIN7_SP1_BUILD = 7601   # Windows 7 SP1 最低要求
WIN8_BUILD = 9200       # Windows 8
WIN8_1_BUILD = 9600     # Windows 8.1
WIN10_BUILD = 10240     # Windows 10 (1507)


class CompatLevel:
    """兼容性等级"""
    UNSUPPORTED = 0   # 低于 Win7 SP1，无法运行
    LEGACY = 1        # Win7 SP1 - Win8，需要兼容补丁
    PARTIAL = 2       # Win8.1，理论可运行，少量补丁
    NATIVE = 3        # Win10+，完整支持


# ---------------------------------------------------------------------------
# 版本检测
# ---------------------------------------------------------------------------

def get_windows_version() -> Tuple[int, int, int]:
    """
    获取 Windows 真实版本号 (major, minor, build)。

    在 Windows 8.1 及以上，Python 通过 GetVersionEx 获取的版本号
    可能被兼容性 shim 截断为 6.2（Win8），
    因此使用 RtlGetVersion 或读取注册表来获取真实版本。

    Returns:
        (major, minor, build) 元组，非 Windows 系统返回 (0, 0, 0)
    """
    if not sys.platform.startswith('win'):
        return (0, 0, 0)

    # 方法1：使用 ctypes 调用 ntdll.RtlGetVersion（最可靠，不受 manifest shim 影响）
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

        if result == 0:  # STATUS_SUCCESS
            return (osvi.dwMajorVersion, osvi.dwMinorVersion, osvi.dwBuildNumber)
    except Exception:
        pass

    # 方法2：回退到 sys.getwindowsversion()
    try:
        win_ver = sys.getwindowsversion()
        return (win_ver.major, win_ver.minor, win_ver.build)
    except Exception:
        pass

    # 方法3：回退到 platform.version()
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
    获取当前系统的兼容性等级。

    Returns:
        (level, description) 元组
    """
    if not sys.platform.startswith('win'):
        return (CompatLevel.NATIVE, "非 Windows 系统")

    major, minor, build = get_windows_version()

    if major == 0:
        return (CompatLevel.PARTIAL, "无法检测 Windows 版本，按部分兼容处理")

    if major < 6:
        return (CompatLevel.UNSUPPORTED, f"Windows {major}.{minor} (Build {build}) - 不受支持")

    if major == 6 and minor == 0:
        return (CompatLevel.UNSUPPORTED, f"Windows Vista (Build {build}) - 不受支持")

    if major == 6 and minor == 1:
        if build >= WIN7_SP1_BUILD:
            return (CompatLevel.LEGACY, f"Windows 7 SP1 (Build {build}) - 旧版兼容模式")
        else:
            return (CompatLevel.UNSUPPORTED, f"Windows 7 (Build {build}, 需要 SP1) - 不受支持")

    if major == 6 and minor == 2:
        return (CompatLevel.LEGACY, f"Windows 8 (Build {build}) - 旧版兼容模式")

    if major == 6 and minor == 3:
        return (CompatLevel.PARTIAL, f"Windows 8.1 (Build {build}) - 部分兼容")

    # Windows 10+ (major >= 10)
    return (CompatLevel.NATIVE, f"Windows 10+ (Build {build}) - 完整支持")


def is_legacy_windows() -> bool:
    """判断当前系统是否为旧版 Windows（Win7 SP1 / Win8）"""
    level, _ = get_compat_level()
    return level == CompatLevel.LEGACY


def is_windows_7() -> bool:
    """判断当前系统是否为 Windows 7"""
    if not sys.platform.startswith('win'):
        return False
    major, minor, _ = get_windows_version()
    return major == 6 and minor == 1


def is_windows_8() -> bool:
    """判断当前系统是否为 Windows 8"""
    if not sys.platform.startswith('win'):
        return False
    major, minor, _ = get_windows_version()
    return major == 6 and minor == 2


def is_windows_8_1() -> bool:
    """判断当前系统是否为 Windows 8.1"""
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

    Win7 SP1 默认仅启用 SSL 3.0 和 TLS 1.0，
    而 Edge-TTS 和 GitHub API 等服务要求 TLS 1.2+。

    本函数通过以下方式启用 TLS 1.2：
    1. Python ssl 模块级别确认 TLS 1.2 可用
    2. 设置环境变量引导请求库使用 TLS 1.2
    3. 尝试设置 Windows 注册表以全局启用 TLS 1.2（需要管理员权限，失败不报错）

    Returns:
        True 如果补丁成功应用，False 如果无法完全应用
    """
    if not sys.platform.startswith('win'):
        return True

    level, _ = get_compat_level()
    if level >= CompatLevel.PARTIAL:
        return True  # Win8.1+ 默认已支持 TLS 1.2

    success = True

    # 方法1：Python ssl 模块级别
    try:
        import ssl
        # 确认 TLS 1.2 在可用协议列表中
        if hasattr(ssl, 'PROTOCOL_TLSv1_2') or hasattr(ssl, 'PROTOCOL_TLS_CLIENT'):
            pass  # TLS 1.2 协议可用
        else:
            success = False
    except Exception:
        success = False

    # 方法2：设置环境变量，告知 requests/urllib3 使用系统证书
    os.environ.setdefault('CURL_SSL_BACKEND', 'schannel')
    os.environ.setdefault('REQUESTS_CA_BUNDLE', '')  # 使用系统证书存储

    # 方法3：尝试通过注册表启用 TLS 1.2（需要管理员权限）
    try:
        import winreg
        # 启用 TLS 1.2 客户端
        key_path = r"SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client"
        try:
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "DisabledByDefault", 0, winreg.REG_DWORD, 0)
        except PermissionError:
            # 非管理员权限无法写入 HKLM，尝试 HKCU 备选
            try:
                cu_key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cu_key_path, 0,
                                    winreg.KEY_READ | winreg.KEY_WRITE) as key:
                    secure_protocols = winreg.QueryValueEx(key, "SecureProtocols")
                    # 0x800 = TLS 1.2, 0x200 = TLS 1.1, 0x80 = TLS 1.0
                    new_value = secure_protocols[0] | 0x800 | 0x200 | 0x80
                    winreg.SetValueEx(key, "SecureProtocols", 0,
                                     winreg.REG_DWORD, new_value)
            except Exception:
                pass  # 注册表操作全部失败，不影响程序运行
    except ImportError:
        pass  # winreg 不可用

    return success


# ---------------------------------------------------------------------------
# Qt 渲染引擎降级
# ---------------------------------------------------------------------------

def patch_qt_rendering() -> None:
    """
    为 Windows 7 SP1 / Windows 8 降级 Qt 渲染引擎。

    Win7 的 DirectWrite 实现存在缺陷，可能导致：
    - 文字渲染模糊
    - 字体缺失
    - 界面闪烁

    本函数设置环境变量，强制 Qt 使用兼容渲染：
    - QT_OPENGL=software  以避免 GPU 驱动不兼容
    - QT_QPA_PLATFORM=windows:fontengine=freetype  使用 FreeType 替代 DirectWrite

    **必须在导入 PyQt5 之前调用！**
    """
    if not sys.platform.startswith('win'):
        return

    level, _ = get_compat_level()
    if level >= CompatLevel.PARTIAL:
        return  # Win8.1+ 不需要降级

    # 强制使用软件 OpenGL 渲染（避免 Win7 GPU 驱动不兼容）
    os.environ.setdefault('QT_OPENGL', 'software')

    # 使用 FreeType 字体引擎代替 DirectWrite（更稳定）
    os.environ.setdefault('QT_QPA_PLATFORM', 'windows:fontengine=freetype')


# ---------------------------------------------------------------------------
# DPI 感知兼容性
# ---------------------------------------------------------------------------

def patch_dpi_awareness() -> None:
    """
    为 Windows 7 SP1 / Windows 8 设置 DPI 感知。

    Win7 仅支持系统级 DPI 感知 (System DPI Awareness)，
    不支持 Win10 的 Per-Monitor DPI Awareness v2。

    本函数在 Win7/8 上设置应用程序为 System DPI Aware，避免模糊缩放。

    **必须在创建 QApplication 之前调用！**
    """
    if not sys.platform.startswith('win'):
        return

    level, _ = get_compat_level()

    if level <= CompatLevel.LEGACY:
        # Win7/Win8: 仅设置系统级 DPI 感知
        try:
            import ctypes
            # SetProcessDPIAware 在 user32.dll 中，Win7+ 可用
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    # Win8.1+ / Win10: Per-Monitor DPI 由 Qt 自动处理


# ---------------------------------------------------------------------------
# subprocess 兼容性
# ---------------------------------------------------------------------------

def get_subprocess_startupinfo():
    """
    获取兼容 Win7+ 的 subprocess.STARTUPINFO 对象。

    在 Win7 上，subprocess.STARTUPINFO / STARTF_USESHOWWINDOW / SW_HIDE
    均可用（自 Python 2.x 起），此函数提供统一接口。

    Returns:
        subprocess.STARTUPINFO 实例（已配置隐藏 cmd 窗口），
        非 Windows 返回 None
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
    检查兼容性问题并返回警告列表。

    Returns:
        警告字符串列表，空列表表示无问题
    """
    warnings = []

    if not sys.platform.startswith('win'):
        return warnings

    level, desc = get_compat_level()

    if level == CompatLevel.UNSUPPORTED:
        warnings.append(f"不受支持的操作系统：{desc}。程序可能无法正常运行。")
        return warnings

    if level == CompatLevel.LEGACY:
        # 检查 Python 版本 — Python 3.9+ 不再官方支持 Win7
        py_ver = sys.version_info
        if py_ver >= (3, 9):
            warnings.append(
                f"当前 Python {py_ver.major}.{py_ver.minor} 不官方支持 Windows 7/8。"
                f"建议使用 Python 3.8.x 以获得最佳兼容性。"
            )

        # 检查是否缺少 Universal C Runtime (UCRT)
        # Win7 需要手动安装 KB2999226 才能获得 UCRT
        try:
            import ctypes
            # 尝试加载 ucrtbase.dll，如果失败说明缺少 UCRT
            ctypes.CDLL('ucrtbase.dll')
        except OSError:
            warnings.append(
                "检测到系统可能缺少 Universal C Runtime (UCRT)。"
                "请安装 KB2999226 更新补丁，否则程序可能无法启动。"
            )

        # TLS 1.2 提醒
        warnings.append(
            f"运行于旧版兼容模式（{desc}）。"
            f"已自动启用 TLS 1.2 补丁和 Qt 渲染降级。"
        )

    return warnings


# ---------------------------------------------------------------------------
# 一键初始化（推荐入口）
# ---------------------------------------------------------------------------

def apply_all_compat_patches() -> Tuple[int, List[str]]:
    """
    一键应用所有 Windows 兼容性补丁。

    调用顺序：
    1. patch_qt_rendering()  — 必须在 import PyQt5 之前
    2. patch_dpi_awareness() — 必须在 QApplication 之前
    3. patch_tls_12()        — 网络请求初始化之前
    4. check_compat_warnings() — 收集警告

    Returns:
        (compat_level, warnings) 元组
    """
    # 1. Qt 渲染降级（必须在 PyQt5 导入前）
    patch_qt_rendering()

    # 2. DPI 感知（必须在 QApplication 创建前）
    patch_dpi_awareness()

    # 3. TLS 1.2 补丁
    patch_tls_12()

    # 4. 收集兼容性警告
    warnings = check_compat_warnings()

    level, desc = get_compat_level()
    return level, warnings
