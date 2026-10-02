"""Run from this folder: python -m streamlit run app.py"""
import json
import os
from pathlib import Path
import streamlit as st
from materials.core import InputError, parse_text
from materials.document import generate_docx, filename
from materials.prompts import manual_prompt
from materials import api

ROOT = Path(__file__).resolve().parent
MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
st.set_page_config(page_title='Material List Generator', page_icon='📋', layout='centered')

def setting(name, default=''):
    if name in os.environ: return os.environ[name]
    try: return st.secrets.get(name, default)
    except st.errors.StreamlitSecretNotFoundError: return default

def clear_result(): st.session_state.pop('result', None)

def access_check():
    if str(setting('AUTH_REQUIRED', 'false')).lower() != 'true': return
    # For Railway/public hosting, require OIDC AND an explicit email allowlist.
    allowed = {e.strip().casefold() for e in str(setting('ALLOWED_EMAILS')).split(',') if e.strip()}
    if not allowed:
        st.error('Team access is not configured. The owner must set ALLOWED_EMAILS.'); st.stop()
    if not st.user.is_logged_in:
        st.title('Material List Generator')
        st.write('Sign in with your approved team account.')
        if st.button('Sign in'):
            try: st.login()
            except Exception: st.error('Sign-in is not configured. Ask the app owner to check the authentication settings.')
        st.stop()
    if str(st.user.get('email', '')).casefold() not in allowed or st.user.get('email_verified') is not True:
        st.error('This verified account is not on the team access list.')
        if st.button('Sign out'): st.logout()
        st.stop()
    with st.sidebar:
        st.caption(st.user.get('email', ''))
        if st.button('Sign out'):
            st.session_state.clear(); st.logout()

access_check()
st.title('Material List Generator')
st.write('Turn your flooring schedule into an editable Word material list.')
mode = st.radio('Choose how to add materials', ['Paste ChatGPT Output', 'Use API'],
                horizontal=True, key='mode', on_change=clear_result)

with st.expander('Optional project details'):
    project_override = st.text_input('Project name override', help='Leave blank to use the supplied project name.', on_change=clear_result)
    supplied_area = st.text_input('Area supplied by you', help='Leave blank when no area has been supplied.', on_change=clear_result)
    spec_override = st.checkbox('A separate specification file was supplied, or I want the separate-file sentence', on_change=clear_result)
    drawing_file = st.file_uploader('Drawing Set screenshot (optional)', type=['png','jpg','jpeg'],
                                  key='drawing_set', max_upload_size=20, on_change=clear_result)
    st.caption('Uploading here explicitly includes this screenshot under Drawing Set.')

def save_result(report, usage=None):
    if project_override: report.project['project'] = project_override.strip()
    # Area must be supplied by the user, rather than inferred by the extractor.
    if supplied_area: report.project['area'] = supplied_area.strip()
    if spec_override: report.project['specifications'] = 'yes'
    drawing = api.prepare_image(drawing_file.getvalue(), 'png') if drawing_file else None
    docx = generate_docx(report, drawing_image=drawing)
    st.session_state['result'] = {'report':report, 'docx':docx, 'name':filename(report), 'usage':usage}

if mode == 'Paste ChatGPT Output':
    st.caption('No API key needed. This mode makes no AI requests.')
    with st.expander('1. Get the prompt for ChatGPT'):
        st.write('Copy this prompt using the copy icon, attach your schedule in ChatGPT, and paste its response below.')
        st.code(manual_prompt(), language=None, height=260)
        st.download_button('Download ChatGPT prompt', manual_prompt(), 'flooring-extraction-prompt.txt', on_click='ignore')
    input_kind = st.radio('Add ChatGPT output', ['Paste text', 'Upload text file'], horizontal=True,
                          key='input_kind', on_change=clear_result)
    raw = ''
    if input_kind == 'Paste text':
        raw = st.text_area('2. Paste ChatGPT output', height=280, key='manual_text', on_change=clear_result,
                           placeholder='Project: …\n\nGroup: Ceramic\nTag: T-1\nDetail: …')
    else:
        text_file = st.file_uploader('ChatGPT output (.txt or .json)', type=['txt','json'],
                                    key='manual_file', max_upload_size=1, on_change=clear_result)
        if text_file:
            try: raw = text_file.getvalue().decode('utf-8-sig')
            except UnicodeError: st.error('Save the text file as UTF-8 and upload it again.')
    with st.expander('See the expected format'):
        sample = (ROOT / 'examples/sample-materials.txt').read_text(encoding='utf-8')
        st.caption('Demonstration data only. Replace it with your project information.')
        st.code(sample, language=None)
        st.download_button('Download example', sample, 'sample-materials.txt', on_click='ignore')
    if st.button('Generate Word Document', type='primary', key='generate_manual'):
        clear_result()
        try:
            with st.spinner('Checking materials and formatting your document…'): save_result(parse_text(raw))
        except InputError as e: st.error(str(e))
elif mode == 'Use API':
    key = str(setting('OPENAI_API_KEY'))
    model = str(setting('OPENAI_MODEL', 'gpt-4.1'))
    if not key: st.info('API not configured. Manual mode is ready to use; the owner can add an API key later.')
    st.caption('Extract with API sends the selected page and saved instructions to OpenAI. API usage charges apply.')
    source_file = st.file_uploader('Upload a schedule PDF or picture', type=['pdf','png','jpg','jpeg','webp'],
                                  key='api_file', max_upload_size=20, on_change=clear_result)
    page = 0; image = None
    if source_file:
        try:
            extension = Path(source_file.name).suffix.lstrip('.').lower()
            if extension == 'pdf':
                count = api.page_count(source_file.getvalue())
                page = st.number_input('Page to extract', min_value=1, max_value=count, value=1,
                                       key='selected_page', on_change=clear_result) - 1
            image = api.prepare_image(source_file.getvalue(), extension, page)
            st.image(image, caption=f'Selected source: {source_file.name}' + (f' — page {page+1}' if extension == 'pdf' else ''), width='stretch')
        except InputError as e: st.error(str(e))
    if st.button('Extract with API', type='primary', key='extract_api', disabled=not key or image is None):
        clear_result()
        try:
            with st.spinner('Reading the selected page and generating your Word document…'):
                report, usage = api.extract(image, key, model, f'{source_file.name}, page {page+1}')
                # AI cannot establish that the user specifically supplied a project area/specification file.
                report.project['area'] = supplied_area.strip()
                report.project['specifications'] = 'yes' if spec_override else 'no'
                save_result(report, usage)
        except (InputError, api.APIError) as e: st.error(str(e))

result = st.session_state.get('result')
if result:
    report = result['report']
    st.success(f'Word document ready · {len(report.materials)} materials')
    st.download_button('Download Word Document', result['docx'], result['name'], MIME,
                       type='primary', key='download_docx', on_click='ignore')
    with st.expander('Review extracted materials', expanded=True):
        st.dataframe([{'Group':m['group'], 'Tag':m['tag'], 'Type':m['type'], 'Detail':m['detail'],
                       'Size':m['size'], 'Location':m['location']} for m in report.materials], hide_index=True)
    with st.expander('Source checks and qualifications'):
        st.write('The app checks the supplied fields and formatting. Review source facts before procurement.')
        for warning in report.warnings: st.write('• ' + warning)
        st.caption('Numeric thickness without a clear label may require manual review. Rendering is not visually inspected automatically on the server.')
    st.download_button('Save extracted data', json.dumps({'project':report.project,'materials':report.materials}, ensure_ascii=False, indent=2),
                       'material-data.json', 'application/json', on_click='ignore')
    if result['usage']:
        st.caption(f'API tokens: {result["usage"].get("input_tokens", 0)} input · {result["usage"].get("output_tokens", 0)} output')

st.caption('Your Word template · Editable .docx · No project history stored by this app')
