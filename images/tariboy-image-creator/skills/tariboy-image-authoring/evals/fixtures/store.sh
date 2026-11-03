#!/usr/bin/env bash
# Fixture for the tariboy-image-authoring evals: the Store a case acts on.
#
# Usage: store.sh VARIANT [SKILL...]
#   reviewer-v2            case A: images/reviewer is schema v2, version 1.2.3,
#                          plugin tasks, no skills; it has instructions.md and
#                          an authored skills/review/SKILL.md.
#   reviewer-local-skills  case C: images/reviewer has an authored
#                          skills/local-review, an installed upstream `review`
#                          skill with a stale lock hash, an installed
#                          `obsolete-review`, and a teammate's uncommitted work:
#                          a manual copy in .agents/skills/local-review and a
#                          direct Tariboyfile.yaml edit.
#   empty                  cases S1, S2: an empty images/ directory.
#   Each SKILL argument copies skills/SKILL of the revision under test into the
#   Store's skills/. A name that the revision does not have is skipped.
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates $EVAL_DIR/store, a Git repository with one commit. The
# teammate's work of reviewer-local-skills stays uncommitted. Grade the actor
# on its answer and on the final state of $EVAL_DIR/store.
set -euo pipefail

: "${EVAL_DIR:?}"
variant=${1:?usage: store.sh VARIANT [SKILL...]}
shift
store_root=$(cd "$(dirname "$0")/../../../../../.." && pwd)
store="$EVAL_DIR/store"

rm -rf "$store"
mkdir -p "$store/images" "$store/skills"
for name in "$@"; do
  if [ -d "$store_root/skills/$name" ]; then
    cp -a "$store_root/skills/$name" "$store/skills/$name"
    rm -rf "$store/skills/$name/evals"
  fi
done

reviewer="$store/images/reviewer"
write_skill() { # DIR NAME DESCRIPTION
  mkdir -p "$1"
  printf -- '---\nname: %s\ndescription: %s\n---\n\n# %s\n\n%s\n' "$2" "$3" "$2" "$3" > "$1/SKILL.md"
}

case "$variant" in
  reviewer-v2)
    mkdir -p "$reviewer"
    cat > "$reviewer/Tariboyfile.yaml" <<'YAML_EOF'
schema_version: 2
image_version: 1.2.3
plugins:
    - name: tasks
prompts:
    - file: ./instructions.md
YAML_EOF
    printf '# Reviewer\n\nReview the pull request of the selected task and comment on it.\n' > "$reviewer/instructions.md"
    write_skill "$reviewer/skills/review" review "Use when reviewing a pull request diff."
    ;;
  reviewer-local-skills)
    mkdir -p "$reviewer"
    cat > "$reviewer/Tariboyfile.yaml" <<'YAML_EOF'
schema_version: 2
image_version: 1.2.3
plugins:
    - name: tasks
skills:
    - dir: ./.agents/skills/review
    - dir: ./.agents/skills/obsolete-review
prompts:
    - file: ./instructions.md
YAML_EOF
    printf '# Reviewer\n\nReview the pull request of the selected task and comment on it.\n' > "$reviewer/instructions.md"
    write_skill "$reviewer/skills/local-review" local-review "Use when reviewing changes against this Store's local rules."
    cat > "$reviewer/skills-lock.json" <<'JSON_EOF'
{
  "version": 1,
  "skills": {
    "obsolete-review": {
      "source": "example-org/review-skills",
      "sourceType": "github",
      "computedHash": "1111111111111111111111111111111111111111111111111111111111111111"
    },
    "review": {
      "source": "example-org/review-skills",
      "sourceType": "github",
      "computedHash": "2222222222222222222222222222222222222222222222222222222222222222"
    }
  }
}
JSON_EOF
    write_skill "$reviewer/.agents/skills/review" review "Use when reviewing a pull request diff (old upstream release)."
    write_skill "$reviewer/.agents/skills/obsolete-review" obsolete-review "Use when reviewing with the retired checklist."
    printf '.agents/\n' > "$reviewer/.gitignore"
    ;;
  empty)
    ;;
  *)
    echo "store.sh: unknown variant: $variant" >&2
    exit 2
    ;;
esac

git -C "$store" init -q -b main
git -C "$store" add -A
git -C "$store" -c user.name=fixture -c user.email=fixture@example.invalid commit -q --allow-empty -m 'Fixture Store'

if [ "$variant" = reviewer-local-skills ]; then
  cp -a "$reviewer/skills/local-review" "$reviewer/.agents/skills/local-review"
  sed -i 's#^prompts:$#    - dir: ./skills/local-review\nprompts:#' "$reviewer/Tariboyfile.yaml"
fi
