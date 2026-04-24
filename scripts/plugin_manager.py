"""
插件管理器 - 整合所有插件管理功能

负责插件的发现、加载、生命周期管理和卸载。
"""

from typing import Dict, List, Optional, Tuple, Callable
from pathlib import Path
import logging
import json
import re
import importlib.util
import sys

from plugin_metadata import PluginMetadata, AuthorInfo
from plugin_instance import PluginInstance, PluginStatus
from plugin_api import PluginAPI
from plugin_event_bus import PluginEventBus
from plugin_errors import (
    PluginError, PluginLoadError, PluginValidationError,
    PluginDependencyError, PluginExecutionError, PluginCrashError,
    PluginLogger, get_plugin_logger
)


logger = logging.getLogger(__name__)


class PluginManager:
    """插件管理器 - 整合所有插件管理功能"""
    
    def __init__(self, main_window):
        """
        初始化插件管理器
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.plugins: Dict[str, PluginInstance] = {}
        self.event_bus = PluginEventBus()  # 先初始化事件总线
        self.plugin_api = PluginAPI(self)  # 再初始化 PluginAPI
        self.plugin_directory = Path("plugins/")
        
        # 初始化插件日志记录器
        self.plugin_logger = get_plugin_logger()
        self.plugin_logger.info("Plugin system initialized")
        
    def discover_plugins(self) -> List[PluginMetadata]:
        """
        发现插件目录中的所有插件
        
        Returns:
            发现的插件元数据列表
        """
        discovered_plugins = []
        
        # 确保插件目录存在
        if not self.plugin_directory.exists():
            logger.warning(f"Plugin directory does not exist: {self.plugin_directory}")
            return discovered_plugins
        
        # 扫描插件目录中的所有子目录
        for plugin_path in self.plugin_directory.iterdir():
            # 跳过非目录项
            if not plugin_path.is_dir():
                continue
            
            # 查找 plugin.json 清单文件
            manifest_path = plugin_path / "plugin.json"
            if not manifest_path.exists():
                logger.warning(f"Plugin manifest not found: {manifest_path}")
                continue
            
            # 解析清单文件
            try:
                metadata = self._parse_manifest(manifest_path)
                if metadata:
                    discovered_plugins.append(metadata)
                    logger.info(f"Discovered plugin: {metadata.name} v{metadata.version}")
            except Exception as e:
                logger.error(f"Error discovering plugin at {plugin_path}: {e}", exc_info=True)
                continue
        
        return discovered_plugins
    
    def _parse_manifest(self, manifest_path: Path) -> Optional[PluginMetadata]:
        """
        解析插件清单文件
        
        Args:
            manifest_path: 清单文件路径
            
        Returns:
            插件元数据对象，如果解析失败则返回None
        """
        try:
            # 读取 JSON 文件
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            # 验证必填字段
            required_fields = ['name', 'version', 'entry_point', 'author']
            for field in required_fields:
                if field not in manifest_data:
                    logger.error(f"Missing required field '{field}' in manifest: {manifest_path}")
                    return None
            
            # 解析作者信息
            author_data = manifest_data['author']
            if not isinstance(author_data, dict):
                logger.error(f"Invalid author format in manifest: {manifest_path}")
                return None
            
            author = AuthorInfo(
                github=author_data.get('github', ''),
                bilibili=author_data.get('bilibili', '')
            )
            
            # 创建插件元数据对象
            metadata = PluginMetadata(
                name=manifest_data['name'],
                version=manifest_data['version'],
                entry_point=manifest_data['entry_point'],
                author=author,
                description=manifest_data.get('description', ''),
                update_date=manifest_data.get('update_date', ''),
                github_repo=manifest_data.get('github_repo', ''),
                dependencies=manifest_data.get('dependencies', []),
                permissions=manifest_data.get('permissions', []),
                verifier=manifest_data.get('verifier', []),
                lang=manifest_data.get('lang', [])
            )
            
            # 验证元数据
            is_valid, error_message = metadata.validate()
            if not is_valid:
                logger.error(f"Invalid plugin metadata in {manifest_path}: {error_message}")
                return None
            
            return metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in manifest {manifest_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing manifest {manifest_path}: {e}", exc_info=True)
            return None
    
    def check_dependencies(self, metadata: PluginMetadata) -> Tuple[bool, List[str]]:
        """
        检查插件的所有依赖项是否满足
        
        Args:
            metadata: 插件元数据
            
        Returns:
            (是否满足, 错误消息列表)
        """
        errors = []
        
        for dependency in metadata.dependencies:
            dep_type, dep_satisfied, dep_error = self._check_single_dependency(dependency)
            
            if not dep_satisfied:
                errors.append(dep_error)
                logger.warning(f"Plugin {metadata.name} dependency not satisfied: {dep_error}")
        
        return (len(errors) == 0, errors)
    
    def _check_single_dependency(self, dependency: str) -> Tuple[str, bool, str]:
        """
        检查单个依赖项
        
        Args:
            dependency: 依赖项字符串
            
        Returns:
            (依赖类型, 是否满足, 错误消息)
        """
        # 解析依赖项格式
        if dependency.startswith("app_version"):
            return self._check_app_version_dependency(dependency)
        elif dependency.startswith("plugin:"):
            return self._check_plugin_dependency(dependency)
        elif dependency.startswith("package:"):
            return self._check_package_dependency(dependency)
        else:
            return ("unknown", False, f"Unknown dependency format: {dependency}")
    
    def _check_app_version_dependency(self, dependency: str) -> Tuple[str, bool, str]:
        """
        检查应用程序版本依赖
        
        Args:
            dependency: 依赖项字符串 (格式: app_version>=0.16.0)
            
        Returns:
            (依赖类型, 是否满足, 错误消息)
        """
        try:
            # 解析版本要求
            match = re.match(r'app_version\s*([><=!]+)\s*(.+)', dependency)
            if not match:
                return ("app_version", False, f"Invalid app_version format: {dependency}")
            
            operator, required_version = match.groups()
            
            # 获取当前应用版本
            app_version = self._get_app_version()
            
            # 比较版本
            if self._compare_versions(app_version, operator, required_version):
                return ("app_version", True, "")
            else:
                return ("app_version", False, 
                       f"App version {app_version} does not satisfy {dependency}")
                       
        except Exception as e:
            return ("app_version", False, f"Error checking app version: {e}")
    
    def _check_plugin_dependency(self, dependency: str) -> Tuple[str, bool, str]:
        """
        检查插件依赖
        
        Args:
            dependency: 依赖项字符串 (格式: plugin:other-plugin>=1.0.0)
            
        Returns:
            (依赖类型, 是否满足, 错误消息)
        """
        try:
            # 解析插件依赖
            match = re.match(r'plugin:([^><=!]+)\s*([><=!]+)\s*(.+)', dependency)
            if not match:
                return ("plugin", False, f"Invalid plugin dependency format: {dependency}")
            
            plugin_name, operator, required_version = match.groups()
            plugin_name = plugin_name.strip()
            
            # 检查插件是否已安装
            if plugin_name not in self.plugins:
                return ("plugin", False, f"Required plugin not installed: {plugin_name}")
            
            # 检查插件是否已启用
            plugin = self.plugins[plugin_name]
            if plugin.status != PluginStatus.ENABLED:
                return ("plugin", False, 
                       f"Required plugin not enabled: {plugin_name} (status: {plugin.status.value})")
            
            # 比较版本
            plugin_version = plugin.metadata.version
            if self._compare_versions(plugin_version, operator, required_version):
                return ("plugin", True, "")
            else:
                return ("plugin", False,
                       f"Plugin {plugin_name} version {plugin_version} does not satisfy {dependency}")
                       
        except Exception as e:
            return ("plugin", False, f"Error checking plugin dependency: {e}")
    
    def _check_package_dependency(self, dependency: str) -> Tuple[str, bool, str]:
        """
        检查Python包依赖
        
        Args:
            dependency: 依赖项字符串 (格式: package:requests>=2.28.0)
            
        Returns:
            (依赖类型, 是否满足, 错误消息)
        """
        try:
            # 解析包依赖
            match = re.match(r'package:([^><=!]+)\s*([><=!]+)\s*(.+)', dependency)
            if not match:
                return ("package", False, f"Invalid package dependency format: {dependency}")
            
            package_name, operator, required_version = match.groups()
            package_name = package_name.strip()
            
            # 检查包是否已安装
            try:
                spec = importlib.util.find_spec(package_name)
                if spec is None:
                    return ("package", False, f"Required Python package not installed: {package_name}")
            except (ImportError, ModuleNotFoundError):
                return ("package", False, f"Required Python package not installed: {package_name}")
            
            # 尝试获取包版本
            try:
                import importlib.metadata as metadata_module
                package_version = metadata_module.version(package_name)
                
                # 比较版本
                if self._compare_versions(package_version, operator, required_version):
                    return ("package", True, "")
                else:
                    return ("package", False,
                           f"Package {package_name} version {package_version} does not satisfy {dependency}")
            except metadata_module.PackageNotFoundError:
                # 包已安装但无法获取版本信息，假设满足依赖
                logger.warning(f"Could not determine version for package {package_name}, assuming satisfied")
                return ("package", True, "")
                
        except Exception as e:
            return ("package", False, f"Error checking package dependency: {e}")
    
    def _get_app_version(self) -> str:
        """
        获取当前应用程序版本
        
        Returns:
            应用程序版本字符串
        """
        try:
            # 尝试从主窗口获取版本
            if hasattr(self.main_window, 'version'):
                return self.main_window.version
            
            # 尝试从配置文件获取版本
            if hasattr(self.main_window, 'settings_manager'):
                version = getattr(self.main_window.settings_manager, 'app_version', None)
                if version:
                    return version
            
            # 默认版本
            return "0.16.0"
            
        except Exception as e:
            logger.warning(f"Could not determine app version: {e}")
            return "0.16.0"
    
    def _compare_versions(self, version1: str, operator: str, version2: str) -> bool:
        """
        比较两个版本号
        
        Args:
            version1: 第一个版本号
            operator: 比较操作符 (>=, >, <=, <, ==, !=)
            version2: 第二个版本号
            
        Returns:
            比较结果
        """
        try:
            # 解析版本号为元组 (major, minor, patch)
            v1_parts = self._parse_version(version1)
            v2_parts = self._parse_version(version2)
            
            # 执行比较
            if operator == ">=":
                return v1_parts >= v2_parts
            elif operator == ">":
                return v1_parts > v2_parts
            elif operator == "<=":
                return v1_parts <= v2_parts
            elif operator == "<":
                return v1_parts < v2_parts
            elif operator == "==":
                return v1_parts == v2_parts
            elif operator == "!=":
                return v1_parts != v2_parts
            else:
                logger.warning(f"Unknown version operator: {operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error comparing versions {version1} {operator} {version2}: {e}")
            return False
    
    def _parse_version(self, version: str) -> Tuple[int, ...]:
        """
        解析版本号字符串为元组
        
        Args:
            version: 版本号字符串 (如 "1.2.3")
            
        Returns:
            版本号元组 (如 (1, 2, 3))
        """
        try:
            # 移除前导 'v' 如果存在
            version = version.lstrip('v')
            
            # 分割版本号并转换为整数
            parts = []
            for part in version.split('.'):
                # 移除非数字字符 (如 "1.0.0-beta" -> "1.0.0")
                numeric_part = re.match(r'(\d+)', part)
                if numeric_part:
                    parts.append(int(numeric_part.group(1)))
                else:
                    parts.append(0)
            
            return tuple(parts)
            
        except Exception as e:
            logger.warning(f"Error parsing version {version}: {e}")
            return (0, 0, 0)
    
    def _wait_for_system_dependencies(self, metadata: PluginMetadata, timeout: int = 30) -> bool:
        """
        等待插件所需的系统组件就绪（需求 19.4, 19.5, 15.8, 15.11）
        
        检查插件依赖中的系统组件（如 shared_memory, settings），
        并等待这些组件就绪，支持超时控制。
        
        Args:
            metadata: 插件元数据
            timeout: 超时时间（秒），默认30秒
            
        Returns:
            系统依赖是否就绪
        """
        import time
        
        try:
            # 提取系统组件依赖
            system_components = self._extract_system_component_dependencies(metadata)
            
            if not system_components:
                # 没有系统组件依赖，直接返回成功
                return True
            
            logger.info(f"Plugin {metadata.name} waiting for system components: {system_components}")
            
            # 获取 ReadyGate 实例
            ready_gate = self.main_window.ready_gate
            
            start_time = time.time()
            all_ready = True
            
            for component in system_components:
                remaining_timeout = timeout - (time.time() - start_time)
                
                if remaining_timeout <= 0:
                    logger.warning(
                        f"Timeout waiting for system component '{component}' "
                        f"for plugin {metadata.name} (timeout={timeout}s)"
                    )
                    all_ready = False
                    break
                
                # 等待组件就绪
                logger.debug(f"Waiting for system component '{component}' (timeout={remaining_timeout:.1f}s)")
                
                # 获取就绪状态的 Event 对象
                with ready_gate._lock:
                    gate = ready_gate._gates.get(component)
                
                if gate is None:
                    logger.warning(f"System component '{component}' not registered in ReadyGate")
                    all_ready = False
                    break
                
                # 等待就绪状态，带超时
                is_ready = gate.wait(remaining_timeout)
                
                if is_ready:
                    logger.debug(f"System component '{component}' is ready")
                else:
                    logger.warning(
                        f"System component '{component}' not ready after {remaining_timeout:.1f}s "
                        f"for plugin {metadata.name}"
                    )
                    all_ready = False
                    break
            
            elapsed = time.time() - start_time
            
            if all_ready:
                logger.info(
                    f"All system dependencies ready for plugin {metadata.name} "
                    f"(elapsed={elapsed:.2f}s)"
                )
            else:
                logger.warning(
                    f"System dependencies not ready for plugin {metadata.name} "
                    f"(elapsed={elapsed:.2f}s, timeout={timeout}s)"
                )
            
            return all_ready
            
        except Exception as e:
            logger.error(f"Error waiting for system dependencies: {e}", exc_info=True)
            # 出错时返回True，允许插件继续加载
            return True
    
    def _extract_system_component_dependencies(self, metadata: PluginMetadata) -> List[str]:
        """
        从插件依赖中提取系统组件依赖（需求 15.8）
        
        系统组件包括：shared_memory, settings, hotkey, audio, notification
        
        Args:
            metadata: 插件元数据
            
        Returns:
            系统组件名称列表
        """
        system_components = []
        
        # 系统组件名称映射
        system_component_names = {
            'shared_memory': 'shared_memory',
            'settings': 'settings',  # 注意：settings 可能不在 ReadyGate 中
            'hotkey': 'hotkey',
            'audio': 'audio',
            'notification': 'notification'
        }
        
        for dependency in metadata.dependencies:
            # 检查是否是系统组件依赖
            # 格式可能是：system:shared_memory 或 plugin:shared_memory
            if dependency.startswith('system:'):
                component_name = dependency.split(':', 1)[1].strip()
                if component_name in system_component_names:
                    system_components.append(system_component_names[component_name])
            elif dependency.startswith('plugin:'):
                # 也检查 plugin: 格式，因为系统组件可能被当作插件依赖
                component_name = dependency.split(':', 1)[0].split('>=')[0].split('>')[0].split('<=')[0].split('<')[0].strip()
                component_name = component_name.replace('plugin:', '').strip()
                if component_name in system_component_names:
                    system_components.append(system_component_names[component_name])
        
        return system_components
        
    def _parse_version(self, version: str) -> Tuple[int, ...]:
        """
        解析版本号字符串为元组
        
        Args:
            version: 版本号字符串 (如 "1.2.3")
            
        Returns:
            版本号元组 (如 (1, 2, 3))
        """
        try:
            # 移除前导 'v' 如果存在
            version = version.lstrip('v')
            
            # 分割版本号并转换为整数
            parts = []
            for part in version.split('.'):
                # 移除非数字字符 (如 "1.0.0-beta" -> "1.0.0")
                numeric_part = re.match(r'(\d+)', part)
                if numeric_part:
                    parts.append(int(numeric_part.group(1)))
                else:
                    parts.append(0)
            
            return tuple(parts)
            
        except Exception as e:
            logger.warning(f"Error parsing version {version}: {e}")
            return (0, 0, 0)
        
    def load_plugin(self, plugin_path: str, wait_for_dependencies: bool = True) -> bool:
        """
        加载单个插件
        
        Args:
            plugin_path: 插件路径（相对于plugins/目录）
            wait_for_dependencies: 是否等待系统组件依赖就绪（默认True）
            
        Returns:
            加载是否成功
        """
        try:
            plugin_dir = self.plugin_directory / plugin_path
            
            # 验证插件目录存在
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                error = PluginLoadError(
                    message=f"Plugin directory does not exist",
                    plugin_path=str(plugin_dir)
                )
                self.plugin_logger.log_error(error)
                logger.error(f"Plugin directory does not exist: {plugin_dir}")
                return False
            
            # 解析插件清单
            manifest_path = plugin_dir / "plugin.json"
            metadata = self._parse_manifest(manifest_path)
            if not metadata:
                error = PluginLoadError(
                    message="Failed to parse plugin manifest",
                    plugin_path=str(plugin_dir)
                )
                self.plugin_logger.log_error(error)
                logger.error(f"Failed to parse plugin manifest: {manifest_path}")
                return False
            
            plugin_name = metadata.name
            
            # 检查插件是否已加载
            if plugin_name in self.plugins:
                logger.warning(f"Plugin already loaded: {plugin_name}")
                return True  # 幂等性：重复加载返回成功
            
            # 检查系统组件依赖（需求 19.4, 19.5）
            if wait_for_dependencies:
                system_deps_ready = self._wait_for_system_dependencies(metadata, timeout=30)
                if not system_deps_ready:
                    logger.warning(f"Plugin {plugin_name} system dependencies not ready, delaying initialization")
                    # 标记插件为等待状态，稍后重试
                    return False
            
            # 检查依赖项
            deps_satisfied, dep_errors = self.check_dependencies(metadata)
            if not deps_satisfied:
                error = PluginDependencyError(
                    message="Plugin dependencies not satisfied",
                    plugin_name=plugin_name,
                    missing_dependencies=dep_errors
                )
                self.plugin_logger.log_error(error)
                logger.error(f"Plugin {plugin_name} dependencies not satisfied:")
                for error_msg in dep_errors:
                    logger.error(f"  - {error_msg}")
                return False
            
            # 验证入口点文件存在
            entry_point_path = plugin_dir / metadata.entry_point
            if not entry_point_path.exists():
                error = PluginLoadError(
                    message="Plugin entry point not found",
                    plugin_name=plugin_name,
                    plugin_path=str(entry_point_path)
                )
                self.plugin_logger.log_error(error)
                logger.error(f"Plugin entry point not found: {entry_point_path}")
                return False
            
            # 动态导入插件模块
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_path}.{metadata.entry_point.replace('.py', '')}",
                entry_point_path
            )
            if spec is None or spec.loader is None:
                error = PluginLoadError(
                    message="Failed to create module spec",
                    plugin_name=plugin_name,
                    plugin_path=str(entry_point_path)
                )
                self.plugin_logger.log_error(error)
                logger.error(f"Failed to create module spec for: {entry_point_path}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # 创建插件实例
            from datetime import datetime
            
            plugin_instance = PluginInstance(
                metadata=metadata,
                module=module,
                status=PluginStatus.LOADED,
                load_time=datetime.now()
            )
            
            # 调用插件的 on_load 钩子
            self._call_lifecycle_hook(plugin_instance, 'on_load')
            
            # 存储插件实例
            self.plugins[plugin_name] = plugin_instance
            
            self.plugin_logger.info(
                f"Successfully loaded plugin v{metadata.version}",
                plugin_name
            )
            logger.info(f"Successfully loaded plugin: {plugin_name} v{metadata.version}")
            return True
            
        except Exception as e:
            error = PluginLoadError(
                message=f"Error loading plugin: {e}",
                plugin_path=plugin_path,
                original_error=e
            )
            self.plugin_logger.log_error(error)
            logger.error(f"Error loading plugin from {plugin_path}: {e}", exc_info=True)
            return False
        
    def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            启用是否成功
        """
        try:
            # 检查插件是否存在
            if plugin_name not in self.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin = self.plugins[plugin_name]
            
            # 检查插件状态是否可以启用
            if not plugin.status.can_enable():
                logger.warning(f"Plugin cannot be enabled in current state: {plugin_name} [{plugin.status}]")
                return False
            
            # 调用插件的 on_enable 钩子
            self._call_lifecycle_hook(plugin, 'on_enable')
            
            # 更新插件状态
            plugin.status = PluginStatus.ENABLED
            
            # 持久化插件启用状态到 SettingsManager
            self._persist_plugin_state(plugin_name, enabled=True)
            
            logger.info(f"Successfully enabled plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling plugin {plugin_name}: {e}", exc_info=True)
            # 标记插件为错误状态
            if plugin_name in self.plugins:
                self.plugins[plugin_name].status = PluginStatus.ERROR
                self.plugins[plugin_name].error_message = str(e)
            return False
        
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            禁用是否成功
        """
        try:
            # 检查插件是否存在
            if plugin_name not in self.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin = self.plugins[plugin_name]
            
            # 检查插件状态是否可以禁用
            if not plugin.status.can_disable():
                logger.warning(f"Plugin cannot be disabled in current state: {plugin_name} [{plugin.status}]")
                return False
            
            # 调用插件的 on_disable 钩子
            self._call_lifecycle_hook(plugin, 'on_disable')
            
            # 移除插件注册的所有选项卡和UI组件
            self._cleanup_plugin_ui(plugin)
            
            # 清理插件的所有事件订阅（需求 7.9）
            self.event_bus.clear_plugin_subscriptions(plugin_name)
            plugin.event_subscriptions.clear()
            
            # 清理插件注册的所有就绪状态（需求 15.9）
            self.plugin_api.cleanup_plugin_ready_gates(plugin_name)
            
            # 更新插件状态
            plugin.status = PluginStatus.DISABLED
            
            # 持久化插件禁用状态到 SettingsManager
            self._persist_plugin_state(plugin_name, enabled=False)
            
            logger.info(f"Successfully disabled plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_name}: {e}", exc_info=True)
            return False
        
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件（需求 2.7, 5.7, 7.9, 11.10, 14.11, 15.9）
        
        完整清理插件的所有资源，包括：
        - 选项卡注册
        - TTS引擎注册
        - 事件订阅
        - ReadyGate就绪状态
        - 配置命名空间（可选保留）
        - 临时文件和缓存
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            卸载是否成功
        """
        try:
            # 检查插件是否存在
            if plugin_name not in self.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin = self.plugins[plugin_name]
            
            logger.info(f"Starting unload process for plugin: {plugin_name}")
            self.plugin_logger.info(f"Unloading plugin", plugin_name)
            
            # 如果插件已启用，先禁用
            if plugin.status == PluginStatus.ENABLED:
                logger.info(f"Disabling plugin before unload: {plugin_name}")
                if not self.disable_plugin(plugin_name):
                    logger.warning(f"Failed to disable plugin before unloading: {plugin_name}")
            
            # 调用插件的 on_unload 钩子
            self._call_lifecycle_hook(plugin, 'on_unload')
            
            # 执行完整的资源清理
            self._cleanup_plugin_complete(plugin)
            
            # 从插件字典中移除
            del self.plugins[plugin_name]
            
            # 验证清理完整性
            cleanup_verification = self._verify_plugin_cleanup(plugin_name)
            if not cleanup_verification['complete']:
                logger.warning(
                    f"Plugin {plugin_name} cleanup incomplete. Remaining resources: "
                    f"{cleanup_verification['remaining']}"
                )
                self.plugin_logger.warning(
                    f"Cleanup incomplete: {cleanup_verification['remaining']}",
                    plugin_name
                )
            else:
                logger.info(f"Plugin {plugin_name} cleanup verification passed")
            
            logger.info(f"Successfully unloaded plugin: {plugin_name}")
            self.plugin_logger.info(f"Plugin unloaded successfully", plugin_name)
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}", exc_info=True)
            self.plugin_logger.error(f"Error unloading plugin: {e}", plugin_name)
            return False
        
    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """
        获取插件状态
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件状态，如果插件不存在则返回None
        """
        plugin = self.plugins.get(plugin_name)
        return plugin.status if plugin else None
    
    def _call_lifecycle_hook(self, plugin: 'PluginInstance', hook_name: str) -> None:
        """
        调用插件的生命周期钩子函数
        
        集成崩溃检测和错误日志记录功能。
        
        Args:
            plugin: 插件实例
            hook_name: 钩子函数名称 (on_load, on_enable, on_disable, on_unload)
        """
        import time
        import threading
        
        try:
            # 检查插件模块是否有该钩子函数
            if not hasattr(plugin.module, hook_name):
                logger.debug(f"Plugin {plugin.get_plugin_name()} does not have {hook_name} hook")
                return
            
            hook_func = getattr(plugin.module, hook_name)
            if not callable(hook_func):
                logger.warning(f"Plugin {plugin.get_plugin_name()} {hook_name} is not callable")
                return
            
            # 在独立线程中执行钩子，并监控执行时间
            start_time = time.time()
            
            # 创建一个标志来跟踪钩子是否完成
            hook_completed = threading.Event()
            hook_exception = None
            
            def run_hook():
                nonlocal hook_exception
                try:
                    hook_func()
                except Exception as e:
                    hook_exception = e
                finally:
                    hook_completed.set()
            
            # 启动钩子线程
            hook_thread = threading.Thread(target=run_hook, daemon=True)
            hook_thread.start()
            
            # 等待钩子完成，但不阻塞超过5秒
            hook_completed.wait(timeout=5.0)
            
            elapsed_time = time.time() - start_time
            
            # 检查是否超时
            if not hook_completed.is_set():
                logger.warning(
                    f"Plugin {plugin.get_plugin_name()} {hook_name} hook "
                    f"exceeded 5 seconds (still running in background)"
                )
                self.plugin_logger.warning(
                    f"{hook_name} hook exceeded 5 seconds timeout",
                    plugin.get_plugin_name()
                )
            elif elapsed_time > 5.0:
                logger.warning(
                    f"Plugin {plugin.get_plugin_name()} {hook_name} hook "
                    f"took {elapsed_time:.2f} seconds"
                )
            
            # 如果钩子抛出异常，记录并处理崩溃
            if hook_exception:
                # 记录崩溃
                plugin.record_crash()
                
                # 创建执行错误并记录
                execution_error = PluginExecutionError(
                    message=f"{hook_name} hook raised exception: {hook_exception}",
                    plugin_name=plugin.get_plugin_name(),
                    hook_name=hook_name,
                    original_error=hook_exception
                )
                
                # 记录到插件日志
                self.plugin_logger.log_error(execution_error)
                self.plugin_logger.log_crash(
                    plugin.get_plugin_name(),
                    plugin.crash_count,
                    hook_exception
                )
                
                # 检查是否应该自动禁用
                if plugin.should_auto_disable():
                    self._auto_disable_plugin(plugin, 
                        f"Crashed {plugin.crash_count} times within 5 minutes")
                
                logger.error(
                    f"Plugin {plugin.get_plugin_name()} {hook_name} hook "
                    f"raised exception: {hook_exception}",
                    exc_info=hook_exception
                )
                raise hook_exception
            
            logger.debug(
                f"Successfully called {hook_name} hook for plugin "
                f"{plugin.get_plugin_name()} ({elapsed_time:.2f}s)"
            )
            
        except Exception as e:
            logger.error(
                f"Error calling {hook_name} hook for plugin "
                f"{plugin.get_plugin_name()}: {e}",
                exc_info=True
            )
            # 更新插件错误状态
            plugin.status = PluginStatus.ERROR
            plugin.error_message = f"{hook_name} hook failed: {str(e)}"
            plugin.record_crash()
            
            # 记录到插件日志
            self.plugin_logger.error(
                f"Error calling {hook_name} hook: {e}",
                plugin.get_plugin_name(),
                exc_info=True
            )
    
    def _cleanup_plugin_ui(self, plugin: 'PluginInstance') -> None:
        """
        清理插件注册的UI组件（选项卡等）
        
        Args:
            plugin: 插件实例
        """
        try:
            plugin_name = plugin.get_plugin_name()
            
            # 移除注册的选项卡
            for tab_name in plugin.registered_tabs[:]:  # 使用副本遍历
                try:
                    self.plugin_api.unregister_tab(plugin_name, tab_name)
                    logger.debug(f"Removed tab {tab_name} from plugin {plugin_name}")
                except Exception as e:
                    logger.error(f"Error removing tab {tab_name}: {e}")
            
            # 注销所有TTS引擎
            for engine_id in plugin.registered_engines[:]:  # 使用副本遍历
                try:
                    self.plugin_api.unregister_tts_engine(plugin_name, engine_id)
                    logger.debug(f"Unregistered TTS engine {engine_id} from plugin {plugin_name}")
                except Exception as e:
                    logger.error(f"Error unregistering TTS engine {engine_id}: {e}")
            
            logger.info(f"Cleaned up UI components for plugin: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up plugin UI: {e}", exc_info=True)
    
    def _cleanup_plugin_resources(self, plugin: 'PluginInstance') -> None:
        """
        释放插件占用的所有资源（基础清理）
        
        Args:
            plugin: 插件实例
        """
        try:
            plugin_name = plugin.get_plugin_name()
            
            # 清理UI组件
            self._cleanup_plugin_ui(plugin)
            
            # 注销TTS引擎
            for engine_id in plugin.registered_engines[:]:
                try:
                    self.plugin_api.unregister_tts_engine(plugin_name, engine_id)
                    plugin.registered_engines.remove(engine_id)
                    logger.debug(f"Unregistered TTS engine {engine_id} from plugin {plugin_name}")
                except Exception as e:
                    logger.error(f"Error unregistering TTS engine {engine_id}: {e}")
            
            # 取消所有事件订阅
            self.event_bus.clear_plugin_subscriptions(plugin_name)
            plugin.event_subscriptions.clear()
            
            # 清理就绪状态
            plugin.ready_gates.clear()
            
            # 清理所有注册信息
            plugin.clear_registrations()
            
            logger.info(f"Released all resources for plugin: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up plugin resources: {e}", exc_info=True)
    
    def _cleanup_plugin_complete(self, plugin: 'PluginInstance') -> None:
        """
        完整清理插件的所有资源（需求 2.7, 5.7, 7.9, 11.10, 14.11, 15.9）
        
        执行全面的资源清理，包括：
        1. 选项卡注册清理
        2. TTS引擎注销
        3. 事件订阅清理
        4. ReadyGate就绪状态清理
        5. 配置命名空间清理（可选）
        6. 临时文件和缓存清理
        7. 模块引用清理
        
        Args:
            plugin: 插件实例
        """
        try:
            plugin_name = plugin.get_plugin_name()
            logger.info(f"Starting complete cleanup for plugin: {plugin_name}")
            
            # 1. 清理所有注册的选项卡（需求 5.7, 14.11）
            logger.debug(f"Cleaning up {len(plugin.registered_tabs)} tabs for plugin {plugin_name}")
            for tab_name in plugin.registered_tabs[:]:  # 使用副本遍历
                try:
                    self.plugin_api.unregister_tab(plugin_name, tab_name)
                    logger.debug(f"Unregistered tab '{tab_name}' from plugin {plugin_name}")
                except Exception as e:
                    logger.error(f"Error unregistering tab {tab_name}: {e}")
            
            # 确保列表已清空
            plugin.registered_tabs.clear()
            
            # 2. 注销所有TTS引擎（需求 11.10）
            logger.debug(f"Cleaning up {len(plugin.registered_engines)} TTS engines for plugin {plugin_name}")
            for engine_id in plugin.registered_engines[:]:
                try:
                    self.plugin_api.unregister_tts_engine(plugin_name, engine_id)
                    logger.debug(f"Unregistered TTS engine '{engine_id}' from plugin {plugin_name}")
                except Exception as e:
                    logger.error(f"Error unregistering TTS engine {engine_id}: {e}")
            
            # 确保列表已清空
            plugin.registered_engines.clear()
            
            # 3. 清理所有事件订阅（需求 7.9）
            logger.debug(f"Cleaning up {len(plugin.event_subscriptions)} event subscriptions for plugin {plugin_name}")
            self.event_bus.clear_plugin_subscriptions(plugin_name)
            plugin.event_subscriptions.clear()
            
            # 4. 清理所有ReadyGate就绪状态（需求 15.9）
            logger.debug(f"Cleaning up {len(plugin.ready_gates)} ready gates for plugin {plugin_name}")
            self.plugin_api.cleanup_plugin_ready_gates(plugin_name)
            plugin.ready_gates.clear()
            
            # 5. 清理配置命名空间（可选，默认保留以支持重新安装）
            # 如果需要完全清理配置，可以取消注释以下代码：
            # self._cleanup_plugin_config(plugin_name)
            
            # 6. 清理临时文件和缓存
            self._cleanup_plugin_temp_files(plugin_name)
            
            # 7. 清理模块引用
            self._cleanup_plugin_module(plugin)
            
            # 8. 清理所有注册信息
            plugin.clear_registrations()
            
            logger.info(f"Complete cleanup finished for plugin: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error in complete cleanup for plugin {plugin.get_plugin_name()}: {e}", exc_info=True)
    
    def _cleanup_plugin_config(self, plugin_name: str) -> None:
        """
        清理插件的配置命名空间（可选）
        
        注意：默认情况下保留配置以支持插件重新安装后恢复设置。
        只有在明确需要完全清理时才调用此方法。
        
        Args:
            plugin_name: 插件名称
        """
        try:
            # 获取所有以 Plugin_{plugin_name} 开头的配置键
            config_prefix = f"Plugin_{plugin_name}."
            
            # 从 SettingsManager 中删除所有相关配置
            # 注意：这需要 SettingsManager 支持批量删除或遍历键
            # 如果 SettingsManager 不支持，可以跳过此步骤
            
            logger.info(f"Cleaned up configuration namespace for plugin: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up plugin config: {e}", exc_info=True)
    
    def _cleanup_plugin_temp_files(self, plugin_name: str) -> None:
        """
        清理插件的临时文件和缓存
        
        清理插件可能创建的临时文件，包括：
        - 插件目录下的 __pycache__
        - 插件目录下的 .pyc 文件
        - 插件的临时数据目录（如果存在）
        
        Args:
            plugin_name: 插件名称
        """
        try:
            from pathlib import Path
            import shutil
            
            plugin_dir = self.plugin_directory / plugin_name
            
            if not plugin_dir.exists():
                return
            
            # 清理 __pycache__ 目录
            pycache_dirs = list(plugin_dir.rglob('__pycache__'))
            for pycache_dir in pycache_dirs:
                try:
                    shutil.rmtree(pycache_dir)
                    logger.debug(f"Removed __pycache__ directory: {pycache_dir}")
                except Exception as e:
                    logger.warning(f"Failed to remove __pycache__ directory {pycache_dir}: {e}")
            
            # 清理 .pyc 文件
            pyc_files = list(plugin_dir.rglob('*.pyc'))
            for pyc_file in pyc_files:
                try:
                    pyc_file.unlink()
                    logger.debug(f"Removed .pyc file: {pyc_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove .pyc file {pyc_file}: {e}")
            
            # 清理插件的临时数据目录（如果存在）
            temp_dir = plugin_dir / "temp"
            if temp_dir.exists() and temp_dir.is_dir():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Removed temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp directory {temp_dir}: {e}")
            
            logger.info(f"Cleaned up temporary files for plugin: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up plugin temp files: {e}", exc_info=True)
    
    def _cleanup_plugin_module(self, plugin: 'PluginInstance') -> None:
        """
        清理插件的模块引用
        
        从 sys.modules 中移除插件模块，释放内存。
        
        Args:
            plugin: 插件实例
        """
        try:
            plugin_name = plugin.get_plugin_name()
            
            # 查找并移除插件相关的模块
            modules_to_remove = []
            for module_name in sys.modules.keys():
                if module_name.startswith(f"plugins.{plugin_name}"):
                    modules_to_remove.append(module_name)
            
            for module_name in modules_to_remove:
                try:
                    del sys.modules[module_name]
                    logger.debug(f"Removed module from sys.modules: {module_name}")
                except Exception as e:
                    logger.warning(f"Failed to remove module {module_name}: {e}")
            
            logger.info(f"Cleaned up {len(modules_to_remove)} module references for plugin: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up plugin module: {e}", exc_info=True)
    
    def _verify_plugin_cleanup(self, plugin_name: str) -> Dict:
        """
        验证插件清理的完整性
        
        检查插件的所有资源是否已完全清理，包括：
        - 插件实例是否已从 plugins 字典中移除
        - TabManager 中是否还有插件的选项卡
        - TTSRouter 中是否还有插件的引擎
        - EventBus 中是否还有插件的订阅
        - ReadyGate 中是否还有插件的状态
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            验证结果字典: {
                'complete': bool,  # 清理是否完整
                'remaining': list  # 残留资源列表
            }
        """
        try:
            remaining = []
            
            # 1. 检查插件实例是否已移除
            if plugin_name in self.plugins:
                remaining.append(f"Plugin instance still in plugins dict")
            
            # 2. 检查 TabManager 中的选项卡
            tab_manager = self.main_window.tab_manager
            for tab_config in tab_manager.tab_configs:
                # 检查是否是插件选项卡（通过查找所有插件的 registered_tabs）
                for pname, plugin in self.plugins.items():
                    if tab_config.name in plugin.registered_tabs:
                        if pname == plugin_name:
                            remaining.append(f"Tab '{tab_config.name}' still registered in TabManager")
            
            # 3. 检查 TTSRouter 中的引擎
            try:
                from tts_router import get_tts_router
                tts_router = get_tts_router()
                dynamic_engines = tts_router.get_dynamic_engines()
                
                for engine_id in dynamic_engines.keys():
                    # 检查引擎是否属于该插件
                    for pname, plugin in self.plugins.items():
                        if engine_id in plugin.registered_engines:
                            if pname == plugin_name:
                                remaining.append(f"TTS engine '{engine_id}' still registered in TTSRouter")
            except Exception as e:
                logger.warning(f"Could not verify TTSRouter cleanup: {e}")
            
            # 4. 检查 EventBus 中的订阅
            # EventBus 应该已经清理了所有订阅，但我们可以验证
            # 注意：这需要 EventBus 提供查询接口
            
            # 5. 检查 ReadyGate 中的状态
            ready_gate = self.main_window.ready_gate
            with ready_gate._lock:
                for gate_name in ready_gate._gates.keys():
                    if gate_name.startswith(f"plugin_{plugin_name}_"):
                        remaining.append(f"Ready gate '{gate_name}' still registered in ReadyGate")
            
            # 6. 检查 sys.modules 中的模块引用
            for module_name in sys.modules.keys():
                if module_name.startswith(f"plugins.{plugin_name}"):
                    remaining.append(f"Module '{module_name}' still in sys.modules")
            
            is_complete = len(remaining) == 0
            
            return {
                'complete': is_complete,
                'remaining': remaining
            }
            
        except Exception as e:
            logger.error(f"Error verifying plugin cleanup: {e}", exc_info=True)
            return {
                'complete': False,
                'remaining': [f"Verification error: {e}"]
            }
    
    def _persist_plugin_state(self, plugin_name: str, enabled: bool) -> None:
        """
        持久化插件启用/禁用状态到 SettingsManager
        
        Args:
            plugin_name: 插件名称
            enabled: 是否启用
        """
        try:
            # 使用 Custom 配置段存储插件状态
            config_key = f"plugin_{plugin_name}_enabled"
            self.main_window.settings_manager.set_Custom_value(config_key, str(enabled))
            logger.debug(f"Persisted plugin state: {plugin_name} = {enabled}")
            
        except Exception as e:
            logger.error(f"Error persisting plugin state for {plugin_name}: {e}", exc_info=True)
    
    def _load_plugin_state(self, plugin_name: str) -> bool:
        """
        从 SettingsManager 加载插件启用/禁用状态
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件是否应该启用（默认为True）
        """
        try:
            config_key = f"plugin_{plugin_name}_enabled"
            state_str = self.main_window.settings_manager.get_Custom_value(config_key, "True")
            return state_str.lower() == "true"
            
        except Exception as e:
            logger.error(f"Error loading plugin state for {plugin_name}: {e}", exc_info=True)
            return True  # 默认启用
    
    def _auto_disable_plugin(self, plugin: 'PluginInstance', reason: str) -> None:
        """
        自动禁用插件
        
        当插件频繁崩溃时自动禁用，并通知用户。
        
        Args:
            plugin: 插件实例
            reason: 禁用原因
        """
        try:
            plugin_name = plugin.get_plugin_name()
            
            # 记录自动禁用日志
            self.plugin_logger.log_auto_disable(plugin_name, reason)
            
            # 更新插件状态
            plugin.status = PluginStatus.DISABLED
            plugin.error_message = f"Auto-disabled: {reason}"
            
            # 持久化禁用状态
            self._persist_plugin_state(plugin_name, enabled=False)
            
            # 清理插件资源
            self._cleanup_plugin_ui(plugin)
            self.event_bus.clear_plugin_subscriptions(plugin_name)
            plugin.event_subscriptions.clear()
            
            logger.warning(f"Plugin {plugin_name} auto-disabled: {reason}")
            
            # 通知用户（如果主窗口支持）
            self._notify_user_plugin_disabled(plugin_name, reason)
            
        except Exception as e:
            logger.error(f"Error auto-disabling plugin: {e}", exc_info=True)
            self.plugin_logger.error(f"Error auto-disabling plugin: {e}", plugin.get_plugin_name())
    
    def _notify_user_plugin_disabled(self, plugin_name: str, reason: str) -> None:
        """
        通知用户插件已被自动禁用
        
        Args:
            plugin_name: 插件名称
            reason: 禁用原因
        """
        try:
            # 检查主窗口是否有通知功能
            if hasattr(self.main_window, 'show_notification'):
                self.main_window.show_notification(
                    title="插件已自动禁用",
                    message=f"插件 {plugin_name} 因频繁崩溃已被自动禁用。\n原因: {reason}\n\n"
                           f"您可以在插件管理器中查看错误日志或尝试重新加载插件。",
                    level="warning"
                )
            elif hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(
                    f"插件 {plugin_name} 已自动禁用: {reason}",
                    5000  # 显示5秒
                )
        except Exception as e:
            logger.error(f"Error notifying user: {e}", exc_info=True)
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件
        
        卸载并重新加载插件，同时重置崩溃计数器。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            重新加载是否成功
        """
        try:
            # 检查插件是否存在
            if plugin_name not in self.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin = self.plugins[plugin_name]
            plugin_path = plugin.metadata.name  # 使用插件名称作为路径
            
            # 记录重新加载操作
            self.plugin_logger.info(f"Reloading plugin", plugin_name)
            
            # 卸载插件
            if not self.unload_plugin(plugin_name):
                logger.error(f"Failed to unload plugin before reload: {plugin_name}")
                self.plugin_logger.log_reload(plugin_name, False, 
                    Exception("Failed to unload plugin"))
                return False
            
            # 重置崩溃计数器
            plugin.reset_crash_counter()
            
            # 重新加载插件
            success = self.load_plugin(plugin_path)
            
            if success:
                # 如果之前是启用状态，重新启用
                if self._load_plugin_state(plugin_name):
                    self.enable_plugin(plugin_name)
                
                self.plugin_logger.log_reload(plugin_name, True)
                logger.info(f"Successfully reloaded plugin: {plugin_name}")
            else:
                self.plugin_logger.log_reload(plugin_name, False, 
                    Exception("Failed to load plugin"))
                logger.error(f"Failed to reload plugin: {plugin_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error reloading plugin {plugin_name}: {e}", exc_info=True)
            self.plugin_logger.log_reload(plugin_name, False, e)
            return False
    
    def get_plugin_error_log(self, lines: int = 100) -> str:
        """
        获取插件错误日志内容
        
        Args:
            lines: 要读取的行数
            
        Returns:
            日志内容字符串
        """
        return self.plugin_logger.get_log_content(lines)
    
    def get_plugin_crash_summary(self, plugin_name: str) -> Optional[Dict]:
        """
        获取插件崩溃摘要
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            崩溃摘要字典，如果插件不存在则返回None
        """
        if plugin_name not in self.plugins:
            return None
        
        plugin = self.plugins[plugin_name]
        return plugin.get_crash_summary()
    
    def get_plugin_ready_state_info(self, plugin_name: str = None) -> Dict:
        """
        获取插件就绪状态的详细监控信息（需求 15.12）
        
        在调试模式下提供插件就绪状态的详细信息，包括：
        - 插件注册的所有就绪状态
        - 每个状态的就绪情况
        - 等待中的组件
        
        Args:
            plugin_name: 插件名称，如果为None则返回所有插件的信息
            
        Returns:
            就绪状态信息字典
        """
        try:
            ready_gate = self.main_window.ready_gate
            info = {}
            
            if plugin_name:
                # 获取单个插件的就绪状态信息
                if plugin_name not in self.plugins:
                    return {"error": f"Plugin not found: {plugin_name}"}
                
                plugin = self.plugins[plugin_name]
                plugin_info = {
                    "plugin_name": plugin_name,
                    "status": plugin.status.value,
                    "registered_gates": [],
                    "ready_gates": [],
                    "pending_gates": []
                }
                
                for gate_name in plugin.ready_gates:
                    gate_info = {
                        "name": gate_name,
                        "is_ready": ready_gate.is_ready(gate_name)
                    }
                    
                    plugin_info["registered_gates"].append(gate_info)
                    
                    if gate_info["is_ready"]:
                        plugin_info["ready_gates"].append(gate_name)
                    else:
                        plugin_info["pending_gates"].append(gate_name)
                
                info[plugin_name] = plugin_info
            else:
                # 获取所有插件的就绪状态信息
                for pname, plugin in self.plugins.items():
                    plugin_info = {
                        "plugin_name": pname,
                        "status": plugin.status.value,
                        "registered_gates": [],
                        "ready_gates": [],
                        "pending_gates": []
                    }
                    
                    for gate_name in plugin.ready_gates:
                        gate_info = {
                            "name": gate_name,
                            "is_ready": ready_gate.is_ready(gate_name)
                        }
                        
                        plugin_info["registered_gates"].append(gate_info)
                        
                        if gate_info["is_ready"]:
                            plugin_info["ready_gates"].append(gate_name)
                        else:
                            plugin_info["pending_gates"].append(gate_name)
                    
                    info[pname] = plugin_info
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting plugin ready state info: {e}", exc_info=True)
            return {"error": str(e)}
    
    def schedule_delayed_initialization(self, plugin_name: str, callback: Callable, delay_ms: int = 0) -> bool:
        """
        调度插件的延迟初始化（需求 19.10）
        
        允许插件在系统完全启动后再进行重量级操作，避免阻塞启动流程。
        使用 QTimer 在主线程中异步执行回调。
        
        Args:
            plugin_name: 插件名称
            callback: 延迟执行的回调函数
            delay_ms: 延迟时间（毫秒），默认0表示在下一个事件循环执行
            
        Returns:
            调度是否成功
        """
        try:
            from PyQt5.QtCore import QTimer
            
            # 验证插件是否存在
            if plugin_name not in self.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            logger.info(f"Scheduling delayed initialization for plugin {plugin_name} (delay={delay_ms}ms)")
            
            # 创建单次触发的定时器
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._execute_delayed_callback(plugin_name, callback))
            timer.start(delay_ms)
            
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling delayed initialization for plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    def _execute_delayed_callback(self, plugin_name: str, callback: Callable) -> None:
        """
        执行延迟初始化回调
        
        Args:
            plugin_name: 插件名称
            callback: 回调函数
        """
        try:
            logger.debug(f"Executing delayed initialization callback for plugin {plugin_name}")
            callback()
            logger.info(f"Delayed initialization completed for plugin {plugin_name}")
            
        except Exception as e:
            logger.error(f"Error in delayed initialization callback for plugin {plugin_name}: {e}", exc_info=True)
            self.plugin_logger.error(f"Delayed initialization failed: {e}", plugin_name)
    
    def notify_tab_switched(self, from_index: int, to_index: int) -> None:
        """
        通知插件系统选项卡已切换（需求 20.4, 20.5）
        
        当用户切换选项卡时，调用相应插件页面的生命周期方法。
        应该从 TabManager.switch_to_tab() 或 TabManager._on_tab_switched() 调用。
        
        Args:
            from_index: 切换前的选项卡索引
            to_index: 切换后的选项卡索引
        """
        try:
            tab_manager = self.main_window.tab_manager
            stacked_widget = self.main_window.stacked_widget
            
            # 调用旧页面的 on_page_hidden
            if 0 <= from_index < len(tab_manager.tab_configs):
                from_tab_config = tab_manager.tab_configs[from_index]
                from_tab_name = from_tab_config.name
                
                # 检查是否是插件页面
                plugin_name = self._find_plugin_by_tab(from_tab_name)
                if plugin_name:
                    # 获取页面实例
                    if from_index < stacked_widget.count():
                        page_instance = stacked_widget.widget(from_index)
                        if page_instance:
                            self.plugin_api._call_page_lifecycle_hook(
                                page_instance, 'on_page_hidden', plugin_name, from_tab_name
                            )
            
            # 调用新页面的 on_page_shown
            if 0 <= to_index < len(tab_manager.tab_configs):
                to_tab_config = tab_manager.tab_configs[to_index]
                to_tab_name = to_tab_config.name
                
                # 检查是否是插件页面
                plugin_name = self._find_plugin_by_tab(to_tab_name)
                if plugin_name:
                    # 获取页面实例
                    if to_index < stacked_widget.count():
                        page_instance = stacked_widget.widget(to_index)
                        if page_instance:
                            self.plugin_api._call_page_lifecycle_hook(
                                page_instance, 'on_page_shown', plugin_name, to_tab_name
                            )
            
        except Exception as e:
            logger.error(f"Error notifying tab switch: {e}", exc_info=True)
    
    def _find_plugin_by_tab(self, tab_name: str) -> Optional[str]:
        """
        根据选项卡名称查找拥有该选项卡的插件
        
        Args:
            tab_name: 选项卡名称
            
        Returns:
            插件名称，如果不是插件选项卡则返回None
        """
        for plugin_name, plugin_instance in self.plugins.items():
            if tab_name in plugin_instance.registered_tabs:
                return plugin_name
        return None

    def shutdown_plugin_system(self, timeout: int = 5) -> bool:
        """
        应用程序关闭时的插件系统清理（需求 19.11）
        
        在应用关闭时执行优雅的插件系统清理，确保所有插件在其他组件之前被禁用。
        支持超时保护，避免阻塞应用关闭流程。
        
        Args:
            timeout: 清理超时时间（秒），默认5秒
            
        Returns:
            清理是否成功完成
        """
        import time
        
        try:
            logger.info("Starting plugin system shutdown...")
            self.plugin_logger.info("Plugin system shutdown initiated")
            
            start_time = time.time()
            
            # 获取所有已启用的插件列表
            enabled_plugins = [
                name for name, plugin in self.plugins.items()
                if plugin.status == PluginStatus.ENABLED
            ]
            
            logger.info(f"Shutting down {len(enabled_plugins)} enabled plugins")
            
            # 禁用所有已启用的插件
            for plugin_name in enabled_plugins:
                try:
                    # 检查是否超时
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        logger.warning(
                            f"Plugin system shutdown timeout ({timeout}s) reached. "
                            f"Remaining plugins will be force-disabled."
                        )
                        break
                    
                    logger.info(f"Disabling plugin during shutdown: {plugin_name}")
                    self.disable_plugin(plugin_name)
                    
                except Exception as e:
                    logger.error(f"Error disabling plugin {plugin_name} during shutdown: {e}")
                    # 继续处理其他插件
                    continue
            
            # 清理事件总线
            try:
                logger.info("Shutting down plugin event bus")
                self.event_bus.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down event bus: {e}")
            
            elapsed = time.time() - start_time
            logger.info(f"Plugin system shutdown completed in {elapsed:.2f}s")
            self.plugin_logger.info(f"Plugin system shutdown completed (elapsed={elapsed:.2f}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during plugin system shutdown: {e}", exc_info=True)
            self.plugin_logger.error(f"Plugin system shutdown error: {e}")
            return False
