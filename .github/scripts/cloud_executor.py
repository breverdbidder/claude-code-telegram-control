#!/usr/bin/env python3
"""
cloud_executor.py -- compatibility shim
Redirects to cloud_executor_v4.py (real Claude tool_use implementation).
Kept so any external references still resolve.
"""
import subprocess, sys, os

v4 = os.path.join(os.path.dirname(__file__), "cloud_executor_v4.py")
result = subprocess.run([sys.executable, v4], env=os.environ)
sys.exit(result.returncode)
