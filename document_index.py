from collections import Counter
from contextlib import closing
import re
import sqlite3
import unicodedata

from readers import read_document


WORD_PATTERN = re.compile(r"[^\W_]+")

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


def search_index(database, word):
    terms = tokenize(word)
    if len(terms) != 1:
        raise ValueError("Upiši jednu riječ za pretragu.")
    if not database.is_file():
        raise ValueError("Indeks ne postoji. Prvo pokreni naredbu index.")

    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT documents.path
            FROM docindex_postings AS postings
            JOIN docindex_parts AS parts ON parts.id = postings.part_id
            JOIN docindex_documents AS documents ON documents.id = parts.document_id
            WHERE postings.term = ?
            ORDER BY documents.path
            """,
            (terms[0],),
        )
        return [path for (path,) in rows]
