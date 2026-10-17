import io
import zipfile

from fastapi.testclient import TestClient

from advocacy_intel.api.main import app

client = TestClient(app)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

REC = "The authorities should strengthen judicial independence."


def _zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, xml in members.items():
            zf.writestr(name, xml)
    return buf.getvalue()


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    return _zip({"word/document.xml": f'<w:document xmlns:w="{_W}"><w:body>{body}</w:body></w:document>'})


def _pptx(slides: list[list[str]]) -> bytes:
    members = {}
    for i, paragraphs in enumerate(slides, start=1):
        body = "".join(f"<a:p><a:r><a:t>{p}</a:t></a:r></a:p>" for p in paragraphs)
        members[f"ppt/slides/slide{i}.xml"] = f'<p:sld xmlns:a="{_A}" xmlns:p="{_P}">{body}</p:sld>'
    return _zip(members)


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for n, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


def _post(content: bytes, filename: str):
    return client.post(f"/api/extract?filename={filename}", content=content)


def test_docx_returns_paragraphs_and_drops_short_ones():
    resp = _post(_docx(["Heading", REC, "  ", REC + " Again."]), "draft.docx")
    assert resp.status_code == 200
    assert resp.json() == {"paragraphs": [REC, REC + " Again."], "truncated": False}


def test_pptx_reads_slides_in_order():
    second = "Parliament should adopt legislation protecting judges."
    resp = _post(_pptx([[REC], [second]]), "deck.pptx")
    assert resp.status_code == 200
    assert resp.json()["paragraphs"] == [REC, second]


def test_txt_splits_on_blank_lines_and_joins_wrapped_lines():
    head, tail = REC.split("strengthen ")
    text = f"Title\n\n{head}strengthen\n{tail}\n\n1. {REC} Second.\n"
    resp = _post(text.encode(), "notes.txt")
    assert resp.status_code == 200
    assert resp.json()["paragraphs"] == [REC, f"1. {REC} Second."]


def test_txt_falls_back_to_cp1252():
    resp = _post("The authorities should protect Beirut’s judges.".encode("cp1252"), "n.txt")
    assert resp.status_code == 200
    assert "Beirut’s" in resp.json()["paragraphs"][0]


def test_pdf_text_is_extracted():
    resp = _post(_pdf(REC), "report.pdf")
    assert resp.status_code == 200
    assert resp.json()["paragraphs"] == [REC]


def test_unreadable_files_are_rejected():
    assert _post(b"not a zip file", "x.docx").status_code == 422
    assert _post(b"not a zip file", "x.pptx").status_code == 422
    assert _post(b"not a pdf", "x.pdf").status_code == 422


def test_unsupported_extension_is_rejected():
    assert _post(b"whatever", "x.doc").status_code == 422
    assert client.post("/api/extract", content=b"whatever").status_code == 422


def test_file_without_text_is_rejected():
    assert _post(_docx(["short"]), "x.docx").status_code == 422


def test_oversized_upload_is_rejected():
    assert _post(b"0" * (5 * 1024 * 1024 + 1), "x.txt").status_code == 413
