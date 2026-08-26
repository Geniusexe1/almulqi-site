"""Scan the 148 root files in pics/, pull date + GPS, and make working JPEGs.

The three solo* folders are Unity Perception datasets, not personal media, and are
skipped. Originals are never modified; everything here writes to work/.
"""
import os, json, subprocess, re, sys
from datetime import datetime
from PIL import Image, ExifTags, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()

SRC   = 'C:/Users/Belal/Desktop/pics'
WORK  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work')
FRAMES= os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vidframes')
FFMPEG= 'C:/Program Files/ShareX/ffmpeg.exe'

IMG_EXT = {'.jpg', '.jpeg', '.heic', '.png'}
VID_EXT = {'.mov', '.mp4'}

# journey stops, for GPS routing when coordinates survived the export
PLACES = {'riyadh': (24.7136, 46.6753), 'ankara': (39.9334, 32.8597),
          'daejeon': (36.3504, 127.3845)}

def dms(v):
    try:    return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
    except Exception: return None

def exif_of(path):
    """(iso date string or None, (lat,lon) or None, (w,h))"""
    try:
        im = Image.open(path)
    except Exception:
        return None, None, None
    size = im.size
    try:    ex = im.getexif()
    except Exception: return None, None, size
    tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
    raw  = tags.get('DateTimeOriginal') or tags.get('DateTime')
    date = None
    if raw:
        try:    date = datetime.strptime(str(raw)[:19], '%Y:%m:%d %H:%M:%S').isoformat()
        except Exception: pass
    coords = None
    try:    gps = ex.get_ifd(0x8825)
    except Exception: gps = None
    if gps:
        g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps.items()}
        if 'GPSLatitude' in g and 'GPSLongitude' in g:
            lat, lon = dms(g['GPSLatitude']), dms(g['GPSLongitude'])
            if lat is not None and lon is not None:
                if str(g.get('GPSLatitudeRef', '')).upper().startswith('S'):  lat = -lat
                if str(g.get('GPSLongitudeRef', '')).upper().startswith('W'): lon = -lon
                coords = (round(lat, 5), round(lon, 5))
    return date, coords, size

def nearest_place(coords):
    if not coords: return None
    lat, lon = coords
    best, bd = None, 1e9
    for name, (a, b) in PLACES.items():
        d = ((lat - a) ** 2 + (lon - b) ** 2) ** 0.5
        if d < bd: best, bd = name, d
    return best if bd < 3.0 else 'elsewhere'   # ~300 km

def probe_video(path):
    """duration seconds, creation time, w/h — parsed from ffmpeg's own report."""
    p = subprocess.run([FFMPEG, '-hide_banner', '-i', path],
                       capture_output=True, text=True, errors='ignore')
    s = p.stderr
    dur = None
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', s)
    if m: dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    created = None
    m = re.search(r'creation_time\s*:\s*([0-9T:\-\.]+)', s)
    if m: created = m.group(1)[:19]
    wh = None
    m = re.search(r'Stream #\d+:\d+.*?Video:.*?(\d{3,5})x(\d{3,5})', s, re.S)
    if m: wh = (int(m.group(1)), int(m.group(2)))
    rot = 0
    m = re.search(r'rotation of ([\-0-9\.]+) degrees', s)
    if m: rot = int(float(m.group(1)))
    return dur, created, wh, rot

def key_of(fn):
    return re.sub(r'[^A-Za-z0-9]+', '_', os.path.splitext(fn)[0]).strip('_')[:48]

def main():
    files = [f for f in sorted(os.listdir(SRC))
             if os.path.isfile(os.path.join(SRC, f))]
    prev = {}
    inv_path = os.path.join(os.path.dirname(WORK), 'inventory.json')
    if os.path.exists(inv_path):
        for r in json.load(open(inv_path)):
            prev[r['file']] = r
    out = []
    for i, fn in enumerate(files):
        src = os.path.join(SRC, fn)
        ext = os.path.splitext(fn)[1].lower()
        k = key_of(fn)
        if fn in prev and prev[fn].get('work'):
            wp0 = os.path.join(WORK, prev[fn]['work'])
            if os.path.exists(wp0):
                r = dict(prev[fn]); r['idx'] = i; out.append(r)
                continue
        rec = {'idx': i, 'file': fn, 'key': k, 'ext': ext,
               'bytes': os.path.getsize(src)}
        if ext in IMG_EXT:
            rec['kind'] = 'image'
            date, coords, size = exif_of(src)
            rec['date'], rec['gps'] = date, coords
            rec['place_guess'] = nearest_place(coords)
            if size: rec['w'], rec['h'] = size
            # working JPEG, long edge 1400, orientation applied
            try:
                im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
                im.thumbnail((1400, 1400), Image.LANCZOS)
                wp = os.path.join(WORK, k + '.jpg')
                im.save(wp, 'JPEG', quality=88)
                rec['work'] = os.path.basename(wp)
                rec['orient'] = 'landscape' if im.width >= im.height else 'portrait'
            except Exception as e:
                rec['error'] = 'convert: %s' % e
        elif ext in VID_EXT:
            rec['kind'] = 'video'
            dur, created, wh, rot = probe_video(src)
            rec['duration'], rec['date'] = dur, created
            if wh: rec['w'], rec['h'] = wh
            rec['rotation'] = rot
            eff = (wh[1], wh[0]) if wh and rot in (90, 270, -90) else wh
            rec['orient'] = ('landscape' if eff[0] >= eff[1] else 'portrait') if eff else None
            # six candidate frames across the clip
            if dur and dur > 0:
                picks = [dur * f for f in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85)]
                names = []
                for kk, t in enumerate(picks):
                    fp = os.path.join(FRAMES, '%s_%d.jpg' % (k, kk))
                    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', '%.2f' % t,
                                    '-i', src, '-frames:v', '1', '-vf', 'scale=700:-2',
                                    fp], capture_output=True)
                    if os.path.exists(fp): names.append(os.path.basename(fp))
                rec['frames'] = names
        else:
            rec['kind'] = 'other'
        out.append(rec)
        print('%3d/%d %-46s %-8s %s' % (i + 1, len(files), fn[:46], rec['kind'],
              (rec.get('date') or '-')[:10]), flush=True)

    with open(os.path.join(os.path.dirname(WORK), 'inventory.json'), 'w') as f:
        json.dump(out, f, indent=1)
    imgs = [r for r in out if r['kind'] == 'image']
    vids = [r for r in out if r['kind'] == 'video']
    print('\nimages %d  videos %d  other %d' % (len(imgs), len(vids),
          len(out) - len(imgs) - len(vids)))
    print('with date: %d   with GPS: %d' %
          (sum(1 for r in out if r.get('date')), sum(1 for r in out if r.get('gps'))))

main()
