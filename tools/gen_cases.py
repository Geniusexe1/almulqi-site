"""Replace the placeholder media blocks in the case studies with the real files.

    python3 tools/gen_cases.py

Idempotent: it only rewrites blocks that still carry the `media--empty`
placeholder class, so running it twice does nothing the second time.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(ROOT, 'assets', 'media.json'), encoding='utf-8'))
P = '../'                                   # case studies live one level down


def esc(s):
    return (s or '').replace('"', '&quot;')


def pic(name, sizes, cap=None, cls=''):
    e = M[name]
    if e['kind'] == 'render':
        body = ('<img src="%sassets/img/%s.png" width="%d" height="%d" alt="%s"\n'
                '         loading="lazy" decoding="async" style="background:#dcded5">'
                % (P, name, e['w'], e['h'], esc(e['alt'])))
    else:
        ws = e['widths']
        def ss(ext):
            return ', '.join('%sassets/img/%s-%d.%s %dw' % (P, name, w, ext, w) for w in ws)
        mid = ws[min(1, len(ws) - 1)]
        body = ('<picture>\n'
                '      <source type="image/avif" srcset="%s" sizes="%s">\n'
                '      <source type="image/webp" srcset="%s" sizes="%s">\n'
                '      <img src="%sassets/img/%s-%d.jpg" srcset="%s" sizes="%s"\n'
                '           width="%d" height="%d" alt="%s" loading="lazy" decoding="async"\n'
                '           style="background-color:%s">\n'
                '    </picture>'
                % (ss('avif'), sizes, ss('webp'), sizes, P, name, mid, ss('jpg'), sizes,
                   e['w'], e['h'], esc(e['alt']), e['avg']))
    figcap = '\n    <figcaption>%s</figcaption>' % (cap or e.get('caption')) if (cap or e.get('caption')) else ''
    return '<figure class="media reveal %s" data-scrub>\n    %s%s\n  </figure>' % (cls, body, figcap)


def clip(name, cap=None):
    e = M[name]
    figcap = '\n    <figcaption>%s</figcaption>' % (cap or e.get('caption')) if (cap or e.get('caption')) else ''
    return ('<figure class="clip reveal">\n'
            '    <video src="%sassets/video/%s.mp4" poster="%sassets/video/%s-poster.jpg"\n'
            '           width="%d" height="%d" muted loop playsinline preload="none"\n'
            '           aria-label="%s" style="background-color:%s"></video>%s\n'
            '  </figure>'
            % (P, name, P, name, e['w'], e['h'], esc(e['alt']), e['avg'], figcap))


def block(name, **kw):
    return clip(name, **kw) if M[name]['kind'] == 'video' else pic(name, '(max-width:900px) 92vw, 46vw', **kw)


PAGES = {
    'robonexus.html': dict(
        hero=pic('robot-iso', '(max-width:1100px) 92vw, 1100px',
                 cap='The machine, rendered from its own URDF and CAD meshes. '
                     '400 &times; 419 mm, 439 mm tall, 9.51 kg of aluminium.'),
        grid=['robonexus-unity', 'robonexus-sim', 'robonexus-grab', 'robonexus-cnc'],
        extra=pic('robot-side', '(max-width:900px) 92vw, 46vw',
                  cap='Front elevation. The chain loop and one claw hanging from it; '
                      'the bottom run sits 81 mm above the floor.')),
    'autonomous-drone.html': dict(
        hero=clip('drone-piloting'),
        grid=['drone-flight', 'drone-calibration'],
        extra=None),
    'racing-car.html': dict(
        hero=pic('car-bench', '(max-width:1100px) 92vw, 1100px'),
        grid=['car-racing', 'car-line', 'car-floor'],
        extra=None),
    'caricature-robot.html': dict(
        hero=pic('caricature-machine', '(max-width:1100px) 92vw, 1100px'),
        grid=['caricature-drawing', 'caricature-portrait', 'caricature-portrait-2'],
        extra=None),
}

HERO_RE = re.compile(
    r'<figure class="media media--empty reveal" data-scrub>.*?</figure>'
    r'|<figure class="media reveal" data-scrub>\s*<div class="media--empty".*?</figure>',
    re.S)
GRID_RE = re.compile(r'(<div class="media-grid">)(.*?)(</div>)', re.S)


def main():
    for fn, spec in PAGES.items():
        p = os.path.join(ROOT, 'projects', fn)
        s = open(p, encoding='utf-8').read()
        if 'media--empty' not in s:
            print('%-26s already wired, skipped' % fn); continue

        s, n1 = HERO_RE.subn(lambda m: spec['hero'], s, count=1)

        def grid_sub(m):
            items = '\n        '.join(block(n) for n in spec['grid'])
            if spec['extra']:
                items += '\n        ' + spec['extra']
            return m.group(1) + '\n        ' + items + '\n      ' + m.group(3)
        s, n2 = GRID_RE.subn(grid_sub, s, count=1)

        # the grid holds clips and stills side by side now
        s = s.replace('<div class="media-grid">', '<div class="media-grid clip-grid">')
        open(p, 'w', encoding='utf-8', newline='\n').write(s)
        print('%-26s hero:%d grid:%d  %d media' % (fn, n1, n2,
              len(spec['grid']) + (1 if spec['extra'] else 0) + 1))
        if 'media--empty' in s:
            print('   WARNING: placeholders still present')


main()
