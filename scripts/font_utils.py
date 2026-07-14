"""
font_utils.py — Geometric Font Decoder for OAB PDF Ingestion

Resolves character corruption in PDFs that embed fonts without /ToUnicode
mappings (e.g. XXXV Exame de Ordem — Calibri, Calibri,Italic, Symbol).

Strategy:
  1. Scan the ENTIRE document for fonts that DO have /ToUnicode mappings.
     For each glyph in those fonts, extract the vector path ("shape") and
     associate it with the known Unicode character.  This builds a global
     shape→char database.

  2. For fonts WITHOUT /ToUnicode, extract the shape of every glyph and
     look it up in the global database.  If a match is found we now know
     the real character.

  3. A small EXTRA_FALLBACKS dict covers residual gaps (e.g. fraction
     characters that exist only in corrupted fonts).

All operations are in-memory; no OCR, no network calls.
"""

import re
from io import BytesIO
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.basePen import AbstractPen
from fontTools.pens.transformPen import TransformPen


# ---------------------------------------------------------------------------
# DecomposingPen: flattens composite glyphs into a single RecordingPen
# ---------------------------------------------------------------------------
class DecomposingPen(AbstractPen):
    """Wraps a RecordingPen and resolves composite glyph references inline."""

    def __init__(self, glyf_table, recording_pen):
        self.glyf = glyf_table
        self.pen = recording_pen

    def moveTo(self, pt):
        self.pen.moveTo(pt)

    def lineTo(self, pt):
        self.pen.lineTo(pt)

    def curveTo(self, *pts):
        self.pen.curveTo(*pts)

    def qCurveTo(self, *pts):
        self.pen.qCurveTo(*pts)

    def closePath(self):
        self.pen.closePath()

    def endPath(self):
        self.pen.endPath()

    def addComponent(self, glyphName, transformation):
        tpen = TransformPen(self, transformation)
        self.glyf[glyphName].draw(tpen, self.glyf)


# ---------------------------------------------------------------------------
# parse_cmap: extract code→unicode mapping from a /ToUnicode CMap stream
# ---------------------------------------------------------------------------
def parse_cmap(cmap_text: str) -> dict[int, int]:
    """Parse a PDF /ToUnicode CMap stream into {charCode: unicodeCodepoint}."""
    mapping = {}

    # beginbfchar blocks
    for block in re.findall(r'beginbfchar(.*?)endbfchar', cmap_text, re.DOTALL):
        for line in block.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = re.findall(r'<([0-9a-fA-F]+)>', line)
            if len(parts) == 2:
                mapping[int(parts[0], 16)] = int(parts[1], 16)

    # beginbfrange blocks
    for block in re.findall(r'beginbfrange(.*?)endbfrange', cmap_text, re.DOTALL):
        for line in block.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if '[' in line:
                parts = re.findall(r'<([0-9a-fA-F]+)>', line)
                if len(parts) >= 2:
                    start = int(parts[0], 16)
                    end = int(parts[1], 16)
                    dest_list = [int(x, 16) for x in parts[2:]]
                    for idx, code in enumerate(range(start, end + 1)):
                        if idx < len(dest_list):
                            mapping[code] = dest_list[idx]
            else:
                parts = re.findall(r'<([0-9a-fA-F]+)>', line)
                if len(parts) == 3:
                    start = int(parts[0], 16)
                    end = int(parts[1], 16)
                    dest_start = int(parts[2], 16)
                    for code in range(start, end + 1):
                        mapping[code] = dest_start + (code - start)
    return mapping


# ---------------------------------------------------------------------------
# build_font_char_maps: whole-document geometric decoder
# ---------------------------------------------------------------------------
def build_font_char_maps(doc) -> dict:
    """
    Analyse *all* fonts in *doc* (a fitz.Document) and return a dictionary:

        font_char_maps[(page_number_1based, font_clean_name)] = {charCode: unicodeChar, ...}

    Only fonts WITHOUT /ToUnicode mappings get entries (those are the
    corrupted ones that need translation).

    The function is safe to call on documents that have no corruption —
    it will simply return an empty dict.
    """

    # ---- Phase 1: build global shape→char database from healthy fonts ----
    shape_to_char: dict[tuple, set[str]] = {}
    processed_xrefs: set[int] = set()

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        for f in page.get_fonts():
            xref = f[0]
            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)

            try:
                font_dict = doc.xref_object(xref)
                if '/ToUnicode' not in font_dict:
                    continue

                to_unicode_xref = int(
                    re.search(r'/ToUnicode\s+(\d+)\s+0\s+R', font_dict).group(1)
                )
                to_unicode_text = doc.xref_stream(to_unicode_xref).decode(
                    'utf-8', errors='ignore'
                )
                code_to_uni = parse_cmap(to_unicode_text)

                descriptor_ref = re.search(
                    r'/FontDescriptor\s+(\d+)\s+0\s+R', font_dict
                )
                if not descriptor_ref:
                    continue
                descriptor_dict = doc.xref_object(int(descriptor_ref.group(1)))

                ff_ref = re.search(
                    r'/FontFile\d?\s+(\d+)\s+0\s+R', descriptor_dict
                )
                if not ff_ref:
                    continue

                font_data = doc.xref_stream(int(ff_ref.group(1)))
                font = TTFont(BytesIO(font_data))

                cmap_table = _best_cmap(font)
                if not cmap_table:
                    continue

                glyf = font['glyf']
                for code, glyph_name in cmap_table.items():
                    lookup_code = code
                    if lookup_code > 0xF000:
                        lookup_code = lookup_code & 0xFF
                    if lookup_code in code_to_uni:
                        uni_char = chr(code_to_uni[lookup_code])
                        rec_pen = RecordingPen()
                        dec_pen = DecomposingPen(glyf, rec_pen)
                        try:
                            glyf[glyph_name].draw(dec_pen, glyf)
                            shape = tuple(rec_pen.value)
                            if shape not in shape_to_char:
                                shape_to_char[shape] = set()
                            shape_to_char[shape].add(uni_char)
                        except Exception:
                            pass
            except Exception:
                pass

    # ---- Phase 2: build per-(page, font) char maps for corrupted fonts ----
    font_char_maps: dict[tuple, dict[int, str]] = {}
    processed_xrefs.clear()

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        p_num = page_idx + 1
        for f in page.get_fonts():
            xref = f[0]
            font_name_full = f[3]
            font_name_clean = re.sub(r'^[A-Z]{6}\+', '', font_name_full)

            # Skip if this xref already has a mapping for this page
            if (p_num, font_name_clean) in font_char_maps:
                continue

            try:
                font_dict = doc.xref_object(xref)
                if '/ToUnicode' in font_dict:
                    continue  # healthy font, no translation needed

                descriptor_ref = re.search(
                    r'/FontDescriptor\s+(\d+)\s+0\s+R', font_dict
                )
                if not descriptor_ref:
                    continue
                descriptor_dict = doc.xref_object(int(descriptor_ref.group(1)))

                ff_ref = re.search(
                    r'/FontFile\d?\s+(\d+)\s+0\s+R', descriptor_dict
                )
                if not ff_ref:
                    continue

                font_data = doc.xref_stream(int(ff_ref.group(1)))
                font = TTFont(BytesIO(font_data))

                cmap_table = _best_cmap(font)
                if not cmap_table:
                    continue

                glyf = font['glyf']
                char_map: dict[int, str] = {}
                for code, glyph_name in cmap_table.items():
                    rec_pen = RecordingPen()
                    dec_pen = DecomposingPen(glyf, rec_pen)
                    try:
                        glyf[glyph_name].draw(dec_pen, glyf)
                        shape = tuple(rec_pen.value)
                        if shape in shape_to_char:
                            char_map[code] = next(iter(shape_to_char[shape]))
                    except Exception:
                        pass
                if char_map:
                    font_char_maps[(p_num, font_name_clean)] = char_map
            except Exception:
                pass

    return font_char_maps


# ---------------------------------------------------------------------------
# translate_page_text: rawdict-based text extractor with font translation
# ---------------------------------------------------------------------------
def translate_page_text(page, font_char_maps: dict, page_num: int) -> list[tuple[float, float, str]]:
    """
    Extract text from *page* using rawdict, translating corrupted chars
    through *font_char_maps*.

    Returns a list of (y0, x_center, text) tuples — same shape expected
    by the column-splitting logic in extrair_prova.
    """
    rd = page.get_text("rawdict")
    results = []  # (y0, x_center, line_text)

    for block in rd.get("blocks", []):
        for line_obj in block.get("lines", []):
            bbox = line_obj["bbox"]
            y0 = bbox[1]
            x_center = (bbox[0] + bbox[2]) / 2

            line_text = ""
            for span in line_obj.get("spans", []):
                font_name = span.get("font", "")
                font_clean = re.sub(r'^[A-Z]{6}\+', '', font_name)
                cmap_key = (page_num, font_clean)

                for char_info in span.get("chars", []):
                    c = char_info["c"]
                    c_code = ord(c)

                    # Synthetic chars are spacing inserted by PyMuPDF based on
                    # glyph positioning — always keep them as-is (they're spaces)
                    if char_info.get("synthetic"):
                        line_text += c
                        continue

                    # If we have a translation map for this font+page, use it
                    if cmap_key in font_char_maps and c_code in font_char_maps[cmap_key]:
                        line_text += font_char_maps[cmap_key][c_code]
                    elif 32 <= c_code <= 126 or 160 <= c_code <= 255:
                        # Printable ASCII/Latin-1 in a corrupted font:
                        # These code points often map to WRONG glyphs in corrupted
                        # fonts (e.g. code 32 → 'R' shape).  If the font IS
                        # corrupted but we have no map entry, drop the char to
                        # avoid injecting wrong letters.
                        if cmap_key in font_char_maps:
                            # Corrupted font, unmapped code → skip
                            pass
                        else:
                            line_text += c
                    elif c_code < 32 and cmap_key in font_char_maps:
                        # Control char in a corrupted font but no map entry — skip
                        pass
                    else:
                        line_text += c

            if line_text.strip():
                results.append((y0, x_center, line_text))

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _best_cmap(font: TTFont) -> dict | None:
    """Return the best available cmap table from a TTFont object."""
    # Prefer platformID=1 (Macintosh) for embedded subsets
    for table in font['cmap'].tables:
        if table.platformID == 1 and table.platEncID == 0:
            return table.cmap
    # Fallback to getBestCmap (usually platformID=3)
    return font['cmap'].getBestCmap()
