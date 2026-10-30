"""
🎹 KEYBOARD DJ 🎹
────────────────────────────────────────
A  B  C  D  E  F  G  → Musical notes (A4–G5)
Q  W  E  R  T  Y  U  → Higher octave notes
1-9 keys             → Drum hits / sound effects
SPACE                → BEAT DROP 🔥
ESC                  → Quit
────────────────────────────────────────
Requirements: pip install simpleaudio numpy pynput
"""

import math
import time
import threading
import struct
import os

# ── Try importing required libs ──────────────────────────────────────────────
try:
    import numpy as np
except ImportError:
    print("❌ numpy missing! Run: pip install numpy")
    exit(1)

try:
    import simpleaudio as sa
except ImportError:
    print("❌ simpleaudio missing! Run: pip install simpleaudio")
    exit(1)

try:
    from pynput import keyboard
except ImportError:
    print("❌ pynput missing! Run: pip install pynput")
    exit(1)

# ── Audio settings ────────────────────────────────────────────────────────────
SAMPLE_RATE = 44100
CHANNELS    = 1

# ── Note frequencies (Hz) ─────────────────────────────────────────────────────
NOTES = {
    # Row 1: A-G → A4 to G5
    'a': ('A4',  440.00),
    'b': ('B4',  493.88),
    'c': ('C5',  523.25),
    'd': ('D5',  587.33),
    'e': ('E5',  659.25),
    'f': ('F5',  698.46),
    'g': ('G5',  783.99),
    # Row 2: Q-U → higher octave
    'q': ('A5',  880.00),
    'w': ('B5',  987.77),
    'r': ('C6', 1046.50),
    't': ('D6', 1174.66),
    'y': ('E6', 1318.51),
    'u': ('F6', 1396.91),
    # Extra keys
    'h': ('C4',  261.63),
    'j': ('D4',  293.66),
    'k': ('E4',  329.63),
    'l': ('F4',  349.23),
    'z': ('G4',  392.00),
    'x': ('Ab4', 415.30),
    'v': ('Bb4', 466.16),
    'n': ('Eb5', 622.25),
    'm': ('F#5', 739.99),
}

# Drum/FX sounds via number keys
DRUMS = {
    '1': ('KICK 🥁',   60,   0.3, 'kick'),
    '2': ('SNARE 🪘',  200,  0.2, 'snare'),
    '3': ('HI-HAT 🎩', 8000, 0.08, 'hihat'),
    '4': ('TOM 🥁',    120,  0.25, 'tom'),
    '5': ('CLAP 👏',   1000, 0.15, 'clap'),
    '6': ('BASS 🔊',   55,   0.4, 'bass'),
    '7': ('ZAP ⚡',    2000, 0.1, 'zap'),
    '8': ('RISE 🚀',   500,  0.3, 'rise'),
    '9': ('COIN 🪙',   1200, 0.12, 'coin'),
}

# ── Waveform generators ───────────────────────────────────────────────────────

def make_sine(freq, duration, volume=0.5, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(2 * np.pi * freq * t)
    # Envelope: attack + decay
    env = np.ones(len(t))
    attack = int(0.01 * sample_rate)
    release = int(0.1 * sample_rate)
    env[:attack] = np.linspace(0, 1, attack)
    env[-release:] = np.linspace(1, 0, release)
    return (wave * env * volume * 32767).astype(np.int16)

def make_noise(duration, sample_rate=SAMPLE_RATE):
    samples = int(sample_rate * duration)
    return (np.random.uniform(-1, 1, samples) * 32767 * 0.4).astype(np.int16)

def make_kick(sample_rate=SAMPLE_RATE):
    duration = 0.3
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freq = 60 * np.exp(-20 * t)           # Pitch drops fast
    wave = np.sin(2 * np.pi * freq * t)
    env = np.exp(-10 * t)
    return (wave * env * 32767 * 0.8).astype(np.int16)

def make_snare(sample_rate=SAMPLE_RATE):
    duration = 0.2
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(2 * np.pi * 200 * t) * 0.5
    noise = np.random.uniform(-1, 1, len(t)) * 0.5
    env = np.exp(-15 * t)
    return ((tone + noise) * env * 32767 * 0.6).astype(np.int16)

def make_hihat(sample_rate=SAMPLE_RATE):
    duration = 0.08
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    noise = np.random.uniform(-1, 1, len(t))
    env = np.exp(-60 * t)
    return (noise * env * 32767 * 0.5).astype(np.int16)

def make_zap(sample_rate=SAMPLE_RATE):
    duration = 0.15
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freq = 2000 * np.exp(-15 * t)
    wave = np.sign(np.sin(2 * np.pi * freq * t))  # Square wave
    env = np.exp(-15 * t)
    return (wave * env * 32767 * 0.5).astype(np.int16)

def make_rise(sample_rate=SAMPLE_RATE):
    duration = 0.4
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freq = 200 + 2000 * (t / duration)
    wave = np.sin(2 * np.pi * freq * t)
    env = t / duration
    return (wave * env * 32767 * 0.5).astype(np.int16)

def make_coin(sample_rate=SAMPLE_RATE):
    duration = 0.25
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = (np.sin(2 * np.pi * 1200 * t) + np.sin(2 * np.pi * 1500 * t)) * 0.5
    env = np.exp(-20 * t)
    return (wave * env * 32767 * 0.6).astype(np.int16)

def make_beat_drop(sample_rate=SAMPLE_RATE):
    """Epic beat drop: bass thump + noise sweep + rising tone"""
    duration = 1.2
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # Sub bass
    bass_freq = 80 * np.exp(-3 * t)
    bass = np.sin(2 * np.pi * bass_freq * t) * np.exp(-4 * t)

    # White noise sweep
    noise = np.random.uniform(-1, 1, len(t)) * np.exp(-8 * t) * 0.4

    # High ping
    ping = np.sin(2 * np.pi * 880 * t) * np.exp(-20 * t) * 0.3

    combined = bass + noise + ping
    combined = np.clip(combined, -1, 1)
    return (combined * 32767 * 0.9).astype(np.int16)

# ── Sound player ──────────────────────────────────────────────────────────────

def play_audio(audio_data):
    def _play():
        try:
            play_obj = sa.play_buffer(audio_data, CHANNELS, 2, SAMPLE_RATE)
            # Don't wait — fire and forget for responsiveness
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()

def play_note(key_char):
    if key_char in NOTES:
        name, freq = NOTES[key_char]
        audio = make_sine(freq, 0.4, volume=0.6)
        play_audio(audio)
        return f"🎵 {name} ({freq:.1f} Hz)"

def play_drum(key_char):
    if key_char not in DRUMS:
        return None
    name, freq, dur, kind = DRUMS[key_char]

    makers = {
        'kick':  make_kick,
        'snare': make_snare,
        'hihat': make_hihat,
        'zap':   make_zap,
        'rise':  make_rise,
        'coin':  make_coin,
        'tom':   lambda: make_sine(freq, dur, 0.7),
        'clap':  make_snare,
        'bass':  lambda: make_sine(freq, dur, 0.8),
    }
    audio = makers[kind]()
    play_audio(audio)
    return f"  {name}"

# ── Display ───────────────────────────────────────────────────────────────────

COLORS = {
    'reset':   '\033[0m',
    'bold':    '\033[1m',
    'cyan':    '\033[96m',
    'yellow':  '\033[93m',
    'green':   '\033[92m',
    'magenta': '\033[95m',
    'red':     '\033[91m',
    'blue':    '\033[94m',
    'dim':     '\033[2m',
    'white':   '\033[97m',
}

def c(color, text):
    return f"{COLORS.get(color,'')}{text}{COLORS['reset']}"

def print_header():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(c('cyan', """
  ██╗  ██╗███████╗██╗   ██╗██████╗  ██████╗   ██████╗      ██╗
  ██║ ██╔╝██╔════╝╚██╗ ██╔╝██╔══██╗██╔═══██╗ ██╔═══██╗    ██╔╝
  █████╔╝ █████╗   ╚████╔╝ ██████╔╝██║   ██║ ███████║    ██╔╝ 
  ██╔═██╗ ██╔══╝    ╚██╔╝  ██╔══██╗██║   ██║ ██╔══██║   ██╔╝  
  ██║  ██╗███████╗   ██║   ██████╔╝╚██████╔╝ ██║  ██║  ██╔╝   
  ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═════╝  ╚═════╝  ╚═╝  ╚═╝ ╚═╝    
"""))
    print(c('dim', '  ' + '─'*55))
    print(f"  {c('yellow','NOTES')}  {c('white','A B C D E F G')}  →  {c('green','A4 B4 C5 D5 E5 F5 G5')}")
    print(f"  {c('yellow','OCTAVE')} {c('white','Q W R T Y U')}    →  {c('green','Higher octave')}")
    print(f"  {c('yellow','DRUMS')}  {c('white','1 2 3 4 5 6 7 8 9')}  →  {c('magenta','Kick Snare Hat Tom Clap Bass Zap Rise Coin')}")
    print(f"  {c('yellow','SPACE')}  {c('red','► BEAT DROP ◄')}")
    print(f"  {c('yellow','ESC')}    Quit")
    print(c('dim', '  ' + '─'*55))
    print(f"\n  {c('dim','Waiting for keypress...')}\n")

# Log of recent sounds
log_lines = []
MAX_LOG = 8

def log_sound(text, color='white'):
    log_lines.append(c(color, f"  ► {text}"))
    if len(log_lines) > MAX_LOG:
        log_lines.pop(0)

    # Redraw log area (cursor to line 15)
    print(f"\033[15;0H", end='')
    for line in log_lines:
        print(f"\033[K{line}")         # Clear line then print
    # Clear remaining old lines
    for _ in range(MAX_LOG - len(log_lines)):
        print("\033[K")

# ── Key listener ──────────────────────────────────────────────────────────────

pressed_keys = set()

def on_press(key):
    try:
        k = key.char.lower() if hasattr(key, 'char') and key.char else None
    except Exception:
        k = None

    # Space = beat drop
    if key == keyboard.Key.space:
        if 'space' not in pressed_keys:
            pressed_keys.add('space')
            audio = make_beat_drop()
            play_audio(audio)
            log_sound('🔥🔥 BEAT DROP 🔥🔥', 'red')
        return

    # ESC = quit
    if key == keyboard.Key.esc:
        print(f"\n\n  {c('cyan','Thanks for DJing! Peace ✌️')}\n")
        return False  # Stop listener

    if k is None:
        return

    if k in pressed_keys:
        return  # Ignore held-down repeats
    pressed_keys.add(k)

    if k in NOTES:
        msg = play_note(k)
        if msg:
            log_sound(msg, 'green')

    elif k in DRUMS:
        msg = play_drum(k)
        if msg:
            log_sound(msg, 'magenta')

    else:
        # Any other key → random beep based on char code
        freq = 200 + (ord(k) * 17) % 1600
        audio = make_sine(freq, 0.15, 0.3)
        play_audio(audio)
        log_sound(f"? [{k.upper()}] → {freq:.0f} Hz", 'dim')

def on_release(key):
    try:
        k = key.char.lower() if hasattr(key, 'char') and key.char else None
    except Exception:
        k = None

    if key == keyboard.Key.space:
        pressed_keys.discard('space')
    elif k:
        pressed_keys.discard(k)

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print_header()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
