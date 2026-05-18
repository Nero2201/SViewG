from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QByteArray, QPointF, QRectF
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsScene

from app.model.svg_document import SvgDocument
from app.settings import SelectionStyle


class SvgScene(QGraphicsScene):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc: Optional[SvgDocument] = None
        self._renderer: Optional[QSvgRenderer] = None
        self._svg_item: Optional[QGraphicsSvgItem] = None
        self._highlight_item: Optional[QGraphicsRectItem] = None
        self._hover_item: Optional[QGraphicsRectItem] = None
        self._style = SelectionStyle()
        self._current_highlight_id: Optional[str] = None

    def load_svg(self, svg_bytes: bytes, doc: SvgDocument) -> None:
        self.clear()
        self._highlight_item = None
        self._hover_item = None
        self._current_highlight_id = None
        self._doc = doc

        self._renderer = QSvgRenderer(QByteArray(svg_bytes))
        self._svg_item = QGraphicsSvgItem()
        self._svg_item.setSharedRenderer(self._renderer)
        self._svg_item.setPos(0, 0)
        self.addItem(self._svg_item)
        self.setSceneRect(self._svg_item.boundingRect())

    def clear_document(self) -> None:
        self.clear()
        self._highlight_item = None
        self._hover_item = None
        self._current_highlight_id = None
        self._doc = None
        self._renderer = None
        self._svg_item = None

    def set_style(self, style: SelectionStyle) -> None:
        self._style = style
        if self._current_highlight_id:
            self.highlight_element(self._current_highlight_id)

    # ── Selection overlay ─────────────────────────────────────────────────

    def highlight_element(self, element_id: str) -> None:
        self._remove_item(self._highlight_item)
        self._highlight_item = None
        if self._renderer is None or self._svg_item is None:
            return
        bounds = self._renderer.boundsOnElement(element_id)
        if bounds.isNull() or (bounds.width() == 0 and bounds.height() == 0):
            return

        c = QColor(self._style.color)
        c.setAlpha(self._style.opacity)
        b = QColor(self._style.color)
        b.setAlpha(220)

        item = QGraphicsRectItem(bounds, self._svg_item)
        item.setBrush(QBrush(c))
        pen = QPen(b, self._style.border_width)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setZValue(10)
        self._highlight_item = item
        self._current_highlight_id = element_id

    def clear_highlight(self) -> None:
        self._remove_item(self._highlight_item)
        self._highlight_item = None
        self._current_highlight_id = None

    # ── Hover overlay ─────────────────────────────────────────────────────

    def set_hover_element(self, element_id: Optional[str]) -> None:
        self._remove_item(self._hover_item)
        self._hover_item = None
        if element_id is None or self._renderer is None or self._svg_item is None:
            return
        bounds = self._renderer.boundsOnElement(element_id)
        if bounds.isNull() or (bounds.width() == 0 and bounds.height() == 0):
            return

        hc = QColor(self._style.hover_color)
        hc.setAlpha(self._style.hover_opacity)
        hb = QColor(self._style.hover_color)
        hb.setAlpha(220)

        item = QGraphicsRectItem(bounds, self._svg_item)
        item.setBrush(QBrush(hc))
        pen = QPen(hb, self._style.hover_border_width)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setZValue(9)
        self._hover_item = item

    # ── Hit test ──────────────────────────────────────────────────────────

    def element_at_item_pos(self, item_pos: QPointF) -> Optional[str]:
        if self._renderer is None or self._doc is None:
            return None
        best_id: Optional[str] = None
        best_area = float('inf')
        for eid in self._doc.element_ids:
            bounds: QRectF = self._renderer.boundsOnElement(eid)
            if bounds.isNull():
                continue
            if bounds.contains(item_pos):
                area = bounds.width() * bounds.height()
                if area < best_area:
                    best_area = area
                    best_id = eid
        return best_id

    # ── Helpers ───────────────────────────────────────────────────────────

    def _remove_item(self, item: Optional[QGraphicsRectItem]) -> None:
        if item is not None:
            s = item.scene()
            if s:
                s.removeItem(item)

    @property
    def renderer(self) -> Optional[QSvgRenderer]:
        return self._renderer

    @property
    def svg_item(self) -> Optional[QGraphicsSvgItem]:
        return self._svg_item
