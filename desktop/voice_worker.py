"""ClipBridge's offline inference worker. The chosen GGUF is loaded only on dictation."""
import argparse
import base64
import json
import os
from pathlib import Path
import sys


def run(model_path):
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    model = None
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request['id']
            pcm = base64.b64decode(request['audio'], validate=True)
            if not pcm or len(pcm) % 2 or len(pcm) > 16000*2*60:
                raise ValueError('Invalid voice recording')
            import numpy as np
            audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32)/32768.0
            text = ''
            if len(audio) >= 2880:
                audio -= float(np.mean(audio))
                peak = float(np.max(np.abs(audio)))
                if peak >= .00015 and float(np.sqrt(np.mean(audio*audio))) >= .000025:
                    audio *= min(120.0, .1/max(peak, 1e-9))
                    from voice_vad import VadOptions, get_speech_timestamps
                    spans = get_speech_timestamps(audio, VadOptions(
                        threshold=.35, min_speech_duration_ms=120,
                        min_silence_duration_ms=350, speech_pad_ms=240))
                    if spans:
                        audio = audio[spans[0]['start']:spans[-1]['end']]
                        if len(audio) < 32000:
                            audio = np.pad(audio, (8000, 3200))
                        if model is None:
                            from transcribe_cpp import Model
                            model = Model(str(model_path), backend='cpu')
                        with model.session(n_threads=6) as session:
                            text = session.run(audio, language='en', task='transcribe',
                                               timestamps='none', pnc='on').text.strip()
            result = {'id': request_id, 'ok': True, 'text': text}
        except Exception as exc:
            result = {'id': request_id, 'ok': False,
                      'error': 'The selected voice model could not transcribe this recording ('+type(exc).__name__+').'}
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    args = parser.parse_args()
    run(args.model)
