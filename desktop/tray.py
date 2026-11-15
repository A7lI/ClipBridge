"""Windows notification-area controls. Tk actions are drained on the UI thread."""
import queue
import threading
from pathlib import Path
import sys

from PIL import Image, ImageDraw


class Tray:
    def __init__(self):
        import pystray
        self.actions = queue.Queue()
        logo = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets' / 'clipbridge.png'
        image = Image.open(logo).convert('RGBA').resize((64, 64)) if logo.is_file() else Image.new('RGBA', (64, 64), '#c7b5ff')
        self.icon = pystray.Icon('ClipBridge', image, 'ClipBridge · phone ↔ PC', pystray.Menu(
            pystray.MenuItem('Open ClipBridge', lambda *_: self.actions.put('open'), default=True),
            pystray.MenuItem('Pause / resume sync', lambda *_: self.actions.put('toggle')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit ClipBridge', lambda *_: self.actions.put('quit'))))
        threading.Thread(target=self.icon.run, daemon=True, name='ClipBridgeTray').start()

    def stop(self):
        self.icon.stop()
