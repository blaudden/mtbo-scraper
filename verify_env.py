#!/usr/bin/env python3
"""
verify_env.py - Environment validation script for Agent-First optimization.
Run this script to ensure the environment is correctly aligned for the scraper.
"""

import os
import shutil
import subprocess
import sys


def check_python_version() -> bool:
    print("🔍 Checking Python version...")
    required = (3, 12)
    current = sys.version_info
    if current.major == required[0] and current.minor >= required[1]:
        print(f"✅ Python {current.major}.{current.minor}.{current.micro} found.")
        print(
            f"❌ Python {required[0]}.{required[1]}+ is required. "
            f"Found {current.major}.{current.minor}."
        )
        return False
    return True


def check_venv() -> bool:
    print("🔍 Checking virtual environment...")
    if (
        hasattr(sys, "real_prefix")
        or getattr(sys, "base_prefix", sys.prefix) != sys.prefix
    ):
        print(f"✅ Running inside a virtual environment: {sys.prefix}")
    else:
        print("⚠️ Not running inside a virtual environment.")
        print("   It is highly recommended to use a venv.")

    # Check if .venv exists in current dir
    if os.path.exists(".venv"):
        print("✅ Found .venv directory.")
    else:
        print("❌ .venv directory not found in the current folder.")
        return False
    return True


def check_uv() -> None:
    print("🔍 Checking for 'uv' package manager...")
    if shutil.which("uv"):
        print("✅ 'uv' is installed.")
    else:
        print("⚠️ 'uv' is not found in PATH. Using standard 'pip' if needed.")


def check_dependencies() -> bool:
    print("🔍 Checking dependencies via 'uv sync' or 'pip check'...")
    try:
        if shutil.which("uv"):
            result = subprocess.run(
                ["uv", "sync", "--check"], capture_output=True, text=True
            )
            if result.returncode == 0:
                print("✅ Dependencies are synced (uv).")
            else:
                print("❌ Dependencies are out of sync. Run 'uv sync'.")
                return False
        else:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "check"], capture_output=True, text=True
            )
            if result.returncode == 0:
                print("✅ Pip dependency check passed.")
            else:
                print(f"❌ Pip dependency check failed:\n{result.stdout}")
                return False
    except Exception as e:
        print(f"⚠️ Could not check dependencies: {e}")
    return True


def main() -> None:
    print("--- MTBO Scraper Environment Verification ---")
    checks = [check_python_version(), check_venv(), check_dependencies()]

    check_uv()

    if all(checks):
        print("\n✨ Environment is READY for agent operations.")
        sys.exit(0)
    else:
        print("\n❌ Environment has issues. Please fix them before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
