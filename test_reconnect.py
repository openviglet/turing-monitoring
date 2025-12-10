"""
Test script to check reconnection status
"""

import os
import json
from src.services import CheckerService

# Check checkpoint file
checkpoint_file = 'checkpoints/checker_progress.json'
print("=" * 80)
print("RECONNECTION DEBUG TEST")
print("=" * 80)

# Check if checkpoint exists
if os.path.exists(checkpoint_file):
    print(f"✓ Checkpoint file exists: {checkpoint_file}")
    
    try:
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
        
        print(f"\nCheckpoint data:")
        print(f"  Timestamp: {checkpoint.get('timestamp')}")
        print(f"  Base URL: {checkpoint.get('base_url')}")
        print(f"  Locale: {checkpoint.get('locale')}")
        print(f"  Current page: {checkpoint.get('current_page')}")
        print(f"  Last completed: {checkpoint.get('last_completed_page')}")
        print(f"  URLs checked: {checkpoint.get('total_urls_checked')}")
        print(f"  Failed URLs: {len(checkpoint.get('failed_urls', []))}")
        print(f"  Error codes: {checkpoint.get('error_status_codes')}")
    except Exception as e:
        print(f"✗ Error reading checkpoint: {e}")
else:
    print(f"✗ Checkpoint file NOT found: {checkpoint_file}")

# Check if checker service detects running thread
print(f"\n" + "=" * 80)
print("Checking for running threads...")
print("=" * 80)

checker_service = CheckerService()
is_running = checker_service.is_running()
print(f"CheckerService.is_running(): {is_running}")

if is_running:
    print("✓ Background process IS running")
    print("  → Should reconnect automatically")
else:
    print("✗ Background process NOT running")
    if os.path.exists(checkpoint_file):
        print("  → Will resume from checkpoint when started")
    else:
        print("  → Will start from beginning")

print("\n" + "=" * 80)
