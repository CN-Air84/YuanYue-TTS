"""
插件事件总线 - 独立的事件系统

提供插件间和插件与主应用的事件通信机制，不依赖SharedMemoryManager。
完全独立的事件系统，使用独立的事件命名空间（plugin_ 前缀）。
"""

from typing import Dict, List, Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
import logging
import uuid
import threading
import time


logger = logging.getLogger(__name__)


@dataclass
class EventSubscription:
    """事件订阅信息"""
    subscription_id: str
    event_type: str
    callback: Callable
    plugin_name: str
    priority: int = 0  # 优先级，数值越大优先级越高
    filter_func: Optional[Callable[[dict], bool]] = None  # 事件过滤函数


class PluginEventBus:
    """
    插件事件总线 - 独立的事件系统
    
    特性:
    - 完全独立于 SharedMemoryManager
    - 使用独立的事件命名空间（plugin_ 前缀）
    - 支持事件优先级和过滤
    - 线程安全的订阅管理
    - 带超时保护的异步事件处理
    """
    
    # 事件命名空间前缀
    EVENT_NAMESPACE = "plugin_"
    
    # 事件回调超时时间（秒）
    CALLBACK_TIMEOUT = 3
    
    def __init__(self):
        """初始化插件事件总线"""
        # 订阅信息: event_type -> List[EventSubscription]
        self._subscriptions: Dict[str, List[EventSubscription]] = {}
        
        # 订阅ID到订阅信息的映射
        self._subscription_map: Dict[str, EventSubscription] = {}
        
        # 插件名称到订阅ID列表的映射
        self._plugin_subscriptions: Dict[str, List[str]] = {}
        
        # 线程池用于异步事件处理
        self._thread_pool = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="PluginEventBus"
        )
        
        # 线程锁保证线程安全
        self._lock = threading.RLock()
        
        # 事件统计
        self._event_stats = {
            'total_events': 0,
            'total_subscriptions': 0,
            'failed_callbacks': 0
        }
        
        logger.info("PluginEventBus initialized with thread pool (max_workers=4)")
        
    def subscribe(
        self,
        event_type: str,
        callback: Callable,
        plugin_name: str = "unknown",
        priority: int = 0,
        filter_func: Optional[Callable[[dict], bool]] = None
    ) -> str:
        """
        订阅事件
        
        Args:
            event_type: 事件类型（自动添加 plugin_ 前缀）
            callback: 回调函数，接收一个 dict 参数
            plugin_name: 插件名称，用于管理和清理
            priority: 优先级，数值越大优先级越高（默认0）
            filter_func: 可选的事件过滤函数，返回True表示接收该事件
            
        Returns:
            订阅ID，用于取消订阅
        """
        # 确保事件类型使用插件命名空间
        event_type = self._normalize_event_type(event_type)
        
        # 验证事件类型
        if not self._validate_event_type(event_type):
            logger.error(f"Invalid event type: {event_type}")
            raise ValueError(f"Invalid event type: {event_type}")
        
        subscription_id = str(uuid.uuid4())
        
        subscription = EventSubscription(
            subscription_id=subscription_id,
            event_type=event_type,
            callback=callback,
            plugin_name=plugin_name,
            priority=priority,
            filter_func=filter_func
        )
        
        with self._lock:
            # 添加到订阅列表
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            
            self._subscriptions[event_type].append(subscription)
            
            # 按优先级排序（优先级高的在前）
            self._subscriptions[event_type].sort(
                key=lambda s: s.priority,
                reverse=True
            )
            
            # 添加到映射表
            self._subscription_map[subscription_id] = subscription
            
            # 添加到插件订阅列表
            if plugin_name not in self._plugin_subscriptions:
                self._plugin_subscriptions[plugin_name] = []
            self._plugin_subscriptions[plugin_name].append(subscription_id)
            
            self._event_stats['total_subscriptions'] += 1
        
        logger.info(
            f"Event subscribed: {event_type} by plugin '{plugin_name}' "
            f"(priority={priority}, subscription_id={subscription_id})"
        )
        
        return subscription_id
        
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅
        
        Args:
            subscription_id: 订阅ID
            
        Returns:
            取消订阅是否成功
        """
        with self._lock:
            if subscription_id not in self._subscription_map:
                logger.warning(f"Subscription not found: {subscription_id}")
                return False
            
            subscription = self._subscription_map[subscription_id]
            event_type = subscription.event_type
            plugin_name = subscription.plugin_name
            
            # 从订阅列表中移除
            if event_type in self._subscriptions:
                self._subscriptions[event_type] = [
                    s for s in self._subscriptions[event_type]
                    if s.subscription_id != subscription_id
                ]
                
                # 如果该事件类型没有订阅者了，删除该键
                if not self._subscriptions[event_type]:
                    del self._subscriptions[event_type]
            
            # 从映射表中移除
            del self._subscription_map[subscription_id]
            
            # 从插件订阅列表中移除
            if plugin_name in self._plugin_subscriptions:
                self._plugin_subscriptions[plugin_name] = [
                    sid for sid in self._plugin_subscriptions[plugin_name]
                    if sid != subscription_id
                ]
                
                # 如果该插件没有订阅了，删除该键
                if not self._plugin_subscriptions[plugin_name]:
                    del self._plugin_subscriptions[plugin_name]
            
            self._event_stats['total_subscriptions'] -= 1
        
        logger.info(
            f"Event unsubscribed: {event_type} by plugin '{plugin_name}' "
            f"(subscription_id={subscription_id})"
        )
        
        return True
        
    def emit(self, event_type: str, data: dict) -> None:
        """
        发送事件（同步）
        
        Args:
            event_type: 事件类型（自动添加 plugin_ 前缀）
            data: 事件数据
        """
        event_type = self._normalize_event_type(event_type)
        
        with self._lock:
            if event_type not in self._subscriptions:
                logger.debug(f"No subscribers for event: {event_type}")
                return
            
            subscriptions = self._subscriptions[event_type].copy()
            self._event_stats['total_events'] += 1
        
        logger.debug(
            f"Emitting event: {event_type} to {len(subscriptions)} subscribers"
        )
        
        for subscription in subscriptions:
            # 应用过滤器
            if subscription.filter_func:
                try:
                    if not subscription.filter_func(data):
                        logger.debug(
                            f"Event filtered out for subscription {subscription.subscription_id}"
                        )
                        continue
                except Exception as e:
                    logger.error(
                        f"Error in filter function for subscription "
                        f"{subscription.subscription_id}: {e}",
                        exc_info=True
                    )
                    continue
            
            # 执行回调
            try:
                start_time = time.time()
                subscription.callback(data)
                elapsed = time.time() - start_time
                
                if elapsed > self.CALLBACK_TIMEOUT:
                    logger.warning(
                        f"Event callback took {elapsed:.2f}s (exceeds {self.CALLBACK_TIMEOUT}s timeout): "
                        f"plugin '{subscription.plugin_name}', event '{event_type}'"
                    )
            except Exception as e:
                self._event_stats['failed_callbacks'] += 1
                logger.error(
                    f"Error in event callback for plugin '{subscription.plugin_name}', "
                    f"event '{event_type}': {e}",
                    exc_info=True
                )
        
    def emit_async(self, event_type: str, data: dict) -> List[Future]:
        """
        异步发送事件
        
        Args:
            event_type: 事件类型（自动添加 plugin_ 前缀）
            data: 事件数据
            
        Returns:
            Future对象列表，可用于等待或取消异步任务
        """
        event_type = self._normalize_event_type(event_type)
        
        with self._lock:
            if event_type not in self._subscriptions:
                logger.debug(f"No subscribers for async event: {event_type}")
                return []
            
            subscriptions = self._subscriptions[event_type].copy()
            self._event_stats['total_events'] += 1
        
        logger.debug(
            f"Emitting async event: {event_type} to {len(subscriptions)} subscribers"
        )
        
        futures = []
        for subscription in subscriptions:
            future = self._thread_pool.submit(
                self._safe_async_callback,
                subscription,
                data
            )
            futures.append(future)
        
        return futures
    
    def _safe_async_callback(
        self,
        subscription: EventSubscription,
        data: dict
    ) -> None:
        """
        安全执行异步回调函数
        
        Args:
            subscription: 订阅信息
            data: 事件数据
        """
        # 应用过滤器
        if subscription.filter_func:
            try:
                if not subscription.filter_func(data):
                    logger.debug(
                        f"Async event filtered out for subscription {subscription.subscription_id}"
                    )
                    return
            except Exception as e:
                logger.error(
                    f"Error in async filter function for subscription "
                    f"{subscription.subscription_id}: {e}",
                    exc_info=True
                )
                return
        
        # 执行回调
        try:
            start_time = time.time()
            subscription.callback(data)
            elapsed = time.time() - start_time
            
            if elapsed > self.CALLBACK_TIMEOUT:
                logger.warning(
                    f"Async event callback took {elapsed:.2f}s (exceeds {self.CALLBACK_TIMEOUT}s timeout): "
                    f"plugin '{subscription.plugin_name}', event '{subscription.event_type}'"
                )
        except Exception as e:
            with self._lock:
                self._event_stats['failed_callbacks'] += 1
            
            logger.error(
                f"Error in async event callback for plugin '{subscription.plugin_name}', "
                f"event '{subscription.event_type}': {e}",
                exc_info=True
            )
        
    def clear_plugin_subscriptions(self, plugin_name: str) -> int:
        """
        清理插件的所有事件订阅
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            清理的订阅数量
        """
        with self._lock:
            if plugin_name not in self._plugin_subscriptions:
                logger.debug(f"No subscriptions found for plugin: {plugin_name}")
                return 0
            
            subscription_ids = self._plugin_subscriptions[plugin_name].copy()
            count = len(subscription_ids)
        
        # 逐个取消订阅
        for subscription_id in subscription_ids:
            self.unsubscribe(subscription_id)
        
        logger.info(
            f"Cleared {count} subscriptions for plugin '{plugin_name}'"
        )
        
        return count
    
    def get_event_stats(self) -> dict:
        """
        获取事件统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                **self._event_stats,
                'active_subscriptions': len(self._subscription_map),
                'active_plugins': len(self._plugin_subscriptions),
                'event_types': len(self._subscriptions)
            }
    
    def get_plugin_subscriptions(self, plugin_name: str) -> List[str]:
        """
        获取插件的所有订阅ID
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            订阅ID列表
        """
        with self._lock:
            return self._plugin_subscriptions.get(plugin_name, []).copy()
    
    def shutdown(self) -> None:
        """
        关闭事件总线，清理所有资源
        """
        logger.info("Shutting down PluginEventBus...")
        
        # 清理所有订阅
        with self._lock:
            plugin_names = list(self._plugin_subscriptions.keys())
        
        for plugin_name in plugin_names:
            self.clear_plugin_subscriptions(plugin_name)
        
        # 关闭线程池
        self._thread_pool.shutdown(wait=True, cancel_futures=True)
        
        logger.info(
            f"PluginEventBus shutdown complete. "
            f"Final stats: {self.get_event_stats()}"
        )
    
    def _normalize_event_type(self, event_type: str) -> str:
        """
        规范化事件类型，确保使用插件命名空间
        
        Args:
            event_type: 原始事件类型
            
        Returns:
            规范化的事件类型
        """
        if not event_type.startswith(self.EVENT_NAMESPACE):
            return f"{self.EVENT_NAMESPACE}{event_type}"
        return event_type
    
    def _validate_event_type(self, event_type: str) -> bool:
        """
        验证事件类型是否有效
        
        Args:
            event_type: 事件类型
            
        Returns:
            是否有效
        """
        # 必须以 plugin_ 开头
        if not event_type.startswith(self.EVENT_NAMESPACE):
            return False
        
        # 不能为空
        if len(event_type) <= len(self.EVENT_NAMESPACE):
            return False
        
        # 只能包含字母、数字、下划线
        event_name = event_type[len(self.EVENT_NAMESPACE):]
        if not event_name.replace('_', '').isalnum():
            return False
        
        return True
