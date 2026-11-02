#!/usr/bin/env python3
"""Codex hook guard: covered-call budgets and automatic final-record checks.

This is not a sandbox: hosted tools, hook failures and same-user tampering remain
outside its guarantee. Stop audits generated text; it cannot retract that text.
"""
import hashlib
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import research_control as control

PLUGIN = Path(__file__).resolve().parents[1]
VALIDATOR = PLUGIN / 'skills/deep-research-circuit/scripts/validate_claims.py'
START = re.compile(r'^\s*(?:\$deep-research-circuit\b|(?:use|run)\s+(?:\$deep-research-circuit\b|Deep Research Circuit\b))', re.I)
COMPLETION = {'apply_patch', 'Edit', 'Write', 'spawn_agent', 'Agent', 'wait_agent',
              'send_message', 'followup_task', 'list_agents', 'interrupt_agent',
              'request_user_input', 'request_user_input_async', 'update_plan'}
BATCH_KEYS = {'queries', 'urls', 'search_query', 'open', 'click', 'image_query', 'requests'}
DEFAULT_CALLS = 12
COMPLETION_CALLS = 12


def actor_identity(payload, state):
    """Use host callback fields, never command arguments or inherited environment."""
    session = payload.get('session_id')
    transcript = payload.get('transcript_path')
    has_child = any(payload.get(k) is not None for k in ('agent_id', 'agent_type'))
    coordinator = (not has_child and isinstance(transcript, str) and bool(transcript)
        and session == state.get('coordinator_session')
        and transcript == state.get('coordinator_transcript')
        and transcript not in state.get('child_transcripts', [])
        and not state.get('ambiguous_authority', False))
    return {'coordinator': coordinator, 'identity': {
        'session': session, 'transcript': transcript, 'agent_id': payload.get('agent_id')}}


def coordination(tool):
    short = tool.rsplit('.', 1)[-1].removeprefix('collaboration').lstrip('_')
    return short in {'send_message', 'wait_agent', 'list_agents', 'interrupt_agent'}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def deny(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny', 'permissionDecisionReason': reason}}


def context(event, state):
    message = dict(
        guard='Deep Research Circuit automatic guard is active on covered local tool calls.',
        evidence_root=state['root'], remaining_units=state['limit'] - state['used'],
        strong_lead_reserve_units=(state.get('stage_units', state['limit']) + 3) // 4,
        completion_units_remaining=state.get('completion_limit', COMPLETION_CALLS) - state['completion_used'],
        hard_ceiling=state.get('ceiling'),
        pending_requests=[k for k,v in state.get('requests', {}).items() if v['status']=='pending'],
        pending_leads=[k for k,v in state.get('leads', {}).items() if v['status']=='pending'],
        instructions='Put claims.json and an actual independent review.json in evidence_root. '
            'Use the installed skill and its claim-validation guide. Final text must equal validator render. '
            'Reserve the final quarter of each approved stage for the strongest unread leads. '
            'Register valuable leads immediately using guard.py control; see references/search-extensions.md. '
            'Workers request bounded extensions; only the host-identified coordinator decides them. '
            'Allowance exhaustion alone cannot justify stopping. Disposition every registered lead and '
            'bind the current research-scope.json into the independent final review. Do not fabricate review. '
            'Only one automatic repair is allowed. /drc end is a user-only control.',
        scope='Counts intercepted calls/recognised batches, not all searches or tokens. '
            'Hosted search, opaque programs, hook failures and editable state are not secured. '
            'Stop checks generated text; it cannot hide or retract it.')
    return {'hookSpecificOutput': {'hookEventName': event,
                                  'additionalContext': json.dumps(message)}}


def local_validator_call(args):
    command = args.get('command', args.get('cmd', '')) if isinstance(args, dict) else ''
    if not isinstance(command, str) or any(c in command for c in '\n\r`$'):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if any(any(c in p for c in '\n\r;|&`$<>') for p in parts if p != '>'):
        return False
    # Permit only a direct local validator invocation, optionally with output redirection.
    if len(parts) == 3 and Path(parts[0]).name in {'python', 'python3'} and Path(parts[1]).resolve() == Path(__file__).resolve() and parts[2] == 'clock':
        return True
    if len(parts) < 4 or Path(parts[0]).name not in {'python', 'python3'}:
        return False
    if Path(parts[1]).resolve() != VALIDATOR or parts[2] not in {'fingerprint', 'review-template', 'check', 'render'}:
        return False
    if '>' in parts:
        if parts.count('>') != 1 or parts[-2] != '>':
            return False
        parts = parts[:-2]
    return len(parts) == 4 or (len(parts) == 6 and parts[4] == '--review' and parts[2] in {'check', 'render'})


def local_evidence_read(args, root, cwd):
    command = args.get('command', args.get('cmd', '')) if isinstance(args, dict) else ''
    if not isinstance(command, str) or any(c in command for c in '\n\r`$'):
        return False
    workdir = args.get('workdir', args.get('cwd', cwd))
    if not isinstance(workdir, str):
        return False
    effective_cwd = (Path(cwd) / workdir).resolve()
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>()')
        lexer.whitespace_split = True
        parts = list(lexer)
    except ValueError:
        return False
    base = Path(root).resolve()
    groups = [[]]
    for value in parts:
        if value in {';', '&&'}:
            groups.append([])
        else:
            groups[-1].append(value)
    for group in groups:
        if len(group) < 2 or group[0] not in {'cat', '/bin/cat'}:
            return False
        for value in group[1:]:
            if any(c in value for c in '\n\r;|&`$<>*?[]()'):
                return False
            path = Path(value)
            path = (effective_cwd / path).resolve() if not path.is_absolute() else path.resolve()
            if not path.is_file() or not (base in path.parents or PLUGIN in path.parents):
                return False
    return True


def charge(tool, args, root, cwd):
    short = tool.rsplit('.', 1)[-1]
    # Codex 0.163 also reports names such as collaborationsend_message.
    if short.startswith('collaboration'):
        short = short.removeprefix('collaboration').lstrip('_')
    # Supported nested calls are metered when the host delivers their callbacks.
    # The networkless wrapper must not spend the reserve needed for those calls.
    # Do not extend this exemption to browser JS or unrestricted code execution.
    if tool == 'functions.exec':
        return 'completion_used', 0
    if coordination(tool):
        return 'completion_used', 0
    if short in {'Bash', 'exec_command', 'shell_command'} and local_validator_call(args):
        return 'completion_used', 0  # Never spend the allowance needed to establish clearance.
    if short in {'Bash', 'exec_command', 'shell_command'} and local_evidence_read(args, root, cwd):
        return 'completion_used', 0
    if short in COMPLETION:
        return 'completion_used', 1
    units = sum(len(v) for k, v in args.items() if k in BATCH_KEYS and isinstance(v, list)) if isinstance(args, dict) else 0
    return 'used', max(1, units)


def check_snapshot(state, message, root):
    command = [sys.executable, str(VALIDATOR), 'check', str(root / 'claims.json'),
               '--review', str(root / 'review.json')]
    checked = subprocess.run(command, capture_output=True, text=True, timeout=8)
    try:
        receipt = json.loads(checked.stdout or checked.stderr)
    except ValueError:
        receipt = {'ok': False, 'errors': [{'code': 'validator_unreadable'}]}
    ok = checked.returncode == 0 and receipt.get('ok') is True
    if ok:
        command[2] = 'render'
        rendered = subprocess.run(command, capture_output=True, text=True, timeout=8)
        ok = rendered.returncode == 0 and isinstance(message, str) and message.strip() == rendered.stdout.strip()
        if not ok:
            receipt = dict(receipt, ok=False, errors=[{'code': 'final_text_mismatch'}])
    scope_errors = control.scope_errors(state, root)
    if scope_errors:
        ok = False
        receipt = dict(receipt, ok=False, errors=receipt.get('errors', []) + scope_errors)
    return ok, receipt


def check_final(state, message):
    root = Path(state['root']).resolve()
    try:
        # All three checks use identical bytes, even if a worker edits live files.
        raw = (root/'claims.json').read_bytes()
        manifest = control.load_json(raw)
        names = {'claims.json', 'review.json', 'research-scope.json', manifest['report']['path']}
        names.update(s['artifact'] for s in manifest['sources'])
        frozen = {'claims.json': raw}
        with tempfile.TemporaryDirectory(prefix='drc-final-') as directory:
            snapshot = Path(directory)
            for name in names:
                relative = Path(name)
                source = (root/relative).resolve()
                if relative.is_absolute() or '..' in relative.parts or '\\' in name or root not in source.parents:
                    raise ValueError('Evidence path leaves the run')
                content = frozen.setdefault(name, source.read_bytes())
                destination = snapshot/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            ok, receipt = check_snapshot(state, message, snapshot)
            if any((root/name).read_bytes() != content for name, content in frozen.items()):
                ok = False
                receipt = dict(receipt, ok=False, errors=receipt.get('errors', []) +
                    [{'code': 'evidence_changed_during_validation'}])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ok = False
        receipt = {'ok': False, 'errors': [{'code': 'validation_snapshot_unavailable', 'detail': str(exc)}]}
    root.mkdir(parents=True, exist_ok=True)
    control.atomic_write(root/'guard-check.json', (json.dumps(receipt, indent=2)+'\n').encode())
    return ok


def handle(payload):
    event = payload.get('hook_event_name')
    session = payload.get('session_id')
    if not isinstance(session, str) or not session:
        raise ValueError('Missing host session identity')
    prompt = payload.get('prompt', '')
    activate = event == 'UserPromptSubmit' and isinstance(prompt, str) and START.match(prompt)
    data = os.environ.get('PLUGIN_DATA')
    if not data:
        if not activate:
            return {}
        raise ValueError('PLUGIN_DATA unavailable: automatic guard cannot activate')
    folder = Path(data).resolve()
    database = folder / 'research-guard.sqlite3'
    if not database.exists() and not activate:
        return {}
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database, timeout=3, isolation_level=None)
    try:
        if activate:
            db.execute('CREATE TABLE IF NOT EXISTS runs (session TEXT PRIMARY KEY, state TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, session TEXT, event TEXT, detail TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS aliases (child TEXT PRIMARY KEY, parent TEXT NOT NULL)')
        alias = db.execute('SELECT parent FROM aliases WHERE child=?', (session,)).fetchone()
        if alias:
            session = alias[0]
        row = db.execute('SELECT state FROM runs WHERE session=?', (session,)).fetchone()
        initial = json.loads(row[0]) if row else None
        # Unrelated chats need no write lock and must not be denied by contention.
        if not activate and (not initial or not initial['active']):
            return {}
        # Validation can read large artifacts: never hold the shared counter lock.
        final_ok = check_final(initial, payload.get('last_assistant_message')) if event == 'Stop' else None
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT state FROM runs WHERE session=?', (session,)).fetchone()
        state = json.loads(row[0]) if row else None
        if event == 'Stop' and (not state or not state['active'] or state['root'] != initial['root']):
            db.execute('COMMIT')
            return {}
        result = {}
        control_receipt = None
        detail = 'inactive'
        if event == 'UserPromptSubmit' and prompt.strip() == '/drc end' and state:
            state['active'] = False
            result = {'systemMessage': 'Deep Research Circuit guard ended by the user; no clearance implied.'}
            detail = 'user_ended'
        elif activate and (not state or not state['active']):
            first_line = prompt.splitlines()[0]
            match = re.search(r'\[calls=(\d+)\]', first_line)
            limit = int(match.group(1)) if match else DEFAULT_CALLS
            if limit > 100:
                raise ValueError('calls must be between 0 and 100')
            match = re.search(r'\[ceiling=(\d+)\]', first_line)
            ceiling = int(match.group(1)) if match else None
            if ceiling is not None and not limit <= ceiling <= 10000:
                raise ValueError('ceiling must be at least calls and no more than 10000')
            cwd = Path(payload['cwd']).resolve()
            if cwd == PLUGIN or PLUGIN in cwd.parents or (cwd / '.hyperresearch-plugin-development').exists():
                raise ValueError('Use a separate study workspace, not the plugin development root')
            generation = state.get('generation', 0) + 1 if state else 1
            root = cwd / 'research-workspaces' / f'drc-{digest(session)[:12]}-{generation}'
            root.mkdir(parents=True, exist_ok=False)
            state = dict(active=True, root=str(root), generation=generation, limit=limit, used=0,
                         completion_used=0, completion_limit=COMPLETION_CALLS, stage_units=limit,
                         ceiling=ceiling, repairs=0, reserve_notified=False, seen={}, request_sha256=digest(prompt),
                         coordinator_session=session, coordinator_transcript=payload.get('transcript_path'),
                         child_transcripts=[], ambiguous_authority=False)
            control.initialise(state)
            control.refresh(state)
            result = context(event, state)
            detail = 'activated'
        elif state and state['active']:
            if event in {'UserPromptSubmit', 'SessionStart', 'SubagentStart'}:
                child = payload.get('agent_id') if event == 'SubagentStart' else None
                if isinstance(child, str) and child and child != session:
                    prior = db.execute('SELECT parent FROM aliases WHERE child=?', (child,)).fetchone()
                    if prior and prior[0] != session:
                        raise ValueError('Host child identity belongs to another parent')
                    db.execute('INSERT OR REPLACE INTO aliases VALUES (?,?)', (child, session))
                    transcript = payload.get('agent_transcript_path', payload.get('transcript_path'))
                    if isinstance(transcript, str) and transcript:
                        if transcript == state.get('coordinator_transcript'):
                            # A parent trace on SubagentStart does not identify the child.
                            # Actual child PreToolUse must still carry its child identity.
                            pass
                        elif transcript not in state.setdefault('child_transcripts', []):
                            state['child_transcripts'].append(transcript)
                result = context(event, state)
                detail = 'resumed_no_reset'
            elif event == 'PreToolUse':
                tool = payload.get('tool_name')
                key = payload.get('tool_use_id')
                if not isinstance(tool, str) or not isinstance(key, str) or not key:
                    raise ValueError('Missing host tool identity')
                args = payload.get('tool_input', {})
                actor = actor_identity(payload, state)
                if payload.get('agent_id') is not None:
                    transcript = payload.get('transcript_path')
                    if transcript == state.get('coordinator_transcript'):
                        state['ambiguous_authority'] = True
                    elif isinstance(transcript, str) and transcript not in state.setdefault('child_transcripts', []):
                        state['child_transcripts'].append(transcript)
                action_file = control.command_file(tool, args, payload['cwd'], state['root'], Path(__file__))
                if action_file:
                    try:
                        raw = action_file.read_bytes()
                        if len(raw) > 1024 * 1024:
                            raise control.ControlError('Control file exceeds 1 MiB')
                        state, response = control.apply(state, raw, actor)
                        control_receipt = (action_file, raw, response)
                        result = {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                            'additionalContext': json.dumps(response)}}
                        detail = 'control_applied'
                    except (control.ControlError, OSError, ValueError) as exc:
                        result = deny(str(exc))
                        detail = 'control_denied'
                    db.execute('INSERT OR REPLACE INTO runs VALUES (?, ?)', (session, json.dumps(state)))
                    db.execute('INSERT INTO events(session,event,detail) VALUES (?,?,?)', (session,event,detail))
                    db.execute('COMMIT')
                    publish_state(database, session)
                    if control_receipt:
                        path, raw, response = control_receipt
                        control.atomic_write(receipt_path(path), json.dumps({
                            'action_sha256': control.sha(raw), 'result': response}).encode())
                    return result
                signature = digest(json.dumps([tool, args], sort_keys=True))
                prior = state['seen'].get(key)
                if prior:
                    result = prior['output'] if signature == prior['signature'] else deny('Tool identity reused with different arguments.')
                    detail = 'duplicate_callback'
                else:
                    control_edit = control.control_patch(tool, args, state['root'], payload['cwd'])
                    counter, units = ('completion_used', 0) if control_edit else charge(tool, args, state['root'], payload['cwd'])
                    maximum = state['limit'] if counter == 'used' else state.get('completion_limit', COMPLETION_CALLS)
                    if state[counter] + units > maximum:
                        result = deny('Deep Research Circuit allowance exhausted for this covered call. '
                                      'This is not a completion reason. Register strong leads and submit a bounded '
                                      'extension request with the unresolved question, next check and expected gain. '
                                      'The coordinator must grant or explain refusal. Control JSON edits under '
                                      'control-actions/, control commands, existing-agent messages and validator '
                                      'checks remain available; do not switch retrieval routes to evade the limit.')
                        if counter == 'used' and not state.get('budget_review_required', False):
                            state['budget_review_required'] = True
                            state['finish'] = None
                            control.refresh(state)
                        detail = 'denied_budget'
                    else:
                        state[counter] += units
                        if counter == 'used' and units:
                            state['finish'] = None
                            control.refresh(state)
                        detail = f'allowed:{counter}:{units}'
                        if counter == 'used' and not state.get('reserve_notified', False) and state['limit'] - state['used'] <= (state.get('stage_units', state['limit']) + 3) // 4:
                            state['reserve_notified'] = True
                            result = {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                'additionalContext': 'Use the remaining approved allowance to check the strongest unresolved leads. '
                                'Stop broad discovery; retain any unverified promising source with its importance and missing check. '
                                f"Remaining units after this call: {state['limit'] - state['used']}. The total is unchanged."}}
                    state['seen'][key] = dict(signature=signature, output=result)
            elif event == 'Stop':
                if state.get('scope_revision') != initial.get('scope_revision'):
                    final_ok = False
                    control.atomic_write(Path(state['root'])/'guard-check.json', json.dumps({
                        'ok': False, 'errors': [{'code': 'scope_changed_during_validation'}]}).encode())
                if final_ok:
                    result = {'systemMessage': 'DRC CLEARED: final text matches the checked report and recorded independent review. '
                               'This is record validation, not source authentication.'}
                    detail = 'cleared'
                elif state['repairs'] == 0 and not payload.get('stop_hook_active', False):
                    state['repairs'] = 1
                    result = {'decision': 'block', 'systemMessage': 'DRC NOT CLEARED: automatic validation failed.',
                        'reason': 'Deep Research Circuit final check failed. Inspect guard-check.json in ' + state['root'] +
                        '. Make one bounded correction using existing evidence and actual independent review; '
                        'do not invent approval or restart research. Final text must match successful render. '
                        'If clearance is unavailable, state the limitation and stop.'}
                    detail = 'repair_once'
                else:
                    result = {'continue': False, 'stopReason': 'DRC validation did not clear after the bounded repair.',
                              'systemMessage': 'DRC NOT CLEARED. Automatic retries stopped; the generated answer is unvalidated.'}
                    detail = 'stopped_uncleared'
        if state:
            db.execute('INSERT OR REPLACE INTO runs VALUES (?, ?)', (session, json.dumps(state)))
            db.execute('INSERT INTO events(session,event,detail) VALUES (?,?,?)', (session, event, detail))
        db.execute('COMMIT')
        if state and state.get('scope_observed_at'):
            publish_state(database, session)
        return result
    finally:
        db.close()


def receipt_path(path):
    return path.with_name(path.name + '.receipt.json')


def publish_state(database, session):
    # Reload while serialising publication: an older hook cannot overwrite a newer snapshot.
    with closing(sqlite3.connect(database, timeout=3)) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT state FROM runs WHERE session=?', (session,)).fetchone()
        state = json.loads(row[0])
        control.atomic_write(Path(state['root'])/'research-scope.json', control.scope_bytes(state))
        db.commit()


def main():
    if sys.argv[1:] == ['clock']:
        print(json.dumps({'observed_at': datetime.now(timezone.utc).isoformat()}))
        return
    if len(sys.argv) == 3 and sys.argv[1] == 'control':
        try:
            path = Path(sys.argv[2]).resolve()
            receipt = control.load_json(receipt_path(path).read_bytes())
            if receipt['action_sha256'] != control.sha(path.read_bytes()):
                raise ValueError('Action contents changed after the hook decision')
            print(json.dumps(receipt['result']))
        except (OSError, ValueError, KeyError) as exc:
            print(json.dumps({'ok': False, 'error': 'No matching hook decision. Load/trust the guard; '
                'this command cannot authorise itself.', 'detail': str(exc)}))
            sys.exit(1)
        return
    payload = {}
    try:
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Oversized hook input')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Expected hook object')
        output = handle(payload)
    except Exception as exc:
        # Emit a valid explicit decision on internal failures, not an accidental hook-error allow.
        message = 'DRC guard error; clearance unavailable: ' + type(exc).__name__
        if isinstance(payload, dict) and payload.get('hook_event_name') == 'PreToolUse':
            output = deny(message)
        else:
            output = {'continue': False, 'stopReason': message, 'systemMessage': message}
    print(json.dumps(output))


if __name__ == '__main__':
    main()
