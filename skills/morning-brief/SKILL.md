# Morning Brief Skill

## Description
Generate a prioritized morning briefing by scanning Gmail, Google Calendar, and GitHub notifications.

## Instructions
1. Check Gmail for unread/urgent emails from the last 24 hours
2. Check Google Calendar for today's events and tomorrow's first event
3. Check GitHub notifications for all breverdbidder repos
4. Generate a prioritized summary with:
   - Top 3 priorities for today
   - Urgent emails requiring response
   - Today's schedule
   - GitHub items needing attention
5. Save as an HTML file on the desktop called morning-brief.html
6. Send a Slack/text summary of the top 3 priorities

## Output Format
HTML dashboard with sections:
- 🎯 Top Priorities (numbered 1-3)
- 📧 Email Actions (sender, subject, urgency)
- 📅 Today's Schedule (time, event, location)
- 🔔 GitHub Alerts (repo, type, title)
- 📊 Quick Stats (unread count, meetings count, PRs open)

## Trigger
Run this skill when I say: "morning brief", "brief me", "what's on today", or "daily update"
