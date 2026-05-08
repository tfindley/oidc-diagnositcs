Commit all staged/unstaged changes on the current branch, push to remote, open a pull request against `main`, and merge it. Follow these steps in order:

## 1. Understand the current state

Run these in parallel:
- `git status` — show working tree state
- `git diff HEAD` — show all changes (staged and unstaged)
- `git log main..HEAD --oneline` — show commits ahead of main
- `git branch --show-current` — confirm the current branch

If the current branch IS `main`, stop and tell the user to create a feature branch first. Do not commit directly to main.

## 2. Stage files

Stage changed files by name — do NOT use `git add -A` or `git add .`. Only stage files that are part of the current work. If there are untracked files that look unrelated (e.g. `.env`, temp files, credentials), skip them and flag them to the user.

If there is nothing to commit (clean working tree and no commits ahead of main), tell the user and stop.

## 3. Draft the commit message

Write a conventional commit message that matches the project's style:
- Format: `<type>: <short summary>`
- Types: `feat` (new feature), `fix` (bug fix), `docs` (documentation only), `chore` (tooling/config), `refactor` (no behaviour change), `security` (security hardening)
- Keep the subject line under 72 characters
- Focus on *why*, not *what*
- End with: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

If there are multiple logical changes across files, use the type that describes the dominant change.

## 4. Commit

Create the commit using a HEREDOC to preserve formatting:

```bash
git commit -m "$(cat <<'EOF'
<type>: <summary>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

If the commit is rejected by a pre-commit hook, fix the underlying issue and retry — do NOT use `--no-verify`.

## 5. Push

Push the current branch to origin:

```bash
git push -u origin HEAD
```

## 6. Create a pull request

Use `gh pr create` targeting `main`. Write a concise PR body using a HEREDOC:

```bash
gh pr create --base main --title "<same as commit subject>" --body "$(cat <<'EOF'
## Summary
- <bullet points covering what changed and why>

## Test plan
- [ ] <key things to verify manually>

🤖 Generated with [Claude Code](https://claude.ai/claude-code)
EOF
)"
```

Print the PR URL for the user.

## 7. Merge

Merge the PR with the squash strategy and delete the branch:

```bash
gh pr merge --squash --delete-branch
```

If the merge fails (e.g. merge conflicts or failing checks), report the error clearly and stop — do not force.

## 8. Confirm

Run `git log main --oneline -5` after switching back to main (`git checkout main && git pull`) to confirm the merge landed, and print the final commit SHA to the user.

## 9. Tag and release (if this is a version branch)

Check whether the branch name (captured in step 1) matches the semver pattern `v[0-9]+.[0-9]+.[0-9]+` (e.g. `v0.2.0`).

**If it matches:**
1. Create an annotated tag on main pointing at the merge commit:
   ```bash
   git tag -a <branch-name> -m "Release <branch-name>"
   ```
2. Push the tag to origin:
   ```bash
   git push origin <branch-name>
   ```
3. Tell the user the tag was pushed and that the GitHub Actions release workflow has been triggered. Show them the Actions URL: `https://github.com/<owner>/<repo>/actions`

**If it does not match:**
Tell the user no tag was pushed (this branch isn't a release branch). If they want to trigger a release manually they should run:
```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z
```
