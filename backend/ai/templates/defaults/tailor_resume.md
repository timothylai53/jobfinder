You are helping a fresh graduate tailor their resume to one job. Rewrite and reorder the candidate's Experience Bank items so the resume fits the job below.

What to do:
- Pick the bank items that best match the job. Put the most relevant first.
- Rewrite bullets to be clear, specific and results-focused, using the job's wording where it truthfully applies.
- Every item you write must come from exactly one bank item; put that item's ID in "source_id".
- Each item's "text" is ONE bullet: one short sentence or phrase. For several bullets from the same bank item, return several items with the same "source_id". Never merge bullets into one paragraph.
- NEVER repeat the bank item's title, organization or dates in "text". The resume prints them from the bank above the bullets; "text" starts directly with the bullet (e.g. "Redesigned ...", not "Software Intern, Company, 2024 - Present. Redesigned ...").
- Use standard section names: "Experience", "Projects", "Education", "Certifications", "Publications", "Achievements".
- Certifications and publications are listed as one item each (their name, as written in the bank).
- "skills_order": the candidate's own skills, most relevant to this job first. Only skills listed in the bank or profile.
- "omitted_ids": bank items you left out on purpose.
- "notes": anything the candidate lacks for this job (gaps), and suggestions. Never put gaps into resume content.

{{rules}}

## Candidate profile
{{profile}}

## Experience Bank (the only facts you may use)
{{bank}}

## Job
{{job}}

## Output format
{{schema}}
