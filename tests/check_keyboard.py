"""Run the production offline completion engine and Arabic-layout checks."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
java = Path(os.environ.get("JAVA_HOME", "C:/Program Files/Android/Android Studio/jbr")) / "bin"
with tempfile.TemporaryDirectory() as folder:
    subprocess.run([str(java / "javac.exe"), "-encoding", "UTF-8", "-d", folder,
                    str(root / "android/src/app/clipbridge/WordSuggestions.java"),
                    str(root / "tests/KeyboardHarness.java")], check=True)
    subprocess.run([str(java / "java.exe"), "-Dfile.encoding=UTF-8", "-cp", folder, "app.clipbridge.KeyboardHarness",
                    str(root / "android/src/app/clipbridge/BridgeKeyboard.java"),
                    str(root / "android/assets")], check=True)
