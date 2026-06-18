# godot-skills

A collection of **Agent Skills** for building games in **Godot 4** — in the open
[Agent Skills](https://agentskills.io) format (`skills/<name>/SKILL.md`), portable across
agents, and also exposed as a [Claude Code](https://code.claude.com) plugin marketplace.
**C# (.NET) and GDScript are both first-class**: every skill that used to be C#-only now
documents the GDScript path too, while keeping the C#-specific tips.

## Install

**Any agent** (Claude Code, Cursor, Codex, Gemini CLI, … — via the cross-agent
[`skills`](https://github.com/vercel-labs/skills) CLI):

```bash
npx skills add cnqdztp/godot-skills            # all skills, into your detected agents
npx skills add cnqdztp/godot-skills --list     # preview them first
npx skills add cnqdztp/godot-skills@godot-mobile-web -g   # one skill, global
```

**Claude Code** (as a plugin) — alternatively:

```
/plugin marketplace add cnqdztp/godot-skills
/plugin install godot@godot-skills
```

Either way you get all the skills below. Under Claude Code they're invoked as
`/godot:<skill-name>`; most also auto-trigger from their `description` when relevant.

## Skills

| Skill | What it covers |
|-------|----------------|
| `godot-mobile-web` | GDScript web (HTML5) + mobile + portrait desktop-pet conventions: audio-autoplay gesture, on-screen-keyboard export flag, seamless scrolling backdrop, shadow-at-feet, coroutine overlap, downloadable packs, headless QA. |
| `godot-api` | Targeted Godot class/API + C#/GDScript syntax lookup. **Version- and language-aware**: stores a separate API tree per Godot version and language. |
| `godot-quirks` | Engine-level gotchas for both C# and GDScript (serialization, physics, cameras, container relayout / `offset_transform`, …). |
| `godot-ui-tscn` | Author UI as `.tscn` scenes + thin scripts; 3-layer styling. |
| `godot-ui-foundation` | Viewport stretch, HiDPI/Retina scaling, theme taxonomy, variable-font weights. |
| `godot-asset-gen` | Generate images / 3D models / sprite sheets (Gemini, Grok, Tripo3D), bg removal, slicing. |
| `godot-automatic-ui-qa` | Inject a screenshot timer, run the project, and read the PNG yourself to verify UI. |
| `godot-capture` | Headless screenshot + video capture (Xvfb/Vulkan) for C# or GDScript projects. |
| `godot-passthrough-game` | Transparent desktop-pet / widget / overlay games and their click-through traps. |
| `godot-scaffold` | Design architecture + emit a compilable project skeleton (C# `.csproj` or GDScript). |
| `godot-scene-builder` | Generate `.tscn` files programmatically with a headless SceneTree builder (C# or GDScript). |
| `godot-test-harness` | Write a SceneTree test script (C# `.cs` or GDScript `.gd`) for visual verification. |
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
