"""Maintainer utility: strip reference project data while retaining actual template styling.

Usage: python templates/prepare_template.py MASTER.docx HEB_REFERENCE.docx
The source files are read only. Sanitized output is written beside this script.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as E
from zipfile import ZipFile, ZIP_DEFLATED

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/package/2006/relationships'
def w(n): return '{' + W + '}' + n

def prepare(master, reference):
    destination = Path(__file__).resolve().parent
    with ZipFile(master) as z: parts = {n: z.read(n) for n in z.namelist()}
    root = E.fromstring(parts['word/document.xml'])
    # The rebuilt document uses baseline WordprocessingML only. ElementTree drops
    # unused namespace declarations, so stale mc:Ignorable prefix lists are invalid.
    root.attrib.clear()
    body = root.find(w('body')); paragraphs = body.findall(w('p'))
    with ZipFile(reference) as z:
        ref = E.fromstring(z.read('word/document.xml')).find(w('body')).findall(w('p'))
    def props(p):
        node = p.find(w('pPr'))
        return E.tostring(node, encoding='unicode') if node is not None else ''
    layout = {'cover': [props(p) for p in paragraphs[:21]],
              'links_heading': props(ref[20]), 'group': props(ref[21]),
              'entry': props(ref[22]), 'field': props(ref[24])}
    (destination / 'layout.json').write_text(json.dumps(layout, indent=2), encoding='utf-8')
    section = deepcopy(body.find(w('sectPr')))
    body.clear(); body.append(section)
    parts['word/document.xml'] = E.tostring(root, encoding='utf-8', xml_declaration=True)
    # Whitelist necessary style parts: do not ship images, author metadata, comments, thumbnails, or old links.
    allowed = {'[Content_Types].xml', '_rels/.rels', 'word/document.xml', 'word/styles.xml',
               'word/fontTable.xml', 'word/theme/theme1.xml', 'word/numbering.xml',
               'word/_rels/document.xml.rels'}
    parts = {n: v for n, v in parts.items() if n in allowed}
    rels = E.Element('Relationships', xmlns=R)
    for number, (name, typ) in enumerate([('styles.xml','styles'), ('fontTable.xml','fontTable'),
                                        ('theme/theme1.xml','theme'), ('numbering.xml','numbering')]):
        if 'word/' + name in parts:
            E.SubElement(rels, 'Relationship', Id=f'rId{number+1}', Target=name,
                         Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/' + typ)
    parts['word/_rels/document.xml.rels'] = E.tostring(rels, encoding='utf-8', xml_declaration=True)
    parts['_rels/.rels'] = (f'<Relationships xmlns="{R}"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>').encode()
    ct = E.fromstring(parts['[Content_Types].xml'])
    for n in list(ct):
        if n.get('PartName') and n.get('PartName').lstrip('/') not in parts: ct.remove(n)
    parts['[Content_Types].xml'] = E.tostring(ct, encoding='utf-8', xml_declaration=True)
    with ZipFile(destination / 'master.docx', 'w', ZIP_DEFLATED) as z:
        for n, v in parts.items(): z.writestr(n, v)
    manifest = {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (master, reference)}
    (destination / 'provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

if __name__ == '__main__': prepare(*sys.argv[1:])
