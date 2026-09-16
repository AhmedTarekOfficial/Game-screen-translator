"""
Quick syntax check — imports all modules to verify no syntax errors.
Run with: python check_imports.py
"""
print("Checking imports...")

try:
    from app.data.config_manager import ConfigManager
    print("✓ config_manager")
except Exception as e:
    print(f"✗ config_manager: {e}")

try:
    from app.data.history_manager import HistoryManager
    print("✓ history_manager")
except Exception as e:
    print(f"✗ history_manager: {e}")

try:
    from app.core.hotkey_manager import HotkeyManager
    print("✓ hotkey_manager")
except Exception as e:
    print(f"✗ hotkey_manager: {e}")

try:
    from app.core.screenshot import capture_region
    print("✓ screenshot")
except Exception as e:
    print(f"✗ screenshot: {e}")

try:
    from app.core.translator import translate, SUPPORTED_LANGUAGES, SUPPORTED_LLMS
    print("✓ translator")
except Exception as e:
    print(f"✗ translator: {e}")

try:
    from app.core.ocr_engine import extract_text, preprocess_image
    print("✓ ocr_engine")
except Exception as e:
    print(f"✗ ocr_engine: {e}")

print("\nAll non-UI imports checked!")
print("(UI imports require a display — run main.py to test those)")
