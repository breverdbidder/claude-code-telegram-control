#!/usr/bin/env python3
"""
Example: Claude Code task that uses approval system
"""

from claude_code_approval import request_approval
import time

def dangerous_operation():
    """Simulate a dangerous operation that needs approval"""
    print("🚀 Starting task that needs approval...")
    
    # Request approval before proceeding
    result = request_approval(
        task_id="test_dangerous_op",
        request_text="Delete 100 test files from /tmp directory?",
        context={
            "files": 100,
            "directory": "/tmp",
            "severity": "medium",
            "reversible": False
        },
        timeout=120  # 2 minutes
    )
    
    if result == "approved":
        print("✅ Approval granted - executing operation")
        # Simulate work
        for i in range(5):
            print(f"  Processing... {(i+1)*20}%")
            time.sleep(1)
        print("✓ Operation completed successfully")
        
    elif result == "rejected":
        print("❌ User rejected - operation cancelled")
        
    elif result == "timeout":
        print("⏱️ No response received - operation cancelled for safety")

if __name__ == "__main__":
    dangerous_operation()
