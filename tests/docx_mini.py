"""Minimal DOCX writer (standard library only) for the test fixtures: paragraphs, tables, real Word comments and tracked changes."""
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
DATE = "2026-03-20T10:00:00Z"


def _t(text, tag="w:t"):
    return f'<{tag} xml:space="preserve">{escape(text)}</{tag}>'


def build_docx(path, blocks, comments=(), tracked=()):
    """blocks: ("p", text) | ("table", rows) | ("img", png_path, width_px, height_px). comments: [(author, text, paragraph_prefix)].
    tracked: [(paragraph_prefix, [("ins"|"del", author, text), ...])]."""
    cid_of = {}
    for i, (author, text, prefix) in enumerate(comments):
        cid_of.setdefault(prefix, []).append(i)
    tr = {}
    for prefix, items in tracked:
        tr.setdefault(prefix, []).extend(items)
    rev = [900]
    media = []  # (zip name, bytes)

    def image(path, wpx, hpx):
        n = len(media) + 1
        media.append((f"word/media/image{n}.png", Path(path).read_bytes()))
        cx, cy = int(wpx) * 9525, int(hpx) * 9525
        return (f'<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
                f'<wp:docPr id="{n}" name="Picture {n}"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{escape(Path(path).name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="rIdImg{n}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')

    def para(text):
        pre = next((k for k in set(list(cid_of) + list(tr)) if text.startswith(k)), None)
        starts = "".join(f'<w:commentRangeStart w:id="{c}"/>' for c in cid_of.get(pre, []))
        ends = "".join(f'<w:commentRangeEnd w:id="{c}"/><w:r><w:commentReference w:id="{c}"/></w:r>' for c in cid_of.get(pre, []))
        extra = ""
        for kind, author, t in tr.get(pre, []):
            rev[0] += 1
            inner = f"<w:r>{_t(t)}</w:r>" if kind == "ins" else f"<w:r>{_t(t, 'w:delText')}</w:r>"
            extra += f'<w:{kind} w:id="{rev[0]}" w:author="{escape(author)}" w:date="{DATE}">{inner}</w:{kind}>'
        return f"<w:p>{starts}<w:r>{_t(text)}</w:r>{ends}{extra}</w:p>"

    body = ""
    for b in blocks:
        if b[0] == "p":
            body += para(b[1])
        elif b[0] == "img":
            body += image(b[1], b[2], b[3])
        else:
            rows = "".join("<w:tr>" + "".join(f"<w:tc>{para(c)}</w:tc>" for c in row) + "</w:tr>" for row in b[1])
            body += f"<w:tbl>{rows}</w:tbl>"
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{body}</w:body></w:document>'
    com = "".join(
        f'<w:comment w:id="{i}" w:author="{escape(a)}" w:date="{DATE}" w:initials="{"".join(w[0] for w in a.split())}"><w:p><w:r>{_t(t)}</w:r></w:p></w:comment>'
        for i, (a, t, _) in enumerate(comments))
    comments_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:comments {NS}>{com}</w:comments>'
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    img_rels = "".join(f'<Relationship Id="rIdImg{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{Path(n).name}"/>'
                       for i, (n, _) in enumerate(media, 1))
    com_rel = '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>' if comments else ""
    drels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             + com_rel + img_rels + '</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc); z.writestr("word/_rels/document.xml.rels", drels)
        if comments:
            z.writestr("word/comments.xml", comments_xml)
        for name, data in media:
            z.writestr(name, data)
