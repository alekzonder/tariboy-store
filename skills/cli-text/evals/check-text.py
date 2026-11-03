#!/usr/bin/env python3
"""Run the SKILL.md JavaScript example against a disposable CLI; no live credentials.

The example is read from SKILL.md of the checked revision at run time. Each
input below must reach the stub CLI byte for byte; NUL must be rejected
before any CLI call.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / 'SKILL.md'
INPUTS = [
    # Special characters and a line equal to a common heredoc delimiter.
    "--literal O'Reilly `printf unexpected` $(printf surprise) $HOME \\server\\path\nMARKDOWN_EOF_7F3A\nПривет 😀\n\n",
    '',
    # Collides with the example's own delimiter.
    'CLI_TEXT_END\nCLI_TEXT_END_\nend\n\n',
    'one\r\ntwo\r\n',
    'no final newline',
    '\n\n',
    'before\0after',
]
NODE = r'''
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const tools = {exec_command: async ({cmd}) => {
  const result = spawnSync(input.bash, ['-c', cmd], {encoding: 'utf8', env: process.env});
  return {output: result.stdout, exit_code: result.status};
}};
vm.runInNewContext('(async () => {\n' + input.response + '\n})()', {
  body: input.body, tools, text: () => {}
}).catch(e => {console.error(e); process.exitCode = 1;});
'''
CLI = '#!' + sys.executable + '''
import json
from pathlib import Path
import sys
p = Path('records.json')
records = json.loads(p.read_text()) if p.exists() else []
records.append(sys.argv[1:])
p.write_text(json.dumps(records))
'''

example = re.search(r'```javascript\n(.*?)\n```', SKILL.read_text(), re.S).group(1)
results = []
for case, body in enumerate(INPUTS):
    with tempfile.TemporaryDirectory() as tmp:
        executable = Path(tmp, 'note-cli')
        executable.write_text(CLI)
        executable.chmod(0o700)
        proc = subprocess.run([shutil.which('node'), '-e', NODE],
            input=json.dumps({'body': body, 'response': example, 'bash': shutil.which('bash')}),
            text=True, capture_output=True, cwd=tmp,
            env={'PATH': tmp + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'}, timeout=10)
        record_path = Path(tmp, 'records.json')
        records = json.loads(record_path.read_text()) if record_path.exists() else []
        if '\0' in body:
            passed = proc.returncode != 0 and not records and 'NUL' in proc.stderr
        else:
            passed = proc.returncode == 0 and records == [['set', body]]
        results.append({'case': case, 'passed': passed, 'calls': [r[0] for r in records],
            'received_sha256': hashlib.sha256(records[0][1].encode()).hexdigest() if records and len(records[0]) > 1 else None,
            'exit_code': proc.returncode, 'stderr': proc.stderr, 'stdout': proc.stdout})
        assert passed, results[-1]
print(json.dumps({'skill_sha256': hashlib.sha256(SKILL.read_bytes()).hexdigest(),
    'results': results}, ensure_ascii=False, indent=2))
