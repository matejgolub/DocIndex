from dataclasses import dataclass
from zipfile import BadZipFile


@dataclass
class DocumentPart:
    text: str
    number: int | None = None


def read_text(path):
    return [DocumentPart(path.read_text(encoding="utf-8-sig"))]


def read_pdf(path):
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        with path.open("rb") as file:
            reader = PdfReader(file)
            if reader.is_encrypted:
                raise ValueError("PDF je šifriran.")
            return [
                DocumentPart(page.extract_text() or "", number)
                for number, page in enumerate(reader.pages, start=1)
            ]
    except PyPdfError as error:
        raise ValueError("PDF se ne može otvoriti ili pročitati.") from error


def word_text(container):
    from docx.text.paragraph import Paragraph

    for item in container.iter_inner_content():
        if isinstance(item, Paragraph):
            if item.text.strip():
                yield item.text
        else:
            seen_cells = set()
            for row in item.rows:
                for cell in row.cells:
                    if cell._tc not in seen_cells:
                        seen_cells.add(cell._tc)
                        yield from word_text(cell)


def read_docx(path):
    from docx import Document
    from docx.opc.exceptions import OpcError

    try:
        with path.open("rb") as file:
            return [DocumentPart("\n".join(word_text(Document(file))))]
    except (OpcError, BadZipFile, KeyError, SyntaxError) as error:
        raise ValueError("DOCX se ne može otvoriti ili pročitati.") from error


def slide_text(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from slide_text(shape.shapes)
        elif shape.has_text_frame:
            if shape.text.strip():
                yield shape.text.replace("\v", "\n")
        elif shape.has_table:
            for cell in shape.table.iter_cells():
                if not cell.is_spanned and cell.text.strip():
                    yield cell.text.replace("\v", "\n")


def read_pptx(path):
    from pptx import Presentation
    from pptx.exc import PythonPptxError

    try:
        with path.open("rb") as file:
            slides = Presentation(file).slides
            return [
                DocumentPart("\n".join(slide_text(slide.shapes)), number)
                for number, slide in enumerate(slides, start=1)
            ]
    except (PythonPptxError, BadZipFile, KeyError, SyntaxError) as error:
        raise ValueError("PPTX se ne može otvoriti ili pročitati.") from error


READERS = {
    ".txt": read_text,
    ".md": read_text,
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".pptx": read_pptx,
}
SUPPORTED_EXTENSIONS = set(READERS)


def read_document(path):
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError("Podržani formati: TXT, Markdown, PDF, DOCX i PPTX.")
    return reader(path)
