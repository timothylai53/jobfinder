# Product

<!-- impeccable:product-schema 1 -->

> From PROJECT_BRIEF.md, the code and the user's visual-identity brief; confirmed by the user on 22 Nov 2026.

## Platform

web

## Users

One person: a software-engineering fresh graduate in Malaysia, using the app on their own Windows laptop most days of a job search. They read job ads, decide which are worth applying to, tailor a resume for each and track where every application stands.

Second audience: recruiters and interviewers, who judge the project from the README screenshots and demo GIF. It must read clearly and look polished at a glance, while staying calm and simple, never flashy.

## Product Purpose

A local, private job-search tool. It fetches ads politely, scores each against the user's own Experience Bank with a score that explains every point, keeps a tracker, and helps tailor resumes and cover letters with AI without letting the AI invent anything. Success: the user applies to better-fitting jobs with honest resumes and never loses track of an application.

## Positioning

Every number is explainable and every AI-written line is tied to a real item in the user's bank, with anything that isn't flagged before it can be saved. It runs entirely on the user's laptop: no accounts, no paid APIs, no logging in to job sites.

## Operating Context

Daily, short sessions at a laptop: open Today, see what needs doing, open a job, read why it fits, tailor and download a resume, mark as applied. AI work goes through a free web chat (copy and paste) or a local model. Resume PDFs and Word files are sent to employers and read by ATS software.

## Capabilities and Constraints

Jobs, scoring with breakdown, filters, tracker (Kanban and table), Experience Bank, AI tasks (deep analysis, tailor resume, cover letter, interview prep, resume parsing), documents (PDF, DOCX), automations, skill gaps, settings. Constraints: free and offline (except fetching ads), single user, no feature removal in a restyle, resume documents stay plain and unbranded.

## Brand Commitments

Name: JobFinder. Voice: plain, short, friendly, honest ("You're missing 2 skills", not technical labels). Must feel calm, trustworthy and simple, like a careful personal tool, not a generic SaaS dashboard or an AI-generated template. One accent colour, used only for the primary action and good scores; warm neutrals elsewhere. No gradients, glass, neon, glow, heavy shadows, emoji or illustrations.

## Evidence on Hand

Fake demo data only (scripts/seed_demo.py: "Aisyah Tan", "Contoh" companies). There is no real user content, testimonial or logo, and none may be invented or published.

## Product Principles

1. Accurate before anything else: show the working, never overstate.
2. One obvious next step per screen; everything else can wait behind a tab or "More".
3. Calm over clever: restraint, plain words, nothing that competes for attention.
4. The user's data stays theirs and on their laptop.

## Accessibility & Inclusion

WCAG AA contrast, body text at least 14 px, visible keyboard focus, fully keyboard usable, reduced motion respected.
