# CI and releases

`build.yml` checks every push and pull request and publishes nothing. `release.yml` runs only for
a `vX.Y.Z` tag and publishes the images and the GitHub Release. `pages.yml` builds these docs.

## Build workflow

On every push to `main` and every pull request:

| Job | What it does |
| --- | --- |
| `lint` | actionlint (pinned version, verified by sha256) over the workflows; shellcheck over the s6 scripts and `scripts/*.sh`. |
| `python` | Installs with uv on Python 3.14; ruff lint, ruff format check, mypy, pytest. |
| `add-on manifest` | `frenck/action-addon-linter` on `auracast/`, because a manifest the Supervisor rejects is a store card that silently never appears. |
| `amd64`, `aarch64` | Native runners, no qemu. Builds the image with the per-architecture base image, checks the image architecture, runs the smoke test. |

Every third-party action is pinned to a commit SHA with the version as a trailing comment;
Dependabot updates them weekly.

## Docs workflow

`pages.yml` builds the docs with `sphinx-build -W` on every pull request that touches `docs/`,
`src/` or `pyproject.toml`, so a broken docstring fails CI. On a push to `main` touching the same
paths, or when run by hand, it also deploys the result to GitHub Pages.

## Cutting a release

1. Bump the version in **both** `auracast/config.yaml` (`version: "X.Y.Z"`) and `pyproject.toml`
   (`version = "X.Y.Z"`).
2. Add a `## X.Y.Z` section at the **top** of `auracast/CHANGELOG.md`, written for users.
3. Merge to `main`.
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.

## Release workflow

| Job | What it does |
| --- | --- |
| `preflight` | Fails before anything is built unless the tag is `vMAJOR.MINOR.PATCH`, `config.yaml` has exactly one matching `version:` line, and `pyproject.toml` agrees. |
| `amd64`, `aarch64` | Builds with buildx and pushes to `ghcr.io/yagoor/auracast-addon` *by digest*, untagged. Pulls it back, checks the architecture and runs the smoke test against what the registry holds. Uploads the digest. |
| `manifest` | Checks both digests arrived, assembles a multi-architecture manifest tagged `:X.Y.Z` and `:latest`, and verifies it lists `linux/amd64` and `linux/arm64`. |
| `release` | Last, so a Release never announces an image that failed to publish. Skips if the tag already has a Release, so re-running is safe. Otherwise writes the notes with `release_notes.sh` and creates the Release. |

## Release notes

`scripts/release_notes.sh` builds the Release body from the changelog, not from pull request
titles. It takes every `## X.Y.Z` section after the previous release's version up to the one
being released, so versions that were bumped but never tagged are not lost.

```sh
scripts/release_notes.sh --version 0.1.1 --previous 0.1.0 --image ghcr.io/yagoor/auracast-addon
```

- The previous release is the highest earlier `vX.Y.Z` tag in the tag's history;
  `--previous ''` means the first release.
- It fails if the released version has no section, or if its section is not the topmost one in
  range.
- Code fences are skipped when looking for headings, and an unclosed fence is an error.
- The body starts with *Published as `…:X.Y.Z` and `…:latest`*, and names any folded-in
  versions.
