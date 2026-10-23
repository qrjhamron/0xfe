"""Transparent top-level arrow overlay drawn by Qt, never by the page."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .geometry import arrow_points, arrow_styles


class ArrowOverlay(QWidget):
    """Frameless, click-through window that paints up to three arrows."""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._arrows = []  # [(uci, flipped, color, width)]
        self._flipped = False

    def set_recommendation(self, moves, flipped, color_hex, width):
        self._arrows = list(moves or [])[:3]
        self._flipped = bool(flipped)
        self._color = QColor(color_hex)
        self._width = width
        self.update()

    def clear(self):
        self._arrows = []
        self.update()

    def paintEvent(self, event):
        if not self._arrows or self.width() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = self.width() / 800.0
        styles = arrow_styles(len(self._arrows), getattr(self, '_width', 14))
        for index, move in enumerate(self._arrows):
            line_width, opacity = styles[index]
            x1, y1, x2, y2 = arrow_points(move, self._flipped)
            color = QColor(self._color)
            color.setAlphaF(opacity)
            pen = QPen(color, line_width * scale)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            start, end = QPointF(x1 * scale, y1 * scale), QPointF(x2 * scale, y2 * scale)
            painter.drawLine(start, end)
            # Arrow head: a small filled triangle oriented along the line.
            import math
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            size = max(10.0, line_width * scale * 1.5)
            left = QPointF(end.x() - size * math.cos(angle - 0.42),
                           end.y() - size * math.sin(angle - 0.42))
            right = QPointF(end.x() - size * math.cos(angle + 0.42),
                            end.y() - size * math.sin(angle + 0.42))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(QPolygonF([end, left, right]))
