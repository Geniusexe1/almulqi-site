"""Build a local page for hand-picking which photographs go where.

    python3 tools/gen_picker.py
    then open tools/picker/picker.html in a browser

Every file in the source folder gets a thumbnail and a slot dropdown. Choices
are saved in the browser as you go, so closing the tab does not lose them.
"Download picks.json" writes the file; drop it next to this script and run
    python3 tools/apply_picks.py
to fold the choices into tools/manifest.json.

The index is inlined into the HTML rather than fetched, because a page opened
from file:// cannot fetch a sibling JSON file — Chrome blocks it as
cross-origin. Thumbnails are ordinary <img src> paths, which do work.
"""
import json, os, subprocess
from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC    = 'C:/Users/Belal/Desktop/pics'
OUT    = os.path.join(ROOT, 'tools', 'picker')
THUMBS = os.path.join(OUT, 'thumbs')
FFMPEG = 'C:/Program Files/ShareX/ffmpeg.exe'
IMG_EXT = {'.jpg', '.jpeg', '.heic', '.png'}
VID_EXT = {'.mov', '.mp4'}
SKIP_DIRS = {'solo', 'solo_1', 'solo_2'}

SLOTS = [
    ('unused',    'Not used'),
    ('hero',      'Hero photo'),
    ('montage',   'Photo strip'),
    ('riyadh',    'Journey: Riyadh'),
    ('ankara',    'Journey: Ankara'),
    ('daejeon',   'Journey: Daejeon'),
    ('robonexus', 'Work: ROBONEXUS'),
    ('drone',     'Work: Drone'),
    ('car',       'Work: Racing car'),
    ('caricature','Work: Caricature robot'),
    ('personal',  'Off the clock'),
]


def collect():
    files = []
    for dirpath, dirnames, names in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for n in sorted(names):
            rel = os.path.relpath(os.path.join(dirpath, n), SRC).replace('\\', '/')
            ext = os.path.splitext(n)[1].lower()
            if ext in IMG_EXT or ext in VID_EXT:
                files.append((rel, ext))
    return files


def thumb(rel, ext):
    key = rel.replace('/', '__').replace(' ', '_')
    dst = os.path.join(THUMBS, key + '.jpg')
    if os.path.exists(dst):
        return os.path.basename(dst)
    src = os.path.join(SRC, rel)
    try:
        if ext in VID_EXT:
            tmp = dst + '.src.jpg'
            subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', '1', '-i', src,
                            '-frames:v', '1', '-vf', 'scale=400:-2', tmp],
                           capture_output=True)
            if not os.path.exists(tmp):
                return None
            im = Image.open(tmp).convert('RGB')
        else:
            im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
        im.thumbnail((400, 400), Image.LANCZOS)
        im.save(dst, 'JPEG', quality=78)
        if ext in VID_EXT and os.path.exists(dst + '.src.jpg'):
            os.remove(dst + '.src.jpg')
        return os.path.basename(dst)
    except Exception as e:
        print('  thumb failed', rel, e)
        return None


def current_assignments():
    """Pre-select whatever the manifest already uses, so the picker opens
    showing the current state rather than a blank slate."""
    p = os.path.join(ROOT, 'tools', 'manifest.json')
    if not os.path.exists(p):
        return {}
    man = json.load(open(p, encoding='utf-8'))
    out = {}
    for e in man.get('images', []) + man.get('videos', []):
        use = (e.get('use') or '')
        slot = 'unused'
        if use == 'hero': slot = 'hero'
        elif use.startswith('journey:'):
            slot = {'saudi': 'riyadh', 'turkiye': 'ankara', 'korea': 'daejeon'}.get(
                use.split(':')[1], 'unused')
        elif use.startswith('project:'):
            slot = {'robonexus': 'robonexus', 'autonomous-drone': 'drone',
                    'racing-car': 'car', 'caricature-robot': 'caricature'}.get(
                use.split(':')[1], 'unused')
        elif use == 'personal': slot = 'personal'
        out[e['src'].replace('\\', '/')] = slot
    return out


def main():
    os.makedirs(THUMBS, exist_ok=True)
    files = collect()
    pre = current_assignments()
    items = []
    for i, (rel, ext) in enumerate(files):
        t = thumb(rel, ext)
        if not t:
            continue
        items.append({'src': rel, 'thumb': 'thumbs/' + t,
                      'kind': 'video' if ext in VID_EXT else 'image',
                      'slot': pre.get(rel, 'unused')})
        if (i + 1) % 25 == 0:
            print('  %d/%d' % (i + 1, len(files)), flush=True)

    html = PAGE.replace('__DATA__', json.dumps(items))
    html = html.replace('__SLOTS__', json.dumps(SLOTS))
    dst = os.path.join(OUT, 'picker.html')
    open(dst, 'w', encoding='utf-8', newline='\n').write(html)
    print('\n%d files -> %s' % (len(items), dst))
    print('open that in a browser, pick, then Download picks.json')


PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pick the photos</title>
<style>
  :root { --bg:#151814; --panel:#1e221c; --ink:#eef0e8; --dim:#a9b0a2; --acc:#dcab5c; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 "Segoe UI",system-ui,sans-serif; }
  header { position:sticky; top:0; z-index:9; background:var(--panel);
           border-bottom:1px solid #333a30; padding:.75rem 1rem;
           display:flex; gap:1rem; align-items:center; flex-wrap:wrap; }
  h1 { font-size:1rem; margin:0; letter-spacing:.12em; text-transform:uppercase; }
  .counts { color:var(--dim); font-size:.85rem; }
  button { background:var(--acc); color:#1a1a15; border:0; padding:.5rem .9rem;
           font-weight:700; cursor:pointer; border-radius:3px; }
  button.ghost { background:transparent; color:var(--ink); border:1px solid #3c463a; }
  select { background:#11140f; color:var(--ink); border:1px solid #39422f;
           padding:.35rem; width:100%; border-radius:3px; }
  #filter { background:#11140f; color:var(--ink); border:1px solid #39422f;
            padding:.4rem .6rem; border-radius:3px; }
  .grid { display:grid; gap:.9rem; padding:1rem;
          grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); }
  figure { margin:0; background:var(--panel); border:1px solid #2c332a;
           border-radius:4px; overflow:hidden; }
  figure.set { border-color:var(--acc); }
  .ph { aspect-ratio:1; background:#0d0f0b; display:grid; place-items:center; }
  .ph img { width:100%; height:100%; object-fit:contain; }
  figcaption { padding:.5rem; }
  .fn { font:11px/1.35 ui-monospace,Consolas,monospace; color:var(--dim);
        word-break:break-all; margin-bottom:.4rem; height:2.7em; overflow:hidden; }
  .vid { position:absolute; margin:6px; background:#000a; padding:1px 5px;
         font-size:10px; letter-spacing:.1em; border-radius:2px; }
  textarea { width:100%; height:130px; background:#11140f; color:var(--ink);
             border:1px solid #39422f; font:12px ui-monospace,monospace; padding:.5rem; }
  .wrap { padding:0 1rem 2rem; }
</style></head><body>
<header>
  <h1>Pick the photos</h1>
  <span class="counts" id="counts"></span>
  <input id="filter" placeholder="filter by name or slot">
  <button id="dl">Download picks.json</button>
  <button class="ghost" id="show">Show JSON</button>
  <button class="ghost" id="reset">Reset to current site</button>
</header>
<div class="wrap"><textarea id="json" hidden readonly></textarea></div>
<div class="grid" id="grid"></div>
<script>
var ITEMS = __DATA__, SLOTS = __SLOTS__, KEY = 'almulqi-picks';
var saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
ITEMS.forEach(function (it) { if (saved[it.src]) it.slot = saved[it.src]; });

function save() {
  var o = {};
  ITEMS.forEach(function (it) { if (it.slot !== 'unused') o[it.src] = it.slot; });
  localStorage.setItem(KEY, JSON.stringify(o));
  var n = Object.keys(o).length;
  document.getElementById('counts').textContent = n + ' of ' + ITEMS.length + ' assigned';
  return o;
}

function draw() {
  var q = (document.getElementById('filter').value || '').toLowerCase();
  var g = document.getElementById('grid');
  g.innerHTML = '';
  ITEMS.forEach(function (it, i) {
    if (q && it.src.toLowerCase().indexOf(q) < 0 && it.slot.indexOf(q) < 0) return;
    var f = document.createElement('figure');
    if (it.slot !== 'unused') f.className = 'set';
    var opts = SLOTS.map(function (s) {
      return '<option value="' + s[0] + '"' + (s[0] === it.slot ? ' selected' : '') +
             '>' + s[1] + '</option>';
    }).join('');
    f.innerHTML =
      (it.kind === 'video' ? '<span class="vid">VIDEO</span>' : '') +
      '<div class="ph"><img loading="lazy" src="' + it.thumb + '" alt=""></div>' +
      '<figcaption><div class="fn">' + it.src + '</div>' +
      '<select data-i="' + i + '">' + opts + '</select></figcaption>';
    g.appendChild(f);
  });
  g.onchange = function (e) {
    var s = e.target;
    if (s.tagName !== 'SELECT') return;
    ITEMS[+s.dataset.i].slot = s.value;
    s.closest('figure').className = s.value === 'unused' ? '' : 'set';
    save();
  };
  save();
}

document.getElementById('filter').oninput = draw;
document.getElementById('dl').onclick = function () {
  var blob = new Blob([JSON.stringify(save(), null, 2)], {type: 'application/json'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'picks.json';
  document.body.appendChild(a); a.click(); a.remove();
};
document.getElementById('show').onclick = function () {
  var t = document.getElementById('json');
  t.hidden = !t.hidden; t.value = JSON.stringify(save(), null, 2); t.select();
};
document.getElementById('reset').onclick = function () {
  localStorage.removeItem(KEY); location.reload();
};
draw();
</script></body></html>'''


main()
