"""Fold picks.json (from tools/picker/picker.html) into tools/manifest.json.

    python3 tools/apply_picks.py [path/to/picks.json]

Defaults to looking in tools/, then in your Downloads folder, since that is
where the browser puts it.

What it does NOT do is invent alt text. Anything newly added is listed at the
end as NEEDS ALT — every published image needs a real description of what is in
the frame, and only a person who was there can write that.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, 'tools', 'manifest.json')

SLOT_TO_USE = {
    'hero':       'hero',
    'montage':    'montage',
    'riyadh':     'journey:saudi',
    'ankara':     'journey:turkiye',
    'daejeon':    'journey:korea',
    'robonexus':  'project:robonexus',
    'drone':      'project:autonomous-drone',
    'car':        'project:racing-car',
    'caricature': 'project:caricature-robot',
    'personal':   'personal',
}
SLOT_PREFIX = {
    'hero': 'hero', 'montage': 'shot', 'riyadh': 'saudi', 'ankara': 'ankara',
    'daejeon': 'korea', 'robonexus': 'robonexus', 'drone': 'drone',
    'car': 'car', 'caricature': 'caricature', 'personal': 'life',
}
VID_EXT = {'.mov', '.mp4'}


def find_picks():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for c in (os.path.join(ROOT, 'tools', 'picks.json'),
              os.path.join(ROOT, 'picks.json'),
              os.path.expanduser('~/Downloads/picks.json')):
        if os.path.exists(c):
            return c
    sys.exit('picks.json not found. Pass its path as an argument.')


def stem(src, slot, taken):
    base = re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(src))[0].lower()).strip('-')
    # UUID-ish filenames carry no meaning; number them by slot instead
    if len(base) > 18 or re.fullmatch(r'[0-9a-f-]+', base):
        base = ''
    name = '%s-%s' % (SLOT_PREFIX[slot], base) if base else SLOT_PREFIX[slot]
    cand, n = name, 2
    while cand in taken:
        cand = '%s-%d' % (name, n); n += 1
    taken.add(cand)
    return cand


def main():
    picks = json.load(open(find_picks(), encoding='utf-8'))
    man = json.load(open(MAN, encoding='utf-8'))

    by_src = {}
    for kind in ('images', 'videos'):
        for e in man[kind]:
            by_src[e['src'].replace('\\', '/')] = (kind, e)
    taken = {e['name'] for k in ('images', 'videos') for e in man[k]}

    kept, added, dropped, needs_alt = 0, [], [], []

    # anything previously used but not picked now falls out
    for src, (kind, e) in list(by_src.items()):
        if src not in picks and (e.get('use') or '') != 'montage':
            man[kind].remove(e)
            dropped.append(e['name'])

    for src, slot in sorted(picks.items()):
        use = SLOT_TO_USE.get(slot)
        if not use:
            continue
        if src in by_src:
            kind, e = by_src[src]
            if e.get('use') != use:
                e['use'] = use
            kept += 1
            continue
        ext = os.path.splitext(src)[1].lower()
        kind = 'videos' if ext in VID_EXT else 'images'
        name = stem(src, slot, taken)
        entry = {'src': src, 'name': name, 'use': use, 'alt': ''}
        if kind == 'videos':
            entry['trim'] = [0, 10]
        man[kind].append(entry)
        added.append(name)
        needs_alt.append((name, src))

    json.dump(man, open(MAN, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

    print('kept %d, added %d, dropped %d' % (kept, len(added), len(dropped)))
    if dropped:
        print('dropped:', ', '.join(dropped))
    if needs_alt:
        print('\nNEEDS ALT TEXT - describe what is in each frame before publishing:')
        for name, src in needs_alt:
            print('  %-22s %s' % (name, src))
    print('\nthen:  python3 tools/derive.py && python3 tools/gen_index.py')


main()
