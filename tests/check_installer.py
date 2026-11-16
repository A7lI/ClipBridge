"""Test the real installer in an isolated folder without launching clipboard sync."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import winreg
import zipfile

APP_ID = '{C76D5B54-78B0-4C5C-962E-C56DACF1F657}_is1'
REGISTRY = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + APP_ID


def folder(identity):
    value = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, identity, None, 0, value):
        raise OSError('Could not locate Windows shortcuts')
    return Path(value.value)


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            return True
    except FileNotFoundError:
        return False


def contents(path):
    return path.read_bytes() if path.exists() else None


def run(executable, *arguments):
    subprocess.run([str(executable), *map(str, arguments)], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=90)


def check_link(link, target):
    # Data travels through environment variables, not interpolated shell code.
    env = dict(os.environ, CLIPBRIDGE_TEST_LINK=str(link), CLIPBRIDGE_TEST_TARGET=str(target))
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CLIPBRIDGE_TEST_LINK); "
                    "if ($s.TargetPath -ine $env:CLIPBRIDGE_TEST_TARGET) { throw 'Incorrect shortcut target' }"],
                   env=env, check=True, creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--portable', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    scratch = args.work.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    target = scratch / 'installed-app'
    assert target.resolve().is_relative_to(scratch)
    start_group = folder(2) / 'ClipBridge'
    desktop_link = folder(0x10) / 'ClipBridge.lnk'
    sendto = folder(9) / 'Share to My Phone (ClipBridge).lnk'
    settings = Path(os.environ['LOCALAPPDATA']) / 'ClipBridge/settings.json'
    assert not registered(), 'A real ClipBridge installation already exists; use a clean Windows test account'
    assert not target.exists() and not start_group.exists() and not desktop_link.exists(), 'Test paths must be unused'
    saved_settings, saved_sendto = contents(settings), contents(sendto)
    tasks = 'desktopicon' + (',sendto' if saved_sendto is None else '')
    installer = args.installer.resolve()
    uninstaller = target / 'unins000.exe'
    executable = target / 'ClipBridge-PC.exe'
    sentinel = target / 'user-added-file.txt'
    arguments = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART', '/NOCLOSEAPPLICATIONS',
                 '/NORESTARTAPPLICATIONS', '/DIR=' + str(target), '/TASKS=' + tasks]
    try:
        run(installer, *arguments, '/LOG=' + str(scratch / 'install.log'))
        assert registered() and uninstaller.exists()
        with zipfile.ZipFile(args.portable) as archive:
            for entry in archive.infolist():
                if not entry.is_dir():
                    assert hashlib.sha256((target / entry.filename).read_bytes()).digest() == hashlib.sha256(archive.read(entry)).digest(), entry.filename
        check_link(start_group / 'ClipBridge.lnk', executable)
        check_link(desktop_link, executable)
        if saved_sendto is None:
            check_link(sendto, executable)
        else:
            assert contents(sendto) == saved_sendto
        report = scratch / 'runtime.json'
        run(executable, '--check', report)
        assert json.loads(report.read_text('utf-8'))['ok']
        print('Installed payload matches portable ZIP; Start and desktop shortcuts and installed runtime passed.', flush=True)
        sentinel.write_text('Keep user files during uninstall', encoding='utf-8')
        run(installer, *arguments, '/LOG=' + str(scratch / 'reinstall.log'))
        assert contents(settings) == saved_settings
        assert sentinel.exists()
        print('Reinstall passed and preserved existing pairing settings and user-added files.', flush=True)
    finally:
        if uninstaller.exists():
            run(uninstaller, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LOG=' + str(scratch / 'uninstall.log'))
            for _ in range(100):
                if not executable.exists():
                    break
                time.sleep(.1)
    assert not registered() and not executable.exists()
    assert not (start_group / 'ClipBridge.lnk').exists() and not desktop_link.exists()
    assert contents(sendto) == saved_sendto
    assert contents(settings) == saved_settings
    assert sentinel.read_text('utf-8') == 'Keep user files during uninstall'
    sentinel.unlink()
    # Inno's temporary cleanup process may finish after the uninstaller exits.
    # Remove the test directory only when empty; never delete remaining files.
    for attempt in range(50):
        try:
            if target.exists():
                target.rmdir()
            break
        except OSError:
            if attempt == 49:
                raise
            time.sleep(.1)
    print('Uninstall removed owned program files and shortcuts, retained settings, unrelated Send to shortcut and user files.', flush=True)


if __name__ == '__main__':
    main()
