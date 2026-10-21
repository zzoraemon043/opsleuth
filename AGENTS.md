# Contributor rules

These rules apply to every contributor, human or automated.

## Code

- Do not write code comments. Name things so the code explains itself.
- Do not use emoji in code, docs, commit messages, issues or pull requests.
- Keep functions small and files focused on one job.
- Tests only use bytecode compiled from sources in `tests/data/src`. Never commit bytecode, keys or recovered sources taken from a shipped product.
- Do not add decryption, key search or protection bypass features. See docs/responsible-use.md.

## Commits and pull requests

- Commit messages are one short line in Traditional Chinese with a prefix and an ASCII colon, for example `新增:LuaJIT 檔頭解析` or `修正:CLOSURE 約束邊界`.
- Author commits as the repository owner: `zzoraemon043 <195147269+zzoraemon043@users.noreply.github.com>`.
- Do not add co-author trailers, tool attribution lines, session links or "generated with" footers.

## Docs

- Keep `README.md` bilingual: Traditional Chinese (Taiwan) and English.

## Checks before pushing

- `ruff check .`
- `python -m pytest -q`
