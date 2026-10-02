# Material List Generator

A standalone app for converting flooring material information into an editable Word qualification. It runs independently of PDF Toolkit.

## Start on Windows

Open a terminal in **this folder**:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

After setup, double-click **Start App.bat**. Open the local URL printed in the terminal. No Microsoft Word installation is needed to generate files.

## Manual mode — no API charges

1. Expand **Get the prompt for ChatGPT**. Copy the prompt using the code block's copy icon, or download it.
2. Attach your schedule to ChatGPT with that prompt.
3. Paste its labeled output, or upload a UTF-8 `.txt`/`.json` file.
4. Click **Generate Word Document**, review the material preview, and download.

Use the supplied prompt: arbitrary prose and tables are not silently guessed into fields. Each material starts with `Group:`. Invalid entries show a correction message and never trigger paid AI calls. The example under `examples/` is fictional demonstration data, not a real material specification.

Optional project details let you override the project name, supply area, request the separate-specification sentence, and explicitly insert a Drawing Set screenshot. Other missing cover information remains blank; the generation date uses Asia/Karachi unless an explicit `Date: YYYY-MM-DD` override is supplied.

## Optional API mode

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill `OPENAI_API_KEY`. Environment variables with the same names also work. Never commit the actual secrets file.

`OPENAI_MODEL` defaults to `gpt-4.1`; the selected model must support Responses API image input and strict JSON-schema output. Ordinary API usage is billed separately from a ChatGPT subscription. This app does not use ChatGPT subscription sign-in or automate a shared account.

Choose **Use API**, upload a PDF or image, select the PDF page if applicable, then click **Extract with API**. Only this button sends the prepared page image and instructions to OpenAI. Files are limited to 20 MB; selected page images are capped at 2,800 pixels on the long edge. Dense schedules may need a clearer crop. Failed requests are not retried automatically; a timeout can still represent a billed provider request.

No key is needed for manual mode. The API adapter is tested with simulated success/error responses; live extraction requires your configured API account and a real sample. Never put keys into chat or client-side code.

## Accuracy and limitations

- The packaged Word master is sanitized from your Christ Hospital document, with HEB paragraph formatting for revised entries. Original names, materials, embedded screenshots, hyperlinks, and author metadata are not shipped in it. Template source hashes are recorded in `templates/provenance.json`.
- Both modes use the same validation and Word generator. Manufacturer-derived Size lines are yellow with the required suffix; poured-system Size lines use yellow `SFT Estimated` without that suffix. Base, Grout, and Trim use separate supporting fields.
- Missing data is omitted; unknown fields, duplicate entries, obvious thickness, and ambiguous three-axis dimensions block generation with actionable errors. Numeric thickness without a clear label is not perfectly detectable; review against the source. The app does not certify extraction accuracy or independently verify pasted source claims.
- **No automated manufacturer web research is connected in this version.** The manual prompt asks ChatGPT to verify official sources when browsing is available. The API reads the selected source only, preserves supported drawing facts, and does not invent manufacturer-only sizes or links. URLs and supplied evidence need human review. Broadloom repeats absent from the input are omitted and flagged.
- No quantity takeoff. The original schedule and Word pagination must be reviewed before procurement. Word generation preserves the template's styling; page count depends on content. Server-side visual QA is not automatic.
- Upload and result data are held in the user's Streamlit session, not a shared project cache or project database. No project history is written by the application. Provider/host retention policies are separate; this is not a guarantee of immediate deletion from host memory. API requests set `store: false`.

## Free hosting pilot: Streamlit Community Cloud

1. Put **the contents of this folder** in its own private GitHub repository. Include `templates/master.docx`, `templates/layout.json`, and `materials/master-instructions.txt`. Exclude `.venv`, `.verification`, uploads, and actual secrets.
2. In Streamlit Community Cloud, create an app from that repository with entry point `app.py`; choose Python 3.12 or newer.
3. Set the app's visibility to **private** and invite your teammates as viewers. A private repository alone is not your app-access policy: verify a signed-out browser is denied access.
4. Manual mode requires no API secrets. Add the API settings in the host's secrets editor only if you want the optional paid button enabled.
5. Test a real schedule, Word download, and two separate user sessions before sharing broadly. Hosting resource limits still apply.

Official instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app

## Railway or another Docker host

The included Dockerfile runs the whole app and respects `PORT`. Connect the repository as one service; no separate frontend is required. Railway's free allowance is limited and does not pay OpenAI charges.

Before making the service public, enable `AUTH_REQUIRED=true`, configure an OIDC provider using the example `[auth]` settings, and set `ALLOWED_EMAILS` to the comma-separated team email addresses. This implementation requires a verified email claim (Google is the documented example). Missing allowlist or unapproved/unverified users fail closed when authentication is enabled. Configure the correct `/oauth2callback` URL at both ends. Keep the API key server-side. OIDC requires setup and live verification; it is not provisioned automatically.

Use `.streamlit/secrets.toml` through the host's secret-file support for the `[auth]` table; do not bake it into the container. Keep the app private while testing authentication. On Community Cloud, private viewer access can handle sign-in instead, with `AUTH_REQUIRED=false`.

Authentication docs: https://docs.streamlit.io/develop/api-reference/user/st.login

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`templates/prepare_template.py` is an optional maintainer utility for rebuilding the sanitized template from the two original reference files. Normal operation uses the packaged template and does not need those originals.

## Verification status

22 automated checks passed on October 2, 2026. Browser text-file import, Word generation, and actual DOCX download were verified. The downloaded file opens and renders in Word. Live AI extraction, hosted team sign-in, and real-project accuracy still need configured services and representative source documents. See `docs/progress.md`.
