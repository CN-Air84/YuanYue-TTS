# coding=utf-8

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class _MarkRecord:
    name: str
    elapsed_ms: float
    delta_ms: float
    detail: str = ""


@dataclass(frozen=True)
class _SpanRecord:
    name: str
    duration_ms: float
    detail: str = ""


class StartupProfiler:
    """记录启动阶段关键节点与耗时区间。"""

    SUMMARY_ORDER: List[Tuple[str, str]] = [
        ("module_imports_ready", "顶层导入完成"),
        ("main_enter", "进入 main()"),
        ("encoding_ready", "编码环境就绪"),
        ("single_instance_checked", "单实例检查完成"),
        ("qapplication_created", "QApplication 创建完成"),
        ("main_window_init_started", "MainWindow 构造开始"),
        ("core_components_ready", "核心组件就绪"),
        ("settings_loaded", "设置加载完成"),
        ("ui_shell_ready", "窗口壳体就绪"),
        ("window_visible", "窗口首次可见"),
        ("deferred_init_started", "deferred init 开始"),
        ("background_preload_started", "后台预热开始"),
        ("async_initialization_started", "异步初始化开始"),
        ("first_page_ready", "首屏页面就绪"),
        ("shared_memory_ready", "共享内存就绪"),
        ("notification_ready", "通知管理器就绪"),
        ("async_finished", "异步初始化完成"),
    ]

    DEFAULT_GUARDS: List[Tuple[str, float, str]] = [
        ("window_visible", 300.0, "窗口可见时间"),
        ("first_page_ready", 600.0, "首屏可交互时间"),
        ("async_finished", 3000.0, "启动全量完成时间"),
    ]

    def __init__(self, base_time: Optional[float] = None):
        self._base_time = base_time if base_time is not None else time.perf_counter()
        self._last_time = self._base_time
        self._marks: List[_MarkRecord] = []
        self._last_mark_by_name: Dict[str, _MarkRecord] = {}
        self._span_starts: Dict[str, Tuple[float, str]] = {}
        self._spans: List[_SpanRecord] = []
        self._lock = threading.RLock()

    def has_mark(self, name: str) -> bool:
        with self._lock:
            return name in self._last_mark_by_name

    def mark(self, name: str, detail: str = "") -> _MarkRecord:
        with self._lock:
            now = time.perf_counter()
            elapsed_ms = (now - self._base_time) * 1000.0
            delta_ms = (now - self._last_time) * 1000.0
            record = _MarkRecord(name=name, elapsed_ms=elapsed_ms, delta_ms=delta_ms, detail=detail)
            self._marks.append(record)
            self._last_mark_by_name[name] = record
            self._last_time = now
            return record

    def mark_once(self, name: str, detail: str = "") -> _MarkRecord:
        with self._lock:
            existing = self._last_mark_by_name.get(name)
            if existing is not None:
                return existing
            return self.mark(name, detail)

    def start_span(self, name: str, detail: str = "") -> None:
        with self._lock:
            self._span_starts[name] = (time.perf_counter(), detail)

    def end_span(self, name: str, detail: str = "") -> Optional[float]:
        with self._lock:
            start_info = self._span_starts.pop(name, None)
            if start_info is None:
                return None

            started_at, start_detail = start_info
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            span_detail = detail or start_detail
            self._spans.append(_SpanRecord(name=name, duration_ms=duration_ms, detail=span_detail))
            return duration_ms

    def get_mark_elapsed_ms(self, name: str) -> Optional[float]:
        with self._lock:
            record = self._last_mark_by_name.get(name)
            return None if record is None else record.elapsed_ms

    def total_elapsed_ms(self) -> float:
        with self._lock:
            if self._marks:
                return self._marks[-1].elapsed_ms
            return (time.perf_counter() - self._base_time) * 1000.0

    def build_report_lines(self, max_spans: int = 8) -> List[str]:
        with self._lock:
            lines = [f"启动耗时报告：总计 {self.total_elapsed_ms():.1f}ms"]

            for mark_name, label in self.SUMMARY_ORDER:
                record = self._last_mark_by_name.get(mark_name)
                if record is None:
                    continue
                detail_suffix = f"（{record.detail}）" if record.detail else ""
                lines.append(f"{label}: {record.elapsed_ms:.1f}ms (+{record.delta_ms:.1f}ms){detail_suffix}")

            if self._spans:
                lines.append("关键阶段耗时：")
                top_spans = sorted(self._spans, key=lambda item: item.duration_ms, reverse=True)[:max_spans]
                for span in top_spans:
                    detail_suffix = f"（{span.detail}）" if span.detail else ""
                    lines.append(f"- {span.name}: {span.duration_ms:.1f}ms{detail_suffix}")

            return lines

    def build_guard_results(self) -> List[Tuple[bool, str]]:
        with self._lock:
            results: List[Tuple[bool, str]] = []
            for mark_name, threshold_ms, label in self.DEFAULT_GUARDS:
                record = self._last_mark_by_name.get(mark_name)
                if record is None:
                    results.append((False, f"{label}: 缺少关键埋点 {mark_name}"))
                    continue

                passed = record.elapsed_ms <= threshold_ms
                comparator = "<=" if passed else ">"
                results.append((passed, f"{label}: {record.elapsed_ms:.1f}ms {comparator} {threshold_ms:.0f}ms"))

            return results


def run_smoke_validation() -> Tuple[bool, List[str]]:
    """最小冒烟自检：验证报告输出和 guard 判定链路。"""
    logs: List[str] = []
    try:
        profiler = StartupProfiler()
        profiler.mark("window_visible", "smoke")
        profiler.mark("first_page_ready", "smoke")
        profiler.mark("async_finished", "smoke")

        report_lines = profiler.build_report_lines()
        guard_results = profiler.build_guard_results()

        if not report_lines or not report_lines[0].startswith("启动耗时报告"):
            logs.append("报告生成失败：缺少总览行")
            return False, logs

        if len(guard_results) != len(StartupProfiler.DEFAULT_GUARDS):
            logs.append("guard 判定失败：返回数量不匹配")
            return False, logs

        failed_guards = [line for passed, line in guard_results if not passed]
        if failed_guards:
            logs.append("guard 判定失败：正常链路出现未通过项")
            logs.extend(failed_guards)
            return False, logs

        missing_mark_profiler = StartupProfiler()
        missing_mark_profiler.mark("window_visible", "smoke_missing")
        missing_results = missing_mark_profiler.build_guard_results()
        if not any((not passed) and ("缺少关键埋点" in line) for passed, line in missing_results):
            logs.append("guard 判定失败：缺失埋点未触发告警")
            return False, logs

        logs.append("StartupProfiler 冒烟自检通过")
        return True, logs
    except Exception as exc:
        logs.append(f"StartupProfiler 冒烟自检异常: {exc}")
        return False, logs


if __name__ == "__main__":
    ok, messages = run_smoke_validation()
    for message in messages:
        print(message)
    raise SystemExit(0 if ok else 1)

