# part_fileview.py -- loaded into serve.py's namespace by load_part (0.101.0).
#
# ---- a linked file opened as itself (0.101.0, 2026-10-30) ----
# The owner pressed a link to a side-by-side comparison page on a Today card and the side drawer showed the page's
# source code: the drawer read every file it did not know as text. GET /api/file/view says what a linked file is and
# hands the drawer what it needs to show it as itself: a web page or a PDF is framed from /raw/, a Word file is its
# words, a spreadsheet its sheets as tables, a slide deck its slides' words, a folder its files, and a file that is
# not on this computer says so with the files it may have become. Read-only, like every read here; the same refusals
# as the Files page (files_abs: no climbing out, no skipped folder, never a key file).

FILEVIEW_ROWS = 200          # a sheet's rows drawn; the rest are counted
FILEVIEW_COLS = 30           # a sheet's columns drawn
FILEVIEW_SHEETS = 12         # sheets drawn from one workbook
FILEVIEW_SLIDES = 80         # slides drawn from one deck
FILEVIEW_FOLDER = 40         # a folder's files listed, newest first
FILEVIEW_NEAR = 4            # files offered for a link whose file is gone
FILEVIEW_XML_MAX = 40 * 1024 * 1024   # a part of an Office file larger than this is not read
FILEVIEW_PAGE = {".html", ".htm"}
FILEVIEW_FRAME = {".pdf": "pdf", ".mp4": "video"}
_FV_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_FV_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_FV_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_FV_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_FV_DATE = re.compile(r"[-_]?\d{4}-\d{2}-\d{2}(?:[-_]\d{4})?")


def _fv_xml(z, name):
    """One XML part of an Office file, parsed, or None when it is missing or too large."""
    import xml.etree.ElementTree as ET
    try:
        info = z.getinfo(name)
    except KeyError:
        return None
    if info.file_size > FILEVIEW_XML_MAX:
        return None
    return ET.fromstring(z.read(name))


def _fv_text(el, ns):
    """The words of one paragraph: its text runs, a tab as a space, a break as a new line."""
    out = []
    for n in el.iter():
        if n.tag == ns + "t" and n.text:
            out.append(n.text)
        elif n.tag in (ns + "tab",):
            out.append(" ")
        elif n.tag in (ns + "br", ns + "cr"):
            out.append("\n")
    return "".join(out)


def fileview_docx(ap):
    """A Word file's words as markdown: a heading style as a heading, a numbered or bulleted paragraph as a list line,
    a table as a markdown table."""
    import zipfile
    with zipfile.ZipFile(ap) as z:
        root = _fv_xml(z, "word/document.xml")
    if root is None:
        return None
    body = root.find(_FV_W + "body")
    lines = []
    for el in list(body) if body is not None else []:
        if el.tag == _FV_W + "p":
            text = _fv_text(el, _FV_W).strip()
            if not text:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            ppr = el.find(_FV_W + "pPr")
            style = ""
            if ppr is not None:
                ps = ppr.find(_FV_W + "pStyle")
                style = (ps.get(_FV_W + "val") or "") if ps is not None else ""
                listed = ppr.find(_FV_W + "numPr") is not None
            else:
                listed = False
            m = re.match(r"(?i)heading\s*(\d)", style)
            if style.lower() == "title":
                lines += ["# " + text.replace("\n", " "), ""]
            elif m:
                lines += ["#" * min(6, int(m.group(1)) + 1) + " " + text.replace("\n", " "), ""]
            elif listed or style.lower().startswith("list"):
                lines.append("- " + text.replace("\n", " "))
            else:
                lines += [text.replace("\n", "  \n"), ""]
        elif el.tag == _FV_W + "tbl":
            rows = []
            for tr in el.iter(_FV_W + "tr"):
                cells = [" ".join(_fv_text(p, _FV_W).strip() for p in tc.iter(_FV_W + "p")).strip().replace("|", "/")
                         for tc in tr.findall(_FV_W + "tc")]
                rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines += ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                lines.append("")
    return "\n".join(lines).strip() + "\n"


def _fv_col(ref):
    """B12 -> 1 (the column, from zero)."""
    n = 0
    for ch in re.match(r"[A-Z]*", ref or "").group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _fv_num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return str(int(f)) if f.is_integer() and abs(f) < 1e15 else "{:.10g}".format(f)


def fileview_xlsx(ap):
    """A workbook's sheets as rows of cell text: [{name, rows, rowsTotal, colsTotal}], each sheet cut at
    FILEVIEW_ROWS rows and FILEVIEW_COLS columns."""
    import zipfile
    import posixpath
    with zipfile.ZipFile(ap) as z:
        wb = _fv_xml(z, "xl/workbook.xml")
        rels = _fv_xml(z, "xl/_rels/workbook.xml.rels")
        sst = _fv_xml(z, "xl/sharedStrings.xml")
        shared = ["".join(t.text or "" for t in si.iter(_FV_S + "t")) for si in sst.findall(_FV_S + "si")] if sst is not None else []
        targets = {}
        for r in list(rels) if rels is not None else []:
            t = (r.get("Target") or "").lstrip("/")
            targets[r.get("Id")] = t if t.startswith("xl/") else posixpath.normpath("xl/" + t)
        sheets = []
        listed = wb.find(_FV_S + "sheets") if wb is not None else None
        for sh in list(listed) if listed is not None else []:
            if len(sheets) >= FILEVIEW_SHEETS:
                break
            root = _fv_xml(z, targets.get(sh.get(_FV_R + "id"), ""))
            if root is None:
                continue
            grid, total, width = [], 0, 0
            data = root.find(_FV_S + "sheetData")
            for row in list(data) if data is not None else []:
                total += 1
                cells = {}
                for k, c in enumerate(row.findall(_FV_S + "c")):
                    col = _fv_col(c.get("r")) if c.get("r") else k
                    t, v = c.get("t"), c.find(_FV_S + "v")
                    if t == "s" and v is not None:
                        try:
                            val = shared[int(v.text)]
                        except (ValueError, IndexError, TypeError):
                            val = ""
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(_FV_S + "t"))
                    elif t == "b" and v is not None:
                        val = "TRUE" if v.text == "1" else "FALSE"
                    elif v is not None:
                        val = (v.text or "") if t in ("str", "e") else _fv_num(v.text)
                    else:
                        val = ""
                    if val != "":
                        cells[col] = val
                if cells:
                    width = max(width, max(cells) + 1)
                if len(grid) < FILEVIEW_ROWS:
                    grid.append(cells)
            cols = min(width, FILEVIEW_COLS)
            sheets.append({"name": sh.get("name") or "Sheet", "rows": [[r.get(i, "") for i in range(cols)] for r in grid],
                           "rowsTotal": total, "colsTotal": width})
    return sheets


def fileview_pptx(ap):
    """A deck's slides, each its paragraphs' words, in slide order."""
    import zipfile
    with zipfile.ZipFile(ap) as z:
        names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                       key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        slides = []
        for n in names[:FILEVIEW_SLIDES]:
            root = _fv_xml(z, n)
            if root is None:
                continue
            paras = [_fv_text(p, _FV_A).strip() for p in root.iter(_FV_A + "p")]
            slides.append([p for p in paras if p])
    return slides, len(names)


def fileview_near(rel):
    """The files a link whose file is gone may now mean: the same name in another folder (it moved), else the same
    name with another date in the same folder (another version), newest first."""
    leaf = rel.rsplit("/", 1)[-1]
    folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
    stem, ext = os.path.splitext(leaf)
    base = _FV_DATE.sub("", stem).lower()
    moved, versions = [], []
    for p, fn, mtime, size in files_stat_walk():
        if fn == leaf and p != rel:
            moved.append((mtime, p))
        elif base and (p.rsplit("/", 1)[0] if "/" in p else "") == folder:
            s, e = os.path.splitext(fn)
            if e.lower() == ext.lower() and _FV_DATE.sub("", s).lower() == base:
                versions.append((mtime, p))
    pick = moved or versions
    return [p for _, p in sorted(pick, reverse=True)[:FILEVIEW_NEAR]]


def fileview_api(rel):
    """GET /api/file/view?path=: what a linked file is and what the drawer needs to show it -> (code, body)."""
    raw = str(rel or "").strip().rstrip("/")
    if not raw:
        return 400, {"error": "no file named"}
    rel = norm(raw)
    if not rel:
        return 403, {"error": "the viewer does not open files from there (outside the brain)", "kind": "refused"}
    leaf = rel.rsplit("/", 1)[-1]
    if files_hidden(leaf):
        return 403, {"error": "a key file is never opened in the viewer", "kind": "key"}
    ap = files_abs(rel)
    if not ap:
        return 403, {"error": "the viewer does not open files from there (outside the brain, or a folder it skips)", "kind": "refused"}
    if os.path.isdir(ap):
        every = files_walk()
        rows = sorted((r for r in every if r["folder"] == rel), key=lambda r: r["modified"], reverse=True)
        subs = sorted({r["folder"][len(rel) + 1:].split("/")[0] for r in every if r["folder"].startswith(rel + "/")})
        return 200, {"kind": "folder", "path": rel, "count": len(rows),
                     "files": [{"path": r["path"], "name": r["name"], "modified": r["modified"], "size": r["size"]}
                               for r in rows[:FILEVIEW_FOLDER]],
                     "folders": subs}
    if not os.path.isfile(ap):
        return 404, {"error": "not on this computer", "kind": "missing", "path": rel, "near": fileview_near(rel)}
    st = os.stat(ap)
    ext = os.path.splitext(leaf)[1].lower()
    out = {"path": rel, "ext": ext.lstrip("."), "size": st.st_size,
           "mtime": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}
    stem_md = os.path.splitext(rel)[0] + ".md"
    if ext in FILEVIEW_PAGE:
        out["kind"] = "page"
    elif ext in FILEVIEW_FRAME:
        out["kind"] = FILEVIEW_FRAME[ext]
    elif ext in (".docx", ".xlsx", ".pptx"):
        try:
            if ext == ".docx":
                out["kind"], out["text"] = "docx", fileview_docx(ap) or ""
            elif ext == ".xlsx":
                out["kind"], out["sheets"] = "xlsx", fileview_xlsx(ap)
            else:
                out["kind"], (out["slides"], out["slidesTotal"]) = "pptx", fileview_pptx(ap)
        except Exception as e:   # a damaged or password-locked Office file: said plainly, with the download
            out["kind"], out["why"] = "other", "this %s could not be read (%s)" % (ext.lstrip("."), type(e).__name__)
        if os.path.isfile(os.path.join(BRAIN, stem_md.replace("/", os.sep))):
            out["source"] = stem_md   # the markdown it was exported from, when it sits beside it
    else:
        out["kind"] = "other"
    return 200, out
