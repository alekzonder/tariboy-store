Before passing text to a CLI (including comments, context, messages and status),
read and apply the `cli-text` skill together with the command's owning skill.
Text is data: JSON serialization is not shell quoting. Use a structured input,
a documented file/stdin input, or the skill's quoted-heredoc recipe.
