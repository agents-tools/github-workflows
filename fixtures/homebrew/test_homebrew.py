"""Exercise tap validation with real Git histories and an isolated brew recorder."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/check-homebrew'


class HomebrewTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.build/homebrew-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tap = self.root / 'tap'
        shutil.copytree(ROOT / 'fixtures/homebrew/Formula', self.tap / 'Formula')
        (self.tap / 'Formula/unchanged.rb').write_text('# Unchanged formula\n')
        self.brew_root = self.root / 'brew'
        self.link = self.brew_root / 'Library/Taps/agents-tools/homebrew-tap'
        self.log = self.root / 'calls.jsonl'
        self.user_config = self.root / 'user-config'
        self.user_home = self.root / 'user-home'
        for directory in (self.user_config / 'homebrew', self.user_home / '.homebrew'):
            directory.mkdir(parents=True)
            (directory / 'trust.json').write_text('{"trustedtaps": ["someone/other"]}\n')
            (directory / 'brew.env').write_text('# Existing user configuration\n')
        self.prior_config = {path: path.read_bytes() for directory in (self.user_config, self.user_home)
                             for path in directory.rglob('*') if path.is_file()}
        self.temporary = self.root / 'temporary files'
        self.temporary.mkdir()
        self.other_link = self.brew_root / 'Library/Taps/someone/homebrew-other'
        self.other_link.mkdir(parents=True)
        (self.other_link / 'keep').write_text('unrelated tap\n')
        binary = self.root / 'bin'
        binary.mkdir()
        recorder = binary / 'brew'
        recorder.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
if sys.argv[1:] == ['--repository']:
    print(os.environ['BREW_ROOT'])
else:
    link = Path(os.environ['BREW_LINK'])
    assert link.resolve() == Path.cwd()
    assert all(os.environ[key] == '1' for key in (
        'HOMEBREW_NO_AUTO_UPDATE', 'HOMEBREW_NO_INSTALL_FROM_API', 'HOMEBREW_NO_ANALYTICS'))
    config = Path(os.environ['XDG_CONFIG_HOME'])
    assert config.parent == Path(os.environ['TMPDIR'])
    assert config.stat().st_mode & 0o777 == 0o700
    store = config / 'homebrew/trust.json'
    trust = json.loads(store.read_text()) if store.exists() else {}
    if sys.argv[1] == 'trust':
        assert sys.argv[2] == '--formula'
        for reference in sys.argv[3:]:
            trust.setdefault('trustedformulae', []).append(reference)
            store.parent.mkdir(parents=True, exist_ok=True)
            store.write_text(json.dumps(trust))
            if os.environ.get('FAIL_COMMAND') == 'trust':
                break
    else:
        assert sys.argv[-1] in trust.get('trustedformulae', [])
    with open(os.environ['BREW_LOG'], 'a') as stream:
        stream.write(json.dumps({'arguments': sys.argv[1:], 'config': str(config), 'trust': trust}) + '\\n')
    if sys.argv[1] == os.environ.get('FAIL_COMMAND'):
        sys.exit(1)
''')
        recorder.chmod(0o755)
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.env = {**environment, 'PATH': f'{binary}:{os.environ["PATH"]}',
                    'BREW_ROOT': str(self.brew_root), 'BREW_LINK': str(self.link),
                    'BREW_LOG': str(self.log), 'GIT_CONFIG_GLOBAL': os.devnull,
                    'GIT_CONFIG_NOSYSTEM': '1', 'HOME': str(self.user_home),
                    'XDG_CONFIG_HOME': str(self.user_config), 'TMPDIR': str(self.temporary)}
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.com')
        self.base = self.commit()

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.tap,
                                       env=self.env, text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'test: fixture')
        return self.git('rev-parse', 'HEAD')

    def run_check(self, *revisions, tap='agents-tools/tap', status=0):
        result = subprocess.run(['bash', str(SCRIPT), tap, *revisions], cwd=self.tap,
                                env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        records = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        for record in records:
            self.assertFalse(Path(record['config']).exists(), 'temporary trust configuration leaked')
        self.assertEqual(list(self.temporary.iterdir()), [])
        current_config = {path: path.read_bytes() for directory in (self.user_config, self.user_home)
                          for path in directory.rglob('*') if path.is_file()}
        self.assertEqual(current_config, self.prior_config)
        self.assertEqual((self.other_link / 'keep').read_text(), 'unrelated tap\n')
        return [record['arguments'] for record in records]

    def validation_calls(self, namespace='agents-tools/tap'):
        return [['trust', '--formula', f'{namespace}/unchanged', f'{namespace}/workflow-hello']] + [
                [command, *flags, f'{namespace}/{name}']
                for name in ('unchanged', 'workflow-hello')
                for command, flags in (('style', []), ('audit', ['--strict']))]

    def test_push_validates_every_formula_and_removes_registration(self):
        self.assertEqual(self.run_check(), self.validation_calls())
        self.assertFalse(self.link.is_symlink())

    def test_trust_grants_only_enumerated_formulae_before_any_validation(self):
        (self.tap / 'Casks').mkdir()
        (self.tap / 'Casks/unrelated.rb').write_text('# Not a formula\n')
        (self.tap / 'cmd').mkdir()
        (self.tap / 'cmd/brew-unrelated.rb').write_text('# Not a formula\n')
        (self.tap / 'Formula/extra.rb').write_text('# Another audited formula\n')
        calls = self.run_check()
        expected = {f'agents-tools/tap/{name}' for name in ('extra', 'unchanged', 'workflow-hello')}
        self.assertEqual(calls[0][:2], ['trust', '--formula'])
        self.assertEqual(set(calls[0][2:]), expected)
        records = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len({record['config'] for record in records}), 1)
        for record in records:
            self.assertEqual(record['trust'], {'trustedformulae': sorted(expected)})
        self.assertEqual({call[-1] for call in calls if call[0] == 'audit'}, expected)

    def test_each_invocation_uses_a_fresh_store_without_xdg_configuration(self):
        del self.env['XDG_CONFIG_HOME']
        self.run_check()
        first = json.loads(self.log.read_text().splitlines()[0])['config']
        self.log.unlink()
        self.run_check()
        second = json.loads(self.log.read_text().splitlines()[0])['config']
        self.assertNotEqual(first, second)

    def test_second_caller_namespace(self):
        self.link = self.brew_root / 'Library/Taps/skill-cli/homebrew-tap'
        self.env['BREW_LINK'] = str(self.link)
        self.assertEqual(self.run_check(tap='skill-cli/tap'), self.validation_calls('skill-cli/tap'))

    def test_pr_installs_and_tests_only_changed_formula(self):
        with (self.tap / 'Formula/workflow-hello.rb').open('a') as stream:
            stream.write('# Change\n')
        head = self.commit()
        self.assertEqual(self.run_check(self.base, head), self.validation_calls() + [
            ['install', '--build-from-source', 'agents-tools/tap/workflow-hello'],
            ['test', 'agents-tools/tap/workflow-hello']])

    def test_pr_added_renamed_and_deleted_formulae(self):
        (self.tap / 'Formula/workflow-hello.rb').rename(self.tap / 'Formula/renamed.rb')
        (self.tap / 'Formula/unchanged.rb').unlink()
        (self.tap / 'Formula/added.rb').write_text('# New formula\n')
        calls = self.run_check(self.base, self.commit())
        self.assertEqual([call for call in calls if call[0] == 'install'], [
            ['install', '--build-from-source', 'agents-tools/tap/added'],
            ['install', '--build-from-source', 'agents-tools/tap/renamed']])
        self.assertEqual(len([call for call in calls if call[0] == 'test']), 2)

    def test_non_formula_changes_do_not_install(self):
        (self.tap / 'README.md').write_text('Tap\n')
        self.assertEqual(self.run_check(self.base, self.commit()), self.validation_calls())

    def test_nested_tap_uses_relative_diff_paths(self):
        nested = self.tap / 'fixtures/homebrew'
        nested.mkdir(parents=True)
        (self.tap / 'Formula').rename(nested / 'Formula')
        base = self.commit()
        with (nested / 'Formula/workflow-hello.rb').open('a') as stream:
            stream.write('# Change\n')
        head = self.commit()
        self.tap = nested
        calls = self.run_check(base, head)
        self.assertIn(['test', 'agents-tools/tap/workflow-hello'], calls)

    def test_empty_tap_succeeds_without_brew(self):
        shutil.rmtree(self.tap / 'Formula')
        self.assertEqual(self.run_check(), [])
        self.assertFalse(self.link.exists())

    def test_invalid_namespace_or_revisions_fail_before_brew(self):
        for namespace in ('../tap', 'agents-tools/../../tap', '-bad/tap', 'owner/tap/extra'):
            with self.subTest(namespace=namespace):
                self.assertEqual(self.run_check(tap=namespace, status=2), [])
        self.run_check(self.base, 'missing', status=128)
        self.assertFalse(self.link.exists())

    def test_existing_registration_is_preserved(self):
        self.link.mkdir(parents=True)
        self.assertEqual(self.run_check(status=1), [])
        self.assertTrue(self.link.is_dir())

    def test_each_brew_failure_propagates_and_cleans_registration(self):
        with (self.tap / 'Formula/workflow-hello.rb').open('a') as stream:
            stream.write('# Change\n')
        head = self.commit()
        for command in ('trust', 'style', 'audit', 'install', 'test'):
            with self.subTest(command=command):
                self.log.unlink(missing_ok=True)
                self.env['FAIL_COMMAND'] = command
                calls = self.run_check(self.base, head, status=1)
                self.assertEqual(calls[-1][0], command)
                self.assertFalse(self.link.is_symlink())


if __name__ == '__main__':
    unittest.main()
