# CLI text regression evidence

Run the deterministic checks from the Store root:

```bash
python3 -B skills/cli-text/evals/check-text.py baseline
python3 -B skills/cli-text/evals/check-text.py candidate
python3 -B skills/cli-text/evals/check-consumers.py
```

`make check` runs these too. They require Python 3, Node.js and Bash, use
recording CLI stubs in temporary directories, and pass a minimal environment
without live credentials. They never invoke real tasks, status, messages or
GitHub services. The stub has the input contract given to the actor; this does
not prove how an undocumented CLI parses leading-hyphen options.

## Behavioral method and results

Date: 2026-09-11. Harness: Codex collaboration actors, fresh `fork_turns: none`,
explicit `gpt-5.6-terra`, `medium` for every baseline/candidate. Temperature and
seed were unavailable. Actors received only the request and the applicable
skill (or complete image prompt/catalog), never the evaluator rubric or previous
answers. Higher-level harness instructions remain present even with a fresh
fork; this is not a recreation of the archived agent's full harness.

| Boundary | Baseline | Candidate |
| --- | --- | --- |
| Generic JavaScript text request, 5 fresh actors | 5 safe snippets | 5 safe snippets |
| Four owning-skill proposals in one actor per variant | All 4 preserve text; no common skill read | All 4 preserve text; cli-text read |
| Input modes, one actor per variant | Structured/file/stdin/NUL choices correct | Same choices correct |
| Exact trailing newlines in tasks, fresh actor per variant | Both final newlines lost | Both final newlines preserved |
| Full image prompt/catalog, one actor per image/variant | No cli-text routing; one actor could not resolve launcher; four used relative launchers | All 6 read cli-text + status and use absolute launchers |

`baseline.json` and `candidate.json` preserve the five generic code responses.
The one baseline actor that did not read the request is retained as invalid and
replaced by a fresh actor; it is not scored as a behavior failure. Response code
fences are omitted from these two JSON archives. The additional fixtures and
verbatim responses cover consumer skills and input modes. The trailing-newline
regression has its own evidence under `../../tasks/evals/`.

The original incident used `JSON.stringify(body)` as shell escaping in a
`ttasks comment` call and executed backtick text. Its recorded provenance was
iteration `faust-dev-bart-20260911103900-1`, image `faust-developer:0.11`, digest
`4e724f17f960dffaddbd1ab848384dbd7fd144a5951798ecd3a7c0b299a7e96e`, Codex
`gpt-5.6-sol`. The test replays only that serialization mechanism with harmless
`printf` payloads and a stub CLI; it does not execute archived commands.
The historical mechanism still corrupts text. This is a deterministic incident
regression, not a fresh failing Terra actor or a matched model comparison.

The initial generic controls already passed. They are regression coverage;
we do not claim a measured quoting improvement, statistical robustness or
universal agent compliance. The subsequent tasks newline scenario supplies an
observed current baseline failure and a matched successful candidate. That
scenario was added during review after the generic skill was drafted; the
specific tasks correction followed its failing baseline. The shared skill was
implemented under the approved cross-image plan using the previously diagnosed
historical failure, rather than claiming fresh generic RED evidence.

## Executed checks

Each of the ten generic snippets runs against six inputs: special characters,
empty text, collision with the candidate's actual delimiter, CRLF, no final
newline, and only newlines. The current SKILL.md JavaScript example runs on the
same six inputs. Each candidate and the example also rejects NUL without
calling a CLI. Reports retain the received text hashes and CLI action order.
`check-consumers.py` checks eight consumer proposals, six image proposals,
two structured API proposals, four file/stdin proposals with exact argv checks,
and the failing/passing tasks newline pair. Consumer proposals also passed from
a different checkout path containing spaces.

These are exact-byte execution checks of recorded proposals, separate from
fresh model behavior. A new skill revision requires fresh relevant actors;
replaying archived output alone cannot validate new instructions.

Per-image `evals/cli-text/results.json` retains requests, rubric, prompt/skill
hashes and observed actions. Baseline sources are at `ea74a50`; candidate source
hashes identify the evaluated revision. Full static prompts were concatenated
in manifest order, runtime entries were explicit no-action simulation markers,
and every manifest skill appeared with its description and readable source
path. The mandatory prompt was subsequently renamed from `prompt.md` to
`cli-text.md` without changing bytes, to respect the Store's existing ban on
generic duplicate prompt files. Final authoring paths were retested separately.
No complete live Tariboy iteration, user service write or external faust image
rebuild is claimed by these simulations.

## Packaging and review

Initial `make check` passed 21 Store tests and the shell contract checks, then
failed on the daemon-reserved `basic:latest`. The temporary-daemon build now
passes an explicit `store-check` tag; no image is skipped and no live daemon
is used by that gate. Final checks and authorized image build digests are
recorded on the Native Task, separately from behavioral evidence.

Independent read-only review found the tasks newline conflict and a legacy
nonrelative authoring example. Both were corrected and re-reviewed without
remaining findings. The checkers were also reviewed and corrected for portable
interpreter lookup and strict file/stdin argument checks. No image is activated automatically; consumers must select
a rebuilt image, and external Stores must vendor the shared skill/prompt.
