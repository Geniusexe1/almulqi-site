"""Turn a reference image into an SVG silhouette for the journey map.

    python3 tools/trace_landmark.py <image> <mode> <out-name> [--invert]

Modes
  lines     The reference is a line drawing and you want it kept as line art.
            Traces each stroke as a ring; evenodd fill reproduces the drawing.
  ink       The reference is a line drawing. Flood the background from the
            frame edge and keep what it cannot reach, which turns the enclosed
            outlines into one solid silhouette - far more legible at map size
            than reproducing every stroke.
  skyline   The reference is a photograph of something against sky. Find the
            sky (bright, low saturation, connected to the top edge), and take
            the boundary between sky and everything else as the silhouette.

Output is a path string in the same local coordinate system the LANDMARKS dict
uses: (0,0) at the base centre, the shape growing upward, about 58 units tall.
"""
import os, sys
import numpy as np
import cv2


def simplify(cnt, eps_frac=0.004):
    peri = cv2.arcLength(cnt, True)
    return cv2.approxPolyDP(cnt, eps_frac * peri, True)


def to_path(polys, height=58.0, pad=0.0):
    """Normalise a list of point arrays into the landmark coordinate system."""
    allp = np.vstack([p.reshape(-1, 2) for p in polys]).astype(float)
    x0, y0 = allp[:, 0].min(), allp[:, 1].min()
    x1, y1 = allp[:, 0].max(), allp[:, 1].max()
    s = height / max(1e-6, (y1 - y0))
    cx = (x0 + x1) / 2.0
    out = []
    for p in polys:
        pts = p.reshape(-1, 2).astype(float)
        if len(pts) < 3:
            continue
        d = []
        for i, (px, py) in enumerate(pts):
            X = (px - cx) * s
            Y = (py - y1) * s          # y1 is the base -> Y = 0 there, negative above
            d.append('%s%.1f,%.1f' % ('M' if i == 0 else 'L', X, Y))
        out.append(' '.join(d) + ' Z')
    return ' '.join(out)


def trace_ink(img, invert):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    _, ink = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if invert:
        ink = 255 - ink
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    # Flood the paper from the border. Anything the flood cannot reach is
    # enclosed by an outline, so ink + unreachable = the solid buildings.
    h, w = ink.shape
    free = (ink == 0).astype(np.uint8) * 255
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(free, mask, (0, 0), 128)
    cv2.floodFill(free, mask, (w - 1, 0), 128)
    solid = ((free != 128) | (ink > 0)).astype(np.uint8) * 255
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    # Keep holes. The Kingdom Centre IS its void - fill that in and the
    # silhouette stops being the Kingdom Centre. RETR_CCOMP gives outer
    # contours and their holes; both are emitted and fill-rule=evenodd on the
    # SVG path punches the holes back out.
    cnts, hier = cv2.findContours(solid, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hier is not None:
        for c, h in zip(cnts, hier[0]):
            a = cv2.contourArea(c)
            if h[3] == -1 and a > 120:            # outer
                out.append(simplify(c, 0.004))
            elif h[3] != -1 and a > 90:           # a hole worth keeping
                out.append(simplify(c, 0.006))
    return out[:24]


def trace_lines(img, invert):
    """Trace the strokes themselves, not the regions they enclose.

    Each stroke becomes a thin closed ring; filling those rings with
    fill-rule=evenodd reproduces the drawing as line art, which is what an
    'outline' means here - and it keeps the Kingdom Centre's void, which
    flood-filling the enclosed area destroys.
    """
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    _, ink = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if invert:
        ink = 255 - ink
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, hier = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hier is not None:
        for c, h in zip(cnts, hier[0]):
            if cv2.contourArea(c) > 30:
                out.append(simplify(c, 0.003))
    return out[:80]


def trace_skyline(img):
    """Sky = bright, unsaturated, and reachable from the top edge."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    sky = ((V > 140) & (S < 90)).astype(np.uint8) * 255
    sky = cv2.morphologyEx(sky, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    # flood from the top edge so bright roofs and roads are not called sky
    h, w = sky.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    seeded = sky.copy()
    for x in range(0, w, max(1, w // 60)):
        if seeded[0, x] == 255:
            cv2.floodFill(seeded, mask, (x, 0), 128)
    sky = (seeded == 128).astype(np.uint8) * 255

    ground = 255 - sky
    ground = cv2.morphologyEx(ground, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))

    # the silhouette is the topmost non-sky pixel in each column
    top = np.full(w, h - 1, dtype=int)
    for x in range(w):
        col = np.nonzero(ground[:, x])[0]
        if len(col):
            top[x] = col[0]
    xs = np.arange(0, w, max(1, w // 220))
    pts = [[int(x), int(top[x])] for x in xs]
    pts = [[0, int(top[0])]] + pts + [[w - 1, int(top[-1])], [w - 1, h - 1], [0, h - 1]]
    poly = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
    return [simplify(poly, 0.0022)]


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    path, mode, name = sys.argv[1], sys.argv[2], sys.argv[3]
    invert = '--invert' in sys.argv
    crop = None
    for a in sys.argv[4:]:
        if a.startswith('--crop='):
            crop = [float(v) for v in a.split('=')[1].split(',')]   # l,t,r,b as fractions
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit('cannot read ' + path)
    if crop:
        h, w = img.shape[:2]
        l, t, r, b = crop
        img = img[int(t * h):int(b * h), int(l * w):int(r * w)]
    scale = 900.0 / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    if mode == 'ink':      polys = trace_ink(img, invert)
    elif mode == 'lines':  polys = trace_lines(img, invert)
    else:                  polys = trace_skyline(img)
    d = to_path(polys)
    print('%s: %d contours, %d chars' % (name, len(polys), len(d)))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'traced')
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, name + '.path'), 'w').write(d)

    # preview, so the result can be judged before it goes near the site
    prev = np.full((520, 620, 3), 223, np.uint8)
    pts = []
    for seg in d.split('Z'):
        seg = seg.strip()
        if not seg:
            continue
        p = [tuple(map(float, t[1:].split(','))) for t in seg.split() if t[0] in 'ML']
        pts.append(np.array([[int(310 + x * 6), int(430 + y * 6)] for x, y in p], np.int32))
    for poly in pts:                       # even-odd: each ring toggles
        layer = np.zeros(prev.shape[:2], np.uint8)
        cv2.fillPoly(layer, [poly], 1)
        cur = (prev[:, :, 0] < 100).astype(np.uint8)
        new = cur ^ layer
        prev[new == 1] = (34, 34, 30)
        prev[new == 0] = 223
    cv2.line(prev, (0, 430), (620, 430), (154, 161, 146), 2)
    cv2.imwrite(os.path.join(out, name + '.png'), prev)
    print('  preview:', os.path.join(out, name + '.png'))


main()
