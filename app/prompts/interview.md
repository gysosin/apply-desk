# Interview prep for one application

Candidate: see CLAUDE.md. Application: {company} - "{role}".
Inputs: the posting `documents/applications/{slug}/job_posting.md`, the CV sent `{cv_file}`, the cover letter `{cover_file}`, and `.claude/skills/job-application-assistant/07-interview-prep.md` (method and existing STAR material), plus `01-candidate-profile.md` for facts.

Write `documents/applications/{slug}/interview_prep.md`:
1. The company and role in 3 lines (verify company facts with WebSearch; if unverifiable, leave them out).
2. The 8 most likely questions for this role (technical and behavioural), each with a short answer outline grounded only in real profile facts, plus the STAR story to use.
3. The 3 gaps an interviewer will probe, with honest bridging answers.
4. Salary and notice answers (current pay, expected range and notice period from the profile in CLAUDE.md).
5. 5 sharp questions to ask them.

Never name the side-work employer or its clients (see CLAUDE.local.md). No invented facts. Return the structured result: {{"status": "READY", "path": "documents/applications/{slug}/interview_prep.md"}}.
