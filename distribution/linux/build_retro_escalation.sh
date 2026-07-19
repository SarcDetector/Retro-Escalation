#!/usr/bin/env bash
set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${RE_OSCR_PYTHON:-$repo_root/.venv/bin/python}"
work_root="$repo_root/.artifacts/pyinstaller/linux"
app_name="RE-OSCR"
output_root=""
package=false

usage() {
    printf 'Usage: %s --output-root PATH [--package]\n' "$0"
}

while (($#)); do
    case "$1" in
        --output-root)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            output_root="$2"
            shift 2
            ;;
        --package)
            package=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -n "$output_root" ]] || { usage >&2; exit 2; }
[[ -x "$python" ]] || {
    printf 'The repository virtual environment is missing. Create .venv and install .[pyinst].\n' >&2
    exit 1
}

# Capture source identity before PyInstaller creates or replaces any output files.
commit="$(git -c "safe.directory=$repo_root" -C "$repo_root" rev-parse HEAD 2>/dev/null || printf 'unknown')"
if [[ -z "$(git -c "safe.directory=$repo_root" -C "$repo_root" status --porcelain)" ]]; then
    working_tree="clean"
else
    working_tree="uncommitted changes included"
fi

mkdir -p "$output_root" "$work_root"
output_root="$(CDPATH= cd -- "$output_root" && pwd)"
app_output="$output_root/$app_name"

version="$($python -c 'import re, sys; text = open(sys.argv[1], encoding="utf-8").read(); match = re.search(r"__version__\s*=\s*[\"'"'"']([^\"'"'"']+)", text); print(match.group(1) if match else "")' "$repo_root/retro_escalation.py")"
[[ -n "$version" ]] || { printf 'Unable to read the RE-OSCR version.\n' >&2; exit 1; }

"$python" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name "$app_name" \
    --distpath "$output_root" \
    --workpath "$work_root/work" \
    --specpath "$work_root" \
    --add-data "$repo_root/assets:assets" \
    --add-data "$repo_root/locales:locales" \
    --add-data "$repo_root/theme_assets:theme_assets" \
    "$repo_root/retro_escalation.py"

cp "$repo_root/LICENSE" "$app_output/LICENSE"
cp "$repo_root/README.md" "$app_output/README.md"
mkdir -p "$app_output/docs" "$app_output/distribution/linux"
for document in PROJECT_SCOPE.md TESTING.md DEVELOPMENT.md; do
    cp "$repo_root/docs/$document" "$app_output/docs/$document"
done
release_note="$repo_root/docs/releases/v$version.md"
if [[ -f "$release_note" ]]; then
    cp "$release_note" "$app_output/docs/"
fi
cp "$repo_root/distribution/linux/README.md" "$app_output/distribution/linux/README.md"
chmod +x "$app_output/$app_name"

cat > "$app_output/BUILD_INFO.txt" <<EOF
RE-OSCR - Retro Escalation $version
Upstream GPLv3 frontend baseline: 11.1.0
Commit: $commit
Working tree: $working_tree
Built: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
Platform: Linux $(uname -m)

Experimental, unofficial community development build.
Settings are stored in the settings folder beside the executable.
EOF

if $package; then
    architecture="$(uname -m)"
    archive="$output_root/$app_name-$version-linux-$architecture.tar.gz"
    tar -C "$output_root" -czf "$archive" "$app_name"
    hash="$(sha256sum "$archive" | awk '{print $1}')"
    printf '%s  %s\n' "$hash" "$(basename "$archive")" > "$archive.sha256"
    printf 'Package: %s\n' "$archive"
    printf 'SHA-256: %s\n' "$hash"
fi

printf 'Application: %s\n' "$app_output"
