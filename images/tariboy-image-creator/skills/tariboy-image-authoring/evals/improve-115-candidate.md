Case C representative candidate response (repetition 1 of 5):

```bash
cd images/reviewer
npx skills add ../../skills/cli-text
npx skills add ./skills/local-review
npx skills update review -p -y
npx skills remove obsolete-review -y
```

Keep `skills/local-review/SKILL.md` as the canonical local source. Point the
manifest and the cli-text prompt at `./.agents/skills/NAME`, remove the
hand-wired source entry and obsolete skill, commit the canonical source and
`skills-lock.json`, and do not commit `.agents/`.

All five candidate repetitions met all five case C criteria. One regression
sample each for existing cases A and B also met their unchanged rubrics.
