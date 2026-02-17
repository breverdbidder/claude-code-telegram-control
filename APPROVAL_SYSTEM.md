# AgentRemote Approval System Documentation

## Overview

The approval system enables **human-in-the-loop authorization** for Claude Code tasks. When a task needs your approval (e.g., deleting files, making API calls, deploying to production), it pauses and sends a Telegram notification with Approve/Reject buttons.

## Features

- 📱 **Mobile Approvals** - Approve/reject from Telegram on your phone
- ⏱️ **Timeout Protection** - Auto-rejects after 5 minutes (configurable)
- 🔄 **Parallel Tasks** - Multiple tasks can request approval simultaneously
- 📊 **Approval History** - All decisions are logged
- ✅ **Simple API** - One function call to request approval

## Quick Start

### 1. In Your Claude Code Task

```python
from claude_code_approval import request_approval

# Request approval
result = request_approval(
    task_id="delete_old_files",
    request_text="Delete 500 old log files from /tmp?",
    context={"files": 500, "path": "/tmp", "severity": "medium"},
    timeout=300  # 5 minutes
)

if result == "approved":
    print("✅ User approved - proceeding with deletion")
    # Delete files here
elif result == "rejected":
    print("❌ User rejected - aborting")
elif result == "timeout":
    print("⏱️ No response after 5 minutes - aborting")
```

### 2. In Telegram

You'll receive a message like:

```
🔐 Approval Request

Task: delete_old_files
Request: Delete 500 old log files from /tmp?
Time: 2026-02-17T02:15:30

[✅ Approve]  [❌ Reject]
```

Click a button, and the response is sent back to Claude Code instantly.

## Commands

### `/approvals`
View all pending approval requests. Shows:
- Task ID
- Request description
- Time created
- Approve/Reject buttons

### `/status`
Shows number of pending approvals (along with execution mode)

## Use Cases

### 1. Dangerous Operations
```python
# Before deleting production data
result = request_approval(
    "delete_prod_data",
    f"DELETE {count} records from production database?",
    {"count": count, "table": "users", "severity": "critical"}
)
```

### 2. Expensive API Calls
```python
# Before making paid API call
result = request_approval(
    "openai_api_call",
    f"Make API call to OpenAI? Estimated cost: ${estimated_cost}",
    {"tokens": token_count, "cost": estimated_cost}
)
```

### 3. Deployment Actions
```python
# Before deploying to production
result = request_approval(
    "deploy_production",
    "Deploy current branch to production?",
    {"branch": branch_name, "commit": commit_hash}
)
```

### 4. External Integrations
```python
# Before sending emails
result = request_approval(
    "send_bulk_email",
    f"Send email to {len(recipients)} recipients?",
    {"count": len(recipients), "subject": email_subject}
)
```

## Advanced Usage

### Custom Timeout
```python
# Wait up to 10 minutes for approval
result = request_approval(
    "complex_decision",
    "Approve complex refactoring with 50 file changes?",
    timeout=600  # 10 minutes
)
```

### Contextual Information
```python
# Provide rich context for decision-making
result = request_approval(
    "database_migration",
    "Run database migration? See details below.",
    context={
        "tables_affected": ["users", "orders", "products"],
        "estimated_downtime": "5 minutes",
        "rollback_available": True,
        "backup_created": True
    }
)
```

## Parallel Task Support

The approval system handles multiple concurrent approval requests:

**Task 1:**
```python
# Task 1 requests approval
result1 = request_approval("task1", "Delete files?")
```

**Task 2 (running in parallel):**
```python
# Task 2 requests approval simultaneously
result2 = request_approval("task2", "Deploy to prod?")
```

Both requests appear in Telegram, and you can approve/reject them independently.

## File Locations

- **Pending approvals:** `~/claude_code_tasks/pending_approvals.json`
- **Approval responses:** `~/claude_code_tasks/approval_responses.json`
- **Sent tracking:** `~/claude_code_tasks/sent_approvals.json`

## Implementation Details

### Approval Flow

1. **Task requests approval** → Creates entry in `pending_approvals.json`
2. **Bot detects new approval** → Sends Telegram message with buttons
3. **User clicks button** → Response saved to `approval_responses.json`
4. **Task checks for response** → Polls `approval_responses.json` every 2s
5. **Task receives result** → Proceeds or aborts based on response

### Timeout Behavior

After timeout expires:
- Auto-reject response is written
- Task receives `'timeout'` result
- Approval request is removed from pending

### Error Handling

The approval system is robust:
- Missing files are created automatically
- Malformed JSON is handled gracefully
- Network issues don't block tasks (timeout fallback)
- Concurrent access is safe (file-based locking)

## Testing

### Test the approval system:

```bash
# Run the test script
python3 claude_code_approval.py
```

This creates a test approval request. Open Telegram, run `/approvals`, and click a button to test.

## Integration with Existing Tasks

### Example: BrevardBidderAI Integration

```python
# In BECA scraper task
from claude_code_approval import request_approval

if high_value_property and liens_unclear:
    result = request_approval(
        "manual_lien_review",
        f"Property {address}: Multiple liens detected. Manual review recommended?",
        context={
            "address": address,
            "arv": arv,
            "liens": lien_count,
            "recommended_action": "skip"
        }
    )
    
    if result == "approved":
        # Trigger manual review workflow
        mark_for_manual_review(property_id)
```

## Best Practices

1. **Use descriptive task IDs** - Make them meaningful for logging
2. **Provide clear request text** - User should understand exactly what they're approving
3. **Add context** - Include relevant data to inform the decision
4. **Set appropriate timeouts** - Critical actions: 5 min, routine: 2 min
5. **Handle all responses** - Check for 'approved', 'rejected', AND 'timeout'
6. **Log decisions** - Keep audit trail of all approval decisions

## Security Considerations

- Approval responses are stored in plaintext
- No authentication beyond Telegram bot token
- Suitable for personal use, not multi-tenant environments
- Consider encrypting sensitive context data

## Future Enhancements

- Multi-user approval (require N of M approvals)
- Approval delegation (assign to specific users)
- Approval templates (pre-approved patterns)
- Approval analytics dashboard
- Integration with GitHub PR approvals

---

## Summary

The approval system gives you **mobile authorization control** over autonomous Claude Code tasks. It's perfect for:

- ✅ High-stakes operations
- ✅ Cost-sensitive actions
- ✅ Production deployments
- ✅ Data modifications
- ✅ External integrations

**You maintain control while enabling automation.** 🎯
