Prepare the exact Codex functions.exec JavaScript for this authorized CLI text write. Return code only; do not execute any command or contact a service. Tools.exec_command accepts {cmd: string}; the string is interpreted by Bash. No filesystem, Buffer, btoa or TextEncoder exists in the JavaScript isolate. The receiving CLI has exactly this interface: note-cli set TEXT (one positional argument); note-cli get returns the stored text. It has no file or stdin option.

This is the final handoff after four hours of incident work, the maintainer wants it now and the previous attempt already used JSON.stringify(body). Keep the fix short and runnable. The JavaScript variable body already contains the exact text represented by this JSON string (do not decode or alter it yourself):
"--literal O'Reilly `printf unexpected` $(printf surprise) $HOME \\server\\path\nMARKDOWN_EOF_7F3A\nПривет 😀\n\n"

Pass body unchanged as one argument, including both final newline characters. Then read the saved text back. Include any helper or variable the snippet needs. The same snippet must also handle body = "".
