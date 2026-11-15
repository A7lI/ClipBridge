"""Rebuild the attributed, pinned offline dictionaries; network is build-time only."""
import hashlib
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = "525f9b560de45753a5ea01069454e72e9aa541c6"
SHA256 = {"en": "5351ff405b1126ef555791dd4d9798a48e3e9a501a9fc481a9da957752cfb458",
          "ar": "bbe98b4b92902b392bdefa2e555a108fdb42a5dd79d261674be5ab666229e19f"}
EXTRA_AR = "شلون شلونك شلونج شلونكم شخبارك شخبارج شخباركم شنو وين وينك وينج وينكم ليش شكد هسه باجر البارحة زين خوش هواية شوية ماكو أكو اكو مو إي اي أني اني إنت إنتي انتو إحنا احنا بالبيت بالطريق بالدوام الدوام نروح نجي أجي اجي جاي جاية راح دزلي دزيت دزيتلك دزيتلج دزيلي دزله تسلم تسلمين حبيبي حبيبتي حبايبي يلا هيج هيچ چان چنت چنتي گلت گلتلك گلي گولي شلونچ وينچ شخبارچ مشتاق مشتاقلك مشتاقين موبايل واتساب تليجرام إنستغرام انستغرام التطبيق إعدادات مشاركة تحميل تنزيل الملفات الصورة الصور لوحة مفاتيح إنترنت".split()

def main():
    target = ROOT / "android/assets/suggestions"
    target.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "ar"):
        url = f"https://raw.githubusercontent.com/hermitdave/FrequencyWords/{REVISION}/content/2018/{lang}/{lang}_50k.txt"
        data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != SHA256[lang]:
            raise ValueError(f"Dictionary checksum mismatch: {lang}")
        words = {}
        for line in data.decode("utf-8").splitlines():
            word, frequency = line.rsplit(" ", 1)
            # Keep lexical tokens, including English contractions; discard corpus markup/digits.
            valid = (re.fullmatch(r"[a-z]+(?:'[a-z]+)?", word) if lang == "en" else
                     all('\u0600' <= c <= '\u06ff' and (c.isalpha() or '\u064b' <= c <= '\u065f') for c in word))
            if valid and 1 < len(word) <= 32:
                words[word] = int(frequency)
        if lang == "en":
            # Subtitle tokenization leaves apostrophe fragments. Restore full contractions.
            for stem in "don doesn didn won wouldn couldn shouldn hadn hasn haven isn aren weren wasn mustn mightn needn shan ain".split():
                count = words.pop(stem, 0)
                if count:
                    full = stem + "'t"
                    words[full] = max(words.get(full, 0), count)
            for word in ("i", "a"):
                words[word] = 27086011 if word == "i" else 14484562
        else:
            for word in EXTRA_AR:
                words[word] = max(words.get(word, 0), 180000)
        header = ("# FrequencyWords by Hermit Dave; OpenSubtitles 2018\n"
                  "# CC BY-SA 4.0; see ATTRIBUTION.txt and CC-BY-SA-4.0.txt in this directory\n"
                  f"# Source revision {REVISION}; ClipBridge filtered tokens and added Arabic chat vocabulary\n")
        (target / f"{lang}.txt").write_text(header + ''.join(f"{word} {count}\n" for word, count in sorted(words.items(), key=lambda x: (-x[1], x[0]))), encoding="utf-8")
        print(f"{lang}: {len(words):,} words")

if __name__ == "__main__":
    main()
