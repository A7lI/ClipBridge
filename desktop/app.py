"""ClipBridge: clipboard sync and self-contained local voice typing."""
import base64
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
import queue
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlencode

from PIL import Image, ImageTk
import qrcode

from protocol import Protocol, b64, validate_clip
from server import State, Server
from speech import LocalSpeech, DEFAULT_MODEL, validate_model
from voice_model import download_model, DownloadCancelled, MODEL_SIZE
from windows_clipboard import WindowsClipboard, signature
from discovery import Discovery
from file_transfer import pack_files, RECEIVED
from local_sender import LocalSender, send_selection, launch_companion
from tray import Tray
from web_bridge import WebBridge

APPDATA = Path(os.environ.get('LOCALAPPDATA', '.')) / 'ClipBridge'
CONFIG = APPDATA / 'settings.json'
WEB_APP_URL = os.environ.get('CLIPBRIDGE_WEB_URL', 'https://www.a7li.dev/apps/clipbridge/web/')
BG, PANEL, FG, MUTED, ACCENT = '#080911', '#141420', '#f5f3fa', '#aaa6bf', '#c7b5ff'


class Blob(C.Structure):
    _fields_ = [('cbData', W.DWORD), ('pbData', C.POINTER(C.c_ubyte))]


def protect(raw, decrypt=False):
    """Keep the pairing secret protected by this Windows user's DPAPI key."""
    source = C.create_string_buffer(raw)
    inp = Blob(len(raw), C.cast(source, C.POINTER(C.c_ubyte)))
    out = Blob()
    crypt = C.WinDLL('crypt32', use_last_error=True)
    if decrypt:
        success = crypt.CryptUnprotectData(C.byref(inp), None, None, None, None, 1, C.byref(out))
    else:
        success = crypt.CryptProtectData(C.byref(inp), 'ClipBridge', None, None, None, 1, C.byref(out))
    if not success:
        raise OSError('Windows could not protect pairing settings')
    try:
        return C.string_at(out.pbData, out.cbData)
    finally:
        local = C.WinDLL('kernel32')
        local.LocalFree.argtypes = [C.c_void_p]
        local.LocalFree(out.pbData)


def addresses():
    candidates = []
    try:
        # UDP connect selects an interface without sending a packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 9))
            candidates.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        candidates.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return list(dict.fromkeys(x for x in candidates if not x.startswith('127.'))) or ['127.0.0.1']


class App:
    def __init__(self, root):
        self.root = root
        self.closed = False
        self.voice_download = None
        self.voice_events = queue.Queue()
        self.voice_download_message = ''
        self.settings = {}
        try:
            self.settings = json.loads(CONFIG.read_text('utf-8'))
            self.key = protect(base64.b64decode(self.settings['key']), decrypt=True)
            if len(self.key) != 32:
                raise ValueError('Invalid saved key')
        except (OSError, ValueError, KeyError):
            self.key = secrets.token_bytes(32)
        try:
            self.web_key = protect(base64.b64decode(self.settings['web_key']), decrypt=True)
            if len(self.web_key) != 32:
                raise ValueError('Invalid web pairing key')
        except (OSError, ValueError, KeyError):
            self.web_key = secrets.token_bytes(32)
        self.web = None
        self.web_window = None
        self.web_enabled = bool(self.settings.get('web_enabled', False)) and '--preview' not in sys.argv
        self.speech = LocalSpeech(self.settings.get('voice_model', str(DEFAULT_MODEL)))
        self.auto_sync = bool(self.settings.get('auto_sync', True))
        self.clipboard = WindowsClipboard(root.winfo_id())
        self.last_seq = self.clipboard.sequence()
        self.last_sig = None
        self.state = State(self.key, self.receive, self.speech, read_text=self.clipboard.read_text)
        self.state.pause(not self.auto_sync)
        self.state.last_event = 'Sync ready · waiting for your paired phone'
        self.server = Server(('127.0.0.1', 0) if '--preview' in sys.argv else ('0.0.0.0', 48721), self.state)
        self.port = self.server.server_port
        self.discovery = None
        if '--preview' not in sys.argv:
            try:
                self.discovery = Discovery(self.key, self.port)
            except OSError:
                self.state.last_error = 'Automatic PC discovery is unavailable; the saved Wi-Fi address still works.'
        threading.Thread(target=self.server.serve_forever, daemon=True, name='ClipBridgeLAN').start()
        self.local_sender = None
        if '--preview' not in sys.argv:
            self.local_sender = LocalSender(APPDATA, self.key, self.state.send_files)
        self.render()
        self.tray = Tray()
        if self.web_enabled:
            self.start_web()
        self.save()
        threading.Thread(target=self.watch, daemon=True, name='ClipBridgeClipboard').start()
        self.tick()
        root.protocol('WM_DELETE_WINDOW', root.withdraw)
        if '--tray' in sys.argv:
            root.withdraw()

    def save(self):
        APPDATA.mkdir(parents=True, exist_ok=True)
        self.settings.pop('cipher_source', None)
        self.settings.update(key=b64(protect(self.key)), voice_model=str(self.speech.model), auto_sync=self.auto_sync)
        temporary = CONFIG.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.settings, indent=2), encoding='utf-8')
        temporary.replace(CONFIG)

    def label(self, parent, text, size=11, color=FG, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                        font=('Segoe UI', size), **kwargs)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else '#282035',
                         fg=BG if primary else FG, activebackground='#ddd0ff', activeforeground=BG,
                         font=('Segoe UI Semibold', 10), relief='flat', padx=15, pady=9, highlightthickness=1, highlightbackground='#443653', highlightcolor=ACCENT, cursor='hand2')

    def render(self):
        root = self.root
        root.title('ClipBridge')
        root.geometry('710x650')
        root.minsize(640, 600)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 12))
        style.configure('TNotebook.Tab', background='#171521', foreground=MUTED, padding=(22, 10), font=('Segoe UI Semibold', 10), borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', '#30243f')], foreground=[('selected', ACCENT)])
        style.layout('Plain.TNotebook.Tab', [])
        style.configure('Plain.TNotebook', background=BG, borderwidth=0, lightcolor=BG, darkcolor=BG, bordercolor=BG)
        style.configure('Vertical.TScrollbar', background='#30243f', troughcolor=BG, arrowcolor=MUTED, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure('TProgressbar', background=ACCENT, troughcolor='#211c30', borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure('TCombobox', fieldbackground=BG, foreground=FG, background=PANEL, arrowcolor=ACCENT)
        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=22, pady=(18, 12))
        logo_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets' / 'clipbridge.png'
        if logo_path.is_file():
            self.logo_image = ImageTk.PhotoImage(Image.open(logo_path).resize((36, 36), Image.Resampling.LANCZOS))
            tk.Label(header, image=self.logo_image, bg=BG).pack(side='left', padx=(0, 9))
            root.iconphoto(True, self.logo_image)
        self.label(header, 'ClipBridge.', 22).pack(side='left')
        self.label(header, '0.7.0', 10, MUTED).pack(side='right')
        self.connection = self.label(root, 'Connect your phone to get started', 10, MUTED)
        self.connection.pack(anchor='w', padx=24, pady=(0, 12))
        navigation = tk.Frame(root, bg='#12111d', padx=4, pady=4)
        navigation.pack(fill='x', padx=22, pady=(0, 12))
        self.nav_buttons = []
        self.pages = ttk.Notebook(root, style='Plain.TNotebook')
        for index, title in enumerate(('Share', 'Connect', 'Settings')):
            button = self.button(navigation, title, lambda index=index: self.show_page(index))
            button.pack(side='left', fill='x', expand=True, padx=2)
            self.nav_buttons.append(button)
        self.pages.pack(fill='both', expand=True, padx=22)
        self.page_canvases = {}
        def page(title):
            frame = tk.Frame(self.pages, bg=BG)
            self.pages.add(frame, text=title)
            canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
            scrollbar.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            body = tk.Frame(canvas, bg=BG)
            window = canvas.create_window((0, 0), window=body, anchor='nw')
            def layout(event=None):
                canvas.configure(scrollregion=canvas.bbox('all'))
                if body.winfo_reqheight() > canvas.winfo_height() + 2:
                    if not scrollbar.winfo_manager(): scrollbar.pack(side='right', fill='y')
                else:
                    scrollbar.pack_forget()
            body.bind('<Configure>', layout)
            canvas.bind('<Configure>', lambda event: (canvas.itemconfigure(window, width=event.width), layout()))
            self.page_canvases[str(frame)] = canvas
            return body
        def card(parent, title):
            frame = tk.Frame(parent, bg=PANEL, padx=17, pady=14, highlightbackground='#30293f', highlightthickness=1)
            frame.pack(fill='x', pady=(0, 12), padx=(0, 6))
            self.label(frame, title, 15).pack(anchor='w', pady=(0, 8))
            return frame
        share = page('Share')
        connect = page('Connect')
        settings = page('Settings')
        root.bind('<MouseWheel>', lambda event: self.page_canvases[self.pages.select()].yview_scroll(-int(event.delta/120), 'units'))
        clipboard = card(share, 'Clipboard')
        self.activity = self.label(clipboard, 'Ready to share', 11, MUTED, wraplength=550, justify='left')
        self.activity.pack(anchor='w', pady=(0, 7))
        self.toggle = self.button(clipboard, 'Start syncing' if self.state.paused else 'Pause syncing', self.toggle_sync, True)
        self.toggle.pack(anchor='w')
        transfer = card(share, 'Send & receive')
        row = tk.Frame(transfer, bg=PANEL)
        row.pack(fill='x')
        self.button(row, 'Send to Android…', self.send_files, True).pack(side='left', padx=(0, 8))
        self.button(row, 'Send to iPhone…', self.send_web_files).pack(side='left')
        self.button(row, 'Received files', self.open_received).pack(side='left', padx=(8, 0))
        self.label(transfer, '20 files · 300 MB total. Copy received files with Ctrl+V.', 10, MUTED).pack(anchor='w', pady=(10, 0))
        pair = card(connect, 'Connect Android')
        body = tk.Frame(pair, bg=PANEL)
        body.pack(fill='x')
        self.qr = self.label(body, '')
        self.qr.pack(side='left', padx=(0, 18))
        side = tk.Frame(body, bg=PANEL)
        side.pack(side='left', fill='both', expand=True)
        self.label(side, 'Same Wi-Fi.', 12, ACCENT).pack(anchor='w', pady=(9, 5))
        self.label(side, 'In ClipBridge on your phone,\nopen Connect and scan this QR.', 10, MUTED, justify='left').pack(anchor='w')
        advanced = tk.Frame(pair, bg=PANEL)
        def toggle_advanced():
            if advanced.winfo_manager(): advanced.pack_forget()
            else: advanced.pack(fill='x', pady=(10, 0))
        self.button(side, 'Link & Wi-Fi options', toggle_advanced).pack(anchor='w', pady=(12, 0))
        self.label(advanced, 'PC address', 10, MUTED).pack(anchor='w')
        self.host = ttk.Combobox(advanced, values=addresses(), font=('Segoe UI', 10))
        self.host.set(addresses()[0])
        self.host.pack(fill='x', pady=(4, 8))
        self.host.bind('<<ComboboxSelected>>', lambda _: self.update_pair())
        self.host.bind('<FocusOut>', lambda _: self.update_pair())
        self.pair_text = tk.Entry(advanced, bg=BG, fg=FG, insertbackground=FG, relief='flat', font=('Consolas', 9))
        self.pair_text.pack(fill='x', ipady=7)
        self.label(advanced, 'Private link. Share only with your phone.', 9, MUTED).pack(anchor='w', pady=(5, 0))
        self.button(advanced, 'Reset pairing', self.reset_pair).pack(anchor='w', pady=(8, 0))
        self.update_pair()
        iphone = card(connect, 'Connect iPhone')
        self.label(iphone, 'Pair the web app on the same Wi-Fi.', 10, MUTED).pack(anchor='w')
        self.button(iphone, 'iPhone web pairing…', self.open_web_pairing, True).pack(anchor='w', pady=(9, 0))
        voice = card(settings, 'Offline voice typing')
        self.voice_status = self.label(voice, '', 10, MUTED, wraplength=550, justify='left')
        self.voice_status.pack(anchor='w')
        self.label(voice, 'English · Canary model · 218 MB one-time download', 10, MUTED).pack(anchor='w', pady=(5, 8))
        row = tk.Frame(voice, bg=PANEL)
        row.pack(fill='x')
        self.download_button = self.button(row, 'Download Canary model', self.download_voice, True)
        self.download_button.pack(side='left', padx=(0, 8))
        self.choose_model_button = self.button(row, 'Use existing model…', self.choose_model)
        self.choose_model_button.pack(side='left')
        self.voice_progress = ttk.Progressbar(voice, maximum=100, mode='determinate')
        # Shown only during a model download.
        self.model_path = self.label(voice, '', 9, MUTED, wraplength=550, justify='left')
        self.model_path.pack(anchor='w')
        preferences = card(settings, 'Preferences')
        self.auto_sync_var = tk.BooleanVar(value=self.auto_sync)
        tk.Checkbutton(preferences, text='Start syncing when ClipBridge opens', variable=self.auto_sync_var, command=self.save_auto_sync, bg=PANEL, fg=FG, activebackground=PANEL, activeforeground=FG, selectcolor=BG, font=('Segoe UI', 10), highlightthickness=0).pack(anchor='w')
        self.button(preferences, 'Help & privacy', lambda: messagebox.showinfo('Quick help', 'PC sharing needs the same Wi-Fi.\n\nKeep pairing links private. Pause syncing to stop sharing your clipboard.\n\nVoice typing uses the Canary model on this PC.\n\nClosing the window keeps ClipBridge in the tray. Choose Quit there to stop it.')).pack(anchor='w', pady=(9, 0))
        self.notice = self.label(root, '', 9, '#ffc5ba', wraplength=640, justify='left')
        self.notice.pack(fill='x', padx=24, pady=(5, 0))
        self.label(root, 'Runs in your system tray.', 9, MUTED).pack(anchor='w', padx=24, pady=(4, 12))
        self.show_page(0)

    def show_page(self, index):
        self.pages.select(index)
        for item, button in enumerate(self.nav_buttons):
            button.configure(bg='#30243f' if item == index else '#12111d', fg=ACCENT if item == index else MUTED)

    def update_pair(self):
        host = self.host.get().strip()
        link = f'clipbridge://{host}:{self.port}/pair?' + urlencode({'key': base64.urlsafe_b64encode(self.key).decode().rstrip('=')})
        self.pair_text.delete(0, 'end')
        self.pair_text.insert(0, link)
        self.qr_image = self.pairing_image(link, size=176)
        self.qr.configure(image=self.qr_image)

    def pairing_image(self, link, size=None):
        qr = qrcode.QRCode(border=4, box_size=4)
        qr.add_data(link)
        qr.make(fit=True)
        image = qr.make_image(fill_color=BG, back_color='white').convert('RGB')
        if size:
            image = image.resize((size, size), Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(image)

    def start_web(self):
        try:
            self.web = WebBridge(WEB_APP_URL, self.web_key, self.state, self.clipboard)
        except ValueError as error:
            self.web_enabled = False
            self.state.last_error = str(error)

    def stop_web(self):
        if self.web:
            self.web.close()
            self.web = None

    def open_web_pairing(self):
        if self.web_window and self.web_window.winfo_exists():
            self.web_window.lift()
            return
        self.web_window = tk.Toplevel(self.root)
        self.web_window.title('ClipBridge · iPhone web pairing')
        self.web_window.configure(bg=BG, padx=24, pady=20)
        self.render_web_pairing()

    def render_web_pairing(self):
        window = self.web_window
        for widget in window.winfo_children():
            widget.destroy()
        self.label(window, 'iPhone web pairing', 17).pack(anchor='w')
        self.label(window, 'Same Wi-Fi. Open ClipBridge in Safari.', 10, MUTED).pack(anchor='w', pady=(6, 10))
        self.web_status = self.label(window, '', 10, ACCENT, wraplength=365, justify='left')
        self.web_status.pack(anchor='w', pady=(0, 8))
        if self.web:
            self.web_qr = self.pairing_image(self.web.link, size=200)
            tk.Label(window, image=self.web_qr, bg=BG).pack(pady=8)
            self.label(window, 'Scan from the iPhone web app. Keep this code private.', 10, MUTED).pack(anchor='w')
            link = tk.StringVar(window, value=self.web.link)
            entry = tk.Entry(window, textvariable=link, state='readonly', width=52)
            entry.pack(fill='x', pady=(8, 3), ipady=4)
            self.button(window, 'Reset web pairing', self.reset_web_pairing).pack(anchor='w', pady=(8, 0))
            self.button(window, 'Send files to iPhone…', self.send_web_files).pack(anchor='w', pady=(8, 0))
            self.button(window, 'Received files', self.open_received).pack(anchor='w', pady=(8, 0))
        self.button(window, 'Disable web pairing' if self.web else 'Enable web pairing', self.toggle_web).pack(anchor='w', pady=(8, 0))
        self.update_web_status()

    def update_web_status(self):
        if self.web_window and self.web_window.winfo_exists():
            self.web_status.configure(text=self.web.status if self.web else 'Web pairing is off.')

    def send_web_files(self):
        if not self.web:
            self.open_web_pairing()
            return
        paths = filedialog.askopenfilenames(title='Send files to iPhone (300 MB total)')
        if paths and self.web:
            try:
                self.web.offer_paths(paths)
                self.update_web_status()
            except (ValueError, OSError) as error:
                messagebox.showerror('Send files', str(error))

    def toggle_web(self):
        self.web_enabled = not self.web_enabled
        if self.web_enabled:
            self.start_web()
        else:
            self.stop_web()
        self.save_web_pairing()
        self.render_web_pairing()

    def reset_web_pairing(self):
        self.stop_web()
        self.web_key = secrets.token_bytes(32)
        if self.web_enabled:
            self.start_web()
        self.save_web_pairing()
        if self.web_window and self.web_window.winfo_exists():
            self.render_web_pairing()

    def save_web_pairing(self):
        self.settings.update(web_key=b64(protect(self.web_key)), web_enabled=self.web_enabled)
        self.save()

    def toggle_sync(self):
        with self.state.changed:
            # Starting sync deliberately ignores the existing clipboard.
            self.last_seq = self.clipboard.sequence()
            self.last_sig = None
            self.state.pause(not self.state.paused)
        self.toggle.configure(text='Start syncing' if self.state.paused else 'Pause syncing')

    def save_auto_sync(self):
        self.auto_sync = bool(self.auto_sync_var.get())
        self.save()

    def send_files(self):
        if self.state.paused or time.monotonic() - self.state.last_seen > 35:
            messagebox.showinfo('Send files', 'Connect your phone and enable syncing first.')
            return
        paths = filedialog.askopenfilenames(title='Send files to your phone (300 MB total)')
        if not paths:
            return
        def send():
            try:
                self.state.send_files(pack_files(paths))
            except Exception as exc:
                self.state.last_error = str(exc)[:200]
        threading.Thread(target=send, daemon=True, name='ClipBridgeFiles').start()

    def open_received(self):
        RECEIVED.mkdir(parents=True, exist_ok=True)
        os.startfile(str(RECEIVED))

    def reset_pair(self):
        if not messagebox.askyesno('Reset pairing', 'Disconnect paired devices and generate a new pairing link?'):
            return
        with self.state.changed:
            self.key = secrets.token_bytes(32)
            self.state.protocol = Protocol(self.key)
            if self.local_sender:
                self.local_sender.close()
                self.local_sender = LocalSender(APPDATA, self.key, self.state.send_files)
            if self.discovery:
                self.discovery.key = self.key
            self.state.pause(True)
            self.state.last_seen = 0
            self.state.device = ''
            self.last_seq = self.clipboard.sequence()
            self.last_sig = None
        self.toggle.configure(text='Start syncing')
        self.reset_web_pairing()
        self.update_pair()

    def choose_model(self):
        selected = filedialog.askopenfilename(
            title='Choose your Canary voice model',
            initialdir=str(self.speech.model.parent) if self.speech.model.parent.is_dir() else None,
            filetypes=[('GGUF voice models', '*.gguf'), ('All files', '*.*')],
        )
        if selected:
            try:
                model = validate_model(selected)
            except (OSError, ValueError) as exc:
                messagebox.showerror('Voice model', str(exc))
                return
            self.speech.close()
            self.speech = LocalSpeech(model)
            self.state.speech = self.speech
            self.save()
            self.update_voice_status()

    def download_voice(self):
        if self.voice_download is not None:
            self.voice_download.set()
            self.download_button.configure(state='disabled', text='Cancelling…')
            return
        cancel = self.voice_download = threading.Event()
        self.voice_download_message = 'Connecting to Hugging Face…'
        self.download_button.configure(text='Cancel download')
        self.choose_model_button.configure(state='disabled')
        self.voice_progress.configure(value=0)
        self.voice_progress.pack(fill='x', pady=(10, 3), before=self.model_path)

        def download():
            last_update = 0
            def progress(received, total):
                nonlocal last_update
                now = time.monotonic()
                if now-last_update >= .15 or received == total:
                    self.voice_events.put(('progress', received, total))
                    last_update = now
            try:
                path = download_model(progress=progress, cancel=cancel)
                self.voice_events.put(('complete', path))
            except DownloadCancelled:
                self.voice_events.put(('cancelled',))
            except Exception as exc:
                self.voice_events.put(('error', str(exc)[:230]))
        threading.Thread(target=download, daemon=True, name='ClipBridgeCanaryDownload').start()

    def check_voice_download(self):
        while True:
            try:
                event = self.voice_events.get_nowait()
            except queue.Empty:
                break
            if event[0] == 'progress':
                received, total = event[1:]
                percent = received*100/total
                self.voice_download_message = f'Downloading Canary · {percent:.0f}% · {received/1_000_000:.1f} / {total/1_000_000:.1f} MB'
                self.voice_progress.configure(value=percent)
                continue
            self.voice_download = None
            self.voice_progress.pack_forget()
            self.download_button.configure(text='Download Canary model', state='normal')
            self.choose_model_button.configure(state='normal')
            if event[0] == 'complete':
                self.speech.close()
                self.speech = LocalSpeech(event[1])
                self.state.speech = self.speech
                self.save()
                self.voice_download_message = ''
                self.voice_progress.configure(value=100)
            elif event[0] == 'cancelled':
                self.voice_download_message = 'Download cancelled. Click Download Canary model to retry.'
                self.voice_progress.configure(value=0)
            else:
                self.voice_download_message = 'Download failed. '+event[1]+' Click Download Canary model to retry.'
                self.voice_progress.configure(value=0)

    def update_voice_status(self):
        problem = self.speech.problem()
        self.voice_status.configure(text=getattr(self, 'voice_download_message', '') or problem or 'Ready · local voice typing',
                                    fg='#ffcaa6' if problem else FG)
        self.model_path.configure(text=str(self.speech.model) if self.speech.model.is_file() else '')

    def receive(self, item):
        self.clipboard.write(item)
        self.last_seq = self.clipboard.sequence()
        self.last_sig = signature(item)

    def watch(self):
        while not self.closed:
            try:
                with self.state.changed:
                    seq = self.clipboard.sequence()
                    if seq != self.last_seq:
                        if self.state.paused or time.monotonic()-self.state.last_seen > 45:
                            self.last_seq = seq
                        else:
                            # Only mark read once successful; a busy clipboard is retried.
                            item = self.clipboard.read()
                            if seq != self.clipboard.sequence():
                                continue
                            self.last_seq = seq
                            if item:
                                item = validate_clip(item)
                                sig = signature(item)
                                if sig != self.last_sig:
                                    self.last_sig = sig
                                    self.state.publish(item, 'pc')
            except Exception as exc:
                self.state.last_error = str(exc)[:200]
            time.sleep(.15)

    def tick(self):
        if self.closed:
            return
        while not self.tray.actions.empty():
            action = self.tray.actions.get_nowait()
            if action == 'quit':
                self.close()
                return
            if action == 'toggle':
                self.toggle_sync()
            if action == 'open':
                self.root.deiconify()
                self.root.lift()
        self.check_voice_download()
        self.update_web_status()
        connected = time.monotonic()-self.state.last_seen < 35
        self.connection.configure(text='● Phone connected' if connected else ('○ iPhone pairing ready' if self.web else '○ Ready to connect'),
                                  fg=ACCENT if connected else MUTED)
        self.activity.configure(text='Paused · clipboard is not shared' if self.state.paused else self.state.last_event)
        self.update_voice_status()
        self.notice.configure(text=self.state.last_error)
        self.root.after(700, self.tick)

    def close(self):
        self.closed = True
        self.stop_web()
        self.tray.stop()
        if self.voice_download is not None:
            self.voice_download.set()
        self.state.pause(True)
        if self.local_sender:
            self.local_sender.close()
        self.server.shutdown()
        self.server.server_close()
        if self.discovery:
            self.discovery.close()
        self.speech.close()
        self.root.destroy()


def main():
    if '--install-explorer-menu' in sys.argv or '--restore-explorer-menu' in sys.argv:
        from explorer_menu import install, uninstall
        root = tk.Tk(); root.withdraw()
        folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
        try:
            if '--restore-explorer-menu' in sys.argv:
                uninstall(APPDATA, folder/'ClipBridge-PC.exe')
                messagebox.showinfo('ClipBridge', 'The ClipBridge Explorer entry has been removed.')
            else:
                folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
                install(folder, APPDATA)
                messagebox.showinfo('ClipBridge', 'Share to My Phone (ClipBridge) has been added to Explorer. Right-click files, choose Show more options, then Send to → Share to My Phone (ClipBridge).')
        except Exception as exc:
            messagebox.showerror('ClipBridge Explorer sharing', str(exc))
        root.destroy()
        return
    if '--send-files' in sys.argv:
        paths = sys.argv[sys.argv.index('--send-files')+1:]
        if paths and paths[0] == '--':
            paths = paths[1:]
        root = tk.Tk()
        root.title('Share to My Phone · ClipBridge')
        root.geometry('460x155')
        root.configure(bg=BG)
        label = tk.Label(root, text='Sending files to your phone…', bg=BG, fg=FG,
                         font=('Segoe UI', 12), wraplength=420, justify='left')
        label.pack(fill='both', expand=True, padx=20, pady=20)
        def send():
            try:
                if not CONFIG.is_file():
                    raise ValueError('Open ClipBridge on your PC and pair your phone first.')
                settings = json.loads(CONFIG.read_text('utf-8'))
                key = protect(base64.b64decode(settings['key']), decrypt=True)
                result = send_selection(APPDATA, key, paths, launch_companion)
                root.after(0, lambda: label.configure(text=result['message'], fg=ACCENT))
                root.after(2200, root.destroy)
            except Exception as exc:
                message = str(exc)[:240]
                root.after(0, lambda: label.configure(text=message, fg='#ffcaa6'))
        threading.Thread(target=send, daemon=True, name='ClipBridgeSendSelection').start()
        root.mainloop()
        return
    if '--check' in sys.argv:
        # Packaged-runtime smoke check, without starting a network listener or
        # touching the user's clipboard. All speech input is an explicit WAV.
        import wave
        target = Path(sys.argv[sys.argv.index('--check')+1])
        try:
            from explorer_menu import REGISTRY_PATH
            assert REGISTRY_PATH.endswith('{03B9580F-25C4-44A6-B150-A7B58F06FC10}')
            key = secrets.token_bytes(32)
            assert protect(protect(key), decrypt=True) == key
            assert isinstance(WindowsClipboard().sequence(), int)
            result = {'ok': True, 'packaged': bool(getattr(sys, 'frozen', False)), 'dpapi': True, 'explorer_sender': True}
            if '--sender' in sys.argv:
                settings = json.loads(CONFIG.read_text('utf-8'))
                saved_key = protect(base64.b64decode(settings['key']), decrypt=True)
                try:
                    send_selection(APPDATA, saved_key, [str(APPDATA/'nonexistent-runtime-check.txt')])
                except Exception as exc:
                    result['sender_response'] = type(exc).__name__+': '+str(exc)
            if '--wav' in sys.argv:
                wav = Path(sys.argv[sys.argv.index('--wav')+1])
                with wave.open(str(wav), 'rb') as sample:
                    assert sample.getframerate() == 16000 and sample.getnchannels() == 1 and sample.getsampwidth() == 2
                    model = Path(sys.argv[sys.argv.index('--model')+1]) if '--model' in sys.argv else DEFAULT_MODEL
                    engine = LocalSpeech(model)
                    try:
                        transcript = engine.transcribe(sample.readframes(sample.getnframes()))
                    finally:
                        engine.close()
                result['transcript'] = transcript
                result['model'] = str(model)
        except Exception as exc:
            result = {'ok': False, 'error': repr(exc)}
        target.write_text(json.dumps(result), encoding='utf-8')
        return
    root = tk.Tk()
    try:
        App(root)
    except Exception as exc:
        root.withdraw()
        messagebox.showerror('ClipBridge', str(exc)+'\n\nIf ClipBridge is already running, use its existing window.')
        root.destroy()
        return
    root.mainloop()


if __name__ == '__main__':
    main()
