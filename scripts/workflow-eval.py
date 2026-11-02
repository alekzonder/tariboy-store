#!/usr/bin/env python3
"""Run the behavioral eval cases of a Store workflow in an isolated daemon.

A workflow case puts one task into one status of the workflow, lets one real
agent iteration of the case's actor image work it from the real Goal block,
and checks the result with scripts: the outcome the actor declared, the
artifacts it stored, the question it asked, its comments and the state of the
fixture repository. No LLM judge is involved.

The runner never touches the live daemon: it starts its own `tariboyd` with
its own TARIBOY_BASE_DIR and TARIBOY_RUNTIME_DIR, a Unix socket and no HTTP
listener, and refuses to continue when the daemon it reaches already has
queues. GitHub is replaced by a fake that answers through the
TARIBOY_GITHUB_CURL_BIN seam (scripts/workflow_eval/fake_curl.py).

Usage:
    python3 scripts/workflow-eval.py --workflow development
    python3 scripts/workflow-eval.py --workflow development --case plan-new-task --repeat 3
    python3 scripts/workflow-eval.py --workflow development --model sonnet
    python3 scripts/workflow-eval.py --workflow development --render-only
    python3 scripts/workflow-eval.py --workflow development \
        --status-override complete=/tmp/broken-complete.md --case complete-squash-merge

`--render-only` runs no model: the actor uses the `stub` harness, and the
runner only walks every case to its status and checks the Goal block. It is
free and runs in `make check`.

Exit codes: 0 every run passed (or the workflow has no cases), 1 a run
failed, 2 a usage, schema or environment error.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import signal
import string
import subprocess
import sys
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlsplit

STORE = Path(__file__).resolve().parent.parent
FAKE_CURL = Path(__file__).resolve().parent / "workflow_eval" / "fake_curl.py"
STUB_HARNESS = Path(__file__).resolve().parent / "workflow_eval" / "stub-harness.sh"
DEFAULT_MODEL = "haiku"
DEFAULT_EFFORT = "low"
DEFAULT_HARNESS = "claude"
DEFAULT_TIMEOUT_S = 1200
STATUS_TIMEOUT_S = 300
FAKE_TOKEN = "eval-fake-github-token"
CUSTOMER = "user:customer"

STEP_KINDS = {"move", "artifact", "advance", "comment", "wait_status"}
CRITERIA_KINDS = {
    "status",
    "outcome",
    "no_outcome",
    "artifacts",
    "question",
    "comments",
    "repo",
}
CASE_FIELDS = {
    "id",
    "status",
    "actor",
    "task",
    "fixture",
    "path",
    "criteria",
    "prompt",
    "expected_output",
    "timeout_s",
    "files",
}


class EvalError(Exception):
    """A usage, schema or environment error: exit 2."""


# --------------------------------------------------------------------------
# Case loading and validation


def workflow_statuses(workflow_dir: Path) -> dict[str, Any]:
    """Status id -> owner, read from Workflowfile.yaml without a YAML library.

    Only the `- id:` and `owner:` lines of the statuses list are read."""
    statuses: dict[str, Any] = {}
    current = None
    for line in (workflow_dir / "Workflowfile.yaml").read_text().splitlines():
        match = re.match(r"^\s*-\s+id:\s*(\S+)\s*$", line)
        if match:
            current = match.group(1)
            statuses[current] = None
            continue
        match = re.match(r"^\s+owner:\s*(.+?)\s*$", line)
        if match and current is not None and statuses[current] is None:
            owner = match.group(1)
            pool = re.match(r"^\{\s*pool:\s*([^}\s]+)\s*\}$", owner)
            statuses[current] = {"pool": pool.group(1)} if pool else owner
    return statuses


def load_cases(workflow_dir: Path) -> list[dict]:
    path = workflow_dir / "evals" / "evals.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    return [case for case in data.get("evals", []) if "status" in case]


def validate_case(case: dict, statuses: dict[str, Any], workflow_dir: Path) -> list[str]:
    errors: list[str] = []
    cid = case.get("id")
    label = f"case {cid!r}"
    if not isinstance(cid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", cid or ""):
        errors.append(f"{label}: id must be lowercase words joined by hyphens")
    unknown = set(case) - CASE_FIELDS
    if unknown:
        errors.append(f"{label}: unknown fields {sorted(unknown)}")
    status = case.get("status")
    owner = statuses.get(status)
    if status not in statuses:
        errors.append(f"{label}: status {status!r} is not a status of the workflow")
    elif not isinstance(owner, dict):
        errors.append(f"{label}: status {status!r} is not owned by an agent pool")
    actor = case.get("actor")
    if not isinstance(actor, dict) or not isinstance(actor.get("image"), str):
        errors.append(f"{label}: actor.image is required")
    task = case.get("task")
    if not isinstance(task, dict) or not task.get("title") or not task.get("description"):
        errors.append(f"{label}: task.title and task.description are required")
    fixture = case.get("fixture")
    if not isinstance(fixture, dict) or not isinstance(fixture.get("script"), str):
        errors.append(f"{label}: fixture.script is required")
    elif not (workflow_dir / fixture["script"]).is_file():
        errors.append(f"{label}: fixture script {fixture['script']} does not exist")
    path = case.get("path")
    if not isinstance(path, list) or not path:
        errors.append(f"{label}: path must list the steps that bring the task to its status")
    else:
        for index, step in enumerate(path):
            if not isinstance(step, dict) or len(step) != 1 or next(iter(step)) not in STEP_KINDS:
                errors.append(f"{label}: path[{index}] must be one of {sorted(STEP_KINDS)}")
    criteria = case.get("criteria")
    if not isinstance(criteria, dict) or not criteria:
        errors.append(f"{label}: criteria are required")
    else:
        unknown = set(criteria) - CRITERIA_KINDS
        if unknown:
            errors.append(f"{label}: unknown criteria {sorted(unknown)}")
    for field in ("prompt", "expected_output"):
        if not isinstance(case.get(field), str) or not case.get(field):
            errors.append(f"{label}: {field} is required by the evals.json contract")
    return errors


# --------------------------------------------------------------------------
# Substitution of fixture values


def substitute(value: Any, variables: dict[str, str]) -> Any:
    """Replace ${name} in strings with fixture values; unknown names fail.
    Any other `$`, as in a regular expression, stays as written."""
    if isinstance(value, str):

        def replace(match: re.Match) -> str:
            name = match.group(1)
            if name not in variables:
                raise EvalError(f"unknown fixture value ${{{name}}}")
            return str(variables[name])

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, variables) for key, item in value.items()}
    return value


# --------------------------------------------------------------------------
# Criteria


def requests_of(workflow: dict) -> list[dict]:
    """Transition requests of the task, oldest first, from `workflow get --json`.

    The daemon keeps only the last request. Each applied one also left a visit
    with its outcome, entered by the requester in the next visit, so the
    history is the visits' outcomes plus the last request when it did not
    apply (a rejected request makes no visit)."""
    visits = sorted(workflow.get("visits") or [], key=lambda v: v.get("sequence", 0))
    requests = []
    for visit, following in zip(visits, visits[1:]):
        if visit.get("outcome"):
            requests.append(
                {"outcome": visit["outcome"], "actor": following.get("entered_by"), "state": "applied", "status": visit.get("status")}
            )
    last = workflow.get("last_request")
    if isinstance(last, dict) and last.get("state") != "applied":
        requests.append({"outcome": last.get("outcome"), "actor": last.get("actor"), "state": last.get("state")})
    return requests


def artifacts_of(workflow: dict) -> dict[str, str]:
    """Artifact name -> value from `workflow get --json`."""
    values = {}
    for item in workflow.get("artifacts") or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            values[item["name"]] = item.get("value") or ""
    return values


def request_field(request: dict, *names: str) -> Any:
    for name in names:
        if name in request:
            return request[name]
    return None


def check_criteria(criteria: dict, snap: dict, actor: str) -> list[tuple[str, bool, str]]:
    """Each criterion as (name, passed, detail). `snap` is the collected
    state: status, requests, artifacts, comments, waits, repo."""
    results: list[tuple[str, bool, str]] = []
    agent_requests = [
        r for r in snap["requests"] if request_field(r, "requested_by", "by", "actor") == actor
    ]

    if "status" in criteria:
        want = criteria["status"]
        results.append(("status", snap["status"] == want, f"status {snap['status']!r}, want {want!r}"))

    if "outcome" in criteria:
        want = criteria["outcome"]
        last = agent_requests[-1] if agent_requests else None
        name = request_field(last, "outcome") if last else None
        state = request_field(last, "state", "status") if last else None
        ok = name == want["name"] and (want.get("state") is None or state == want["state"])
        results.append(("outcome", ok, f"last actor request {name!r} {state!r}, want {want['name']!r} {want.get('state')!r}"))

    if "no_outcome" in criteria:
        banned = set(criteria["no_outcome"])
        used = [request_field(r, "outcome") for r in agent_requests]
        hit = [name for name in used if name in banned]
        results.append(("no_outcome", not hit, f"actor requests {used}, banned {sorted(banned)}"))

    for name, rules in (criteria.get("artifacts") or {}).items():
        value = snap["artifacts"].get(name)
        label = f"artifact {name}"
        if rules.get("absent"):
            results.append((label, value in (None, ""), "absent" if not value else "present"))
            continue
        if not value:
            results.append((label, False, "missing"))
            continue
        problems = []
        for heading in rules.get("headings", []):
            if not re.search(rf"^#+\s*{re.escape(heading)}\s*$", value, re.MULTILINE):
                problems.append(f"no heading {heading!r}")
        for text in rules.get("contains", []):
            if text not in value:
                problems.append(f"does not contain {text!r}")
        if "matches" in rules and not re.search(rules["matches"], value):
            problems.append(f"does not match {rules['matches']!r}")
        if "equals" in rules and value != rules["equals"]:
            problems.append(f"is {value!r}, want {rules['equals']!r}")
        if rules.get("changed") and value == snap["artifacts_before"].get(name):
            problems.append("unchanged by the actor")
        results.append((label, not problems, "; ".join(problems) or "ok"))

    if "question" in criteria:
        want = criteria["question"]
        asked = [
            w
            for w in snap["waits"]
            if w.get("requesting_principal") == actor and w.get("expected_principal") == CUSTOMER
        ]
        results.append(("question", bool(asked) == bool(want), f"open questions from the actor to the customer: {len(asked)}"))

    if "comments" in criteria:
        rules = criteria["comments"]
        bodies = [c.get("body", "") for c in snap["comments"] if c.get("author") == actor]
        problems = []
        if rules.get("labels"):
            if not any(all(label in body for label in rules["labels"]) for body in bodies):
                problems.append(f"no actor comment has all of {rules['labels']}")
        for text in rules.get("contains", []):
            if not any(text in body for body in bodies):
                problems.append(f"no actor comment contains {text!r}")
        if rules.get("worktree_path"):
            # Every linked worktree is named in a comment, by its absolute
            # path or by its path relative to the main checkout.
            linked = snap["repo"].get("linked_worktrees", [])
            if not linked:
                problems.append("the repository has no linked worktree")
            for path in linked:
                names = {path["absolute"], path["relative"]}
                if not any(name in body for name in names for body in bodies):
                    problems.append(f"no actor comment names the worktree {path['relative']}")
        results.append(("comments", not problems, "; ".join(problems) or f"{len(bodies)} actor comments"))

    if "repo" in criteria:
        rules = criteria["repo"]
        repo = snap["repo"]
        problems = []
        if "branches" in rules and sorted(repo["branches"]) != sorted(rules["branches"]):
            problems.append(f"branches {repo['branches']}, want {rules['branches']}")
        if "branches_include" in rules:
            missing = [b for b in rules["branches_include"] if b not in repo["branches"]]
            if missing:
                problems.append(f"branches {repo['branches']} lack {missing}")
        if "worktrees" in rules and repo["worktrees"] != rules["worktrees"]:
            problems.append(f"{repo['worktrees']} worktrees, want {rules['worktrees']}")
        if "min_worktrees" in rules and repo["worktrees"] < rules["min_worktrees"]:
            problems.append(f"{repo['worktrees']} worktrees, want at least {rules['min_worktrees']}")
        if rules.get("clean") and not repo["clean"]:
            problems.append("the main checkout has uncommitted changes")
        if "main" in rules and repo["main"] != rules["main"]:
            problems.append(f"main is {repo['main'][:12]}, want {rules['main'][:12]}")
        if "main_contains" in rules and not repo["contains"].get(rules["main_contains"]):
            problems.append(f"main does not contain {rules['main_contains'][:12]}")
        if "origin_branches_include" in rules:
            missing = [b for b in rules["origin_branches_include"] if b not in repo["origin_branches"]]
            if missing:
                problems.append(f"origin lacks {missing}")
        results.append(("repo", not problems, "; ".join(problems) or "ok"))
    return results


# --------------------------------------------------------------------------
# Fake GitHub over loopback HTTP, for the workflow's own scripts


def load_fake_curl():
    spec = importlib.util.spec_from_file_location("fake_curl", FAKE_CURL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGitHub:
    """Serves each run's fake GitHub state at http://127.0.0.1:PORT/RUN_ID.

    The run's directory holds the same github.json the agent's fake curl
    uses, so both sides see one state."""

    def __init__(self):
        fake = load_fake_curl()
        runs: dict[str, Path] = {}
        self.runs = runs

        class Handler(BaseHTTPRequestHandler):
            def _answer(self) -> None:
                parts = urlsplit(self.path)
                run_id, _, rest = parts.path.lstrip("/").partition("/")
                directory = runs.get(run_id)
                length = int(self.headers.get("Content-Length") or 0)
                data = self.rfile.read(length).decode("utf-8") if length else None
                if directory is None:
                    status, body = 404, {"message": "Not Found"}
                else:
                    status, body = fake.handle(directory, self.command, "/" + rest, parts.query, data)
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = _answer

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def url(self, run_id: str, directory: Path) -> str:
        self.runs[run_id] = directory
        return f"http://127.0.0.1:{self.server.server_address[1]}/{run_id}"

    def close(self) -> None:
        self.server.shutdown()


# --------------------------------------------------------------------------
# Isolated daemon


class Daemon:
    def __init__(self, root: Path):
        self.root = root
        self.base = root / "base"
        self.runtime = Path(tempfile.mkdtemp(prefix="tbwe."))
        self.socket = self.runtime / "tariboyd.sock"
        self.log = root / "daemon.log"
        self.process: subprocess.Popen | None = None
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("TARIBOY_") and key not in {"ANTHROPIC_BASE_URL", "OPENAI_BASE_URL"}
        }
        self.env.update(
            TARIBOY_BASE_DIR=str(self.base),
            TARIBOY_RUNTIME_DIR=str(self.runtime),
            TARIBOY_STUB_HARNESS=str(STUB_HARNESS),
        )

    def start(self) -> None:
        if self.base.exists():
            raise EvalError(f"{self.base} exists: give --out a new directory")
        self.base.mkdir(parents=True)
        tariboyd = shutil.which(os.environ.get("TARIBOYD_BIN", "tariboyd"))
        if not tariboyd:
            raise EvalError("tariboyd is not on PATH")
        with self.log.open("w") as log:
            self.process = subprocess.Popen(
                [tariboyd, "--listen", f"unix:{self.socket}", "--http-addr", ""],
                env=self.env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        for _ in range(400):
            if self.socket.exists():
                break
            if self.process.poll() is not None:
                raise EvalError(f"isolated tariboyd exited; see {self.log}")
            time.sleep(0.05)
        else:
            raise EvalError("isolated tariboyd did not create its socket")
        # A new daemon has only its default TASK queue and no agents. Anything
        # else means the commands reached another daemon: stop before writing.
        queues = self.json("tasks", "queue", "list") or {}
        found = queues.get("queues") if isinstance(queues, dict) else queues
        extra = [q.get("prefix") for q in found or [] if q.get("prefix") != "TASK"]
        agents = self.json("agent", "ps", check=False)
        listed = agents.get("agents") if isinstance(agents, dict) else agents
        if extra or listed:
            raise EvalError("the daemon reached is not a new isolated daemon; refusing to touch it")

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        subprocess.run(["chmod", "-R", "u+w", str(self.base)], check=False)
        shutil.rmtree(self.runtime, ignore_errors=True)

    def run(self, *args: str, stdin: str | None = None, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
        tariboy = shutil.which(os.environ.get("TARIBOY_BIN", "tariboy"))
        result = subprocess.run(
            [tariboy, "--socket", str(self.socket), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode != 0:
            raise EvalError(f"tariboy {' '.join(args[:4])} failed: {(result.stderr or result.stdout).strip()[:2000]}")
        return result

    def json(self, *args: str, check: bool = True) -> Any:
        result = self.run(*args, "--json", check=check)
        try:
            return json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            return None


# --------------------------------------------------------------------------
# Store copy


def extends_chain(images: Path, name: str) -> list[str]:
    chain = []
    current: str | None = name
    while current:
        if current in chain:
            raise EvalError(f"image {name}: extends cycle")
        chain.insert(0, current)
        manifest = (images / current / "Tariboyfile.yaml").read_text()
        match = re.search(r"^extends:\s*(\S+)\s*$", manifest, re.MULTILINE)
        current = match.group(1).split(":")[0].split("/")[-1] if match else None
        if current and not (images / current).is_dir():
            current = None
    return chain


def prepare_store(dest: Path, workflow: str, overrides: dict[str, Path], images: set[str], log: Path) -> Path:
    shutil.copytree(STORE, dest, ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__"), symlinks=True)
    workflow_dir = dest / "workflows" / workflow
    for status, source in overrides.items():
        target = workflow_dir / "statuses" / f"{status}.md"
        if not target.is_file():
            raise EvalError(f"--status-override: workflow {workflow} has no statuses/{status}.md")
        shutil.copyfile(source, target)
    for image in sorted(images):
        for layer in extends_chain(dest / "images", image):
            directory = dest / "images" / layer
            if not (directory / "skills-lock.json").is_file():
                continue
            with log.open("a") as out:
                result = subprocess.run(
                    ["npx", "skills", "experimental_install"],
                    cwd=directory,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            if result.returncode != 0:
                raise EvalError(f"restoring the skills of image {layer} failed; see {log}")
    return workflow_dir


# --------------------------------------------------------------------------
# One run of one case


def queue_prefix(index: int) -> str:
    letters = string.ascii_uppercase
    return "W" + letters[index // 26 % 26] + letters[index % 26]


def git_state(repo: Path, contains: list[str]) -> dict:
    def git(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    branches = [b for b in git("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines() if b]
    worktree_dirs = [line[len("worktree "):] for line in git("worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    worktrees = len(worktree_dirs)
    main_dir = Path(worktree_dirs[0]).resolve() if worktree_dirs else repo.resolve()
    linked = []
    for directory in worktree_dirs[1:]:
        absolute = Path(directory).resolve()
        relative = os.path.relpath(absolute, main_dir)
        linked.append({"absolute": str(absolute), "relative": relative})
    main = git("rev-parse", "--verify", "--quiet", "refs/heads/main")
    origin_branches = [
        b for b in git("ls-remote", "--heads", "origin").splitlines() if b
    ]
    origin_branches = [line.split("refs/heads/", 1)[1] for line in origin_branches if "refs/heads/" in line]
    contained = {}
    for sha in contains:
        if sha:
            result = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, "refs/heads/main"],
                capture_output=True,
                check=False,
            )
            contained[sha] = result.returncode == 0
    return {
        "branches": branches,
        "worktrees": worktrees,
        "linked_worktrees": linked,
        "main": main,
        "clean": git("status", "--porcelain") == "",
        "contains": contained,
        "origin_branches": origin_branches,
    }


def goal_block_check(prompt: str, key: str, status: str, workflow_dir: Path) -> tuple[bool, str]:
    """The prompt carries the Goal block of the task in the expected status,
    with that status's instructions."""
    problems = []
    if key not in prompt:
        problems.append(f"the prompt does not name the task {key}")
    if not re.search(rf"^status:\s*{re.escape(status)}\s*$", prompt, re.MULTILINE):
        problems.append(f"the Goal block does not show status {status}")
    first = (workflow_dir / "statuses" / f"{status}.md").read_text().strip().splitlines()[0]
    if first not in prompt:
        problems.append("the Goal block does not carry the status instructions")
    return not problems, "; ".join(problems) or "ok"


def wait_for_status(daemon: Daemon, key: str, status: str, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    current = ""
    while time.monotonic() < deadline:
        current = (daemon.json("tasks", "workflow", "get", key) or {}).get("status", "")
        if current == status:
            return current
        time.sleep(3)
    raise EvalError(f"task {key} did not reach status {status!r} within {timeout}s (status {current!r})")


def wait_for_iteration(daemon: Daemon, agent: str, timeout: int) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = daemon.json("iteration", "ls", agent, check=False) or {}
        for iteration in data.get("iterations") or []:
            if iteration.get("done"):
                return iteration
        time.sleep(5)
    return None


def collect(daemon: Daemon, key: str, variables: dict, artifacts_before: dict) -> dict:
    workflow = daemon.json("tasks", "workflow", "get", key) or {}
    shown = daemon.json("tasks", "show", key) or {}
    artifacts = artifacts_of(workflow)
    repo = Path(variables["repo"])
    contains = [variables.get("merge_sha", "")]
    return {
        "status": workflow.get("status", ""),
        "requests": requests_of(workflow),
        "artifacts": artifacts,
        "artifacts_before": artifacts_before,
        "comments": shown.get("comments") or [],
        "waits": shown.get("waiting_for") or [],
        "repo": git_state(repo, contains),
        "workflow": workflow,
    }


def artifact_values(daemon: Daemon, key: str) -> dict:
    return artifacts_of(daemon.json("tasks", "workflow", "get", key) or {})


def run_case(daemon: Daemon, github: FakeGitHub, case: dict, workflow_dir: Path, workflow_ref: str, index: int, run_dir: Path, options: argparse.Namespace) -> dict:
    run_dir.mkdir(parents=True)
    actor = case["actor"]
    render_only = options.render_only
    harness = "stub" if render_only else (options.harness or actor.get("harness") or DEFAULT_HARNESS)
    model = options.model or actor.get("model") or DEFAULT_MODEL
    effort = options.effort or actor.get("effort") or DEFAULT_EFFORT
    agent = f"eval-{index:03d}"
    principal = f"agent:{agent}"
    prefix = queue_prefix(index)
    started = time.time()

    # Fixture: repository, fake GitHub state, values for the path.
    fake_dir = run_dir / "github"
    fake_dir.mkdir()
    shutil.copy2(FAKE_CURL, fake_dir / "fake_curl.py")
    (fake_dir / "fake_curl.py").chmod(0o755)
    env = dict(daemon.env)
    env.update(
        EVAL_DIR=str(run_dir),
        EVAL_GITHUB_STATE=str(fake_dir / "github.json"),
        EVAL_VARS=str(run_dir / "vars.json"),
    )
    fixture = case["fixture"]
    result = subprocess.run(
        ["bash", str(workflow_dir / fixture["script"]), *fixture.get("args", [])],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    (run_dir / "fixture.log").write_text(result.stdout + result.stderr)
    if result.returncode != 0:
        raise EvalError(f"fixture failed; see {run_dir / 'fixture.log'}")
    variables = json.loads((run_dir / "vars.json").read_text())
    task_spec = substitute(case["task"], variables)
    path = substitute(case["path"], variables)
    criteria = substitute(case["criteria"], variables)

    # Agent, queue, pool, workflow.
    agent_env = f"TARIBOY_GITHUB_CURL_BIN={fake_dir / 'fake_curl.py'},GITHUB_TOKEN={FAKE_TOKEN}"
    run_args = [
        "agent", "run", f"{actor['image']}:latest", "--name", agent, "--cwd", variables["repo"],
        "--harness", harness, "--interactive", "false", "--env", agent_env,
        "--max_idle_iterations", "1",
        "--hard_timeout_s", str(case.get("timeout_s") or options.timeout),
    ]
    if not render_only:
        run_args += ["--model", model, "--effort", effort]
    daemon.run(*run_args)
    daemon.run("tasks", "queue", "create", "--prefix", prefix, "--name", f"Workflow eval {case['id']}")
    pool = workflow_statuses(workflow_dir)[case["status"]]["pool"]
    daemon.run("tasks", "queue", "pool", "set", prefix, pool, "--agents", agent, "--revision", "0", "--idempotency-key", f"pool-{prefix}")
    daemon.run("tasks", "queue", "env", "set", prefix, "GITHUB_API_URL", github.url(prefix, fake_dir))
    daemon.run("tasks", "queue", "secret", "set", prefix, "GITHUB_TOKEN", stdin=FAKE_TOKEN)
    # Revision 0: a new queue has no workflow binding yet.
    daemon.run("tasks", "queue", "workflow", "set", prefix, workflow_ref, "--revision", "0")
    created = daemon.json(
        "tasks", "create", "--queue", prefix, "--title", task_spec["title"], "--description", task_spec["description"]
    ) or {}
    key = (created.get("task") or created).get("key")
    if not key:
        listed = daemon.json("tasks", "list", "--queue", prefix) or {}
        tasks = listed.get("tasks", listed) if isinstance(listed, dict) else listed
        key = tasks[0]["key"]

    # Path: bring the task to the case's status as the customer and operator.
    for step in path:
        kind, value = next(iter(step.items()))
        if kind == "move":
            daemon.run("tasks", "workflow", "move", key, "--to", value, "--reason", "workflow eval fixture")
        elif kind == "artifact":
            name, text = value
            daemon.run("tasks", "artifacts", "set", key, name, stdin=text)
        elif kind == "advance":
            args = ["tasks", "advance", key, "--outcome", value["outcome"]]
            if value.get("from"):
                args += ["--from", value["from"]]
            if value.get("message"):
                args += ["--message", value["message"]]
            daemon.run(*args)
        elif kind == "comment":
            daemon.run("tasks", "comment", key, value)
        elif kind == "wait_status":
            wait_for_status(daemon, key, value, STATUS_TIMEOUT_S)
    wait_for_status(daemon, key, case["status"], STATUS_TIMEOUT_S)
    artifacts_before = artifact_values(daemon, key)

    # One iteration of the actor. With the stub harness it only receives
    # its prompt; the daemon keeps the prompt of every iteration.
    daemon.run("agent", "start", agent)
    timeout = int(case.get("timeout_s") or options.timeout)
    iteration = wait_for_iteration(daemon, agent, timeout + 120)
    daemon.run("agent", "stop", agent, check=False)
    record: dict[str, Any] = {
        "case": case["id"],
        "status": case["status"],
        "task": key,
        "agent": agent,
        "harness": harness,
        "model": None if render_only else model,
        "effort": None if render_only else effort,
        "run_dir": str(run_dir),
        "checks": [],
    }
    if iteration is None:
        record["checks"].append(["iteration", False, f"no iteration finished within {timeout + 120}s"])
        goal = ""
    else:
        record["iteration"] = iteration["id"]
        prompt = daemon.base / "agents" / agent / "iterations" / iteration["id"] / "PROMPT.md"
        goal = prompt.read_text() if prompt.is_file() else ""
    (run_dir / "PROMPT.md").write_text(goal)
    record["checks"].insert(0, ["goal_block", *goal_block_check(goal, key, case["status"], workflow_dir)])
    if render_only:
        record["passed"] = all(check[1] for check in record["checks"])
        record["cost_usd"] = 0.0
        record["seconds"] = round(time.time() - started, 1)
        return record
    if iteration is not None:
        transcript = daemon.run("transcript", agent, iteration["id"], check=False)
        (run_dir / "transcript.txt").write_text(transcript.stdout + transcript.stderr)
    # Checks started by the actor's last advance finish within their timeouts.
    time.sleep(5)
    snap = collect(daemon, key, variables, artifacts_before)
    (run_dir / "workflow.json").write_text(json.dumps(snap.pop("workflow"), indent=2))
    (run_dir / "snapshot.json").write_text(json.dumps(snap, indent=2, default=str))
    for name, passed, detail in check_criteria(criteria, snap, principal):
        record["checks"].append([name, passed, detail])
    usage = daemon.json("usage", "--agent", agent, check=False) or {}
    record["cost_usd"] = float(usage.get("total_cost_usd") or 0.0)
    record["seconds"] = round(time.time() - started, 1)
    record["passed"] = all(check[1] for check in record["checks"])
    return record


# --------------------------------------------------------------------------
# Main


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the eval cases of a Store workflow in an isolated daemon.")
    parser.add_argument("--workflow", required=True, help="workflow directory name under workflows/")
    parser.add_argument("--case", action="append", default=[], help="run only this case id (repeatable)")
    parser.add_argument("--model", help=f"actor model (default: the case's, else {DEFAULT_MODEL})")
    parser.add_argument("--effort", help=f"actor effort (default: the case's, else {DEFAULT_EFFORT})")
    parser.add_argument("--harness", help=f"actor harness (default: the case's, else {DEFAULT_HARNESS})")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="iteration timeout in seconds")
    parser.add_argument(
        "--status-override",
        action="append",
        default=[],
        metavar="STATUS=FILE",
        help="replace statuses/STATUS.md in the evaluated copy with FILE",
    )
    parser.add_argument("--render-only", action="store_true", help="stub harness, no model: walk each case to its status and check the Goal block")
    parser.add_argument("--validate-only", action="store_true", help="check the case schema and exit")
    parser.add_argument("--out", help="directory for run records (default: a new temporary directory)")
    parser.add_argument("--keep", action="store_true", help="keep the isolated daemon's data in --out")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    workflow_dir = STORE / "workflows" / options.workflow
    if not (workflow_dir / "Workflowfile.yaml").is_file():
        raise EvalError(f"workflows/{options.workflow}/Workflowfile.yaml does not exist")
    statuses = workflow_statuses(workflow_dir)
    cases = load_cases(workflow_dir)
    if options.case:
        unknown = set(options.case) - {case.get("id") for case in cases}
        if unknown:
            raise EvalError(f"unknown case ids: {sorted(unknown)}")
        cases = [case for case in cases if case.get("id") in options.case]
    errors = [error for case in cases for error in validate_case(case, statuses, workflow_dir)]
    if errors:
        raise EvalError("\n".join(errors))
    if not cases:
        print(f"workflow {options.workflow}: no workflow cases")
        return 0
    if options.validate_only:
        print(f"workflow {options.workflow}: {len(cases)} cases valid")
        return 0
    overrides: dict[str, Path] = {}
    for item in options.status_override:
        status, _, file = item.partition("=")
        if not status or not file or not Path(file).is_file():
            raise EvalError(f"--status-override {item!r}: want STATUS=FILE with an existing file")
        overrides[status] = Path(file).resolve()

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(options.out).resolve() if options.out else Path(tempfile.mkdtemp(prefix=f"workflow-eval-{options.workflow}-{stamp}."))
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    images = {case["actor"]["image"] for case in cases}
    daemon = Daemon(out)
    github = FakeGitHub()
    records: list[dict] = []
    try:
        copy_dir = prepare_store(out / "store", options.workflow, overrides, images, out / "restore.log")
        daemon.start()
        for image in sorted(images):
            for layer in extends_chain(out / "store" / "images", image):
                daemon.run("image", "build", "--path", str(out / "store" / "images" / layer), "--name", layer, "--tag", "latest")
        built = daemon.run("workflow", "build", "--path", str(copy_dir))
        version = re.search(r"workflow_version:\s*(\S+)", (copy_dir / "Workflowfile.yaml").read_text())
        workflow_ref = f"{options.workflow}:latest"
        print(f"workflow {options.workflow} {version.group(1) if version else '?'}"
              f"{' (status override: ' + ', '.join(sorted(overrides)) + ')' if overrides else ''}"
              f"; mode {'render-only' if options.render_only else 'model'}; records {out}")
        del built
        index = 0
        for case in cases:
            for attempt in range(1, options.repeat + 1):
                run_dir = out / "runs" / f"{case['id']}-{attempt}"
                try:
                    record = run_case(daemon, github, case, copy_dir, workflow_ref, index, run_dir, options)
                except EvalError as exc:
                    record = {"case": case["id"], "passed": False, "cost_usd": 0.0, "checks": [["runner", False, str(exc)]], "run_dir": str(run_dir)}
                record["attempt"] = attempt
                index += 1
                records.append(record)
                mark = "PASS" if record["passed"] else "FAIL"
                model = record.get("model") or record.get("harness") or "-"
                print(f"{mark} {case['id']} #{attempt} [{case['status']}] model={model} cost=${record.get('cost_usd', 0):.4f} time={record.get('seconds', '-')}s")
                for name, passed, detail in record["checks"]:
                    print(f"    {'ok ' if passed else 'BAD'} {name}: {detail}")
                sys.stdout.flush()
    finally:
        daemon.stop()
        github.close()
        (out / "results.json").write_text(json.dumps(records, indent=2))
        if not options.keep:
            subprocess.run(["chmod", "-R", "u+w", str(out / "base")], check=False)
            shutil.rmtree(out / "base", ignore_errors=True)
            shutil.rmtree(out / "store", ignore_errors=True)
    passed = sum(1 for record in records if record["passed"])
    if options.render_only and not options.out and not options.keep and passed == len(records):
        # A passing free run in `make check` leaves nothing behind.
        shutil.rmtree(out, ignore_errors=True)
        out = Path("(removed)")
    total_cost = sum(record.get("cost_usd", 0.0) for record in records)
    print(f"summary: {passed}/{len(records)} passed; cost ${total_cost:.4f}; records {out}")
    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except EvalError as exc:
        print(f"workflow-eval: {exc}", file=sys.stderr)
        sys.exit(2)
