/* almulqi.com — the only script on the site.
 *
 * It does four things: assemble the email address, drive the scroll journey,
 * place the mission rail, and mark the section you are in.
 *
 * The animation strategy: JavaScript never animates anything. It writes two
 * plain numbers onto elements — --e (entry progress) and --p (travel
 * progress) — and CSS does the rest with transform and opacity, which the
 * browser runs on the compositor without touching layout. Every frame reads
 * all the geometry first and writes afterwards, so the browser is never
 * forced into a synchronous re-layout partway through the loop.
 */
(function () {
  'use strict';

  var root = document.documentElement;

  /* Tell the stylesheet the script is alive. The inline snippet in <head> adds
     `js` before first paint (so nothing flashes visible then collapses), and
     arms a timer that strips it again if we never get here — otherwise a
     failed script load would leave the whole page invisible. */
  root.className += ' js-ready';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  /* --- email, assembled at runtime --------------------------------------
     Split across a data attribute so a scraper reading the HTML source does
     not get a usable address. Without JS the visible text still tells a human
     what it is; it just is not clickable. */
  Array.prototype.forEach.call(
    document.querySelectorAll('a[data-email]'),
    function (a) {
      var parts = a.getAttribute('data-email').split('|');
      if (parts.length !== 2) return;
      var address = parts[0] + '@' + parts[1];
      a.href = 'mailto:' + address;
      var v = a.querySelector('.v');
      if (v) v.textContent = address;
    }
  );

  /* --- what moves -------------------------------------------------------- */

  var revealEls = [].slice.call(document.querySelectorAll('.reveal, .reveal-x'));
  var scrubEls  = [].slice.call(document.querySelectorAll('[data-scrub]'));
  var heroScrub = document.querySelector('[data-scrub="page"]');
  var heroIndex = scrubEls.indexOf(heroScrub);

  /* The route path is the single source of truth for both the trail and the
     robot's position, so the two can never disagree. */
  var route = document.querySelector('.arena .route');
  var botCarrier = document.querySelector('.bot-carrier');
  var arena = document.querySelector('.arena');
  var routeLen = 0;
  if (route && typeof route.getTotalLength === 'function') {
    try {
      routeLen = route.getTotalLength();
      if (arena && routeLen) arena.style.setProperty('--route-len', routeLen);
    } catch (err) { routeLen = 0; }
  }

  /* Resolve each rail waypoint to its section once, not every frame. */
  var stops = [].slice.call(document.querySelectorAll('.rail-stops li'))
    .map(function (li) {
      return { li: li, section: document.getElementById(li.getAttribute('data-stop')) };
    })
    .filter(function (s) { return s.section; });

  function clamp01(n) { return n < 0 ? 0 : (n > 1 ? 1 : n); }

  /* --- the journey ------------------------------------------------------
     The act plays as three equal stages. `stage` says which one is on screen
     and drives every swap in CSS; --k is progress inside that stage, which
     drives the slow push-in on the photograph; --f on each progress segment
     is how full that segment is.

     Splitting stage from progress is what keeps the cuts crisp. One
     continuous number would cross-dissolve everything at once and the change
     of city would stop reading as a change, which is the point of the act. */
  var jsection = document.querySelector('.act-journey');
  var jstages = [].slice.call(document.querySelectorAll('.j-stage'));
  var jblob = document.querySelector('.j-blob');

  function journey(p) {
    if (!jsection) return;

    var n = jstages.length || 3;
    var stage = Math.floor(p * n);
    if (stage > n - 1) stage = n - 1;
    if (stage < 0) stage = 0;
    var k = p * n - stage;

    if (jsection.getAttribute('data-stage') !== String(stage)) {
      jsection.setAttribute('data-stage', String(stage));
    }
    jsection.style.setProperty('--k', k.toFixed(3));

    /* The blob rides the whole act, 0 at the first dot and 1 at the last, and
       squeezes while it travels: widest stretch halfway between two dots, back
       to a circle when it arrives. sin() gives that shape for free. */
    if (jblob) {
      jblob.style.setProperty('--jpos', p.toFixed(4));
      var squeeze = 1 + 0.85 * Math.sin(Math.PI * k);
      jblob.style.setProperty('--jsq', squeeze.toFixed(3));
    }
  }

  function placeRobot(p) {
    if (!botCarrier || !routeLen) return;
    var pt = route.getPointAtLength(p * routeLen);
    /* No rotation. At 419 mm wide in a 600 mm gate the robot physically cannot
       cross turned, so keeping it square is the honest depiction. */
    botCarrier.setAttribute('transform',
      'translate(' + pt.x.toFixed(2) + ',' + pt.y.toFixed(2) + ')');
  }

  function settle() {
    revealEls.forEach(function (el) { el.style.setProperty('--e', '1'); });
    scrubEls.forEach(function (el) { el.style.setProperty('--p', '1'); });
    root.style.setProperty('--scroll', '0');
    placeRobot(1);
    journey(1);
  }

  if (reduced.matches) {
    settle();
    wireNavHighlight();
    wireClips();
    return;
  }

  /* --- cached page metrics ----------------------------------------------- */
  /* Document height forces a layout to read, so it is measured on resize and
     load rather than every frame. */

  var vh = window.innerHeight;
  var maxScroll = 1;

  function measure() {
    vh = window.innerHeight || root.clientHeight;
    var docH = Math.max(
      document.body.scrollHeight, root.scrollHeight,
      document.body.offsetHeight, root.offsetHeight
    );
    maxScroll = Math.max(1, docH - vh);

    /* The rail is a scale drawing of the page: each waypoint sits at the point
       on the track matching where its section sits in the document. */
    var pageY = window.pageYOffset || 0;
    stops.forEach(function (s) {
      var absTop = s.section.getBoundingClientRect().top + pageY;
      s.li.style.top = (clamp01(absTop / maxScroll) * 100).toFixed(2) + '%';
    });
  }

  /* --- the frame --------------------------------------------------------- */

  var ticking = false;
  var last = {};

  function write(el, prop, value, key) {
    var v = value.toFixed(3);
    if (last[key] === v) return;      // skip writes that have not moved
    last[key] = v;
    el.style.setProperty(prop, v);
  }

  function update() {
    ticking = false;
    var scrollY = window.pageYOffset || root.scrollTop;

    /* ---- read ---- */
    /* Height is measured every frame, not just on resize. Lazy images landing
       and browser zoom both change the document height, and a stale maxScroll
       makes every progress number wrong - which is what made zooming look
       like it broke the page. It is in the read batch with everything else,
       so it costs one layout, not one per element. */
    vh = window.innerHeight || root.clientHeight;
    var docH = Math.max(document.body.scrollHeight, root.scrollHeight,
                        document.body.offsetHeight, root.offsetHeight);
    maxScroll = Math.max(1, docH - vh);
    var reveals = revealEls.map(function (el) {
      var top = el.getBoundingClientRect().top;
      // 0 when the top edge touches the bottom of the viewport,
      // 1 once it has risen a further 35% of a viewport.
      return clamp01((vh - top) / (vh * 0.35));
    });

    var scrubs = scrubEls.map(function (el) {
      var mode = el.getAttribute('data-scrub');
      if (mode === 'pin') {
        /* Progress through a section that pins itself with position:sticky.
           0 while its top is still below the viewport top, 1 once its bottom
           has arrived — which is exactly the span the sticky child is stuck
           for, so the pinned artwork and this number stay in step. */
        var rp = el.getBoundingClientRect();
        var travel = rp.height - vh;
        if (travel <= 0) return 0;
        return clamp01(-rp.top / travel);
      }
      if (mode === 'page') {
        /* Tied to the page's own scroll rather than this element's position:
           the hero is already on screen at load, so the robot has to start
           moving when the reader starts scrolling, not before. */
        return clamp01(scrollY / (vh * 0.9));
      }
      var r = el.getBoundingClientRect();
      return clamp01((vh - r.top) / (vh + r.height));
    });

    var stopTops = stops.map(function (s) {
      return s.section.getBoundingClientRect().top;
    });

    var overall = clamp01(scrollY / maxScroll);

    /* ---- write ---- */
    revealEls.forEach(function (el, i) { write(el, '--e', reveals[i], 'e' + i); });
    scrubEls.forEach(function (el, i) { write(el, '--p', scrubs[i], 'p' + i); });
    root.style.setProperty('--scroll', overall.toFixed(4));

    placeRobot(heroIndex >= 0 ? scrubs[heroIndex] : overall);

    var jt = document.querySelector('.act-journey');
    if (jt) journey(parseFloat(jt.style.getPropertyValue('--p')) || 0);

    stops.forEach(function (s, i) {
      var top = stopTops[i];
      var passed = top < vh * 0.5;
      var active = passed && top > -s.section.offsetHeight + vh * 0.4;
      if (passed) s.li.setAttribute('data-passed', ''); else s.li.removeAttribute('data-passed');
      if (active) s.li.setAttribute('data-active', ''); else s.li.removeAttribute('data-active');
    });
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(update);
  }

  /* --- nav current-section highlight ------------------------------------- */

  function wireNavHighlight() {
    var navLinks = [].slice.call(document.querySelectorAll('.site-nav a[href*="#"]'));
    if (!navLinks.length || !('IntersectionObserver' in window)) return;
    var byId = {};
    navLinks.forEach(function (a) {
      var id = a.getAttribute('href').split('#')[1];
      if (id) byId[id] = a;
    });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var link = byId[entry.target.id];
        if (!link || !entry.isIntersecting) return;
        navLinks.forEach(function (a) { a.removeAttribute('aria-current'); });
        link.setAttribute('aria-current', 'page');
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    Object.keys(byId).forEach(function (id) {
      var s = document.getElementById(id);
      if (s) spy.observe(s);
    });
  }

  /* --- clips play only while they are on screen --------------------------
     They are muted, looping and preload="none", so nothing downloads until a
     clip is actually about to be seen, and nothing keeps decoding once it has
     scrolled away. */
  function wireClips() {
    var vids = [].slice.call(document.querySelectorAll('video[loop]'));
    if (!vids.length) return;
    if (reduced.matches || !('IntersectionObserver' in window)) {
      vids.forEach(function (v) { v.setAttribute('controls', ''); });
      return;
    }
    var vo = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var v = e.target;
        if (e.isIntersecting) {
          if (v.preload === 'none') v.preload = 'auto';
          var pr = v.play();
          if (pr && pr.catch) pr.catch(function () {
            v.setAttribute('controls', '');   // autoplay refused: give the reader the control
          });
        } else if (!v.paused) {
          v.pause();
        }
      });
    }, { rootMargin: '10% 0px', threshold: 0.25 });
    vids.forEach(function (v) { vo.observe(v); });
  }

  /* --- go ---------------------------------------------------------------- */

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', function () { measure(); onScroll(); });
  window.addEventListener('load', function () { measure(); update(); });

  /* Browser zoom does not always surface as a window resize, and images
     finishing their load changes the document height without any event at
     all. Watching the body covers both. */
  if ('ResizeObserver' in window) {
    var ro = new ResizeObserver(function () { measure(); onScroll(); });
    ro.observe(document.body);
  }
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', function () {
      measure(); onScroll();
    });
  }
  /* a late pass once everything has settled */
  setTimeout(function () { measure(); update(); }, 1200);

  /* If the reader turns reduced-motion on mid-session, stop moving at once. */
  if (typeof reduced.addEventListener === 'function') {
    reduced.addEventListener('change', function (e) {
      if (!e.matches) return;
      window.removeEventListener('scroll', onScroll);
      settle();
    });
  }

  measure();
  update();
  wireNavHighlight();
  wireClips();
})();
