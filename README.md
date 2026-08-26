# almulqi.com

Personal site. Plain HTML, CSS and about 250 lines of vanilla JavaScript — no
framework, no runtime build step, no external requests.

```
index.html                 the landing page: five acts
projects/*.html            one case study each
assets/css/site.css        tokens, type, shared components, the motion contract
assets/css/acts.css        the landing page acts only
assets/js/site.js          the whole script
assets/img/                generated derivatives (avif + webp + jpg, 3 widths)
assets/video/              trimmed, muted, tone-mapped clips + posters
assets/media.json          what the generators read: sizes, alt text, avg colour
tools/                     the pipeline (see below)
```

## Working on it

```bash
cd ~/Desktop/almulqi-site
python3 -m http.server 8000
```

Then <http://localhost:8000>. Nothing compiles — save and reload.

## The five acts

1. **Hero** — two full-bleed photographs. Scrolling cross-fades the snowfield
   into the exhibition shot while `ABDULLAH` drifts against them.
2. **Montage** — rows of photographs drifting at different rates.
3. **The journey** — Riyadh, Ankara, Daejeon. A horizontal track pinned with
   `position: sticky`, with hand-drawn SVG landmarks.
4. **The work** — four project bundles. The photo cluster fans out on hover;
   the name, role and headline figures are readable without interacting.
5. **Dossier** — currently, skills, off the clock, contact.

## How motion works

**JavaScript never animates anything.** `site.js` writes two plain numbers onto
elements and CSS does the rest with transform and opacity only, so it stays on
the compositor:

| | |
|---|---|
| `--e` | entry progress, 0 → 1 as an element rises into view |
| `--p` | travel progress, 0 → 1 — `data-scrub`, `data-scrub="page"`, or `data-scrub="pin"` |

Every frame reads all geometry first and writes afterwards, so the browser is
never forced into a mid-loop re-layout.

**If you add something that uses `--e` or `--p`, give it (or an ancestor) a
`reveal` class or a `data-scrub` attribute.** Otherwise the variable is never
set and the element sits at its start state forever — invisible, or scaled to
zero. This actually happened to four "Next" links.

The `js` class is added inline in `<head>` before first paint, and an inline
2.5-second timer strips it again unless `site.js` checks in with `js-ready`.
Without that failsafe a failed script load leaves the page blank. Do not remove it.

## The media pipeline

Nothing here runs at page load. These are one-off tools; the site is static.

```bash
python3 tools/inventory.py      # scan the source folder, read EXIF, convert HEIC
python3 tools/contact_sheet.py  # numbered thumbnail grids, for identifying files
python3 tools/derive.py         # manifest -> assets/img, assets/video, media.json
python3 tools/gen_index.py      # media.json -> index.html
python3 tools/gen_cases.py      # wire real media into projects/*.html (idempotent)
python3 tools/render_robot.py   # URDF + CAD meshes -> triangle soup
python3 tools/raster.py         # triangle soup -> orthographic robot renders
```

**To add or swap a photograph:** put it in the source folder, add an entry to
`tools/manifest.json` with a `name` and honest `alt` text, run `derive.py`, then
reference it in the markup. `gen_index.py` rewrites `index.html` wholesale, so
once you have edited that file by hand, add new images to it by hand too.

Requirements, all already present on this machine: Pillow with AVIF support,
`pillow-heif`, `rembg` (only for the hero cutout), and ffmpeg at
`C:/Program Files/ShareX/ffmpeg.exe`.

### Two things that will bite you

- **iPhone clips are 10-bit HLG HDR.** Browsers cannot decode H.264 High 10 —
  the video plays black. `derive.py` detects it and tone-maps to 8-bit SDR
  bt709. If you add a clip by hand, do the same.
- **HEIC needs `pillow-heif`**, and converting via ffmpeg drops EXIF, so dates
  and GPS must be read from the original before conversion.

## Before it goes live

```bash
grep -rn "REPLACE-ME" .
```

1. **LinkedIn URL** and 2. **Instagram URL** — `index.html`, contact section.
3. **GitHub** is deliberately absent. Add it once the profile has work on it.
4. Replace `assets/cv/abdullah-al-mulqi-cv.pdf` with a version that includes the
   FAIR Lab internship.

## Deploying — Cloudflare Pages

The domain is already bought. Push this directory to GitHub, then:

Cloudflare Dash → Workers & Pages → Create → Pages → Connect to Git.

| Setting | Value |
|---|---|
| Framework preset | None |
| Build command | *(empty)* |
| Build output directory | `/` |

Then Custom domains → `almulqi.com`, and add `www` so it redirects to the apex.
HTTPS is automatic. After that, `git push` deploys.

Limits worth knowing: 25 MB per file (nothing here is close), and no external
requests — no font CDN, no analytics. That is what keeps it fast and private.

## Checks to re-run after editing

- Every page at 375, 768 and 1440 px; nothing may scroll horizontally.
- Keyboard only: tab the whole page, focus must always be visible.
- Both colour themes, and `prefers-reduced-motion` on — the journey should
  collapse to a plain vertical stack and the clips should gain controls.
- Total transferred bytes for `/` — the eager first load is currently 0.41 MB.
