#!/usr/bin/env python3
"""Dev/Skill helper: .docx -> plain text on stdout, stdlib only.

Tables come out as tab-separated cells, one row per line, so an SOP's process
table stays machine-readable for the extraction step. Not imported by the runtime.
"""
import html
import re
import sys
import zipfile


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    # Inside a table cell, paragraph breaks become spaces so a row stays one line;
    # cells end in a tab, rows in a newline. Order matters: cells before paragraphs.
    xml = re.sub(r"<w:tc(?: [^>]*)?>([\s\S]*?)</w:tc>",
                 lambda m: re.sub(r"</w:p>", " ", m.group(1)) + "\t", xml)
    xml = re.sub(r"</w:tr>", "\n", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    text = html.unescape(xml)
    text = re.sub(r"[ \t]+\n", "\n", text)          # strip trailing cell tabs
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: docx2txt.py <file.docx>", file=sys.stderr)
        return 2
    try:
        sys.stdout.write(docx_text(argv[0]))
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        print(f"I/O error: {argv[0]}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
