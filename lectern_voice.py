#!/usr/bin/env python3
"""Lectern voice helper: a human-like voice that runs on this computer.

What it does
    It speaks the sentences that Lectern sends, with the open voice model Kokoro (82 million
    parameters, Apache 2.0 licence). It also tells Lectern the time of every word, so the text
    on the screen and the voice stay together. No text leaves this computer. No cost.

Set-up (one time)
    1. Python 3.10 or newer.
    2. pip install kokoro-onnx          (tested with version 0.6.1)
    3. python lectern_voice.py
       The first start downloads two files (about 350 MB together) into the folder
       "lectern_voice_model" beside this file. After that the helper needs no network.

Use
    Keep this window open. In Lectern: Audio, Voice engine "Neural voice"; then "Key, model and
    voice", Service for the neural voice "This computer". Switch on "Read aloud (sync)" and
    press Play. Lectern talks to http://127.0.0.1:8765.

Options
    --port 8765        port on this computer
    --dir  FOLDER      folder for the two model files
    --voice af_heart   standard voice (Lectern can choose another one)

Safety
    The helper answers only requests that come from this computer (address 127.0.0.1). A page
    that is open in a browser on this computer can ask it to speak a text. The helper reads no
    files and sends nothing to the network after the first start.
"""
import argparse, io, json, os, select, socket, sys, threading, time, urllib.request, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx'
VOICES_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin'
SR = 24000
MAX_TEXT = 6000            # characters of one request
MAX_BODY = 400000          # bytes of one request
# The voice model places the start of a word about 0.05 s after the first sound of the word.
# Measured on 123 test sentences with three voices: the first sound after a pause came 0.045 to
# 0.07 s (median for each voice, 371 pauses) before the time mark of the model. The times that
# Lectern gets mark the first sound of each word.
EDGE_LAG = 0.05
# signs of the phoneme text that are no speech sounds: spaces, stress and length marks, punctuation
DROP = set(" ˈˌː;:,.!?¡¿—…\"«»“”()")
OPENERS = set("(“\"«")
# language of the phoneme rules for each group of voices (first letter of the voice name)
LANG = {'a': 'en-us', 'b': 'en-gb', 'e': 'es', 'f': 'fr-fr', 'h': 'hi', 'i': 'it', 'p': 'pt-br'}


def say(*parts):
    """Print a line; signs that the window cannot show are replaced."""
    line = ' '.join(str(p) for p in parts)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode('ascii'), flush=True)


def fetch(url, path):
    """Download a file with a progress line."""
    say('Downloading', os.path.basename(path), '...')
    tmp = path + '.part'
    with urllib.request.urlopen(url) as r, open(tmp, 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        done = last = 0
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            f.write(block)
            done += len(block)
            if total and done - last >= 20 << 20:
                last = done
                say('  %d of %d MB' % (done >> 20, total >> 20))
    if total and done != total:
        os.remove(tmp)
        raise SystemExit('The download of %s was cut off. Start the helper again.' % os.path.basename(path))
    os.replace(tmp, path)


def sounds(ph):
    """Speech sounds of a phoneme text, each with its place in the text."""
    return [(c, i) for i, c in enumerate(ph) if c not in DROP]


def align(a, b):
    """Match two lists of speech sounds. Returns for each place of `a` the place of `b` that stands against it, or -1."""
    n, m = len(a), len(b)
    prev = list(range(m + 1))
    rows = [prev]
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            c = prev[j - 1] + (0 if ai == b[j - 1] else 1)
            d = prev[j] + 1
            e = cur[j - 1] + 1
            cur[j] = c if (c <= d and c <= e) else (d if d <= e else e)
        rows.append(cur)
        prev = cur
    out = [-1] * n
    i, j = n, m
    while i > 0 and j > 0:
        if rows[i][j] == rows[i - 1][j - 1] + (0 if a[i - 1] == b[j - 1] else 1):
            out[i - 1] = j - 1
            i -= 1
            j -= 1
        elif rows[i][j] == rows[i - 1][j] + 1:
            i -= 1
        else:
            j -= 1
    return out


class Line:
    """Requests are served one at a time, in the order of their arrival."""

    def __init__(self):
        self.cv = threading.Condition()
        self.issued = 0
        self.serving = 0

    def __enter__(self):
        with self.cv:
            ticket = self.issued
            self.issued += 1
            while self.serving != ticket:
                self.cv.wait()

    def __exit__(self, *exc):
        with self.cv:
            self.serving += 1
            self.cv.notify_all()


def client_gone(sock):
    """True if the page has closed the connection: it no longer waits for this sentence."""
    try:
        readable, _, _ = select.select([sock], [], [], 0)
        return bool(readable) and sock.recv(1, socket.MSG_PEEK) == b''
    except (OSError, ValueError):
        return True


class Voice:
    def __init__(self, model, voices, default_voice):
        from kokoro_onnx import Kokoro
        self.k = Kokoro(model, voices)
        names = self.k.get_voices() if hasattr(self.k, 'get_voices') else list(self.k.voices.files)
        self.names = sorted(n for n in names if n[:1] in LANG)
        self.default = default_voice if default_voice in self.names else ('af_heart' if 'af_heart' in self.names else self.names[0])
        # word times need a model file that reports the length of each speech sound, and a library that passes it on
        self.timed = bool(getattr(self.k, 'has_timings', False)) and hasattr(self.k, 'create_timed')
        self.line = Line()

    def speak(self, text, voice, tokens, gone=lambda: False):
        """Returns (samples as 16 bit numbers, start time of each token in seconds or None).
        Returns (None, None) if the page no longer waits for the sentence."""
        import numpy as np
        k = self.k
        voice = voice if voice in self.names else self.default
        lang = LANG.get(voice[:1], 'en-us')
        with self.line:
            if gone():
                return None, None
            starts = None
            spoken = []
            if self.timed:
                try:
                    audio, _, spoken = k.create_timed(text, voice=voice, speed=1.0, lang=lang)
                except (AttributeError, TypeError) as e:        # another version of the library
                    self.timed = False
                    say('Word times are not available with this version of kokoro-onnx (%s). Lectern will estimate them from the sound.' % e)
            if not self.timed:
                audio, _ = k.create(text, voice=voice, speed=1.0, lang=lang)
            if tokens and spoken:
                # the speech sounds of each token alone are matched with the speech sounds of the whole sentence
                A, token_of = [], []
                for ti, t in enumerate(tokens):
                    for c, _ in sounds(k.tokenizer.phonemize(str(t), lang)):
                        A.append(c)
                        token_of.append(ti)
                B = sounds(''.join(s.phoneme for s in spoken))
                match = align(A, [c for c, _ in B])
                starts = [None] * len(tokens)
                for ai, ti in enumerate(token_of):
                    if starts[ti] is None and match[ai] >= 0:
                        ki = B[match[ai]][1]
                        while ki > 0 and spoken[ki - 1].phoneme in OPENERS:    # an opening bracket holds the first sound of the word
                            ki -= 1
                        starts[ti] = max(0.0, float(spoken[ki].start) - EDGE_LAG)
                later = len(audio) / SR
                for ti in range(len(starts) - 1, -1, -1):       # a token with no sound of its own (a dash) starts with the next token
                    if starts[ti] is None or starts[ti] > later:
                        starts[ti] = later
                    later = starts[ti]
        # cut the silence before the first sound and after the last sound
        level = np.abs(audio)
        loud = np.where(level > 0.01 * max(1e-6, float(level.max())))[0]
        if len(loud):
            a = max(0, int(loud[0]) - int(0.04 * SR))
            b = min(len(audio), int(loud[-1]) + int(0.15 * SR))
            audio = audio[a:b]
            if starts is not None:
                starts = [min(len(audio) / SR, max(0.0, s - a / SR)) for s in starts]
        return (np.clip(audio, -1, 1) * 32767).astype('<i2'), starts


def wav_bytes(samples):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # a page that closes its connection is no error of the helper
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_handler(voice):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            pass

        def cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'authorization, content-type')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Expose-Headers', 'X-Lectern-Times')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Access-Control-Max-Age', '600')

        def send(self, status, body, ctype, extra=None):
            self.send_response(status)
            self.cors()
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def error(self, status, message):
            self.send(status, json.dumps({'error': {'message': message}}).encode(), 'application/json')

        def do_OPTIONS(self):
            self.send_response(204)
            self.cors()
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            path = self.path.split('?')[0].rstrip('/')
            if path.endswith('/audio/speech/models'):
                par = {'voice': {'type': 'enum', 'values': voice.names}, 'response_format': {'values': ['wav']}}
                data = {'data': [{'id': 'kokoro', 'name': 'Kokoro 82M on this computer', 'word_times': voice.timed,
                                  'output_modalities': [{'type': 'speech', 'supported_parameters': par}]}]}
                self.send(200, json.dumps(data).encode(), 'application/json')
            else:
                self.send(200, ('Lectern voice helper is running. Voices: %d. Word times: %s.\n' % (len(voice.names), 'yes' if voice.timed else 'no')).encode(), 'text/plain; charset=utf-8')

        def do_POST(self):
            path = self.path.split('?')[0].rstrip('/')
            try:
                size = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                size = -1
            if size < 0 or size > MAX_BODY:
                self.close_connection = True
                self.error(413, 'the request is too long')
                return
            raw = self.rfile.read(size)                          # the whole request is read before any answer
            if not path.endswith('/audio/speech'):
                self.error(404, 'unknown address')
                return
            try:
                body = json.loads(raw or b'{}')
                if not isinstance(body, dict):
                    raise ValueError('the request is not a JSON object')
                text = str(body.get('input') or '').strip()
                if not text:
                    raise ValueError('no text')
                if len(text) > MAX_TEXT:
                    raise ValueError('the text is longer than %d characters' % MAX_TEXT)
                tokens = body.get('lectern_tokens')
                if not (isinstance(tokens, list) and 0 < len(tokens) <= 2000):
                    tokens = None
            except (ValueError, UnicodeDecodeError) as e:
                self.error(400, 'the request could not be read' if isinstance(e, json.JSONDecodeError) else str(e)[:200])
                return
            try:
                t0 = time.time()
                samples, starts = voice.speak(text, str(body.get('voice') or ''), tokens, gone=lambda: client_gone(self.connection))
                if samples is None:                              # the page has moved on to another sentence
                    self.close_connection = True
                    return
                extra = {'X-Lectern-Times': ','.join('%.3f' % s for s in starts)} if starts is not None else None
                say('%5.1f s of speech in %4.1f s   %s' % (len(samples) / SR, time.time() - t0, text[:60]))
                self.send(200, wav_bytes(samples), 'audio/wav', extra)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except Exception as e:                               # the voice model could not speak this text
                say('Error:', e)
                try:
                    self.error(500, str(e)[:200])
                except OSError:
                    self.close_connection = True

    return Handler


def main():
    ap = argparse.ArgumentParser(description='Lectern voice helper: a human-like voice on this computer.')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lectern_voice_model'))
    ap.add_argument('--voice', default='af_heart')
    args = ap.parse_args()
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        raise SystemExit('The package "kokoro-onnx" is missing. Install it with:  pip install kokoro-onnx')
    os.makedirs(args.dir, exist_ok=True)
    model, voices = os.path.join(args.dir, 'kokoro-v1.0.onnx'), os.path.join(args.dir, 'voices-v1.0.bin')
    if not os.path.exists(voices):
        fetch(VOICES_URL, voices)
    if not os.path.exists(model):
        fetch(MODEL_URL, model)
    say('Loading the voice model ...')
    v = Voice(model, voices, args.voice)
    try:
        server = Server(('127.0.0.1', args.port), make_handler(v))
    except OSError as e:
        raise SystemExit('Port %d cannot be used (%s). Is the helper already running? Another port: --port 8766 (then set the same address in Lectern).' % (args.port, e))
    say('Lectern voice helper is ready at http://127.0.0.1:%d  (%d voices; word times: %s).' % (args.port, len(v.names), 'yes' if v.timed else 'no, Lectern estimates them from the sound'))
    say('Keep this window open. Stop with Ctrl+C.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        say('\nStopped.')


if __name__ == '__main__':
    main()
