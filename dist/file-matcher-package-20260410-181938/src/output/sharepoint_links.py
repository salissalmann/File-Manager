"""Build SharePoint AllItems.aspx links (mirrors web/src/lib/file-links.ts)."""

from __future__ import annotations

import os
import re
from urllib.parse import quote

_DEFAULT_FORMS_URL = (
    "https://meskencustomhomes.sharepoint.com/Shared%20Documents/Forms/AllItems.aspx"
)
_DEFAULT_FOLDER_ID = "/Shared Documents/1523 Milford - All Invoices"
_DEFAULT_VIEW_ID = "8618cf10-248c-4334-ae74-b9785410dac7"

_MM_YYYY_FOLDER = re.compile(r"^(\d{2})-(\d{4})$")


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return default


def norm_slashes(s: str) -> str:
    return s.replace("\\", "/").lstrip("/")


def normalize_sharepoint_relative_path(path_from_root: str) -> str:
    rel = norm_slashes(path_from_root.strip())
    if not rel:
        return rel
    if _env("SHAREPOINT_DISABLE_MMYYYY_MAP", "NEXT_PUBLIC_SHAREPOINT_DISABLE_MMYYYY_MAP") == "1":
        return rel
    i = rel.find("/")
    first = rel if i == -1 else rel[:i]
    rest = "" if i == -1 else rel[i + 1 :]
    m = _MM_YYYY_FOLDER.match(first)
    if not m:
        return rel
    year = m.group(2)
    return f"{year}/{first}/{rest}" if rest else f"{year}/{first}"


def build_sharepoint_document_url(path_from_root: str) -> str:
    rel = normalize_sharepoint_relative_path(path_from_root.strip())
    if not rel:
        return ""

    forms = _env("SHAREPOINT_FORMS_URL", "NEXT_PUBLIC_SHAREPOINT_FORMS_URL", default=_DEFAULT_FORMS_URL)
    root = _env("SHAREPOINT_FOLDER_ID", "NEXT_PUBLIC_SHAREPOINT_FOLDER_ID", default=_DEFAULT_FOLDER_ID).rstrip("/")
    view_id = _env("SHAREPOINT_VIEW_ID", "NEXT_PUBLIC_SHAREPOINT_VIEW_ID", default=_DEFAULT_VIEW_ID)

    full_path = f"{root}/{rel}"
    last_slash = full_path.rfind("/")
    parent_path = full_path[:last_slash] if last_slash > 0 else root

    id_q = quote(full_path, safe="")
    vid_q = quote(view_id, safe="")
    parent_q = quote(parent_path, safe="")
    sep = "&" if "?" in forms else "?"
    return f"{forms}{sep}viewid={vid_q}&id={id_q}&parent={parent_q}"


def resolve_file_open_url(path_from_root: str, filename: str) -> str:
    """Resolve clickable URL: FILE_LINK_BASE + path, else SharePoint."""
    base = _env("FILE_LINK_BASE", "NEXT_PUBLIC_FILE_LINK_BASE")
    rel = (path_from_root or "").strip() or (filename or "").strip()
    if not rel:
        return ""
    if base:
        return f"{base.rstrip('/')}/{norm_slashes(rel)}"
    return build_sharepoint_document_url(rel)
