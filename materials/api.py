"""Optional OpenAI adapter. Called only by an explicit Extract action."""
import base64
from io import BytesIO
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
import pymupdf
from .core import InputError, validate
from .prompts import api_prompt, output_schema

MAX_UPLOAD = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000

class APIError(ValueError): pass

def page_count(data):
    if not data or len(data) > MAX_UPLOAD: raise InputError('Upload a PDF/image under 20 MB.')
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            if doc.needs_pass: raise InputError('Upload an unlocked PDF.')
            if not doc.page_count: raise InputError('The PDF has no pages.')
            return doc.page_count
    except InputError: raise
    except Exception: raise InputError('This file could not be opened as a PDF.') from None

def prepare_image(data, extension, page=0):
    if not data or len(data) > MAX_UPLOAD: raise InputError('Upload a PDF/image under 20 MB.')
    if extension.lower().lstrip('.') == 'pdf':
        count = page_count(data)
        if not 0 <= page < count: raise InputError('Select a page within this PDF.')
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            p = doc[page]
            longest = max(p.rect.width, p.rect.height)
            if longest <= 0: raise InputError('The PDF page has invalid dimensions.')
            factor = min(3, 2800 / longest)
            return p.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False).tobytes('png')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in ('PNG','JPEG','WEBP'):
                    raise InputError('Use a PNG, JPEG, or WebP image.')
                if original.width * original.height > MAX_IMAGE_PIXELS:
                    raise InputError('Image is too large; use a crop under 40 megapixels.')
                im = ImageOps.exif_transpose(original).convert('RGB')
                im.thumbnail((2800, 2800))
                out = BytesIO(); im.save(out, format='PNG'); return out.getvalue()
    except InputError: raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise InputError('Could not read this image. Try a smaller PNG or JPEG.') from None

def extract(image, key, model, source='Uploaded page'):
    if not key.strip(): raise APIError('API not configured. Use manual mode or ask the app owner to configure it.')
    if not model.strip(): raise APIError('No API model configured.')
    payload = {'model':model, 'store':False, 'max_output_tokens':14000,
        'instructions':api_prompt(),
        'input':[{'role':'user','content':[
            {'type':'input_text','text':'Extract this schedule. Source label: ' + source[:200]},
            {'type':'input_image','image_url':'data:image/png;base64,' + base64.b64encode(image).decode(), 'detail':'high'}]}],
        'text':{'format':{'type':'json_schema','name':'flooring_materials','strict':True,'schema':output_schema()}}}
    request = Request('https://api.openai.com/v1/responses',
                      data=json.dumps(payload).encode(),
                      headers={'Authorization':'Bearer ' + key, 'Content-Type':'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=180) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000: raise APIError('The API response was too large. Try a smaller schedule crop.')
        result = json.loads(raw)
    except HTTPError as exc:
        exc.close()
        messages = {401:'API key was rejected. Ask the app owner to check it.',
                    403:'This API project cannot access the selected model.',
                    429:'API quota or rate limit reached. Check billing or try again later.',
                    400:'API request rejected. Check the configured model supports image input and structured output.'}
        raise APIError(messages.get(exc.code, f'AI service returned HTTP {exc.code}. Try again later.')) from None
    except (URLError, TimeoutError, OSError):
        raise APIError('Could not reach the AI service or the request timed out. Your upload is retained; no automatic retry was made.') from None
    except (ValueError, UnicodeError): raise APIError('The AI service returned an unreadable response.') from None
    if result.get('status') != 'completed':
        raise APIError('Extraction did not complete. Try a smaller page/crop; no partial document was generated.')
    chunks = []
    for item in result.get('output', []):
        for content in item.get('content', []):
            if content.get('type') == 'refusal': raise APIError('The AI service declined this extraction. Try manual import.')
            if content.get('type') == 'output_text': chunks.append(content.get('text',''))
    try:
        data = json.loads(''.join(chunks))
        if data.get('materials') == []: raise APIError('No flooring materials were found on the selected page.')
        report = validate(data)
    except InputError: raise
    except (ValueError, AttributeError, TypeError):
        raise APIError('The extracted data could not be validated. Try manual import.') from None
    report.warnings.append('API extraction read the selected page only. Official manufacturer web research was not performed.')
    return report, result.get('usage', {})
