# Project instructions

## Safety contract
- Rules assign system priority and routing; the LLM provides explanations only.
- Preserve original system decisions and append-only human review history.
- Do not invent clinical content or add diagnosis or treatment suggestions.
- Label simulated data and recorded explanations clearly.

## GitHub workflow
The user has authorized pushing these and future changes to GitHub.
After completing and verifying requested changes, commit and push them to the configured GitHub remote on the current branch, unless the user gives a different instruction.
Check the diff and Git state first. Exclude secrets, local databases, generated output, and unrelated changes. Do not force-push or discard existing work. Report the pushed commit and any verification limitations.
