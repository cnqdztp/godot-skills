---
name: godot-asset-gen-3d
description: |
  Generate 3D game assets via Tripo3D: convert a PNG to a GLB model (30-60¢), rig biped characters (25¢), and retarget ~100 preset animations (walk/run/idle/attack..., 10¢ each). Includes resume for stalled jobs and shared budget tracking. Use for any 3D model / GLB / rigging / character animation need; 2D images live in the godot-asset-gen skill (use it first to make the model reference image). Requires TRIPO3D_API_KEY.
---

# 3D Asset Generator (Tripo3D)

Image → GLB → (biped) rig → retargeted animations. The reference IMAGE is made with
the **godot-asset-gen** (2D) skill first.

## CLI Reference

Tools live at `.claude/skills/godot-asset-gen-3d/tools/`. Run from the project root.
Keep runtime-loaded outputs under `assets/`.

### 0. Make the reference image (2D skill)

Use godot-asset-gen `image` with the 3D-ref prompt shape:
```
3D model reference of {name}. {description}. 3/4 front elevated camera angle, solid
white background, soft diffused studio lighting, matte material finish, single centered
subject, no shadows on background. Any windows or glass should be solid tinted (opaque).
```
Do NOT remove the background — Tripo3D needs the solid white bg for clean separation.
Review the PNG before converting; a bad image wastes 30+ cents.

### Convert image to static GLB (30-60¢)

```bash
python3 .claude/skills/godot-asset-gen-3d/tools/asset_gen_3d.py glb \
  --image assets/img/car.png -o assets/glb/car.glb
```

`--quality`: `default` (30¢ — v3.1, std geometry/texture, 30k face cap, PBR) or
`hd` (60¢ — detailed geometry + HD texture, no face cap)
`--no-pbr`: only if PBR output looks visibly wrong (rare on v3.1)
`--face-limit N` (default 30000, sane 10k-50k, ignored by hd). No separate lowpoly
mode — just shrink the cap.

Writes a `<output>.glb.tripo.json` sidecar with task ids — consumed by `rig`/`resume`.

### Rig a biped character (mesh cost + 25¢)

**Biped only** (rigger v1.0-20240301, humanoid skeletons; quadrupeds must use plain `glb`).

```bash
python3 .claude/skills/godot-asset-gen-3d/tools/asset_gen_3d.py rig \
  --image assets/img/knight_ref.png -o assets/glb/knight_rigged.glb
```

Runs `image_to_model → prerigcheck → animate_rig`; aborts clearly if prerigcheck says
not biped. Same `--quality` / `--no-pbr` flags as `glb`.

### Retarget animation (10¢ per clip)

```bash
python3 .claude/skills/godot-asset-gen-3d/tools/asset_gen_3d.py retarget \
  --rigged assets/glb/knight_rigged.glb \
  --animation preset:biped:walk \
  -o assets/glb/knight_walk.glb
```

Each clip is a separate 10¢ task reusing the rig task id from the sidecar — walk +
idle + attack = 3 retarget calls, **no re-rigging, no re-generation**. Do not assume
the preset name survives into the GLB — inspect imported clip names in your pipeline.

### Resume a stalled job (free)

Tripo jobs routinely sit at 99% for minutes; a timeout does NOT mean failure — the
task id is persisted in the sidecar and the spend already recorded. **Do not resubmit
(double-charges).** Resume instead:

```bash
python3 .claude/skills/godot-asset-gen-3d/tools/asset_gen_3d.py resume -o assets/glb/car.glb
```

Works for glb/rig/retarget; no-ops when the sidecar says complete.

### Set budget

```bash
python3 .claude/skills/godot-asset-gen-3d/tools/asset_gen_3d.py set_budget 500
```
Shared `assets/budget.json` with the 2D skill. Only call when the user explicitly
provides a budget.

### Output format

JSON to stdout: `{"ok": true, "path": "...", "cost_cents": 30}`; progress on stderr
(redirect to a temp file, read only on failure).

## Cost Table

| Operation | Options | Cost |
|---|---|---|
| GLB | default | 30¢ |
| GLB | hd | 60¢ |
| Rig | biped | +25¢ on top of mesh |
| Retarget | per clip | 10¢ |

A full 3D asset (2D ref 7¢ + default GLB 30¢) ≈ 37¢. A rigged biped with
walk/idle/attack ≈ 92¢.

## Biped presets (pass as `preset:biped:<name>`)

```
afraid agree angry_01 angry_02 angry_03 basketball_shot bow box_01 box_02
box_03 cast_a_spell cheer chop clap climb complain_01 complain_02
cross_body_crunch crossover_dribble cry dance_01 dance_02 dance_03 dance_04
dance_05 dance_06 defeat_02 defeat_03 depressed dig dive dribble fall fire
flee_01 flee_02 flip fold_arms football_catch football_save football_pass
freaky frightened front_kick_01 front_kick_02 frustrated_01 frustrated_02
golf greet_01 greet_02 greet_03 greet_04 heart_pose hit_to_body_01
hit_to_body_02 hit_to_head hit_to_side hit_to_stomach hug hurt idle
jump_down jump jump_rope_01 jump_rope_02 laugh_01 laugh_02 lift_heavy
look_around make_a_call_01 make_a_call_02 pitch_baseball play_mobile_game
play_video_game press-up run_upstairs run scared_01 scared_02 scratch shoot
shovel sing_01 sing_02 sing_03 sing_04 sit slash sob standing_relax surf
swagger swim turn victory_celebration volleyball wait walk warm_up
wave_goodbye_01 wave_goodbye_02
```
