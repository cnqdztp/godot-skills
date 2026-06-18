---
name: godot-scaffold
description: |
  Design game architecture and produce a compilable Godot project skeleton in C# (.NET) or GDScript (project.godot, .csproj for C#, STRUCTURE.md, script stubs, scene-builder stubs). Works for fresh projects and for adding/reworking subsystems in an existing one.
---

# Godot Scaffold Generator

Design game architecture and produce a compilable Godot project skeleton: `project.godot`, `STRUCTURE.md`, script stubs, and scene builder stubs (plus a `.csproj` for C# projects). Defines *what exists and how it connects* — not behavior.

Works for both fresh projects and incremental changes (adding scenes/scripts, reimplementing subsystems).

## Language: C# (.NET) or GDScript?

Detect the project's language before scaffolding — the steps below fork by language:

- A `.csproj`/`.sln` in the repo, or a `[dotnet]` section in `project.godot` ⇒ **C# (.NET)**.
- Otherwise ⇒ **GDScript**.

For a fresh project, follow the language the user asked for (default to GDScript if unspecified and there is no .NET toolchain). The **shared** parts (`project.godot`, `STRUCTURE.md`, the scene hierarchy / architecture design) are identical for both; only the script stubs, scene-builder stubs, and the build/verify commands differ. Each forking step below is tagged `(C# / .NET)` or `(GDScript)`.

## Workflow

1. **Check installed toolchain first** — run `godot --version` (always). **[C# only]** also run `dotnet --version` before writing the `.csproj`. Record the detected versions in `MEMORY.md` if the project is long-running.
2. **Match templates to the local toolchain** — never hardcode version-sensitive values from an example. At minimum, match:
   - `project.godot` `config_version` (both languages)
   - **[C# only]** `Project Sdk="Godot.NET.Sdk/..."`
   - **[C# only]** `TargetFramework`
   - any other engine-version-specific keys already present in an existing `project.godot`
   If a project already exists, preserve those version-sensitive values unless the user explicitly asked for a toolchain migration.
3. **Read `reference.png`** — understand the visual target: camera angle, distance, FOV, lighting direction, environment structure, scene layout. Use this to inform architecture decisions (node hierarchy, camera setup, lighting rig).
4. **Read input** — game description (fresh) or change request (incremental).
5. **Assess project state:**
   - No project → create from scratch.
   - Existing project, fresh start requested → delete existing scenes/scripts.
   - Existing project, incremental change → read existing `STRUCTURE.md`, `project.godot`, scripts (and `.csproj` for C#). Identify what to add or replace. Preserve unchanged files, especially version-sensitive settings.
6. **Design / update architecture** — scenes, scripts, signals, input actions. *(shared — language-agnostic)*
7. **Write/update `project.godot`** — create or merge input mappings. **[C# only]** include `[dotnet]` section. Match the local engine's expected `config_version`; do not guess. *(shared; the `[dotnet]` line is the only C#-specific part)*
8. **(C# / .NET) Write `.csproj`** — create or verify the project file exists. Match the local Godot/.NET toolchain instead of hardcoding an SDK version from examples. **(GDScript)** Skip — there is no `.csproj`; GDScript compiles on import.
9. **Write `STRUCTURE.md`** — always the complete architecture, not a diff. *(shared — language-agnostic)*
10. **Write script stubs** — for new scripts and any existing scripts the task explicitly asks to replace. **(C# / .NET)** `.cs` files in `scripts/`. **(GDScript)** `.gd` files in `scripts/`.
11. **Write the scene-builder base** — shared base class (see the `godot-scene-builder` skill). Create once per project; skip if it already exists. **(C# / .NET)** `scenes/SceneBuilderBase.cs`. **(GDScript)** the builders extend `SceneTree` directly, so there is no required base file — skip unless you factor out shared helpers into `scenes/scene_builder_base.gd`.
12. **(C# / .NET) Build .NET project** — `timeout 60 dotnet build 2>&1`. If this fails because the target framework or Godot SDK version does not match the installed toolchain, fix that first before changing game code. **(GDScript)** Skip — there is no compile step; GDScript is checked on import.
13. **Import assets** — `timeout 60 godot --headless --import 2>&1`. If Godot fails here because `project.godot` has the wrong `config_version` or incompatible engine keys, fix the project file before proceeding. *(shared — both languages)*
14. **Build scene stubs** — for each new/changed scene, write a scene builder script, then run in dependency order (leaf scenes first). **(C# / .NET)** `scenes/BuildXxx.cs` → `timeout 60 godot --headless --script scenes/BuildXxx.cs`. **(GDScript)** `scenes/build_xxx.gd` → `timeout 60 godot --headless --script scenes/build_xxx.gd`.
15. **Verify** — `timeout 60 godot --headless --quit 2>&1`. No `ERROR` lines. RID warnings are benign. *(shared — both languages)*
16. **Git commit** — repo is already initialized before Claude starts:
    ```bash
    git add -A && git commit -m "scaffold: project skeleton"
    ```

## Version-Sensitive Files

Treat these as local-toolchain outputs, not static templates:

- `project.godot` `config_version` (both languages)
- **[C# only]** `.csproj` `Project Sdk="Godot.NET.Sdk/..."`
- **[C# only]** `.csproj` `TargetFramework`

Rules:

- Existing project -> preserve the current values unless the user explicitly asked to migrate the toolchain.
- Fresh project -> detect the installed versions first and write matching values.
- Do not blindly copy `config_version=6`, `Godot.NET.Sdk/4.4.0`, or `net9.0` from examples.
- If the first `godot --headless --import` or `godot --headless --quit` reports a project-version mismatch, stop and fix the version fields before doing any more work.

## Output Files

### 1. `project.godot` *(shared — both languages)*

This example is schematic. Version-sensitive fields must match the installed local engine, not the literal values shown in an old template. The `[dotnet]` section is **[C# only]** — omit it for GDScript projects. Autoload paths point at `.cs` files for C# and `.gd` files for GDScript.

```ini
; Engine configuration file
; Do not edit manually

config_version={match local Godot}

[application]

config/name="{ProjectName}"
run/main_scene="res://scenes/main.tscn"

[display]

window/size/viewport_width=1280
window/size/viewport_height=720
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"

; [C# only] — omit this whole section for GDScript projects:
[dotnet]

project/assembly_name="{ProjectName}"

[physics]

common/physics_ticks_per_second=120
common/physics_interpolation=true
; 3D only — omit for 2D projects:
3d/physics_engine="Jolt Physics"

[rendering]

; 3D games:
lights_and_shadows/directional_shadow/soft_shadow_filter_quality=3
anti_aliasing/quality/msaa_3d=2
; 2D pixel art (instead of above):
; textures/canvas_textures/default_texture_filter=0
; 2d/snap/snap_2d_transforms_to_pixel=true

[layer_names]

; Name collision layers used by the game:
2d_physics/layer_1="player"
2d_physics/layer_2="enemies"
; (add as needed)

[autoload]

; Singletons — point at the script for the project's language:
; C#:        GameManager="*res://scripts/GameManager.cs"
; GDScript:  GameManager="*res://scripts/game_manager.gd"

[input]

move_forward={
"deadzone": 0.2,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":87,"key_label":0,"unicode":119)]
}
```

Key physical keycodes: W=87, A=65, S=83, D=68, Up=4194320, Down=4194322, Left=4194319, Right=4194321, Space=32, Enter=4194309, Escape=4194305, Shift=4194325, Ctrl=4194326, Alt=4194328.

Mouse buttons use InputEventMouseButton with button_index (1=left, 2=right) and matching button_mask:
```ini
fire={
"deadzone": 0.2,
"events": [Object(InputEventMouseButton,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"button_mask":1,"position":Vector2(0,0),"global_position":Vector2(0,0),"factor":1.0,"button_index":1,"canceled":false,"pressed":true,"double_click":false)]
}
```

### 2. `.csproj` — **[C# only]** (GDScript projects have no `.csproj`)

This example is schematic. Match the installed Godot and .NET versions on the machine running the project.

```xml
<Project Sdk="Godot.NET.Sdk/{match local Godot/.NET integration}">
  <PropertyGroup>
    <TargetFramework>{match installed dotnet}</TargetFramework>
    <EnableDynamicLoading>true</EnableDynamicLoading>
  </PropertyGroup>
</Project>
```

The file must be named `{ProjectName}.csproj` matching the `assembly_name` in project.godot.

### 3. `STRUCTURE.md` *(shared — language-agnostic)*

Complete architecture reference. Always written in full, even for incremental updates. The scene hierarchy, signal map, and asset hints are identical regardless of language; only the script file extensions in the paths differ (`.cs` for C#, `.gd` for GDScript).

````markdown
# {Project Name}

## Dimension: {2D or 3D}

## Input Actions

| Action | Keys |
|--------|------|
| move_forward | W, Up |
| jump | Space |

## Scenes

### Main
- **File:** res://scenes/main.tscn
- **Root type:** Node3D
- **Children:** Player, Enemy

### Player
- **File:** res://scenes/player.tscn
- **Root type:** CharacterBody3D

## Scripts

### PlayerController
- **File:** res://scripts/PlayerController.cs   ; (GDScript: res://scripts/player_controller.gd)
- **Extends:** CharacterBody3D
- **Attaches to:** Player:Player
- **Signals emitted:** Died, Scored
- **Signals received:** HurtBox.AreaEntered -> OnHurtEntered
- **Instantiates:** Bullet

## Signal Map

- Player:HurtBox.AreaEntered -> PlayerController.OnHurtEntered
- Main:GoalArea.BodyEntered -> LevelManager.OnGoalReached

## Asset Hints

- Player character model (~1.8m tall humanoid)
- Ground texture (tileable grass, 2m repeat)
- Sky panorama (360° daytime sky)
````

Architecture graph plus asset hints for the asset planner. No descriptions, no requirements, no task ordering.

### 4. `.gitignore`

Assets, tools, and build artifacts stay out of git:
```
assets
screenshots
.godot
*.import
bin/
obj/
```
`bin/` and `obj/` are **[C# only]** build artifacts; harmless to leave in a GDScript `.gitignore` but unnecessary.

### 4b. `screenshots/.gdignore`

Create `screenshots/` with an empty `.gdignore` so Godot's importer skips screenshot PNGs (they're not game textures):
```bash
mkdir -p screenshots && touch screenshots/.gdignore
```

Do NOT create `.gdignore` in `assets/` or any subdirectory of it — Godot must import those files. `.gdignore` makes the importer skip the entire directory silently.

### Runtime vs reference/debug separation

`assets/` contains only files the running game loads — it is the exportable subtree. Generation inputs (reference images used only to seed image_to_model, pose frames that don't ship, debug grids), sidecars, and meta files go outside `assets/` — either at repo root (like `reference.png`) or under a sibling like `refs/` or `_meta/` with its own `.gdignore`. Mixing them bloats APK exports and muddies what the asset planner considers "the asset set".

### 5. Script stubs

Write the stub in the project's language. Both versions encode the same architecture: correct base class, signal declarations, exported defaults, and empty lifecycle + handler methods.

#### (C# / .NET) — `scripts/*.cs`

```csharp
using Godot;

/// res://scripts/PlayerController.cs
public partial class PlayerController : CharacterBody3D
{
    [Signal] public delegate void DiedEventHandler();
    [Signal] public delegate void ScoredEventHandler();

    [Export] public float Speed = 7.0f;
    [Export] public float JumpVelocity = -4.5f;

    public override void _Ready()
    {
    }

    public override void _PhysicsProcess(double delta)
    {
    }

    private void OnHurtEntered(Area3D area)
    {
    }
}
```

Correct base class, signal delegate declarations, `[Export]` defaults, empty lifecycle and handler methods. All classes `partial`.

#### (GDScript) — `scripts/*.gd`

GDScript has no `.csproj` and no compile step — it is checked on import. Use `extends <BaseClass>`, `@export var` (instead of `[Export]`), and `signal` declarations (instead of `[Signal]` delegates). No `partial`, no `EventHandler` suffix.

```gdscript
# res://scripts/player_controller.gd
extends CharacterBody3D

signal died
signal scored

@export var speed: float = 7.0
@export var jump_velocity: float = -4.5

func _ready() -> void:
    pass

func _physics_process(delta: float) -> void:
    pass

func _on_hurt_entered(area: Area3D) -> void:
    pass
```

Correct `extends` base class, `signal` declarations, `@export var` defaults, empty lifecycle and handler methods. Add `class_name PlayerController` only if the script needs a global type name.

### 6. Scene-builder base

**(C# / .NET) — `scenes/SceneBuilderBase.cs`** — create once; all builders inherit from this. See the `godot-scene-builder` skill for the full base class.

**(GDScript)** — there is no required base file. GDScript builders `extends SceneTree` directly and implement `func _initialize()`. Only factor out a shared `scenes/scene_builder_base.gd` if multiple builders share helper code.

### 7. Scene builder stubs

Write each scene builder in the project's language — replace all UPPER_CASE placeholders with concrete values, delete optional blocks (SCRIPT, CHILDREN) that don't apply.

#### (C# / .NET) — `scenes/Build*.cs`

```csharp
using Godot;

/// Scene builder — run: dotnet build && timeout 60 godot --headless --script scenes/Build<Name>.cs
public partial class Build<Name> : SceneBuilderBase
{
    public override void _Initialize()
    {
        var temp = new Node();
        var root = new ROOT_TYPE();         // REPLACE ROOT_TYPE — e.g. CharacterBody3D
        root.Name = "ROOT_NAME";            // REPLACE ROOT_NAME — e.g. "Player"
        temp.AddChild(root);

        // CHILDREN — delete block if none, duplicate per child
        var childVar = GD.Load<PackedScene>("CHILD_PATH").Instantiate();  // REPLACE CHILD_PATH
        childVar.Name = "CHILD_NAME";       // REPLACE CHILD_NAME
        root.AddChild(childVar);

        // SCRIPTS — set LAST (SetScript disposes C# wrapper — see the godot-quirks skill)
        root.SetScript(GD.Load("SCRIPT_PATH"));  // REPLACE — e.g. "res://scripts/PlayerController.cs"

        // Re-obtain root (old wrapper is disposed)
        var rootNode = temp.GetChild(0);
        temp.RemoveChild(rootNode);
        temp.Free();

        PackAndSave(rootNode, "OUTPUT_PATH");  // REPLACE — e.g. "res://scenes/player.tscn"
    }
}
```

#### (GDScript) — `scenes/build_*.gd`

GDScript scene builders `extends SceneTree` and run via `godot --headless --script scenes/build_xxx.gd`. No `dotnet build` precedes them — they run straight after `--import`. Assigning the script does not dispose a wrapper (that C# quirk does not apply), so the owner/pack flow is simpler.

```gdscript
# Scene builder — run: timeout 60 godot --headless --script scenes/build_<name>.gd
extends SceneTree

func _initialize() -> void:
    var root := ROOT_TYPE.new()          # REPLACE ROOT_TYPE — e.g. CharacterBody3D
    root.name = "ROOT_NAME"              # REPLACE ROOT_NAME — e.g. "Player"

    # CHILDREN — delete block if none, duplicate per child
    var child := load("CHILD_PATH").instantiate()  # REPLACE CHILD_PATH
    child.name = "CHILD_NAME"            # REPLACE CHILD_NAME
    root.add_child(child)
    child.owner = root

    # SCRIPT — delete if none
    root.set_script(load("SCRIPT_PATH")) # REPLACE — e.g. "res://scripts/player_controller.gd"

    var packed := PackedScene.new()
    packed.pack(root)
    ResourceSaver.save(packed, "OUTPUT_PATH")  # REPLACE — e.g. "res://scenes/player.tscn"
    quit(0)
```

Every child's `owner` must be set to `root` (directly or transitively) or it will be dropped from the packed scene. Always `quit(0)` at the end so the headless run exits.

**CRITICAL: Build order is specified in STRUCTURE.md.** The `## Build Order` section lists the exact sequence. Follow it mechanically — do not infer or reorder.

## UI Overlay Architecture

For HUD/menus, add to the main scene:

```
Main (Node3D or Node2D)
├── ... game nodes ...
└── CanvasLayer (layer=1)
    └── Control (anchors_preset=15, full rect)
        ├── VBoxContainer or HBoxContainer
        │   ├── Label (score)
        │   ├── ProgressBar (health)
        │   └── Button (pause)
        └── ...
```

**Layout containers:**
- `VBoxContainer` — vertical stack; `HBoxContainer` — horizontal
- `GridContainer` — grid (set `Columns` property)
- `MarginContainer` — padding; `CenterContainer` — centering; `PanelContainer` — with background
- `SizeFlagsHorizontal/Vertical = SizeFlags.ExpandFill` *(C#)* / `size_flags_horizontal = SIZE_EXPAND_FILL` *(GDScript)*
- `CustomMinimumSize` *(C#)* / `custom_minimum_size` *(GDScript)* for fixed dimensions

For pause menus, set the CanvasLayer to run during pause: `ProcessMode = ProcessModeEnum.Always` *(C#)* / `process_mode = Node.PROCESS_MODE_ALWAYS` *(GDScript)*.

## Architecture Rules

1. **Explicit 2D or 3D** — never mix dimensions in the same hierarchy.
2. **Declare all input actions** — anything used by scripts must appear in input table and project.godot.
3. **Signal contracts** — if script A emits signal X, receivers must list it in the signal map.

## Common Built-in Signals

- Area2D/3D — BodyEntered, BodyExited, AreaEntered, AreaExited
- Button — Pressed
- Timer — Timeout
- AnimationPlayer — AnimationFinished
- RigidBody2D/3D — BodyEntered (ContactMonitor required)

## Common Errors

**(C# / .NET)**
- **`CS0260: Missing partial modifier`** — all Godot C# classes MUST be declared `partial`. Add `partial` keyword.
- **[C# only] `dotnet build` must succeed before `godot --headless --script`** — scene builders and runtime scripts compile together; a build failure means none of the script changes take effect. Always run and pass `dotnet build` first.
- **[C# only] C# enum names — don't guess, look up** — LLM training data is mostly GDScript, so C# enum member names (e.g. `ProcessModeEnum.Always`, `SizeFlags.ExpandFill`, `Key.Space`) are easy to hallucinate. Verify the exact C# spelling (via the `godot-api` skill) rather than translating a GDScript constant.
- **`GD.Load()` returns null** — asset not imported yet. Run `godot --headless --import` first.
- **Scene builder hangs** — missing `Quit()` call. The template includes `Quit(0)` — never remove it.
- **Signal delegate wrong name** — must end in `EventHandler`. `[Signal] public delegate void Died();` fails silently; use `DiedEventHandler`.

**(GDScript)**
- **`load()` returns null** — asset not imported yet. Run `godot --headless --import` first.
- **Scene builder hangs** — missing `quit()` call. The template includes `quit(0)` — never remove it.
- **Child missing from packed scene** — every child's `owner` must be set to the scene root (directly or transitively) before `PackedScene.pack()`, or it is silently dropped.
- **Parse error on import** — GDScript is validated at import, not compiled ahead of time; a typo surfaces as an `ERROR` during `--import`/`--quit`, not at a separate build step.

## Asset Hints in STRUCTURE.md

Assets are generated AFTER scaffold. Include an `## Asset Hints` section at the end of STRUCTURE.md listing what visual assets the architecture needs. The asset planner uses these to decide what to generate.

```markdown
## Asset Hints

- Player character model (~1.8m tall humanoid)
- Ground texture (tileable grass, 2m repeat)
- Sky panorama (360° daytime sky)
- Enemy model (~1m tall creature)
```

Be specific about type (model, texture, background, sprite), approximate size, and visual role. Don't describe style — the asset planner chooses that.

### Build Order

The scaffold emits an explicit build order in STRUCTURE.md based on scene dependency analysis. Leaf scenes (no child scene references) first, parents after.

**(C# / .NET)** — `dotnet build` is always step 1:

```markdown
## Build Order
1. dotnet build
2. scenes/BuildPlayer.cs → scenes/player.tscn
3. scenes/BuildEnemy.cs → scenes/enemy.tscn
4. scenes/BuildMain.cs → scenes/main.tscn (depends: player.tscn, enemy.tscn)
```

**(GDScript)** — no `dotnet build`; the first step is the import (GDScript is checked then):

```markdown
## Build Order
1. godot --headless --import
2. scenes/build_player.gd → scenes/player.tscn
3. scenes/build_enemy.gd → scenes/enemy.tscn
4. scenes/build_main.gd → scenes/main.tscn (depends: player.tscn, enemy.tscn)
```

The task executor follows this order mechanically. Do not rely on the executor to infer dependencies.

## What NOT to Include

- Implementation details or behavior descriptions
- Task ordering
- Lighting, environment, tonemapping, post-processing
- Any logic beyond empty method stubs — real scripts are written in a later stage
