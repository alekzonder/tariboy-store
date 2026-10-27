---
name: writing-style
description: Use when writing any text for a customer or a person - a task title, description, comment, question or answer, a letter or a reply to one, a status line - or when writing or changing documentation such as a README, guide, runbook or release notes, in English or in Russian.
---

# Writing Style

Every text for a person is short, in the reader's language, and processed by
the plain-language skill of that language. This skill decides the language,
the register and the language skill. The command's owning skill still decides
the storage and the required structure.

## Scope

| Text | Covered |
| --- | --- |
| Communication: task titles, descriptions, comments, questions and answers, letters and letter replies, `status` | yes |
| Documentation for people: `README.md`, guides, runbooks, release notes, other Markdown documents | yes |
| Code, identifiers, commands, commit messages, pull request titles and bodies | no |
| Agent prompts and skills: `SKILL.md`, `instructions.md`, prompt files | no, `writing-skills` owns them |

## Steps for each text

1. Choose the language from the table below.
2. Write the text by the rules of its register: "Brevity rules" for
   communication, "Documentation" for a document.
3. If the language is English, open `simple-english`, apply it and run its
   Self-Check. Task text uses its "The Document" register; a letter reply
   uses "The Reply".
4. If the language is Russian, open `simplified-technical-russian` and apply
   it in its writing mode («Письмо»): only the finished text, no table of
   edits.
5. Before the write, check the text against "Precedence".

Open the language skill for each text; do not apply it from memory. For any
other language, apply only steps 1, 2 and 5.

## Language

| Text | Language |
| --- | --- |
| A reply, an answer, a comment on a task | the language of the question; on a task, the language of the customer's latest text on that task |
| A new task, a question or a letter that starts a conversation | the language of the request that caused it; on a task, the language of its description |
| A change to an existing document | the language of that document |
| A new document | the language of the other documents in the same directory, else in the repository, else the language of the request |

Answer in the language of the question even when the task description uses
another language. Never translate a document into the language of the
request. A new document next to Russian documents is in Russian, even when the
request and these rules are in English. The language of this skill never
selects the language of a text. Code, identifiers, commands, paths, quoted
output and required labels stay as written in every language.

## Brevity rules

These rules apply to communication.

Answer briefly and to the point.

Rules:

- Give the answer first. Add context after it only when the answer is unclear
  or unsafe without it.
- If one sentence can answer the question, answer in one sentence.
- Do not repeat the question. Write no introduction and no closing summary.
- No courtesy phrases and no rating of the question ("Great question", "Hope
  this helps", "Here is what I can suggest").
- Do not offer alternatives or give advice that nobody asked for.
- Do not explain the obvious, and do not mention edge cases that do not change
  the answer.
- Code, a command, a list: give only that, with no explanation around it. If an
  explanation is necessary, keep it to one line.
- One question gets one answer. Ask a clarifying question only when you cannot
  answer without it.
- If you do not know, say "I do not know" and, if there is one, give one
  reason.

Formatting:

- Use lists and headings only when the answer has 3 or more independent items.
- No bold text for decoration.

A detailed answer is allowed only when the user directly asks to explain,
compare or analyze in detail.

Example:

- Question: How do I find which process uses port 8080?
- Answer: `lsof -i :8080`

Write the answer in the language that the "Language" table selects, not in
the language of these rules.

A reply to a question has exactly this shape:

1. The answer: one sentence, or the command or code alone. A "why" question
   gets the cause; a "how" question gets the command or the step.
2. Optional: one more line, only when the answer is unclear or unsafe without
   it.

The reply ends there. A fix, a next step or a check that the question did not
ask for is not part of it. A command answer is the command alone:
`lsof -i :8080`.

## Documentation

A document keeps the headings, numbered steps and tables that its readers
need. A procedure, such as a runbook or setup instructions, is one numbered
list of steps: one action or command per step, verb first. The rules "one sentence if possible" and "lists and headings only for
3+ items" do not apply to it. These brevity rules apply to it: no opener, no
closing summary, no courtesy phrase, no unrequested alternatives or advice,
no explanation of the obvious, no decorative bold.

## Precedence

The owning skill of the command or process wins over this skill on these
points:

- required labels, such as `Required:` or `Verification:`, stay verbatim and
  untranslated, each where the rule puts it, never as a heading;
- a required section or structure stays, even with fewer than 3 items;
- valid Markdown, the one-line `status`, the `cli-text` transport;
- English-only text where the owning skill requires it, such as pull request
  titles and bodies.

A brevity rule never removes a fact, a condition, a number or a warning.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Answering in Russian because the task description is Russian, when the customer asked in English | Use the language of the question |
| Writing a Russian section into an English README for a Russian task | Keep the language of the document |
| Writing a new runbook in English because the request is in English, when the other documents in its directory are in Russian | Use the language of the documents in that directory |
| Explaining around a command, or adding the Windows variant nobody asked for | Give the command alone |
| Adding "Then run it again to confirm" or other advice | Answer the question only |
| Turning `Required:` into `## Required` or translating it | Keep the label verbatim |
| Applying `simplified-technical-russian` to English text, or `simple-english` to Russian text | Apply the skill of the text's language |
