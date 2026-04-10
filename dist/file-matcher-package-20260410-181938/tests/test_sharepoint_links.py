"""SharePoint URL builder (CLI parity with web/src/lib/file-links.ts)."""

from src.output import sharepoint_links as sl


def test_normalize_prepends_year_keeps_month_folder(monkeypatch):
    monkeypatch.delenv("SHAREPOINT_DISABLE_MMYYYY_MAP", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SHAREPOINT_DISABLE_MMYYYY_MAP", raising=False)
    assert sl.normalize_sharepoint_relative_path("01-2022/a.pdf") == "2022/01-2022/a.pdf"
    assert sl.normalize_sharepoint_relative_path("11-2021/x.pdf") == "2021/11-2021/x.pdf"


def test_normalize_disabled(monkeypatch):
    monkeypatch.setenv("SHAREPOINT_DISABLE_MMYYYY_MAP", "1")
    assert sl.normalize_sharepoint_relative_path("01-2022/a.pdf") == "01-2022/a.pdf"


def test_build_sharepoint_url_has_viewid_id_parent():
    url = sl.build_sharepoint_document_url("2021/11-2021/test file.pdf")
    assert "AllItems.aspx" in url
    assert "viewid=" in url
    assert "id=" in url
    assert "parent=" in url
    assert "1523%20Milford" in url or "Milford" in url


def test_resolve_file_link_base(monkeypatch):
    monkeypatch.setenv("FILE_LINK_BASE", "https://dropbox.example/f")
    assert sl.resolve_file_open_url("01-2022/a.pdf", "a.pdf") == "https://dropbox.example/f/01-2022/a.pdf"
    monkeypatch.delenv("FILE_LINK_BASE", raising=False)
