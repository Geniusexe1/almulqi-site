"""Flat-shaded orthographic z-buffer rasteriser. numpy + Pillow only.

Transparent background so the render composites onto either site theme.
"""
import os, math, sys
import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(BASE, 'robot')
tris = np.load(os.path.join(OUT, 'tris.npy'))
cols = np.load(os.path.join(OUT, 'cols.npy'))

def view_matrix(az, el):
    """Look-at with world +Z up. Rows are the screen basis: x right, y up,
    z toward the camera (so a larger z is nearer, which is what the z-buffer
    test below assumes)."""
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.cos(e) * math.cos(a),
                  math.cos(e) * math.sin(a),
                  math.sin(e)])
    up = np.array([0.0, 0.0, 1.0])
    if abs(d[2]) > 0.999:                 # looking straight down: pick a new up
        up = np.array([0.0, 1.0, 0.0])
    x = np.cross(up, d); x /= np.linalg.norm(x)
    y = np.cross(d, x)
    return np.stack([x, y, d])

def render(az, el, W, H, ss=2, margin=0.06, light=(-0.35, -0.55, 0.75)):
    w, h = W * ss, H * ss
    R = view_matrix(az, el)
    v = tris.reshape(-1, 3) @ R.T
    v = v.reshape(-1, 3, 3)

    lo, hi = v.reshape(-1, 3).min(0), v.reshape(-1, 3).max(0)
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    span = max(hi[0] - lo[0], hi[1] - lo[1]) * (1 + margin * 2)
    s = min(w, h) / span

    px = (v[:, :, 0] - cx) * s + w / 2
    py = h / 2 - (v[:, :, 1] - cy) * s          # screen y is down
    pz = v[:, :, 2]

    e1 = v[:, 1] - v[:, 0]
    e2 = v[:, 2] - v[:, 0]
    n = np.cross(e1, e2)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    n[ok] /= ln[ok][:, None]
    front = n[:, 2] > 0                          # cull back faces
    L = np.array(light, dtype=float); L /= np.linalg.norm(L)
    lam = np.clip(n @ L, 0, 1)
    shade = 0.26 + 0.74 * lam                    # ambient + diffuse

    zbuf = np.full((h, w), -np.inf, dtype=np.float32)
    rgb  = np.zeros((h, w, 3), dtype=np.float32)
    hit  = np.zeros((h, w), dtype=bool)

    order = np.nonzero(front & ok)[0]
    for i in order:
        x0, x1 = px[i].min(), px[i].max()
        y0, y1 = py[i].min(), py[i].max()
        ix0, ix1 = max(int(math.floor(x0)), 0), min(int(math.ceil(x1)) + 1, w)
        iy0, iy1 = max(int(math.floor(y0)), 0), min(int(math.ceil(y1)) + 1, h)
        if ix1 <= ix0 or iy1 <= iy0: continue
        X, Y = np.meshgrid(np.arange(ix0, ix1) + .5, np.arange(iy0, iy1) + .5)
        ax, ay = px[i, 0], py[i, 0]; bx, by = px[i, 1], py[i, 1]; ncx, ncy = px[i, 2], py[i, 2]
        d = (by - ncy) * (ax - ncx) + (ncx - bx) * (ay - ncy)
        if abs(d) < 1e-9: continue
        l1 = ((by - ncy) * (X - ncx) + (ncx - bx) * (Y - ncy)) / d
        l2 = ((ncy - ay) * (X - ncx) + (ax - ncx) * (Y - ncy)) / d
        l3 = 1 - l1 - l2
        m = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not m.any(): continue
        z = l1 * pz[i, 0] + l2 * pz[i, 1] + l3 * pz[i, 2]
        sub = zbuf[iy0:iy1, ix0:ix1]
        upd = m & (z > sub)
        if not upd.any(): continue
        sub[upd] = z[upd]
        rgb[iy0:iy1, ix0:ix1][upd] = cols[i] * shade[i]
        hit[iy0:iy1, ix0:ix1][upd] = True

    a = (hit.astype(np.float32) * 255)
    img = np.dstack([np.clip(rgb * 255, 0, 255), a]).astype(np.uint8)
    im = Image.fromarray(img, 'RGBA')
    if ss > 1: im = im.resize((W, H), Image.LANCZOS)
    return im

if __name__ == '__main__':
    views = [('iso',   38,  22, 1600, 1200),
             ('top',    0,  90, 1400, 1400),
             ('front',  0,   0, 1600, 1000),
             ('side',  90,   0, 1600, 1000),
             ('hero',  25,  14, 2000, 1250)]
    for name, az, el, W, H in views:
        im = render(az, el, W, H)
        p = os.path.join(OUT, 'robot_%s.png' % name)
        im.save(p)
        print('%-6s %s  %d KB' % (name, im.size, os.path.getsize(p) // 1024), flush=True)
