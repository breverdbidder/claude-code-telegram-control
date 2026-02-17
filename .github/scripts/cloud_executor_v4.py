#!/usr/bin/env python3
"""
AgentRemote v4.0 Cloud Executor with Smart Router Integration
Achieves 90% FREE tier processing via intelligent routing
"""

import os
import sys
import json
import subprocess
from anthropic import Anthropic

def get_smart_router_model(task_complexity: str = "medium"):
    """
    Determine which model to use based on task complexity
    Returns model name for Smart Router
    """
    # Simple routing logic (can be enhanced)
    if "simple" in task_complexity.lower() or len(task_complexity) < 50:
        return "gemini/gemini-2.0-flash-exp"  # FREE tier
    elif "complex" in task_complexity.lower():
        return "claude-sonnet-4-20250514"  # Paid tier
    else:
        return "gemini/gemini-2.0-flash-exp"  # Default to FREE

def execute_task():
    """Main task execution with Smart Router"""
    
    # Get environment variables
    task_description = os.getenv('TASK_DESCRIPTION', 'No task description provided')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    smart_router_url = os.getenv('SMART_ROUTER_URL')
    smart_router_key = os.getenv('SMART_ROUTER_KEY')
    use_smart_router = os.getenv('USE_SMART_ROUTER', 'false').lower() == 'true'
    
    if not anthropic_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    print(f"🚀 AgentRemote v4.0 Cloud Executor")
    print(f"📋 Task: {task_description}")
    print(f"🎯 Smart Router: {'Enabled (90% FREE tier)' if use_smart_router else 'Disabled'}")
    print(f"🕐 Started: {subprocess.check_output(['date']).decode().strip()}")
    
    # Initialize client
    if use_smart_router and smart_router_url:
        print(f"🔄 Using Smart Router: {smart_router_url}")
        # Use LiteLLM proxy for Smart Router
        from openai import OpenAI
        client = OpenAI(
            base_url=smart_router_url,
            api_key=smart_router_key or anthropic_key
        )
        model = get_smart_router_model(task_description)
        print(f"🎯 Selected model: {model}")
    else:
        print(f"📡 Using direct Anthropic API")
        client = Anthropic(api_key=anthropic_key)
        model = "claude-sonnet-4-20250514"
    
    # Get repository context
    repo_files = subprocess.check_output(
        ['find', '.', '-type', 'f', '-not', '-path', './.git/*', '-not', '-path', './node_modules/*']
    ).decode()
    
    # Build system prompt
    system_prompt = f"""You are AgentRemote, an autonomous code execution agent running in GitHub Actions.

EXECUTION CONTEXT:
- Environment: GitHub Actions (Ubuntu latest)
- Working directory: Repository root
- Python: 3.11
- Available tools: git, bash, pip, npm

YOUR TASK:
{task_description}

REPOSITORY FILES:
{repo_files[:5000]}

EXECUTION PHASES:
1. ANALYZE: Understand the task and plan approach
2. IMPLEMENT: Make necessary code changes
3. VERIFY: Run tests if applicable
4. REPORT: Summarize what was done

RULES:
- Make atomic, focused changes
- Always test your changes when applicable
- Create meaningful commit messages
- If task needs clarification, state assumptions
- Output bash commands you'd run, prefixed with EXEC:

Output format:
ANALYSIS: [your analysis]
IMPLEMENTATION: [changes made]
VERIFICATION: [test results]
SUMMARY: [what was accomplished]
"""
    
    # Execute task
    print("\n🤖 Calling AI model...")
    
    try:
        if use_smart_router and smart_router_url:
            # Use OpenAI client for LiteLLM
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Execute this task: {task_description}"}
                ],
                max_tokens=8000,
                temperature=0.3
            )
            result = response.choices[0].message.content
            print(f"💰 Cost Tier: {'FREE (Gemini)' if 'gemini' in model else 'PAID (Claude)'}")
        else:
            # Use Anthropic client
            response = client.messages.create(
                model=model,
                max_tokens=8000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Execute this task: {task_description}"}
                ]
            )
            result = response.content[0].text
        
        print("\n" + "="*60)
        print(result)
        print("="*60)
        
        # Parse EXEC: commands and execute them
        has_changes = False
        for line in result.split('\n'):
            if line.startswith('EXEC:'):
                command = line[5:].strip()
                print(f"\n💻 Executing: {command}")
                try:
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
                    print(output.decode())
                    has_changes = True
                except subprocess.CalledProcessError as e:
                    print(f"⚠️  Command failed: {e.output.decode()}")
        
        # Set outputs for GitHub Actions
        with open(os.getenv('GITHUB_OUTPUT', '/dev/stdout'), 'a') as f:
            f.write(f"result<<EOF\n{result}\nEOF\n")
            f.write(f"has_changes={'true' if has_changes else 'false'}\n")
        
        print(f"\n✅ Task completed successfully")
        print(f"🕐 Finished: {subprocess.check_output(['date']).decode().strip()}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        with open(os.getenv('GITHUB_OUTPUT', '/dev/stdout'), 'a') as f:
            f.write(f"result=ERROR: {str(e)}\n")
            f.write(f"has_changes=false\n")
        return 1

if __name__ == "__main__":
    sys.exit(execute_task())
