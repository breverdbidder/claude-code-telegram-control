# Repo Status Skill

## Description
Check health of all BidDeed.AI GitHub repositories and report status.

## Instructions
1. Query these 5 repos via GitHub API:
   - breverdbidder/claude-code-telegram-control
   - breverdbidder/cli-anything-biddeed
   - breverdbidder/zonewise-scraper-v4
   - breverdbidder/swimsquad-ai
   - breverdbidder/biddeed-ai
2. For each repo check:
   - Last commit (date, author, message)
   - Open issues count
   - Latest workflow run status (pass/fail)
   - Days since last commit (flag if >7 days stale)
3. Generate a summary table

## Output Format
Table with columns: Repo | Last Commit | Status | Issues | Staleness
Flag any repo with >7 days no commits as ⚠️ STALE
Flag any failed workflow as ❌ FAILING

## Trigger
Run when I say: "repo status", "check repos", "github health", or "repo check"

## Cloud Bridge
This skill can also call the Hetzner executor for deeper analysis:
```
curl -X POST http://87.99.129.125:8318/task \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: $AGENT_SECRET" \
  -d '{"task": "Full repo health check for all breverdbidder repos"}'
```
