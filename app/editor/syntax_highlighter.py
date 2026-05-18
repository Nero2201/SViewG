from __future__ import annotations

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
                          QTextDocument)


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class SvgSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        tag_fmt = _fmt('#569CD6')           # blue  — tag names
        bracket_fmt = _fmt('#808080')       # gray  — < > </ />
        attr_fmt = _fmt('#9CDCFE')          # light blue — attribute names
        value_fmt = _fmt('#CE9178')         # orange — attribute values
        comment_fmt = _fmt('#6A9955', italic=True)  # green — comments
        decl_fmt = _fmt('#C586C0')          # purple — <?xml ... ?>
        entity_fmt = _fmt('#4EC9B0')        # teal  — &entities;

        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            # Processing instructions  <?...?>
            (QRegularExpression(r'<\?[^?]*\?>'), decl_fmt),
            # Comments  <!--...-->
            (QRegularExpression(r'<!--.*?-->'), comment_fmt),
            # Attribute values  "..." or '...'
            (QRegularExpression(r'"[^"]*"'), value_fmt),
            (QRegularExpression(r"'[^']*'"), value_fmt),
            # Tag brackets  <  </  >  />
            (QRegularExpression(r'</|/>|<|>'), bracket_fmt),
            # Tag names  (word after < or </)
            (QRegularExpression(r'(?<=</?)[A-Za-z][\w:.-]*'), tag_fmt),
            # Attribute names  (word before =)
            (QRegularExpression(r'\b[A-Za-z][\w:.-]*(?=\s*=)'), attr_fmt),
            # XML entities  &name;  &#123;
            (QRegularExpression(r'&(?:#\d+|#x[\da-fA-F]+|[\w.:-]+);'), entity_fmt),
        ]

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
