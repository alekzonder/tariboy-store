#!/usr/bin/env python3
"""Check the committed files of every eval suite in the Store.

A suite is a directory D with a tracked D/evals/evals.json. The check reads
only files that `git ls-files` lists and reports:

- missing: a case `files` entry or `fixture.script` names a file that is not
  tracked;
- unused: a file under D/evals/files/ or D/evals/fixtures/ that no case
  references and no referenced fixture script names;
- duplicate: a file whose content is byte-identical to a file of another suite;
- run-result: a file whose name marks a run result (grading, transcript, log,
  baseline or candidate output, provenance).

Each violation has a key such as `unused: PATH`. A key listed in the
known-violations file is accepted; a listed key without a violation is an
error, so the list only shrinks.
"""
import argparse
from collections import defaultdict
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KNOWN = "scripts/check-evals-known.txt"
RESULT_PATTERNS = (
    "*result*", "*grading*", "*benchmark*", "*transcript*", "*timing*",
    "*.log", "*-baseline.*", "*-candidate.*", "baseline.json",
    "candidate.json", "provenance.json",
)
# Suite documentation and executable checks are not run results.
NOT_RESULTS = ("README.md", "check-*.py")


def tracked_files(root):
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True, capture_output=True,
    ).stdout.decode()
    return sorted(path for path in out.split("\0") if path)


def suite_of(path, suites):
    """Return the suite root whose evals/ directory contains path."""
    best = None
    for suite in suites:
        prefix = f"{suite}/evals/" if suite else "evals/"
        if path.startswith(prefix) and (best is None or len(suite) > len(best)):
            best = suite
    return best


def resolve(suite, ref):
    joined = posixpath.normpath(posixpath.join(suite, ref)) if suite else posixpath.normpath(ref)
    return joined


def is_result(name):
    if any(fnmatch.fnmatch(name, pattern) for pattern in NOT_RESULTS):
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in RESULT_PATTERNS)


def find_violations(root):
    files = tracked_files(root)
    tracked = set(files)
    suites = sorted(
        str(PurePosixPath(path).parent.parent) if PurePosixPath(path).parent.parent != PurePosixPath(".") else ""
        for path in files
        if PurePosixPath(path).name == "evals.json" and PurePosixPath(path).parent.name == "evals"
    )
    violations = {}
    # A case may name a file of another suite, so references are global.
    referenced = set()
    scripts = defaultdict(set)
    for suite in suites:
        source = f"{suite}/evals/evals.json" if suite else "evals/evals.json"
        try:
            data = json.loads((root / source).read_text())
        except (OSError, ValueError) as error:
            violations[f"invalid: {source}"] = str(error)
            continue
        cases = data.get("evals", []) if isinstance(data, dict) else []
        for case in cases:
            if not isinstance(case, dict):
                continue
            refs = list(case.get("files") or [])
            fixture = case.get("fixture")
            if isinstance(fixture, dict) and fixture.get("script"):
                refs.append(fixture["script"])
                scripts[suite].add(resolve(suite, fixture["script"]))
            for ref in refs:
                path = resolve(suite, ref)
                referenced.add(path)
                if path not in tracked:
                    violations[f"missing: {source} case {case.get('id')} -> {ref}"] = (
                        "the referenced file is not tracked"
                    )

    owned = defaultdict(list)
    for path in files:
        suite = suite_of(path, suites)
        if suite is not None:
            owned[suite].append(path)

    for suite in suites:
        evals_dir = f"{suite}/evals" if suite else "evals"
        texts = {script: (root / script).read_text(errors="replace")
                 for script in scripts[suite] if script in tracked}
        for path in owned[suite]:
            rel = posixpath.relpath(path, evals_dir)
            if not (rel.startswith("files/") or rel.startswith("fixtures/")):
                continue
            if path in referenced:
                continue
            names = {posixpath.relpath(path, suite or "."), rel}
            named = any(
                name in text or posixpath.relpath(path, posixpath.dirname(script)) in text
                for script, text in texts.items() for name in names
            )
            if not named:
                violations[f"unused: {path}"] = "no case `files` entry or fixture script references it"

    by_hash = defaultdict(list)
    for suite in suites:
        for path in owned[suite]:
            name = PurePosixPath(path).name
            if name == "evals.json":
                continue
            if is_result(name):
                violations[f"run-result: {path}"] = "run results belong in the run workspace in the workdir"
            digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
            by_hash[digest].append((suite, path))
    for group in by_hash.values():
        if len({suite for suite, _ in group}) < 2:
            continue
        for suite, path in group:
            others = ", ".join(other for other_suite, other in group if other_suite != suite)
            violations[f"duplicate: {path}"] = f"same content as {others}"
    return suites, violations


def read_known(path):
    if not path.is_file():
        return []
    lines = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--known", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    known_path = args.known or root / KNOWN
    suites, violations = find_violations(root)
    known = read_known(known_path)
    errors = []
    seen = set()
    for line in known:
        if line in seen:
            errors.append(f"{known_path.name}: duplicate line: {line}")
        seen.add(line)
        if line not in violations:
            errors.append(f"{known_path.name}: fixed, remove the line: {line}")
    for key in sorted(violations):
        if key not in seen:
            errors.append(f"{key} ({violations[key]})")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"evals: {len(suites)} suites checked, {len(known)} known violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
