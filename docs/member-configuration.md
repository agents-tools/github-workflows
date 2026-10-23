# Agents-family member configuration

These examples map the current member CI declarations to
`.github/swift-package.json`. All three use `macos-26`, package directory `.`,
and the repository-root `.swift-format`, formatting `Package.swift`, `Sources`
and `Tests`. Their previous workflow selected the runner's default toolchain;
the examples explicitly select Xcode `26.6`, as in the
[shared CI contract](https://github.com/swift-library/skills/blob/main/skills/swiftpm-github-release/references/shared-ci.md).
Confirm that choice against each member's `minimum_swift` when adopting it.

## agents-tools/core

From [`core` CI](https://github.com/agents-tools/core/blob/main/.github/workflows/ci.yml):
package validation and presentation checks, with no executable smoke job or
terminal demo. Its package configuration is:

```json
{
  "compilers": [{"name": "macos-26", "runner": "macos-26", "xcode": "26.6"}],
  "package_directory": ".",
  "format": {"paths": ["Package.swift", "Sources", "Tests"]},
  "commands": [{"name": "diff", "run": "git diff --check"}]
}
```

## agents-tools/cli

From [`agents` CI](https://github.com/agents-tools/cli/blob/main/.github/workflows/ci.yml):
release product `agents`, isolated smoke checks, and the terminal presentation
using `.github/assets/terminal/script.yml` and its `recording.json`.

```json
{
  "compilers": [{"name": "macos-26", "runner": "macos-26", "xcode": "26.6"}],
  "package_directory": ".",
  "format": {"paths": ["Package.swift", "Sources", "Tests"]},
  "demo": {"product": "agents"},
  "commands": [
    {"name": "smoke", "run": "swift build -c release && scripts/check-smoke"},
    {"name": "diff", "run": "git diff --check"}
  ]
}
```

Before adopting this example, extract the current inline Python smoke check
into executable `scripts/check-smoke`. Preserve its temporary HOME/TMPDIR,
restricted PATH and disabled Git configuration; check `--help`, `skills --help`,
the version from `Sources/CLI/EntryPoint.swift`, and exit 64 with stderr for
`unknown`, `skills unknown` and `help unknown`. The command job builds its own
executable because jobs have separate checkouts.

## skill-cli/cli

From [`skill` CI](https://github.com/skill-cli/cli/blob/main/.github/workflows/ci.yml):
the same package settings, release product `skill`, isolated smoke checks and
the terminal presentation at `.github/assets/terminal/`.

```json
{
  "compilers": [{"name": "macos-26", "runner": "macos-26", "xcode": "26.6"}],
  "package_directory": ".",
  "format": {"paths": ["Package.swift", "Sources", "Tests"]},
  "demo": {"product": "skill"},
  "commands": [
    {"name": "smoke", "run": "swift build -c release && scripts/check-smoke"},
    {"name": "diff", "run": "git diff --check"}
  ]
}
```

Extract this member's inline smoke check to its own `scripts/check-smoke` before
adoption. Preserve the same sandbox and version assertion, help for `add`,
`list`, `remove`, `update`, `init`, `install` and `doctor`, and exit 64 checks
for `unknown`, `unknown --help` and `help unknown`.

## Retained checks and caller wiring

All members call `swift-package.yml` as `validate`, with `contents: read` and
`actions: read`, and `policy.yml` as `policy`; see the [caller example](../README.md#calling-validation-and-policy).
Keep member-specific product allowlists in that policy call and enable the
authenticated Dependabot exception for this family.

The previous package workflow unsets `CODEX_HOME`, `CLAUDE_CONFIG_DIR`,
`XDG_CONFIG_HOME`, `XDG_STATE_HOME` and `XDG_CACHE_HOME` for tests. Keep those
overrides absent from the caller environment. The shared validation runs debug
tests and a release build; `commands` retains the whitespace diff check.

The demo job checks the terminal recording only. Existing presentation checks
for other README assets remain with the presentation workflow. Remove an
executable upload only when no retained presentation job consumes it. These
examples describe member adoption; this repository does not supply the
member-owned smoke scripts or change the members' workflows.
