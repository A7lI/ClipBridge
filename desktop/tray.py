"""Windows notification-area controls. Tk actions are drained on the UI thread."""
import queue
import threading

from PIL import Image, ImageDraw


class Tray:
    def __init__(self):
        import pystray
        self.actions = queue.Queue()
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((3, 3, 61, 61), radius=14, fill='#1b282f')
        draw.rounded_rectangle((12, 14, 34, 44), radius=4, outline='#8ee3c3', width=4)
        draw.rounded_rectangle((31, 22, 51, 52), radius=4, outline='#edf4f3', width=4)
        self.icon = pystray.Icon('ClipBridge', image, 'ClipBridge · phone ↔ PC', pystray.Menu(
            pystray.MenuItem('Open ClipBridge', lambda *_: self.actions.put('open'), default=True),
            pystray.MenuItem('Pause / resume sync', lambda *_: self.actions.put('toggle')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit ClipBridge', lambda *_: self.actions.put('quit'))))
        threading.Thread(target=self.icon.run, daemon=True, name='ClipBridgeTray').start()

    def stop(self):
        self.icon.stop()
