# ClipBridge Android 0.6.2 — improved suggestions

Android 11+, package `app.clipbridge`, version code 9.

The offline engine now bundles **46,693 English and 49,814 Arabic entries** instead of the small hand-written list. Corpus frequency, completion length, and one/two-word phrase context rank the results. Common contractions are preserved. Arabic matching handles alef/hamza variants, vowel marks, tatweel, presentation forms and Persian kaf/yeh; final ة/ه and ى/ي alternatives are available. Iraqi Arabic chat vocabulary and common phrase hints are included. The typed word's script selects the completion language, even if the keyboard layout differs.

Spelling alternatives cover missing, extra, substituted and swapped letters, with up to two edits for longer words. Typo-tolerant partial completions work before the word is finished. These are tap-to-insert alternatives: the engine never silently replaces typed text. Phrase-based next-word hints appear after spaces. This is a frequency/context engine with curated phrase hints, not a neural language model.

Dictionary loading and ranking run on a worker thread. New typing cancels stale requests; results and taps are checked against the field, cursor context, and request generation. Queries are bounded to 256 surrounding characters, a 40-character current word, and a fixed fuzzy-search budget. No typing context is sent to a server.

## Optional personalization

In ClipBridge's keyboard settings, enable **Personalize suggestions on this phone** to learn completed words and adjacent word pairs. It is **off by default**. The phone stores at most 500 words and 1,000 pairs in private preferences. **Clear learned words** removes this data. Turning personalization off stops learning and using the saved data; clearing removes it permanently.

Suggestions and learning are disabled in password, number/phone, email, URL and no-suggestions fields. Address-like, digit-containing and URL-like current tokens are skipped even in ordinary text fields. Android's `IME_FLAG_NO_PERSONALIZED_LEARNING` disables both use and collection of personal suggestions. Password-manager inline suggestions retain priority. The keyboard does not learn from voice insertion or clipboard paste actions.

## Install and build

Install over workspace 0.6.0/0.6.1 to retain pairing. The existing project key is preserved. **The public 0.5.1-keyboard APK has a different signing key**: save important private files, uninstall that version, install this APK, and pair again. Uninstalling removes app-private data and settings.

```powershell
python build_android.py --work C:/path/to/private-android-build
python tests/check_keyboard.py
python tests/check_android_features.py --work C:/path/to/private-android-build
```

The last check requires Pillow and qrcode. To regenerate the bundled dictionaries, run `python tools/prepare_suggestions.py`; downloads use a pinned source revision and SHA-256 checks. This is a developer operation; installed keyboards need no network for suggestions. Data source and adaptation details are in `android/assets/suggestions/ATTRIBUTION.txt`, and are available in the app through **Dictionary credits**. The adapted frequency data is CC BY-SA 4.0, with its full license packaged in the APK and source ZIP.

## Verification — 5 November 2026

- 85 keyboard checks pass, covering corpus-backed English/Arabic completions, contractions, capitalization, context, Iraqi phrases, orthographic variants, personalization persistence/clearing, vocabulary limits, structured-token guards and Arabic alphabet coverage.
- All 16 fixed typo examples include the intended word among the top three results. Examples include `recieve → receive`, `becuase → because`, `keybaord → keyboard`, and Arabic duplicate-letter errors. These examples are regression fixtures, not a comprehensive accuracy benchmark.
- A 240-query desktop JVM run measured approximately 0.47 ms median, 3.76 ms p95 and 9.24 ms maximum lookup time after loading; dictionary initialization was about 290 ms. Phone latency has not been measured.
- Existing filename/screenshot helper tests and all 12 actual QR decoding cases pass. The production APK compiles and passes APK v3 signature verification.
- No phone or configured emulator is available in this workspace. Touch behavior, destination-app editing, popup placement, password-manager integration and Android worker responsiveness still need device testing.
