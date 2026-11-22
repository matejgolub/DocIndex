import argparse
from pathlib import Path
import sys

from readers import SUPPORTED_EXTENSIONS, read_document


PART_LABELS = {".pdf": "Stranica", ".pptx": "Slajd"}


def find_documents(folder):
    documents = (
        path for path in folder.rglob("*")
        if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file()
    )
    return sorted(documents, key=lambda path: (str(path).casefold(), str(path)))


def print_document(path):
    parts = read_document(path)
    label = PART_LABELS.get(path.suffix.lower())
    if label is None:
        print(parts[0].text, end="")
        return

    for part in parts:
        print(f"{label} {part.number}")
        print(part.text.rstrip() if part.text.strip() else "(bez teksta)")


def main():
    parser = argparse.ArgumentParser(description="DocIndex, lokalni pregled dokumenata.")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="Pronađi dokumente u mapi i podmapama.")
    scan.add_argument("folder", type=Path, metavar="mapa")

    read = commands.add_parser("read", help="Ispiši sadržaj dokumenta.")
    read.add_argument("path", type=Path, metavar="datoteka")

    args = parser.parse_args()
    if args.command == "scan":
        folder = args.folder.expanduser()
        if not folder.is_dir():
            parser.error(f"Mapa ne postoji ili nije direktorij: {folder}")
        try:
            documents = find_documents(folder)
        except OSError as error:
            print(error, file=sys.stderr)
            return 1
        for path in documents:
            print(path.relative_to(folder))
        print(f"Pronađeno dokumenata: {len(documents)}")
        return 0

    path = args.path.expanduser()
    try:
        print_document(path)
    except UnicodeDecodeError:
        print(f"Datoteka nije zapisana u UTF-8 formatu: {path}", file=sys.stderr)
        return 1
    except ModuleNotFoundError:
        print("Nedostaju paketi. Pokreni: python -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"Ne mogu pročitati {path}: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
