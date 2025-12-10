"""
Application Constants
Centralized location for all application constants
"""

# File paths
CHECKPOINT_FILE = 'checkpoints/checker_progress.json'
LOG_DIR = 'logs'
REPORTS_DIR = 'reports'

# UI Constants
DEFAULT_REFRESH_RATE = 0.5  # seconds
PROCESSING_MESSAGE = "⏳ Processing... Please wait"

# Thread timeouts
THREAD_STOP_TIMEOUT = 10.0  # seconds
START_DELAY = 2.0  # seconds
RESUME_DELAY = 2.0  # seconds
PAUSE_DELAY = 0.5  # seconds
STOP_DELAY = 3.0  # seconds

# Checkpoint retry
CHECKPOINT_DELETE_ATTEMPTS = 3
CHECKPOINT_DELETE_RETRY_DELAY = 0.5  # seconds

# Logging
MAX_RECENT_LOGS = 15
DEFAULT_LOG_COUNT = 1
