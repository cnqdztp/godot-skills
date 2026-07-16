# godot-skills

A collection of **Agent Skills** for building games in **Godot 4** — in the open
[Agent Skills](https://agentskills.io) format (`skills/<name>/SKILL.md`), portable across
agents, and also exposed as a [Claude Code](https://code.claude.com) plugin marketplace.
**C# (.NET) and GDScript are both first-class**: every skill that used to be C#-only now
documents the GDScript path too, while keeping the C#-specific tips.

## Install

```bash
npx skills add cnqdztp/godot-skills
```

Under Claude Code the skills are invoked as `/godot:<skill-name>`; most also
auto-trigger from their `description` when relevant.

## Skills

| Skill | What it covers |
|-------|----------------|
| `godot-mobile-web` | GDScript web (HTML5) + mobile + portrait desktop-pet conventions: audio-autoplay gesture, on-screen-keyboard export flag, seamless scrolling backdrop, shadow-at-feet, coroutine overlap, downloadable packs, headless QA. |
| `godot-api` | Targeted Godot class/API + C#/GDScript syntax lookup. **Version- and language-aware**: stores a separate API tree per Godot version and language. |
| `godot-quirks` | Engine-level gotchas for both C# and GDScript (serialization, physics, cameras, container relayout / `offset_transform`, …). |
| `godot-ui-tscn` | Author UI as `.tscn` scenes + thin scripts; 3-layer styling. |
| `godot-ui-foundation` | Viewport stretch, HiDPI/Retina scaling, theme taxonomy, variable-font weights. |
| `godot-input` | Multi-device input architecture (C#/GDScript): a semantic-action normalization bus, Steam Input decoupled behind an always-present Godot fallback (plays without Steam), mouse↔controller device switching, focus-based controller navigation, rebinding **without** mutating `InputMap`, per-controller button glyphs, and the touch seam. |
| `godot-asset-gen` | Generate 2D images (Gemini / gpt-image-2 / Wan, via official APIs or wavespeed.ai) and animated sprite sheets (Seedance / Wan video + loop detection); background removal, grid slicing, budget-based asset planning. |
| `godot-asset-gen-3d` | Generate 3D assets via Tripo3D or Meshy: image → GLB, humanoid rigging, provider animation libraries, stalled-job resume, and provider-aware usage tracking. |
| `godot-automatic-qa` | Self-verify your work: a headful screenshot loop (inject a timer, run the project, read the PNG yourself) for visual checks, plus a headless `SceneTree` test script (ASSERT, simulated input) for behavioral checks. |
| `godot-capture` | Headless screenshot + video capture (Xvfb/Vulkan) for C# or GDScript projects. |
| `godot-passthrough-game` | Transparent desktop-pet / widget / overlay games and their click-through traps. |
| `godot-scaffold` | Design architecture + emit a compilable project skeleton (C# `.csproj` or GDScript). |
| `godot-scene-builder` | Generate `.tscn` files programmatically with a headless SceneTree builder (C# or GDScript). |
| `godot-android-export` | Export a Godot project (C# or GDScript) as an Android APK. |

## Note: `godot-api` bootstrap

`godot-api` generates its reference on first use (it clones the matching Godot docs tag and
renders per-class markdown into `doc_api/<version>/<lang>/`, which is git-ignored — not shipped
in this repo). It runs automatically from the skill; to pre-warm it for a project:

```bash
bash <plugin>/skills/godot-api/tools/ensure_doc_api.sh --project-dir /path/to/project
# or force a target:  --version 4.7 --lang gdscript|csharp
```

It detects the Godot version (`config/features` in `project.godot`) and language
(`.csproj`/`.sln`/`[dotnet]`/`config/tags`), and reuses an already-generated tree.

## License

MIT — see [LICENSE](LICENSE).
