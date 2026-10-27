#!/usr/bin/env python3
"""Check that every image packages writing-style and its language skills."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("writing-style", "simple-english", "simplified-technical-russian")
CLI_TEXT_PROMPT = "./.agents/skills/cli-text/cli-text.md"
PROMPT = "./.agents/skills/writing-style/writing-style.md"


def entries(manifest, key):
    # Schema v2 manifests here are flat lists of `- dir:` and `- file:` items.
    values = []
    section = None
    for line in manifest.splitlines():
        if re.match(r"^\S", line):
            section = line.split(":", 1)[0]
        elif section == key:
            match = re.match(r"^\s+- (dir|file|runtime): (.+)$", line)
            if match:
                values.append(match.group(2).strip())
    return values


errors = []
images = sorted(path.parent for path in ROOT.glob("images/*/Tariboyfile.yaml"))
for image in images:
    name = image.name
    manifest = (image / "Tariboyfile.yaml").read_text()
    skills = entries(manifest, "skills")
    prompts = entries(manifest, "prompts")
    for skill in SKILLS:
        if f"./.agents/skills/{skill}" not in skills:
            errors.append(f"{name}: skills does not list ./.agents/skills/{skill}")
    if PROMPT not in prompts:
        errors.append(f"{name}: prompts does not load {PROMPT}")
    elif CLI_TEXT_PROMPT not in prompts or prompts.index(PROMPT) != prompts.index(CLI_TEXT_PROMPT) + 1:
        errors.append(f"{name}: {PROMPT} does not follow {CLI_TEXT_PROMPT}")
    lock_path = image / "skills-lock.json"
    locked = json.loads(lock_path.read_text())["skills"] if lock_path.is_file() else {}
    for skill in SKILLS:
        if skill not in locked:
            errors.append(f"{name}: skills-lock.json does not record {skill}")
    if locked.get("writing-style", {}).get("source") not in (None, "../../skills/writing-style"):
        errors.append(f"{name}: writing-style is not installed from ../../skills/writing-style")

if not images:
    errors.append("no images/*/Tariboyfile.yaml found")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print(f"writing-style: {len(images)} images checked")
