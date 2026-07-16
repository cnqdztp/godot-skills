# Tripo3D Provider Guide

Read this file before any Tripo task. Use the shared CLI at
`tools/asset_gen_3d.py`; the API client is `tripo/client.py`. `SKILL_DIR` below means the
absolute directory containing the parent `SKILL.md`.

## Safety and billing

Require `TRIPO3D_API_KEY`. Before submitting a paid task, show the complete pipeline and
current estimate:

| Stage | Charge |
|---|---:|
| Default GLB | 30¢ |
| HD GLB | 60¢ |
| Biped rig | +25¢ |
| Animation | 10¢ each |

The shared `assets/budget.json` can guard Tripo spending:

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" set_budget 500
```

Call `set_budget` only when the user explicitly provides a budget.

## Image to GLB

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" glb \
  --image assets/img/car.png -o assets/glb/car.glb
```

`default` uses v3.1 standard geometry/texture, PBR, and a 30000 face cap. `hd` uses
detailed geometry and texture with no face cap. Tripo does not expose a separate low-poly
mode; lower `--face-limit` instead. Use `--no-pbr` only when PBR looks wrong.

## Biped rigging

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" rig \
  --image assets/img/hero.png -o assets/glb/hero_rigged.glb
```

The pipeline runs Image-to-Model → pre-rig check → biped rig. Abort when the pre-rig
check reports a non-biped; use plain `glb` for those assets.

## Animation

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" retarget \
  --rigged assets/glb/hero_rigged.glb \
  --animation preset:biped:walk -o assets/glb/hero_walk.glb
```

Reuse the rig task from the sidecar. Do not regenerate or re-rig for each clip.

Available biped preset names:

```text
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

## Async and resume behavior

Accepted tasks are written to `<output>.tripo.json` before polling. A timeout means the
task may still be finishing; run shared `resume` and never resubmit. Rig resume continues
from Image-to-Model, pre-rig check, or rigging. Animation resume reuses the saved task ID.
If any billable POST times out before returning its ID, an older pipeline sidecar may
exist but cannot identify that submission. Check the Tripo dashboard before recovery or a
new submission; never blindly retry a billable POST.

## Official references

- [Generation](https://platform.tripo3d.ai/docs/generation)
- [Animation](https://platform.tripo3d.ai/docs/animation)
