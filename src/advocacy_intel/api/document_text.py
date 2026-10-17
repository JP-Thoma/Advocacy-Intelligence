"""Extract candidate paragraphs from an uploaded .docx, .pptx, .pdf or .txt file.

Everything is parsed in memory and discarded; nothing is written to disk. Office formats
are zip archives, so they are read with the standard library. PDFs use pdfplumber.
"""

import io
import re
import zipfile
from xml.etree import ElementTree

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_XML_BYTES = 20 * 1024 * 1024  # guards against zip bombs
MAX_PDF_PAGES = 150
MAX_PARAGRAPHS = 400
MIN_PARAGRAPH_CHARS = 25  # drops headings, page numbers and empty list stubs
SUPPORTED = (".docx", ".pptx", ".pdf", ".txt")

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_SENTENCE_END = re.compile(r"[.!?:;]['\")\]]?$")
_BULLET = re.compile(r"^(\d+[.)]|[-•*▪●○])\s+")


class DocumentError(ValueError):
    """The upload is not a readable document of a supported type."""


def _clean(text: str) -> str:
    return " ".join(text.split())


def _keep(texts: list[str]) -> list[str]:
    cleaned = (_clean(t) for t in texts)
    return [t for t in cleaned if len(t) >= MIN_PARAGRAPH_CHARS]


def _read_zip_member(zf: zipfile.ZipFile, name: str) -> bytes:
    if zf.getinfo(name).file_size > MAX_XML_BYTES:
        raise DocumentError("The document is too large to read.")
    return zf.read(name)


def _xml_paragraphs(xml: bytes, ns: str) -> list[str]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise DocumentError("The document could not be read.") from exc
    out: list[str] = []
    for p in root.iter(f"{ns}p"):
        parts: list[str] = []
        for node in p.iter():
            if node.tag == f"{ns}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{ns}tab", f"{ns}br", f"{ns}cr"):
                parts.append(" ")
        out.append("".join(parts))
    return out


def _from_docx(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return _xml_paragraphs(_read_zip_member(zf, "word/document.xml"), _W)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise DocumentError("This does not look like a Word (.docx) file.") from exc


def _from_pptx(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            slides = sorted(
                (int(m.group(1)), n) for n in zf.namelist() if (m := _SLIDE.match(n))
            )
            if not slides:
                raise KeyError("no slides")
            out: list[str] = []
            for _, name in slides:
                out.extend(_xml_paragraphs(_read_zip_member(zf, name), _A))
            return out
    except (zipfile.BadZipFile, KeyError) as exc:
        raise DocumentError("This does not look like a PowerPoint (.pptx) file.") from exc


def _decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _group_lines(text: str) -> list[str]:
    """Blank lines separate paragraphs; otherwise a line starts a new paragraph when the
    previous one ended a sentence, or when it begins with a bullet or number."""
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if current and (_SENTENCE_END.search(current[-1]) or _BULLET.match(line)):
            paragraphs.append(" ".join(current))
            current = []
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _from_txt(data: bytes) -> list[str]:
    return _group_lines(_decode(data))


def _from_pdf(data: bytes) -> list[str]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - depends on install
        raise DocumentError("PDF support is not installed on the server.") from exc
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages[:MAX_PDF_PAGES]]
    except Exception as exc:  # pdfminer raises a wide range of exception types
        raise DocumentError("This does not look like a readable PDF file.") from exc
    return _group_lines("\n".join(pages))


_READERS = {".docx": _from_docx, ".pptx": _from_pptx, ".pdf": _from_pdf, ".txt": _from_txt}


def extract_paragraphs(data: bytes, filename: str) -> tuple[list[str], bool]:
    """Return (paragraphs, truncated). Raises DocumentError for unsupported or unreadable files."""
    name = filename.lower()
    ext = next((e for e in SUPPORTED if name.endswith(e)), None)
    if ext is None:
        raise DocumentError("Supported file types are .docx, .pptx, .pdf and .txt.")
    paragraphs = _keep(_READERS[ext](data))
    return paragraphs[:MAX_PARAGRAPHS], len(paragraphs) > MAX_PARAGRAPHS
