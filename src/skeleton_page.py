# coding=utf-8

import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget


class SkeletonPage(QWidget):
    """极轻量骨架屏，占位展示尚未就绪的页面内容。"""

    _DEFAULT_LAYOUTS = {
        "welcome": [
            (0.08, 0.05, 0.84, 0.08),
            (0.08, 0.18, 0.40, 0.28),
            (0.52, 0.18, 0.40, 0.28),
            (0.08, 0.52, 0.84, 0.10),
            (0.08, 0.68, 0.84, 0.20),
        ],
        "dictation": [
            (0.05, 0.04, 0.58, 0.07),
            (0.05, 0.15, 0.58, 0.58),
            (0.68, 0.15, 0.27, 0.42),
            (0.68, 0.62, 0.27, 0.11),
            (0.05, 0.79, 0.90, 0.09),
        ],
        "settings": [
            (0.06, 0.05, 0.28, 0.08),
            (0.06, 0.18, 0.20, 0.60),
            (0.32, 0.18, 0.62, 0.18),
            (0.32, 0.41, 0.62, 0.18),
            (0.32, 0.64, 0.62, 0.14),
        ],
        "personalization": [
            (0.06, 0.05, 0.34, 0.08),
            (0.06, 0.18, 0.88, 0.18),
            (0.06, 0.42, 0.88, 0.18),
            (0.06, 0.66, 0.42, 0.16),
            (0.52, 0.66, 0.42, 0.16),
        ],
        "misc": [
            (0.06, 0.05, 0.34, 0.08),
            (0.06, 0.18, 0.26, 0.20),
            (0.37, 0.18, 0.26, 0.20),
            (0.68, 0.18, 0.26, 0.20),
            (0.06, 0.45, 0.88, 0.16),
            (0.06, 0.67, 0.88, 0.16),
        ],
        "streaming": [
            (0.06, 0.05, 0.46, 0.08),
            (0.06, 0.18, 0.88, 0.16),
            (0.06, 0.40, 0.88, 0.16),
            (0.06, 0.62, 0.88, 0.16),
        ],
    }

    def __init__(self, tab_name, parent=None):
        super().__init__(parent)
        self.tab_name = tab_name
        self._placeholder_rects = self._DEFAULT_LAYOUTS.get(
            tab_name,
            [
                (0.08, 0.05, 0.42, 0.08),
                (0.08, 0.18, 0.84, 0.18),
                (0.08, 0.42, 0.84, 0.18),
                (0.08, 0.66, 0.60, 0.14),
            ],
        )
        self._pulse_phase = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._advance_pulse)
        self._pulse_timer.start(50)

    def _advance_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.18) % (math.pi * 2)
        self.update()

    def _placeholder_color(self, index):
        pulse = (math.sin(self._pulse_phase + index * 0.45) + 1.0) / 2.0
        base = 214 + int(12 * pulse)
        accent = 222 + int(10 * pulse)
        alpha = 138 + int(28 * pulse)
        return QColor(base, accent, 232, alpha)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(255, 255, 255, 0))
        painter.setPen(Qt.NoPen)

        width = max(self.width(), 1)
        height = max(self.height(), 1)
        for index, (rx, ry, rw, rh) in enumerate(self._placeholder_rects):
            painter.setBrush(self._placeholder_color(index))
            painter.drawRoundedRect(
                int(rx * width),
                int(ry * height),
                int(rw * width),
                int(rh * height),
                10,
                10,
            )

        painter.end()
