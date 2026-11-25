#!/usr/bin/env python3
"""Regenerates fixtures/stress.fodt (standard library only): a flat-ODT with TWO columns, justified text with ligatures/accents,
cross-references and a bordered table. Converted to PDF by LibreOffice it is the hardest non-reportlab PDF in the tests."""
import sys
from pathlib import Path
para = ("The coordinator must approve the payment request within three working days; otherwise the request is cancelled automatically and the "
        "student is notified by e-mail. Efficient office workflow: final ﬁle, ﬂow and eﬃcient handling of Öğrenci İşleri, İstanbul Şişli, ağır çalışma. "
        "Interoperability requirements, internationalization considerations and responsibilities are described in section ")
body = "".join(f'<text:p text:style-name="J">{i}. {para}{i}.{i}. (see UC-{i}.1 and QR-G.{i}).</text:p>' for i in range(1, 13))
rows = (["Item", "Value", "Unit"], ["Reminder", "3", "days"], ["Fee", "250", "EUR"], ["Timeout", "15", "minutes"])
tbl = ('<table:table table:name="T"><table:table-column table:number-columns-repeated="3"/>'
       + "".join('<table:table-row>' + "".join(f'<table:table-cell table:style-name="C" office:value-type="string"><text:p>{c}</text:p></table:table-cell>' for c in r) + '</table:table-row>' for r in rows)
       + '</table:table>')
doc = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
<office:automatic-styles>
<style:page-layout style:name="pm1"><style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" fo:margin-left="2cm" fo:margin-right="2cm" fo:margin-top="2cm" fo:margin-bottom="2cm"><style:columns fo:column-count="2" fo:column-gap="1cm"/></style:page-layout-properties></style:page-layout>
<style:style style:name="J" style:family="paragraph"><style:paragraph-properties fo:text-align="justify" fo:margin-bottom="0.2cm"/><style:text-properties fo:hyphenate="true" fo:font-size="10pt" fo:language="en" fo:country="US"/></style:style>
<style:style style:name="C" style:family="table-cell"><style:table-cell-properties fo:border="0.5pt solid #000000" fo:padding="0.1cm"/></style:style>
</office:automatic-styles>
<office:master-styles><style:master-page style:name="Standard" style:page-layout-name="pm1"/></office:master-styles>
<office:body><office:text>{body}{tbl}</office:text></office:body></office:document>'''
out = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures") / "stress.fodt"
out.write_text(doc, encoding="utf-8"); print("wrote", out)
