```bash
CLI_TEXT=$(cat <<'CLI_TEXT_84_END'
## Result

- O'Reilly fixed `parser`.


CLI_TEXT_84_END
printf .
)
CLI_TEXT=${CLI_TEXT%.}
CLI_TEXT=${CLI_TEXT%?}
ttasks comment DEMO-1 "$CLI_TEXT"
```
