"""Offline executable hook-contract checks; synthetic attestations are test inputs."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / 'hooks/guard.py'


class ResearchGuardTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(GUARD.is_file(), 'Automatic guard is not implemented')
        self.tmp = tempfile.TemporaryDirectory(prefix='drc-guard-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, PLUGIN_DATA=str(self.root / 'data'))

    def hook(self, event, **fields):
        payload = dict(session_id='parent', cwd=str(self.root), hook_event_name=event,
                       transcript_path=str(self.root/'parent.jsonl'))
        payload.update(fields)
        p = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                           text=True, capture_output=True, env=self.env, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def start(self, calls=2):
        result = self.hook('UserPromptSubmit', prompt=f'$deep-research-circuit [calls={calls}]\nA real question')
        context = result['hookSpecificOutput']['additionalContext']
        # Fixed hook-owned path is disclosed in structured context for ordinary callers.
        return Path(json.loads(context)['evidence_root'])

    def tool(self, key, tool='mcp__source__search', **args):
        return self.hook('PreToolUse', tool_name=tool, tool_use_id=key, tool_input=args)

    def denied(self, result):
        return result.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'

    def test_unrelated_and_quoted_mentions_do_not_activate(self):
        for prompt in ['Research flights', 'Review this $deep-research-circuit plugin', '> $deep-research-circuit',
                       '$legacy-deep-research', 'Use Legacy Deep Research']:
            self.assertEqual(self.hook('UserPromptSubmit', prompt=prompt), {})
        self.assertEqual(self.tool('ordinary'), {})
        self.assertFalse((self.root / 'data').exists())

    def test_new_invocation_phrases_activate(self):
        for i, prompt in enumerate(['$deep-research-circuit', 'Use Deep Research Circuit',
                                    'Run Deep Research Circuit']):
            result = self.hook('UserPromptSubmit', session_id=f'activation-{i}', prompt=prompt)
            context = json.loads(result['hookSpecificOutput']['additionalContext'])
            self.assertTrue(Path(context['evidence_root']).is_dir())

    def test_package_directory_and_descendants_cannot_be_study_roots(self):
        package = self.root / 'package'
        shutil.copytree(GUARD.parent.parent, package, ignore=shutil.ignore_patterns('__pycache__'))
        alias = self.root / 'package-alias'
        alias.symlink_to(package, target_is_directory=True)
        for i, cwd in enumerate((package, package / 'hooks', alias / 'hooks')):
            with self.subTest(cwd=cwd):
                payload = {'session_id': f'package-{i}', 'cwd': str(cwd),
                           'hook_event_name': 'UserPromptSubmit', 'prompt': '$deep-research-circuit'}
                process = subprocess.run([sys.executable, str(package / 'hooks/guard.py')],
                    input=json.dumps(payload), text=True, capture_output=True, env=self.env, timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertFalse(json.loads(process.stdout)['continue'])
                self.assertFalse((cwd / 'research-workspaces').exists())

    def test_budget_survives_followup_and_duplicate_callback(self):
        self.start()
        self.assertFalse(self.denied(self.tool('one')))
        self.assertFalse(self.denied(self.tool('one')))
        self.hook('UserPromptSubmit', prompt='$deep-research-circuit [calls=99]\nkeep going')
        self.assertFalse(self.denied(self.tool('two')))
        self.assertTrue(self.denied(self.tool('three')))
        self.assertTrue(self.denied(self.tool('three')))

    def test_batch_is_reserved_before_dispatch(self):
        self.start(2)
        self.assertTrue(self.denied(self.tool('large', queries=['a', 'b', 'c'])))
        self.assertFalse(self.denied(self.tool('fits', queries=['a', 'b'])))
        self.assertTrue(self.denied(self.tool('extra')))

    def test_concurrent_calls_share_one_allowance(self):
        self.start(3)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda i: self.tool(str(i)), range(6)))
        self.assertEqual(sum(not self.denied(r) for r in results), 3)

    def test_completion_reserve_is_separate_and_finite(self):
        self.start(0)
        self.assertTrue(self.denied(self.tool('search')))
        for i in range(12):
            self.assertFalse(self.denied(self.tool(f'edit{i}', tool='apply_patch', command='patch')))
        self.assertTrue(self.denied(self.tool('edit13', tool='apply_patch', command='patch')))

    def test_missing_validation_gets_only_one_repair(self):
        self.start()
        first = self.hook('Stop', last_assistant_message='Trust me', stop_hook_active=False)
        self.assertEqual(first['decision'], 'block')
        self.hook('UserPromptSubmit', prompt=first['reason'])
        second = self.hook('Stop', last_assistant_message='Trust me', stop_hook_active=True)
        self.assertFalse(second['continue'])
        self.assertIn('NOT CLEARED', second['systemMessage'])
        third = self.hook('Stop', last_assistant_message='Trust me', stop_hook_active=False)
        self.assertFalse(third['continue'])

    def make_valid_report(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        text = 'On 2025-01-01, the synthetic catalog listed a widget at 42 units.'
        scope_text = 'The saved-price question is answered; no further decision-changing leads remain.'
        action = folder/'finish.json'
        action.write_text(json.dumps({'id':'finish-test','actions':[{'op':'finish','outcome':'answered',
            'reason':scope_text,'claim_id':'scope'}]}))
        decision = self.tool('finish',tool='Bash',command=f'python3 "{GUARD}" control "{action}"')
        self.assertFalse(self.denied(decision),decision)
        scope_source=json.loads(decision['hookSpecificOutput']['additionalContext'])['scope_source']
        report = f'[[claim:price]] {text}\n[[claim:scope]] {scope_text}\n'
        source = 'The synthetic catalog lists the widget at 42 units.'
        (folder / 'report.md').write_text(report)
        (folder / 'source.txt').write_text(source)
        sha = lambda b: hashlib.sha256(b).hexdigest()
        manifest = dict(schema_version=1, producer_id='producer',
            report=dict(path='report.md', sha256=sha(report.encode())),
            sources=[dict(id='source', locator='local:test-source', origin='observed', role='primary',
                observed_at='2025-01-01T12:00:00+11:00', retrieval_status='recovered', content_kind='local_text',
                format='plain_text', artifact='source.txt', sha256=sha(source.encode())),scope_source],
            claims=[dict(id='price', text=text, status='historical', as_of='2025-01-01', citations=[dict(
                source_id='source', locator='local:test-source', quote='42 units', expected_role='primary')]),
                dict(id='scope',text=scope_text,status='supported',citations=[dict(source_id='research_scope',
                    locator='local:research-scope',quote=scope_text,expected_role='primary')])])
        raw = json.dumps(manifest).encode()
        (folder / 'claims.json').write_bytes(raw)
        (folder / 'review.json').write_text(json.dumps(dict(schema_version=1, reviewer_id='test-reviewer',
            manifest_sha256=sha(raw), report_sha256=sha(report.encode()), coverage_complete=True,
            claims=[dict(id=key, verdict='supported', reason='Synthetic unit-test attestation only.')
                    for key in ['price','scope']])))
        return text + '\n' + scope_text + '\n'

    def test_final_text_and_actual_validator_are_checked_automatically(self):
        folder = self.start()
        rendered = self.make_valid_report(folder)
        bad = self.hook('Stop', last_assistant_message=rendered + 'Bags are guaranteed.')
        self.assertEqual(bad['decision'], 'block')
        good = self.hook('Stop', last_assistant_message=rendered)
        self.assertIn('CLEARED', good['systemMessage'])
        self.assertTrue((folder / 'guard-check.json').exists())
        (folder / 'source.txt').write_text('Source silently changed')
        tampered = self.hook('Stop', last_assistant_message=rendered)
        self.assertFalse(tampered['continue'])
        self.assertFalse(json.loads((folder / 'guard-check.json').read_text())['ok'])

    def test_resume_and_explicit_user_end(self):
        self.start(0)
        restored = self.hook('SessionStart', source='compact')
        self.assertIn('additionalContext', restored['hookSpecificOutput'])
        self.hook('UserPromptSubmit', prompt='/drc end')
        self.assertEqual(self.tool('after-end'), {})

    def test_host_child_identity_shares_parent_budget(self):
        self.start(0)
        self.hook('SubagentStart', agent_id='child', agent_type='researcher')
        result = self.hook('PreToolUse', session_id='child', tool_name='mcp__source__search',
                           tool_use_id='child-search', tool_input={})
        self.assertTrue(self.denied(result))

    def test_local_receipt_reads_and_code_mode_completion_remain_possible(self):
        folder = self.start(0)
        receipt = folder / 'guard-check.json'
        receipt.write_text('{"ok": false}')
        self.assertFalse(self.denied(self.tool('read', tool='functions.exec_command', cmd=f'cat "{receipt}"')))
        self.assertTrue(self.denied(self.tool('escape', tool='functions.exec_command', cmd='cat /etc/hosts')))
        self.assertFalse(self.denied(self.tool('wrapper', tool='functions.exec', code='await tools.apply_patch("patch")')))
        self.assertTrue(self.denied(self.tool('nested', tool='mcp__source__search')))

    def test_inactive_sessions_do_not_acquire_the_active_run_write_lock(self):
        import sqlite3
        self.start(0)
        db = sqlite3.connect(self.root / 'data/research-guard.sqlite3')
        try:
            db.execute('BEGIN IMMEDIATE')
            result = self.hook('PreToolUse', session_id='unrelated', tool_name='Bash',
                               tool_use_id='ordinary', tool_input={'command': 'pwd'})
            self.assertEqual(result, {})
        finally:
            db.close()

    def test_wrapped_research_does_not_consume_completion_reserve(self):
        folder = self.start(12)
        receipt = folder / 'guard-check.json'
        receipt.write_text('{"ok": false}')
        for i in range(12):
            self.assertFalse(self.denied(self.tool(f'wrapper{i}', tool='functions.exec', code='await tools.search()')))
            self.assertFalse(self.denied(self.tool(f'search{i}')))
        self.assertTrue(self.denied(self.tool('extra-search')))
        self.assertFalse(self.denied(self.tool('receipt', tool='Bash', command=f'cat "{receipt}"')))

    def test_final_quarter_is_signalled_without_increasing_the_total(self):
        self.start(4)
        self.tool('one'); self.tool('two')
        warning = self.tool('three')
        self.assertIn('strongest unresolved leads', warning['hookSpecificOutput']['additionalContext'])
        self.assertFalse(self.denied(self.tool('four')))
        self.assertTrue(self.denied(self.tool('five')))

    def test_observed_codex_coordination_names_use_completion_reserve(self):
        self.start(0)
        for name in ['collaborationspawn_agent', 'collaborationsend_message', 'collaborationwait_agent']:
            self.assertFalse(self.denied(self.tool(name, tool=name)))
        self.assertTrue(self.denied(self.tool('fetch', tool='mcp__source__search')))

    def test_observed_relative_read_chains_remain_local(self):
        folder = self.start(0)
        for name in ['guard-check.json','review.json']:(folder/name).write_text('{}')
        a=(folder/'guard-check.json').relative_to(self.root.resolve())
        b=(folder/'review.json').relative_to(self.root.resolve())
        self.assertFalse(self.denied(self.tool('reads',tool='Bash',command=f'cat {a}; cat {b}')))
        self.assertTrue(self.denied(self.tool('network',tool='Bash',command=f'cat {a}; curl https://example.com')))
        self.assertTrue(self.denied(self.tool('substitute',tool='Bash',command=f'cat {a}$(curl https://example.com)')))

    def test_clock_is_available_for_timestamp_repair_after_exhaustion(self):
        self.start(0)
        command=f'python3 "{GUARD}" clock'
        self.assertFalse(self.denied(self.tool('clock',tool='Bash',command=command)))
        p=subprocess.run([sys.executable,str(GUARD),'clock'],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0)
        from datetime import datetime,timezone
        observed=datetime.fromisoformat(json.loads(p.stdout)['observed_at'])
        self.assertLess(abs((datetime.now(timezone.utc)-observed).total_seconds()),5)

    def test_completion_parser_does_not_accept_hidden_commands_and_honours_workdir(self):
        folder=self.start(0)
        a=folder/'guard-check.json';a.write_text('{}')
        executable=folder/'ordinary-file';executable.write_text('not executed by this test')
        self.assertTrue(self.denied(self.tool('newline',tool='Bash',command=f'cat "{a}"\n"{executable}"')))
        self.assertTrue(self.denied(self.tool('clock-injection',tool='Bash',command=f'"$(echo X)/python3" "{GUARD}" clock')))
        self.assertTrue(self.denied(self.tool('clock-chain',tool='Bash',command=f'true;/usr/bin/python3 "{GUARD}" clock')))
        self.assertFalse(self.denied(self.tool('workdir',tool='functions.exec_command',cmd='cat guard-check.json',workdir=str(folder))))

    def test_validation_remains_available_after_completion_allowance(self):
        folder=self.start(0)
        for i in range(12):self.tool(f'edit{i}',tool='apply_patch',command='patch')
        validator=GUARD.parent.parent/'skills/deep-research-circuit/scripts/validate_claims.py'
        command=f'python3 "{validator}" check "{folder}/claims.json" --review "{folder}/review.json"'
        self.assertFalse(self.denied(self.tool('final-check',tool='Bash',command=command)))
        self.assertTrue(self.denied(self.tool('new-search')))
        self.assertTrue(self.denied(self.tool('extra-edit',tool='apply_patch',command='patch')))


if __name__ == '__main__':
    unittest.main()
