#!/usr/bin/env python3
"""Check that every local skill in a skills-lock.json matches its source.

The automatic Store build installs the skills of an image strictly by
skills-lock.json and compares each installed skill with its computedHash. A
stale hash fails the build with skills_lock_mismatch. This check recomputes the
hash of every `sourceType: local` skill and fails on a difference.

Only local skills are checked: a github skill hash depends on the upstream
repository and needs a network. Refresh a lock with `npx skills
experimental_install` in the image directory.

The hash is the one `stores.SkillHash` of tariboy computes: sha256 over every
file of the skill, each as its slash-separated relative path followed by its
content, in localeCompare order, skipping .git and node_modules.
"""

import hashlib
import json
import os
import sys

LOCK = "skills-lock.json"

# CLDR root collation order of the ASCII punctuation, then digits, then letters.
PUNCT = "_-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$"


def char_key(ch):
    if ch.isspace():
        return (0, ord(ch))
    if ch in PUNCT:
        return (1, PUNCT.index(ch))
    if ch.isdigit():
        return (3, ord(ch))
    if ch.isalpha():
        return (4, ord(ch.lower()))
    return (2, ord(ch))


def collate_key(text):
    primary = [char_key(ch) for ch in text]
    tertiary = [ch.isupper() for ch in text]
    return (primary, tertiary)


def skill_hash(directory):
    members = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, directory).replace(os.sep, "/")
            members.append((rel, path))
    members.sort(key=lambda member: collate_key(member[0]))
    digest = hashlib.sha256()
    for rel, path in members:
        digest.update(rel.encode("utf-8"))
        with open(path, "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def lock_files(root):
    found = []
    if os.path.isfile(os.path.join(root, LOCK)):
        found.append(root)
    images = os.path.join(root, "images")
    if os.path.isdir(images):
        for name in sorted(os.listdir(images)):
            directory = os.path.join(images, name)
            if os.path.isfile(os.path.join(directory, LOCK)):
                found.append(directory)
    return found


def check(root):
    errors = []
    for directory in lock_files(root):
        label = os.path.relpath(os.path.join(directory, LOCK), root)
        with open(os.path.join(directory, LOCK), encoding="utf-8") as handle:
            skills = json.load(handle).get("skills", {})
        for name, entry in sorted(skills.items()):
            if entry.get("sourceType") != "local":
                continue
            source = os.path.normpath(os.path.join(directory, entry["source"]))
            if not os.path.isdir(source):
                errors.append("%s: skill %s: source %s is missing" % (label, name, entry["source"]))
                continue
            actual = skill_hash(source)
            if actual != entry.get("computedHash"):
                errors.append(
                    "%s: skill %s: computedHash is stale, source %s hashes to %s"
                    % (label, name, entry["source"], actual)
                )
    return errors


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    errors = check(root)
    for error in errors:
        print("FAIL " + error, file=sys.stderr)
    if errors:
        print(
            "Refresh the lock: run `npx skills experimental_install` in the image directory and commit skills-lock.json.",
            file=sys.stderr,
        )
        return 1
    print("check-skills-lock: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
