"""Word generation from the sanitized supplied master; no Office dependency."""
from copy import deepcopy
from datetime import date, datetime
from io import BytesIO
import json
from pathlib import Path
import re
from xml.etree import ElementTree as E
from zipfile import ZipFile, ZIP_DEFLATED
from zoneinfo import ZoneInfo
from .core import GROUPS, validate

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
E.register_namespace('w', W)
E.register_namespace('r', R)
ROOT = Path(__file__).resolve().parent.parent
DISCLAIMER = 'Tile pattern estimated for Quantity purpose only. Please don’t use it for shop drawing.'

def w(name): return '{' + W + '}' + name

def run(parent, text, bold=False, underline=False, color=None, yellow=False):
    r = E.SubElement(parent, w('r'))
    pr = E.SubElement(r, w('rPr'))
    E.SubElement(pr, w('rFonts'), {w('ascii'): 'Calibri', w('hAnsi'): 'Calibri', w('cs'): 'Calibri'})
    E.SubElement(pr, w('sz'), {w('val'): '22'})
    if bold: E.SubElement(pr, w('b'))
    if underline: E.SubElement(pr, w('u'), {w('val'): 'single'})
    if color: E.SubElement(pr, w('color'), {w('val'): color})
    if yellow: E.SubElement(pr, w('highlight'), {w('val'): 'yellow'})
    for i, line in enumerate(text.splitlines() or ['']):
        if i: E.SubElement(r, w('br'))
        E.SubElement(r, w('t'), {'{http://www.w3.org/XML/1998/namespace}space': 'preserve'}).text = line
    return r

def paragraph(body, properties=None, keep=True, after=None):
    p = E.SubElement(body, w('p'))
    pr = E.fromstring(properties) if properties else E.Element(w('pPr'))
    p.append(pr)
    for node in list(pr):
        if node.tag in (w('keepNext'), w('keepLines')): pr.remove(node)
    E.SubElement(pr, w('keepLines'))
    if keep: E.SubElement(pr, w('keepNext'))
    if after is not None:
        spacing = pr.find(w('spacing'))
        if spacing is None: spacing = E.SubElement(pr, w('spacing'))
        spacing.set(w('after'), str(after))
    return p

def field(body, label, value, props=None, keep=True, yellow=False, color=None):
    p = paragraph(body, props, keep)
    run(p, label + ': ', bold=True, yellow=yellow, color=color)
    run(p, value, yellow=yellow, color=color)
    return p


def detail_with_size(material):
    """Include supplied dimensions before a comma-delimited installation clause."""
    detail = material['detail']
    size = material['size']
    if not size:
        return detail
    # Repeat is already added to Detail by validation; insert dimensions separately.
    dimensions = re.split(r",?\s*Pattern Repeat\b", size, maxsplit=1, flags=re.I)[0].strip(' ,;')
    if not dimensions:
        return detail
    clauses = re.split(r'\s*[,;]\s*', detail)
    installation = re.compile(
        r'^(?:install(?:ation|ed)?\b|lay(?:ing)?\b|pattern\s*:|'
        r'ashlar\b|monolithic\b|quarter[ -]turn\b|herringbone\b|'
        r'running bond\b|stack(?:ed)?(?: bond)?\b|brick(?:work)?\b|'
        r'random\b|(?:\d+%|third|half) offset\b|glue[ -]down\b|'
        r'full[ -]spread\b|direct[ -]glue\b|loose[ -]lay\b)', re.I)
    # Move an existing standalone size, preserving all other source wording.
    clauses = [c for c in clauses if c.casefold() != dimensions.casefold()]
    if not any(dimensions.casefold() in c.casefold() for c in clauses):
        index = next((i for i, c in enumerate(clauses) if installation.match(c)), len(clauses))
        clauses.insert(index, dimensions)
    return ', '.join(clauses)


def generate_docx(report, generated_on=None, drawing_image=None):
    # Revalidate at the output boundary, including reports from alternate callers.
    report = validate({'project': report.project, 'materials': report.materials})
    styles = json.loads((ROOT / 'templates/layout.json').read_text(encoding='utf-8'))
    with ZipFile(ROOT / 'templates/master.docx') as z:
        parts = {n: z.read(n) for n in z.namelist()}
    root = E.fromstring(parts['word/document.xml'])
    root.attrib.clear()
    body = root.find(w('body'))
    section = deepcopy(body.find(w('sectPr')))
    body.clear()
    meta = report.project
    today = generated_on or datetime.now(ZoneInfo('Asia/Karachi')).date()
    if meta['generation_date']: today = date.fromisoformat(meta['generation_date'])
    cover = styles['cover']
    field(body, 'Date', today.strftime('%B %d, %Y'), cover[0])
    for _ in range(2): paragraph(body)
    p = paragraph(body, cover[3]); run(p, 'Material List', True, True)
    paragraph(body)
    for index, key, label in [(5, 'project', 'Project'), (6, 'architect', 'Architect'),
                               (7, 'drawing_date', 'Date on Drawings'), (8, 'area', 'Area'), (9, 'scale', 'Scale')]:
        p = field(body, label, meta[key], cover[index])
        E.SubElement(p.find(w('r') + '/' + w('rPr')), w('u'), {w('val'): 'single'})
    paragraph(body)
    field(body, 'Disclaimer', DISCLAIMER, cover[11])
    paragraph(body)
    p = paragraph(body, cover[13]); run(p, 'SPECIFICATIONS', True, True)
    if meta['specifications'].lower() == 'yes':
        p = paragraph(body, cover[14]); run(p, 'Specification provided as a separate file', color='FF0000')
    else: paragraph(body)
    paragraph(body)
    p = paragraph(body, cover[17]); run(p, 'DRAWING SET', True, True)
    paragraph(body, keep=False)
    # Drawing Set is deliberately blank unless an explicit screenshot is supplied through the UI.
    rels = E.fromstring(parts['word/_rels/document.xml.rels'])
    if drawing_image:
        insert_drawing(body, drawing_image, parts, rels)
    p = paragraph(body, styles['links_heading'])
    run(p, 'MATERIAL VERIFICATION LINKS', True, True)
    for group in GROUPS:
        items = [m for m in report.materials if m['group'] == group]
        if not items: continue
        p = paragraph(body, styles['group'])
        run(p, 'Trims and Transition' if group == 'Trim/Transition' else group, True)
        for m in items:
            compact = group in ('Base', 'Grout', 'Trim/Transition')
            title = m['tag']
            if m['type']: title = f'{title} ({m["type"]})' if title else m['type']
            detail = detail_with_size(m)
            color = 'FF0000' if m['scope'] == 'nic' else None
            if m['scope'] == 'nic': detail += ', NIC / Not Estimated'
            if m['scope'] == 'existing': detail += ', Existing — not new procurement'
            p = paragraph(body, styles['entry'])
            run(p, title + (': ' if compact else ''), True, color=color)
            if compact: run(p, detail, color=color)
            if m['link'] and not compact:
                p = paragraph(body, styles['field']); run(p, 'Link: ', True)
                rid = 'materialLink' + str(len(rels))
                E.SubElement(rels, '{' + REL + '}Relationship', {'Id': rid, 'Type': R + '/hyperlink',
                              'Target': m['link'], 'TargetMode': 'External'})
                link = E.SubElement(p, w('hyperlink'), {'{' + R + '}id': rid})
                run(link, m['link'], underline=True, color='0000FF')
            if not compact: field(body, 'Detail', detail, styles['field'], color=color)
            if m['size']:
                size = m['size']
                sourced = m['size_source'] in ('manufacturer', 'mixed')
                if sourced: size += ' (Size Taken from Manufacturer Website)'
                # Compact descriptions retain explicit size information on a separate line when supplied.
                field(body, 'Size', size, styles['field'], yellow=sourced or size == 'SFT Estimated')
            for key in ('location', 'grout', 'note'):
                if m[key]: field(body, key.title(), m[key], styles['field'])
            # Last visible paragraph ends the keep-next chain; blank separator remains with neither entry.
            last_pr = list(body)[-1].find(w('pPr'))
            keep = last_pr.find(w('keepNext'))
            if keep is not None: last_pr.remove(keep)
            paragraph(body, keep=False, after=100)
    body.append(section)
    parts['word/document.xml'] = E.tostring(root, encoding='utf-8', xml_declaration=True)
    parts['word/_rels/document.xml.rels'] = E.tostring(rels, encoding='utf-8', xml_declaration=True)
    result = BytesIO()
    with ZipFile(result, 'w', ZIP_DEFLATED) as z:
        for name, content in parts.items(): z.writestr(name, content)
    return result.getvalue()

def insert_drawing(body, image, parts, rels):
    from PIL import Image
    with Image.open(BytesIO(image)) as im:
        width, height = im.size
    cx = int(6.8 * 914400); cy = int(cx * height / width)
    if cy > 3 * 914400:
        cx = int(cx * (3 * 914400) / cy); cy = 3 * 914400
    rid = 'drawingSetImage'
    E.SubElement(rels, '{' + REL + '}Relationship', {'Id': rid, 'Type': R + '/image', 'Target': 'media/drawing-set.png'})
    parts['word/media/drawing-set.png'] = image
    types = E.fromstring(parts['[Content_Types].xml'])
    ct = 'http://schemas.openxmlformats.org/package/2006/content-types'
    if not any(n.get('Extension') == 'png' for n in types):
        E.SubElement(types, '{' + ct + '}Default', {'Extension': 'png', 'ContentType': 'image/png'})
    parts['[Content_Types].xml'] = E.tostring(types, encoding='utf-8', xml_declaration=True)
    p = paragraph(body, keep=False)
    r = E.SubElement(p, w('r'))
    r.append(E.fromstring(f'''<w:drawing xmlns:w="{W}" xmlns:r="{R}"
        xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
        xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <wp:inline><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="1" name="Drawing Set"/>
        <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="Drawing Set"/><pic:cNvPicPr/></pic:nvPicPr>
        <pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
        <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>
        </a:graphicData></a:graphic></wp:inline></w:drawing>'''))

def filename(report):
    name = re.sub(r'[^\w\- ]', '', report.project['project']).strip().replace(' ', '_')[:90]
    return (name or 'Flooring') + '_Material_List.docx'
