from __future__ import annotations

import os
import sys
from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence, QMouseEvent
from PyQt6.QtWidgets import (QFileDialog, QInputDialog, QLabel, QMainWindow,
                              QMessageBox, QSizePolicy, QSplitter, QStatusBar,
                              QToolBar, QVBoxLayout, QWidget)

from app.editor.svg_editor import SvgEditor
from app.i18n import set_language, tr
from app.model.svg_document import SvgDocument
from app.settings import AppPrefs, SelectionStyle, SettingsDialog, load_prefs, save_prefs
from app.viewer.svg_viewer import SvgViewer


class _ZoomLabel(QLabel):
    zoom_set = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__('100%', parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr('zoom_tooltip'))
        self.setStyleSheet('padding:0 10px; color:#CCC;')

    def set_zoom(self, factor: float) -> None:
        self.setText(f'{factor * 100:.0f}%')

    def mouseDoubleClickEvent(self, _event: QMouseEvent) -> None:
        try:
            current = float(self.text().rstrip('%'))
        except ValueError:
            current = 100.0
        value, ok = QInputDialog.getInt(
            self, tr('dlg_zoom_title'), tr('dlg_zoom_label'), int(current), 1, 5000, 10
        )
        if ok:
            self.zoom_set.emit(value / 100.0)


def _panel(label_text: str, widget: QWidget) -> tuple[QWidget, QLabel]:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    header = QLabel(label_text)
    header.setStyleSheet(
        'background:#2D2D2D; color:#CCCCCC; padding:4px 8px; font-size:11px;'
        'border-bottom:1px solid #444;'
    )
    layout.addWidget(header)
    layout.addWidget(widget)
    return container, header


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('SViewG')
        self.resize(1280, 800)

        self._doc: Optional[SvgDocument] = None
        self._filepath: str = ''
        self._updating = False
        self._style, self._prefs = load_prefs()
        self._selected_elem = ''

        set_language(self._prefs.language)

        self._editor = SvgEditor()
        self._viewer = SvgViewer()

        editor_panel, self._header_source = _panel(tr('panel_source'), self._editor)
        viewer_panel, self._header_preview = _panel(tr('panel_preview'), self._viewer)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(editor_panel)
        splitter.addWidget(viewer_panel)
        splitter.setSizes([480, 800])
        splitter.setHandleWidth(3)
        self.setCentralWidget(splitter)

        self._build_actions()
        self._build_toolbar()
        self._build_menu()
        self._build_statusbar()
        self._connect_signals()

        self._editor.set_style(self._style)
        self._viewer.set_style(self._style)
        self._editor.set_single_click_select(self._prefs.single_click_select)
        self._viewer.set_single_click_select(self._prefs.single_click_select)

        self.setStyleSheet('QMainWindow { background: #1E1E1E; }')
        self.setAcceptDrops(True)

    # ── Actions ───────────────────────────────────────────────────────────

    def _build_actions(self) -> None:
        self._act_open = QAction(tr('action_open'), self)
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_open.triggered.connect(self._on_open)

        self._act_reload = QAction(tr('action_reload'), self)
        self._act_reload.setShortcut(QKeySequence('Ctrl+R'))
        self._act_reload.triggered.connect(self._on_reload)
        self._act_reload.setEnabled(False)

        self._act_close_file = QAction(tr('action_close'), self)
        self._act_close_file.setShortcut(QKeySequence('Ctrl+W'))
        self._act_close_file.triggered.connect(self._on_close_file)
        self._act_close_file.setEnabled(False)

        self._act_fit = QAction(tr('zoom_fit'), self)
        self._act_fit.setShortcut(QKeySequence('Ctrl+0'))
        self._act_fit.triggered.connect(self._viewer.fit_to_window)

        self._act_zoomin = QAction(tr('zoom_in'), self)
        self._act_zoomin.setShortcut(QKeySequence('Ctrl++'))
        self._act_zoomin.triggered.connect(self._viewer.zoom_in)

        self._act_zoomout = QAction(tr('zoom_out'), self)
        self._act_zoomout.setShortcut(QKeySequence('Ctrl+-'))
        self._act_zoomout.triggered.connect(self._viewer.zoom_out)

        self._act_settings = QAction(tr('action_settings'), self)
        self._act_settings.setShortcut(QKeySequence('Ctrl+,'))
        self._act_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        self._act_settings.triggered.connect(self._on_settings)
        self.addAction(self._act_settings)

        self._act_hover_viewer = QAction(tr('hover_viewer_code'), self)
        self._act_hover_viewer.setCheckable(True)
        self._act_hover_viewer.setChecked(self._prefs.hover_on_viewer)
        self._act_hover_viewer.triggered.connect(self._on_prefs_changed)

        self._act_hover_code = QAction(tr('hover_code_viewer'), self)
        self._act_hover_code.setCheckable(True)
        self._act_hover_code.setChecked(self._prefs.hover_on_code)
        self._act_hover_code.triggered.connect(self._on_prefs_changed)

        self._act_single_click = QAction(tr('single_click'), self)
        self._act_single_click.setCheckable(True)
        self._act_single_click.setChecked(self._prefs.single_click_select)
        self._act_single_click.setShortcut(QKeySequence('Ctrl+K'))
        self._act_single_click.triggered.connect(self._on_prefs_changed)

        act_clear = QAction(self)
        act_clear.setShortcut(QKeySequence('Ctrl+D'))
        act_clear.triggered.connect(self._clear_all)
        self.addAction(act_clear)

    # ── Toolbar ───────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        tb = QToolBar('Main')
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setStyleSheet(
            'QToolBar { background:#2D2D2D; border-bottom:1px solid #444; spacing:4px; }'
            'QToolButton { color:#D4D4D4; padding:4px 10px; border-radius:3px; }'
            'QToolButton:hover { background:#3E3E3E; }'
            'QToolButton:pressed { background:#007ACC; }'
        )
        self.addToolBar(tb)

        tb.addAction(self._act_open)
        tb.addAction(self._act_reload)
        tb.addSeparator()
        tb.addAction(self._act_fit)
        tb.addAction(self._act_zoomin)
        tb.addAction(self._act_zoomout)

        if sys.platform == 'darwin':
            tb.hide()  # On macOS, main actions are in the menu bar, so hide the toolbar

    # ── Menus ─────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()
        mb.setNativeMenuBar(True)

        self._file_menu = mb.addMenu(tr('menu_file'))
        self._file_menu.addAction(self._act_open)
        self._file_menu.addAction(self._act_reload)
        self._file_menu.addSeparator()
        self._file_menu.addAction(self._act_close_file)
        # On non-macOS, settings stays here; on macOS PreferencesRole moves it to app menu
        if sys.platform != 'darwin':
            self._file_menu.addSeparator()
            self._file_menu.addAction(self._act_settings)

        self._view_menu = mb.addMenu(tr('menu_view'))
        self._view_menu.addAction(self._act_hover_viewer)
        self._view_menu.addAction(self._act_hover_code)
        self._view_menu.addSeparator()
        self._view_menu.addAction(self._act_single_click)

        self._zoom_menu = mb.addMenu(tr('menu_zoom'))
        self._zoom_menu.addAction(self._act_fit)
        self._zoom_menu.addSeparator()
        self._zoom_menu.addAction(self._act_zoomin)
        self._zoom_menu.addAction(self._act_zoomout)

    # ── Status bar ────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        sb.setStyleSheet('QStatusBar { background:#2D2D2D; color:#999; font-size:11px; }')
        self.setStatusBar(sb)

        self._lbl_file = QLabel(tr('no_file'))
        self._lbl_file.setStyleSheet('padding:0 8px;')
        self._lbl_elem = QLabel('')
        self._lbl_elem.setStyleSheet('padding:0 8px;')
        self._zoom_label = _ZoomLabel()
        self._zoom_label.zoom_set.connect(self._viewer.set_zoom_factor)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sb.addWidget(self._lbl_file)
        sb.addWidget(spacer)
        sb.addPermanentWidget(self._lbl_elem)
        sb.addPermanentWidget(self._zoom_label)

    # ── Retranslate ───────────────────────────────────────────────────────

    def _retranslate_ui(self) -> None:
        self._act_open.setText(tr('action_open'))
        self._act_reload.setText(tr('action_reload'))
        self._act_close_file.setText(tr('action_close'))
        self._act_fit.setText(tr('zoom_fit'))
        self._act_zoomin.setText(tr('zoom_in'))
        self._act_zoomout.setText(tr('zoom_out'))
        self._act_settings.setText(tr('action_settings'))
        self._act_hover_viewer.setText(tr('hover_viewer_code'))
        self._act_hover_code.setText(tr('hover_code_viewer'))
        self._act_single_click.setText(tr('single_click'))
        self._file_menu.setTitle(tr('menu_file'))
        self._view_menu.setTitle(tr('menu_view'))
        self._zoom_menu.setTitle(tr('menu_zoom'))
        self._header_source.setText(tr('panel_source'))
        self._header_preview.setText(tr('panel_preview'))
        self._zoom_label.setToolTip(tr('zoom_tooltip'))
        if not self._filepath:
            self._lbl_file.setText(tr('no_file'))
        if self._doc and not self._selected_elem:
            self._lbl_elem.setText(tr('n_elements').format(n=len(self._doc.element_ids)))

    # ── Signals ───────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._editor.element_selected.connect(self._on_editor_element_selected)
        self._editor.element_hovered.connect(self._on_editor_hover)
        self._editor.selection_cleared.connect(self._clear_all)
        self._viewer.element_selected.connect(self._on_viewer_element_selected)
        self._viewer.element_hovered.connect(self._on_viewer_hover)
        self._viewer.selection_cleared.connect(self._clear_all)
        self._viewer.zoom_changed.connect(self._zoom_label.set_zoom)

    # ── File loading ──────────────────────────────────────────────────────

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr('dlg_open_title'), '', tr('dlg_open_filter')
        )
        if path:
            self.load_document(path)

    def _on_reload(self) -> None:
        if self._filepath:
            self.load_document(self._filepath)

    def _on_close_file(self) -> None:
        self._doc = None
        self._filepath = ''
        self._selected_elem = ''
        self._editor.clear()
        self._viewer.unload()
        self.setWindowTitle('SViewG')
        self._lbl_file.setText(tr('no_file'))
        self._lbl_elem.setText('')
        self._act_reload.setEnabled(False)
        self._act_close_file.setEnabled(False)

    def load_document(self, filepath: str) -> None:
        try:
            doc = SvgDocument()
            doc.load(filepath)
        except Exception as exc:
            QMessageBox.critical(self, tr('dlg_error_title'),
                                 tr('dlg_error_load').format(exc=exc))
            return

        self._doc = doc
        self._filepath = filepath
        self._selected_elem = ''

        self._editor.set_document(doc)
        self._viewer.load_svg(doc.get_svg_bytes(), doc)

        name = os.path.basename(filepath)
        self.setWindowTitle(f'SViewG — {name}')
        self._lbl_file.setText(name)
        self._zoom_label.set_zoom(self._viewer.current_zoom())
        self._lbl_elem.setText(tr('n_elements').format(n=len(doc.element_ids)))
        self._act_reload.setEnabled(True)
        self._act_close_file.setEnabled(True)

    # ── Settings ──────────────────────────────────────────────────────────

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._style, self._prefs, self)
        if dlg.exec():
            self._style = dlg.result_style()
            new_prefs = dlg.result_prefs()
            lang_changed = new_prefs.language != self._prefs.language
            self._prefs.language = new_prefs.language
            self._editor.set_style(self._style)
            self._viewer.set_style(self._style)
            if lang_changed:
                set_language(self._prefs.language)
                self._retranslate_ui()

    def _on_prefs_changed(self) -> None:
        self._prefs.hover_on_viewer = self._act_hover_viewer.isChecked()
        self._prefs.hover_on_code = self._act_hover_code.isChecked()
        self._prefs.single_click_select = self._act_single_click.isChecked()
        self._editor.set_single_click_select(self._prefs.single_click_select)
        self._viewer.set_single_click_select(self._prefs.single_click_select)

    def closeEvent(self, event) -> None:
        save_prefs(self._style, self._prefs)
        super().closeEvent(event)

    # ── Hover handlers ────────────────────────────────────────────────────

    def _on_viewer_hover(self, elem_id: str) -> None:
        if elem_id and self._prefs.hover_on_viewer:
            self._viewer.set_hover_element(elem_id)
            self._editor.set_hover_element(elem_id)
        else:
            self._viewer.set_hover_element(None)
            self._editor.set_hover_element(None)
        self._update_status_hover(elem_id)

    def _on_editor_hover(self, elem_id: str) -> None:
        if elem_id and self._prefs.hover_on_code:
            self._editor.set_hover_element(elem_id)
            self._viewer.set_hover_element(elem_id)
        else:
            self._editor.set_hover_element(None)
            self._viewer.set_hover_element(None)
        self._update_status_hover(elem_id)

    def _update_status_hover(self, elem_id: str) -> None:
        if elem_id:
            self._lbl_elem.setText(elem_id)
        elif self._selected_elem:
            self._lbl_elem.setText(self._selected_elem)
        elif self._doc:
            self._lbl_elem.setText(tr('n_elements').format(n=len(self._doc.element_ids)))
        else:
            self._lbl_elem.setText('')

    # ── Selection ─────────────────────────────────────────────────────────

    def _clear_all(self) -> None:
        self._selected_elem = ''
        self._editor.clear_highlight()
        self._viewer.clear_highlight()
        if self._doc:
            self._lbl_elem.setText(tr('n_elements').format(n=len(self._doc.element_ids)))

    def _on_editor_element_selected(self, element_id: str) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._selected_elem = element_id
            self._editor.highlight_element(element_id)
            self._viewer.highlight_element(element_id)
            self._viewer.center_on_element(element_id)
            self._lbl_elem.setText(element_id)
        finally:
            self._updating = False

    def _on_viewer_element_selected(self, element_id: str) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._selected_elem = element_id
            self._editor.highlight_element(element_id)
            self._viewer.highlight_element(element_id)
            self._lbl_elem.setText(element_id)
        finally:
            self._updating = False

    # ── Drag & Drop ───────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith(('.svg', '.svgz'))
            for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.svg', '.svgz')):
                self.load_document(path)
                break
