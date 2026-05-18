from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                              QDoubleSpinBox, QFormLayout, QGroupBox,
                              QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                              QSlider, QVBoxLayout, QWidget)

from app.i18n import LANGUAGE_NAMES, tr


@dataclass
class SelectionStyle:
    color: QColor = field(default_factory=lambda: QColor(255, 165, 0))
    border_width: float = 2.0
    opacity: int = 70
    hover_color: QColor = field(default_factory=lambda: QColor(100, 149, 237))
    hover_border_width: float = 1.0
    hover_opacity: int = 45


@dataclass
class AppPrefs:
    hover_on_viewer: bool = True
    hover_on_code: bool = True
    single_click_select: bool = False
    language: str = 'de'


def save_prefs(style: SelectionStyle, prefs: AppPrefs) -> None:
    s = QSettings('SViewG', 'SViewG')
    s.setValue('style/color', style.color.name())
    s.setValue('style/border_width', style.border_width)
    s.setValue('style/opacity', style.opacity)
    s.setValue('style/hover_color', style.hover_color.name())
    s.setValue('style/hover_border_width', style.hover_border_width)
    s.setValue('style/hover_opacity', style.hover_opacity)
    s.setValue('prefs/hover_on_viewer', prefs.hover_on_viewer)
    s.setValue('prefs/hover_on_code', prefs.hover_on_code)
    s.setValue('prefs/single_click_select', prefs.single_click_select)
    s.setValue('prefs/language', prefs.language)


def load_prefs() -> tuple[SelectionStyle, AppPrefs]:
    s = QSettings('SViewG', 'SViewG')
    style = SelectionStyle(
        color=QColor(s.value('style/color', QColor(255, 165, 0).name())),
        border_width=float(s.value('style/border_width', 2.0)),
        opacity=int(s.value('style/opacity', 70)),
        hover_color=QColor(s.value('style/hover_color', QColor(100, 149, 237).name())),
        hover_border_width=float(s.value('style/hover_border_width', 1.0)),
        hover_opacity=int(s.value('style/hover_opacity', 45)),
    )
    prefs = AppPrefs(
        hover_on_viewer=s.value('prefs/hover_on_viewer', True, type=bool),
        hover_on_code=s.value('prefs/hover_on_code', True, type=bool),
        single_click_select=s.value('prefs/single_click_select', False, type=bool),
        language=s.value('prefs/language', 'de'),
    )
    return style, prefs


# ── Widgets ───────────────────────────────────────────────────────────────

class _ColorButton(QPushButton):
    def __init__(self, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self._refresh()
        self.clicked.connect(self._pick)
        self.setFixedWidth(80)

    def color(self) -> QColor:
        return self._color

    def set_color(self, c: QColor) -> None:
        self._color = c
        self._refresh()

    def _refresh(self) -> None:
        self.setStyleSheet(
            f'QPushButton {{ background:{self._color.name()}; border:1px solid #555;'
            f' border-radius:3px; min-height:22px; }}'
        )

    def _pick(self) -> None:
        c = QColorDialog.getColor(self._color, self, tr('dlg_color_pick'))
        if c.isValid():
            self.set_color(c)


def _opacity_row(slider_ref: list, label_ref: list, initial: int) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 255)
    slider.setValue(initial)
    lbl = QLabel(f'{int(initial / 255 * 100)}%')
    lbl.setFixedWidth(34)
    slider_ref.append(slider)
    label_ref.append(lbl)
    layout.addWidget(slider)
    layout.addWidget(lbl)
    return row


class _Preview(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._style = SelectionStyle()
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def update_style(self, style: SelectionStyle) -> None:
        self._style = style
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#1E1E1E'))
        w = self.width()

        hr = self.rect().adjusted(8, 8, -w // 2 - 4, -8)
        hc = QColor(self._style.hover_color)
        hc.setAlpha(self._style.hover_opacity)
        p.fillRect(hr, hc)
        hb = QColor(self._style.hover_color)
        hb.setAlpha(200)
        p.setPen(QPen(hb, self._style.hover_border_width))
        p.drawRect(hr)

        sr = self.rect().adjusted(w // 2 + 4, 8, -8, -8)
        sc = QColor(self._style.color)
        sc.setAlpha(self._style.opacity)
        p.fillRect(sr, sc)
        sb = QColor(self._style.color)
        sb.setAlpha(220)
        p.setPen(QPen(sb, self._style.border_width))
        p.drawRect(sr)

        p.setPen(QColor('#666'))
        p.setFont(self.font())
        p.drawText(hr, Qt.AlignmentFlag.AlignCenter, tr('preview_hover'))
        p.drawText(sr, Qt.AlignmentFlag.AlignCenter, tr('preview_sel'))


class SettingsDialog(QDialog):
    def __init__(self, style: SelectionStyle, prefs: AppPrefs, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr('settings_title'))
        self.setMinimumWidth(340)

        self._prefs = prefs
        self._style = SelectionStyle(
            color=QColor(style.color),
            border_width=style.border_width,
            opacity=style.opacity,
            hover_color=QColor(style.hover_color),
            hover_border_width=style.hover_border_width,
            hover_opacity=style.hover_opacity,
        )

        layout = QVBoxLayout(self)

        # ── Selection ─────────────────────────────────────────────────────
        grp_sel = QGroupBox(tr('grp_selection'))
        form_sel = QFormLayout(grp_sel)
        form_sel.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._sel_color = _ColorButton(self._style.color)
        self._sel_color.clicked.connect(self._refresh)
        form_sel.addRow(tr('lbl_color'), self._sel_color)

        self._sel_border = QDoubleSpinBox()
        self._sel_border.setRange(0.5, 20.0)
        self._sel_border.setSingleStep(0.5)
        self._sel_border.setDecimals(1)
        self._sel_border.setValue(self._style.border_width)
        self._sel_border.setSuffix(' px')
        self._sel_border.valueChanged.connect(self._refresh)
        form_sel.addRow(tr('lbl_border'), self._sel_border)

        self._sel_op_s, self._sel_op_l = [], []
        form_sel.addRow(tr('lbl_opacity'),
                        _opacity_row(self._sel_op_s, self._sel_op_l, self._style.opacity))
        self._sel_op_s[0].valueChanged.connect(self._on_sel_opacity)
        layout.addWidget(grp_sel)

        # ── Hover ──────────────────────────────────────────────────────────
        grp_hov = QGroupBox(tr('grp_hover'))
        form_hov = QFormLayout(grp_hov)
        form_hov.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._hov_color = _ColorButton(self._style.hover_color)
        self._hov_color.clicked.connect(self._refresh)
        form_hov.addRow(tr('lbl_color'), self._hov_color)

        self._hov_border = QDoubleSpinBox()
        self._hov_border.setRange(0.5, 20.0)
        self._hov_border.setSingleStep(0.5)
        self._hov_border.setDecimals(1)
        self._hov_border.setValue(self._style.hover_border_width)
        self._hov_border.setSuffix(' px')
        self._hov_border.valueChanged.connect(self._refresh)
        form_hov.addRow(tr('lbl_border'), self._hov_border)

        self._hov_op_s, self._hov_op_l = [], []
        form_hov.addRow(tr('lbl_opacity'),
                        _opacity_row(self._hov_op_s, self._hov_op_l, self._style.hover_opacity))
        self._hov_op_s[0].valueChanged.connect(self._on_hov_opacity)
        layout.addWidget(grp_hov)

        # ── General ────────────────────────────────────────────────────────
        grp_gen = QGroupBox(tr('grp_general'))
        form_gen = QFormLayout(grp_gen)
        form_gen.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._lang_combo = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self._lang_combo.addItem(name, code)
        idx = self._lang_combo.findData(prefs.language)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        form_gen.addRow(tr('lbl_language'), self._lang_combo)
        layout.addWidget(grp_gen)

        # ── Preview ────────────────────────────────────────────────────────
        grp_pre = QGroupBox(tr('grp_preview'))
        QVBoxLayout(grp_pre).addWidget(self._mk_preview())
        layout.addWidget(grp_pre)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _mk_preview(self) -> _Preview:
        self._preview = _Preview()
        self._preview.update_style(self._style)
        return self._preview

    def _refresh(self) -> None:
        self._style.color = QColor(self._sel_color.color())
        self._style.border_width = self._sel_border.value()
        self._style.hover_color = QColor(self._hov_color.color())
        self._style.hover_border_width = self._hov_border.value()
        self._preview.update_style(self._style)

    def _on_sel_opacity(self, v: int) -> None:
        self._style.opacity = v
        self._sel_op_l[0].setText(f'{int(v / 255 * 100)}%')
        self._refresh()

    def _on_hov_opacity(self, v: int) -> None:
        self._style.hover_opacity = v
        self._hov_op_l[0].setText(f'{int(v / 255 * 100)}%')
        self._refresh()

    def result_style(self) -> SelectionStyle:
        return self._style

    def result_prefs(self) -> AppPrefs:
        return dataclasses.replace(self._prefs, language=self._lang_combo.currentData())
