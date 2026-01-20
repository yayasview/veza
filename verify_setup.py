#!/usr/bin/env python3
"""
Setup Verification Script

Quick script to verify your environment is configured correctly.
"""

import os
import sys
from pathlib import Path


def check_mark(condition):
    return "✓" if condition else "✗"


def verify_setup():
    print("=" * 60)
    print("AVOMA TO NOTION EXPORT - SETUP VERIFICATION")
    print("=" * 60)
    print()

    all_good = True

    # Check Python version
    print("1. Python Version")
    py_version = sys.version_info
    is_valid = py_version.major == 3 and py_version.minor >= 7
    print(f"   {check_mark(is_valid)} Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    if not is_valid:
        print("   ⚠️  Python 3.7+ required")
        all_good = False
    print()

    # Check dependencies
    print("2. Dependencies")
    required_packages = [
        "notion_client",
        "requests",
        "dotenv",
        "dateutil",
        "tenacity",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("_", "-"))
            print(f"   ✓ {package}")
        except ImportError:
            print(f"   ✗ {package} (missing)")
            missing.append(package)
            all_good = False

    if missing:
        print()
        print("   ⚠️  Install missing packages:")
        print("      pip install -r requirements.txt")
    print()

    # Check .env file
    print("3. Environment Configuration")
    env_file = Path(".env")
    env_exists = env_file.exists()
    print(f"   {check_mark(env_exists)} .env file exists")

    if env_exists:
        # Check for required variables
        from dotenv import dotenv_values

        config = dotenv_values(".env")

        required_vars = ["AVOMA_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID"]

        for var in required_vars:
            value = config.get(var, "")
            is_set = bool(value and value != f"your_{var.lower()}_here")
            print(f"   {check_mark(is_set)} {var} {'set' if is_set else 'not set'}")
            if not is_set:
                all_good = False
    else:
        print("   ⚠️  Create .env file:")
        print("      cp .env.example .env")
        all_good = False
    print()

    # Check directories
    print("4. Directory Structure")
    dirs = ["src", "exports", "logs"]
    for dir_name in dirs:
        dir_path = Path(dir_name)
        exists = dir_path.exists()
        print(f"   {check_mark(exists)} {dir_name}/ {'exists' if exists else 'missing'}")
        if not exists and dir_name in ["exports", "logs"]:
            print(f"      (will be created automatically)")
    print()

    # Check source files
    print("5. Source Files")
    source_files = [
        "main.py",
        "src/__init__.py",
        "src/config.py",
        "src/logger.py",
        "src/avoma_client.py",
        "src/notion_client_wrapper.py",
        "src/transformer.py",
    ]

    for file_name in source_files:
        file_path = Path(file_name)
        exists = file_path.exists()
        print(f"   {check_mark(exists)} {file_name}")
        if not exists:
            all_good = False
    print()

    # Summary
    print("=" * 60)
    if all_good:
        print("✓ SETUP COMPLETE!")
        print()
        print("Next steps:")
        print("  1. Test connections:    python main.py --test-connection")
        print("  2. Verify schema:       python main.py --verify-schema")
        print("  3. Run dry-run:         python main.py --dry-run")
        print("  4. Start export:        python main.py")
    else:
        print("✗ SETUP INCOMPLETE")
        print()
        print("Please fix the issues above before running the export.")
    print("=" * 60)
    print()

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(verify_setup())
