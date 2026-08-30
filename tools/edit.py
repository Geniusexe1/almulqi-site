"""Edit the site's text in a browser, with the real page live beside it.

    python3 tools/edit.py

Opens http://127.0.0.1:8787/edit - the words on the left, the actual site on
the right. Save and the page regenerates and reloads in place, holding its
scroll position, so you see the change where it lands rather than guessing.

Nothing here ships. It binds to localhost only, and .assetsignore already keeps
tools/ and *.py out of the deploy. The editor writes tools/content.json and
re-runs gen_index.py; if the generator fails, the error comes back into the
page instead of leaving you with a half-written site.
"""
import http.server
import json
import os
import subprocess
import sys
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, 'tools', 'content.json')
GEN = os.path.join(ROOT, 'tools', 'gen_index.py')
PORT = 8787

# Which part of the page each top-level group belongs to, so selecting a field
# can scroll the preview to the thing being edited.
ANCHORS = {'hero': 'top', 'now': 'now', 'work': 'work', 'skills': 'skills',
           'journey': 'journey', 'personal': 'personal', 'contact': 'contact'}

LABELS = {'hero': 'Hero', 'now': 'Currently', 'work': 'The work',
          'skills': 'What I work with', 'journey': 'Before KAIST',
          'personal': 'Off the clock', 'contact': 'Get in touch'}


def regenerate():
    """Run the generator. Returns (ok, message)."""
    r = subprocess.run([sys.executable, GEN], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode == 0:
        return True, (r.stdout or '').strip() or 'regenerated'
    # the traceback's last line is the useful part
    err = (r.stderr or r.stdout or 'gen_index.py failed').strip()
    return False, err.splitlines()[-1] if err else 'gen_index.py failed'


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        # one line per save is useful; a line per image is not. This runs on
        # every request, so it must never raise - a throw in here kills the
        # worker thread and the request just hangs.
        try:
            line = fmt % args
        except Exception:
            return
        if '/api/' in line:
            sys.stderr.write('  %s\n' % line)

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        body = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split('?')[0] in ('/edit', '/edit/'):
            return self._send(200, PAGE, 'text/html; charset=utf-8')
        if self.path == '/api/content':
            return self._send(200, open(CONTENT, encoding='utf-8').read())
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/content':
            return self._send(404, '{"ok":false,"message":"no such endpoint"}')
        try:
            n = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception as e:
            return self._send(400, json.dumps({'ok': False, 'message': 'bad JSON: %s' % e}))

        # Write to a sibling first, then replace. A half-written content.json
        # would take the generator down with it on the next run.
        tmp = CONTENT + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, CONTENT)

        ok, message = regenerate()
        self._send(200, json.dumps({'ok': ok, 'message': message}))


PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>almulqi.com - text</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { --bg:#14160f; --panel:#1c1f17; --line:#3a3f33; --ink:#eceee6;
          --dim:#a3a998; --accent:#c98b3a; --ok:#7fb069; --bad:#d9534f; }
  * { box-sizing: border-box; }
  body { margin:0; height:100vh; display:grid; grid-template-columns:minmax(360px,34%) 1fr;
         background:var(--bg); color:var(--ink);
         font:15px/1.5 ui-monospace,"Cascadia Mono","SF Mono",Menlo,Consolas,monospace; }
  .pane { display:flex; flex-direction:column; min-height:0; border-right:1px solid var(--line); }
  header { padding:.9rem 1rem; border-bottom:1px solid var(--line); display:flex;
           align-items:center; gap:.75rem; flex-wrap:wrap; }
  h1 { font-size:.95rem; margin:0; letter-spacing:.06em; text-transform:uppercase; }
  .hint { color:var(--dim); font-size:.72rem; flex-basis:100%; }
  button { font:inherit; font-size:.8rem; padding:.4rem .8rem; cursor:pointer;
           background:var(--accent); color:#14160f; border:0; letter-spacing:.04em; }
  button:disabled { opacity:.45; cursor:default; }
  button.ghost { background:transparent; color:var(--dim); border:1px solid var(--line); }
  #status { font-size:.75rem; color:var(--dim); margin-left:auto; }
  #status.ok { color:var(--ok); } #status.bad { color:var(--bad); }
  #form { overflow-y:auto; padding:0 1rem 4rem; }
  section { margin-top:1.6rem; }
  h2 { font-size:.78rem; letter-spacing:.12em; text-transform:uppercase;
       color:var(--accent); margin:0 0 .6rem; padding-bottom:.35rem;
       border-bottom:1px solid var(--line); }
  label { display:block; margin:.85rem 0 .2rem; font-size:.7rem; letter-spacing:.08em;
          text-transform:uppercase; color:var(--dim); }
  textarea { width:100%; background:var(--panel); color:var(--ink); border:1px solid var(--line);
             padding:.5rem .6rem; font:inherit; font-size:.82rem; resize:none; overflow:hidden;
             line-height:1.55; }
  textarea:focus { outline:2px solid var(--accent); outline-offset:-2px; }
  .item { display:flex; gap:.4rem; align-items:flex-start; margin-bottom:.35rem; }
  .item textarea { flex:1; }
  .item button { background:transparent; color:var(--dim); border:1px solid var(--line);
                 padding:.3rem .5rem; line-height:1; }
  .add { margin-top:.2rem; font-size:.72rem; }
  iframe { width:100%; height:100%; border:0; background:#fff; }
  .dirty h1::after { content:" *"; color:var(--accent); }
  @media (max-width:820px) { body { grid-template-columns:1fr; grid-template-rows:1fr 1fr; } }
</style>

<div class="pane" id="pane">
  <header>
    <h1>Text</h1>
    <button id="save">Save</button>
    <button class="ghost" id="revert">Revert</button>
    <span id="status">loading</span>
    <span class="hint">Ctrl+S saves and reloads the preview. HTML entities
      (&amp;mdash; &amp;rsquo; &amp;nbsp;) are allowed and render as characters.</span>
  </header>
  <div id="form"></div>
</div>
<iframe id="preview" src="/index.html" title="Live preview"></iframe>

<script>
(function () {
  var form = document.getElementById('form');
  var statusEl = document.getElementById('status');
  var saveBtn = document.getElementById('save');
  var preview = document.getElementById('preview');
  var data = null, saved = '', dirty = false;

  var LABELS = %LABELS%;
  var ANCHORS = %ANCHORS%;

  function say(text, kind) {
    statusEl.textContent = text;
    statusEl.className = kind || '';
  }

  function mark() {
    dirty = JSON.stringify(data) !== saved;
    document.getElementById('pane').classList.toggle('dirty', dirty);
    if (dirty) say('unsaved');
  }

  function grow(t) { t.style.height = 'auto'; t.style.height = (t.scrollHeight + 2) + 'px'; }

  function nameOf(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  // Jump the preview to whatever is being edited, so a change is visible
  // without hunting for it.
  function focusPreview(anchor) {
    try {
      var doc = preview.contentWindow.document;
      var el = anchor === 'top' ? doc.body : doc.getElementById(anchor);
      if (el) el.scrollIntoView({ block: 'start' });
    } catch (e) { /* preview still loading */ }
  }

  function field(label, get, set, anchor) {
    var wrap = document.createElement('div');
    var l = document.createElement('label');
    l.textContent = label;
    var t = document.createElement('textarea');
    t.value = get();
    t.rows = 1;
    t.addEventListener('input', function () { set(t.value); grow(t); mark(); });
    t.addEventListener('focus', function () { focusPreview(anchor); });
    wrap.appendChild(l); wrap.appendChild(t);
    setTimeout(function () { grow(t); }, 0);
    return wrap;
  }

  function list(label, arr, anchor) {
    var wrap = document.createElement('div');
    var l = document.createElement('label');
    l.textContent = label + ' (' + arr.length + ')';
    wrap.appendChild(l);
    var body = document.createElement('div');
    wrap.appendChild(body);

    function draw() {
      body.textContent = '';
      l.textContent = label + ' (' + arr.length + ')';
      arr.forEach(function (v, i) {
        var row = document.createElement('div');
        row.className = 'item';
        var t = document.createElement('textarea');
        t.value = v; t.rows = 1;
        t.addEventListener('input', function () { arr[i] = t.value; grow(t); mark(); });
        t.addEventListener('focus', function () { focusPreview(anchor); });
        var x = document.createElement('button');
        x.type = 'button'; x.textContent = 'x'; x.title = 'Remove';
        x.addEventListener('click', function () { arr.splice(i, 1); draw(); mark(); });
        row.appendChild(t); row.appendChild(x);
        body.appendChild(row);
        setTimeout(function () { grow(t); }, 0);
      });
      var add = document.createElement('button');
      add.type = 'button'; add.className = 'ghost add'; add.textContent = '+ add';
      add.addEventListener('click', function () { arr.push(''); draw(); mark(); });
      body.appendChild(add);
    }
    draw();
    return wrap;
  }

  function build() {
    form.textContent = '';
    Object.keys(data).forEach(function (top) {
      if (top.charAt(0) === '_') return;          // _note is documentation
      var group = data[top];
      var anchor = ANCHORS[top] || 'top';
      var sec = document.createElement('section');
      var h = document.createElement('h2');
      h.textContent = LABELS[top] || nameOf(top);
      sec.appendChild(h);

      Object.keys(group).forEach(function (key) {
        var value = group[key];
        if (typeof value === 'string') {
          sec.appendChild(field(nameOf(key),
            function () { return group[key]; },
            function (v) { group[key] = v; }, anchor));
        } else if (Array.isArray(value)) {
          sec.appendChild(list(nameOf(key), value, anchor));
        } else if (value && typeof value === 'object') {
          // one level deeper: a project, or a stop on the journey
          var sub = document.createElement('div');
          var sh = document.createElement('label');
          sh.style.color = 'var(--ink)';
          sh.style.marginTop = '1.2rem';
          sh.textContent = '- ' + nameOf(key);
          sub.appendChild(sh);
          Object.keys(value).forEach(function (k2) {
            if (Array.isArray(value[k2])) {
              sub.appendChild(list(nameOf(k2), value[k2], anchor));
            } else {
              sub.appendChild(field(nameOf(k2),
                function () { return value[k2]; },
                function (v) { value[k2] = v; }, anchor));
            }
          });
          sec.appendChild(sub);
        }
      });
      form.appendChild(sec);
    });
  }

  function load() {
    fetch('/api/content').then(function (r) { return r.json(); }).then(function (j) {
      data = j;
      saved = JSON.stringify(data);
      build();
      say('ready');
    }).catch(function (e) { say('could not load: ' + e.message, 'bad'); });
  }

  function save() {
    saveBtn.disabled = true;
    say('saving');
    // hold the reader's place across the regenerate
    var y = 0;
    try { y = preview.contentWindow.scrollY; } catch (e) {}
    fetch('/api/content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(function (r) { return r.json(); }).then(function (j) {
      saveBtn.disabled = false;
      if (!j.ok) { say(j.message, 'bad'); return; }
      saved = JSON.stringify(data);
      mark();
      say('saved', 'ok');
      preview.addEventListener('load', function once() {
        preview.removeEventListener('load', once);
        try { preview.contentWindow.scrollTo(0, y); } catch (e) {}
      });
      preview.contentWindow.location.reload();
    }).catch(function (e) {
      saveBtn.disabled = false;
      say('save failed: ' + e.message, 'bad');
    });
  }

  saveBtn.addEventListener('click', save);
  document.getElementById('revert').addEventListener('click', function () {
    if (dirty && !confirm('Throw away unsaved changes?')) return;
    load();
  });
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  load();
})();
</script>
"""

PAGE = (PAGE.replace('%LABELS%', json.dumps(LABELS))
            .replace('%ANCHORS%', json.dumps(ANCHORS)))


def main():
    ok, message = regenerate()
    print('generator:', message)
    url = 'http://127.0.0.1:%d/edit' % PORT
    server = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    server.daemon_threads = True
    print('\n  editing %s' % os.path.relpath(CONTENT, ROOT))
    print('  open    %s' % url)
    print('  stop    Ctrl+C\n')
    if '--no-open' not in sys.argv:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped. index.html is written; commit and push when you are happy.')


if __name__ == '__main__':
    main()
