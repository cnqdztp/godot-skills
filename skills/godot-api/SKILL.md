---
name: godot-api
display_name: Godot API Lookup
short_description: Targeted Godot class and C#/GDScript API lookup, version-aware
default_prompt: "Use /godot-api to answer a specific Godot API or C#/GDScript Godot syntax question."
allow_implicit_invocation: false
description: |
  Look up Godot engine class APIs, methods, properties, signals, enums, or C#/GDScript Godot syntax. Use when you need a targeted Godot API answer or a specific engine-class recommendation. The reference is version- and language-aware: it generates and stores a separate API tree per Godot version and per language (gdscript / csharp), and pulls a fresh one when the project's version doesn't match.
context: fork
model: sonnet
agent: Explore
---

# Godot API Lookup

A narrow reference tool. Keep answers targeted to the caller's question.

The reference lives under `${CLAUDE_PLUGIN_ROOT}/skills/godot-api/doc_api/<version>/<lang>/`
— one tree per Godot version (e.g. `4.7`) and language (`gdscript` or `csharp`). Several
trees coexist and are reused across projects. **Do not list or enumerate `doc_api/` or
`doc_source/`** — they contain hundreds of files. Navigate via `_common.md`, `_other.md`,
and the specific class file you need.

## Step 0 — detect the project's Godot version and language

Pick the tree that matches the project under discussion (default: the current directory).

- **Version** — first element of `config/features` in `project.godot`:
  ```bash
  grep -oE 'config/features=PackedStringArray\("[0-9]+\.[0-9]+' project.godot | grep -oE '[0-9]+\.[0-9]+' | head -1
  ```
- **Language** — `csharp` if the project has a `*.csproj`/`*.sln`, a `[dotnet]` section in
  `project.godot`, or a `csharp` entry in `config/tags`; otherwise `gdscript`.

So `<version>/<lang>` is e.g. `4.7/gdscript` or `4.6/csharp`.

## Step 1 — ensure the matching reference exists

If `${CLAUDE_PLUGIN_ROOT}/skills/godot-api/doc_api/<version>/<lang>/_common.md` is missing,
generate it (auto-detects version + language from the project; pass overrides if needed). The
script clones the matching Godot docs tag and is a no-op if that tree already exists:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/godot-api/tools/ensure_doc_api.sh --project-dir <project>
# overrides: --version 4.7 --lang gdscript|csharp
```

If the stored tree's version doesn't match the project's, generate the project's version (the
old one stays cached for other projects). Each tree carries a `_meta.json` recording its
version/lang.

## Step 2 — answer

Let `DOC=${CLAUDE_PLUGIN_ROOT}/skills/godot-api/doc_api/<version>/<lang>`.

1. If you already know the likely class, search `$DOC/_common.md` and `$DOC/_other.md` for the
   class name instead of reading the whole index files.
2. If the caller does not name a class, use `$DOC/_common.md` and `$DOC/_other.md` to identify
   candidates, then read only the relevant docs.
3. Read only the relevant `$DOC/{ClassName}.md` file(s).
4. Return only what the caller needs:
   - **Specific question** ("how to detect collisions") → the relevant methods/signals/patterns
     with short descriptions.
   - **Full API request** ("full API for CharacterBody3D") → the whole class doc summary.

**Syntax reference (pick by detected language):**
- GDScript → `${CLAUDE_PLUGIN_ROOT}/skills/godot-api/gdscript.md`
- C# → `${CLAUDE_PLUGIN_ROOT}/skills/godot-api/csharp.md`

Read it when the caller asks about Godot syntax, idioms, or common patterns (input handling,
tweens, state machines, signals). The per-class `doc_api` files are already rendered in the
selected language (snake_case/GDScript types vs PascalCase/C# types).
