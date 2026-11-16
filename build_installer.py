"""Wrap a Windows release ZIP in a per-user Inno Setup installer."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile


def build(compiler, portable, work, output):
    root = Path(__file__).resolve().parent
    work, output = work.resolve(), output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    version = re.search(r"StringStruct\('FileVersion','([^']+)'\)",
                        (root / 'desktop/version-info.txt').read_text('utf-8')).group(1)
    with tempfile.TemporaryDirectory(prefix='payload-', dir=work) as temporary:
        payload = Path(temporary).resolve()
        assert payload.is_relative_to(work)
        with zipfile.ZipFile(portable) as archive:
            for entry in archive.infolist():
                if not (payload / entry.filename).resolve().is_relative_to(payload):
                    raise ValueError('Unsafe release archive path')
            required = {'ClipBridge-PC.exe', 'README-Windows.md', 'THIRD_PARTY.md',
                        'shell/ClipBridge-Phone.ico'}
            if not required.issubset(archive.namelist()):
                raise ValueError('Use the complete Windows portable release ZIP')
            archive.extractall(payload)
        shutil.copyfile(root / 'INSTALLER.md', payload / 'INSTALLER.md')
        license_dir = payload / 'licenses/inno-setup'
        license_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'licenses/inno-setup/LICENSE.txt', license_dir / 'LICENSE.txt')
        subprocess.run([str(compiler.resolve()), '/Qp', '/DAppVersion=' + version,
                        '/DPayloadDir=' + str(payload), '/DOutputDir=' + str(output),
                        '/DProjectDir=' + str(root), str(root / 'installer/ClipBridge.iss')], check=True)
    print('Built', output / f'ClipBridge-Setup-{version}.exe')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc', type=Path, required=True)
    parser.add_argument('--portable', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.iscc, args.portable, args.work, args.output)
