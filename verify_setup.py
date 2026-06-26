"""
SETUP & VERIFICATION CHECKLIST
Run this to verify all components are ready
"""

# ============================================================
# VERIFICATION CHECKLIST - RUN THIS FIRST
# ============================================================

import os
import sys
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if file exists"""
    exists = os.path.exists(filepath)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {filepath}")
    return exists

def check_directory_exists(dirpath, description):
    """Check if directory exists"""
    exists = os.path.isdir(dirpath)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {dirpath}")
    return exists

def main():
    print("\n" + "="*70)
    print("BANK FRAUD DETECTION SYSTEM - VERIFICATION CHECKLIST")
    print("="*70 + "\n")
    
    base_path = Path(__file__).parent.absolute()
    os.chdir(base_path)
    
    all_good = True
    
    # Check directories
    print("DIRECTORIES:")
    print("-" * 70)
    dirs_to_check = [
        ("src", "Source code"),
        ("src/modules", "Verification modules"),
        ("src/utils", "Utilities"),
        ("src/api", "API routes"),
        ("tests", "Test suite"),
        ("database", "Database folder"),
        ("models", "Models folder"),
        ("logs", "Logs folder (will be created)"),
    ]
    
    for dir_path, desc in dirs_to_check:
        full_path = os.path.join(base_path, dir_path)
        if os.path.exists(full_path):
            print(f"✓ {desc}: {dir_path}")
        else:
            if dir_path not in ["logs"]:
                print(f"✗ {desc}: {dir_path} (MISSING)")
                all_good = False
            else:
                print(f"○ {desc}: {dir_path} (Will be created at runtime)")
    
    # Check core files
    print("\nCORE FILES:")
    print("-" * 70)
    core_files = [
        ("requirements.txt", "Python dependencies"),
        ("README.md", "Project documentation"),
        ("QUICKSTART.md", "Quick start guide"),
        ("API_GUIDE.md", "API documentation"),
        ("IMPLEMENTATION_ROADMAP.md", "Development roadmap"),
        ("PROJECT_SUMMARY.md", "Project summary"),
        ("Dockerfile", "Docker configuration"),
        ("docker-compose.yml", "Docker Compose setup"),
        (".gitignore", "Git ignore rules"),
        (".env.example", "Environment template"),
    ]
    
    for filename, desc in core_files:
        full_path = os.path.join(base_path, filename)
        if check_file_exists(full_path, desc):
            pass
        else:
            all_good = False
    
    # Check source modules
    print("\nSOURCE MODULES:")
    print("-" * 70)
    modules = [
        ("src/__init__.py", "Package init"),
        ("src/main.py", "FastAPI application"),
        ("src/modules/__init__.py", "Modules init"),
        ("src/modules/motion_verifier.py", "Motion verification"),
        ("src/modules/rppg_verifier.py", "rPPG verification"),
        ("src/modules/morph_detector.py", "Morph detection"),
        ("src/modules/iris_recognizer.py", "Iris recognition"),
        ("src/modules/trust_token.py", "Trust token management"),
        ("src/utils/__init__.py", "Utils init"),
        ("src/utils/config.py", "Configuration"),
        ("src/utils/database.py", "Database models"),
        ("src/utils/logger.py", "Logging setup"),
    ]
    
    for filepath, desc in modules:
        full_path = os.path.join(base_path, filepath)
        if check_file_exists(full_path, desc):
            pass
        else:
            all_good = False
    
    # Check test files
    print("\nTEST FILES:")
    print("-" * 70)
    test_files = [
        ("tests/test_modules.py", "Unit tests"),
        ("demo.py", "Demo script"),
    ]
    
    for filepath, desc in test_files:
        full_path = os.path.join(base_path, filepath)
        if check_file_exists(full_path, desc):
            pass
        else:
            all_good = False
    
    # Check imports
    print("\nMODULE IMPORTS:")
    print("-" * 70)
    sys.path.insert(0, str(base_path))
    
    imports_to_check = [
        ("cv2", "OpenCV"),
        ("numpy", "NumPy"),
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
    ]
    
    missing_modules = []
    for module_name, desc in imports_to_check:
        try:
            __import__(module_name)
            print(f"✓ {desc} ({module_name})")
        except ImportError:
            print(f"✗ {desc} ({module_name}) - NOT INSTALLED")
            missing_modules.append(module_name)
    
    # Summary
    print("\n" + "="*70)
    if all_good and not missing_modules:
        print("✓ ALL CHECKS PASSED - SYSTEM READY!")
        print("="*70)
        print("\nNEXT STEPS:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run demo: python demo.py")
        print("3. Run tests: pytest tests/test_modules.py -v")
        print("4. Start API: python src/main.py")
        return 0
    else:
        print("✗ SOME CHECKS FAILED - PLEASE FIX:")
        print("="*70)
        if missing_modules:
            print(f"\nMissing packages: {', '.join(missing_modules)}")
            print(f"Install with: pip install {' '.join(missing_modules)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
