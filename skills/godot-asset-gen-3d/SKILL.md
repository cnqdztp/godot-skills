---
name: godot-asset-gen-3d
description: |
  Generate 3D game assets through Tripo3D or Meshy: convert PNG/JPEG references to GLB, rig humanoid characters, apply preset animations, and resume stalled jobs without resubmitting. Use for any 3D model, GLB, rigging, or character-animation need; use godot-asset-gen first when a 2D reference image is needed. Supports TRIPO3D_API_KEY and MESHY_API_KEY.
---

# 3D Asset Generator

Run image → GLB → optional humanoid rig → optional animation through a single CLI.
Keep runtime-loaded outputs under `assets/`.

## Choose and load a provider

Honor an explicit provider choice. Otherwise keep `tripo` as the backward-compatible
default. Prefer Meshy when the user requests Meshy or low-poly generation.

Before using a provider, read its complete guide:

- **Meshy**: [meshy/reference.md](meshy/reference.md)
- **Tripo3D**: [tripo/reference.md](tripo/reference.md)

Do not load both provider guides unless comparing providers or auto-detecting an ambiguous
sidecar. Provider clients live beside their guides; the shared CLI stays under `tools/`.

## Plan paid work

Before the first billable submission, state the chosen provider, every planned stage, and
the estimated total charge. Ask for confirmation unless the user already approved that
exact provider and charge in the current turn. Never silently add rigging or animation.

Set only the API key for the chosen provider:

- Meshy: `MESHY_API_KEY`
- Tripo: `TRIPO3D_API_KEY`

Never print, persist, or commit API keys.

## Prepare the reference image

Use **godot-asset-gen** first when no reference exists. A useful prompt shape is:

```text
3D model reference of {name}. {description}. 3/4 front elevated camera angle, solid
white background, soft diffused studio lighting, matte material finish, single centered
subject, no shadows on background. Any windows or glass should be solid tinted (opaque).
```

Review the image before conversion. Preserve the solid background, especially for Tripo.

## Shared CLI

Set `SKILL_DIR` to the absolute directory containing this `SKILL.md`; do not assume a
Claude-, Codex-, or repository-specific install path. Run from the Godot project root:

```bash
# Image to GLB; omit --provider for Tripo
python3 "$SKILL_DIR/tools/asset_gen_3d.py" glb \
  --provider meshy --image assets/img/car.png -o assets/glb/car.glb

# Image to rigged humanoid
python3 "$SKILL_DIR/tools/asset_gen_3d.py" rig \
  --provider meshy --image assets/img/hero.png -o assets/glb/hero_rigged.glb

# Provider is detected from the rig sidecar
python3 "$SKILL_DIR/tools/asset_gen_3d.py" retarget \
  --rigged assets/glb/hero_rigged.glb --animation 92 \
  -o assets/glb/hero_attack.glb
```

Both riggers are humanoid/biped only. Use plain `glb` for props and quadrupeds.

## Resume instead of resubmitting

After a provider returns a task ID, the CLI immediately stores it in a sidecar before
polling. A polling timeout does not mean failure; resubmitting can charge twice.

```bash
python3 "$SKILL_DIR/tools/asset_gen_3d.py" resume \
  -o assets/glb/car.glb
```

Resume auto-detects `.tripo.json` or `.meshy.json`. If both exist for the same output,
pass `--provider tripo` or `--provider meshy`.

If any billable POST times out before returning its task ID, an older pipeline sidecar may
exist, but it cannot identify or recover that submission. The CLI marks the output
`manual_check_required` and refuses automatic retry. Check the provider dashboard before
running `resume` or submitting again.

The CLI prints progress to stderr and one JSON result to stdout. Meshy results include
`credits`; Tripo results include `cost_cents`. Provider sidecars retain task IDs, stages,
status, and reported usage.
