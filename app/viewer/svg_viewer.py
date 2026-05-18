from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from app.model.svg_document import SvgDocument
from app.settings import SelectionStyle
from app.viewer.minimap import MinimapWidget
from app.viewer.svg_scene import SvgScene


class SvgViewer(QGraphicsView):
    element_selected = pyqtSignal(str)
    element_hovered = pyqtSignal(str)   # "" = no element
    selection_cleared = pyqtSignal()
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = SvgScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setMouseTracking(True)

        self._pan_start: Optional[QPoint] = None
        self._is_panning = False
        self._zoom_level = 1.0
        self._last_hover_id = ''
        self._single_click_select = False

        self._minimap = MinimapWidget(self)
        self._minimap.navigate_to.connect(self._on_minimap_navigate)
        self._minimap.raise_()

    # ── Load / Style ──────────────────────────────────────────────────────

    def load_svg(self, svg_bytes: bytes, doc: SvgDocument) -> None:
        self._scene.load_svg(svg_bytes, doc)
        self._minimap.set_renderer(self._scene.renderer)
        self._last_hover_id = ''
        self.fit_to_window()

    def unload(self) -> None:
        self._scene.clear_document()
        self._last_hover_id = ''
        self._minimap.setVisible(False)

    def set_style(self, style: SelectionStyle) -> None:
        self._scene.set_style(style)

    def set_single_click_select(self, enabled: bool) -> None:
        self._single_click_select = enabled

    # ── Highlight / Hover / Navigate ──────────────────────────────────────

    def highlight_element(self, element_id: str) -> None:
        self._scene.highlight_element(element_id)

    def clear_highlight(self) -> None:
        self._scene.clear_highlight()

    def set_hover_element(self, element_id: Optional[str]) -> None:
        self._scene.set_hover_element(element_id)

    def center_on_element(self, element_id: str) -> None:
        renderer = self._scene.renderer
        svg_item = self._scene.svg_item
        if renderer is None or svg_item is None:
            return
        bounds: QRectF = renderer.boundsOnElement(element_id)
        if bounds.isNull():
            return
        self.centerOn(svg_item.mapToScene(bounds.center()))
        self._update_minimap()

    # ── Zoom ──────────────────────────────────────────────────────────────

    def zoom_in(self) -> None:
        self._apply_zoom(1.25, anchor_center=True)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / 1.25, anchor_center=True)

    def fit_to_window(self) -> None:
        rect = self._scene.sceneRect()
        if rect.isNull():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = self.transform().m11()
        self._update_minimap()
        self.zoom_changed.emit(self._zoom_level)

    def set_zoom_factor(self, factor: float) -> None:
        current = self.transform().m11()
        if current > 0:
            old = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.scale(factor / current, factor / current)
            self.setTransformationAnchor(old)
        self._zoom_level = self.transform().m11()
        self._update_minimap()
        self.zoom_changed.emit(self._zoom_level)

    def current_zoom(self) -> float:
        return self._zoom_level

    def _apply_zoom(self, factor: float, anchor_center: bool = False) -> None:
        if anchor_center:
            old = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.scale(factor, factor)
            self.setTransformationAnchor(old)
        else:
            self.scale(factor, factor)
        self._zoom_level = self.transform().m11()
        self._update_minimap()
        self.zoom_changed.emit(self._zoom_level)

    # ── Hover ─────────────────────────────────────────────────────────────

    def _item_pos_at(self, viewport_pos: QPoint) -> Optional[tuple[str, bool]]:
        """Returns (elem_id_or_empty, within_svg_bounds)."""
        svg_item = self._scene.svg_item
        if svg_item is None:
            return None, False
        item_pos = svg_item.mapFromScene(self.mapToScene(viewport_pos))
        within = svg_item.boundingRect().contains(item_pos)
        if not within:
            return '', False
        return self._scene.element_at_item_pos(item_pos) or '', True

    def _detect_hover(self, viewport_pos: QPoint) -> None:
        elem_id, _ = self._item_pos_at(viewport_pos)
        if elem_id is None:
            elem_id = ''
        if elem_id != self._last_hover_id:
            self._last_hover_id = elem_id
            self.element_hovered.emit(elem_id)

    # ── Mouse events ──────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._apply_zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = event.pos()
            self._is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._emit_hover_clear()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            if not self._is_panning and delta.manhattanLength() > 4:
                self._is_panning = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._is_panning:
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta.y())
                self._pan_start = event.pos()
                self._update_minimap()
                return
        self._detect_hover(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_panning = self._is_panning
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = None
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if (self._single_click_select
                and event.button() == Qt.MouseButton.LeftButton
                and not was_panning):
            self._handle_select(event.pos())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._pan_start = None
        self._is_panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if not self._single_click_select:
            self._handle_select(event.pos())
        event.accept()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._emit_hover_clear()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._reposition_minimap()
        self._update_minimap()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._reposition_minimap()
        self._update_minimap()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _handle_select(self, viewport_pos: QPoint) -> None:
        elem_id, within = self._item_pos_at(viewport_pos)
        if elem_id:
            self.element_selected.emit(elem_id)
        else:
            self.selection_cleared.emit()

    def _emit_hover_clear(self) -> None:
        if self._last_hover_id:
            self._last_hover_id = ''
            self.element_hovered.emit('')

    # ── Minimap ───────────────────────────────────────────────────────────

    def _update_minimap(self) -> None:
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        total = self.sceneRect()
        if total.width() <= 0 or total.height() <= 0:
            self._minimap.setVisible(False)
            return
        show = not (visible.width() >= total.width() * 0.95
                    and visible.height() >= total.height() * 0.95)
        self._minimap.setVisible(show)
        if show:
            self._minimap.update_viewport(visible, total)

    def _reposition_minimap(self) -> None:
        vp = self.viewport().geometry()
        self._minimap.move(max(vp.left(), vp.right() - self._minimap.width() - 8),
                           vp.top() + 8)
        self._minimap.raise_()

    def _on_minimap_navigate(self, norm: QPointF) -> None:
        total = self.sceneRect()
        self.centerOn(total.x() + norm.x() * total.width(),
                      total.y() + norm.y() * total.height())
        self._update_minimap()
