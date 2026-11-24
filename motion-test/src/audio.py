import sys, json, subprocess, numpy as np
voice, sfxjson, out = sys.argv[1:4]
SR = 48000
def load(ss, dur):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(ss), '-t', str(dur), '-i', voice,
                          '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()
def fade(x, a=0.015, b=0.03):
    na, nb = int(a*SR), int(b*SR)
    x[:na] *= np.linspace(0, 1, na); x[-nb:] *= np.linspace(1, 0, nb); return x
# voice cuts (original file times): A 10.95-20.65, B 24.05-29.80 (skips false start), C 35.38-39.00
segs = [(0.0, fade(load(10.95, 9.70))), (9.62, fade(load(24.05, 5.75))), (15.62, fade(load(35.38, 3.62), b=0.06))]
total = 20.0
mix = np.zeros(int(total*SR), np.float32)
for t, x in segs:
    i = int(t*SR); mix[i:i+len(x)] += x[:len(mix)-i]
rng = np.random.default_rng(1)
def env(n, att, dec):
    t = np.arange(n)/SR; return np.minimum(1, t/att) * np.exp(-t/dec)
def lp(x, k):  # crude one-pole lowpass, k in (0,1)
    y = np.empty_like(x); acc = 0.0
    for i, v in enumerate(x): acc += k*(v-acc); y[i] = acc
    return y
def sfx(kind):
    if kind == 'pop':
        n = int(.09*SR); t = np.arange(n)/SR
        f = 520*np.exp(-t*18)+260; ph = 2*np.pi*np.cumsum(f)/SR
        return 0.22*np.sin(ph)*env(n, .002, .025)
    if kind == 'tick':
        n = int(.03*SR); return 0.10*rng.standard_normal(n)*env(n, .0005, .004)
    if kind in ('whoosh', 'flip', 'swish'):
        d = {'whoosh': .45, 'flip': .25, 'swish': .35}[kind]; n = int(d*SR)
        x = rng.standard_normal(n); t = np.linspace(0, 1, n)
        x = lp(x, 0.08) * np.sin(np.pi*t)**2
        return {'whoosh': .35, 'flip': .22, 'swish': .12}[kind] * x / (np.abs(x).max()+1e-9)
    if kind == 'stamp':
        n = int(.22*SR); t = np.arange(n)/SR
        thump = np.sin(2*np.pi*(70+60*np.exp(-t*30))*t) * env(n, .001, .06)
        crack = lp(rng.standard_normal(n), .35) * env(n, .0005, .015)
        return 0.55*thump + 0.35*crack/np.abs(crack).max()
    if kind in ('draw', 'scribble'):
        d = .5 if kind == 'draw' else .35; n = int(d*SR); t = np.arange(n)/SR
        x = rng.standard_normal(n); x = x - lp(x, .25)
        am = 0.6+0.4*np.sin(2*np.pi*11*t)
        return 0.05*x*am*np.sin(np.pi*t/d)
    return np.zeros(1)
# --- voice stem: loudness-normalised on its own ---
def ff(x, af):
    pcm = (np.clip(x, -1, 1)*32767).astype('<i2').tobytes()
    o = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', af,
                        '-ar', str(SR), '-f', 'f32le', '-'], input=pcm, capture_output=True, check=True).stdout
    y = np.frombuffer(o, np.float32).copy(); z = np.zeros_like(x); z[:min(len(y), len(z))] = y[:len(z)]; return z
voice_st = ff(mix, 'loudnorm=I=-15:TP=-1.5:LRA=11')
# --- sfx stem: fixed absolute level, peaks at SFX_PEAK_DB dBFS ---
SFX_PEAK_DB = -26.0
sfx_st = np.zeros_like(mix)
for kind, t in json.load(open(sfxjson)):
    x = sfx(kind).astype(np.float32); i = int(t*SR)
    sfx_st[i:i+len(x)] += x[:max(0, len(mix)-i)]
sfx_st *= 10**(SFX_PEAK_DB/20)/np.abs(sfx_st).max()
mix = voice_st + sfx_st
print('voice peak %.1f dBFS, sfx peak %.1f dBFS' % (20*np.log10(np.abs(voice_st).max()), 20*np.log10(np.abs(sfx_st).max())))
pcm = (np.clip(mix, -1, 1)*32767).astype('<i2').tobytes()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', out], input=pcm, check=True)
print('ok', len(mix)/SR)
