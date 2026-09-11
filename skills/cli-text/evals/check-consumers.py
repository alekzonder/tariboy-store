#!/usr/bin/env python3
"""Replay recorded Bash proposals against temporary recording CLIs."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUB = '#!' + sys.executable + '''
import json
import sys
print(json.dumps(sys.argv[1:]))
'''

def capture(code):
    with tempfile.TemporaryDirectory() as tmp:
        # Replace only known launcher paths; never execute a real service CLI.
        for name in ('tasks', 'context', 'messages', 'status'):
            replacement = Path(tmp, name)
            replacement.write_text(STUB)
            replacement.chmod(0o700)
            pattern = r"""/[^\s'"]*/skills/""" + name + '/scripts/' + name + r'\.sh'
            code = re.sub(pattern, lambda _: str(replacement), code)
        stub = Path(tmp, 'ttasks')
        stub.write_text(STUB)
        stub.chmod(0o700)
        result = subprocess.run([shutil.which('bash'), '-c', code], cwd=tmp,
            env={'PATH': tmp + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'},
            text=True, capture_output=True, timeout=10, check=True)
        return json.loads(result.stdout)

expected = [
    ['comment', 'DEMO-1', "## Result\n\n- O'Reilly fixed `parser` and literal $(printf surprise).\nMARKDOWN_EOF_7F3A"],
    ['set', 'DEMO-1 verify-`parser`\nDEMO-2 inspect-$(printf surprise)'],
    ['message', 'processed', 'fixture:1', "Handled O'Reilly's `parser`; literal $HOME and $(printf surprise)."],
    ['set', "Checking O'Reilly's `parser` with literal $HOME."],
]
for variant in ('baseline', 'candidate'):
    text = (HERE / ('dependent-' + variant + '.md')).read_text()
    snippets = re.findall(r'```bash\n(.*?)\n```', text, re.S)
    assert len(snippets) == len(expected)
    for snippet, value in zip(snippets, expected):
        assert capture(snippet) == value

image_results = list((ROOT / 'images').glob('*/evals/cli-text/results.json'))
assert len(image_results) == 6
for path in image_results:
    result = json.loads(path.read_text())
    assert capture(result['candidate']['command']) == expected[-1]

newline_results = {}
for variant in ('baseline', 'candidate'):
    path = ROOT / 'skills/tasks/evals' / ('cli-text-newlines-' + variant + '.md')
    snippet = re.search(r'```bash\n(.*?)\n```', path.read_text(), re.S).group(1)
    received = capture(snippet)
    exact = received == ['comment', 'DEMO-1', "## Result\n\n- O'Reilly fixed `parser`.\n\n"]
    assert exact == (variant == 'candidate'), received
    newline_results[variant] = {'exact': exact, 'received': received}

for variant in ('baseline', 'candidate'):
    text = (HERE / ('input-modes-' + variant + '.md')).read_text()
    expression = re.search(r'A\. `(.*?)`', text).group(1)
    structured = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
let received;
const add_comment = async value => { received = value; };
vm.runInNewContext('(async () => {' + input.expression + '})()', {
  body: input.body, add_comment, tools: {add_comment}
}).then(() => {
  if (!received || Object.keys(received).join() !== 'body' || received.body !== input.body) process.exitCode = 1;
}).catch(() => {process.exitCode = 1;});
"""
    subprocess.run([shutil.which('node'), '-e', structured],
        input=json.dumps({'expression':expression,'body':"O'Reilly `parser` $HOME\n\0"}),
        env={}, text=True, capture_output=True, check=True)
    code = re.search(r'```bash\n(.*?)\n```', text, re.S).group(1)
    result = subprocess.run([shutil.which('bash'), '-c', 'note-cli() { [ "$#" -eq 2 ] && [ "$1" = set ] && [ "$2" = --stdin ] || return 64; cat; }\n' + code],
        env={'PATH':'/usr/bin:/bin'}, text=True, capture_output=True, check=True)
    assert result.stdout == "O'Reilly `parser` $(printf surprise) $HOME — Привет\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, 'comment body.md')
        path.write_text(result.stdout)
        command = 'gh() { [ "$#" -eq 5 ] && [ "$1" = pr ] && [ "$2" = comment ] && [ "$3" = 42 ] && [ "$4" = --body-file ] && [ "$5" = "$CLI_EXPECTED_FILE" ] || return 64; cat "$5"; }\n' + re.search(r'`(gh pr comment.*?)`', text).group(1)
        command = command.replace('/tmp/comment body.md', str(path))
        received = subprocess.run([shutil.which('bash'), '-c', command],
            env={'PATH':'/usr/bin:/bin','CLI_EXPECTED_FILE':str(path)}, text=True, capture_output=True, check=True)
        assert received.stdout == path.read_text()
print(json.dumps({'consumer_proposals': 8, 'image_proposals': 6,
    'structured_proposals': 2, 'file_and_stdin_proposals': 4, 'tasks_newlines': newline_results}, ensure_ascii=False, indent=2))
