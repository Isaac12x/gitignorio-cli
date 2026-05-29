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
gitignore update              # sync detected languages
gitignore add python node     # append specific templates
gitignore list                # list available templates
```

Use `--path` / `-p` to target a directory other than the current one.

## Language detection

`create` and `update` use [github-linguist](https://github.com/github-linguist/linguist) and [magika](https://github.com/google/magika). The CLI installs them automatically on first run if Ruby `gem` and `pipx` are available.

## License

MIT — see [LICENSE.md](LICENSE.md).

Generated `.gitignore` content comes from gitignore.io and is [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
