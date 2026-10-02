# Material List tool — simplified proposed design

Status: implementation authorized on October 1, 2026; first local version verified October 2, 2026. See README.md and docs/progress.md for implemented behavior and remaining external checks. Historical design follows. This is the current first-release proposal following the user's clarification. It supersedes the broader workflow and unresolved-input lists in the earlier design and implementation drafts. The full master instructions remain the content rules.

## What you will do

1. Open the separate **Material List Generator** app, independently of the PDF Toolkit.
2. Choose **Paste ChatGPT Output** (default) or **Use API** (optional).
3. Supply the selected mode's input and generate the material list as described below.
4. Download an editable Word document in the supplied format.

The templates are configured once. No repeated template uploads, project setup wizard, technical settings, or compulsory draft approval. A short status message shows progress. Relevant uncertainty appears in a concise notice; essential unreadable information may require a clearer image. Clipboard image input needs browser testing, with file upload always available.

### Paste ChatGPT Output — no API key required

- Provide a **Copy ChatGPT Prompt** control containing the saved extraction rules and a consistent output format. The user supplies that prompt and their schedule to ChatGPT themselves.
- Accept pasted ChatGPT output or a UTF-8 `.txt` file containing it. Use plain, labeled material blocks with a documented schema so the user does not need to write code. The prompt requests those blocks and source references, manufacturer URLs, and the origin of any externally supplied sizes.
- Click **Generate Word Document** to parse, validate, and format the supplied data without an AI call. Both modes feed the same internal material model and Word generator.
- Accept the documented format and explicitly supported variations; arbitrary prose cannot be promised to parse reliably without AI. Preserve the original input and identify malformed or ambiguous fields for correction. Do not silently discard entries or call a paid API to repair them.
- This mode cannot independently establish that the pasted extraction matches an unseen drawing. Distinguish imported source claims from checks actually performed by this app. Missing evidence or unavailable manufacturer verification is disclosed; never fabricate it or claim full source review.
- Manual mode incurs no API charges from this app. The user's own ChatGPT access and limits remain separate.

### Use API — optional automatic extraction

- Upload a PNG/JPEG schedule image or PDF, with a page selector for multipage PDFs; provide clipboard image input where supported.
- Click **Extract with API** to send the selected source and saved instructions to the configured AI service. Show that external processing and usage charges apply beside this button; configuring a key alone must not trigger processing.
- Validate the returned material fields, then generate and offer the Word document in the same template. Do not require a routine extra approval step.
- If no key is configured, show **API not configured** and keep manual generation fully usable. Failed requests preserve the upload; retries are explicit and bounded, with no hidden fallback from manual mode.
- The app owner configures the API key securely on the server once; teammates do not need to provide keys or share a ChatGPT login.

## What the tool will do

- In API mode, read both the visible page layout and its text, using OCR where needed. Associate each material with its own row, tag, and notes. In manual mode, import the user's ChatGPT extraction with its supplied evidence.
- Extract flooring and the related in-scope base, grout, tile, trim, and other systems defined in the master instructions. Exclude unrelated finishes.
- Preserve supported manufacturer, product, color, size, location, and installation information. Never infer rooms or facts from unseen sheets. Omit unsupported fields and flag material ambiguities instead of guessing.
- Apply the master rules, including no thickness anywhere, the specified manufacturer-size highlighting, broadloom repeat checks, and the correct treatment of base, grout, and transitions.
- Where the rules require manufacturer verification, use official sources for the matching product. An unavailable source must never produce an invented link or specification.
- Generate Word from the supplied layout, with only applicable material groups. It is a material qualification list, not a measured quantity takeoff.

The existing OCR/highlighting automation is not a required step for the user. API mode reads the supplied original page directly; manual mode reads the supplied extraction. The existing tools remain available separately.

## How the two supplied documents will be used

Both actual DOCX files were inspected through their paragraph, run, style, relationship, and section structures. Visual rendering still needs verification during implementation.

| Reference | Role |
|---|---|
| Christ_Hospital_Postpartum_Renovation_Level_8_South_Material_List.docx | Master page layout, cover, headings, field styling, and disclaimer. |
| HEB_Royse_City_837_Material_List.docx | Refined Base, Grout, and Trim entries with separate supporting fields. Its filename need not have the `(1)` suffix mentioned in the original instructions. |

Confirmed common formatting: Letter portrait, 0.65-inch top/bottom margins, 0.70-inch side margins, Calibri 11 body text, centered bold material-group headings, bold field labels, blue underlined hyperlinks, and yellow highlights where prescribed. Both documents use paragraphs rather than tables. Some fields are separated by line breaks within a paragraph, which the template adapter must preserve intentionally.

**Material Verification Links appears before the material groups in the supplied documents.** Preserve that placement rather than inventing a second bibliography at the end. Preserve appropriate page breaks and keep headings with entries; page count grows with the new material list.

Old project names, dates, areas, scales, material entries, links, and project screenshots are example data and must be removed or replaced. Christ contains two embedded images; HEB contains none. Do not carry the old images into a new project. Cover information absent from the input remains blank, except the generation date. Drawing-set images and the separate-specification sentence follow the conditions in the master instructions.

Current written requirements take priority over conflicting example content, including old `Link: N/A` placeholders and the older wording “Specification provided as a separate PDF.” The conditional required sentence is “Specification provided as a separate file.” Exact template formatting does not mean copying old project facts or mistakes.

## Backend approach

Use two input adapters: a deterministic parser for manual ChatGPT output and an optional image-capable AI adapter for automatic extraction. Both feed shared validation, content rules, and template-based Word generation on the app server (or the user's computer when run locally). OCR alone is a weaker option for reliably associating dense or irregular schedule rows. The developer handles this integration; technical choices do not become routine user controls.

An online AI service requires a one-time API configuration and may incur usage charges. Approval for external processing and secure configuration must be settled before transmitting any project page. No project content has been sent to such a service during planning. Do not promise that a normal chat subscription covers API usage.

Build an independent project with its own entry point, dependencies, templates, configuration, and deployment files. Do not add it to the PDF Toolkit sidebar or require the other tools to run. Keep extraction, content rules, and Word rendering in separate modules. Store source evidence internally so every generated fact can be checked against its page or verified official source. No project database, resume console, or batch document-management system is required for this first release.

## Team hosting and cost constraint

The user may share this app with their team and prefers no additional purchases. Keep the source in its own private GitHub repository and deploy the Python app to a hosting service. GitHub stores the source; the hosting service runs the application. A separate frontend/backend deployment is not required for Streamlit.

Use Streamlit Community Cloud as the proposed free pilot host, with private viewer access. Railway is another deployment option, but its free resource allowance is limited and does not guarantee sustained team usage at no cost. Hosting and AI processing are separate costs: free hosting does not include paid OpenAI API calls. The user selected manual ChatGPT import plus an optional API button. Manual generation is the default and has no API dependency; the optional API provider, credentials, and usage budget still need configuration before use. Do not promise an unlimited, zero-cost automatic team service or silently enable paid fallback.

Before sharing, test user/session isolation, restrict access to approved teammates, keep credentials server-side, and define temporary upload cleanup. Do not distribute a shared personal ChatGPT login. The existing subscription sign-in possibility requires separate eligibility validation for a hosted team app.

## Build and acceptance sequence

1. Create the reusable Word template from the supplied documents, clearing all example project data and mapping the correct paragraph blocks.
2. Define the shared material schema, copyable ChatGPT prompt, manual text parser, and actionable input validation. Complete manual generation first.
3. Add optional single-page PDF/image reading and evidence-backed API extraction, isolated from manual mode.
4. Apply the full master instructions and official-source checks; generate the DOCX with deterministic formatting, reporting evidence limitations honestly.
5. Add the two input modes, Generate, progress, and download controls to the standalone app, with team access controls before deployment.
6. Validate with real ChatGPT output and a schedule image/PDF paired with the user's expected material list. Check adjacent-row associations, missing facts, excluded finishes, thickness removal, links, yellow size lines, and Base/Grout/Trim formatting. Verify manual mode makes no AI calls, works without a key, rejects malformed input helpfully, and yields the same document as API mode for equivalent material data.
7. Open/render the generated Word document and inspect every page for layout, wrapping, page breaks, and stale template content. Test both browser flows, downloads, and concurrent-user isolation; confirm existing tools still work.

A representative schedule page/image is still needed for acceptance testing. It is not needed to understand or agree on this proposed flow. Implementation begins after the user agrees to proceed, as requested in the planning-only instruction.

Full content rules: [master instructions](master-instructions.txt).
