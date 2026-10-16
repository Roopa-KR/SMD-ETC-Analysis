# Packaging and continuation rules

1. Work from the most recent delivered ZIP, not an older snapshot. If starting a fresh conversation, re-upload the latest ZIP so its content and tracking history remain available.
2. Create a task entry for every requested project update, including analysis-only work (record `No source changes` where appropriate).
3. Record each exact file added/modified/removed, the reasoning for key decisions, newly observed issues and attempted/implemented solutions.
4. Distinguish tested and verified results from assumptions or previously reported validation.
5. Update the issue register with issue status changes and supporting evidence.
6. Package the updated source, Excel/SQLite data, documentation, templates, scripts, and all accumulated tracking records into a new uniquely versioned ZIP. Validate ZIP integrity and the manifest.
7. Treat source/configuration archives as private. This delivery retains `.env` and `.git` supplied by the user; audit those before sharing. Do not add private tokens/passwords to change logs.
8. Exclude Windows-specific duplicate virtual environments and disposable temporary files; `requirements.txt` remains available for local dependency installation.
9. Respond with the latest ZIP link and concise notes on what was changed, checked, and remains unresolved.
10. Do not imply unattended tracking or edits after a response; records update when a new task is performed in an active chat turn.

## Rebuild locally

From the project directory: `python scripts/package_project.py --output ../truck-etc-app-latest.zip`

The script re-creates a ZIP and updates the manifest inside the archive based on the current local project directory. It does not modify project files in place. Keep the logs current before packaging.
