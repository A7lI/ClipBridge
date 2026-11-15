# Windows web preview third-party components

The Windows binary uses aiortc for WebRTC data channels and websockets for signaling. Python dependency licenses are in `licenses/`.

PyAV 19.0.2 is packaged from the upstream Windows x64 wheel, which dynamically links FFmpeg DLLs. The DLLs report FFmpeg 9.0.2 under LGPL version 3 or later. Download the corresponding FFmpeg source alongside this build at https://github.com/A7lI/ClipBridge/releases/tag/v0.6.4-web-preview. The exact PyAV build recipe is at https://github.com/PyAV-Org/PyAV/tree/v19.0.2 and its dependency configuration is in `scripts/build-deps` and `pyproject.toml` in that source tree.

FFmpeg configuration reported by the binary:

```
--disable-static --enable-shared --libdir=/c/cibw/vendor/lib --prefix=/c/cibw/vendor --disable-programs --disable-doc --disable-libxml2 --disable-lzma --disable-libtheora --disable-libfreetype --disable-libfontconfig --disable-libbluray --disable-libopenjpeg --enable-mediafoundation --enable-version3 --disable-alsa --disable-gnutls --enable-libdav1d --enable-libmp3lame --enable-libopus --enable-libsvtav1 --enable-libvmaf --enable-libvpx --enable-libwebp --disable-libxcb --enable-zlib --enable-libx265 --enable-libx264 --enable-nvenc --enable-nvdec --enable-amf --enable-libvpl --disable-encoder='avui,dca,mlp,opus,s302m,sonic,sonic_ls,truehd' --disable-decoder=sonic --disable-libjack --disable-indev=jack --disable-filter=gfxcapture
```
