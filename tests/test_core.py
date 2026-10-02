import io
import json
import unittest
from datetime import date
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from materials.core import parse_text, validate, InputError
from materials.document import generate_docx

SAMPLE = '''Project: Sample Clinic
Architect: Example Architect
Date on Drawings: 2026-09-10

Group: Ceramic
Tag: T-1
Type: Porcelain Floor Tile
Detail: Example Tile, Stone, Gray
Size: 12 x 24 inches
Size Source: drawing
Location: Lobby 101
Source: A601 row T-1

Group: Base
Tag: RB-1
Detail: Example Rubber, Blue, 4-inch height
Location: Lobby 101
'''
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

class CoreTests(unittest.TestCase):
    def test_word_compatibility_prefixes_are_declared(self):
        with ZipFile(io.BytesIO(generate_docx(parse_text(SAMPLE)))) as z:
            xml = z.read('word/document.xml')
        namespaces = dict(E for _, E in ET.iterparse(io.BytesIO(xml), events=['start-ns']))
        root = ET.fromstring(xml)
        for prefix in root.get('{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable', '').split():
            self.assertIn(prefix, namespaces)

    def test_repeat_without_width_roundtrips(self):
        report = parse_text('Group: Carpet\nTag: C1\nType: Broadloom Carpet\nDetail: Specified carpet\nRepeat: 6 inches W x 2 inches L\nRepeat Source: drawing')
        self.assertTrue(generate_docx(report).startswith(b'PK'))

    def test_alternative_sizes_in_notes_are_not_thickness(self):
        report = parse_text('Group: Ceramic\nTag: T1\nDetail: Specified tile\nNote: Drawing shows 12 x 24 or 24 x 48')
        self.assertIn('12 x 24 or 24 x 48', report.materials[0]['note'])

    def test_import_and_generation_preserve_source_fields(self):
        report = parse_text(SAMPLE)
        self.assertEqual(report.project['project'], 'Sample Clinic')
        self.assertEqual(len(report.materials), 2)
        output = generate_docx(report, date(2026, 10, 1))
        with ZipFile(io.BytesIO(output)) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            text = ''.join(root.itertext())
            self.assertIn('Sample Clinic', text)
            self.assertIn('October 01, 2026', text)
            self.assertIn('Lobby 101', text)
            self.assertNotIn('Christ', text)
            self.assertNotIn('H-E-B', text)
            self.assertFalse(any(n.startswith('word/media/') for n in z.namelist()))
            self.assertEqual(root.find('.//w:pgSz', NS).get('{%s}w' % NS['w']), '12240')

    def test_unknown_lines_and_duplicate_fields_rejected(self):
        for extra in ['\nSomething: discarded?', '\nLocation: duplicate']:
            with self.assertRaises(InputError):
                parse_text(SAMPLE + extra)

    def test_thickness_is_blocked_not_silently_removed(self):
        for thickness in ['6 mm thick', 'Thickness 3/8 inch', '12 x 24 x 0.4 inches']:
            with self.subTest(thickness=thickness), self.assertRaises(InputError):
                parse_text(SAMPLE.replace('12 x 24 inches', thickness))

    def test_preserve_base_height_and_joint_width(self):
        report = parse_text(SAMPLE.replace('Example Rubber, Blue, 4-inch height',
                                          'Example Rubber, 4-inch height, 1/8-inch grout joint'))
        self.assertIn('4-inch height', report.materials[1]['detail'])

    def test_json_and_labeled_input_agree(self):
        first = parse_text(SAMPLE)
        second = parse_text(json.dumps({'project': first.project, 'materials': first.materials}))
        self.assertEqual(first.materials, second.materials)

    def test_manufacturer_size_requires_url_and_highlights_whole_line(self):
        bad = SAMPLE.replace('Size Source: drawing', 'Size Source: manufacturer')
        with self.assertRaises(InputError): parse_text(bad)
        report = parse_text(bad.replace('Source: A601 row T-1',
                    'Source: A601 row T-1\nSize Evidence: https://example.com/tile'))
        with ZipFile(io.BytesIO(generate_docx(report))) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            p = next(p for p in root.findall('.//w:p', NS)
                     if ''.join(p.itertext()).startswith('Size:'))
            self.assertIn('(Size Taken from Manufacturer Website)', ''.join(p.itertext()))
            for r in p.findall('w:r', NS):
                self.assertIsNotNone(r.find('w:rPr/w:highlight', NS))

    def test_poured_system_and_compact_groups(self):
        report = parse_text('Group: Concrete/Epoxy/Terrazzo\nTag: C-1\nType: Sealed Concrete\nDetail: Sealed concrete\nSystem: poured')
        self.assertEqual(report.materials[0]['size'], 'SFT Estimated')
        self.assertIn('SFT Estimated', report.materials[0]['detail'])

    def test_unsafe_link_and_unknown_json_keys_rejected(self):
        with self.assertRaises(InputError):
            parse_text(SAMPLE + '\nLink: javascript:alert(1)')
        with self.assertRaises(InputError): validate({'materials': [], 'ignored': 'value'})

    def test_same_tag_different_functions_allowed_exact_duplicates_rejected(self):
        report = parse_text(SAMPLE)
        material = report.materials[0]
        with self.assertRaises(InputError):
            validate({'materials': [material, material]})
        other = dict(material, type='Porcelain Wall Tile')
        self.assertEqual(len(validate({'materials': [material, other]}).materials), 2)

    def test_placeholders_omitted(self):
        report = parse_text(SAMPLE.replace('Location: Lobby 101', 'Location: N/A'))
        self.assertEqual(report.materials[0]['location'], '')

    def test_broadloom_repeat_in_both_fields(self):
        report = parse_text('Group: Carpet\nTag: C1\nType: Broadloom Carpet\nDetail: Example carpet\nSize: 12 ft W\nSize Source: drawing\nRepeat: 6 inches W x 2 inches L\nRepeat Source: drawing')
        self.assertIn('Pattern Repeat 6 inches', report.materials[0]['detail'])
        self.assertIn('Pattern Repeat 6 inches', report.materials[0]['size'])

if __name__ == '__main__': unittest.main()
