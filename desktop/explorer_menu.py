"""Register ClipBridge's own Explorer verb; leave Windows' protected inbox class intact."""
import ctypes
import json
import os
import base64
import subprocess
from pathlib import Path
import winreg

PHONE_COMMAND = '{03B9580F-25C4-44A6-B150-A7B58F06FC10}'
REGISTRY_PATH = r'Software\Classes\CLSID' + '\\' + PHONE_COMMAND
VERB_PATH = r'Software\Classes\*\shell\ClipBridge.SendToPhone'


def snapshot(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            values, children = [], {}
            index = 0
            while True:
                try:
                    values.append(winreg.EnumValue(key, index)); index += 1
                except OSError:
                    break
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(key, index); index += 1
                    children[name] = snapshot(path+'\\'+name)
                except OSError:
                    break
            return {'values': values, 'children': children}
    except FileNotFoundError:
        return None


def delete_tree(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            children = [winreg.EnumKey(key, index) for index in range(winreg.QueryInfoKey(key)[0])]
        for child in children:
            delete_tree(path+'\\'+child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass


def restore(path, data):
    if data is not None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            for name, value, kind in data['values']:
                winreg.SetValueEx(key, name, 0, kind, value)
        for name, child in data['children'].items():
            restore(path+'\\'+name, child)


def shortcut_path():
    return Path(os.environ['APPDATA'])/'Microsoft/Windows/SendTo/Share to My Phone (ClipBridge).lnk'


def shortcut_script(script):
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    subprocess.run([str(Path(os.environ['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
                    '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                   check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def ps_string(value):
    return "'"+str(value).replace("'", "''")+"'"


def install(root, settings_folder):
    root = Path(root).resolve()
    executable = root/'ClipBridge-PC.exe'
    launcher = executable
    if not executable.is_file():
        raise ValueError('Keep the shell folder beside ClipBridge-PC.exe.')
    backup = Path(settings_folder)/'explorer-clipbridge-backup.json'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        data = json.loads(backup.read_text('utf-8'))
        if data['path'] != REGISTRY_PATH or data.get('verb_path') != VERB_PATH:
            raise ValueError('Unexpected registry backup path')
    else:
        data = {'path': REGISTRY_PATH, 'verb_path': VERB_PATH, 'original': snapshot(REGISTRY_PATH),
                'verb_original': snapshot(VERB_PATH)}
    data['executable'] = str(launcher)
    backup.write_text(json.dumps(data, indent=2), 'utf-8')
    destination = shortcut_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shortcut_script("$ErrorActionPreference='Stop'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut("+
                    ps_string(destination)+"); $s.TargetPath="+ps_string(launcher)+
                    "; $s.Arguments='--send-files --'; $s.IconLocation="+
                    ps_string(root/'shell/ClipBridge-Phone.ico')+"; $s.Save()")
    # Retire the unsuccessful experimental verb and our own COM registration.
    delete_tree(REGISTRY_PATH)
    restore(REGISTRY_PATH, data['original'])
    delete_tree(VERB_PATH)
    restore(VERB_PATH, data['verb_original'])
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


def uninstall(settings_folder, executable=None):
    backup = Path(settings_folder)/'explorer-clipbridge-backup.json'
    if backup.exists():
        data = json.loads(backup.read_text('utf-8'))
    elif executable is not None:
        data = {'path': REGISTRY_PATH, 'verb_path': VERB_PATH, 'executable': str(Path(executable).resolve())}
    else:
        raise ValueError('No ClipBridge Explorer-menu backup exists.')
    if data['path'] != REGISTRY_PATH or data.get('verb_path') != VERB_PATH:
        raise ValueError('Unexpected registry backup path')
    destination = shortcut_path()
    if destination.exists():
        expected = data.get('executable', str(Path(data['dll']).parent.parent/'ClipBridge-PC.exe') if 'dll' in data else '')
        shortcut_script("$ErrorActionPreference='Stop'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut("+
                        ps_string(destination)+"); if ($s.TargetPath -ine "+ps_string(expected)+
                        ") { throw 'Another application changed this shortcut; it was left in place.' }")
        destination.unlink()
    if backup.exists():
        backup.unlink()
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'restore'])
    args = parser.parse_args()
    settings = Path(os.environ['LOCALAPPDATA'])/'ClipBridge'
    if args.action == 'install':
        install(Path(__file__).resolve().parents[1], settings)
    else:
        uninstall(settings, Path(__file__).resolve().parents[1]/'ClipBridge-PC.exe')
    print('ClipBridge Send to shortcut '+('installed.' if args.action == 'install' else 'removed.'))
