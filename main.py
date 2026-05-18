from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QFileOpenEvent
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


class _App(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self._window: MainWindow | None = None
        self._pending: str = ''

    def set_window(self, window: MainWindow) -> None:
        self._window = window
        if self._pending:
            window.load_document(self._pending)
            self._pending = ''

    def event(self, e: QEvent) -> bool:
        if isinstance(e, QFileOpenEvent):
            path = e.file()
            if path:
                if self._window:
                    self._window.load_document(path)
                else:
                    self._pending = path
        return super().event(e)


def main() -> None:
    if sys.version_info < (3, 9):
        print('SViewG requires Python 3.9 or newer.', file=sys.stderr)
        sys.exit(1)

    app = _App(sys.argv)
    app.setApplicationName('SViewG')
    app.setOrganizationName('SViewG')

    window = MainWindow()
    app.set_window(window)
    window.show()

    if len(sys.argv) > 1:
        window.load_document(sys.argv[1])

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
