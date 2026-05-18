from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QMouseEvent, QPaintEvent, QPainter,
                          QPalette, QPolygonF, QResizeEvent, QTextCharFormat,
                          QTextCursor)
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from app.editor.syntax_highlighter import SvgSyntaxHighlighter
from app.model.svg_document import SvgDocument
from app.settings import SelectionStyle


class FoldGutter(QWidget):
    fold_toggled = pyqtSignal(int)
    _WIDTH = 18

    def __init__(self, editor: 'SvgEditor') -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._WIDTH, 0)

    def paintEvent(self, _event: QPaintEvent) -> None:
        editor = self._editor
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#252526'))
        if editor._doc is None:
            return
        fold_starts = editor._doc.get_fold_starts()
        folded = editor._folded
        block = editor.firstVisibleBlock()
        top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
        while block.isValid() and top <= self.rect().bottom():
            h = editor.blockBoundingRect(block).height()
            if block.isVisible() and top + h >= self.rect().top():
                eid = fold_starts.get(block.blockNumber())
                if eid is not None:
                    cy = top + h / 2
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor('#858585'))
                    if eid in folded:
                        p.drawPolygon(QPolygonF([
                            QPointF(5, cy - 4), QPointF(13, cy), QPointF(5, cy + 4)
                        ]))
                    else:
                        p.drawPolygon(QPolygonF([
                            QPointF(4, cy - 3), QPointF(14, cy - 3), QPointF(9, cy + 4)
                        ]))
            top += h
            block = block.next()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._editor._doc is None:
            return
        y = event.pos().y()
        block = self._editor.firstVisibleBlock()
        top = self._editor.blockBoundingGeometry(block).translated(
            self._editor.contentOffset()).top()
        while block.isValid():
            h = self._editor.blockBoundingRect(block).height()
            if block.isVisible() and top <= y < top + h:
                self.fold_toggled.emit(block.blockNumber())
                break
            top += h
            block = block.next()


class SvgEditor(QPlainTextEdit):
    element_selected = pyqtSignal(str)
    element_hovered = pyqtSignal(str)   # "" = no element
    selection_cleared = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc: Optional[SvgDocument] = None
        self._highlighter: Optional[SvgSyntaxHighlighter] = None
        self._style = SelectionStyle()
        self._folded: set[str] = set()
        self._active_id: Optional[str] = None
        self._hover_id: Optional[str] = None
        self._last_hover_id = ''
        self._single_click_select = False

        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMouseTracking(True)

        font = QFont()
        font.setFamilies(['Menlo', 'Consolas', 'Courier New'])
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.setFont(font)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor('#1E1E1E'))
        palette.setColor(QPalette.ColorRole.Text, QColor('#D4D4D4'))
        self.setPalette(palette)

        self._gutter = FoldGutter(self)
        self._gutter.fold_toggled.connect(self._on_fold_toggled)
        self.updateRequest.connect(self._on_update_request)
        self.blockCountChanged.connect(self._update_gutter_width)
        self._update_gutter_width()

    # ── Document ──────────────────────────────────────────────────────────

    def set_document(self, doc: SvgDocument) -> None:
        self._doc = doc
        self._folded.clear()
        self._active_id = None
        self._hover_id = None
        self._last_hover_id = ''
        self.setPlainText(doc.get_formatted_text())
        if self._highlighter is None:
            self._highlighter = SvgSyntaxHighlighter(self.document())
        else:
            self._highlighter.setDocument(self.document())
        self._gutter.update()

    def clear(self) -> None:
        self._doc = None
        self._folded.clear()
        self._active_id = None
        self._hover_id = None
        self._last_hover_id = ''
        self.setPlainText('')
        self._gutter.update()

    # ── Style / Behavior ──────────────────────────────────────────────────

    def set_style(self, style: SelectionStyle) -> None:
        self._style = style
        self._update_extra_selections()

    def set_single_click_select(self, enabled: bool) -> None:
        self._single_click_select = enabled

    # ── Highlight API ─────────────────────────────────────────────────────

    def highlight_element(self, element_id: str) -> None:
        self._active_id = element_id
        self._update_extra_selections()
        rng = self._doc.get_element_range(element_id) if self._doc else None
        if rng:
            block = self.document().findBlockByLineNumber(rng[0])
            if block.isValid():
                self.setTextCursor(QTextCursor(block))
                self.ensureCursorVisible()

    def clear_highlight(self) -> None:
        self._active_id = None
        self._update_extra_selections()

    def set_hover_element(self, element_id: Optional[str]) -> None:
        self._hover_id = element_id
        self._update_extra_selections()

    # ── Extra selections ──────────────────────────────────────────────────

    def _update_extra_selections(self) -> None:
        sels = []
        if self._active_id:
            s = self._make_sel(self._active_id, self._style.color, self._style.opacity)
            if s:
                sels.append(s)
        if self._hover_id and self._hover_id != self._active_id:
            s = self._make_sel(self._hover_id,
                               self._style.hover_color, self._style.hover_opacity)
            if s:
                sels.append(s)
        self.setExtraSelections(sels)

    def _make_sel(self, eid: str, color: QColor,
                  opacity: int) -> Optional[QTextEdit.ExtraSelection]:
        if not self._doc:
            return None
        rng = self._doc.get_element_range(eid)
        if rng is None:
            return None
        start_line, end_line = rng
        qdoc = self.document()
        sb = qdoc.findBlockByLineNumber(start_line)
        if not sb.isValid():
            return None
        eb = qdoc.findBlockByLineNumber(end_line)
        if not eb.isValid():
            eb = sb
        cursor = QTextCursor(sb)
        cursor.setPosition(eb.position() + max(0, eb.length() - 1),
                           QTextCursor.MoveMode.KeepAnchor)
        bg = QColor(color)
        bg.setAlpha(opacity)
        fmt = QTextCharFormat()
        fmt.setBackground(bg)
        fmt.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        sel = QTextEdit.ExtraSelection()
        sel.format = fmt
        sel.cursor = cursor
        return sel

    # ── Folding ───────────────────────────────────────────────────────────

    def _on_fold_toggled(self, line: int) -> None:
        if self._doc is None:
            return
        eid = self._doc.get_fold_starts().get(line)
        if eid is None:
            return
        if eid in self._folded:
            self._folded.discard(eid)
        else:
            self._folded.add(eid)
        self._apply_fold_state()

    def _apply_fold_state(self) -> None:
        if self._doc is None:
            return
        qdoc = self.document()
        block = qdoc.begin()
        while block.isValid():
            block.setVisible(True)
            block = block.next()
        for eid in self._folded:
            rng = self._doc.get_element_range(eid)
            if rng:
                for ln in range(rng[0] + 1, rng[1] + 1):
                    b = qdoc.findBlockByNumber(ln)
                    if b.isValid():
                        b.setVisible(False)
        qdoc.markContentsDirty(0, qdoc.characterCount())
        self.viewport().update()
        self._gutter.update()

    # ── Gutter geometry ───────────────────────────────────────────────────

    def _update_gutter_width(self) -> None:
        self.setViewportMargins(FoldGutter._WIDTH, 0, 0, 0)

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), FoldGutter._WIDTH, cr.height()))

    # ── Mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if not self._single_click_select and self._active_id is not None:
            self.clear_highlight()
            self.selection_cleared.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if self._single_click_select and event.button() == Qt.MouseButton.LeftButton:
            self._handle_select(event.pos())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)
        if not self._single_click_select and self._doc is not None:
            line = self.cursorForPosition(event.pos()).blockNumber()
            elem_id = self._doc.get_id_at_line(line)
            if elem_id:
                self.highlight_element(elem_id)
                self.element_selected.emit(elem_id)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self._doc is None:
            return
        line = self.cursorForPosition(event.pos()).blockNumber()
        elem_id = self._doc.get_id_at_line(line) or ''
        if elem_id != self._last_hover_id:
            self._last_hover_id = elem_id
            self.element_hovered.emit(elem_id)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._last_hover_id:
            self._last_hover_id = ''
            self.element_hovered.emit('')

    def _handle_select(self, pos) -> None:
        if self._doc is None:
            return
        line = self.cursorForPosition(pos).blockNumber()
        elem_id = self._doc.get_id_at_line(line)
        if elem_id:
            self.highlight_element(elem_id)
            self.element_selected.emit(elem_id)
        elif self._active_id is not None:
            self.clear_highlight()
            self.selection_cleared.emit()
