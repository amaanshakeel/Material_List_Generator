import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

class AppTests(unittest.TestCase):
    def test_manual_without_key_downloads_and_input_change_clears_result(self):
        with patch('materials.api.extract') as call:
            at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()
            self.assertFalse(at.exception)
            at.text_area(key='manual_text').set_value((ROOT / 'examples/sample-materials.txt').read_text(encoding='utf-8')).run()
            at.button(key='generate_manual').click().run()
            self.assertFalse(at.exception)
            self.assertIn('result', at.session_state)
            self.assertTrue(at.session_state['result']['docx'].startswith(b'PK'))
            at.text_area(key='manual_text').set_value('bad input').run()
            self.assertNotIn('result', at.session_state)
            at.button(key='generate_manual').click().run()
            self.assertTrue(at.error)
            call.assert_not_called()

    def test_api_disabled_without_key(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY':''}):
            at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()
            at.radio(key='mode').set_value('Use API').run()
            self.assertFalse(at.exception)
            self.assertTrue(at.button(key='extract_api').disabled)

    def test_sessions_do_not_share_documents(self):
        first = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()
        first.text_area(key='manual_text').set_value((ROOT / 'examples/sample-materials.txt').read_text(encoding='utf-8')).run()
        first.button(key='generate_manual').click().run()
        second = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()
        self.assertNotIn('result', second.session_state)

if __name__ == '__main__': unittest.main()
