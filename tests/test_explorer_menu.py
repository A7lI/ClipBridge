from pathlib import Path
import sys
import tempfile
import unittest
import uuid
import winreg
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
import explorer_menu as menu


class ExplorerMenuTests(unittest.TestCase):
    def setUp(self):
        self.path=r'Software\Classes\CLSID\{'+str(uuid.uuid4())+'}'
        self.verb=r'Software\Classes\*\shell\ClipBridge.Test.'+uuid.uuid4().hex
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        (self.root/'shell').mkdir();(self.root/'ClipBridge-PC.exe').touch()
        self.settings=self.root/'settings'

    def tearDown(self):
        menu.delete_tree(self.path)
        menu.delete_tree(self.verb)
        self.temporary.cleanup()

    def test_install_reinstall_remove_shortcut_and_restore_experimental_keys(self):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,self.path) as key:
            winreg.SetValueEx(key,'Original',0,winreg.REG_DWORD,42)
        original=menu.snapshot(self.path)
        link=self.root/'Share to phone.lnk'
        with patch.object(menu,'REGISTRY_PATH',self.path),patch.object(menu,'VERB_PATH',self.verb),patch.object(menu,'shortcut_path',return_value=link):
            menu.install(self.root,self.settings);menu.install(self.root,self.settings)
            self.assertTrue(link.is_file())
            menu.shortcut_script("$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+menu.ps_string(link)+
                                 "); if ($s.TargetPath -ine "+menu.ps_string(self.root/'ClipBridge-PC.exe')+
                                 " -or $s.Arguments -ne '--send-files --') { throw 'Incorrect shortcut' }")
            self.assertEqual(menu.snapshot(self.path),original)
            self.assertIsNone(menu.snapshot(self.verb))
            menu.uninstall(self.settings)
            self.assertFalse(link.exists())

    def test_remove_owned_shortcut_without_development_view_backup(self):
        link=self.root/'Share to phone.lnk'
        with patch.object(menu,'REGISTRY_PATH',self.path),patch.object(menu,'VERB_PATH',self.verb),patch.object(menu,'shortcut_path',return_value=link):
            menu.install(self.root,self.settings)
            (self.settings/'explorer-clipbridge-backup.json').unlink()
            menu.uninstall(self.settings,self.root/'ClipBridge-PC.exe')
            self.assertFalse(link.exists())

    def test_remove_does_not_overwrite_another_later_shortcut(self):
        link=self.root/'Share to phone.lnk'
        with patch.object(menu,'REGISTRY_PATH',self.path),patch.object(menu,'VERB_PATH',self.verb),patch.object(menu,'shortcut_path',return_value=link):
            menu.install(self.root,self.settings)
            menu.shortcut_script("$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+menu.ps_string(link)+
                                 "); $s.TargetPath="+menu.ps_string(self.root/'other.exe')+"; $s.Save()")
            with self.assertRaises(Exception):menu.uninstall(self.settings)
            self.assertTrue(link.exists())


if __name__=='__main__':unittest.main()
