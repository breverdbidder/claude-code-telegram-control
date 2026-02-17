#!/usr/bin/env python3
"""
AgentRemote v3.0 Approval System
Handles authorization requests from Claude Code tasks via Telegram
"""

import os
import json
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

APPROVAL_FILE = os.path.expanduser("~/claude_code_tasks/pending_approvals.json")
APPROVAL_RESPONSES = os.path.expanduser("~/claude_code_tasks/approval_responses.json")

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approval button clicks"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data: approval_id:action
    data = query.data.split(':')
    if len(data) != 2 or data[0] != 'approve':
        return
    
    approval_id = data[1]
    action = query.data.split('_')[1]  # approve_yes or approve_no
    
    # Load pending approvals
    approvals = {}
    if os.path.exists(APPROVAL_FILE):
        with open(APPROVAL_FILE, 'r') as f:
            approvals = json.load(f)
    
    if approval_id not in approvals:
        await query.edit_message_text("⚠️ Approval request expired or already processed")
        return
    
    approval_data = approvals[approval_id]
    
    # Record response
    response = {
        'approval_id': approval_id,
        'action': 'approved' if action == 'yes' else 'rejected',
        'timestamp': datetime.now().isoformat(),
        'task': approval_data.get('task', 'Unknown'),
        'request': approval_data.get('request', 'Unknown')
    }
    
    # Save response
    responses = {}
    if os.path.exists(APPROVAL_RESPONSES):
        with open(APPROVAL_RESPONSES, 'r') as f:
            responses = json.load(f)
    
    responses[approval_id] = response
    
    os.makedirs(os.path.dirname(APPROVAL_RESPONSES), exist_ok=True)
    with open(APPROVAL_RESPONSES, 'w') as f:
        json.dump(responses, f, indent=2)
    
    # Remove from pending
    del approvals[approval_id]
    with open(APPROVAL_FILE, 'w') as f:
        json.dump(approvals, f, indent=2)
    
    # Update message
    emoji = "✅" if action == 'yes' else "❌"
    status = "APPROVED" if action == 'yes' else "REJECTED"
    
    await query.edit_message_text(
        f"{emoji} **{status}**\n\n"
        f"**Task:** {approval_data.get('task', 'Unknown')}\n"
        f"**Request:** {approval_data.get('request', 'Unknown')}\n"
        f"**Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"✓ Response recorded and sent to Claude Code",
        parse_mode='Markdown'
    )

def send_approval_request(task_id: str, request_text: str, context: dict = None):
    """
    Send approval request to Telegram
    Called by Claude Code tasks that need authorization
    
    Usage:
        from approval_system import send_approval_request
        approval_id = send_approval_request(
            task_id="task_123",
            request_text="Delete 500 files in production database?",
            context={"files": 500, "severity": "high"}
        )
        
        # Wait for approval
        response = wait_for_approval(approval_id, timeout=300)
        if response == "approved":
            # proceed
        else:
            # abort
    """
    approval_id = f"{task_id}_{int(time.time())}"
    
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
    
    return approval_id

def wait_for_approval(approval_id: str, timeout: int = 300) -> str:
    """
    Wait for approval response (blocking)
    
    Args:
        approval_id: Approval request ID
        timeout: Max wait time in seconds (default 5 min)
    
    Returns:
        'approved', 'rejected', or 'timeout'
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if os.path.exists(APPROVAL_RESPONSES):
            with open(APPROVAL_RESPONSES, 'r') as f:
                responses = json.load(f)
            
            if approval_id in responses:
                return responses[approval_id]['action']
        
        time.sleep(2)  # Check every 2 seconds
    
    # Timeout - auto-reject
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

def check_pending_approvals():
    """Check and return all pending approval requests"""
    if not os.path.exists(APPROVAL_FILE):
        return []
    
    with open(APPROVAL_FILE, 'r') as f:
        approvals = json.load(f)
    
    return list(approvals.values())

if __name__ == "__main__":
    # Test approval request
    approval_id = send_approval_request(
        task_id="test_task",
        request_text="Test approval - delete test file?",
        context={"severity": "low"}
    )
    print(f"Created approval request: {approval_id}")
    print(f"Waiting for response...")
    
    result = wait_for_approval(approval_id, timeout=60)
    print(f"Result: {result}")
