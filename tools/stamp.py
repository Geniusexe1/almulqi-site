"""Tag every stylesheet, script and CV link with a hash of the file it points at.

    python3 tools/stamp.py

The CSS and JS are cached for an hour (see _headers) under names that never
change, so after a deploy a returning visitor got the new HTML with the old
stylesheet and saw new markup with no styles. A `?v=<hash>` that changes
whenever the file changes makes the browser fetch it fresh. gen_index.py runs
this after writing index.html; run it by hand after editing a case study.
"""
import hashlib, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = re.compile(r'((?:href|src)="(?:\.\./|/)?(assets/(?:css|js|cv)/[\w.-]+\.(?:css|js|pdf)))(?:\?v=\w+)?"')


def digest(rel):
    with open(os.path.join(ROOT, rel), 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


def main():
    pages = ['index.html', '404.html'] + [
        os.path.join('projects', n) for n in sorted(os.listdir(os.path.join(ROOT, 'projects')))
        if n.endswith('.html')]
    for page in pages:
        p = os.path.join(ROOT, page)
        s = open(p, encoding='utf-8').read()
        t = REF.sub(lambda m: '%s?v=%s"' % (m.group(1), digest(m.group(2))), s)
        if t != s:
            open(p, 'w', encoding='utf-8', newline='\n').write(t)
            print('stamped', page)


if __name__ == '__main__':
    main()
