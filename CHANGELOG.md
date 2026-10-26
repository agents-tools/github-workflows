# Changelog

## Unreleased

- `policy.yml` accepts the agents CLI's tracked instruction files:
  `.agent/instructions/`, `.agent/agents.json` and `.agent/agents.resolved`.
  Other `.agent/` paths stay private execution files. The declaration and lock
  may name agent IDs such as `codex` without an allowed product term.

## 0.1.0

- Add `swift-package.yml` validation for formatting, compiler tests and release
  builds with default traits, additional trait tests on the first compiler,
  Linux, Apple platforms, DocC, terminal demo recording, and repository commands.
- Add `swift-package-release.yml` to verify signed tags and publish changelog
  release notes.
- Add `policy.yml` for commit, pull request, source, and version policy checks.
- Add `organization.yml` to check membership, repository descriptions, and settings.
- Add `homebrew.yml` for formula style, audits, source installation, and tests.
- Add the `select-toolchain` action to select Xcode and optionally install an
  official Swift release.
