#!/usr/bin/env python3
"""
Claude Code Approval Helper
Import this in Claude Code tasks to request human approval
"""

import os
import json
import time
from datetime import datetime

APPROVAL_FILE = os.path.expanduser("~/claude_code_tasks/pending_approvals.json")
APPROVAL_RESPONSES = os.path.expanduser("~/claude_code_tasks/approval_responses.json")

def request_approval(task_id: str, request_text: str, context: dict = None, timeout: int = 300):
    """
    Request approval from user via Telegram and wait for response
    
    Args:
        task_id: Unique task identifier
        request_text: Description of what needs approval
        context: Additional context data
        timeout: Max wait time in seconds (default 5 min)
    
    Returns:
        'approved', 'rejected', or 'timeout'
    
    Example:
        from claude_code_approval import request_approval
        
        result = request_approval(
            task_id="delete_production_db",
            request_text="Delete 500 records from production database?",
            context={"records": 500, "severity": "high"}
        )
        
        if result == "approved":
            # Proceed with deletion
            delete_records()
        else:
            print(f"Action cancelled: {result}")
    """
    approval_id = f"{task_id}_{int(time.time())}"
    
    # Create approval request
    approval_data = {
        'approval_id': approval_id,
        'task': task_id,
        'request': request_text,
        'context': context or {},
        'created_at': datetime.now().isoformat(),
        'status': 'pending'
    }
    
    # Save to pending approvals
    approvals = {}
    if os.path.exists(APPROVAL_FILE):
        with open(APPROVAL_FILE, 'r') as f:
            approvals = json.load(f)
    
    approvals[approval_id] = approval_data
    
    os.makedirs(os.path.dirname(APPROVAL_FILE), exist_ok=True)
    with open(APPROVAL_FILE, 'w') as f:
        json.dump(approvals, f, indent=2)
    
    print(f"🔐 Approval request created: {approval_id}")
    print(f"   Request: {request_text}")
    print(f"   Waiting for user response (timeout: {timeout}s)...")
    
    # Wait for approval response
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if os.path.exists(APPROVAL_RESPONSES):
            with open(APPROVAL_RESPONSES, 'r') as f:
                responses = json.load(f)
            
            if approval_id in responses:
                result = responses[approval_id]['action']
                print(f"✓ Received response: {result}")
                return result
        
        time.sleep(2)  # Check every 2 seconds
    
    # Timeout - auto-reject
    print(f"⏱️  Approval timeout - auto-rejecting")
    response = {
        'approval_id': approval_id,
        'action': 'timeout',
        'timestamp': datetime.now().isoformat()
    }
    
    responses = {}
    if os.path.exists(APPROVAL_RESPONSES):
        with open(APPROVAL_RESPONSES, 'r') as f:
            responses = json.load(f)
    
    responses[approval_id] = response
    with open(APPROVAL_RESPONSES, 'w') as f:
        json.dump(responses, f, indent=2)
    
    return 'timeout'

# Example usage
if __name__ == "__main__":
    result = request_approval(
        task_id="test_approval",
        request_text="Test approval request - proceed with test action?",
        context={"severity": "low", "action": "test"},
        timeout=60
    )
    print(f"Final result: {result}")
