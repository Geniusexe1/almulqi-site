"""Emit index.html from assets/media.json.

    python3 tools/gen_index.py

Every photograph needs a <picture> with three formats, up to three widths, and
an object-position aimed at the faces in it. Hand-writing forty of those is how
wrong srcset attributes and cropped-off heads get shipped. The OUTPUT is plain
HTML with no build step; re-running overwrites index.html.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(ROOT, 'assets', 'media.json'), encoding='utf-8'))


def esc(s):
    return (s or '').replace('"', '&quot;')


def obj_pos(e):
    """Where a cover-crop should aim. derive.py finds the faces; without one it
    falls back slightly above centre, where subjects usually sit."""
    p = e.get('pos') or [50, 42]
    return 'object-position:%d%% %d%%' % (p[0], p[1])


def pic(name, sizes, cls='', lazy=True, ratio=None, extra=''):
    e = M[name]
    ws = e['widths']
    def ss(ext):
        return ', '.join('assets/img/%s-%d.%s %dw' % (name, w, ext, w) for w in ws)
    mid = ws[min(1, len(ws) - 1)]
    style = 'background-color:%s' % e['avg']
    if ratio:
        style += ';aspect-ratio:%s' % ratio
    return (
        '<span class="shot %s" style="%s"%s>\n'
        '        <picture>\n'
        '          <source type="image/avif" srcset="%s" sizes="%s">\n'
        '          <source type="image/webp" srcset="%s" sizes="%s">\n'
        '          <img src="assets/img/%s-%d.jpg" srcset="%s" sizes="%s"\n'
        '               width="%d" height="%d" alt="%s"%s decoding="async" style="%s">\n'
        '        </picture>\n'
        '      </span>' % (
            cls, style, extra, ss('avif'), sizes, ss('webp'), sizes,
            name, mid, ss('jpg'), sizes, e['w'], e['h'], esc(e['alt']),
            ' loading="lazy"' if lazy else '', obj_pos(e))
    )


def hero_img(name):
    e = M[name]
    ws = e['widths']
    def ss(ext):
        return ', '.join('assets/img/%s-%d.%s %dw' % (name, w, ext, w) for w in ws)
    return (
        '<picture>\n'
        '            <source type="image/avif" srcset="%s" sizes="100vw">\n'
        '            <source type="image/webp" srcset="%s" sizes="100vw">\n'
        '            <img src="assets/img/%s-%d.jpg" srcset="%s" sizes="100vw"\n'
        '                 width="%d" height="%d" alt="%s" fetchpriority="high"\n'
        '                 decoding="async" style="%s">\n'
        '          </picture>' % (
            ss('avif'), ss('webp'), name, ws[-1], ss('jpg'),
            e['w'], e['h'], esc(e['alt']), obj_pos(e))
    )


def poster(name, cls='', extra='', ratio=None):
    """A video's poster frame used as a still."""
    e = M[name]
    style = 'background-color:%s' % e['avg']
    if ratio:
        style += ';aspect-ratio:%s' % ratio
    return ('<span class="shot %s" style="%s"%s>\n'
            '          <img src="assets/video/%s-poster.jpg" width="%d" height="%d"\n'
            '               alt="%s" loading="lazy" decoding="async" style="%s">\n'
            '        </span>' % (cls, style, extra, name, e['w'], e['h'],
                                 esc(e['alt']), obj_pos(e)))


def cluster_item(name, cls):
    e = M[name]
    if e['kind'] == 'video':
        return poster(name, cls)
    if e['kind'] == 'render':
        return ('<span class="shot %s" style="background-color:#dfe2d8">\n'
                '          <img src="assets/img/%s.png" width="%d" height="%d"\n'
                '               alt="%s" loading="lazy" decoding="async"\n'
                '               style="object-fit:contain;padding:6%%">\n'
                '        </span>' % (cls, name, e['w'], e['h'], esc(e['alt'])))
    return pic(name, '(max-width:900px) 90vw, 42vw', cls)


def any_shot(name, sizes, cls='', ratio=None, extra=''):
    return (poster(name, cls, extra, ratio) if M[name]['kind'] == 'video'
            else pic(name, sizes, cls, ratio=ratio, extra=extra))


STOPS = [
    dict(id='riyadh', place='Riyadh', when='to 2024', country='Saudi Arabia',
         bg='saudi-podium', wipe='right', dark='left', side='left',
         lede='School, and the first things I built for other people rather than for myself.',
         facts=['Valedictorian, ranked 1st in the graduating class',
                'Highest mark in the world, AS-Level Chemistry',
                'Highest mark in Saudi Arabia, A-Level Physics',
                "Founded the school's first student club, and ran its PC-building workshops",
                'Hosted the graduation ceremony to an audience of over a thousand'],
         shots=['saudi-graduation', 'saudi-stage', 'saudi-pcbuild-1', 'saudi-img-0947']),
    dict(id='ankara', place='Ankara', when='Oct 2024 - Jan 2025', country='T&uuml;rkiye',
         bg='ankara-snow', wipe='left', dark='right', side='right',
         lede='One semester at Middle East Technical University, in a language and a city I did not know.',
         facts=['Electrical Engineering, ODT&Uuml;',
                'GPA 3.55 / 4.0 &mdash; High Honours'],
         shots=['ankara-lecture', 'ankara-f1', 'ankara-img-5856', 'ankara']),
    dict(id='daejeon', place='Daejeon', when='Feb 2025 &mdash;', country='South Korea',
         bg='korea-blossom', wipe='top', dark='bottom', side='bottom',
         lede='KAIST, a double degree, and the point where the projects got serious.',
         facts=['Mechanical + Electrical Engineering, expected Feb 2029',
                'Micro-Robotics club since March 2025',
                'Project lead on ROBONEXUS &mdash; &#8361;6,000,000 secured',
                'KAIST Ambassador &mdash; presented KAIST back home in Saudi Arabia',
                'Robotics research intern at the FAIR Lab since August 2026'],
         shots=['kaist-ambassador', 'car-bench', 'life-bike', 'life-statue']),
]

ROBONEXUS = dict(
    href='projects/robonexus.html', title='ROBONEXUS', role='Project lead',
    text='A mecanum-wheeled robot for a capture-the-flag competition: collect flags, cross a '
         'barrier through a 600&nbsp;mm gate, deliver them &mdash; the first 45 seconds with no '
         'driver. I designed the machine, built the simulation, and trained the flag detector on '
         '5,001 synthetic renders because no footage of the venue exists.',
    dims=[('&#8361;6,000,000', 'funding secured'), ('0.940', 'detector mAP@50'), ('9.51', 'kg, aluminium')],
    cluster=[('robot-iso', 'c1'), ('robonexus-unity', 'c2'), ('robonexus-sim', 'c3')])

CARICATURE = dict(
    href='projects/caricature-robot.html', title='Caricature drawing robot', role='Software',
    text='A dead 3D printer stripped for its steppers and rebuilt as a plotter that draws your '
         'face back at you. The interesting part is between the photo and the pen: the portrait '
         'becomes a graph, and Dijkstra orders the strokes so the pen spends its time drawing '
         'instead of travelling.',
    dims=[('3', 'axes: X, Y, pen up/down'), ('Dijkstra', 'stroke ordering'), ('ESP32', 'G-code over Wi-Fi')],
    cluster=[('caricature-output', 'c1'), ('caricature-drawing', 'c2'), ('caricature-portrait', 'c3')])

DRONE = dict(
    href='projects/autonomous-drone.html', title='Autonomous drone', role='EE478',
    text='A quadrotor that flies a whole mission alone: read a riddle, hand it to a language '
         'model, pick the gate the answer points to, avoid what is in the way, then find one '
         'storefront from the air and land on it. Knowing its own altitude turned out to be the '
         'hard part.',
    dims=[('6', 'gates, 3 decision pairs'), ('0.70', 'm cruise altitude'), ('13', 'm of drift, fixed')],
    cluster=[('drone-hardware', 'c1'), ('drone-course', 'c2'), ('drone-reprojection', 'c3')])

CAR = dict(
    href='projects/racing-car.html', title='Self-driving racing car', role='ME209 &middot; solo',
    text='A Raspberry Pi car I built end to end. It follows a white line to the grid under a '
         'convolutional network, waits for the lights, then hands over to a PID loop on '
         'ultrasonic range to race a walled circuit. Two control paradigms, one vehicle, '
         'swapping mid-run.',
    dims=[('2', 'controllers, one handoff'), ('CNN', 'line following, PyTorch'), ('PID', 'wall keeping, ultrasound')],
    cluster=[('car-bench', 'c1'), ('car-racing', 'c2'), ('car-line', 'c3')])

STRAND = dict(
    kicker='KAIST Micro-Robotics Club', title='MR', banner='mr-banner',
    text='I joined MR in March 2025 and have built two robots with it. It is also where I first '
         'had to raise money, run a team and answer for a schedule rather than just write the code.',
    bundles=[ROBONEXUS, CARICATURE])

LOOSE = [DRONE, CAR]

MONTAGE_A = ['hero-snow', 'saudi-graduation', 'korea-summit', 'life-statue',
             'life-img-0910', 'caricature-portrait', 'shot-img-1245']
MONTAGE_B = ['saudi-stage', 'life-bike', 'ankara-lecture', 'shot-img-0188',
             'saudi-street', 'shot-img-1493', 'life-beach']

LIFE = ['life-friends-meal', 'life-flatbread', 'life-kitchen', 'life-dinner',
        'life-cinnamon', 'life-bike', 'life-img-0910', 'life-beach',
        'life-table', 'life-buns', 'life-statue', 'life-dsc-0617']

HEAD = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Abdullah Al Mulqi &mdash; Robotics Engineer</title>
<meta name="description" content="Robotics engineer at KAIST, double degree in mechanical and electrical engineering. Autonomous drones, mobile robots, perception and navigation. Research intern at the FAIR Lab.">
<link rel="canonical" href="https://almulqi.com/">
<meta property="og:type" content="website">
<meta property="og:url" content="https://almulqi.com/">
<meta property="og:title" content="Abdullah Al Mulqi - Robotics Engineer">
<meta property="og:description" content="Autonomous drones, mobile robots, and the software that makes them work. Riyadh to Ankara to Daejeon.">
<meta property="og:image" content="https://almulqi.com/assets/img/hero-talk-1920.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' fill='%23eceee6'/><path d='M3 13V3h10' fill='none' stroke='%230e110c' stroke-width='1.6'/><circle cx='11' cy='11' r='2' fill='%237a4b0d'/></svg>">
<link rel="preload" as="image" href="assets/img/hero-snow-1920.avif" type="image/avif" fetchpriority="high">
<link rel="stylesheet" href="assets/css/site.css">
<link rel="stylesheet" href="assets/css/acts.css">
<script>
/* Add js before first paint so animated content never flashes in and then
   collapses. The timer is a failsafe: if site.js never runs (blocked, 404,
   parse error) it strips the class again so the page is readable rather than
   invisible. */
(function(d){d.className+=' js';setTimeout(function(){
  if(d.className.indexOf('js-ready')<0){d.classList.remove('js');}
},2500);})(document.documentElement);
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Person","name":"Abdullah Al Mulqi",
 "url":"https://almulqi.com/","jobTitle":"Robotics Engineer",
 "alumniOf":[{"@type":"CollegeOrUniversity","name":"Korea Advanced Institute of Science and Technology (KAIST)"},
             {"@type":"CollegeOrUniversity","name":"Middle East Technical University"}],
 "knowsAbout":["Robotics","Autonomous drones","ROS","Computer vision","SLAM","Control systems"]}
</script>
</head>
<body>

<a class="skip" href="#main">Skip to content</a>
<div class="progress" aria-hidden="true"></div>

<header class="site-header">
  <div class="wrap">
    <a class="wordmark" href="/">
      <svg class="axis-mark" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path d="M3 15 V3" stroke="#3f9d4a" stroke-width="1.8"/>
        <path d="M3 15 H15" stroke="#c0442f" stroke-width="1.8"/>
        <circle cx="3" cy="15" r="1.8" fill="currentColor"/>
      </svg>
      Abdullah Al Mulqi
    </a>
    <nav class="site-nav" aria-label="Sections">
      <a href="#journey">Journey</a>
      <a href="#work" class="nav-keep">Work</a>
      <a href="#skills">Skills</a>
      <a href="#contact" class="nav-keep">Contact</a>
    </nav>
  </div>
</header>

<main id="main">'''

TAIL = '''
</main>

<footer class="site-footer">
  <div class="wrap">
    <span>Abdullah Al Mulqi &mdash; Daejeon, Korea</span>
  </div>
</footer>

<script src="assets/js/site.js" defer></script>
</body>
</html>'''


def bundle_html(b):
    cl = '\n        '.join(cluster_item(n, c) for n, c in b['cluster'])
    return '''<a class="bundle reveal" href="%s">
        <div>
          <div class="project-head">
            <h3 class="bundle-title">%s</h3>
            <span class="bundle-role">%s</span>
          </div>
          <p>%s</p>
          <span class="more">Read the case study</span>
        </div>
        <div class="cluster">
        %s
        </div>
      </a>''' % (b['href'], b['title'], b['role'], b['text'], cl)


def main():
    out = [HEAD]
    A = out.append

    # ------------------------------------------------------------------ act 1
    A('''
  <!-- ============ ACT 1 - HERO ============ -->
  <section class="act-hero" id="top" data-scrub="pin" aria-label="Introduction">
    <div class="hero-pin">
      <div class="hero-shot hero-shot--a">
        %s
      </div>
      <div class="hero-shot hero-shot--b">
        %s
      </div>
      <div class="hero-scrim"></div>
      <h1 class="hero-name"><span>ABDULLAH</span></h1>
      <div class="hero-foot">
        <div>
          <h2>AL MULQI</h2>
          <p>I build autonomous robots &mdash; drones and ground vehicles &mdash; and the
             perception, navigation and control software that makes them do
             something useful with nobody holding the sticks.</p>
        </div>
        <div class="right"><span class="scroll-cue">Scroll</span></div>
      </div>
    </div>
  </section>''' % (hero_img('hero-snow'), hero_img('hero-talk')))

    # ------------------------------------------------------------------ act 2
    rows = []
    for cls, names in (('a', MONTAGE_A), ('b', MONTAGE_B)):
        shots = '\n      '.join(
            any_shot(n, '(max-width:700px) 45vw, 24vw',
                     'wide' if M[n]['w'] > M[n]['h'] else '')
            for n in names)
        rows.append('<div class="montage-row montage-row--%s">\n      %s\n    </div>' % (cls, shots))
    A('''
  <!-- ============ ACT 2 - MONTAGE ============ -->
  <section class="act-montage" data-scrub aria-label="Photographs">
    %s
  </section>''' % '\n    '.join(rows))

    # ------------------------------------------------------------------ act 3
    bgs, shades, stages, dots = [], [], [], []
    for i, st in enumerate(STOPS):
        bgs.append(any_shot(st['bg'], '100vw',
                            extra=' data-i="%d" data-wipe="%s"' % (i, st['wipe'])))
        shades.append('<div class="j-shade" data-i="%d" data-dark="%s"></div>'
                      % (i, st['dark']))
        dots.append('<span class="dot"></span>')
        shots = '\n            '.join(
            any_shot(n, '(max-width:900px) 30vw, 10vw', ratio='3/4') for n in st['shots'])
        facts = '\n              '.join('<li>%s</li>' % f for f in st['facts'])
        stages.append('''<article class="j-stage" data-i="%d" data-side="%s" id="stop-%s">
          <p class="j-meta">%s &middot; %s</p>
          <h3 class="j-city"><span><b>%s</b></span></h3>
          <div class="j-panel">
            <p>%s</p>
            <ul class="j-facts">
              %s
            </ul>
            <div class="j-shots">
            %s
            </div>
          </div>
        </article>''' % (i, st['side'], st['id'], st['when'], st['country'],
                        st['place'], st['lede'], facts, shots))

    A('''
  <!-- ============ ACT 3 - THE JOURNEY ============ -->
  <section class="act-journey" id="journey" data-scrub="pin" data-stage="0"
           aria-labelledby="journey-h">
    <h2 id="journey-h" class="visually-hidden">The journey</h2>
    <div class="journey-pin">
      <div class="j-bg" aria-hidden="true">
        %s
      </div>
      %s
      <div class="j-stages">
        %s
      </div>
      <div class="j-dots" aria-hidden="true">
        %s
        <span class="j-blob"></span>
      </div>
    </div>
  </section>''' % ('\n        '.join(bgs), '\n      '.join(shades),
                  '\n        '.join(stages), '\n        '.join(dots)))

    # ------------------------------------------------------------------ act 4
    strand = '''<section class="strand reveal">
        <div class="strand-banner">
          %s
          <div class="veil"></div>
          <div class="strand-text">
            <span class="strand-kicker">%s</span>
            <h3>%s</h3>
            <p>%s</p>
          </div>
        </div>
        <div class="bundles">
        %s
        </div>
      </section>''' % (
        any_shot(STRAND['banner'], '(max-width:1180px) 100vw, 1180px'),
        STRAND['kicker'], STRAND['title'], STRAND['text'],
        '\n        '.join(bundle_html(b) for b in STRAND['bundles']))

    A('''
  <!-- ============ ACT 4 - THE WORK ============ -->
  <section class="section act-work" id="work" aria-labelledby="work-h">
    <div class="wrap">
      <div class="section-head reveal">
        <h2 id="work-h">The work</h2>
        <span class="ref">Four builds &middot; 2025&ndash;2026</span>
      </div>
      <div class="bundles">
      %s
      </div>
      %s
    </div>
  </section>''' % ('\n      '.join(bundle_html(b) for b in LOOSE), strand))

    # ------------------------------------------------------------------ act 5
    life = '\n      '.join(pic(n, '(max-width:700px) 46vw, 22vw', ratio='4/3') for n in LIFE)

    A('''
  <!-- ============ ACT 5 - DOSSIER ============ -->
  <section class="section act-dossier" id="now" aria-labelledby="now-h">
    <div class="wrap">
      <div class="now reveal">
        <h2 id="now-h"><span class="pulse" aria-hidden="true"></span>Currently</h2>
        <div>
          <p class="role"><strong>Robotics research intern, FAIR Lab</strong> (Field AI and Robotics) &mdash; since August 2026.</p>
          <p>Mobile robots and mesh networking, and porting the lab&rsquo;s stack from ROS&nbsp;1 to ROS&nbsp;2.
             Alongside it I lead the ROBONEXUS robot team at KAIST&rsquo;s Micro-Robotics club.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="skills" aria-labelledby="skills-h">
    <div class="wrap">
      <div class="section-head reveal">
        <h2 id="skills-h">What I work with</h2>
        <span class="ref">Used on shipped builds</span>
      </div>
      <div class="skills">
        <div class="skill reveal"><h3>Robotics &amp; autonomy</h3><ul>
          <li>ROS 1</li><li>ROS 2</li><li>Gazebo</li><li>URDF / xacro</li><li>SLAM</li>
          <li>Visual odometry</li><li>EKF sensor fusion</li><li>A* planning</li><li>PID control</li><li>TF</li></ul></div>
        <div class="skill reveal"><h3>Perception &amp; ML</h3><ul>
          <li>PyTorch</li><li>YOLO</li><li>OpenCV</li><li>Stereo depth</li><li>AprilTag</li>
          <li>Synthetic data (Unity Perception)</li><li>ONNX</li><li>TensorRT</li></ul></div>
        <div class="skill reveal"><h3>Programming</h3><ul>
          <li>Python</li><li>C</li><li>Bash</li><li>NumPy</li><li>Pandas</li><li>React</li></ul></div>
        <div class="skill reveal"><h3>Hardware</h3><ul>
          <li>Jetson Orin</li><li>Raspberry Pi 5</li><li>Hailo-8 AI HAT</li><li>ESP32</li><li>Arduino</li>
          <li>RealSense depth cameras</li><li>Stepper &amp; servo drive</li><li>PX4 / MAVROS</li></ul></div>
        <div class="skill reveal"><h3>Design &amp; tooling</h3><ul>
          <li>SolidWorks</li><li>Fusion 360</li><li>Linux</li><li>Docker</li><li>Git</li><li>Unity</li></ul></div>
        <div class="skill reveal"><h3>Also</h3><ul>
          <li>Networking</li><li>Self-hosted servers</li><li>Video editing</li><li>PC building</li></ul></div>
      </div>
    </div>
  </section>

  <section class="section" id="personal" aria-labelledby="personal-h">
    <div class="wrap">
      <div class="section-head reveal">
        <h2 id="personal-h">Off the clock</h2>
        <span class="ref">The other half</span>
      </div>
      <div class="personal-copy reveal">
        <p>I game, and I run the servers I game on &mdash; which is where the networking and
           Linux on my skills list actually came from. Nothing teaches you DNS and port
           forwarding like a friend saying they can&rsquo;t connect.</p>
        <p>I cook, a lot. I like bikes. And I am genuinely interested in the business side
           of engineering, not just the build &mdash; writing the ROBONEXUS proposal and
           walking away with &#8361;6,000,000 was one of the more satisfying things I have
           done, and it was not a technical problem.</p>
      </div>
      <div class="life-grid reveal">
      %s
      </div>
    </div>
  </section>

  <section class="section" id="contact" aria-labelledby="contact-h">
    <div class="wrap">
      <div class="section-head reveal">
        <h2 id="contact-h">Get in touch</h2>
        <span class="ref">Open to internships &amp; research</span>
      </div>
      <div class="contact-grid">
        <div class="reveal">
          <p class="lede">I am looking for robotics internships and research positions &mdash;
             perception, navigation and autonomy on real hardware. If you have something
             running in the field, I would like to hear about it.</p>
          <p style="margin-top:1.75rem">
            <a class="button" href="assets/cv/abdullah-al-mulqi-cv.pdf" download>Download CV
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M7 1v9M3.5 6.5 7 10l3.5-3.5M1.5 12.5h11"/></svg></a>
          </p>
        </div>
        <ul class="links reveal">
          <li><a href="#" data-email="belalabdullahmn|gmail.com">
            <span class="k">Email</span><span class="v">belalabdullahmn (at) gmail (dot) com</span></a></li>
          <li><a href="https://www.linkedin.com/in/REPLACE-ME" rel="me">
            <span class="k">LinkedIn</span><span class="v">Abdullah Al Mulqi</span></a></li>
          <li><a href="https://www.instagram.com/REPLACE-ME" rel="me">
            <span class="k">Instagram</span><span class="v">@REPLACE-ME</span></a></li>
        </ul>
      </div>
    </div>
  </section>''' % life)

    A(TAIL)
    html = '\n'.join(out)
    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8', newline='\n').write(html)
    print('wrote index.html  %.1f KB' % (len(html) / 1024))


main()
