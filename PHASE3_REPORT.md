# Phase 3 report: AI and documents

**Date:** 2026-11-13. **Status:** built, tested offline and checked in the browser on a scratch copy with fake data.

- No AI website was contacted. Ollama isn't installed, so the Ollama provider was built and tested against a mocked local API.
- No job site was contacted.
- Your real database wasn't used for any check. Two dry runs used temporary copies, which were deleted.
- No real resume content is in any fixture or commit.

Before Phase 3, the Phase 2 fixes you asked for were committed separately (`9025417`): entry-level default keywords, "Version control" no longer counted as Git, skills in ads without a requirements section counted as required, and thin evidence scored as low confidence. Before/after scores are in `PHASE2_REPORT.md` section 8.

## 1. What was built

| Area | What you get |
|---|---|
| **AI modes** | **Settings → AI:** Copy-Paste (default), Ollama, or Off. On Job Detail you can switch any single action between Copy-Paste and Ollama. There is no paid provider. Ollama is only ever called at `127.0.0.1:11434`. Default model `qwen2.5:3b`; "Check Ollama" says whether it's running and whether the model is installed (with the `ollama pull …` command if not). |
| **Prompts** | Every prompt contains: the task's instructions, your Experience Bank items **with their IDs**, the job description, your profile basics (no email or phone), the four rules from the brief, and an example of the exact JSON to return. Each task's instructions are a template you can edit in **Settings → Prompt templates** (stored as files under `backend/ai/templates/`, with a reset button). Rules and format are re-added if an edit removes them. |
| **Checking replies** | Broken JSON is repaired where possible (smart quotes, trailing commas, comments, text around the JSON), and the repairs are listed. A wrong field is named exactly (e.g. `sections.0.items.0.text: Field required`). You can edit the reply and check again, or **Generate fix-up prompt** to ask the chat to correct itself. |
| **Fabrication guard** | Flags in red:<br>• a bullet with no bank ID, or an ID that isn't in your bank;<br>• any unknown evidence / used / suggested ID;<br>• any skill (in lists **or** in rewritten text) that isn't in your bank or profile;<br>• a requirement marked "met" with no evidence;<br>• for resume parsing, anything that isn't in the resume text. |
| **Review screen** | Tailored resume: your original bank item on the left, the rewritten text on the right.<br>• Accept, edit or reject each item.<br>• Items with a missing or unknown ID start rejected and **can't be saved** until they point at a real bank item.<br>• Unclaimed skills are struck out of the skills list.<br>• Bank items the AI left out (education, certifications, publications…) can be added as written.<br>• Only accepted content is saved. |
| **Tasks** | Deep analysis (✅⚠️❌ per requirement, with the bank IDs that prove it), Tailor resume, Cover letter, Interview prep, and **Parse resume** (a "Parse with AI" button on the resume review screen, feeding the same review). |
| **Cover letter template** | Works with AI off. Built from the role and company, your education, your top 3 matched skills, and 1–2 bank items you pick (quoted word for word). Fully editable. |
| **Documents** | Every save is a numbered version per job (Resume v1, v2…), marked Copy-Paste / Ollama / Template.<br>• Preview, or download an **ATS-friendly PDF**: one column, standard headings, selectable text, no tables or icons. PDFs are saved under `data\documents\<job_id>\`.<br>• Certifications and publications have their own sections.<br>• The newest deep analysis is shown on Job Detail and also saved as a "deep" score next to the quick score. |
| **Applications** | The Application card records **which resume and cover letter version you sent**. That version shows "sent with application" and can't be deleted while linked. |
| **Warnings** | For summary-only or low-confidence jobs, Tailor resume and Cover letter warn you first (Continue anyway / Cancel). |
| **Automation** | `ollama_deep_analysis` (**off** by default): after a fetch, it analyses new jobs at or above the high-match threshold through local Ollama, at most 3 per run. It skips summary-only and low-confidence jobs and never uses Copy-Paste. If Ollama isn't running, the run log says so. |

## 2. How to use the Copy-Paste flow, step by step

1. **Once:** check **Settings → AI** shows *Copy-Paste* (the default). Make sure your Experience Bank is filled in (**Resume & Bank**). Every bullet the AI writes must point at one of those items.
2. Open a job (**Jobs → click a title**). If it says *rough (summary only)*, use **Open & paste full JD** first.
3. In **AI tools**, click **Tailor resume**. (Deep analysis, Cover letter and Interview prep work the same way.)
4. **Step 1, copy the prompt:** click **Copy prompt**.
5. Open a free web chat in your browser (ChatGPT, Claude or Gemini). Paste the prompt and send it.
6. When it answers, copy its **whole reply** (the copy button under the answer is easiest).
7. **Step 2, paste the reply** into the box in JobFinder and click **Check reply**.
   - If a field is wrong, the exact field is listed. Either fix it in the box and check again, or click **Generate fix-up prompt**, paste that into the same chat, and paste its new reply.
8. **Review:**
   - Anything red is possibly invented: an ID not in your bank, a missing ID, or a skill you don't have. Edit or reject it.
   - Check the summary and the skills list (crossed-out skills are left out).
   - Tick any left-out bank items you want included as written (e.g. your degree).
9. Click **Save as new resume version**. In the confirmation, click **Download PDF** (or **Preview**).
10. When you apply, open the **Application** card and choose that version under **Resume sent** (and **Cover letter sent**).

**Ollama instead:** install Ollama, run `ollama pull qwen2.5:3b`, then click **Check Ollama** in Settings → AI. Choose Ollama as the mode, or per action. The reply arrives by itself (a timer shows progress) and goes through the same checks and review. If Ollama fails, the dialog offers **Try Ollama again** or **Use Copy-Paste instead** with the same prompt.

**AI off:** use **Cover letter from template (no AI)** on Job Detail.

## 3. Test results

| Suite | Result |
|---|---|
| Backend `pytest` | **351 passed**. An autouse guard blocks every real HTTP request and the real JobSpy call; Ollama is a mocked local API. |
| Frontend `vitest` | **27 passed** |
| Type-check and production build | OK |

New Phase 3 tests:
- **Tolerant parser (19 tests):** every prompt example matches its schema; code block with chatter around it; broken JSON repaired; field paths for schema errors; braces inside strings; Python literals and comments (URLs kept); unusable replies explained.
- **Copy-Paste flow through the API (20 tests), with saved fake replies:**
  - The prompt contents (bank IDs, JD, rules, schema, **no email or phone**).
  - Valid, broken-JSON, schema-error and **fabricated** replies. B99, a missing ID, Docker/Kubernetes/AWS and an omitted B42 are each flagged at the right path.
  - Fix-up prompt, and editing the JSON by hand.
  - Saving versions, including certifications and publications; unknown IDs refused.
  - The template cover letter with AI off; links to the application; deleting a linked version blocked.
  - `parse_resume` flags an invented "Senior Architect at Google".
  - Templates edited and reset, with rules re-added; tests never write into the repo.
- **Ollama, mocked (13 tests):** status messages (not running / model missing / ready); not running, model missing and timeout errors; a tailored resume via Ollama going through the same guard; retry after failure; a pasted reply counting as Copy-Paste; the automation analysing once and skipping low-confidence jobs, reporting "not running", and skipping when AI is off.
- **PDF, real Playwright + Chromium, offline (3 tests):** the PDF is read back with pdfplumber, proving selectable text and standard headings (SUMMARY, SKILLS, EXPERIENCE, EDUCATION, CERTIFICATIONS, PUBLICATIONS).
- **Frontend:** review helpers (flags per item, accept/reject rows, the save body, unused bank items, AI parse to draft with duplicate marking).

**Browser check** (scratch copy, fake bank "Ali Bin Contoh", fake jobs):
- Tailor resume: copied the prompt, then pasted the fabricated reply. Summary/skills/B99/missing ID/Docker showed in red, and the B99 item couldn't be accepted. I edited a bullet, added the degree, certification and publication as written, and saved. Resume v1's PDF downloaded with correct text.
- Recorded Resume v1 as "sent".
- Template cover letter saved.
- Deep analysis with Ollama (really not installed) showed "Ollama is not running…". Use Copy-Paste instead → paste → B42 crossed out → saved.
- The summary-only job showed the warning before tailoring.
- Settings → AI and Check Ollama work.

The check found three problems, now fixed:
- A pasted reply on a task that started on Ollama was labelled "Ollama".
- "2023 - 2023" was printed when the start and end dates matched.
- Checking Ollama was slow because of an IPv6 attempt on Windows.

## 4. Acceptance criteria (brief §8, Phase 3)

- [x] AI provider layer: Copy-Paste, Ollama, Off (global, overridable per action)
- [x] Prompt templates (editable files), tolerant parser, schema validation, fabrication guard, review screen
- [x] Tasks: parse_resume, deep_analysis, tailor_resume, cover_letter (+ template mode), interview_prep
- [x] Document versioning, ATS-friendly PDF export, linking versions to applications
- [x] `ollama_deep_analysis` automation (default off)
- [x] Publications and certifications usable in tailored resumes (own sections in the PDF; offered as "include as written")
- [x] Summary-only and low-confidence jobs warn before tailoring
- [x] "Ollama not running / model not installed" shown clearly in the UI
- [x] **Done-when, Copy-Paste:** for a saved job I can copy a tailor-resume prompt, paste a reply back, see fabricated items flagged, accept the changes and download a PDF. Verified in the browser.
- [~] **Done-when, Ollama:** the same flow runs automatically with Ollama. Verified against a **mocked** Ollama API, in tests and through the UI's failure path. **Not yet run against a real model**, because Ollama isn't installed.

## 5. Decisions for you to review

All are in `DECISIONS.md` #111–129. The ones worth a look:

1. **#116 Default model `qwen2.5:3b`.** It's small and good at JSON. `llama3.2:3b` also fits your GPU; change it in Settings → AI.
2. **#117 No email or phone in prompts.** The AI doesn't need them; the PDF adds them from your profile.
3. **#120 How invented skills are detected.** Skills are spotted in free text through the **skill dictionary**. A made-up number or achievement that names no skill (e.g. "improved speed by 40%") isn't detected automatically. The side-by-side review is your check for those.
4. **#121 Items with an unknown or missing bank ID can't be saved**, even if you accept them; give them a real ID or reject them. Items that only mention an unclaimed skill are your call.
5. **#126 The automation saves deep analyses without review.** They're analysis, not resume content, and their flags are kept. It's off until you turn it on.

## 6. Known limitations

- **Ollama hasn't been tried with a real model.** Small 3B models may produce weaker rewrites and miss JSON fields more often than web chats. The parser, fix-up prompt and review screen exist for that. A long bank plus a long JD may exceed the 8k context; if so, a larger `num_ctx` is a one-line change.
- **Invented numbers or achievements that name no known skill** aren't flagged automatically (see decision 3 above).
- The AI chooses the section names (e.g. it may put a project under "Experience"). The review screen can't move an item between sections, but you can reject it and add the bank item as written.
- One resume layout and one cover-letter layout. DOCX export is out of scope (brief §6.7).
- Copy-Paste depends on you copying the whole reply. The parser tolerates extra text around the JSON, but not a reply cut off half-way; you get "No JSON object found".
- The cover-letter template is plain on purpose. It quotes your first bullet as written, so a bullet that doesn't start with a verb reads a little stiffly.
- Desktop notifications still aren't built (optional in the brief).
