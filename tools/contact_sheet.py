"""Composite numbered thumbnail grids so many files can be identified at once.

Each cell is captioned with the inventory index, so anything I spot on a sheet
can be referred back to an exact file.
"""
import os, json, math
from PIL import Image, ImageDraw, ImageFont

BASE   = os.path.dirname(os.path.abspath(__file__))
WORK   = os.path.join(BASE, 'work')
FRAMES = os.path.join(BASE, 'vidframes')
SHEETS = os.path.join(BASE, 'sheets')
inv = json.load(open(os.path.join(BASE, 'inventory.json')))

CELL, PAD, CAP = 430, 10, 30
COLS, ROWS = 4, 4

try:    font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 19)
except Exception: font = ImageFont.load_default()

def sheet(cells, name):
    """cells: list of (thumbnail path, caption)"""
    n = len(cells)
    rows = math.ceil(n / COLS)
    W = COLS * (CELL + PAD) + PAD
    H = rows * (CELL + CAP + PAD) + PAD
    canvas = Image.new('RGB', (W, H), (24, 24, 26))
    d = ImageDraw.Draw(canvas)
    for i, (path, cap) in enumerate(cells):
        cx = PAD + (i % COLS) * (CELL + PAD)
        cy = PAD + (i // COLS) * (CELL + CAP + PAD)
        try:
            im = Image.open(path).convert('RGB')
            im.thumbnail((CELL, CELL), Image.LANCZOS)
            canvas.paste(im, (cx + (CELL - im.width) // 2,
                              cy + (CELL - im.height) // 2))
        except Exception as e:
            d.text((cx + 8, cy + 8), 'ERR %s' % e, fill=(255, 90, 90), font=font)
        d.text((cx + 4, cy + CELL + 5), cap[:52], fill=(235, 235, 225), font=font)
    out = os.path.join(SHEETS, name)
    canvas.save(out, 'JPEG', quality=86)
    print(out, '%dx%d' % canvas.size, '%d cells' % n)

# --- images -------------------------------------------------------------
imgs = [r for r in inv if r['kind'] == 'image' and r.get('work')]
per = COLS * ROWS
for s in range(math.ceil(len(imgs) / per)):
    chunk = imgs[s * per:(s + 1) * per]
    cells = [(os.path.join(WORK, r['work']),
              '#%d %s %s' % (r['idx'], (r.get('date') or 'no-date')[:10],
                             (r.get('place_guess') or '')))
             for r in chunk]
    sheet(cells, 'img_%02d.jpg' % s)

# --- videos: one representative frame each, to identify the clip ---------
vids = [r for r in inv if r['kind'] == 'video' and r.get('frames')]
cells = []
for r in vids:
    mid = r['frames'][min(2, len(r['frames']) - 1)]
    cells.append((os.path.join(FRAMES, mid),
                  '#%d %ss %s' % (r['idx'], round(r.get('duration') or 0),
                                  (r.get('date') or '')[:10])))
for s in range(math.ceil(len(cells) / per)):
    sheet(cells[s * per:(s + 1) * per], 'vid_%02d.jpg' % s)

print('\nimages on sheets:', len(imgs), ' videos on sheets:', len(vids))
