"""
插件API - 为插件提供的统一接口

封装对主应用程序功能的访问，提供选项卡管理、TTS引擎管理、
事件系统、配置管理和资源管理等功能。
"""

from typing import Callable, Any, Optional
import logging


logger = logging.getLogger(__name__)


class PluginAPI:
    """插件API - 为插件提供的统一接口"""
    
    def __init__(self, plugin_manager):
        """
        初始化插件API
        
        Args:
            plugin_manager: 插件管理器实例
        """
        self.plugin_manager = plugin_manager
        # 处理测试环境中 main_window 为 None 的情况
        if plugin_manager.main_window is not None:
            self.settings_manager = plugin_manager.main_window.settings_manager
        else:
            # 测试环境：尝试创建 SettingsManager
            try:
                from misc_func import SettingsManager
                self.settings_manager = SettingsManager()
            except Exception:
                self.settings_manager = None
        self.event_bus = plugin_manager.event_bus  # 引用 PluginManager 的事件总线
        
    # 选项卡管理
    def register_tab(self, plugin_name: str, tab_name: str, 
                    display_name: str, widget_class, order: int = 999) -> bool:
        """
        注册插件选项卡（与 TabManager 的 register_tab_lazy 兼容）
        
        使用延迟加载机制，避免在应用启动时立即实例化插件页面。
        
        Args:
            plugin_name: 插件名称
            tab_name: 选项卡内部名称（唯一标识符）
            display_name: 选项卡显示名称
            widget_class: 选项卡页面类（必须继承自 QWidget）
            order: 选项卡排序位置（默认999，显示在最后）
            
        Returns:
            注册是否成功
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 验证选项卡名称唯一性
            tab_manager = self.plugin_manager.main_window.tab_manager
            for tab_config in tab_manager.tab_configs:
                if tab_config.name == tab_name:
                    logger.error(f"Tab name already exists: {tab_name}")
                    return False
            
            # 验证 widget_class 是否继承自 QWidget
            try:
                from PyQt5.QtWidgets import QWidget
                if not issubclass(widget_class, QWidget):
                    logger.error(f"Widget class must inherit from QWidget: {widget_class}")
                    return False
            except (ImportError, TypeError) as e:
                logger.error(f"Invalid widget class: {e}")
                return False
            
            # 创建 class_getter 函数用于延迟加载
            def class_getter():
                """延迟加载插件页面类（需求 20.3, 14.9）"""
                try:
                    # 实例化页面时设置插件上下文
                    page_instance = widget_class(self.plugin_manager.main_window)
                    
                    # 如果页面继承自 PluginPageBase，设置插件上下文
                    if hasattr(page_instance, 'set_plugin_context'):
                        page_instance.set_plugin_context(self, plugin_name)
                    
                    # 调用生命周期方法 on_page_created（需求 20.3）
                    if hasattr(page_instance, 'on_page_created'):
                        try:
                            page_instance.on_page_created()
                            logger.info(f"Plugin page '{tab_name}' created for plugin '{plugin_name}'")
                        except Exception as lifecycle_error:
                            logger.error(
                                f"Error in on_page_created for plugin '{plugin_name}', tab '{tab_name}': {lifecycle_error}",
                                exc_info=True
                            )
                            # 记录错误但继续，页面仍然可用
                            self.plugin_manager.plugin_logger.error(
                                f"on_page_created failed: {lifecycle_error}",
                                plugin_name
                            )
                    
                    # 开始监控页面内存使用（需求 20.9）
                    self._start_memory_monitoring(plugin_name, tab_name, page_instance)
                    
                    return page_instance.__class__
                except Exception as e:
                    logger.error(f"Error loading plugin page class: {e}", exc_info=True)
                    # 记录到插件日志（需求 14.9）
                    self.plugin_manager.plugin_logger.error(
                        f"Failed to load plugin page '{tab_name}': {e}",
                        plugin_name
                    )
                    # 返回一个错误页面类（需求 14.9）
                    return self._create_error_page_class(plugin_name, tab_name, e)
            
            # 使用 TabManager 的 register_tab_lazy 方法注册选项卡
            tab_manager.register_tab_lazy(tab_name, display_name, class_getter)
            
            # 记录到插件实例
            plugin_instance.registered_tabs.append(tab_name)
            
            # 持久化选项卡可见性配置到 SettingsManager
            self._persist_tab_visibility(tab_name, visible=True, order=order)
            
            logger.info(f"Successfully registered tab '{tab_name}' for plugin '{plugin_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error registering tab for plugin {plugin_name}: {e}", exc_info=True)
            return False
        
    def unregister_tab(self, plugin_name: str, tab_name: str) -> bool:
        """
        注销插件选项卡
        
        从 TabManager 中移除插件注册的选项卡，并清理相关配置。
        
        Args:
            plugin_name: 插件名称
            tab_name: 选项卡内部名称
            
        Returns:
            注销是否成功
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 验证选项卡是否由该插件注册
            if tab_name not in plugin_instance.registered_tabs:
                logger.warning(f"Tab '{tab_name}' not registered by plugin '{plugin_name}'")
                return False
            
            # 从 TabManager 中移除选项卡
            tab_manager = self.plugin_manager.main_window.tab_manager
            
            # 查找并移除选项卡配置
            tab_index = None
            for i, tab_config in enumerate(tab_manager.tab_configs):
                if tab_config.name == tab_name:
                    tab_index = i
                    break
            
            if tab_index is not None:
                # 移除选项卡配置
                tab_manager.tab_configs.pop(tab_index)
                
                # 移除选项卡按钮（如果已创建）
                if tab_index < len(tab_manager.tab_buttons):
                    button = tab_manager.tab_buttons.pop(tab_index)
                    button.deleteLater()
                
                # 移除选项卡页面（如果已创建）
                stacked_widget = self.plugin_manager.main_window.stacked_widget
                if tab_index < stacked_widget.count():
                    widget = stacked_widget.widget(tab_index)
                    stacked_widget.removeWidget(widget)
                    
                    # 调用页面销毁生命周期方法
                    if hasattr(widget, 'on_page_destroyed'):
                        try:
                            widget.on_page_destroyed()
                        except Exception as e:
                            logger.error(f"Error calling on_page_destroyed: {e}")
                    
                    widget.deleteLater()
                
                # 调整当前选项卡索引
                if tab_manager.current_tab_index >= tab_index:
                    tab_manager.current_tab_index = max(0, tab_manager.current_tab_index - 1)
            
            # 从插件实例中移除记录
            plugin_instance.registered_tabs.remove(tab_name)
            
            # 更新选项卡可见性配置
            self._persist_tab_visibility(tab_name, visible=False)
            
            logger.info(f"Successfully unregistered tab '{tab_name}' from plugin '{plugin_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering tab for plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    def _create_error_page_class(self, plugin_name: str, tab_name: str, error: Exception):
        """
        创建错误页面类，用于显示插件页面加载失败的信息
        
        Args:
            plugin_name: 插件名称
            tab_name: 选项卡名称
            error: 错误异常
            
        Returns:
            错误页面类
        """
        try:
            from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
            from PyQt5.QtCore import Qt
        except ImportError:
            # 如果无法导入 PyQt5，返回一个简单的类
            class ErrorPage:
                def __init__(self, parent=None):
                    pass
            return ErrorPage
        
        class PluginErrorPage(QWidget):
            """插件页面加载错误页面"""
            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                
                title_label = QLabel(f"插件页面加载失败")
                title_label.setAlignment(Qt.AlignCenter)
                title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: red;")
                layout.addWidget(title_label)
                
                info_label = QLabel(
                    f"插件: {plugin_name}\n"
                    f"选项卡: {tab_name}\n\n"
                    f"错误信息:\n{str(error)}"
                )
                info_label.setAlignment(Qt.AlignCenter)
                info_label.setWordWrap(True)
                layout.addWidget(info_label)
                
                layout.addStretch()
        
        return PluginErrorPage
    
    def _persist_tab_visibility(self, tab_name: str, visible: bool, order: int = 999) -> None:
        """
        持久化选项卡可见性和排序配置到 SettingsManager
        
        Args:
            tab_name: 选项卡名称
            visible: 是否可见
            order: 排序位置
        """
        try:
            # 保存可见性配置
            visibility_key = f"tab_visibility_{tab_name}"
            self.settings_manager.set_Custom_value(visibility_key, str(visible))
            
            # 保存排序配置
            order_key = f"tab_order_{tab_name}"
            self.settings_manager.set_Custom_value(order_key, str(order))
            
            logger.debug(f"Persisted tab config: {tab_name} (visible={visible}, order={order})")
            
        except Exception as e:
            logger.error(f"Error persisting tab visibility: {e}", exc_info=True)
        
    # TTS引擎管理
    def register_tts_engine(self, plugin_name: str, engine_id: str, 
                           engine_class) -> bool:
        """
        注册TTS引擎
        
        验证引擎类实现了 TTSEngineInterface 接口，并将引擎注册到 TTS_Router。
        
        Args:
            plugin_name: 插件名称
            engine_id: 引擎唯一标识符
            engine_class: 引擎类（必须实现 TTSEngineInterface）
            
        Returns:
            注册是否成功
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 验证引擎类实现了 TTSEngineInterface 接口
            from tts_engine_interface import TTSEngineInterface
            
            if not issubclass(engine_class, TTSEngineInterface):
                logger.error(f"Engine class must implement TTSEngineInterface: {engine_class}")
                return False
            
            # 实例化引擎以验证接口完整性
            try:
                engine_instance = engine_class()
            except Exception as e:
                logger.error(f"Failed to instantiate engine class: {e}", exc_info=True)
                return False
            
            # 验证必需的接口方法
            required_methods = ['synthesize', 'get_voices', 'get_engine_info']
            for method_name in required_methods:
                if not hasattr(engine_instance, method_name):
                    logger.error(f"Engine missing required method: {method_name}")
                    return False
                
                method = getattr(engine_instance, method_name)
                if not callable(method):
                    logger.error(f"Engine method is not callable: {method_name}")
                    return False
            
            # 测试 get_engine_info() 方法
            try:
                engine_info = engine_instance.get_engine_info()
                if not engine_info or not hasattr(engine_info, 'engine_id'):
                    logger.error("Engine get_engine_info() returned invalid data")
                    return False
            except Exception as e:
                logger.error(f"Engine get_engine_info() failed: {e}", exc_info=True)
                return False
            
            # 将引擎注册到 TTS_Router
            from tts_router import get_tts_router
            tts_router = get_tts_router()
            
            # 检查 TTS_Router 是否支持动态注册
            if not hasattr(tts_router, 'register_dynamic_engine'):
                logger.error("TTS_Router does not support dynamic engine registration")
                return False
            
            # 注册引擎到 TTS_Router
            if not tts_router.register_dynamic_engine(engine_id, engine_class):
                logger.error(f"Failed to register engine to TTS_Router: {engine_id}")
                return False
            
            # 记录到插件实例的 registered_engines 列表
            plugin_instance.registered_engines.append(engine_id)
            
            logger.info(f"Successfully registered TTS engine '{engine_id}' for plugin '{plugin_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error registering TTS engine for plugin {plugin_name}: {e}", exc_info=True)
            return False
        
    def unregister_tts_engine(self, plugin_name: str, engine_id: str) -> bool:
        """
        注销TTS引擎
        
        从 TTS_Router 中注销引擎，并从插件实例的 registered_engines 列表中移除。
        
        Args:
            plugin_name: 插件名称
            engine_id: 引擎唯一标识符
            
        Returns:
            注销是否成功
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 验证引擎是否由该插件注册
            if engine_id not in plugin_instance.registered_engines:
                logger.warning(f"Engine '{engine_id}' not registered by plugin '{plugin_name}'")
                return False
            
            # 从 TTS_Router 中注销引擎
            from tts_router import get_tts_router
            tts_router = get_tts_router()
            
            # 检查 TTS_Router 是否支持动态注销
            if not hasattr(tts_router, 'unregister_dynamic_engine'):
                logger.error("TTS_Router does not support dynamic engine unregistration")
                return False
            
            # 注销引擎
            if not tts_router.unregister_dynamic_engine(engine_id):
                logger.error(f"Failed to unregister engine from TTS_Router: {engine_id}")
                return False
            
            # 从插件实例的 registered_engines 列表中移除
            plugin_instance.registered_engines.remove(engine_id)
            
            logger.info(f"Successfully unregistered TTS engine '{engine_id}' from plugin '{plugin_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering TTS engine for plugin {plugin_name}: {e}", exc_info=True)
            return False
        
    # 事件系统
    def subscribe_event(self, plugin_name: str, event_type: str, 
                       callback: Callable) -> str:
        """
        订阅事件
        
        Args:
            plugin_name: 插件名称
            event_type: 事件类型（自动添加 plugin_ 前缀）
            callback: 回调函数，接收一个 dict 参数
            
        Returns:
            订阅ID，用于取消订阅
        """
        try:
            # 调用事件总线的订阅方法
            subscription_id = self.event_bus.subscribe(
                event_type=event_type,
                callback=callback,
                plugin_name=plugin_name
            )
            
            # 记录订阅到插件实例
            if plugin_name in self.plugin_manager.plugins:
                plugin_instance = self.plugin_manager.plugins[plugin_name]
                plugin_instance.event_subscriptions.append(subscription_id)
            
            logger.info(f"Plugin '{plugin_name}' subscribed to event '{event_type}' (subscription_id={subscription_id})")
            return subscription_id
            
        except Exception as e:
            logger.error(f"Error subscribing to event for plugin {plugin_name}: {e}", exc_info=True)
            raise
        
    def unsubscribe_event(self, plugin_name: str, subscription_id: str) -> bool:
        """
        取消订阅事件
        
        Args:
            plugin_name: 插件名称
            subscription_id: 订阅ID（由 subscribe_event 返回）
            
        Returns:
            取消订阅是否成功
        """
        try:
            # 调用事件总线的取消订阅方法
            success = self.event_bus.unsubscribe(subscription_id)
            
            # 从插件实例中移除订阅记录
            if success and plugin_name in self.plugin_manager.plugins:
                plugin_instance = self.plugin_manager.plugins[plugin_name]
                if subscription_id in plugin_instance.event_subscriptions:
                    plugin_instance.event_subscriptions.remove(subscription_id)
            
            if success:
                logger.info(f"Plugin '{plugin_name}' unsubscribed from event (subscription_id={subscription_id})")
            else:
                logger.warning(f"Failed to unsubscribe plugin '{plugin_name}' from event (subscription_id={subscription_id})")
                
            return success
            
        except Exception as e:
            logger.error(f"Error unsubscribing from event for plugin {plugin_name}: {e}", exc_info=True)
            return False
        
    def emit_plugin_event(self, plugin_name: str, event_type: str, 
                         data: dict) -> None:
        """
        发送插件事件
        
        Args:
            plugin_name: 插件名称
            event_type: 事件类型（自动添加 plugin_ 前缀）
            data: 事件数据
        """
        try:
            # 调用事件总线的发送方法
            self.event_bus.emit(event_type, data)
            logger.debug(f"Plugin '{plugin_name}' emitted event '{event_type}'")
            
        except Exception as e:
            logger.error(f"Error emitting event for plugin {plugin_name}: {e}", exc_info=True)
            raise
        
    # 配置管理
    def get_config(self, plugin_name: str, key: str, default=None) -> Any:
        """
        读取插件配置（带命名空间隔离）
        
        配置命名空间格式：Plugin_{plugin_name}.{key}
        
        Args:
            plugin_name: 插件名称
            key: 配置键
            default: 默认值
            
        Returns:
            配置值，如果不存在则返回默认值
        """
        try:
            # 构建带命名空间的配置键
            namespaced_key = self._build_config_key(plugin_name, key)
            
            # 从 SettingsManager 读取配置
            value_str = self.settings_manager.get_Custom_value(namespaced_key, None)
            
            # 如果配置不存在，返回默认值
            if value_str is None:
                logger.debug(f"Config key not found: {namespaced_key}, returning default: {default}")
                return default
            
            # 尝试反序列化配置值
            try:
                import json
                value = json.loads(value_str)
                logger.debug(f"Retrieved config: {namespaced_key} = {value}")
                return value
            except (json.JSONDecodeError, ValueError):
                # 如果不是JSON格式，直接返回字符串
                logger.debug(f"Retrieved config (string): {namespaced_key} = {value_str}")
                return value_str
                
        except Exception as e:
            logger.error(f"Error reading config for plugin {plugin_name}, key {key}: {e}", exc_info=True)
            return default
        
    def set_config(self, plugin_name: str, key: str, value: Any) -> bool:
        """
        保存插件配置（带命名空间隔离）
        
        配置命名空间格式：Plugin_{plugin_name}.{key}
        
        Args:
            plugin_name: 插件名称
            key: 配置键
            value: 配置值（支持 str, int, float, bool, dict, list, tuple, None）
            
        Returns:
            保存是否成功
        """
        try:
            # 验证配置键不与系统保留键冲突
            if not self._validate_config_key(key):
                logger.error(f"Invalid config key for plugin {plugin_name}: {key}")
                return False
            
            # 验证配置值类型
            if not self._validate_config_value(value):
                logger.error(f"Invalid config value type for plugin {plugin_name}, key {key}: {type(value)}")
                return False
            
            # 构建带命名空间的配置键
            namespaced_key = self._build_config_key(plugin_name, key)
            
            # 序列化配置值
            try:
                import json
                if value is None:
                    value_str = json.dumps(None)  # 序列化为 "null"
                elif isinstance(value, (dict, list, tuple)):
                    value_str = json.dumps(value, ensure_ascii=False)
                elif isinstance(value, (int, float, bool)):
                    value_str = json.dumps(value)
                else:
                    value_str = str(value)
            except Exception as e:
                logger.error(f"Error serializing config value: {e}")
                return False
            
            # 保存到 SettingsManager
            success = self.settings_manager.set_Custom_value(namespaced_key, value_str)
            
            if success:
                logger.info(f"Saved config: {namespaced_key} = {value_str}")
            else:
                logger.error(f"Failed to save config: {namespaced_key}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error saving config for plugin {plugin_name}, key {key}: {e}", exc_info=True)
            return False
    
    def _build_config_key(self, plugin_name: str, key: str) -> str:
        """
        构建带命名空间的配置键
        
        Args:
            plugin_name: 插件名称
            key: 配置键
            
        Returns:
            带命名空间的配置键 (格式: Plugin_{plugin_name}.{key})
        """
        return f"Plugin_{plugin_name}.{key}"
    
    def _validate_config_key(self, key: str) -> bool:
        """
        验证配置键是否有效（不与系统保留键冲突）
        
        Args:
            key: 配置键
            
        Returns:
            是否有效
        """
        # 系统保留的配置键前缀
        reserved_prefixes = [
            'window_size',
            'background_color',
            'notification_',
            'global_font',
            'min_font_size',
            'max_font_size',
            'animation_',
            'position_',
            'width_ratio',
            'height_ratio',
            'max_visible',
            'offset_',
            'spacing_',
            'auto_close_time',
            'github_acceleration',
            'online_import_mode',
            'current_theme',
            'highlight_button_color',
            'card_background_color',
            'component_background_color',
            'text_color',
            'tab_order',
            'tab_visibility',
            'initial_tab',
            'hk_',
            'is_first_run',
            'download_thread_num'
        ]
        
        # 检查是否以保留前缀开头
        for prefix in reserved_prefixes:
            if key.startswith(prefix):
                logger.warning(f"Config key conflicts with system reserved key: {key}")
                return False
        
        return True
    
    def _validate_config_value(self, value: Any) -> bool:
        """
        验证配置值类型是否有效
        
        Args:
            value: 配置值
            
        Returns:
            是否有效
        """
        # 支持的配置值类型
        valid_types = (str, int, float, bool, dict, list, tuple, type(None))
        
        if not isinstance(value, valid_types):
            return False
        
        # 对于容器类型，递归验证内部元素
        if isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(k, str):
                    return False
                if not self._validate_config_value(v):
                    return False
        elif isinstance(value, (list, tuple)):
            for item in value:
                if not self._validate_config_value(item):
                    return False
        
        return True
    
    # 主应用设置访问
    def get_app_config(self, plugin_name: str, key: str, default=None) -> Any:
        """
        读取主应用配置（需要用户授权）
        
        敏感配置（如 API Key）会弹窗询问用户是否允许访问。
        
        Args:
            plugin_name: 插件名称
            key: 配置键
            default: 默认值
            
        Returns:
            配置值，如果用户拒绝访问则返回 None
        """
        try:
            # 检查是否是敏感配置
            if self._is_sensitive_config(key):
                # 弹窗询问用户
                if not self._request_sensitive_permission(plugin_name, key):
                    logger.warning(f"Plugin {plugin_name} was denied access to sensitive config: {key}")
                    return None
            
            # 读取配置
            value_str = self.settings_manager.get_Custom_value(key, None)
            
            if value_str is None:
                return default
            
            # 尝试反序列化
            try:
                import json
                return json.loads(value_str)
            except (json.JSONDecodeError, ValueError):
                return value_str
                
        except Exception as e:
            logger.error(f"Error reading app config for plugin {plugin_name}, key {key}: {e}", exc_info=True)
            return default
    
    def _is_sensitive_config(self, key: str) -> bool:
        """
        判断配置键是否是敏感信息
        
        Args:
            key: 配置键
            
        Returns:
            是否敏感
        """
        # 敏感配置关键词
        sensitive_keywords = [
            'api_key', 'apikey', 'api-key',
            'secret', 'password', 'token',
            'access_key', 'private_key',
            'credential', 'auth'
        ]
        
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)
    
    def _request_sensitive_permission(self, plugin_name: str, config_key: str) -> bool:
        """
        请求用户授权访问敏感配置
        
        Args:
            plugin_name: 插件名称
            config_key: 配置键
            
        Returns:
            用户是否授权
        """
        try:
            from PyQt5.QtWidgets import QMessageBox
            
            # 检查是否已授权（记住用户选择）
            permission_key = f"plugin_permission_{plugin_name}_{config_key}"
            cached_permission = self.settings_manager.get_Custom_value(permission_key, None)
            
            if cached_permission == "allowed":
                return True
            elif cached_permission == "denied":
                return False
            
            # 弹窗询问用户
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("插件权限请求")
            msg_box.setText(f"插件 '{plugin_name}' 请求访问敏感配置")
            msg_box.setInformativeText(
                f"配置键: {config_key}\n\n"
                f"此配置可能包含敏感信息（如 API Key）。\n"
                f"是否允许该插件访问？"
            )
            
            # 添加按钮
            allow_btn = msg_box.addButton("允许", QMessageBox.AcceptRole)
            deny_btn = msg_box.addButton("拒绝", QMessageBox.RejectRole)
            remember_checkbox = msg_box.addButton("记住我的选择", QMessageBox.ActionRole)
            
            msg_box.setDefaultButton(deny_btn)
            msg_box.exec_()
            
            clicked_button = msg_box.clickedButton()
            
            # 判断用户选择
            if clicked_button == allow_btn:
                # 如果勾选了"记住选择"
                if msg_box.checkBox() and msg_box.checkBox().isChecked():
                    self.settings_manager.set_Custom_value(permission_key, "allowed")
                return True
            else:
                # 如果勾选了"记住选择"
                if msg_box.checkBox() and msg_box.checkBox().isChecked():
                    self.settings_manager.set_Custom_value(permission_key, "denied")
                return False
                
        except Exception as e:
            logger.error(f"Error requesting permission: {e}", exc_info=True)
            # 出错时默认拒绝
            return False
        
    # 资源管理
    def get_resource_path(self, plugin_name: str, resource_name: str) -> Optional[str]:
        """
        获取插件资源文件路径（带安全验证）
        
        支持插件资源目录结构：
        - plugins/{plugin_name}/resources/{resource_name}
        - plugins/{plugin_name}/{resource_name}
        
        安全验证：
        - 防止路径遍历攻击（../ 等）
        - 确保路径始终在插件目录内
        - 验证资源文件存在性
        
        Args:
            plugin_name: 插件名称
            resource_name: 资源文件名（相对于插件目录或resources/子目录）
            
        Returns:
            资源文件的绝对路径，如果不存在或不安全则返回None
        """
        try:
            from pathlib import Path
            import os
            
            # 获取插件目录
            plugin_dir = self.plugin_manager.plugin_directory / plugin_name
            
            # 验证插件目录存在
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                logger.warning(f"Plugin directory does not exist: {plugin_dir}")
                return None
            
            # 规范化资源名称，移除可能的路径遍历字符
            # 将路径分隔符统一为 /，然后分割
            resource_parts = resource_name.replace('\\', '/').split('/')
            
            # 过滤掉危险的路径组件
            safe_parts = []
            for part in resource_parts:
                # 跳过空字符串、当前目录标记和父目录标记
                if part and part != '.' and part != '..':
                    safe_parts.append(part)
            
            if not safe_parts:
                logger.warning(f"Invalid resource name after sanitization: {resource_name}")
                return None
            
            # 重新构建安全的资源路径
            safe_resource_name = '/'.join(safe_parts)
            
            # 尝试两个可能的资源路径：
            # 1. plugins/{plugin_name}/resources/{resource_name}
            # 2. plugins/{plugin_name}/{resource_name}
            
            resource_path_1 = plugin_dir / "resources" / safe_resource_name
            resource_path_2 = plugin_dir / safe_resource_name
            
            # 解析为绝对路径并验证安全性
            try:
                resolved_path_1 = resource_path_1.resolve()
                resolved_path_2 = resource_path_2.resolve()
                plugin_dir_resolved = plugin_dir.resolve()
                
                # 检查路径1是否在插件目录内且文件存在
                if self._is_safe_path(resolved_path_1, plugin_dir_resolved):
                    if resolved_path_1.exists() and resolved_path_1.is_file():
                        logger.debug(f"Found resource: {resolved_path_1}")
                        return str(resolved_path_1)
                
                # 检查路径2是否在插件目录内且文件存在
                if self._is_safe_path(resolved_path_2, plugin_dir_resolved):
                    if resolved_path_2.exists() and resolved_path_2.is_file():
                        logger.debug(f"Found resource: {resolved_path_2}")
                        return str(resolved_path_2)
                
                # 资源文件不存在
                logger.warning(f"Resource not found: {resource_name} in plugin {plugin_name}")
                return None
                
            except (OSError, RuntimeError) as e:
                logger.error(f"Error resolving resource path: {e}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting resource path for plugin {plugin_name}, resource {resource_name}: {e}", exc_info=True)
            return None
    
    def _is_safe_path(self, resource_path, plugin_dir) -> bool:
        """
        验证资源路径是否安全（在插件目录内）
        
        Args:
            resource_path: 资源文件的绝对路径
            plugin_dir: 插件目录的绝对路径
            
        Returns:
            路径是否安全
        """
        try:
            # 检查资源路径是否以插件目录为前缀
            # 使用 Path.is_relative_to() 方法（Python 3.9+）或手动检查
            try:
                # Python 3.9+
                return resource_path.is_relative_to(plugin_dir)
            except AttributeError:
                # Python 3.8 及以下版本的兼容实现
                try:
                    resource_path.relative_to(plugin_dir)
                    return True
                except ValueError:
                    return False
        except Exception as e:
            logger.error(f"Error checking path safety: {e}")
            return False
        
    # TTS引擎与UI集成
    def get_plugin_tts_engines(self) -> list:
        """
        获取所有插件TTS引擎列表（用于SettingsPage显示）
        
        Returns:
            插件引擎列表，每个元素为 dict: {
                'engine_id': str,
                'engine_name': str,
                'provider': str,
                'version': str,
                'plugin_name': str
            }
        """
        try:
            from tts_router import get_tts_router
            tts_router = get_tts_router()
            
            engines = []
            dynamic_engines = tts_router.get_dynamic_engines()
            
            for engine_id, engine_class in dynamic_engines.items():
                try:
                    # 实例化引擎获取信息
                    engine_instance = engine_class()
                    engine_info = engine_instance.get_engine_info()
                    
                    # 查找注册该引擎的插件
                    plugin_name = None
                    for pname, plugin_instance in self.plugin_manager.plugins.items():
                        if engine_id in plugin_instance.registered_engines:
                            plugin_name = pname
                            break
                    
                    engines.append({
                        'engine_id': engine_id,
                        'engine_name': engine_info.engine_name,
                        'provider': engine_info.provider,
                        'version': engine_info.version,
                        'plugin_name': plugin_name or 'Unknown'
                    })
                except Exception as e:
                    logger.error(f"Error getting engine info for {engine_id}: {e}")
                    continue
            
            logger.info(f"Retrieved {len(engines)} plugin TTS engines")
            return engines
            
        except Exception as e:
            logger.error(f"Error getting plugin TTS engines: {e}", exc_info=True)
            return []
    
    def get_plugin_engine_voices(self, engine_id: str) -> list:
        """
        获取插件TTS引擎的音色列表（用于GenerationPage显示）
        
        Args:
            engine_id: 引擎ID
            
        Returns:
            音色列表，每个元素为 dict: {
                'voiceID': str,
                'voiceName': str,
                'language': str,
                'gender': str,
                'belongingModel': str
            }
        """
        try:
            from tts_router import get_tts_router
            tts_router = get_tts_router()
            
            # 获取音色列表
            voices = tts_router.get_voices(engine_id, use_cache=True)
            
            # 转换为GenerationPage期望的格式
            voice_list = []
            for voice in voices:
                voice_list.append({
                    'voiceID': voice.voice_id,
                    'voiceName': voice.voice_name,
                    'language': voice.language,
                    'gender': voice.gender if hasattr(voice, 'gender') else '',
                    'belongingModel': f"Plugin/{engine_id}"  # 标记为插件引擎
                })
            
            logger.info(f"Retrieved {len(voice_list)} voices for engine {engine_id}")
            return voice_list
            
        except Exception as e:
            logger.error(f"Error getting voices for engine {engine_id}: {e}", exc_info=True)
            return []
    
    def refresh_plugin_engine_voices(self, engine_id: str = None) -> bool:
        """
        刷新插件TTS引擎的音色列表缓存
        
        Args:
            engine_id: 引擎ID，如果为None则刷新所有引擎
            
        Returns:
            刷新是否成功
        """
        try:
            from tts_router import get_tts_router
            tts_router = get_tts_router()
            
            success = tts_router.refresh_voices(engine_id)
            
            if success:
                logger.info(f"Refreshed voices for engine: {engine_id or 'all'}")
            else:
                logger.warning(f"Failed to refresh voices for engine: {engine_id or 'all'}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error refreshing voices: {e}", exc_info=True)
            return False
    
    # ReadyGate集成
    def register_ready_gate(self, plugin_name: str, component: str) -> bool:
        """
        注册插件就绪状态（带命名空间隔离）
        
        为插件组件注册就绪状态检查点，使用命名空间格式：plugin_{plugin_name}_{component}
        自动检测与系统保留状态的冲突。
        
        Args:
            plugin_name: 插件名称
            component: 组件名称
            
        Returns:
            注册是否成功
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 构建带命名空间的状态名称
            state_name = self._build_ready_gate_name(plugin_name, component)
            
            # 检测与系统保留状态的冲突
            if self._is_system_reserved_state(component):
                logger.warning(
                    f"Component name '{component}' conflicts with system reserved state. "
                    f"Using namespaced name: {state_name}"
                )
            
            # 获取 ReadyGate 实例
            ready_gate = self.plugin_manager.main_window.ready_gate
            
            # 注册就绪状态
            ready_gate.register(state_name)
            
            # 记录到插件实例
            if state_name not in plugin_instance.ready_gates:
                plugin_instance.ready_gates.append(state_name)
            
            logger.info(f"Registered ready gate '{state_name}' for plugin '{plugin_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error registering ready gate for plugin {plugin_name}: {e}", exc_info=True)
            return False
        
    def mark_ready(self, plugin_name: str, component: str, component_instance=None) -> None:
        """
        标记插件组件就绪（带命名空间隔离）
        
        更新插件组件的就绪状态，可选地保存组件实例。
        
        Args:
            plugin_name: 插件名称
            component: 组件名称
            component_instance: 组件实例（可选）
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return
            
            # 构建带命名空间的状态名称
            state_name = self._build_ready_gate_name(plugin_name, component)
            
            # 获取 ReadyGate 实例
            ready_gate = self.plugin_manager.main_window.ready_gate
            
            # 标记就绪
            ready_gate.mark_ready(state_name, component_instance)
            
            logger.info(f"Marked ready gate '{state_name}' for plugin '{plugin_name}'")
            
        except Exception as e:
            logger.error(f"Error marking ready for plugin {plugin_name}: {e}", exc_info=True)
        
    def wait_for_ready(self, component: str, timeout: int = 30) -> bool:
        """
        等待组件就绪（支持系统组件和插件组件）
        
        等待指定组件的就绪状态，支持超时控制。
        可以等待系统组件（如 shared_memory, notification）或插件组件（如 plugin_xxx_yyy）。
        
        Args:
            component: 组件名称（系统组件名或完整的插件组件名）
            timeout: 超时时间（秒），默认30秒
            
        Returns:
            组件是否在超时前就绪
        """
        try:
            # 获取 ReadyGate 实例
            ready_gate = self.plugin_manager.main_window.ready_gate
            
            # 获取就绪状态的 Event 对象
            with ready_gate._lock:
                gate = ready_gate._gates.get(component)
            
            if gate is None:
                logger.warning(f"Component '{component}' not registered in ReadyGate")
                return False
            
            # 等待就绪状态，带超时
            is_ready = gate.wait(timeout)
            
            if is_ready:
                logger.debug(f"Component '{component}' is ready")
            else:
                logger.warning(f"Timeout waiting for component '{component}' (timeout={timeout}s)")
            
            return is_ready
            
        except Exception as e:
            logger.error(f"Error waiting for component {component}: {e}", exc_info=True)
            return False
    
    def _build_ready_gate_name(self, plugin_name: str, component: str) -> str:
        """
        构建带命名空间的就绪状态名称
        
        Args:
            plugin_name: 插件名称
            component: 组件名称
            
        Returns:
            带命名空间的状态名称 (格式: plugin_{plugin_name}_{component})
        """
        return f"plugin_{plugin_name}_{component}"
    
    def _is_system_reserved_state(self, component: str) -> bool:
        """
        检查组件名称是否与系统保留状态冲突
        
        系统保留状态包括：
        - page_{name}: 页面就绪状态
        - hotkey: 热键管理器
        - audio: 音频预览
        - shared_memory: 共享内存管理器
        - notification: 通知管理器
        
        Args:
            component: 组件名称
            
        Returns:
            是否与系统保留状态冲突
        """
        # 系统保留的状态名称
        reserved_states = [
            'hotkey',
            'audio',
            'shared_memory',
            'notification'
        ]
        
        # 检查是否与保留状态完全匹配
        if component in reserved_states:
            return True
        
        # 检查是否以 page_ 开头（页面状态）
        if component.startswith('page_'):
            return True
        
        return False
    
    def cleanup_plugin_ready_gates(self, plugin_name: str) -> None:
        """
        清理插件注册的所有就绪状态（用于插件禁用时）
        
        从 ReadyGate 中移除插件注册的所有就绪状态，并清理插件实例的记录。
        
        Args:
            plugin_name: 插件名称
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.warning(f"Plugin not found: {plugin_name}")
                return
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 获取 ReadyGate 实例
            ready_gate = self.plugin_manager.main_window.ready_gate
            
            # 清理所有注册的就绪状态
            for state_name in plugin_instance.ready_gates[:]:  # 使用副本遍历
                try:
                    with ready_gate._lock:
                        # 移除就绪状态
                        if state_name in ready_gate._gates:
                            del ready_gate._gates[state_name]
                        
                        # 移除组件实例
                        if state_name in ready_gate._components:
                            del ready_gate._components[state_name]
                    
                    # 从插件实例中移除记录
                    plugin_instance.ready_gates.remove(state_name)
                    
                    logger.debug(f"Cleaned up ready gate '{state_name}' for plugin '{plugin_name}'")
                    
                except Exception as e:
                    logger.error(f"Error cleaning up ready gate '{state_name}': {e}")
            
            logger.info(f"Cleaned up all ready gates for plugin '{plugin_name}'")
            
        except Exception as e:
            logger.error(f"Error cleaning up ready gates for plugin {plugin_name}: {e}", exc_info=True)
    
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
        return self.plugin_manager.schedule_delayed_initialization(plugin_name, callback, delay_ms)
    
    def get_plugin_ready_state_info(self, plugin_name: str = None) -> dict:
        """
        获取插件就绪状态的详细监控信息（需求 15.12）
        
        在调试模式下提供插件就绪状态的详细信息。
        
        Args:
            plugin_name: 插件名称，如果为None则返回所有插件的信息
            
        Returns:
            就绪状态信息字典
        """
        return self.plugin_manager.get_plugin_ready_state_info(plugin_name)
    
    def _start_memory_monitoring(self, plugin_name: str, tab_name: str, page_instance) -> None:
        """
        开始监控插件页面的内存使用（需求 20.9）
        
        使用 psutil 监控页面实例的内存占用，防止内存泄漏。
        
        Args:
            plugin_name: 插件名称
            tab_name: 选项卡名称
            page_instance: 页面实例
        """
        try:
            import psutil
            import os
            
            # 获取当前进程
            process = psutil.Process(os.getpid())
            
            # 记录初始内存使用
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 存储到插件实例的元数据中
            if plugin_name in self.plugin_manager.plugins:
                plugin_instance = self.plugin_manager.plugins[plugin_name]
                
                # 初始化内存监控字典（如果不存在）
                if not hasattr(plugin_instance, 'page_memory_usage'):
                    plugin_instance.page_memory_usage = {}
                
                plugin_instance.page_memory_usage[tab_name] = {
                    'initial_memory_mb': initial_memory,
                    'page_instance': page_instance,
                    'created_at': __import__('datetime').datetime.now()
                }
                
                logger.debug(
                    f"Started memory monitoring for plugin '{plugin_name}', "
                    f"tab '{tab_name}' (initial: {initial_memory:.2f} MB)"
                )
        except ImportError:
            logger.warning("psutil not available, memory monitoring disabled")
        except Exception as e:
            logger.error(f"Error starting memory monitoring: {e}", exc_info=True)
    
    def check_plugin_page_memory(self, plugin_name: str, tab_name: str = None) -> dict:
        """
        检查插件页面的内存使用情况（需求 20.9）
        
        Args:
            plugin_name: 插件名称
            tab_name: 选项卡名称（可选，如果为None则检查所有页面）
            
        Returns:
            内存使用信息字典
        """
        try:
            import psutil
            import os
            
            if plugin_name not in self.plugin_manager.plugins:
                return {"error": f"Plugin not found: {plugin_name}"}
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            if not hasattr(plugin_instance, 'page_memory_usage'):
                return {"error": "No memory monitoring data available"}
            
            process = psutil.Process(os.getpid())
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            memory_info = {
                'plugin_name': plugin_name,
                'current_total_memory_mb': current_memory,
                'pages': {}
            }
            
            # 检查指定页面或所有页面
            pages_to_check = [tab_name] if tab_name else list(plugin_instance.page_memory_usage.keys())
            
            for page_name in pages_to_check:
                if page_name in plugin_instance.page_memory_usage:
                    page_data = plugin_instance.page_memory_usage[page_name]
                    initial_memory = page_data['initial_memory_mb']
                    memory_delta = current_memory - initial_memory
                    
                    memory_info['pages'][page_name] = {
                        'initial_memory_mb': initial_memory,
                        'memory_delta_mb': memory_delta,
                        'created_at': page_data['created_at'].isoformat()
                    }
                    
                    # 警告：如果内存增长超过100MB
                    if memory_delta > 100:
                        logger.warning(
                            f"High memory usage detected for plugin '{plugin_name}', "
                            f"tab '{page_name}': +{memory_delta:.2f} MB"
                        )
                        memory_info['pages'][page_name]['warning'] = 'High memory usage'
            
            return memory_info
            
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as e:
            logger.error(f"Error checking plugin page memory: {e}", exc_info=True)
            return {"error": str(e)}
    
    def update_tab_display_name(self, plugin_name: str, tab_name: str, new_display_name: str) -> bool:
        """
        动态更新选项卡显示名称（需求 14.10, 20.11）
        
        支持多语言切换时更新插件页面的显示名称。
        
        Args:
            plugin_name: 插件名称
            tab_name: 选项卡内部名称
            new_display_name: 新的显示名称
            
        Returns:
            更新是否成功
        """
        try:
            # 验证插件是否存在
            if plugin_name not in self.plugin_manager.plugins:
                logger.error(f"Plugin not found: {plugin_name}")
                return False
            
            plugin_instance = self.plugin_manager.plugins[plugin_name]
            
            # 验证选项卡是否由该插件注册
            if tab_name not in plugin_instance.registered_tabs:
                logger.warning(f"Tab '{tab_name}' not registered by plugin '{plugin_name}'")
                return False
            
            # 更新 TabManager 中的显示名称
            tab_manager = self.plugin_manager.main_window.tab_manager
            
            for tab_config in tab_manager.tab_configs:
                if tab_config.name == tab_name:
                    tab_config.display_name = new_display_name
                    
                    # 如果选项卡按钮已创建，更新按钮文本
                    tab_index = tab_manager.tab_configs.index(tab_config)
                    if tab_index < len(tab_manager.tab_buttons):
                        button = tab_manager.tab_buttons[tab_index]
                        button.setText(new_display_name)
                    
                    logger.info(
                        f"Updated display name for tab '{tab_name}' "
                        f"(plugin '{plugin_name}') to '{new_display_name}'"
                    )
                    return True
            
            logger.warning(f"Tab config not found for '{tab_name}'")
            return False
            
        except Exception as e:
            logger.error(f"Error updating tab display name: {e}", exc_info=True)
            return False
    
    def _call_page_lifecycle_hook(self, page_instance, hook_name: str, plugin_name: str, tab_name: str) -> None:
        """
        调用插件页面的生命周期钩子（需求 20.4, 20.5, 20.11）
        
        安全地调用页面生命周期方法，带错误处理和日志记录。
        
        Args:
            page_instance: 页面实例
            hook_name: 钩子方法名称 (on_page_shown, on_page_hidden, on_page_destroyed)
            plugin_name: 插件名称
            tab_name: 选项卡名称
        """
        try:
            if hasattr(page_instance, hook_name):
                hook_method = getattr(page_instance, hook_name)
                if callable(hook_method):
                    try:
                        hook_method()
                        logger.debug(
                            f"Called {hook_name} for plugin '{plugin_name}', tab '{tab_name}'"
                        )
                    except Exception as lifecycle_error:
                        logger.error(
                            f"Error in {hook_name} for plugin '{plugin_name}', tab '{tab_name}': {lifecycle_error}",
                            exc_info=True
                        )
                        # 记录到插件日志（需求 20.11）
                        self.plugin_manager.plugin_logger.error(
                            f"{hook_name} failed: {lifecycle_error}",
                            plugin_name
                        )
        except Exception as e:
            logger.error(f"Error calling lifecycle hook {hook_name}: {e}", exc_info=True)
