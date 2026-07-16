# Meshy Provider Guide

Read this file before any Meshy task. Use the shared CLI at
`tools/asset_gen_3d.py`; the API client is `meshy/client.py`. `SKILL_DIR` below means the
absolute directory containing the parent `SKILL.md`.

## Safety and billing

Require `MESHY_API_KEY`. Before submitting a paid task, show the complete pipeline and
current estimate:

| Stage | Current charge |
|---|---:|
| Textured Meshy-6/latest or low-poly Image-to-3D | 30 credits |
| Humanoid auto-rig | 5 credits |
| Custom animation | 3 credits each |

Charges are service credits, not cents. Do not convert them to money because their value
depends on the user's plan. Re-check the official
[pricing page](https://docs.meshy.ai/en/api/pricing) before a large batch.

## Image to GLB

Local PNG/JPEG files are submitted as Data URIs, so they do not need public hosting.

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" glb \
  --provider meshy --image assets/img/car.png -o assets/glb/car.glb
```

Quality mapping:

| `--quality` | Meshy request behavior |
|---|---|
| `default` | Meshy latest, textured PBR, triangle remesh to `--face-limit` (30000 default) |
| `hd` | No remesh cap and 4K base-color texture |
| `lowpoly` | Meshy low-poly model |

Use `--no-pbr` only when the PBR output is visibly wrong. For `default`, Meshy accepts
`--face-limit` values from 100 to 300000.

## Humanoid rigging

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" rig \
  --provider meshy --height-meters 1.8 \
  --image assets/img/hero.png -o assets/glb/hero_rigged.glb
```

The CLI generates the intermediate character in A-pose, waits for Image-to-3D to finish,
then passes that task ID directly to Rigging. Meshy rigging needs a textured humanoid with
clear limbs; `--height-meters` must be positive and defaults to 1.7.

## Custom animation

Pass a numeric Meshy `action_id`; provider detection comes from the rig sidecar.

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" retarget \
  --rigged assets/glb/hero_rigged.glb --animation 92 \
  -o assets/glb/hero_attack.glb
```

Select IDs from Meshy's official
[Animation Library](https://docs.meshy.ai/en/api/animation-library). Inspect the imported
clip name in Godot instead of assuming the action name survives in the GLB. In the current
library, action `92` is `Double_Combo_Attack`; re-check the live library when precision
matters.

## Async and resume behavior

Meshy POST responses contain a task ID, not a model. The client polls the matching GET
endpoint until `SUCCEEDED`, then downloads the documented GLB URL. It treats `FAILED` and
`CANCELED` as terminal and records accepted tasks in `<output>.meshy.json` before polling.

On timeout, run shared `resume`; never create a replacement task. A rig resume continues
from the saved Image-to-3D or Rigging stage, and animation resume reuses its saved task ID.
If any billable POST times out before returning its ID, an older pipeline sidecar may
exist, but it cannot identify that submission. The CLI marks it `manual_check_required`
and blocks both the original command and `resume`. Check the Meshy dashboard before any
manual recovery or new submission.

## Official references

- [Authentication](https://docs.meshy.ai/en/api/authentication)
- [Image to 3D](https://docs.meshy.ai/en/api/image-to-3d)
- [Rigging](https://docs.meshy.ai/en/api/rigging)
- [Animation](https://docs.meshy.ai/en/api/animation)
- [Meshy 3D Agent](https://github.com/meshy-dev/meshy-3d-agent) — design reference only;
  do not copy its scripts or prompts into this skill
