#!/usr/bin/env python3
"""Check on publish -> done: the publication artifact proves what the merge
published.

The artifact is one JSON object:

    {"images": [{"name": "tariboy-image-creator", "version": "0.21.0",
                 "version_digest": "<64 hex>", "latest_digest": "<64 hex>"}],
     "workflows": [{"name": "image-improve", "workflow_version": "0.1.0"}]}

Every published image has its version tag and `latest` under one full digest:
both digests are 64 lowercase hex characters and equal. Every merged workflow
is listed with its merged `workflow_version`; the agent does not build it, the
operator does. The object lists at least one image or workflow. The check
cannot read the registry: it proves the record is complete and consistent, and
the customer verifies it with `tariboy image ls`."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def image_problem(image: object) -> str | None:
    if not isinstance(image, dict):
        return "every entry of 'images' must be an object"
    name = image.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        return "an image has no valid 'name'"
    version = image.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        return f"image '{name}' has no 'version' in the form MAJOR.MINOR.PATCH"
    first, second = image.get("version_digest"), image.get("latest_digest")
    for label, digest in (("version_digest", first), ("latest_digest", second)):
        if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
            return f"image '{name}': '{label}' must be a full 64-character lowercase hex digest"
    if first != second:
        return (
            f"image '{name}': the version tag {version} and latest have different "
            "digests; build both tags from the same source and record the same digest"
        )
    return None


def workflow_problem(workflow: object) -> str | None:
    if not isinstance(workflow, dict):
        return "every entry of 'workflows' must be an object"
    name = workflow.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        return "a workflow has no valid 'name'"
    version = workflow.get("workflow_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        return f"workflow '{name}' has no 'workflow_version' in the form MAJOR.MINOR.PATCH"
    return None


def main() -> int:
    task = pr_lib.load_task()
    text = pr_lib.artifact(task, "publication")
    if text is None or not text.strip():
        return reject(
            "The publication artifact is missing or empty. Publish the merged images, "
            "then store the record as JSON (see the publish status) and advance again."
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return reject("The publication artifact is not valid JSON. Store one JSON object and advance again.")
    if not isinstance(data, dict):
        return reject("The publication artifact must be one JSON object.")
    unknown = sorted(set(data) - {"images", "workflows"})
    if unknown:
        return reject(f"The publication artifact has unknown keys: {', '.join(unknown)}.")
    images = data.get("images", [])
    workflows = data.get("workflows", [])
    if not isinstance(images, list) or not isinstance(workflows, list):
        return reject("'images' and 'workflows' must be lists.")
    if not images and not workflows:
        return reject("The publication artifact lists no image and no workflow; the merge published something.")

    seen: set[str] = set()
    for image in images:
        problem = image_problem(image)
        if problem:
            return reject(problem[0].upper() + problem[1:] + ".")
        if image["name"] in seen:
            return reject(f"Image '{image['name']}' appears twice.")
        seen.add(image["name"])
    seen = set()
    for workflow in workflows:
        problem = workflow_problem(workflow)
        if problem:
            return reject(problem[0].upper() + problem[1:] + ".")
        if workflow["name"] in seen:
            return reject(f"Workflow '{workflow['name']}' appears twice.")
        seen.add(workflow["name"])

    pr_lib.write_result(
        message=f"The publication record lists {len(images)} image(s) and {len(workflows)} workflow(s), each consistent."
    )
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
