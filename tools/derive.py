"""Turn the curated originals into web assets.

    python3 tools/derive.py

Reads tools/manifest.json, writes assets/img, assets/video and assets/media.json.
Originals are never touched.

Why each step exists:
  * HEIC is 90 of the source files and browsers do not universally accept it.
  * AVIF and WebP cut a photo-led page from tens of megabytes to a couple.
  * Three widths + srcset means a phone never downloads a 1920px file.
  * Each entry carries the image averaged to one hex colour, so a slot is
    never an empty grey box while the real file loads, and nothing reflows.
  * iPhone clips are 10-bit HLG HDR. Browsers cannot decode High 10 profile
    H.264, so anything HDR is tone-mapped to 8-bit SDR bt709 or it plays black.
"""
import json, os, re, subprocess, sys

import cv2
import numpy as np

from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC    = 'C:/Users/Belal/Desktop/pics'
IMGDIR = os.path.join(ROOT, 'assets', 'img')
VIDDIR = os.path.join(ROOT, 'assets', 'video')
FFMPEG = 'C:/Program Files/ShareX/ffmpeg.exe'
WIDTHS = (480, 960, 1920)
# Full-bleed images are laid out at 100vw. A 1440px window at 2x device
# pixel ratio asks for 2880px, so capping at 1920 visibly softens them.
BIG_WIDTHS = (480, 960, 1920, 2560)

os.makedirs(IMGDIR, exist_ok=True)
os.makedirs(VIDDIR, exist_ok=True)


_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


def focus(im):
    """Where object-fit:cover should keep in frame, as (x%, y%).

    Any slot narrower or shorter than the photo crops it, and the default
    centre crop happily removes a face that sits high or off to one side. So
    find faces and aim the crop at them; with none, aim slightly above centre,
    which is where subjects usually are.
    """
    a = np.array(im.convert('RGB'))
    small = cv2.resize(a, (min(720, a.shape[1]), int(a.shape[0] * min(720, a.shape[1]) / a.shape[1])))
    grey = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    try:
        faces = _CASCADE.detectMultiScale(grey, 1.15, 5, minSize=(28, 28))
    except Exception:
        faces = []
    if len(faces) == 0:
        return (50, 42)
    # the union of every face, so a group shot keeps all of them
    x0 = min(f[0] for f in faces); y0 = min(f[1] for f in faces)
    x1 = max(f[0] + f[2] for f in faces); y1 = max(f[1] + f[3] for f in faces)
    cx = (x0 + x1) / 2.0 / small.shape[1]
    cy = (y0 + y1) / 2.0 / small.shape[0]
    return (int(round(max(0, min(100, cx * 100)))),
            int(round(max(0, min(100, cy * 100)))))


def avg_colour(im):
    """The image averaged to one hex colour.

    It sits under the <img> as a background, so a slot is never an empty grey
    rectangle while the file loads. A one-colour hex beats an inlined base64
    blur here: it is six characters instead of six hundred, which keeps the
    generated HTML small and hand-editable.
    """
    return '#%02x%02x%02x' % im.convert('RGB').resize((1, 1), Image.LANCZOS).getpixel((0, 0))


def do_image(entry, out):
    src = os.path.join(SRC, entry['src'])
    if not os.path.exists(src):
        print('  MISSING', entry['src']); return
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    name = entry['name']
    # Grain does not compress. A noisy frame that also sits under a scrim can
    # take far more compression than a clean one, so quality is per-entry.
    q = entry.get('q') or {}
    qj, qw, qa = q.get('jpg', 86), q.get('webp', 83), q.get('avif', 63)
    pool = BIG_WIDTHS if entry.get('big') else WIDTHS
    widths = [w for w in pool if w <= im.width] or [im.width]
    if im.width not in widths and im.width < max(pool):
        widths = sorted(set(widths + [im.width]))

    for w in widths:
        h = round(im.height * w / im.width)
        r = im.resize((w, h), Image.LANCZOS)
        r.save(os.path.join(IMGDIR, '%s-%d.jpg' % (name, w)), 'JPEG',
               quality=qj, optimize=True, progressive=True)
        r.save(os.path.join(IMGDIR, '%s-%d.webp' % (name, w)), 'WEBP', quality=qw, method=6)
        try:
            r.save(os.path.join(IMGDIR, '%s-%d.avif' % (name, w)), 'AVIF', quality=qa)
        except Exception as e:
            print('  avif failed for %s: %s' % (name, e))

    out[name] = {
        'kind': 'image', 'w': im.width, 'h': im.height,
        'widths': widths, 'avg': avg_colour(im), 'pos': focus(im),
        'alt': entry.get('alt', ''), 'caption': entry.get('caption'),
        'use': entry.get('use'),
    }
    print('  %-24s %dx%d  widths %s' % (name, im.width, im.height, widths))


def is_hdr(path):
    p = subprocess.run([FFMPEG, '-hide_banner', '-i', path],
                       capture_output=True, text=True, errors='ignore')
    s = p.stderr
    return ('bt2020' in s) or ('arib-std-b67' in s) or ('smpte2084' in s)


ROBOT_ALT = {
    'robot-iso':  'Three-quarter orthographic render of the ROBONEXUS robot: '
                  'mecanum wheels, side panels, chain sprockets and the stereo '
                  'camera, generated from its own URDF and CAD meshes.',
    'robot-side': 'Front elevation render of the ROBONEXUS robot showing the '
                  'wheel track, drive motors, chain loop and a claw hanging from it.',
    'robot-top':  'Plan view render of the ROBONEXUS robot.',
}

TONEMAP = ('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,'
           'tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p')


def do_video(entry, out):
    src = os.path.join(SRC, entry['src'])
    if not os.path.exists(src):
        print('  MISSING', entry['src']); return
    name = entry['name']
    ss, dur = entry.get('trim', [0, 10])

    vf = []
    if is_hdr(src):
        vf.append(TONEMAP)
    if entry.get('crop'):
        # used to cut a Snapchat-style caption band out of a screen recording
        vf.append('crop=' + entry['crop'])
    vf.append('scale=-2:%d' % entry.get('height', 960))
    vf.append('fps=30')

    mp4 = os.path.join(VIDDIR, name + '.mp4')
    poster = os.path.join(VIDDIR, name + '-poster.jpg')
    # Re-encoding every clip on every run is the slow part and almost never
    # what is wanted. Existing output is reused unless --force is passed.
    if os.path.exists(mp4) and os.path.exists(poster) and '--force' not in sys.argv:
        pim = Image.open(poster).convert('RGB')
        out[name] = {
            'kind': 'video', 'w': pim.width, 'h': pim.height,
            'avg': avg_colour(pim), 'pos': focus(pim), 'bytes': os.path.getsize(mp4),
            'alt': entry.get('alt', ''), 'caption': entry.get('caption'),
            'use': entry.get('use'),
        }
        print('  %-24s reused' % name)
        return
    cmd = [FFMPEG, '-y', '-loglevel', 'error', '-ss', str(ss), '-t', str(dur),
           '-i', src, '-an',                       # -an: every clip is muted
           '-vf', ','.join(vf),
           '-c:v', 'libx264', '-profile:v', 'main', '-pix_fmt', 'yuv420p',
           '-crf', str(entry.get('crf', 27)), '-preset', 'slow', '-movflags', '+faststart', mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(mp4):
        print('  FAILED', name, r.stderr[:200]); return

    # poster: a frame from the tone-mapped output, so it matches the video
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', str(min(2, dur / 2)),
                    '-i', mp4, '-frames:v', '1', poster], capture_output=True)

    pim = Image.open(poster).convert('RGB')
    pim.save(poster, 'JPEG', quality=80, optimize=True, progressive=True)

    out[name] = {
        'kind': 'video', 'w': pim.width, 'h': pim.height,
        'avg': avg_colour(pim), 'pos': focus(pim), 'bytes': os.path.getsize(mp4),
        'alt': entry.get('alt', ''), 'caption': entry.get('caption'),
        'use': entry.get('use'),
    }
    print('  %-24s %dx%d  %.1f MB' % (name, pim.width, pim.height,
                                      os.path.getsize(mp4) / 1e6))


def main():
    man = json.load(open(os.path.join(ROOT, 'tools', 'manifest.json'), encoding='utf-8'))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    # A filtered run must merge into the existing index, not replace it —
    # otherwise rebuilding one image silently drops every other entry.
    dst = os.path.join(ROOT, 'assets', 'media.json')
    out = {}
    if only and os.path.exists(dst):
        out = json.load(open(dst, encoding='utf-8'))

    print('images:')
    for e in man['images']:
        if only and only not in e['name']: continue
        do_image(e, out)
    print('videos:')
    for e in man['videos']:
        if only and only not in e['name']: continue
        do_video(e, out)

    # the robot renders, produced from the URDF by tools/render_robot.py
    for stem in ('robot-iso', 'robot-side', 'robot-top'):
        p = os.path.join(IMGDIR, stem + '.png')
        if os.path.exists(p):
            im = Image.open(p)
            out[stem] = {'kind': 'render', 'w': im.width, 'h': im.height,
                         'avg': '#8e948a', 'caption': None,
                         'alt': ROBOT_ALT[stem], 'use': 'project:robonexus'}

    json.dump(out, open(dst, 'w', encoding='utf-8'), indent=1)
    total = sum(os.path.getsize(os.path.join(IMGDIR, f)) for f in os.listdir(IMGDIR))
    vtotal = sum(os.path.getsize(os.path.join(VIDDIR, f)) for f in os.listdir(VIDDIR))
    print('\n%d entries -> assets/media.json' % len(out))
    print('img %.1f MB   video %.1f MB' % (total / 1e6, vtotal / 1e6))


main()
