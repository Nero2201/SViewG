from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ElementTextRange:
    element_id: str
    start_line: int
    end_line: int


_OPEN_TAG_RE = re.compile(r'^\s*<([A-Za-z][\w:.-]*)')
_CLOSE_TAG_RE = re.compile(r'^\s*</([A-Za-z][\w:.-]*)')
_SELF_CLOSE_RE = re.compile(r'/>\s*$')
_ID_RE = re.compile(r'\bid=["\']([^"\']+)["\']')

_COMMON_NS = {
    '': 'http://www.w3.org/2000/svg',
    'xlink': 'http://www.w3.org/1999/xlink',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cc': 'http://creativecommons.org/ns#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd',
}

_auto_id_seq = 0


class SvgDocument:
    def __init__(self) -> None:
        self._formatted_text: str = ''
        self._svg_bytes: bytes = b''
        self._id_to_range: dict[str, ElementTextRange] = {}
        self._line_to_id: dict[int, str] = {}
        self._element_ids: list[str] = []
        self._filepath: str = ''

    def load(self, filepath: str) -> None:
        self._filepath = filepath
        content = Path(filepath).read_text(encoding='utf-8-sig')
        self._parse(content)

    def load_from_string(self, content: str) -> None:
        self._filepath = ''
        self._parse(content)

    def _parse(self, content: str) -> None:
        global _auto_id_seq

        # Capture and register all namespaces from source
        for event, elem in ET.iterparse(io.StringIO(content), events=['start-ns']):
            prefix, uri = elem
            ET.register_namespace(prefix, uri)
        for prefix, uri in _COMMON_NS.items():
            ET.register_namespace(prefix, uri)

        root = ET.fromstring(content)

        # Auto-assign IDs
        for elem in root.iter():
            if 'id' not in elem.attrib:
                elem.set('id', f'_sviewg_{_auto_id_seq}')
                _auto_id_seq += 1

        ET.indent(root, space='  ')
        body = ET.tostring(root, encoding='unicode', xml_declaration=False)
        self._formatted_text = '<?xml version="1.0" encoding="UTF-8"?>\n' + body
        self._svg_bytes = self._formatted_text.encode('utf-8')

        self._build_text_map()

    def _build_text_map(self) -> None:
        self._id_to_range = {}
        self._line_to_id = {}
        self._element_ids = []

        lines = self._formatted_text.split('\n')
        stack: list[tuple[Optional[str], int]] = []

        for ln, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('<?') or stripped.startswith('<!--'):
                continue

            is_close = bool(_CLOSE_TAG_RE.match(line))
            m_open = _OPEN_TAG_RE.match(line) if not is_close else None

            if m_open:
                is_self_close = bool(_SELF_CLOSE_RE.search(line))
                tag_name = m_open.group(1)
                # Inline element: opening and matching closing tag on same line
                is_inline = (not is_self_close and
                             (f'</{tag_name}>' in line or
                              f'</{tag_name.split(":")[-1]}>' in line))

                m_id = _ID_RE.search(line)
                eid = m_id.group(1) if m_id else None

                if eid and eid not in self._element_ids:
                    self._element_ids.append(eid)

                if is_self_close or is_inline:
                    if eid:
                        self._id_to_range[eid] = ElementTextRange(eid, ln, ln)
                else:
                    stack.append((eid, ln))

            elif is_close and stack:
                eid, start_ln = stack.pop()
                if eid:
                    self._id_to_range[eid] = ElementTextRange(eid, start_ln, ln)
                    if eid not in self._element_ids:
                        self._element_ids.append(eid)

        # Fill _line_to_id: iterate from largest ranges to smallest so inner wins
        for r in sorted(self._id_to_range.values(),
                        key=lambda r: r.end_line - r.start_line, reverse=True):
            for i in range(r.start_line, r.end_line + 1):
                self._line_to_id[i] = r.element_id

    # ── Public API ─────────────────────────────────────────────────────────

    def get_formatted_text(self) -> str:
        return self._formatted_text

    def get_svg_bytes(self) -> bytes:
        return self._svg_bytes

    def get_id_at_line(self, line: int) -> Optional[str]:
        return self._line_to_id.get(line)

    def get_element_range(self, element_id: str) -> Optional[tuple[int, int]]:
        r = self._id_to_range.get(element_id)
        return (r.start_line, r.end_line) if r else None

    @property
    def element_ids(self) -> list[str]:
        return self._element_ids

    @property
    def filepath(self) -> str:
        return self._filepath

    def get_fold_starts(self) -> dict[int, str]:
        """Returns {start_line: element_id} for all multi-line (foldable) elements."""
        return {r.start_line: r.element_id
                for r in self._id_to_range.values()
                if r.end_line > r.start_line}

    def is_loaded(self) -> bool:
        return bool(self._formatted_text)
