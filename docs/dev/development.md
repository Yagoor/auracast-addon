# Local development

A uv-managed virtual environment, the same checks CI runs, and a Docker build with a
hardware-free smoke test.

## Set up

You need [uv](https://docs.astral.sh/uv/), plus a C compiler and git: `lc3py` has no wheel and is
built from the liblc3 source tag in `pyproject.toml`. uv downloads Python 3.14 if you do not have
it.

```sh
git clone https://github.com/Yagoor/auracast-addon.git
cd auracast-addon
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python --editable '.[dev]'
```

## Run the checks

The same commands as the `python` job in CI:

```sh
.venv/bin/ruff check .           # lint
.venv/bin/ruff format --check .  # formatting
.venv/bin/mypy                   # strict type check of src and tests
.venv/bin/python -m pytest       # tests
```

Ruff targets Python 3.14 with a 100-character line and a broad rule set (including the bandit,
async and pylint rules); mypy runs in `strict` mode. pytest runs with `asyncio_mode = "auto"`,
and the tests mirror the package layout under `tests/`. No Bluetooth hardware is needed.

CI also lints the workflows with actionlint and the shell scripts with shellcheck:

```sh
shellcheck --shell=bash rootfs/etc/s6-overlay/s6-rc.d/*/run rootfs/etc/s6-overlay/s6-rc.d/*/finish
shellcheck scripts/*.sh
```

## Run the player outside Home Assistant

The entry point reads the same options file the Supervisor writes, and keeps its state in a
directory you choose:

```sh
mkdir -p dev-state
cat > dev-options.json <<'JSON'
{"name": "Dev Auracast", "auracast_controller": "/dev/ttyACM0", "log_level": "debug"}
JSON
.venv/bin/auracast-player --options dev-options.json --state-dir dev-state
```

Without `--options` and `--state-dir` it uses `/data/options.json` and `/data`. It still needs a
supported controller to get past startup.

## Build the image

The `Dockerfile` has two stages on the Home Assistant Debian base. The build stage installs a
uv-managed Python 3.14 into `/opt/python` and the project into `/opt/venv`, compiling lc3py; the
final stage copies only `/opt` and `rootfs/`, and adds `libstdc++6`.

`BUILD_FROM` is a per-architecture digest, not a multi-arch index, so build natively and pass the
matching digest. The default is the amd64 one; on an ARM machine pass the aarch64 digest from the
matrix in `.github/workflows/build.yml`:

```sh
# amd64: the Dockerfile's default base
docker build --tag auracast:dev .

# aarch64: pass the base digest from build.yml
docker build --build-arg "BUILD_FROM=ghcr.io/home-assistant/aarch64-base-debian@sha256:…" --tag auracast:dev .
```

```{note}
The base digests appear in the `Dockerfile`, `build.yml` and `release.yml`. Dependabot does not
follow them; a bump moves all of them together.
```

## Smoke test

`scripts/smoke_test.sh` runs the built image without Bluetooth hardware and checks that the
player starts, reads its options, imports its native libraries and fails cleanly:

```sh
scripts/smoke_test.sh auracast:dev
```

| Check | Expects |
| --- | --- |
| prints its usage | exit 0, `usage: auracast-player` |
| refuses a missing options file | exit 1, `Cannot read the add-on options` |
| asks for a controller when none is selected | exit 1, `Select the Auracast controller` |
| refuses a port that is not a supported controller | exit 1, `is not a serial port on this system` |

## Build these docs

The docs are Sphinx with the Furo theme and MyST Markdown, in `docs/`. The API reference is
generated from the docstrings, so the package is installed with all its runtime dependencies,
lc3py included, which needs the same compiler and git as the development setup above.

```sh
uv pip install --python .venv/bin/python --editable '.[docs]'
.venv/bin/sphinx-build -W --keep-going -b html docs docs/_build/html
```

Warnings are errors, as in CI, so a broken docstring or link fails the build. Open
`docs/_build/html/index.html` to read the result.
