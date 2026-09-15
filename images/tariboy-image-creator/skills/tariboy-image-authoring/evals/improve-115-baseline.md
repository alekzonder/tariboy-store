Case C representative baseline response (repetition 2 of 5):

- Keep `images/reviewer/skills/local-review/SKILL.md` as the sole source and
  connect it directly with `dir: ./skills/local-review`.
- Remove the obsolete manifest entry and update the upstream dependency by
  running `npx skills experimental_install`.
- Commit the manifest, local source and lock; do not commit `.agents/skills`.

The response preserved direct manifest wiring and omitted `npx skills add`,
`update`, and `remove`. All five baseline repetitions failed at least the
local-install criterion; four also omitted the required update/remove commands.
