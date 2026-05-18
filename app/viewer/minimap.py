from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget


class MinimapWidget(QWidget):
    navigate_to = pyqtSignal(QPointF)  # normalized 0..1 within SVG area

    WIDTH = 160
    HEIGHT = 120

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._renderer: Optional[QSvgRenderer] = None
        self._viewport_rect: Optional[QRectF] = None  # in minimap pixel coords
        self._render_rect: QRectF = QRectF()           # aspect-ratio rect
        self._dragging = False

        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)

    def set_renderer(self, renderer: QSvgRenderer) -> None:
        self._renderer = renderer
        self._render_rect = self._compute_render_rect()
        self.update()

    def update_viewport(self, visible: QRectF, total: QRectF) -> None:
        rr = self._render_rect
        if total.width() <= 0 or total.height() <= 0 or rr.width() <= 0:
            self._viewport_rect = None
        else:
            sx = rr.width() / total.width()
            sy = rr.height() / total.height()
            rx = rr.x() + (visible.x() - total.x()) * sx
            ry = rr.y() + (visible.y() - total.y()) * sy
            rw = visible.width() * sx
            rh = visible.height() * sy
            self._viewport_rect = QRectF(rx, ry, rw, rh)
        self.update()

    def _compute_render_rect(self) -> QRectF:
        if self._renderer is None or not self._renderer.isValid():
            return QRectF(self.rect())
        svg_size = self._renderer.defaultSize()
        if svg_size.width() <= 0 or svg_size.height() <= 0:
            return QRectF(self.rect())
        scale = min(self.width() / svg_size.width(), self.height() / svg_size.height())
        rw = svg_size.width() * scale
        rh = svg_size.height() * scale
        return QRectF((self.width() - rw) / 2, (self.height() - rh) / 2, rw, rh)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(30, 30, 30, 220))

        if self._renderer and self._renderer.isValid() and not self._render_rect.isNull():
            self._renderer.render(p, self._render_rect)

        if self._viewport_rect:
            clamped = self._viewport_rect.intersected(QRectF(self.rect()))
            p.setPen(QPen(QColor(255, 165, 0), 2))
            p.setBrush(QBrush(QColor(255, 165, 0, 40)))
            p.drawRect(clamped)

        p.setPen(QPen(QColor(80, 80, 80), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._emit_navigate(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._emit_navigate(event.pos())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def _emit_navigate(self, pos) -> None:
        rr = self._render_rect
        if rr.width() <= 0 or rr.height() <= 0:
            return
        nx = max(0.0, min(1.0, (pos.x() - rr.x()) / rr.width()))
        ny = max(0.0, min(1.0, (pos.y() - rr.y()) / rr.height()))
        self.navigate_to.emit(QPointF(nx, ny))
