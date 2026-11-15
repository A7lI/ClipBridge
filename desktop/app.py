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
BG, PANEL, FG, MUTED, ACCENT = '#10191f', '#1b282f', '#edf4f3', '#a9bcc0', '#8ee3c3'


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
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else '#2c3e46',
                         fg=BG if primary else FG, activebackground='#b3f3dc', activeforeground=BG,
                         font=('Segoe UI Semibold', 11), relief='flat', padx=18, pady=11, cursor='hand2')

    def render(self):
        r = self.root
        r.title('ClipBridge · Phone ↔ PC')
        r.geometry('720x790')
        r.minsize(660, 740)
        r.configure(bg=BG)
        canvas = tk.Canvas(r, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(r, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        r = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=r, anchor='nw')
        r.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        self.root.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-int(e.delta/120), 'units'))
        header = tk.Frame(r, bg=BG)
        header.pack(fill='x', padx=28, pady=(23, 16))
        self.label(header, 'ClipBridge', 27).pack(anchor='w')
        self.label(header, 'Copy here. Paste there.', 13, ACCENT).pack(anchor='w', pady=(3, 0))
        self.connection = self.label(header, 'Waiting for your phone', 10, MUTED)
        self.connection.pack(anchor='w', pady=(12, 0))

        pair = tk.Frame(r, bg=PANEL, padx=22, pady=16)
        pair.pack(fill='x', padx=28)
        self.label(pair, '01   CONNECT YOUR PHONE', 11, ACCENT).pack(anchor='w')
        body = tk.Frame(pair, bg=PANEL)
        body.pack(fill='x', pady=(14, 0))
        self.qr = self.label(body, '')
        self.qr.pack(side='left', padx=(0, 22))
        side = tk.Frame(body, bg=PANEL)
        side.pack(side='left', fill='both', expand=True)
        self.label(side, 'Same Wi-Fi. No account.', 12).pack(anchor='w')
        self.label(side, 'In the phone app, tap Scan QR code.\nScan this code to pair automatically.\nOther QR codes copy their text to this PC.', 10, MUTED,
                   justify='left').pack(anchor='w', pady=(8, 13))
        self.label(side, 'PC Wi-Fi address', 10, MUTED).pack(anchor='w')
        self.host = ttk.Combobox(side, values=addresses(), font=('Segoe UI', 11))
        self.host.set(addresses()[0])
        self.host.pack(fill='x', pady=(5, 0))
        self.host.bind('<<ComboboxSelected>>', lambda _: self.update_pair())
        self.host.bind('<FocusOut>', lambda _: self.update_pair())
        self.pair_text = tk.Entry(pair, bg=BG, fg=FG, insertbackground=FG, relief='flat', font=('Consolas', 9))
        self.pair_text.pack(fill='x', pady=(14, 8), ipady=8)
        self.label(pair, 'Keep this pairing link private: it authorizes access to your clipboard.', 9, MUTED).pack(anchor='w')
        self.button(pair, 'Reset pairing', self.reset_pair).pack(anchor='w', pady=(8, 0))
        self.button(pair, 'iPhone web pairing…', self.open_web_pairing).pack(anchor='w', pady=(8, 0))
        self.update_pair()

        sync = tk.Frame(r, bg=PANEL, padx=22, pady=17)
        sync.pack(fill='x', padx=28, pady=14)
        self.label(sync, '02   AUTOMATIC CLIPBOARD', 11, ACCENT).pack(anchor='w')
        self.label(sync, 'Text + photos + files, in both directions', 13).pack(anchor='w', pady=(9, 4))
        self.activity = self.label(sync, 'Paused · turn on when you are ready', 10, MUTED)
        self.activity.pack(anchor='w')
        self.toggle = self.button(sync, 'Start syncing' if self.state.paused else 'Pause syncing', self.toggle_sync, True)
        self.toggle.pack(anchor='w', pady=(13, 0))
        actions = tk.Frame(sync, bg=PANEL)
        actions.pack(fill='x', pady=(10, 0))
        self.button(actions, 'Send files…', self.send_files).pack(side='left')
        self.button(actions, 'Received files', self.open_received).pack(side='left', padx=(8, 0))
        self.label(sync, 'Up to 20 files / 300 MB total. Copy files in Explorer to sync,\nor use Send files. Phone files arrive ready to paste with Ctrl+V.',
                   10, MUTED, justify='left').pack(anchor='w', pady=(8, 0))
        self.auto_sync_var = tk.BooleanVar(value=self.auto_sync)
        tk.Checkbutton(sync, text='Start syncing automatically when ClipBridge opens', variable=self.auto_sync_var,
                       command=self.save_auto_sync, bg=PANEL, fg=FG, activebackground=PANEL,
                       activeforeground=FG, selectcolor=BG, font=('Segoe UI', 10),
                       highlightthickness=0).pack(anchor='w', pady=(10, 0))

        voice = tk.Frame(r, bg=PANEL, padx=22, pady=16)
        voice.pack(fill='x', padx=28)
        self.label(voice, '03   VOICE TYPING', 11, ACCENT).pack(anchor='w')
        self.voice_status = self.label(voice, '', 11)
        self.voice_status.pack(anchor='w', pady=(9, 4))
        self.label(voice, 'Tap the microphone on your phone keyboard.\nCanary transcribes on this PC (English). No Cipher or Handy needed.',
                   10, MUTED, justify='left').pack(anchor='w')
        self.label(voice, 'One-time download: 218 MB from Hugging Face. Saved automatically.\nAfter setup, voice typing works offline over your local Wi-Fi.',
                   10, MUTED, justify='left').pack(anchor='w', pady=(7, 0))
        self.download_button = self.button(voice, 'Download Canary model', self.download_voice, primary=True)
        self.download_button.pack(anchor='w', pady=(11, 0))
        self.voice_progress = ttk.Progressbar(voice, maximum=100, mode='determinate')
        self.voice_progress.pack(fill='x', pady=(9, 0))
        self.model_path = self.label(voice, '', 9, MUTED, wraplength=580, justify='left')
        self.model_path.pack(anchor='w', pady=(5, 2))
        self.choose_model_button = self.button(voice, 'Use an existing model…', self.choose_model)
        self.choose_model_button.pack(anchor='w', pady=(7, 0))
        self.notice = self.label(r, '', 9, '#ffcaa6', wraplength=655, justify='left')
        self.notice.pack(fill='x', padx=28, pady=10)
        self.label(r, 'Leave this window running. Closing it stops clipboard sync and voice typing.', 9, MUTED).pack(pady=(0, 15))

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
        self.label(window, 'Connect your iPhone and PC to the same Wi-Fi.', 10, MUTED).pack(anchor='w', pady=(6, 10))
        self.web_status = self.label(window, '', 10, ACCENT)
        self.web_status.pack(anchor='w', pady=(0, 8))
        if self.web:
            self.web_qr = self.pairing_image(self.web.link)
            tk.Label(window, image=self.web_qr, bg=BG).pack(pady=8)
            self.label(window, 'Scan this QR with the iPhone camera. Keep it private.', 10, MUTED).pack(anchor='w')
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
        self.connection.configure(text='● Phone connected · encrypted Wi-Fi link' if connected else '○ Waiting for your phone · same Wi-Fi required',
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
