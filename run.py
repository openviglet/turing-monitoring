"""
URL Checker - Launcher
Detects execution mode and launches appropriate interface
"""

import sys
import os

# Suppress all warnings before any imports
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
import warnings
warnings.filterwarnings('ignore')

import argparse


def is_gui_mode():
    """Detect if should run in GUI mode"""
    # Check if streamlit is explicitly being used
    if 'streamlit' in sys.modules:
        return True
    
    # Check command line arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--gui', action='store_true', help='Force GUI mode')
    parser.add_argument('--cli', action='store_true', help='Force CLI mode')
    args, _ = parser.parse_known_args()
    
    if args.gui:
        return True
    if args.cli:
        return False
    
    # Default to CLI if any arguments are provided
    if len(sys.argv) > 1:
        return False
    
    # Default to GUI if no arguments
    return True


def run_gui():
    """Launch Streamlit GUI"""
    import subprocess
    
    print("Starting GUI mode (Streamlit)...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app_gui.py"])


def run_cli():
    """Launch CLI"""
    # Remove launcher script from argv to pass clean args to CLI
    sys.argv = [sys.argv[0]] + [arg for arg in sys.argv[1:] if arg not in ['--gui', '--cli']]
    
    # Import and run CLI
    from app_cli import main as cli_main
    sys.exit(cli_main())


if __name__ == "__main__":
    if is_gui_mode():
        run_gui()
    else:
        run_cli()
