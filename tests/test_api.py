import base64
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from PIL import Image
import pymupdf
from materials.api import extract, prepare_image, page_count, APIError
from materials.core import InputError

class APITests(unittest.TestCase):
    def image(self):
        out = io.BytesIO(); Image.new('RGB', (100, 200), 'white').save(out, format='PNG')
        return out.getvalue()

    def test_missing_key_never_makes_request(self):
        with patch('materials.api.urlopen') as send, self.assertRaises(APIError):
            extract(self.image(), '', 'gpt-4.1')
        send.assert_not_called()

    def test_success_uses_structured_schema_and_no_storage(self):
        content = {'materials': [{'group':'Ceramic','tag':'T1','detail':'Example tile'}]}
        response = {'status':'completed','output':[{'type':'message','content':[
            {'type':'output_text','text':json.dumps(content)}]}], 'usage': {'input_tokens': 100}}
        with patch('materials.api.urlopen') as send:
            send.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
            report, usage = extract(self.image(), 'test-key', 'gpt-4.1')
            payload = json.loads(send.call_args.args[0].data)
        self.assertFalse(payload['store'])
        self.assertEqual(payload['text']['format']['type'], 'json_schema')
        self.assertEqual(report.materials[0]['tag'], 'T1')
        self.assertEqual(usage['input_tokens'], 100)

    def test_truncated_and_refusal_are_not_partial_success(self):
        for response in [{'status':'incomplete'}, {'status':'completed','output':[{'content':[{'type':'refusal','refusal':'No'}]}]}]:
            with patch('materials.api.urlopen') as send:
                send.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
                with self.assertRaises(APIError): extract(self.image(), 'key', 'gpt-4.1')

    def test_http_errors_do_not_echo_keys_or_uploads(self):
        with patch('materials.api.urlopen', side_effect=HTTPError('url',401,'secret-key',{},None)):
            with self.assertRaises(APIError) as exc: extract(self.image(), 'secret-key', 'gpt-4.1')
        self.assertNotIn('secret-key', str(exc.exception))

    def test_pdf_page_selection_and_bad_images(self):
        doc = pymupdf.open(); doc.new_page(); doc.new_page()
        data = doc.tobytes(); doc.close()
        self.assertEqual(page_count(data), 2)
        result = prepare_image(data, 'pdf', 1)
        self.assertTrue(result.startswith(b'\x89PNG'))
        with self.assertRaises(InputError): prepare_image(data, 'pdf', 2)
        with self.assertRaises(InputError): prepare_image(b'not an image', 'png')

if __name__ == '__main__': unittest.main()
