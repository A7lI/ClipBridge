"""After build_android.py, check actual production Java helpers and QR decoder."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from PIL import ImageOps
import qrcode

parser=argparse.ArgumentParser()
parser.add_argument('--work',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
java=Path('C:/Program Files/Android/Android Studio/jbr/bin')
sdk=Path.home()/'AppData/Local/Android/Sdk'
android=sorted((sdk/'platforms').glob('android-*'),key=lambda p:int(p.name.split('-')[1].split('.')[0]))[-1]/'android.jar'
libraries=[args.work/'classes',android,root/'android/libs/zxing-core-3.5.3.jar']
# Harness classes stay outside APK build outputs.
with tempfile.TemporaryDirectory() as temporary:
    folder=Path(temporary);classpath=';'.join(str(p) for p in [folder,*libraries])
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',classpath,'-d',str(folder),str(root/'tests/AndroidFeatureHarness.java')],check=True)
    command=[str(java/'java.exe'),'-cp',classpath,'app.clipbridge.AndroidFeatureHarness']
    subprocess.run(command,check=True)
    cases=['clipbridge://192.168.1.2:48721/pair?key='+'a'*43,'https://example.com/qr-test','English العربية 123456']
    for value in cases:
        image=qrcode.make(value).convert('L')
        expected=folder/'expected.txt';expected.write_text(value,encoding='utf-8')
        for rotation,inverted in [(0,False),(90,False),(180,True),(270,False)]:
            frame=image.rotate(rotation,expand=True)
            if inverted:frame=ImageOps.invert(frame)
            raw=folder/'frame.y';raw.write_bytes(frame.tobytes())
            subprocess.run([*command,str(raw),str(frame.width),str(frame.height),str(expected)],check=True)
    print('12 actual QR decoding checks passed: pairing links, URLs, Unicode, rotation, inverted contrast.')
