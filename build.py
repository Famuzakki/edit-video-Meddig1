#!/usr/bin/env python3
"""Build the vertical (1080x1920) social-media edit of the PMD explainer.

Usage: python3 build.py <src_dir> <work_dir> <output.mp4>
  src_dir  : folder with IMG_9402.MOV (hook) and IMG_9431.MOV (main explanation)
  work_dir : scratch folder for intermediate files
"""
import math
import os
import subprocess
import sys

SRC, WORK, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(WORK, exist_ok=True)
W, H, FPS = 1080, 1920, 30

# ----------------------------------------------------------------------------
# 1. Cut list (source seconds) -- dead air / long pauses removed.
#    (name, file, start, end, zoom_start, zoom_end)
# ----------------------------------------------------------------------------
SEGS = [
    ("A1", "IMG_9402", 0.30, 5.20, 1.00, 1.07),   # hook
    ("A2", "IMG_9402", 5.20, 7.95, 1.22, 1.26),   # punch-in "Emang bener?"
    ("B1", "IMG_9431", 1.00, 9.40, 1.00, 1.06),   # gelar + kurikulum
    ("B2", "IMG_9431", 9.75, 15.75, 1.18, 1.20),  # dicari industri
    ("B3a", "IMG_9431", 16.30, 25.05, 1.00, 1.07),  # yang dipelajari
    ("B3b", "IMG_9431", 25.05, 29.90, 1.25, 1.30),  # CTA
]
OUTRO = ("OUT", "IMG_9431", 28.90, 31.90)
XF_AB, XF_OUT = 0.4, 0.5
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo_pill.png")
LOGO_SCALE, LOGO_Y = 0.62, 168

dur = {s[0]: s[3] - s[2] for s in SEGS}
A_LEN = dur["A1"] + dur["A2"]
B_LEN = dur["B1"] + dur["B2"] + dur["B3a"] + dur["B3b"]
B0 = A_LEN - XF_AB                      # timeline start of B
OUT0 = B0 + B_LEN - XF_OUT              # timeline start of outro
OUT_LEN = OUTRO[3] - OUTRO[2]
TOTAL = OUT0 + OUT_LEN


def T(clip, s):
    """Map a source time to the final timeline."""
    if clip == "A":
        return s - 0.30
    if s < 9.75:
        return B0 + (s - 1.00)
    if s < 16.30:
        return B0 + dur["B1"] + (s - 9.75)
    return B0 + dur["B1"] + dur["B2"] + (s - 16.30)


TONEMAP = ("fps=30,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
GRADE = "eq=contrast=1.04:saturation=1.05:gamma=1.01,unsharp=5:5:0.4"


def run(cmd):
    print("+", " ".join(cmd)[:200])
    subprocess.run(cmd, check=True)


def render_seg(name, f, a, b, z0, z1):
    out = f"{WORK}/{name}.mp4"
    if os.path.exists(out) and not os.environ.get("REBUILD"):
        return out
    n = round((b - a) * FPS)
    # zoom pivot at 42% height keeps the face steady
    zp = (f"zoompan=z='{z0}+({z1}-{z0})*on/{n}':d=1:s={W}x{H}:fps={FPS}:"
          f"x='iw/2-iw/zoom/2':y='ih*0.42-ih/zoom*0.42'")
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(a), "-t", f"{b - a:.3f}", "-i", f"{SRC}/{f}.MOV",
         "-map", "0:v:0", "-map", "0:a:0", "-vf", f"{TONEMAP},{zp},{GRADE},setsar=1",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", out])
    return out


def render_outro():
    name, f, a, b = OUTRO
    out = f"{WORK}/{name}.mp4"
    if os.path.exists(out) and not os.environ.get("REBUILD"):
        return out
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(a), "-t", f"{b - a:.3f}", "-i", f"{SRC}/{f}.MOV",
         "-f", "lavfi", "-t", f"{b - a:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v:0", "-map", "1:a:0",
         "-vf", f"{TONEMAP},scale={W}:{H},gblur=sigma=28,eq=brightness=-0.18:saturation=0.8,"
                f"drawbox=x=0:y=0:w=iw:h=ih:color=0x0B1F4D@0.62:t=fill,setsar=1",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-c:a", "pcm_s16le", out])
    return out


# ----------------------------------------------------------------------------
# 2. Graphics + captions (ASS)
# ----------------------------------------------------------------------------
NAVY, CYAN, WHITE, BLACK = "&H4D1F0B&", "&HFFE329&", "&HFFFFFF&", "&H000000&"


def ts(t):
    t = max(0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def rrect(w, h, r):
    k = 0.5523 * r
    return (f"m {r} 0 l {w - r} 0 b {w - r + k} 0 {w} {r - k} {w} {r} l {w} {h - r} "
            f"b {w} {h - r + k} {w - r + k} {h} {w - r} {h} l {r} {h} b {r - k} {h} 0 {h - r + k} 0 {h - r} "
            f"l 0 {r} b 0 {r - k} {r - k} 0 {r} 0")


EV = []


def ev(t0, t1, text, layer=0, style="Cap"):
    EV.append(f"Dialogue: {layer},{ts(t0)},{ts(t1)},{style},,0,0,0,,{text}")


POP = r"\fscx70\fscy70\t(0,120,\fscx108\fscy108)\t(120,200,\fscx100\fscy100)"


def box(t0, t1, cx, cy, w, h, color, alpha="00", r=22, pop=True, layer=1, fade=(120, 150)):
    anim = POP if pop else ""
    ev(t0, t1, rf"{{\an5\pos({cx},{cy})\p1\bord0\shad0\1c{color}\1a&H{alpha}&{anim}\fad({fade[0]},{fade[1]})}}"
               f"{rrect(w, h, r)}{{\\p0}}", layer)


def text(t0, t1, cx, cy, s, size, color=WHITE, font="Montserrat Black", pop=True, layer=2,
         bord=0, extra="", fade=(120, 150)):
    anim = POP if pop else ""
    ev(t0, t1, rf"{{\an5\pos({cx},{cy})\fn{font}\fs{size}\1c{color}\bord{bord}\3c{BLACK}\shad0"
               rf"{anim}\fad({fade[0]},{fade[1]}){extra}}}{s}", layer)


def card(t0, t1, cy, label, value, w=900):
    """Info card: small cyan label + big white value on navy pill."""
    h = 150
    box(t0, t1, 540, cy, w, h, NAVY, "18")
    box(t0, t1, 540 - w // 2 + 14, cy, 12, h - 40, CYAN, "00", r=6, layer=2)
    text(t0, t1, 540, cy - 34, label, 34, CYAN, "Montserrat ExtraBold")
    text(t0, t1, 540, cy + 22, value, 58, WHITE)


def check_row(t0, t1, cy, s):
    box(t0, t1, 540, cy, 820, 92, WHITE, "08", r=46)
    box(t0, t1, 540 - 410 + 52, cy, 64, 64, CYAN, "00", r=32, layer=2)
    text(t0, t1, 540 - 410 + 52, cy + 2, "✓", 44, NAVY, "DejaVu Sans", extra=r"\b1", layer=3)
    ev(t0, t1, rf"{{\an4\pos({540 - 410 + 104},{cy + 2})\fnMontserrat ExtraBold\fs46\1c{NAVY}\bord0\shad0{POP}"
               rf"\fad(120,150)}}{s}", 3)


# --- captions: (clip, src_start, src_end, text) ---
CAPS = [
    ("A", 0.75, 2.00, "Katanya, Komunikasi"), ("A", 2.00, 2.62, "Terapan kini"),
    ("A", 2.62, 3.50, "berubah nama jadi"), ("A", 3.50, 4.66, "D4 Produksi"),
    ("A", 4.66, 5.22, "Media Digital"), ("A", 5.30, 6.30, "Emang bener?"),
    ("A", 6.60, 7.60, "Oke, kepoin yuk!"),
    ("B", 1.15, 2.32, "Jadi, lulusan PMD"), ("B", 2.32, 3.16, "langsung dapat gelar"),
    ("B", 3.16, 3.92, "Sarjana Terapan"), ("B", 3.92, 4.94, "Ilmu Komunikasi."),
    ("B", 5.05, 6.50, "Terus prodinya juga"), ("B", 6.50, 7.16, "berhubungan dengan"),
    ("B", 7.16, 8.66, "industri modern"), ("B", 8.66, 9.35, "sekarang ini."),
    ("B", 9.85, 10.66, "Yang di mana"), ("B", 10.66, 11.44, "lulusannya"),
    ("B", 11.44, 12.32, "dicari-cari"), ("B", 12.32, 13.28, "sama industri tersebut,"),
    ("B", 13.28, 14.76, "karena ada banyak"), ("B", 14.76, 15.72, "praktik langsung."),
    ("B", 16.35, 16.94, "Selain itu,"), ("B", 16.94, 17.72, "kita nggak cuma"),
    ("B", 17.72, 18.80, "belajar komunikasi,"), ("B", 18.80, 19.84, "tapi juga langsung"),
    ("B", 19.84, 20.70, "praktik"), ("B", 20.70, 22.00, "komunikasi digital,"),
    ("B", 22.00, 22.58, "broadcasting,"), ("B", 22.58, 24.24, "sampai manajemen"),
    ("B", 24.24, 25.14, "media digital."), ("B", 25.14, 27.18, "So, buruan"),
    ("B", 27.18, 28.46, "join PMD, guys!"), ("B", 28.46, 29.40, "See you!"),
]


def captions():
    cap_y = 1480
    for clip, a, b, s in CAPS:
        t0, t1 = T(clip, a), T(clip, b)
        words = s.split()
        lens = [len(w) + 2 for w in words]
        tot = sum(lens)
        cur = t0
        for i, w in enumerate(words):
            wt1 = t1 if i == len(words) - 1 else cur + (t1 - t0) * lens[i] / tot
            parts = [(r"{\1c" + CYAN + r"\fscx112\fscy112}" + x + r"{\1c" + WHITE + r"\fscx100\fscy100}")
                     if j == i else x for j, x in enumerate(words)]
            anim = POP if i == 0 else ""
            ev(cur, wt1, rf"{{\an5\pos(540,{cap_y})\q0{anim}}}" + " ".join(parts), 5)
            cur = wt1


def graphics():
    # progress bar
    ev(0, TOTAL, rf"{{\an7\pos(0,0)\p1\bord0\shad0\1c{CYAN}\clip(0,0,0,12)\t(0,{int(TOTAL * 1000)},\clip(0,0,1080,12))}}"
                 f"m 0 0 l 1080 0 l 1080 12 l 0 12{{\\p0}}", 9)

    # ---- HOOK (A) ----
    t_d4 = T("A", 3.50)
    box(0.05, t_d4, 540, 330, 760, 110, NAVY, "10")
    text(0.05, t_d4, 540, 332, "KOMUNIKASI TERAPAN", 58, WHITE)
    box(0.35, t_d4, 540, 455, 560, 110, CYAN, "00")
    text(0.35, t_d4, 540, 457, "GANTI NAMA?!", 62, NAVY)

    t_a2 = T("A", 5.20)
    text(t_d4, t_a2, 540, 260, "RESMI JADI", 40, WHITE, "Montserrat ExtraBold", bord=6)
    box(t_d4, t_a2, 540, 390, 900, 190, CYAN, "00", r=30)
    text(t_d4, t_a2, 540, 352, "D4 PRODUKSI", 74, NAVY)
    text(t_d4, t_a2, 540, 432, "MEDIA DIGITAL", 74, NAVY)
    # "Emang bener?" sticker
    text(T("A", 5.30), T("A", 6.55), 820, 420, "?!", 190, CYAN, bord=10, extra=r"\frz-12")
    box(T("A", 6.60), A_LEN, 540, 400, 620, 120, NAVY, "10")
    text(T("A", 6.60), A_LEN, 540, 402, r"KEPOIN YUK! {\fnDejaVu Sans\b1}↓", 64, WHITE, "Montserrat Black")

    # ---- persistent tag during B ----
    # (logo pill PMD | SV | UNS is overlaid as an image in main(), see LOGO)

    # ---- info cards ----
    card(T("B", 2.60), T("B", 9.35), 320, "GELAR LULUSAN", "SARJANA TERAPAN")
    text(T("B", 3.90), T("B", 9.35), 540, 425, "Ilmu Komunikasi", 40, WHITE, "Montserrat ExtraBold", bord=6)
    card(T("B", 6.50), T("B", 9.35), 545, "KURIKULUM", "RELEVAN DGN INDUSTRI")
    card(T("B", 11.44), T("B", 15.70), 320, "PROSPEK KERJA", "DICARI INDUSTRI")
    card(T("B", 14.46), T("B", 15.70), 490, "METODE BELAJAR", "BANYAK PRAKTIK")

    t_l = T("B", 16.35); t_end = T("B", 25.05)
    box(t_l, t_end, 540, 270, 680, 84, NAVY, "10")
    text(t_l, t_end, 540, 272, "YANG KAMU PELAJARI", 42, CYAN)
    check_row(T("B", 20.70), t_end, 380, "Komunikasi Digital")
    check_row(T("B", 22.00), t_end, 485, "Broadcasting")
    check_row(T("B", 23.74), t_end, 590, "Manajemen Media Digital")

    # ---- CTA ----
    t_c = T("B", 25.20)
    box(t_c, OUT0 + 0.3, 540, 330, 860, 130, CYAN, "00", r=30)
    text(t_c, OUT0 + 0.3, 540, 332, "DAFTAR PMB SEKARANG!", 60, NAVY)
    text(T("B", 27.18), OUT0 + 0.3, 540, 470, "Jangan sampai ketinggalan", 40, WHITE, "Montserrat ExtraBold", bord=6)

    # ---- OUTRO card ----
    o = OUT0 + 0.25
    text(o, TOTAL, 540, 640, "PROGRAM STUDI", 40, CYAN, "Montserrat ExtraBold")
    text(o + 0.1, TOTAL, 540, 780, "D4 PRODUKSI", 96, WHITE)
    text(o + 0.1, TOTAL, 540, 895, "MEDIA DIGITAL", 96, WHITE)
    text(o + 0.3, TOTAL, 540, 1000, "Sekolah Vokasi UNS", 46, WHITE, "Montserrat SemiBold")
    box(o + 0.6, TOTAL, 540, 1160, 760, 120, CYAN, "00", r=60)
    text(o + 0.6, TOTAL, 540, 1162, "DAFTAR PMB SEKARANG", 54, NAVY)
    text(o + 0.9, TOTAL, 540, 1320, "Follow  •  Like  •  Share", 40, WHITE, "Montserrat ExtraBold")


def write_ass(path):
    captions()
    graphics()
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat Black,74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,8,4,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(path, "w") as fh:
        fh.write(head + "\n".join(EV) + "\n")


# ----------------------------------------------------------------------------
# 3. Sound effects (synthesised -- no licensed assets needed)
# ----------------------------------------------------------------------------
def sfx():
    whoosh = f"{WORK}/whoosh.wav"; pop = f"{WORK}/pop.wav"; chime = f"{WORK}/chime.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.6",
         "-af", "bandpass=f=1200:w=1800,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.35:d=0.25,volume=0.35",
         "-ar", "48000", "-ac", "2", whoosh])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*(500*t+1400*t*t))*exp(-28*t)':d=0.18:s=48000",
         "-af", "volume=0.35", "-ac", "2", pop])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "aevalsrc='0.25*(sin(2*PI*880*t)+0.6*sin(2*PI*1320*t)+0.4*sin(2*PI*1760*t))*exp(-3*t)':d=1.6:s=48000",
         "-af", "volume=0.35", "-ac", "2", chime])
    return whoosh, pop, chime


def main():
    segs = [render_seg(*s) for s in SEGS]
    outro = render_outro()
    ass = f"{WORK}/graphics.ass"
    write_ass(ass)
    whoosh, pop, chime = sfx()

    pops = [0.05, 0.35, T("A", 3.5), T("A", 6.6), T("B", 2.6), T("B", 6.5), T("B", 11.44),
            T("B", 14.46), T("B", 16.35), T("B", 20.7), T("B", 22.0), T("B", 23.74), T("B", 25.2)]
    whooshes = [B0 - 0.2, OUT0 - 0.2]

    inputs = []
    for p in segs + [outro]:
        inputs += ["-i", p]
    n = len(segs)
    fc = []
    # video: hard cuts within each scene, smooth transitions between scenes
    fc.append("[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[av0][aa]")
    fc.append("[av0]fps=30,settb=1/30,setpts=N/30/TB[av]")
    fc.append("".join(f"[{i}:v][{i}:a]" for i in range(2, n)) + f"concat=n={n - 2}:v=1:a=1[bv0][ba]")
    fc.append("[bv0]fps=30,settb=1/30,setpts=N/30/TB[bv]")
    fc.append(f"[{n}:v]fps=30,settb=1/30,setpts=N/30/TB[ov]")
    fc.append(f"[av][bv]xfade=transition=smoothleft:duration={XF_AB}:offset={A_LEN - XF_AB:.3f},settb=1/30[abv]")
    fc.append(f"[aa][ba]acrossfade=d={XF_AB}:c1=tri:c2=tri[aba]")
    fc.append(f"[abv][ov]xfade=transition=fade:duration={XF_OUT}:offset={OUT0:.3f},"
              f"subtitles={ass}:fontsdir=/usr/share/fonts[xv]")
    fc.append(f"[aba][{n}:a]acrossfade=d={XF_OUT}:c1=tri:c2=tri,"
              "highpass=f=80,afftdn=nf=-28,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,"
              "acompressor=threshold=-26dB:ratio=3:attack=5:release=90:makeup=4,"
              "loudnorm=I=-14:TP=-1.5:LRA=7[voice]")
    k = n + 1
    sfx_in = []
    mix = []
    for i, t in enumerate(pops):
        sfx_in += ["-i", pop]
        fc.append(f"[{k}:a]adelay={int(t * 1000)}:all=1[p{i}]"); mix.append(f"[p{i}]"); k += 1
    for i, t in enumerate(whooshes):
        sfx_in += ["-i", whoosh]
        fc.append(f"[{k}:a]adelay={int(max(t, 0) * 1000)}:all=1[w{i}]"); mix.append(f"[w{i}]"); k += 1
    sfx_in += ["-i", chime]
    fc.append(f"[{k}:a]adelay={int((OUT0 + 0.6) * 1000)}:all=1[ch]"); mix.append("[ch]")
    # logo pill (PMD | SV | UNS) on top during the explanation + outro
    lg_in = ["-loop", "1", "-t", f"{TOTAL:.3f}", "-i", LOGO]
    l0 = B0 + 0.2
    fc.append(f"[{k + 1}:v]scale=iw*{LOGO_SCALE}:-1,format=rgba,"
              f"fade=t=in:st={l0:.2f}:d=0.35:alpha=1,setpts=PTS-STARTPTS[lg]")
    fc.append(f"[xv][lg]overlay=x=(W-w)/2:y={LOGO_Y}-h/2:enable='gte(t,{l0:.2f})':shortest=1,"
              "format=yuv420p[vout]")
    sfx_in += lg_in
    fc.append("[voice]" + "".join(mix) + f"amix=inputs={len(mix) + 1}:normalize=0:duration=first,"
              "alimiter=limit=0.95[aout]")

    run(["ffmpeg", "-y", "-v", "error", *inputs, *sfx_in, "-filter_complex", ";".join(fc),
         "-map", "[vout]", "-map", "[aout]", "-t", f"{TOTAL:.3f}",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", OUT])
    print(f"done: {OUT}  ({TOTAL:.2f}s)")


if __name__ == "__main__":
    main()
