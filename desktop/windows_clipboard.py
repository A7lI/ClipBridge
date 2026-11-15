"""Windows clipboard ownership and image interoperability, without a polling helper process."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import io
import json
import struct
import time
from contextlib import contextmanager

from PIL import Image, ImageGrab
from protocol import b64, unb64, MAX_IMAGE
from file_transfer import pack_files, save_files

user = C.WinDLL('user32', use_last_error=True)
kernel = C.WinDLL('kernel32', use_last_error=True)
user.GetClipboardData.argtypes = [W.UINT]
user.GetClipboardData.restype = W.HANDLE
user.SetClipboardData.argtypes = [W.UINT, W.HANDLE]
user.SetClipboardData.restype = W.HANDLE
user.OpenClipboard.argtypes = [W.HWND]
user.OpenClipboard.restype = W.BOOL
user.IsClipboardFormatAvailable.argtypes = [W.UINT]
user.IsClipboardFormatAvailable.restype = W.BOOL
user.RegisterClipboardFormatW.argtypes = [W.LPCWSTR]
user.RegisterClipboardFormatW.restype = W.UINT
kernel.GlobalAlloc.argtypes = [W.UINT, C.c_size_t]
kernel.GlobalAlloc.restype = W.HGLOBAL
kernel.GlobalLock.argtypes = [W.HGLOBAL]
kernel.GlobalLock.restype = C.c_void_p
kernel.GlobalUnlock.argtypes = [W.HGLOBAL]
kernel.GlobalFree.argtypes = [W.HGLOBAL]
kernel.GlobalSize.argtypes = [W.HGLOBAL]
kernel.GlobalSize.restype = C.c_size_t
shell = C.WinDLL('shell32', use_last_error=True)
shell.DragQueryFileW.argtypes = [W.HANDLE, W.UINT, W.LPWSTR, W.UINT]
shell.DragQueryFileW.restype = W.UINT
PNG_FORMAT = user.RegisterClipboardFormatW('PNG')


def signature(item):
    if item['kind'] == 'files':
        raw = json.dumps(item['files'], sort_keys=True, ensure_ascii=False).encode('utf-8')
    else:
        raw = item['text'].encode('utf-8') if item['kind'] == 'text' else unb64(item['data'])
    return hashlib.sha256(item['kind'].encode()+raw).hexdigest()


@contextmanager
def opened(owner=None):
    for _ in range(12):
        if user.OpenClipboard(owner):
            break
        time.sleep(.025)
    else:
        raise OSError('Clipboard busy; copy again in a moment')
    try:
        yield
    finally:
        user.CloseClipboard()


def put(format_id, data):
    handle = kernel.GlobalAlloc(0x0042, len(data))
    if not handle:
        raise MemoryError('Clipboard allocation failed')
    pointer = kernel.GlobalLock(handle)
    if not pointer:
        kernel.GlobalFree(handle)
        raise OSError('Clipboard memory unavailable')
    C.memmove(pointer, data, len(data))
    kernel.GlobalUnlock(handle)
    if not user.SetClipboardData(format_id, handle):
        kernel.GlobalFree(handle)
        raise OSError('Could not write clipboard')


def read_unicode_text():
    """Read CF_UNICODETEXT while the caller holds the clipboard open."""
    handle = user.GetClipboardData(13)
    size = kernel.GlobalSize(handle)
    if size > 2 * 1024 * 1024 + 2:
        raise ValueError('Text exceeds 1 MB')
    pointer = kernel.GlobalLock(handle)
    if not pointer:
        return None
    try:
        return C.string_at(pointer, size).decode('utf-16-le').split('\x00', 1)[0]
    finally:
        kernel.GlobalUnlock(handle)


class WindowsClipboard:
    def __init__(self, hwnd=None):
        self.hwnd = hwnd

    def sequence(self):
        return user.GetClipboardSequenceNumber()

    def read_text(self):
        with opened(self.hwnd):
            if user.IsClipboardFormatAvailable(13):
                return read_unicode_text()
        return None

    def read_paths(self):
        with opened(self.hwnd):
            if not user.IsClipboardFormatAvailable(15):
                return []
            handle = user.GetClipboardData(15)
            count = shell.DragQueryFileW(handle, 0xffffffff, None, 0)
            if not 1 <= count <= 20:
                raise ValueError('Copy between 1 and 20 files')
            paths = []
            for index in range(count):
                length = shell.DragQueryFileW(handle, index, None, 0)
                name = C.create_unicode_buffer(length + 1)
                shell.DragQueryFileW(handle, index, name, length + 1)
                paths.append(name.value)
            return paths

    def write_paths(self, paths, png=None):
        formats = [(15, struct.pack('<IiiII', 20, 0, 0, 0, 1) + ('\x00'.join(paths)+'\x00\x00').encode('utf-16-le'))]
        if png:
            with Image.open(io.BytesIO(png)) as image:
                bitmap = io.BytesIO()
                image.convert('RGB').save(bitmap, format='BMP')
            formats.extend([(PNG_FORMAT, png), (8, bitmap.getvalue()[14:])])
        with opened(self.hwnd):
            if not user.EmptyClipboard():
                raise OSError('Could not take ownership of clipboard')
            for format_id, data in formats:
                put(format_id, data)

    def read(self):
        with opened(self.hwnd):
            if user.IsClipboardFormatAvailable(15):
                handle = user.GetClipboardData(15)
                count = shell.DragQueryFileW(handle, 0xffffffff, None, 0)
                if not 1 <= count <= 20:
                    raise ValueError('Copy between 1 and 20 files')
                paths = []
                for index in range(count):
                    length = shell.DragQueryFileW(handle, index, None, 0)
                    name = C.create_unicode_buffer(length + 1)
                    shell.DragQueryFileW(handle, index, name, length + 1)
                    paths.append(name.value)
                return pack_files(paths)
            if user.IsClipboardFormatAvailable(PNG_FORMAT):
                handle = user.GetClipboardData(PNG_FORMAT)
                size = kernel.GlobalSize(handle)
                if 0 < size <= MAX_IMAGE:
                    pointer = kernel.GlobalLock(handle)
                    try:
                        data = C.string_at(pointer, size)
                    finally:
                        kernel.GlobalUnlock(handle)
                    return {'kind': 'image', 'data': b64(data)}
            is_image = user.IsClipboardFormatAvailable(8) or user.IsClipboardFormatAvailable(17)
            if not is_image and user.IsClipboardFormatAvailable(13):
                text = read_unicode_text()
                return {'kind': 'text', 'text': text} if text is not None else None
        if is_image:
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                if image.width * image.height > 24_000_000:
                    raise ValueError('Image exceeds 24 megapixels')
                out = io.BytesIO()
                image.convert('RGBA').save(out, format='PNG')
                if out.tell() > MAX_IMAGE:
                    raise ValueError('Image exceeds 12 MB')
                return {'kind': 'image', 'data': b64(out.getvalue())}
        return None

    def write(self, item):
        if item['kind'] == 'text':
            formats = [(13, (item['text']+'\x00').encode('utf-16-le'))]
        elif item['kind'] == 'files':
            paths = save_files(item)
            # DROPFILES structure followed by a double-null UTF-16 path list.
            formats = [(15, struct.pack('<IiiII', 20, 0, 0, 0, 1) + ('\x00'.join(paths)+'\x00\x00').encode('utf-16-le'))]
        else:
            png = unb64(item['data'])
            with Image.open(io.BytesIO(png)) as im:
                buf = io.BytesIO()
                im.convert('RGB').save(buf, format='BMP')
            formats = [(PNG_FORMAT, png), (8, buf.getvalue()[14:])]
        with opened(self.hwnd):
            if not user.EmptyClipboard():
                raise OSError('Could not take ownership of clipboard')
            for fmt, data in formats:
                put(fmt, data)
