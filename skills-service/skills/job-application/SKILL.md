---
name: job-application
description: >-
  Tailor resumes, CVs, cover letters, and job-application answers to a
  specific job posting using the user's profile database. Use when the user
  asks for a resume, cover letter, motivation letter, application help,
  interview prep, or "apply to this job". Based on the user's get_profile data.
---

# Job Application Skill

You are helping the user apply for a job. Follow this workflow exactly.

## Inputs you need
1. **The user's profile**: call the `get_profile` tool. It returns the full
   database (basics, summary, education, experience, projects, skills,
   certifications, languages, job_preferences, application_extras).
   NEVER invent facts about the user — every claim must trace to the profile.
   If a needed fact is missing from the profile, say what is missing and ask.
2. **The target job**: a job posting (URL or pasted text). If the user gave a
   URL, use `browse_web` to read the posting. Extract: role title, company,
   key requirements, and responsibilities.

## Workflow

### Cover letter
- 250-350 words, 3-5 paragraphs, no clichés ("I am writing to apply...").
- Paragraph 1: the role + one hook connecting the user's strongest relevant
  experience to the company's need.
- Paragraph 2-3: two concrete achievements from `experience`/`projects`
  rewritten for THIS job's requirements. Use numbers from the profile.
- Final paragraph: close confidently; reference `why_hire_me` themes.
- Mirror 3-5 exact keywords from the posting naturally.

### Resume / CV bullet tailoring
- Rewrite the 3-5 most relevant bullets per role for the target posting.
- Format: strong verb + what you did + measurable outcome.
- Keep truthful: rephrase and re-order, never fabricate.
- ATS rules: no tables/columns/graphics; standard section headings
  (Experience, Education, Skills); include exact keywords from the posting
  that the user genuinely has.

### Application question answers
- Short answers 100-200 words unless told otherwise.
- Structure: direct answer first, one proof point from the profile, one line
  on why it fits THIS company.
- Use `career_goals` and `strengths` for "why us / tell me about yourself".

### Gap or mismatch handling
- If the user lacks a listed requirement: do not hide it, do not lie.
  Reframe adjacent experience from the profile as transferable.

## Output rules
- Ask the user for missing critical info (e.g. which company, which role)
  only when it blocks the task; otherwise proceed with profile defaults
  from `job_preferences`.
- Always output ready-to-paste text the user can submit directly.
- If the profile still contains SAMPLE placeholder values, warn the user
  clearly before finalizing and list which fields are placeholders.
