#!/usr/bin/env python3
"""Replay the extra-shell-layer failure against a disposable CLI; no live credentials."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The DEV review texts: an apostrophe, backticks, `$()` and a two-character \n.
payload = ("## Plan correction\n\nThe plan's step 3 must use `tr -d '\\n'`, not `tr -d n`.\n"
           "Don't run `make clean`: $(printf surprise) stays text.")
delimiter = 'CLI_TEXT_S3PB_END'
heredoc = "BODY=$(cat <<'" + delimiter + "'\n" + payload + '\n' + delimiter + '\n)\nnote-cli set "$BODY"'
cli = '#!' + sys.executable + '''
import json
import sys
from pathlib import Path
p = Path('records.json')
records = json.loads(p.read_text()) if p.exists() else []
records.append(sys.argv[1:])
p.write_text(json.dumps(records))
'''
bash = shutil.which('bash')
forms = {
    # What the agents ran: the heredoc recipe inside one more shell layer.
    'bash-lc-wrapper': {'cmd': "bash --noprofile --norc -lc '" + heredoc + "'", 'exact': False},
    # The skill's rule: the same recipe at the top level of the shell tool.
    'top-level-heredoc': {'cmd': heredoc, 'exact': True},
    # The skill's rule: a file written by the file tool, read into one argument.
    'tool-written-file': {'cmd': 'note-cli set "$(cat body.md)"', 'file': True, 'exact': True},
}
results = []
for name, form in forms.items():
    with tempfile.TemporaryDirectory() as tmp:
        executable = Path(tmp, 'note-cli')
        executable.write_text(cli)
        executable.chmod(0o700)
        if form.get('file'):
            Path(tmp, 'body.md').write_text(payload)
        proc = subprocess.run([bash, '--noprofile', '--norc', '-c', form['cmd']], text=True,
            capture_output=True, cwd=tmp, timeout=10,
            env={'PATH': tmp + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        record_path = Path(tmp, 'records.json')
        records = json.loads(record_path.read_text()) if record_path.exists() else []
        exact = proc.returncode == 0 and records == [['set', payload]]
        passed = exact == form['exact']
        results.append({'form': name, 'expected_exact': form['exact'], 'exact': exact,
            'passed': passed, 'exit_code': proc.returncode, 'records': records,
            'stderr': proc.stderr})
        assert passed, results[-1]
print(json.dumps({'results': results}, ensure_ascii=False, indent=2))
