#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator Launcher

This script provides a unified entry point for both the GUI and CLI versions
of the ImageSetConfiguration generator.
"""

import sys
import argparse
from pathlib import Path


def _cli_argv(argv):
    """Return raw argv with launcher-only flags stripped for generator.py."""
    return [arg for arg in argv if arg != "--cli"]


def _load_gui_main():
    """Import GUI entry point for package and direct-script execution."""
    if __package__:
        from .gui import main as gui_main
        return gui_main

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

    from imageset_generator.cli.gui import main as gui_main
    return gui_main


def _load_cli_main():
    """Import CLI entry point for package and direct-script execution."""
    if __package__:
        from ..generator import main as cli_main
        return cli_main

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

    from imageset_generator.generator import main as cli_main
    return cli_main


def check_gui_available():
    """Check if GUI is available (tkinter is working)"""
    try:
        import tkinter as tk

        # Try to create a root window
        root = tk.Tk()
        root.withdraw()  # Hide the window
        root.destroy()   # Clean up
        return True
    except Exception:
        return False


def main():
    """Main launcher function"""
    raw_args = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description="OpenShift ImageSetConfiguration Generator",
        add_help=False  # We'll handle help ourselves
    )
    
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical user interface"
    )
    
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Use command-line interface (default if GUI not available)"
    )
    
    parser.add_argument(
        "--help", "-h",
        action="store_true",
        help="Show this help message"
    )
    
    # Parse known args to avoid conflicts with generator.py args
    args, remaining_args = parser.parse_known_args()

    # Determine which interface to use
    if args.gui and args.cli:
        print("Error: Cannot specify both --gui and --cli")
        sys.exit(1)

    if args.help and not args.cli:
        parser.print_help()
        print("\n" + "="*60)
        print("For CLI options, use: imageset-generator --cli --help")
        print("For module mode, use: python -m imageset_generator.cli.launcher --cli --help")
        print("For direct script mode, use: python launcher.py --cli --help")
        print("For GUI mode, use: imageset-generator --gui")
        print("="*60)
        return
    
    use_gui = False
    if args.gui:
        if not check_gui_available():
            print("Error: GUI not available (tkinter not working)")
            print("Falling back to CLI mode...")
            use_gui = False
        else:
            use_gui = True
    elif args.cli:
        use_gui = False
    else:
        # Auto-detect: use GUI if available and no CLI args provided
        if check_gui_available() and not remaining_args:
            use_gui = True
        else:
            use_gui = False
    
    if use_gui:
        print("Launching GUI...")
        try:
            _load_gui_main()()
        except ImportError as e:
            print(f"Error: Cannot import GUI module: {e}")
            print("Falling back to CLI mode...")
            use_gui = False
        except Exception as e:
            print(f"Error launching GUI: {e}")
            sys.exit(1)
    
    if not use_gui:
        # Launch CLI version
        try:
            # Forward the user's original CLI args, minus launcher-only selectors.
            sys.argv = [sys.argv[0]] + _cli_argv(raw_args)
            _load_cli_main()()
        except ImportError as e:
            print(f"Error: Cannot import generator module: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error running CLI: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
