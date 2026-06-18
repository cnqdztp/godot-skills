#!/usr/bin/env bash
# Bootstrap a VERSIONED, LANGUAGE-SPECIFIC Godot API reference for the godot-api skill.
#
# Detects the target project's Godot version and language (or takes overrides),
# clones the matching Godot docs (sparse checkout), and generates per-class C#/GDScript
# markdown under  doc_api/<version>/<lang>/ .  Multiple <version>/<lang> trees coexist
# and are reused across projects. Safe to re-run — skips a version+lang that already exists.
#
# Usage:
#   bash ensure_doc_api.sh [--project-dir DIR] [--version X.Y] [--lang gdscript|csharp]
#     --project-dir  project whose project.godot is read for version/language (default: $PWD)
#     --version      override the detected Godot version (e.g. 4.7)
#     --lang         override the detected language (gdscript | csharp)
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$SKILL_DIR/tools"

PROJECT_DIR="$PWD"
VERSION=""
API_LANG=""   # not LANG: that's the shell locale var

while [ $# -gt 0 ]; do
    case "$1" in
        --project-dir) PROJECT_DIR="$2"; shift 2 ;;
        --version)     VERSION="$2"; shift 2 ;;
        --lang)        API_LANG="$2"; shift 2 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

PROJECT_GODOT="$PROJECT_DIR/project.godot"

# --- Detect Godot version: first element of config/features, e.g. ("4.7", ...) ---
if [ -z "$VERSION" ] && [ -f "$PROJECT_GODOT" ]; then
    VERSION="$(grep -oE 'config/features=PackedStringArray\("[0-9]+\.[0-9]+' "$PROJECT_GODOT" 2>/dev/null \
               | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)"
fi
if [ -z "$VERSION" ]; then
    echo "godot-api: could not detect a Godot version from $PROJECT_GODOT" >&2
    echo "  pass --version X.Y (e.g. --version 4.7)" >&2
    exit 1
fi

# --- Detect language: C# if a .csproj/.sln, a [dotnet] section, or a csharp tag exists ---
if [ -z "$API_LANG" ]; then
    if find "$PROJECT_DIR" -maxdepth 2 \( -name '*.csproj' -o -name '*.sln' \) 2>/dev/null | grep -q . \
       || grep -qE '^\[dotnet\]' "$PROJECT_GODOT" 2>/dev/null \
       || grep -qiE 'config/tags=PackedStringArray\([^)]*(csharp|c#)' "$PROJECT_GODOT" 2>/dev/null; then
        API_LANG="csharp"
    else
        API_LANG="gdscript"
    fi
fi
case "$API_LANG" in gdscript|csharp) ;; *) echo "invalid --lang: $API_LANG" >&2; exit 2 ;; esac

DOC_SOURCE="$SKILL_DIR/doc_source/$VERSION"
DOC_API="$SKILL_DIR/doc_api/$VERSION/$API_LANG"

echo "godot-api: version=$VERSION lang=$API_LANG  (project: $PROJECT_DIR)"

if [ -d "$DOC_API" ] && [ -f "$DOC_API/_common.md" ]; then
    echo "Already generated at $DOC_API"
    exit 0
fi

# --- Clone the matching Godot docs (sparse). Try <version>, then <version>-stable. ---
if [ ! -d "$DOC_SOURCE/godot/doc/classes" ]; then
    mkdir -p "$DOC_SOURCE"
    cloned=0
    for ref in "$VERSION" "$VERSION-stable"; do
        echo "Cloning godot docs @ $ref ..."
        if git clone --depth 1 --filter=blob:none --sparse --branch "$ref" \
                https://github.com/godotengine/godot.git "$DOC_SOURCE/godot" 2>/dev/null; then
            cloned=1; break
        fi
        rm -rf "$DOC_SOURCE/godot"
    done
    if [ "$cloned" -ne 1 ]; then
        echo "WARNING: no tag/branch for '$VERSION'; falling back to the default branch (latest)." >&2
        git clone --depth 1 --filter=blob:none --sparse \
            https://github.com/godotengine/godot.git "$DOC_SOURCE/godot"
    fi
    git -C "$DOC_SOURCE/godot" sparse-checkout set doc/classes
fi

# --- Generate per-class markdown for this version + language ---
mkdir -p "$DOC_API"
PYTHONPATH="$TOOLS_DIR" python3 "$TOOLS_DIR/godot_api_converter.py" \
    -i "$DOC_SOURCE/godot/doc/classes" \
    --split-dir "$DOC_API" \
    --class-desc full \
    --method-desc full \
    --property-desc full \
    --signal-desc full \
    --constant-desc full \
    --include-virtual \
    --full-signals \
    --lang "$API_LANG"

# --- Record what this tree is, for cache-validity checks ---
cat > "$DOC_API/_meta.json" <<EOF
{
  "version": "$VERSION",
  "lang": "$API_LANG",
  "source": "github.com/godotengine/godot",
  "generated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "doc_api ready at $DOC_API"
