---
name: godot-asset-gen
description: |
  Generate 2D game assets: PNG images (Google AI Studio Gemini x4 / OpenAI gpt-image-2 / Alibaba Wan 2.7, via official APIs or wavespeed.ai), MP4 video for animated sprite sheets (Volcano Ark Seedance 2.0/fast/mini 直链 or Wan 2.7), background removal, grid slicing, loop detection, and budget-based asset planning. Wan 2.7 (wavespeed-only) is the content-permissive route for spicy/nudity art. 3D (GLB/rig) lives in the godot-asset-gen-3d skill. Requires GOOGLE_API_KEY / OPENAI_API_KEY / WAVESPEED_API_KEY / ARK_API_KEY per route, plus local deps (imagemagick, rembg, ffmpeg).
---

# 2D Asset Generator

Generate PNG images and sprite animations. 3D (GLB / rigging / retarget via Tripo3D) is the **godot-asset-gen-3d** skill.

## Image models

| Model (`--model`) | Vendor | Sizes | Cost (est. ¢) | Best for |
|---|---|---|---|---|
| `gemini-3.1-flash-lite-image` | Google | 512/1K/2K/4K | 2/3/5/8 | cheap drafts, textures, kits |
| `gemini-3.1-flash-image` **default** | Google | 512/1K/2K/4K | 5/7/10/15 | precise prompt following — refs, characters, layouts |
| `gemini-3-pro-image` | Google | 1K/2K/4K | 15/20/30 | hero art, 4K quality ceiling |
| `gemini-2.5-flash-image` | Google | 1K | 4 | legacy cheap fallback (Nano Banana) |
| `gpt-image-2` | OpenAI | 1K/2K | 10/15 | alternative style; strong text-in-image |
| `wan-2.7-t2i` / `-pro` | Alibaba | 1K/2K(/4K pro) | 2-12 | **content-permissive** t2i (spicy/nudity game art other providers refuse) |
| `wan-2.7-edit` / `-pro` | Alibaba | 1K/2K(/4K pro) | 3-15 | **content-permissive** image EDIT (requires `--image`) |

Costs are ESTIMATES — tune the `MODELS` table in `tools/asset_gen.py` to your bills.

## Providers (`--provider`)

| Route | Key | Notes |
|---|---|---|
| `official` | `GOOGLE_API_KEY` / `OPENAI_API_KEY` | Google AI Studio / OpenAI direct |
| `wavespeed` | `WAVESPEED_API_KEY` | wavespeed.ai relay; the ONLY route for `wan-2.7-*` |
| `auto` (default) | — | official when the vendor key is set, else wavespeed |

## Video models (`video --video-model`) — for animated sprites

| Model | Route | Cost | Res | Duration |
|---|---|---|---|---|
| `seedance-2.0` | Volcano Ark 直链 (`ARK_API_KEY`) | 1.0¢/s | up to 1080p | 4-15s |
| `seedance-2.0-fast` **default** | Ark 直链 | 0.8¢/s | 720p | 4-15s |
| `seedance-2.0-mini` | Ark 直链 | 0.6¢/s | 720p | 4-15s |
| `wan-2.7` | wavespeed | ~5¢/s (est.) | 720p | 5/10s |

Seedance model ids are Ark inference endpoints, overridable via `SEEDANCE_2_0_EP` / `SEEDANCE_2_0_FAST_EP` / `SEEDANCE_2_0_MINI_EP`.

## CLI Reference

Tools live at `.claude/skills/godot-asset-gen/tools/`. Run from the project root.
Keep runtime-loaded outputs under `assets/`; review-only refs/scratch elsewhere.

### Generate / edit image

```bash
python3 .claude/skills/godot-asset-gen/tools/asset_gen.py image \
  --prompt "the full prompt" -o assets/img/bucket.png
```

- `--model` (default `gemini-3.1-flash-image`), `--provider auto|official|wavespeed`
- `--size 512|1K|2K|4K`, `--aspect-ratio 1:1|16:9|...` (default 1:1)
- `--image path` — reference/edit input, **repeatable** (wan edit & gemini support multi-ref)

Typical picks:
- cheap texture/kit → `--model gemini-3.1-flash-lite-image`
- precise prop/character → default model
- hero/keyart → `--model gemini-3-pro-image --size 2K`
- spicy content → `--model wan-2.7-t2i-pro`; spicy edit → `--model wan-2.7-edit-pro --image src.png`

### Remove background

Read `.claude/skills/godot-asset-gen/rembg.md` (CLI, BG-color strategy, batch mode).

### Item kit (one image, N props)

2x2/3x3 grid in one generation, then slice:
```bash
python3 .claude/skills/godot-asset-gen/tools/grid_slice.py grid.png \
  -o assets/img/items/ --grid 2x2 --names "bucket,stool,ladle,lantern"
```

### Animated sprite (ref → pose → video → slice → loop → rembg)

1. **Reference** (image, 1:1, solid BG color per rembg.md)
2. **Pose frame** (image + `--image` ref, prompt = the action pose)
3. **Video** (pose frame as first_frame):
```bash
python3 .claude/skills/godot-asset-gen/tools/asset_gen.py video \
  --prompt "walking to the right, smooth walk cycle, solid dark-green background" \
  --image assets/img/knight_walk_pose.png \
  --video-model seedance-2.0-mini --duration 4 -o assets/video/knight_walk.mp4
```
4. **Frames**: `ffmpeg -i knight_walk.mp4 -vsync 0 frames/%04d.png`
5. **Loop trim** (cycles only): `python3 .../tools/find_loop_frame.py frames/`
6. **Batch rembg**: `python3 .../tools/rembg_matting.py --batch frames/ -o assets/img/knight_walk/`

A 4s mini video = ~2.4¢; a full walk cycle (ref 7¢ + pose 7¢ + video 2.4¢) ≈ 17¢.

### Set budget

```bash
python3 .claude/skills/godot-asset-gen/tools/asset_gen.py set_budget 500
```
Only call when the user explicitly provides a budget. Shared `assets/budget.json` (the 3D skill records into the same file).

### Output format

JSON to stdout: `{"ok": true, "path": "...", "cost_cents": 7}`. Progress/API noise on stderr — redirect to a temp file and read only on failure:
```bash
_log=$(mktemp)
result=$(python3 .../asset_gen.py image --prompt "..." -o p.png 2>"$_log") || tail -20 "$_log"
```

## Image Resolution

Use full generation resolution; downscale only to hit game PPU targets.
- `1K` default: textures, sprites, refs
- `2K`: HQ objects, backgrounds, title screens
- `4K` (gemini pro/lite, wan pro): large maps, panoramas

### Small sprites problem

1024px downscaled to 64px goes muddy. Mitigations: design at 128px+; generate kits (more px per object); prompt bold simple forms (thick outlines, flat colors) that survive downscale.

## What to Generate — Cheatsheet

For transparency, read rembg.md first (BG color strategy).

- **Background/scenic** (2-10¢): flash-lite for simple; flash/pro `--size 2K --aspect-ratio 16:9` for precise layout. No post-processing.
- **Texture** (2-3¢): flash-lite. "Top-down view, uniform lighting, no shadows, seamless tileable."
- **Single prop/sprite**: flash (precise) or flash-lite (cheap); solid BG color → rembg.
- **Character design** (7¢): flash 1K; variants via `--image` ref (prompt only the CHANGE).
- **Spicy/nudity content**: wan-2.7 family via wavespeed only; same composition rules apply.
- **3D model reference** → then hand off to the **godot-asset-gen-3d** skill: "3/4 front elevated camera angle, solid white background, matte finish, single centered subject, opaque glass."

## Visual Pitfalls

- **Direction/orientation**: generators can't do left/right reliably — generate ONE facing, flip at runtime.
- **Video size consistency**: resize 1024px stills DOWN to video frame size before rembg (`magick input.png -resize 720x720 -filter Lanczos out.png`).
- **Playback fps**: video frames are ~24fps; drive playback at `1.0/24.0`, don't restart the loop on input jitter.
- **Image-to-image prompting**: with `--image`, don't re-describe the subject — prompt only what CHANGES.
- Generate multiple images in parallel via multiple Bash calls in one message.
- Review PNGs before building on them (bad ref poisons every downstream step).
