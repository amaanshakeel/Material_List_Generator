# Implementation record

Plan: docs/design.md. User authorized building in a new folder on 2026-10-01.

Ruling: no Git repository exists in the workspace; use the expressly requested new standalone directory, without modifying the existing toolkit or creating a worktree.
Ruling: use standard-library WordprocessingML to preserve the actual template styles and geometry without requiring Microsoft Word or a document library on the hosting server. Render samples with installed Word for local visual QA.
Pre-flight: manual parser and API return the same validated model; generator consumes only that model. Manual input must never invoke the API.

Tasks: input schema/parser and tests; sanitized template and generator; optional API; Streamlit UI and deployment docs; end-to-end verification and independent review.


## Verification ? 2026-10-02

- Project relocated by the user to `D:/VS Code/OCR Automation/material-list-generator`; continued in that copy.
- Manual importer, shared validation, sanitized template, Word generator, optional API adapter, UI, isolated environment, launcher, Dockerfile, and hosting instructions are implemented.
- Independent reviewer found two input edge cases (repeat without roll width and alternative dimensions in notes). Added failing regressions and fixed both.
- Word opening uncovered stale namespace compatibility declarations after template sanitization. Added a failing regression, corrected serialization, and verified the actual generated file opens in Word.
- 22 unit/Streamlit tests pass. UI tests use a 15-second allowance to accommodate cold imports; a three-second harness timeout caused a transient failure after relocation.
- Browser: imported the example text file, generated five materials, and downloaded a 19,044-byte DOCX. Chrome reported download completed; ZIP integrity and October 02, 2026 generation date checked. The browser-downloaded file opened and exported successfully using Word.
- Download cancellation was isolated to the automation browser context's download policy, not the app. Enabling downloads for that context resolved it without a product-code change.
- Sample pages were visually reviewed on 2026-10-01. Completed app view inspected on 2026-10-02; browser reported no JavaScript errors.
- API success, refusal, incomplete response, HTTP errors, missing key, image validation, and PDF page selection are covered using simulated responses. No live paid API call was made.

### Implementation decisions and remaining external checks

- Keep the app independent and generate Word on the server without Microsoft Office; local Word is used only for sample verification.
- No automated manufacturer web research in this version; the app discloses this and does not invent outside-source facts. Manual extraction can include evidence collected in ChatGPT.
- Hosting and OIDC configuration are documented but not deployed or live-tested. Start with private Community Cloud viewer access.
- A real project schedule paired with an approved result is still needed to evaluate factual extraction accuracy. The fictional sample proves mechanics and layout, not real-project correctness.
- API credentials remain user-supplied; no secrets were added to source.

- Independent Playwright/Chrome check also passed: pasted sample output, generated DOCX, saved actual download, validated its contents, switched to API mode and confirmed the extract button is disabled without a key. No browser JavaScript errors. Verification-only Playwright is installed in the local environment, not a production requirement.
