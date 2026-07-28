# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Rockbox** theme called "iCamVideo" (v1.2) for the iPod Video/Classic (320x240, 24-bit
color). Rockbox is open-source firmware for digital audio players; themes are plain-text layout
scripts ("tags") plus bitmap assets, not compiled code. There is no build system, package
manager, linter, or test suite — this is a pure asset/config repo. It's the live continuation of
an earlier "iVideo" theme (that sibling directory is now an empty shell).

Author: Humberto Santana (humbertosantana@hotmail.com). License: CC BY-SA 3.0 (derivative works
must carry the attribution text specified at the top of each `.wps`/`.sbs`/`.fms` file).

## Repo layout

- `themes/iCamVideo.cfg` — the theme manifest: points to the `.wps`/`.sbs`/`.fms` files below,
  sets the backdrop, font, default colors, and `ui viewport: 0,24,320,216,-,-,-` (the fallback
  list area — see the SBS section below for how the SBS overrides this dynamically).
- `wps/iCamVideo.wps` — **W**hile-**P**laying-**S**creen layout (now-playing screen).
- `wps/iCamVideo.sbs` — **S**tatus-**B**ar **S**creen layout (menu/list screen chrome). Only one
  `.sbs` exists (no `-no-clock` variant for it).
- `wps/iCamVideo.fms` — **F**M radio screen layout.
- `wps/iCamVideo-no-clock-WPS.txt`, `wps/iCamVideo-no-clock-FMS.txt` — alternate variants with the
  clock display commented out. To use one, rename it over the corresponding real file. Note: the
  no-clock WPS variant has a pre-existing bug carried over from upstream — its
  `%?St(battery display)<%Vd(title)|%Vd(titlebat)` substitute line is missing its closing `>`.
- `wps/iCamVideo/` — bitmap assets (battery/icons/progress-bar/album-art-frame images, plus its
  own `Backdrop.bmp` used by the WPS/FMS — distinct from `backdrops/iCamVideo_Backdrop.bmp`, which
  is the menu/list backdrop).
- `backdrops/iCamVideo_Backdrop.bmp` — full-screen backdrop for the menu/list screen.
- `fonts/18 iLike.fnt`, `fonts/24 iLike.fnt` — bitmap fonts (18pt used in the SBS, 24pt is the cfg
  default).
- `icons/blank-10.bmp` — the `iconset`/`viewers iconset` referenced by the cfg (`show icons: on`).
- `sync-to-ipod.sh` — copies this repo's theme-owned files onto a mounted iPod (default
  `/Volumes/JUANCHO'S I`, override with `$1`). It lists each file individually rather than
  globbing — remember to add new assets to it by hand if you add any.

## Editing the layout files (`.wps` / `.sbs` / `.fms`)

These use Rockbox's WPS tag syntax (`%` prefixed tokens). Ground-truth for tag syntax/behavior is
the Rockbox source itself (`lib/skin_parser/tag_table.c` for the argument grammar of every tag,
`apps/gui/skin_engine/skin_parser.c` for how tags get turned into the in-memory viewport tree, and
`apps/gui/statusbar-skinned.c` / `apps/gui/skin_engine/skin_display.c` for how the SBS and album
art actually get drawn) — the public wiki/manual pages are frequently out of date or blocked by
Anubis bot-protection, so don't trust them over the source.

- `#` at the start of a line comments it out.
- `%V(...)` / `%Vl(name,...)` declare viewports (basic / conditional-by-label); `%Vd(name)` draws
  a named one. **Every `%V`/`%Vl`/`%Vi` tag always starts a brand-new, independent top-level
  viewport with its own absolute screen coordinates and its own show/hide state — it never
  becomes a locally-positioned sub-region "inside" whatever viewport textually precedes it, no
  matter how it's indented/grouped in the file.** Coordinates in a `%V`/`%Vl`/`%Vi` call are
  always relative to the screen (0,0 = top-left corner), never relative to a prior viewport. We
  hit this directly trying to draw a small colored bar as a "nested" element right after another
  viewport's content — it actually became a separate, always-on, absolutely-positioned viewport at
  screen (0,0), not the intended spot, and wasn't gated to any show/hide state either. If you want
  something to only appear alongside another conditional viewport, give it its own label and add
  it to the same `%Vd(...)` dispatch branches — see the shadow bar in "Now-playing album art panel"
  below. (Ordinary, non-viewport tags — text, `%Cd`, `%xd`, conditionals — behave the opposite way:
  everything between one viewport declaration and the next genuinely becomes that viewport's
  content/children, drawn local to it, and comments don't break that scope. If you put a dispatch
  conditional right after a fresh `%Vl` with nothing else in between, it gets trapped as that
  viewport's hidden content and only runs once that viewport is already visible — this also bit us
  directly; always park top-level dispatch conditionals right after another top-level tag that's
  never hidden, e.g. right after an existing header dispatch, not right after a `%Vl`.)
- `%Vi(label,x,y,w,h,font)` declares a candidate **UI (list) viewport**; `%VI(label)` switches the
  active one at runtime. `%VI`'s argument type is uppercase in the tag grammar (`"S"`), which means
  it **cannot** be given `-` (the default/dash placeholder) — only lowercase-typed tags accept
  that. So you can't ever call `%VI(-)`; if you need a "back to default width" state, declare a
  second, separately-named `%Vi` with the same geometry as your `%Vi(-,...)` and switch to that
  named one instead. A bare `%Vi(-,...)` viewport (`is_infovp=true`, label = the special default
  sentinel) must exist somewhere in the file regardless — Rockbox's SBS bootstrap
  (`sb_process()`) looks for exactly one of these when the SBS loads and the whole statusbar
  breaks (title text disappears, list starts drawing at y=0 instead of below the header) if it's
  missing.
- `%xl(id,file.bmp,...)` loads an image slice under a one-character id; `%xd(id)` draws it.
  Multi-frame icon strips (battery, playing-status, repeat/shuffle, playmode) are addressed by
  letter-per-frame (e.g. `%xd(Ba)`, `%xd(Bb)`).
- `%?tag<branch1|branch2|...>` is the conditional/ternary construct. `%mp` (playback status) has 9
  branches in a fixed order: `1 stop | 2 play | 3 pause | 4 ffwd | 5 rew | 6 record |
  7 record-paused | 8 radio | 9 radio-muted` — confirmed against the SBS's own existing playmode
  icon logic. Read the innermost condition first when tracing behavior.
- `%Cl(x,y,maxwidth,maxheight,xalign,yalign)` declares the now-playing album art box (once per
  skin file); `%Cd` draws it inside whatever viewport is current when `%Cd` executes; `%C` is true
  when the current track has art. `x`/`y` are plain signed pixel offsets **local to the viewport
  active at draw time**, not percentages of anything by default — Rockbox scales the source image
  (any resolution/aspect) down or up to fit inside `maxwidth`×`maxheight` automatically, so source
  image size never needs special-casing. If the art box is wider than the viewport it's drawn
  into, the viewport's clip crops it — asymmetrically (all off one side) unless you manually
  offset `x` by `-(box_size - viewport_size) / 2` to center the crop. This offset is a one-time,
  hand-computed constant; Rockbox has no formula/expression tags, so it must be recalculated by
  hand any time the box size or viewport size changes.
- Font slots are declared via `%Fl(slot,fontfile)` and referenced by slot number elsewhere.
- Screen canvas is 320x240 — layout coordinates in `%V(...)`/`%Vl(...)`/`%Vi(...)` calls assume
  this.

When modifying a layout, mirror any equivalent change into the matching `-no-clock-*.txt` variant
if the change isn't about the clock itself, so the two stay in sync (there's no `-no-clock` SBS
variant to worry about).

## Now-playing album art panel (menu/list screen)

`wps/iCamVideo.sbs` shows the currently-playing track's cover art on the right 160px of the
menu/list screen, but **only** while a track is actively playing or seeking and has art (NOT
while paused) — unlike the sibling `iClassic` theme, which always reserves that space (art when
available, scrolling track text otherwise). Implementation, near the top of the file:

- `%Vi(-,0,24,320,216,1)` — required bootstrap default UI viewport (see the `%VI` note above).
- `%Vi(full,0,24,320,216,1)` / `%Vi(half,0,24,160,216,1)` — the two real candidates, switched via
  `%VI(full)` / `%VI(half)`.
- `%Vl(aa,160,24,160,216,-)` + `%Cd` — the art panel content, drawn when `%Vd(aa)` fires.
- `%Vl(sh,160,24,2,216,-)` + `%dr(0,0,2,216,FFFFFF)` — a flat 2px white divider line at the
  list/art seam, declared right after `aa` so it draws on top of the art each refresh. This is its
  own labeled/hideable viewport, not a bare `%V` nested after `%Cd` — see the viewport-coordinates
  note above for why that doesn't work (it'd land at absolute screen (0,0), ungated, not at the
  seam). Uses `%dr` (explicit filled rectangle, `x,y,w,h,color[,endcolor]`, local to the current
  viewport) rather than `%Vb` — `%Vb` only colors content drawn after it fires as a child tag; it
  can't retroactively recolor the viewport's own initial clear-to-background, which always uses
  the theme's default color (white here) and happens before any child tag runs. (Earlier attempts
  at a gray line matching the header divider and a left-to-right fade using stacked `%dr` bands
  were tried and dropped in favor of this flat white line; `%dr`'s built-in 2-color gradient form
  only fades vertically, top-to-bottom, hardcoded in the LCD driver, so it couldn't do a
  horizontal fade either way.)
- A single dispatch line, positioned right after the existing `%?St(battery display)<...>` header
  dispatch (must stay there — see the viewport-content-scope note above). `%mp` branches: `1 stop |
  2 play | 3 pause | 4 ffwd | 5 rew | 6 record | 7 record-paused | 8 radio | 9 radio-muted` — only
  2, 4, 5 get the art panel + shadow; 3 (pause) intentionally falls back to `full`:
  `%?C<%?mp<%VI(full)|%VI(half)%Vd(aa)%Vd(sh)|%VI(full)|%VI(half)%Vd(aa)%Vd(sh)|%VI(half)%Vd(aa)%Vd(sh)|%VI(full)|%VI(full)|%VI(full)|%VI(full)>|%VI(full)>`
- `%Cl(-28,0,216,216,c,c)` — the crop-centering offset described above (`-(216-160)/2`).

If you resize the art box or the `half` viewport width, recompute that `-28` by hand.

## Testing changes

There is no automated test suite and no simulator available in this environment. Changes are
verified by:
1. Running `./sync-to-ipod.sh` (or manually copying files into `.rockbox/` matching the paths in
   `themes/iCamVideo.cfg`) to a real device, or using the Rockbox `uisimulator` for ipodvideo.
2. Selecting the "iCamVideo" theme and visually checking the WPS, menu/list screen (stopped, and
   playing with/without art), and FM radio screen.
