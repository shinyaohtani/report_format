# -*- coding: utf-8 -*-
"""
JSON(日本語キー, v1.1想定) → 数式入りMarkdown 変換
要件: モノ指向・読みやすさ・レイアウト安定・数式(TeX)保持・註釈(章末)対応
"""

from __future__ import annotations
from typing import Any, Iterable
import json
from pathlib import Path


class LayoutRule:
    """見出し/数式/註釈の出力規則を保持するモノ。"""

    def __init__(self, title_prefix: str = "# ") -> None:
        self._title_prefix: str = title_prefix

    def heading(self, level: int, text: str) -> str:
        prefix: str = "#" * max(1, level)
        return f"{prefix} {text}".rstrip()

    def callout(self, text: str) -> str:
        return f"> {text}".rstrip()

    def math_display(self, tex: str) -> str:
        body: str = tex.strip().removeprefix("\\[").removesuffix("\\]").strip()
        return f"$$\n{body}\n$$"

    def note_heading(self) -> str:
        return "### 註釈"


class DocSheet:
    """Markdownの紙（シート）として行を蓄えるモノ。"""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def add_heading(self, level: int, text: str) -> None:
        self._lines.append(LayoutRule().heading(level, text))

    def add_block(self, text: str) -> None:
        self._lines.append(text.rstrip())

    def add_math(self, tex: str) -> None:
        self._lines.append(LayoutRule().math_display(tex))

    @property
    def text(self) -> str:
        return "\n".join([ln for ln in self._lines if ln is not None]).strip() + "\n"


class BlockCodec:
    """本文ブロック(段落/数式)をMarkdownに写像するモノ。"""

    def __init__(self) -> None:
        self._rule: LayoutRule = LayoutRule()

    def block(self, block_payload: dict[str, Any], sheet: DocSheet) -> None:
        kind: str = str(block_payload.get("種類", "段落"))
        if kind == "数式":
            tex: str = str(block_payload.get("テキスト", ""))
            sheet.add_math(tex)
            return
        text: str = str(block_payload.get("本文", ""))
        sheet.add_block(self._resolve_links(text))

    def note_body(self, parts: Iterable[dict[str, Any]], sheet: DocSheet) -> None:
        for part in parts:
            self.block(part, sheet)

    def _resolve_links(self, text: str) -> str:
        # ここでは {@式:...} / {@注:...} を素通し（後工程で置換しやすい）
        return text


class ChapterSheet:
    """章配下(節/項/註釈含む)を書き下すモノ。"""

    def __init__(self) -> None:
        self._rule: LayoutRule = LayoutRule()
        self._block: BlockCodec = BlockCodec()

    def chapter(self, ch: dict[str, Any], sheet: DocSheet) -> None:
        title: str = f"第{ch.get('章番号')}章 {ch.get('章タイトル')}"
        sheet.add_heading(1, title)
        one: str = str(ch.get("一行結論", "")).strip()
        if one:
            sheet.add_block(self._rule.callout(f"つまり、{one.removeprefix('つまり、').removeprefix('つまり')}"))
        summary: str = str(ch.get("概要説明", "")).strip()
        if summary:
            sheet.add_block("")
            sheet.add_block(summary)
        for sec in ch.get("節", []) or []:
            self.section(sec, sheet, 2)
        notes: list[dict[str, Any]] = ch.get("註釈", []) or []
        if notes:
            self.notes(notes, sheet, 3)

    def section(self, sec: dict[str, Any], sheet: DocSheet, level: int) -> None:
        head: str = f"{sec.get('節番号')} {sec.get('節タイトル')}"
        sheet.add_block("")
        sheet.add_heading(level, head)
        one: str = str(sec.get("一行結論", "")).strip()
        if one:
            sheet.add_block(self._rule.callout(f"つまり、{one.removeprefix('つまり、').removeprefix('つまり')}"))
        summary: str = str(sec.get("概要説明", "")).strip()
        if summary:
            sheet.add_block("")
            sheet.add_block(summary)
        for itm in sec.get("項", []) or []:
            self.item(itm, sheet, level + 1)

    def item(self, itm: dict[str, Any], sheet: DocSheet, level: int) -> None:
        head: str = f"{itm.get('項番号')} {itm.get('項タイトル')}"
        sheet.add_block("")
        sheet.add_heading(level, head)
        one: str = str(itm.get("一行結論", "")).strip()
        if one:
            sheet.add_block(self._rule.callout(f"つまり、{one.removeprefix('つまり、').removeprefix('つまり')}"))
        summary: str = str(itm.get("概要説明", "")).strip()
        if summary:
            sheet.add_block("")
            sheet.add_block(summary)
        for blk in itm.get("本文", []) or []:
            self._block.block(blk, sheet)

    def notes(self, notes: list[dict[str, Any]], sheet: DocSheet, level: int) -> None:
        sheet.add_block("")
        sheet.add_heading(level, self._rule.note_heading())
        for n in notes:
            title: str = f"- **{n.get('注識別子')} {n.get('タイトル')}**"
            sheet.add_block(title)
            self._block.note_body(n.get("本文", []) or [], sheet)


class BookForm:
    """書籍全体(JSON)を保持し、Markdown文字列を供するモノ。"""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload: dict[str, Any] = payload
        self._chap: ChapterSheet = ChapterSheet()

    def _title_header(self, sheet: DocSheet) -> None:
        title: str = str(self._payload.get("メタデータ", {}).get("タイトル", "")).strip()
        if title:
            sheet.add_heading(1, title)

    def _emit(self, sheet: DocSheet) -> None:
        self._title_header(sheet)
        for ch in self._payload.get("本文", []) or []:
            sheet.add_block("")
            self._chap.chapter(ch, sheet)

    @property
    def markdown(self) -> str:
        sheet: DocSheet = DocSheet()
        self._emit(sheet)
        return sheet.text


# --------------------------
# 使い方（スクリプト実行時）
# --------------------------
def _load_json(json_abspath: str) -> dict[str, Any]:
    p: Path = Path(json_abspath)
    return json.loads(p.read_text(encoding="utf-8"))

def _save_markdown(md_text: str, md_abspath: str) -> None:
    Path(md_abspath).write_text(md_text, encoding="utf-8")

def main(json_abspath: str, md_abspath: str) -> None:
    payload: dict[str, Any] = _load_json(json_abspath)
    book: BookForm = BookForm(payload)
    _save_markdown(book.markdown, md_abspath)


if __name__ == "__main__":
    # 例:
    # python book_to_md.py input.json output.md
    import sys
    if len(sys.argv) >= 3:
        main(sys.argv[1], sys.argv[2])
    else:
        print("使い方: python book_to_md.py <input.json> <output.md>")