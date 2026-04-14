# coding=utf-8

import threading


class ReadyGate:
    """组件就绪栅栏，用于跟踪延迟初始化组件的可用状态。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._gates = {}
        self._components = {}

    def register(self, name):
        """注册一个就绪栅栏；重复注册时保持幂等。"""
        with self._lock:
            if name not in self._gates:
                self._gates[name] = threading.Event()

    def mark_ready(self, name, component=None):
        """标记组件已就绪，并可顺带保存组件实例。"""
        with self._lock:
            gate = self._gates.setdefault(name, threading.Event())
            self._components[name] = component
            gate.set()

    def is_ready(self, name):
        """检查组件是否已经就绪。"""
        with self._lock:
            gate = self._gates.get(name)
        return gate.is_set() if gate is not None else False

    def get(self, name):
        """获取已保存的组件实例。"""
        with self._lock:
            return self._components.get(name)
