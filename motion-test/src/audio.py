"""Voice edit + sfx mix.
usage: python3 audio.py <voice_file> <tmap_out.json> [<sfx.json> <out.wav>]
1) builds the voice from the chosen takes (old timeline),
2) tightens every pause longer than MAX_GAP down to KEEP_GAP (jump-cut),
3) writes the old->new time map (used by the renderer to retime all animations),
4) if sfx.json is given: mixes voice (loudness-normalised) + quiet sfx -> out.wav
"""
import sys, json, subprocess, numpy as np
voice = sys.argv[1]; tmap_out = sys.argv[2]
SR = 48000
SFX_PEAK_DB = -24.5      # loudest sfx peak in dBFS (user wants <= -23)
MAX_GAP, KEEP_GAP = 0.15, 0.08
SIL_DB = -38.0
HOLD_END = 0.7

def load(ss, dur):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(ss), '-t', str(dur), '-i', voice,
                          '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()
def fade(x, a=0.015, b=0.03):
    na, nb = int(a*SR), int(b*SR)
    x[:na] *= np.linspace(0, 1, na); x[-nb:] *= np.linspace(1, 0, nb); return x

# takes on the original recording: A 10.95-20.65, B 24.05-29.80 (skips the false start), C 35.38-39.00
segs = [(0.0, fade(load(10.95, 9.70))), (9.62, fade(load(24.05, 5.75))), (15.62, fade(load(35.38, 3.62), b=0.06))]
old = np.zeros(int(19.4*SR), np.float32)
for t, x in segs:
    i = int(t*SR); old[i:i+len(x)] += x[:len(old)-i]

# --- find pauses (10 ms frames) ---
hop = int(0.01*SR); nfr = len(old)//hop
rms = np.sqrt((old[:nfr*hop].reshape(nfr, hop)**2).mean(1))
sil = 20*np.log10(rms+1e-9) < SIL_DB
runs = []; i = 0
while i < nfr:
    if sil[i]:
        j = i
        while j < nfr and sil[j]: j += 1
        runs.append((i*0.01, j*0.01)); i = j
    else: i += 1
half = KEEP_GAP/2
cuts = []                                   # (old_start, old_end) removed
for s, e in runs:
    if e - s > MAX_GAP:
        a = 0.0 if s == 0 else s + half    # leading silence: drop entirely
        b = e - half
        if e >= nfr*0.01 - 0.011:          # trailing silence: leave it (hold is added later)
            continue
        if b > a: cuts.append((a, b))
# --- build new voice + knots ---
knots = [(0.0, 0.0)]; pieces = []; pos = 0.0; newt = 0.0
for a, b in cuts:
    pieces.append(old[int(pos*SR):int(a*SR)]); newt += a - pos
    knots += [(a, newt), (b, newt)]; pos = b
pieces.append(old[int(pos*SR):]); newt += len(old)/SR - pos
knots.append((len(old)/SR, newt))
# short crossfades at each joint
xf = int(0.008*SR); v = pieces[0]
for p in pieces[1:]:
    if len(v) > xf and len(p) > xf:
        r = np.linspace(0, 1, xf, dtype=np.float32)
        v = np.concatenate([v[:-xf], v[-xf:]*(1-r) + p[:xf]*r, p[xf:]])
    else: v = np.concatenate([v, p])
fr = np.sqrt(np.convolve(v**2, np.ones(hop)/hop, 'same'))
last = np.nonzero(20*np.log10(fr+1e-9) > SIL_DB)[0][-1]/SR
total = round(last + HOLD_END, 2)
json.dump({'knots': knots, 'duration': total, 'cuts': cuts}, open(tmap_out, 'w'))
print('pauses cut: %d, removed %.2fs, new duration %.2fs' % (len(cuts), sum(b-a for a, b in cuts), total))
if len(sys.argv) < 5: sys.exit()

sfxjson, out = sys.argv[3], sys.argv[4]
N = int(total*SR); vo = np.zeros(N, np.float32); vo[:min(N, len(v))] = v[:N]
def ff(x, af):
    pcm = (np.clip(x, -1, 1)*32767).astype('<i2').tobytes()
    o = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', af,
                        '-ar', str(SR), '-f', 'f32le', '-'], input=pcm, capture_output=True, check=True).stdout
    y = np.frombuffer(o, np.float32).copy(); z = np.zeros_like(x); z[:min(len(y), len(z))] = y[:len(z)]; return z
voice_st = ff(vo, 'loudnorm=I=-15:TP=-1.5:LRA=11')

rng = np.random.default_rng(1)
def env(n, att, dec):
    t = np.arange(n)/SR; return np.minimum(1, t/att) * np.exp(-t/dec)
def lp(x, k):
    y = np.empty_like(x); acc = 0.0
    for i, s in enumerate(x): acc += k*(s-acc); y[i] = acc
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
        return 0.05*x*(0.6+0.4*np.sin(2*np.pi*11*t))*np.sin(np.pi*t/d)
    return np.zeros(1)
sfx_st = np.zeros(N, np.float32)
for kind, t in json.load(open(sfxjson)):          # times already in the new timeline
    x = sfx(kind).astype(np.float32); i = int(t*SR)
    if i < N: sfx_st[i:i+len(x)] += x[:N-i]
sfx_st *= 10**(SFX_PEAK_DB/20)/np.abs(sfx_st).max()
mix = voice_st + sfx_st
print('voice peak %.1f dBFS, sfx peak %.1f dBFS' % (20*np.log10(np.abs(voice_st).max()), 20*np.log10(np.abs(sfx_st).max())))
pcm = (np.clip(mix, -1, 1)*32767).astype('<i2').tobytes()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', out], input=pcm, check=True)
