# Project Architecture - URL Checker

## Overview

The project has been refactored to follow a clean and well-organized architecture with clear separation of concerns.

## Directory Structure

```
turing-monitoring/
├── app.py                     # Application entry point (refactored)
├── app_old.py                 # Backup of previous version
├── app_refactored.py          # Refactored version (source)
├── src/
│   ├── core/                  # Core application components
│   │   ├── __init__.py
│   │   ├── state_manager.py   # State management (session_state)
│   │   ├── initialization.py  # Service initialization
│   │   └── process_manager.py # Queue updates management
│   ├── handlers/              # Event handlers
│   │   ├── __init__.py
│   │   └── button_handlers.py # Handlers for Start/Stop/Pause/Resume buttons
│   ├── services/              # Business services
│   │   ├── __init__.py
│   │   ├── checker_service.py # URL verification service
│   │   ├── config_service.py  # Configuration service
│   │   ├── email_service.py   # Email service
│   │   └── stats_service.py   # Statistics service
│   ├── ui/                    # Interface components
│   │   ├── __init__.py
│   │   ├── config_sidebar.py  # Configuration sidebar
│   │   ├── metrics_display.py # Metrics display
│   │   ├── chart_display.py   # Response charts
│   │   ├── logs_display.py    # Logs display
│   │   └── results_table.py   # Results table
│   ├── utils/                 # Utilities
│   │   ├── __init__.py
│   │   └── constants.py       # Application constants
│   ├── models/                # Data models (future)
│   │   └── __init__.py
│   ├── checker.py             # URL checker core
│   ├── config_loader.py       # Configuration loader
│   ├── email_sender.py        # Email sending
│   └── report_generator.py    # Report generation
└── config.ini                 # Configuration file
```

## Main Components

### 1. Core (`src/core/`)

Fundamental application modules:

#### StateManager (`state_manager.py`)
- Manages all application state via `st.session_state`
- Methods for get/set flags (running, paused, processing)
- Centralized initialization of state variables

#### ServiceInitializer (`initialization.py`)
- Initializes all services (Config, Checker, Email, Stats)
- Detects background processes
- Validates email configurations
- Manages reconnection after browser refresh

#### ProcessManager (`process_manager.py`)
- Processes queue updates
- Manages different update types (page, checking, result, complete, etc)
- Updates progress bar
- Sends emails when needed

### 2. Handlers (`src/handlers/`)

UI event handlers:

#### ButtonHandlers (`button_handlers.py`)
- `handle_start()`: Starts verification (new or from checkpoint)
- `handle_stop()`: Stops verification and clears checkpoint
- `handle_pause()`: Pauses verification keeping checkpoint
- `handle_resume()`: Resumes verification from checkpoint
- Retry logic for critical operations

### 3. Services (`src/services/`)

Business services with well-defined responsibilities:

#### CheckerService
- Manages background verification thread
- Controls pause/stop flags
- Provides updates via queue
- Applies monkey patches for monitoring

#### StatsService
- Maintains execution statistics
- Manages activity logs
- Calculates progress and elapsed time
- Saves/loads checkpoints

#### ConfigService
- Loads configurations from config.ini
- Provides centralized access to configurations

#### EmailService
- Sends notification emails
- Uses custom HTML template
- Brevo API integration

### 4. UI (`src/ui/`)

Reusable visual components:

- **config_sidebar**: Configuration in sidebar
- **metrics_display**: Main metrics cards
- **chart_display**: Response times chart
- **logs_display**: Recent activities list
- **results_table**: Table of problematic URLs

### 5. Utils (`src/utils/`)

Utilities and constants:

#### constants.py
- File paths
- Timeouts and delays
- Standard messages
- UI configurations

## Execution Flow

### Initialization
1. `StateManager.initialize_state()` - Initializes state variables
2. `ServiceInitializer.initialize_all()` - Initializes all services
3. Background process detection
4. Configuration validation

### Verification Cycle
1. User clicks Start/Resume
2. `StateManager` marks as "processing"
3. `ButtonHandlers` executes appropriate action
4. `CheckerService` starts background thread
5. `ProcessManager` processes queue updates
6. UI updates in real-time (0.5s)
7. On completion, sends email if configured

### Pause/Resume
1. User clicks Pause
2. `CheckerService` sets `pause_requested` flag
3. Thread enters waiting loop
4. UI stops updating
5. User clicks Resume
6. Flag is cleared, thread continues
7. UI resumes updating

### Stop
1. User clicks Stop
2. `CheckerService` sets `stop_requested` flag
3. Thread saves checkpoint and terminates
4. Browsers are closed
5. Checkpoint is deleted (with retry)
6. Statistics are reset
7. UI returns to initial state

## Design Principles

### Separation of Concerns
- **Core**: Central application logic
- **Handlers**: User events and interactions
- **Services**: Business rules
- **UI**: Visual presentation
- **Utils**: Helper functions

### Single Responsibility
Each module has a specific and well-defined responsibility.

### Don't Repeat Yourself (DRY)
Constants and repeated logic have been centralized.

### Dependency Injection
Services are injected via `st.session_state`, facilitating testing.

### Fail Safe
- Retry logic for critical operations
- Exception handling in WebSocket
- Configuration validation

## Advantages of the New Architecture

1. **Maintainability**: Organized and easy-to-understand code
2. **Testability**: Independent modules can be tested in isolation
3. **Scalability**: Easy to add new features
4. **Reusability**: Components can be used in other contexts
5. **Clarity**: Well-defined responsibilities
6. **Performance**: Localized optimizations
7. **Debug**: Easier to identify problems

## Configurable Constants

All constants are in `src/utils/constants.py`:

```python
# Timeouts
THREAD_STOP_TIMEOUT = 10.0
START_DELAY = 2.0
RESUME_DELAY = 2.0
PAUSE_DELAY = 0.5
STOP_DELAY = 3.0

# UI
DEFAULT_REFRESH_RATE = 0.5
PROCESSING_MESSAGE = "⏳ Processing... Please wait"

# Checkpoint
CHECKPOINT_DELETE_ATTEMPTS = 3
CHECKPOINT_DELETE_RETRY_DELAY = 0.5
```

## Next Steps

1. Create data models in `src/models/`
2. Add unit tests
3. Add API documentation
4. Implement structured logging
5. Add performance metrics
6. Create CI/CD pipeline

## Migration

The `app_old.py` file contains the previous version for reference. To revert:

```bash
cp app_old.py app.py
```

## Conclusion

The refactored architecture makes the project more professional, maintainable, and scalable, following software development best practices.
