import unittest
from materials.core import parse_text, InputError

BASE = "Group: Resilient\nTag: VCT-2\nDetail: Armstrong Flooring, Pearl White 51803\n"
URL = "https://www.armstrongflooring.com/commercial/item/51803.html"

class LinkImportTests(unittest.TestCase):
    def test_markdown_with_duplicate_chatgpt_citation(self):
        text = BASE + f"Link: [{URL}]({URL}) [Armstrong Flooring Commercial]({URL}?utm_source=chatgpt.com)"
        self.assertEqual(parse_text(text).materials[0]['link'], URL)

    def test_evidence_fields_and_autolinks(self):
        text = BASE + f"Size: 12 x 24 inches\nSize Source: manufacturer\nSize Evidence: [Product sheet]({URL})\nLink: <{URL}>"
        self.assertEqual(parse_text(text).materials[0]['size_evidence'], URL)
        self.assertEqual(parse_text(text).materials[0]['link'], URL)

    def test_different_product_links_are_not_silently_discarded(self):
        with self.assertRaises(InputError):
            parse_text(BASE + f"Link: [Product]({URL}) [Other](https://example.com/other)")

    def test_unsafe_and_mismatched_display_urls_rejected(self):
        for value in ["[Product](javascript:alert(1))", "[Product](https://user:password@example.com/x)",
                      f"[https://example.com/other]({URL})"]:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_text(BASE + 'Link: ' + value)

    def test_meaningful_query_and_parentheses_preserved(self):
        url = 'https://example.com/product(tile)?color=blue'
        self.assertEqual(parse_text(BASE + f'Link: [Product]({url})').materials[0]['link'], url)

    def test_plain_url_with_duplicate_citation(self):
        self.assertEqual(parse_text(BASE + f'Link: {URL} [Source]({URL}?utm_source=chatgpt.com)').materials[0]['link'], URL)

if __name__ == '__main__': unittest.main()
