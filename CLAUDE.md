# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Rockbox** theme called "iCamVideo" (v1.2) for the iPod Video/Classic (320x240, 24-bit
color). Rockbox is open-source firmware for digital audio players; themes are plain-text layout
scripts ("tags") plus bitmap assets, not compiled code. There is no build system, package
manager, linter, or test suite for the theme itself — it's a plain asset/config tree. The repo
also carries a small amount of device-side tooling under `tools/` (dark-bitmap generation, video
conversion — see below) that isn't part of the theme but supports using it. It's the live
continuation of an earlier "iVideo" theme (that sibling directory is now an empty shell).

Ships in two variants, selected as separate entries in Rockbox's theme list: "iCamVideo" (light,
the original) and "iCamVideo Dark". See "Light/dark variants" below for how the dark copy is
generated and kept in sync.

Author: Humberto Santana (humbertosantana@hotmail.com). License: CC BY-SA 3.0 (derivative works
must carry the attribution text specified at the top of each `.wps`/`.sbs`/`.fms` file).

## Repo layout

- `themes/iCamVideo.cfg` / `themes/iCamVideo-Dark.cfg` — the theme manifests: each points to its
  own `.wps`/`.sbs`/`.fms` files below, sets the backdrop, font, colors (the only thing that
  actually differs between the two `.cfg`s — see "Light/dark variants"), and
  `ui viewport: 0,24,320,216,-,-,-` (the fallback list area — see the SBS section below for how
  the SBS overrides this dynamically).
- `wps/iCamVideo.wps` / `wps/iCamVideo-Dark.wps` — **W**hile-**P**laying-**S**creen layout
  (now-playing screen).
- `wps/iCamVideo.sbs` / `wps/iCamVideo-Dark.sbs` — **S**tatus-**B**ar **S**creen layout (menu/list
  screen chrome). No `-no-clock` variant exists for either `.sbs`.
- `wps/iCamVideo.fms` / `wps/iCamVideo-Dark.fms` — **F**M radio screen layout.
- `wps/iCamVideo-no-clock-WPS.txt`, `wps/iCamVideo-no-clock-FMS.txt`,
  `wps/iCamVideo-Dark-no-clock-WPS.txt`, `wps/iCamVideo-Dark-no-clock-FMS.txt` — alternate variants
  with the clock display commented out. To use one, rename it over the corresponding real file
  (`iCamVideo.wps`/`iCamVideo-Dark.wps`/etc — keep the `-Dark` in the name for the dark ones, since
  that's what selects the `wps/iCamVideo-Dark/` bitmap folder).
- `wps/iCamVideo/` — bitmap assets (battery/icons/progress-bar/album-art-frame images, plus its
  own `Backdrop.bmp` used by the WPS/FMS — distinct from `backdrops/iCamVideo_Backdrop.bmp`, which
  is the menu/list backdrop). `wps/iCamVideo-Dark/` mirrors it with the dark-mode twins, generated
  by `tools/make-dark.py` — see "Light/dark variants".
- `backdrops/iCamVideo_Backdrop.bmp` / `backdrops/iCamVideo_Backdrop_Dark.bmp` — full-screen
  backdrop for the menu/list screen.
- `fonts/18 iLike.fnt`, `fonts/24 iLike.fnt` — bitmap fonts (18pt used in the SBS, 24pt is the cfg
  default). Shared by both variants; text color, not font, differs.
- `icons/blank-10.bmp` — the `iconset`/`viewers iconset` referenced by both cfgs (`show icons:
  on`). Fully transparent (`FF00FF`), so it needs no dark twin.
- `tools/make-dark.py` — regenerates `wps/iCamVideo-Dark/*.bmp` and
  `backdrops/iCamVideo_Backdrop_Dark.bmp` from their light originals. Re-run it any time a light
  bitmap changes.
- `tools/convert-video.py` — converts arbitrary video files into the MPEG-PS `.mpg` format
  Rockbox's `mpegplayer` plugin can play, optionally copying results straight onto a mounted
  iPod. Not theme-owned, not touched by `sync-to-ipod.sh` — see "Converting videos" below.
- `sync-to-ipod.sh` — copies this repo's theme-owned files (both variants) onto a mounted iPod
  (default `/Volumes/JUANCHO'S I`, override with `$1`). It lists each file individually rather
  than globbing — remember to add new assets to it by hand if you add any (the `wps/iCamVideo/`
  and `wps/iCamVideo-Dark/` bitmap folders are the exception: those are globbed). Videos are user
  media, not theme assets, so this script deliberately does not handle them.

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
  icon logic. Read the innermost condition first when tracing behavior. `%cs` (current screen)
  returns `apps/misc.h`'s `enum current_activity` value, 1-20 in a fixed order (confirmed against
  `manual/appendix/wps_tags.tex` and `skin_tokens.c` in Rockbox master): `1 menus | 2 WPS | 3 rec |
  4 FM radio | 5 playlist | 6 settings | 7 file browser | 8 database browser | 9 plugin browser |
  10 quickscreen | 11 pitchscreen | 12 setting chooser | 13 playlist catalogue | 14 plugin |
  15 context menu | 16 system info | 17 time/date | 18 bookmark browser | 19 shortcuts menu |
  20 track info`. The existing 5-branch `%?cs<...>` dispatches in this SBS (title/battery text)
  rely on out-of-range values clamping to their last branch.
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
- **Layout files carry no `%Vf`(foreground)/`%Vb`(background) color literals** — every viewport
  inherits the `.cfg`'s `foreground color`/`background color` by default, so an explicit
  `%Vf(000000)%Vb(FFFFFF)` on every viewport was pure duplication of the cfg (confirmed: deleting
  all ~96 occurrences from every layout file was a no-op on the light theme). This is what makes
  the dark variant a small diff instead of a full recolor — see "Light/dark variants". The two
  exceptions: `%Vf(888888)`/`%Vf(BDBABD)` (light/dark) for the dim "next track" text, which is
  *not* the cfg default and must stay explicit; and `%dr`'s color argument (the seam divider),
  which has no cfg-inherited form at all — see below.

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
- `%Vl(sh,160,24,2,216,-)` + `%dr(0,0,2,216,FFFFFF)` (light) / `%dr(0,0,2,216,292829)` (dark) — a
  flat 2px divider line at the list/art seam, matching the menu background color in each variant
  (so it reads as a seam, not a stripe), declared right after `aa` so it draws on top of the art
  each refresh. This is its own labeled/hideable viewport, not a bare `%V` nested after `%Cd`
  — see the viewport-coordinates note above for why that doesn't work (it'd land at absolute
  screen (0,0), ungated, not at the seam). Uses `%dr` (explicit filled rectangle,
  `x,y,w,h,color[,endcolor]`, local to the current viewport) rather than `%Vb` — `%Vb` only colors
  content drawn after it fires as a child tag; it can't retroactively recolor the viewport's own
  initial clear-to-background, which always uses the theme's default color and happens before any
  child tag runs. This is also why `%dr`'s color can't just be dropped like every other `%Vf`/`%Vb`
  literal in these files (see the color-inheritance note above) — it's the one color genuinely
  local to the layout file, so it's the one line that differs between `iCamVideo.sbs` and
  `iCamVideo-Dark.sbs`. (Earlier attempts at a gray line matching the header divider and a
  left-to-right fade using stacked `%dr` bands were tried and dropped in favor of this flat line;
  `%dr`'s built-in 2-color gradient form only fades vertically, top-to-bottom, hardcoded in the LCD
  driver, so it couldn't do a horizontal fade either way.)
- A single dispatch line, positioned right after the existing `%?St(battery display)<...>` header
  dispatch (must stay there — see the viewport-content-scope note above). Outermost check is
  `%?if(%cs, =, 14)` (current screen = plugin): if any plugin is running, force `full` regardless
  of playback state. Otherwise fall through to the original `%mp` branches: `1 stop | 2 play |
  3 pause | 4 ffwd | 5 rew | 6 record | 7 record-paused | 8 radio | 9 radio-muted` — only 2, 4, 5
  get the art panel + shadow; 3 (pause) intentionally falls back to `full`:
  `%?if(%cs, =, 14)<%VI(full)|%?C<%?mp<%VI(full)|%VI(half)%Vd(aa)%Vd(sh)|%VI(full)|%VI(half)%Vd(aa)%Vd(sh)|%VI(half)%Vd(aa)%Vd(sh)|%VI(full)|%VI(full)|%VI(full)|%VI(full)>|%VI(full)>>`
  The plugin check exists because a plugin that enables the theme (e.g. the lyrics viewer,
  `apps/plugins/lrcplayer.c`, via `viewportmanager_theme_enable()`) gets whichever `%Vi` the SBS
  last selected as its drawing area (`apps/gui/viewport.c` `viewport_set_defaults()` →
  `sb_skin_get_info_vp()`), and `sb_skin_update()` keeps repainting the SBS — including the art —
  over the plugin's screen for as long as it runs. Without this check, a plugin launched during
  playback would be stuck at 160px with art painted on top of it.
- `%Cl(-28,0,216,216,c,c)` — the crop-centering offset described above (`-(216-160)/2`).

If you resize the art box or the `half` viewport width, recompute that `-28` by hand.

## Light/dark variants

Rockbox has no mechanism to switch bitmaps or the `.wps`/`.fms` backdrop per-`.cfg` — every image
load (`%X`, `%xl`) is a filename baked into the layout file. The dark variant is therefore a
genuine fork of the `.cfg`/`.wps`/`.sbs`/`.fms`/bitmap set, made cheap by two properties confirmed
while building it:

- **`%xl`/`%X` filenames resolve relative to the skin file's own basename**
  (`get_image_filename()` in `apps/gui/skin_engine/skin_parser.c`): `iCamVideo.wps` reads from
  `wps/iCamVideo/`, `iCamVideo-Dark.wps` reads from `wps/iCamVideo-Dark/`, automatically, using the
  *same* bitmap filenames inside each file. So `iCamVideo-Dark.wps`/`.sbs`/`.fms` need zero path
  edits versus their light originals — only bitmap *content* differs.
- **Colors live in the `.cfg`, not the layout files** (see the color-inheritance note in "Editing
  the layout files" above). So the light/dark layout files differ by exactly 5 lines total: the
  `%dr` seam-divider hex in `.sbs`, and the 4 `%Vf(888888)`→`%Vf(BDBABD)` dim-text lines in `.wps`.

Palette (light → dark), set in `themes/iCamVideo.cfg` / `themes/iCamVideo-Dark.cfg`:

| Role | Light | Dark |
|---|---|---|
| `background color` | `FFFFFF` | `292829` |
| `foreground color` | `000000` | `FFFFFF` |
| Dim "next track" text (`%Vf`, layout files only) | `888888` | `BDBABD` |
| `line selector start color` | `6BA6DE` | `3584E4` |
| `line selector end color` | `186DBD` | `1C5FB4` |
| `line selector text color` | `FFFFFF` | `FFFFFF` (unchanged) |
| Art-panel seam (`%dr`, layout files only — matches `background color`) | `FFFFFF` | `292829` |

`tools/make-dark.py` (stdlib-only) generates every dark bitmap from its light original — reads
`wps/iCamVideo/*.bmp`, writes `wps/iCamVideo-Dark/*.bmp` under identical filenames, plus
`backdrops/iCamVideo_Backdrop.bmp` → `backdrops/iCamVideo_Backdrop_Dark.bmp`. Default transform is
per-pixel HSL lightness inversion (`L' = 1 - L`, hue/saturation unchanged) — this turns white
plaques near-black and black glyphs white while keeping colored elements (e.g. the blue battery
icon) their same hue, just darker. Rockbox's `FF00FF` transparency key is passed through
untouched. A few bitmaps that already read fine on a dark background are copied verbatim instead
(`Progress Bar.bmp`, `Volumebar.bmp`, `Radio Icon.bmp` — see the `PASSTHROUGH` set in the script).
Re-run this script whenever a light bitmap in `wps/iCamVideo/` changes; it's idempotent.

`sync-to-ipod.sh` copies both variants' `.cfg`/`.wps`/`.sbs`/`.fms`/`-no-clock-*.txt` files
individually (list must be updated by hand if the file set changes) and globs both
`wps/iCamVideo/*.bmp` and `wps/iCamVideo-Dark/*.bmp` (new bitmaps there are picked up
automatically).

When editing a layout file, mirror the change into its `-Dark` counterpart per the diff table
above (usually a no-op copy, since color literals shouldn't be there) — same rule as the
`-no-clock` mirroring below, just one more axis.

## Converting videos (`tools/convert-video.py`)

The `mpegplayer` plugin (`apps/plugins/mpegplayer/` in Rockbox itself) only decodes a narrow,
legacy format — verified against `Rockbox/rockbox@master` source, not the wiki (stale/blocked by
Anubis bot-protection):

| Constraint | Why |
|---|---|
| Container: **MPEG program stream (`.mpg`) only** | `mpeg_parser.c` probes for a PES packet and sets `STREAM_FMT_MPEG_PS`; with none found in the first 256KB it falls back to `STREAM_FMT_MPV` (raw video elementary stream, silent). No MPEG-TS/MP4 support exists. |
| Video: **MPEG-1/MPEG-2** | decoded via `libmpeg2/` under the plugin dir. |
| Audio: **MPEG audio layer I/II/III** (MP2/MP3) | `audio_thread.c` decodes via libmad. |
| Resolution: **320x240** (native LCD) | `video_out_rockbox.c` can scale/crop mismatched video, but both cost CPU the 80MHz PP5021 doesn't have to spare — encode to native size instead. |
| Audio: **44100Hz stereo** | the hardware's native rate; other rates make `audio_thread.c` reconfigure the DSP resampler at playback time. |
| Framerate: one of the **MPEG-2-legal rates** (23.976/24/25/29.97/30/50/59.94/60) | `mpeg2video` hard-errors on anything else. |

`tools/convert-video.py` (stdlib-only Python, same posture as `make-dark.py`) wraps `ffmpeg`/
`ffprobe` to produce compliant `.mpg` files:

```
tools/convert-video.py movie.mkv                      # -> ./converted-video/movie.mpg
tools/convert-video.py -o out/ --bitrate 400k dir/     # batch-convert a directory
tools/convert-video.py --ipod movie.mkv                # also copy to <mount>/Video/
tools/convert-video.py -n movie.mkv                    # dry run: print the ffmpeg command
tools/convert-video.py -v movie.mkv                     # verbose: probe info, full cmd, live ffmpeg output
```

It probes each source, snaps the source framerate to the nearest legal MPEG-2 rate (capped at
30fps to stay inside the CPU budget; `--fps` overrides), and scales/pads to exactly 320x240 with
`setsar=1` (`--fit pad|crop|stretch` picks letterbox/crop/distort). Default video bitrate is
600k — drop it (`--bitrate 400k`) if a real device stutters. `--ipod [mount]` mirrors
`sync-to-ipod.sh`'s mount-detection contract (default `/Volumes/JUANCHO'S I`, errors clearly if
`.rockbox` isn't found there) but writes to `<mount>/Video/`, a path `sync-to-ipod.sh` never
touches. A bad file in a batch is reported and skipped, not fatal to the rest of the run.

**Do not add `-maxrate`/`-bufsize`/`-muxrate` to the `ffmpeg` invocation in `build_cmd()`.**
Confirmed by direct testing (not the wiki): with those set, ffmpeg's `-f mpeg` (MPEG-1 System
Stream) muxer's internal STD buffer-model check spuriously logs "buffer underflow st=1 bufi=...
size=..." throughout the *entire* encode — harmless on short clips, but on a real ~32-minute
source it eventually escalates into a hard failure (`ffmpeg` exit 234) even though the source was
completely clean. Letting ffmpeg auto-choose its VBV/mux parameters (i.e. omitting those flags
entirely) eliminates it outright.

Separately, `convert-video.py` retries a failed conversion once, trimmed to
`ffprobe`-reported video duration minus `RETRY_TRIM_MARGIN` (15s), because some real-world
sources (observed on a screen recording) have a genuinely corrupted tail right around where the
video track ends — ffmpeg's demuxer desyncs on garbage bytes there (`Invalid NAL unit size`) and
the encode dies instead of ending cleanly. `-shortest` alone does not protect against this, since
the demuxer has to read into the corrupted region before it can even detect the stream ended.

## Testing changes

There is no automated test suite and no simulator available in this environment. Changes are
verified by:
1. Running `./sync-to-ipod.sh` (or manually copying files into `.rockbox/` matching the paths in
   `themes/iCamVideo.cfg`/`themes/iCamVideo-Dark.cfg`) to a real device, or using the Rockbox
   `uisimulator` for ipodvideo.
2. Selecting "iCamVideo" (light) and "iCamVideo Dark" in turn and visually checking the WPS,
   menu/list screen (stopped, playing with/without art, and with a plugin like the lyrics viewer
   running during playback), and FM radio screen for each.
