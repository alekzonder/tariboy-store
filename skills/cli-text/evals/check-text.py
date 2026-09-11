#!/usr/bin/env python3
"""Execute archived snippets against a disposable CLI; no live credentials."""
import hashlib
import json
import re
import sys
from pathlib import Path
import subprocess
import tempfile
import shutil

HERE = Path(__file__).resolve().parent
variant = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
runs = json.loads((HERE / (variant + '.json')).read_text())
payload = "--literal O'Reilly `printf unexpected` $(printf surprise) $HOME \\server\\path\nMARKDOWN_EOF_7F3A\nПривет 😀\n\n"
node = r'''
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
cli = '#!' + sys.executable + '''
import json
from pathlib import Path
import sys
p = Path('records.json')
records = json.loads(p.read_text()) if p.exists() else []
records.append(sys.argv[1:])
p.write_text(json.dumps(records))
if sys.argv[1] == 'get':
    sys.stdout.write(records[0][1])
'''
if variant == 'candidate':
    doc = (HERE.parent / 'SKILL.md').read_text()
    example = re.search(r'```javascript\n(.*?)\n```', doc, re.S).group(1)
    runs['runs'].append({'actor': 'documentation-example', 'response': example, 'invalid': False, 'write_only': True})
else:
    runs['runs'].append({'actor': 'historical-mechanism-reproduction',
        'response': 'await tools.exec_command({cmd: "note-cli set " + JSON.stringify(body)});',
        'invalid': False, 'write_only': True, 'historical': True})
results = []
for run in runs['runs']:
    if run['invalid']:
        results.append({'actor': run['actor'], 'result': 'invalid: actor did not read fixture'})
        continue
    cases = [payload, '', 'CLI_TEXT_END\nCLI_TEXT_END_\nend\n\n', 'one\r\ntwo\r\n', 'no final newline', '\n\n']
    if variant == 'candidate':
        cases.append('before\0after')
    for case, body in enumerate(cases):
        if run.get('historical') and case != 0:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp, 'note-cli')
            executable.write_text(cli)
            executable.chmod(0o700)
            proc = subprocess.run([shutil.which('node'), '-e', node],
                input=json.dumps({'body': body, 'response': run['response'], 'bash': shutil.which('bash')}),
                text=True, capture_output=True, cwd=tmp,
                env={'PATH': tmp + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'}, timeout=10)
            record_path = Path(tmp, 'records.json')
            records = json.loads(record_path.read_text()) if record_path.exists() else []
            expected = [['set', body]] + ([] if run.get('write_only') else [['get']])
            exact = proc.returncode == 0 and records == expected
            rejecting = '\0' in body
            passed = (proc.returncode != 0 and not records and 'NUL' in proc.stderr) if rejecting else (not exact if run.get('historical') else exact)
            results.append({'actor': run['actor'], 'case': case, 'expected_exact': not run.get('historical', False) and not rejecting,
                'expected_rejection': rejecting,
                'passed': passed, 'calls': [r[0] for r in records],
                'received_sha256': hashlib.sha256(records[0][1].encode()).hexdigest() if records and len(records[0]) > 1 else None,
                'exit_code': proc.returncode,
                'stderr': proc.stderr, 'stdout': proc.stdout})
            assert passed, results[-1]
report = {'results': results, 'hashes': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
          for name in ('request.md', 'rubric.md', variant + '.json')}}
if variant == 'candidate':
    report['skill_sha256'] = hashlib.sha256((HERE.parent / 'SKILL.md').read_bytes()).hexdigest()
print(json.dumps(report, ensure_ascii=False, indent=2))
