"""Strict, offline import and shared material validation. Never calls an AI."""
from dataclasses import dataclass
import json
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

GROUPS = ('Carpet', 'Resilient', 'Wood', 'Ceramic', 'Concrete/Epoxy/Terrazzo',
          'Base', 'Grout', 'Trim/Transition')
PROJECT_FIELDS = ('project', 'architect', 'drawing_date', 'area', 'scale', 'generation_date', 'specifications')
MATERIAL_FIELDS = ('group', 'tag', 'type', 'detail', 'size', 'size_source', 'size_evidence',
                   'location', 'grout', 'note', 'link', 'source', 'system', 'repeat',
                   'repeat_source', 'repeat_evidence', 'scope')
LABELS = {'date on drawings': 'drawing_date', 'drawing date': 'drawing_date',
          'date': 'generation_date', 'locations': 'location'}
EMPTY = {'n/a', 'na', 'tbd', 'not provided', 'not available', 'none', 'unknown',
         'confirm with manufacturer', 'not specified', 'unspecified', '-'}
MAX_TEXT = 500_000
DIMENSION = r'\d+(?:[./-]\d+)*(?:\s+\d+/\d+)?\s*(?:inches|inch|in\b|mm\b|cm\b|ft\b|feet|[\"\u2033\u2032\x27])?\s*(?:[WLH]\b)?'
THREE_AXES = re.compile(DIMENSION + r'\s*[x×]\s*' + DIMENSION + r'\s*[x×]\s*\d', re.I)

class InputError(ValueError):
    """Actionable input problem safe to display to the user."""

@dataclass
class Report:
    project: dict
    materials: list
    warnings: list

def clean(value):
    if not isinstance(value, str):
        raise InputError('All field values must be text; use an empty string for missing information.')
    value = value.strip()
    if len(value) > 12000:
        raise InputError('A field is too long (maximum 12,000 characters).')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise InputError('Remove unsupported control characters from the input.')
    return '' if value.casefold().rstrip('.') in EMPTY else value

def valid_url(value):
    try:
        p = urlsplit(value)
        return (p.scheme in ('https', 'http') and bool(p.hostname) and
                not p.username and not p.password and not any(c.isspace() for c in value) and
                not any(c in value for c in '<>[]'))
    except ValueError:
        return False

def normalize_link(value):
    """Accept ChatGPT Markdown wrappers, but never choose between different targets."""
    def identity(url):
        parsed = urlsplit(url)
        # Compare citation duplicates ignoring tracking only, not product selectors.
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_')]
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path,
                           urlencode(query), parsed.fragment))

    value = value.strip()
    if value.startswith('<') and value.endswith('>'):
        value = value[1:-1]
    if valid_url(value):
        return value
    pattern = re.compile(r'\[([^\]]*)\]\((https?://(?:[^()\s]|\([^()\s]*\))+)\)')
    targets = []
    cursor = 0
    for match in pattern.finditer(value):
        gap = value[cursor:match.start()].strip()
        if gap:
            if cursor == 0 and valid_url(gap): targets.append(gap)
            else: raise InputError('Use one plain URL or a Markdown link; remove extra text from this field.')
        display, target = match.groups()
        if not valid_url(target): raise InputError('Link target must be an http(s) URL without credentials or spaces.')
        if display.startswith(('https://', 'http://')) and identity(display) != identity(target):
            raise InputError('The displayed URL and link destination differ. Supply the intended plain URL.')
        targets.append(target)
        cursor = match.end()
    if not targets or value[cursor:].strip():
        raise InputError('Use an http(s) URL without credentials or spaces, or a Markdown link to that URL.')
    if len({identity(target) for target in targets}) != 1:
        raise InputError('Multiple different links were supplied. Keep the intended product URL in this field; put other sources in Note.')
    return targets[0]

def no_duplicate_keys(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj: raise InputError(f'Duplicate field: {k}. Keep one value or explain the conflict in Note.')
        obj[k] = v
    return obj

def parse_text(text):
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise InputError('Input must be text under 500,000 characters.')
    text = text.lstrip('\ufeff').strip()
    if text.startswith('```') and text.endswith('```'):
        text = '\n'.join(text.splitlines()[1:-1]).strip()
    if not text: raise InputError('Paste ChatGPT’s material output or upload a text file first.')
    if text.startswith('{'):
        try: return validate(json.loads(text, object_pairs_hook=no_duplicate_keys))
        except json.JSONDecodeError as e:
            raise InputError(f'Invalid JSON at line {e.lineno}. Use the provided ChatGPT prompt.') from None
    project, items, current = {}, [], None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().replace('**', '')
        if not line or line in ('---', '```', '```text'): continue
        line = re.sub(r'^[-*]\s+', '', line)
        if ':' not in line:
            raise InputError(f'Line {number}: expected Label: value. Use the provided prompt; keep each field on one line.')
        label, value = line.split(':', 1)
        key = LABELS.get(label.lower().strip(), label.lower().strip().replace(' ', '_'))
        value = value.strip()
        if key == 'group':
            current = {'group': value}
            items.append(current)
        elif key in PROJECT_FIELDS and current is None:
            if key in project: raise InputError(f'Line {number}: duplicate {label} field.')
            project[key] = value
        elif current is not None and key in MATERIAL_FIELDS:
            if key in current: raise InputError(f'Line {number}: duplicate {label}. Start each material with Group:')
            current[key] = value
        else:
            raise InputError(f'Line {number}: unrecognized or misplaced field “{label}”. Project fields go first; each material starts with Group:')
    return validate({'project': project, 'materials': items})

def validate(data):
    if not isinstance(data, dict) or set(data) - {'project', 'materials'}:
        raise InputError('Expected project and materials fields only.')
    raw_project = data.get('project', {})
    if not isinstance(raw_project, dict) or set(raw_project) - set(PROJECT_FIELDS):
        raise InputError('Project contains unsupported fields.')
    project = {k: clean(raw_project.get(k, '')) for k in PROJECT_FIELDS}
    if project['generation_date']:
        from datetime import date
        try: date.fromisoformat(project['generation_date'])
        except ValueError: raise InputError('Date must use YYYY-MM-DD, or leave it blank for today.') from None
    if project['specifications'].lower() not in ('', 'yes', 'no'):
        raise InputError('Specifications must be yes or no; yes means a separate file was supplied or explicitly requested.')
    items = data.get('materials')
    if not isinstance(items, list) or not 1 <= len(items) <= 300:
        raise InputError('Provide between 1 and 300 material entries.')
    normalized, warnings, seen = [], [], set()
    for index, raw in enumerate(items, 1):
        if not isinstance(raw, dict) or set(raw) - set(MATERIAL_FIELDS):
            raise InputError(f'Material {index}: unsupported fields. Use the supplied format.')
        m = {k: clean(raw.get(k, '')) for k in MATERIAL_FIELDS}
        label = m['tag'] or f'Material {index}'
        group = next((g for g in GROUPS if g.lower() == m['group'].lower()), None)
        if not group: raise InputError(f'{label}: Group must be one of: {", ".join(GROUPS)}.')
        m['group'] = group
        if not m['detail']: raise InputError(f'{label}: Detail is required. Keep a source-supported description.')
        if not m['tag'] and not m['type']:
            raise InputError(f'Material {index}: supply a source Tag or Type; do not invent a tag.')
        for field in ('link', 'size_evidence', 'repeat_evidence'):
            if m[field]:
                try: m[field] = normalize_link(m[field])
                except InputError as exc:
                    raise InputError(f'{label}: {field.replace("_", " ")}: {exc}') from None
        for field in ('size_source', 'repeat_source'):
            m[field] = m[field].lower()
            if m[field] not in ('', 'drawing', 'manufacturer', 'mixed'):
                raise InputError(f'{label}: {field} must be drawing, manufacturer, or mixed.')
        # Block ambiguous dimensions instead of heuristically deleting legitimate heights or product codes.
        for field in ('tag', 'type', 'detail', 'size', 'location', 'grout', 'note', 'repeat'):
            value = m[field]
            if re.search(r'\b(thick(?:ness)?|gauge|wear[- ]layer)\b', value, re.I):
                raise InputError(f'{label}: remove material thickness from {field}. Keep base height and grout-joint width.')
            if THREE_AXES.search(value):
                raise InputError(f'{label}: review three-axis dimensions in {field}; provide length/width without thickness.')
            if re.search(r'\b(?:TBD|N/A|Not Provided|Not Available|Confirm with Manufacturer)\b', value, re.I):
                if field != 'note':
                    raise InputError(f'{label}: remove placeholder wording from {field}; leave unsupported fields blank.')
        if m['size'] and not m['size_source'] and m['size'] != 'SFT Estimated':
            raise InputError(f'{label}: supply Size Source (drawing, manufacturer, or mixed).')
        if m['size_source'] in ('manufacturer', 'mixed') and m['size'] and not m['size_evidence']:
            raise InputError(f'{label}: a manufacturer-derived size needs its official URL in Size Evidence.')
        if m['repeat']:
            if not m['repeat_source']: raise InputError(f'{label}: supply Repeat Source.')
            if not m['size_source']: m['size_source'] = m['repeat_source']
            if m['repeat_source'] in ('manufacturer', 'mixed'):
                if not m['repeat_evidence']: raise InputError(f'{label}: supply the official Repeat Evidence URL.')
                m['size_source'] = 'mixed' if m['size_source'] == 'drawing' else 'manufacturer'
                m['size_evidence'] = m['size_evidence'] or m['repeat_evidence']
            repeat = 'Pattern Repeat ' + m['repeat']
            for field in ('detail', 'size'):
                if repeat not in m[field]: m[field] = ', '.join(filter(None, (m[field], repeat)))
        elif 'broadloom' in m['type'].lower():
            warnings.append(f'{label}: no verified repeat supplied; repeat omitted. Check the official product literature.')
        m['system'] = m['system'].lower()
        if m['system'] not in ('', 'poured', 'unit'):
            raise InputError(f'{label}: System must be poured or unit when supplied.')
        if m['system'] == 'poured':
            if group != 'Concrete/Epoxy/Terrazzo': raise InputError(f'{label}: poured systems belong in Concrete/Epoxy/Terrazzo.')
            if m['size'] and m['size'] != 'SFT Estimated': raise InputError(f'{label}: a poured system cannot have a unit size.')
            m['size'] = 'SFT Estimated'
            m['size_source'] = ''
            if 'SFT Estimated' not in m['detail']: m['detail'] += ', SFT Estimated'
        elif m['size'] == 'SFT Estimated':
            raise InputError(f'{label}: specify System: poured for SFT Estimated.')
        m['scope'] = m['scope'].lower() or 'included'
        if m['scope'] not in ('included', 'nic', 'existing'):
            raise InputError(f'{label}: Scope must be included, nic, or existing.')
        if group == 'Base' and re.search(r'\b(wood|mdf|millwork)\b', m['type'], re.I) and m['scope'] == 'included':
            m['scope'] = 'nic'
            warnings.append(f'{label}: architectural wood/MDF base marked NIC / Not Estimated.')
        identity = (m['group'], m['tag'].casefold(), m['type'].casefold(), m['location'].casefold())
        if identity in seen: raise InputError(f'{label}: duplicate entry. Combine matching entries or distinguish actual functions/locations.')
        seen.add(identity)
        if not m['source']: warnings.append(f'{label}: no drawing/source reference supplied.')
        if group in ('Base', 'Grout', 'Trim/Transition') and m['link']:
            warnings.append(f'{label}: Link omitted for the compact {group} format.')
        normalized.append(m)
    normalized.sort(key=lambda m: GROUPS.index(m['group']))
    warnings.append('Source facts and manufacturer URLs require review. Imported evidence is not independent verification by this app.')
    return Report(project, normalized, warnings)
