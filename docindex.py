import argparse
from pathlib import Path
import sys


TEXT_EXTENSIONS = {".txt", ".md"}


def find_documents(folder):
    documents = (
        path for path in folder.rglob("*")
        if path.suffix.lower() in TEXT_EXTENSIONS and path.is_file()
    )
    return sorted(documents, key=lambda path: (str(path).casefold(), str(path)))


def read_document(path):
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("Podržane su samo TXT i Markdown datoteke (.txt, .md).")
    return path.read_text(encoding="utf-8-sig")


def main():
    parser = argparse.ArgumentParser(description="DocIndex, lokalni pregled dokumenata.")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="Pronađi dokumente u mapi i podmapama.")
    scan.add_argument("folder", type=Path, metavar="mapa")

    read = commands.add_parser("read", help="Ispiši sadržaj dokumenta.")
    read.add_argument("path", type=Path, metavar="datoteka")

    args = parser.parse_args()
    try:
        if args.command == "scan":
            folder = args.folder.expanduser()
            if not folder.is_dir():
                parser.error(f"Mapa ne postoji ili nije direktorij: {folder}")
            documents = find_documents(folder)
            for path in documents:
                print(path.relative_to(folder))
            print(f"Pronađeno dokumenata: {len(documents)}")
        else:
            path = args.path.expanduser()
            print(read_document(path), end="")
    except UnicodeDecodeError:
        print(f"Datoteka nije zapisana u UTF-8 formatu: {path}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
