from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import unicodedata

from readers import read_document


WORD_PATTERN = re.compile(r"[^\W_]+")
CONTEXT_LENGTH = 55

SCHEMA = """
BEGIN;
CREATE TABLE IF NOT EXISTS docindex_documents (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS docindex_parts (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES docindex_documents(id) ON DELETE CASCADE,
    number INTEGER,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS docindex_parts_document ON docindex_parts(document_id);
CREATE TABLE IF NOT EXISTS docindex_postings (
    part_id INTEGER NOT NULL REFERENCES docindex_parts(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    frequency INTEGER NOT NULL,
    PRIMARY KEY (part_id, term)
);
CREATE INDEX IF NOT EXISTS docindex_postings_term ON docindex_postings(term);
"""


@dataclass
class SearchResult:
    path: Path
    number: int | None
    snippet: str


def tokenize(text):
    normalized = unicodedata.normalize("NFC", text).casefold()
    return WORD_PATTERN.findall(normalized)


def build_index(database, documents):
    indexed = 0
    skipped = []
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        connection.execute("DELETE FROM docindex_documents")
        for path in documents:
            try:
                parts = read_document(path)
            except UnicodeDecodeError:
                skipped.append((path, "Datoteka nije zapisana u UTF-8 formatu."))
                continue
            except (OSError, ValueError) as error:
                skipped.append((path, str(error)))
                continue

            document_id = connection.execute(
                "INSERT INTO docindex_documents (path) VALUES (?)",
                (str(path),),
            ).lastrowid
            for part in parts:
                part_id = connection.execute(
                    "INSERT INTO docindex_parts (document_id, number, text) VALUES (?, ?, ?)",
                    (document_id, part.number, part.text),
                ).lastrowid
                frequencies = Counter(tokenize(part.text))
                connection.executemany(
                    "INSERT INTO docindex_postings (part_id, term, frequency) VALUES (?, ?, ?)",
                    ((part_id, term, count) for term, count in frequencies.items()),
                )
            indexed += 1

        if not indexed and skipped:
            path, error = skipped[0]
            raise ValueError(f"Indeks nije izgrađen. Ne mogu pročitati {path}: {error}")

    return indexed, skipped


def make_snippet(text, term):
    text = " ".join(unicodedata.normalize("NFC", text).split())
    for match in WORD_PATTERN.finditer(text):
        if term in tokenize(match.group()):
            start = max(0, match.start() - CONTEXT_LENGTH)
            end = min(len(text), match.end() + CONTEXT_LENGTH)
            prefix = "…" if start else ""
            suffix = "…" if end < len(text) else ""
            before = text[start:match.start()]
            after = text[match.end():end]
            return f"{prefix}{before}[{match.group()}]{after}{suffix}"
    return text[:CONTEXT_LENGTH]


def search_index(database, word, extension=None):
    terms = tokenize(word)
    if len(terms) != 1:
        raise ValueError("Upiši jednu riječ za pretragu.")
    if not database.is_file():
        raise ValueError("Indeks ne postoji. Prvo pokreni naredbu index.")

    term = terms[0]
    query = """
        SELECT documents.path, parts.number, parts.text
        FROM docindex_postings AS postings
        JOIN docindex_parts AS parts ON parts.id = postings.part_id
        JOIN docindex_documents AS documents ON documents.id = parts.document_id
        WHERE postings.term = ?
    """
    parameters = [term]
    if extension is not None:
        query += " AND lower(substr(documents.path, ?)) = ?"
        parameters.extend((-len(extension), extension))
    query += " ORDER BY documents.path, parts.number"

    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        rows = connection.execute(query, parameters)
        return [
            SearchResult(Path(path), number, make_snippet(text, term))
            for path, number, text in rows
        ]
