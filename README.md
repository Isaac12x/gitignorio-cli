# gitignore-cli

Create and update `.gitignore` files using [gitignore.io](https://www.toptal.com/developers/gitignore) with automatic language detection.

## Install

```bash
uv tool install .
# or
pip install .
```

## Usage

```bash
gitignore create              # OS template + detected languages
gitignore create --no-detect  # OS template only
gitignore update              # append newly detected languages
gitignore add python node     # append specific templates
gitignore list                # list available templates
gitignore hooks install       # auto-create/update .gitignore via git hooks
```

Use `--path` / `-p` to target a directory other than the current one.

## Git hooks

Install hooks once per repository (or use `--global` to seed new repos created with `git init`):

```bash
gitignore hooks install
gitignore hooks install --global
```

This installs:

- **post-checkout** — creates `.gitignore` when a repository is initialized (clone/checkout) if one does not exist
- **pre-push** — updates `.gitignore` before each push, or creates it if missing

Existing hook scripts managed by gitignore-cli are updated in place. Other hook scripts are left intact and receive an appended gitignore-cli block.

Running `gitignore hooks install` also creates `.gitignore` immediately when it is missing in the current repository.

## Language detection

`create` and `update` use [github-linguist](https://github.com/github-linguist/linguist) and [magika](https://github.com/google/magika). The CLI installs them automatically on first run if Ruby `gem` and `pipx` are available.

## License

MIT — see [LICENSE.md](LICENSE.md).

Templates are bundled locally (sourced from [gitignore.io](https://www.toptal.com/developers/gitignore)) and work offline. To refresh them:

```bash
python scripts/download_templates.py
```

Generated `.gitignore` content is [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
