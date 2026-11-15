"""Build a standalone voice engine, then embed it in the Windows app.

Use Python 3.12 x64 with desktop/requirements-voice.txt and PyInstaller 6.22.3
for --voice-python. The main interpreter needs desktop/requirements.txt and
PyInstaller. No Cipher, Handy, model weights or private settings are bundled.
"""
import argparse
import importlib.metadata as metadata
from pathlib import Path
import shutil
import subprocess
import sys


def build(voice_python, work, output):
    root = Path(__file__).resolve().parent
    work, output = work.resolve(), output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    voice_dist = work/'voice-dist'
    subprocess.run([
        str(voice_python), '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--onefile', '--console', '--name', 'ClipBridge-Voice',
        '--distpath', str(voice_dist), '--workpath', str(work/'voice-build'),
        '--specpath', str(work), '--paths', str(root/'desktop'),
        '--collect-all', 'transcribe_cpp_native',
        '--copy-metadata', 'transcribe-cpp-native',
        '--copy-metadata', 'transcribe-cpp',
        '--hidden-import', 'transcribe_cpp_native',
        '--add-data', str(root/'desktop/assets')+';assets',
        str(root/'desktop/voice_worker.py')], check=True)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--onefile', '--windowed', '--name', 'ClipBridge-PC',
        '--distpath', str(output), '--workpath', str(work/'app-build'),
        '--specpath', str(work), '--paths', str(root/'desktop'),
        '--add-binary', str(voice_dist/'ClipBridge-Voice.exe')+';engines',
        '--add-data', str(root/'desktop/assets/clipbridge.png')+';assets',
        '--icon', str(root/'desktop/assets/clipbridge.ico'),
        '--version-file', str(root/'desktop/version-info.txt'),
        str(root/'desktop/app.py')], check=True)
    # Preserve notices from the exact voice build environment.
    collect = r'''
import importlib.metadata as m
from pathlib import Path
import shutil, sys
target = Path(sys.argv[1])
for name in ['numpy','onnxruntime','transcribe-cpp','transcribe-cpp-native','protobuf','flatbuffers']:
    d = m.distribution(name)
    for f in d.files or []:
        if any(k in f.name.lower() for k in ['license','notice','copying']):
            p = Path(d.locate_file(f))
            if p.is_file():
                out = target/name/Path(*f.parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p,out)
p = Path(sys.base_prefix)/'LICENSE.txt'
if p.is_file():
    shutil.copyfile(p,target/'Python-voice-LICENSE.txt')
'''
    subprocess.run([str(voice_python), '-c', collect, str(root/'licenses')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice-python', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.voice_python, args.work, args.output)
