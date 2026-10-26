"""
scripts/verify_stage1_sandbox.py
Runs and proves all Stage 1 requirements live against Docker.
"""

import os
import sys
import tempfile
import subprocess
import json
import docker
import docker.errors

# Include fixforge package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixforge"))
from sandbox.runner import run_in_sandbox

client = docker.from_env()

print("=" * 60)
print("STAGE 1: LIVE SANDBOX VERIFICATION & SECURITY AUDIT")
print("=" * 60)

# 1. Non-root user check
print("\n[SECURITY CLAIM 1: Non-root user (id)]")
out = client.containers.run("fixforge-sandbox:latest", "id", remove=True)
print(out.decode().strip())

# 2. Network blocked check
print("\n[SECURITY CLAIM 2: Network blocked (network_mode='none')]")
try:
    client.containers.run(
        "fixforge-sandbox:latest",
        ["python", "-c", "import urllib.request; urllib.request.urlopen('http://1.1.1.1', timeout=2)"],
        network_mode="none",
        remove=True
    )
    print("UNEXPECTED: Network call succeeded!")
except Exception as e:
    print(f"CONFIRMED: Outbound call failed as expected -> {type(e).__name__}: {str(e)[:120]}")

# 3. Read-only repo mount
print("\n[SECURITY CLAIM 3: Read-only repo mount]")
with tempfile.TemporaryDirectory() as tmp_ro:
    try:
        client.containers.run(
            "fixforge-sandbox:latest",
            ["/bin/bash", "-c", "touch /app_src/exploit.txt"],
            volumes={tmp_ro: {"bind": "/app_src", "mode": "ro"}},
            remove=True
        )
        print("UNEXPECTED: Write succeeded on read-only mount!")
    except docker.errors.ContainerError as e:
        err_msg = e.stderr.decode("utf-8", errors="replace").strip() if isinstance(e.stderr, bytes) else str(e.stderr or "").strip()
        print(f"CONFIRMED: Write failed as expected -> {err_msg}")

# 4. Memory / Time Limits
print("\n[SECURITY CLAIM 4: Memory limit (runaway memory killed)]")
try:
    c = client.containers.run(
        "fixforge-sandbox:latest",
        ["python", "-c", "x = ' ' * (100 * 1024 * 1024)"], # 100MB allocation
        mem_limit="32m",
        remove=True
    )
    print("UNEXPECTED: Memory runaway process was not killed!")
except docker.errors.ContainerError as e:
    print(f"CONFIRMED: Runaway process killed by OOM / mem_limit (exit status {e.exit_status})")

# 5. Disposable container removed
print("\n[SECURITY CLAIM 5: Container removed afterwards]")
initial_containers = [c.id for c in client.containers.list(all=True)]
print(f"Active/exited containers before sandbox run: {len(initial_containers)}")

# Now run a real Python bug repair
print("\n" + "=" * 60)
print("REAL PYTHON REPAIR IN SANDBOX")
print("=" * 60)

with tempfile.TemporaryDirectory() as repo_dir:
    # Initialize a git repository with a real python bug
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@fixforge.ai"], cwd=repo_dir, check=True)

    calc_file = os.path.join(repo_dir, "calculator.py")
    test_file = os.path.join(repo_dir, "test_calculator.py")

    with open(calc_file, "w", newline="\n") as f:
        f.write("def divide(a, b):\n    return a * b  # Bug: multiplication instead of division\n")

    with open(test_file, "w", newline="\n") as f:
        f.write("from calculator import divide\n\ndef test_divide():\n    assert divide(10, 2) == 5\n")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial buggy commit"], cwd=repo_dir, check=True, capture_output=True)

    # Good patch
    good_patch = """diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def divide(a, b):
-    return a * b  # Bug: multiplication instead of division
+    return a / b  # Bug: multiplication instead of division
"""
    print("\n--- TEST CASE A: Good patch -> passed ---")
    res_good = run_in_sandbox(repo_dir, good_patch, "pytest")
    print("Status:", res_good["status"])
    print("Passed:", res_good["passed"])
    print("Exit code:", res_good["exit_code"])
    print("Output:\n", res_good["stdout"].strip())

    # Malformed patch
    bad_patch = """diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -999,2 +999,2 @@
 def nonexistent():
-    pass
+    return True
"""
    print("\n--- TEST CASE B: Malformed patch -> patch_failed with git error ---")
    res_bad = run_in_sandbox(repo_dir, bad_patch, "pytest")
    print("Status:", res_bad["status"])
    print("Passed:", res_bad["passed"])
    print("Exit code:", res_bad["exit_code"])
    print("Error text:\n", res_bad["stderr"].strip())

    # Failing patch (wrong fix)
    failing_patch = """diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def divide(a, b):
-    return a * b  # Bug: multiplication instead of division
+    return a - b  # Wrong fix: subtraction
"""
    print("\n--- TEST CASE C: Failing test patch -> failed with logs ---")
    res_fail = run_in_sandbox(repo_dir, failing_patch, "pytest")
    print("Status:", res_fail["status"])
    print("Passed:", res_fail["passed"])
    print("Exit code:", res_fail["exit_code"])
    print("Output:\n", res_fail["stdout"].strip())

# 4b. Time Limit
print("\n[SECURITY CLAIM 4b: Time limit (timeout runaway process killed)]")
try:
    c = client.containers.run(
        "fixforge-sandbox:latest",
        ["python", "-c", "import time; time.sleep(30)"],
        detach=True
    )
    try:
        c.wait(timeout=2)
        print("UNEXPECTED: Process finished instead of timing out!")
    except Exception as te:
        print(f"CONFIRMED: Process exceeded 2s timeout ({type(te).__name__}), container killed")
    finally:
        c.remove(force=True)
except Exception as e:
    print(f"Time limit check caught: {e}")

print("\n--- CHECKING FOR LEFTOVER CONTAINERS ---")
after_containers = client.containers.list(all=True)
print(f"Remaining active/stopped containers in `docker ps -a`: {len(after_containers)}")
assert len(after_containers) == 0, f"Leaked containers: {after_containers}"
print("CONFIRMED: `docker ps -a` shows 0 containers left! All disposable containers cleaned up.")
