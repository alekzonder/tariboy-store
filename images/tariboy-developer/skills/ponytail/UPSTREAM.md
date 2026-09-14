# Upstream

Source: https://github.com/DietrichGebert/ponytail, `skills/ponytail/SKILL.md`.
Revision: `356918eba965ee1eac64bd3a7f0dd02108350de5` (verified byte-for-byte).
The image's `skills-lock.json` records the upstream source and computed hash.

This copy removes only `argument-hint`, which Tariboy 0.59.0 rejects.
The skill body is unchanged. Restore the lock with
`npx skills experimental_install`, then copy the upstream skill here with that
frontmatter field removed when updating. The manifest intentionally packages
this compatible copy rather than the restored upstream directory.
