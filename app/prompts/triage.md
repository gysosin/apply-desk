# Pick postings worth reading

Below are job search results (key | title | company | location | countries). The candidate is described in CLAUDE.md (target roles, location, remote preference and deal-breakers).

Keep a posting if the role could fit (AI/ML/LLM engineer, full-stack, backend, platform/DevOps, forward-deployed engineer, solutions/applied AI engineer) AND it could plausibly meet the candidate's location and remote rules.

Drop:
- product/project managers, QA/SDET/test, sales, designers, support, data-center, recruiters, interns/early-career/PhD, and management-only roles
- listings restricted to other countries (country lists without "in", or a single foreign city with no remote signal)
- non-English postings
- job aggregators, staffing agencies and reposters that hide the real employer (Jobgether, Weekday, Turing, Crossover, Toptal, Uplers and similar, or "hiring for our client")
- large IT-services body shops (Infosys, TCS, Accenture, Wipro, Cognizant, HCL, Capgemini, LTIMindtree, Tech Mahindra)

When unsure, keep it; a later step reads the full posting.

{listing}

Return the structured result: {{"keep": ["<key>", ...]}}.
