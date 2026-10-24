"""Producing the web page.

The viewer is built once from web/ into a single HTML file with all its
JavaScript and CSS inlined. This drops the knowledge base into that file, so
what comes out can be opened by double-clicking it, sent to someone, or kept
alongside a transcript. It needs no web server and no internet.

Rebuild the template with:   cd web && npm run build
"""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "viewer" / "index.html"

_PLACEHOLDER_OPEN = '<script id="logiclayer-data" type="application/json">'
_PLACEHOLDER_CLOSE = "</script>"


class ViewerMissing(RuntimeError):
    pass


def _escape(payload: dict) -> str:
    """JSON safe to sit inside a <script> tag.

    A string containing </script> would otherwise close the tag early and the
    rest of the data would be parsed as HTML. Escaping the angle brackets is
    the usual defence and leaves the JSON valid.
    """
    text = json.dumps(payload, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render(payload: dict) -> str:
    if not TEMPLATE.exists():
        raise ViewerMissing(
            f"the viewer template is missing from {TEMPLATE}. "
            "Build it with: cd web && npm install && npm run build"
        )

    template = TEMPLATE.read_text(encoding="utf-8")
    start = template.find(_PLACEHOLDER_OPEN)
    if start == -1:
        raise ViewerMissing("the viewer template has no data placeholder in it")

    opened = start + len(_PLACEHOLDER_OPEN)
    closed = template.find(_PLACEHOLDER_CLOSE, opened)
    return template[:opened] + _escape(payload) + template[closed:]


def write(payload: dict, target: str | Path) -> Path:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(payload), encoding="utf-8")
    return path
