import sys
from pathlib import Path

def test_imports():
    try:
        from app.core.config import settings
        print("✅ Successfully imported settings")
        print(f"Project name: {settings.PROJECT_NAME}")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    # Add project root to Python path
    project_root = Path(__file__).resolve().parent.parent
    sys.path.append(str(project_root))
    test_imports()