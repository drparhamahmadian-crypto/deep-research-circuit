"""Local, auditable research decisions. Host identity is supplied by guard.py."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import tempfile

ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')


class ControlError(ValueError):
    pass


def sha(value):
    return hashlib.sha256(value).hexdigest()


def load_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ControlError('Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ControlError('Non-finite JSON')))


def fields(obj, names):
    if not isinstance(obj, dict) or set(obj) != set(names):
        raise ControlError('Control fields do not match the documented operation')


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ControlError('A specific non-empty explanation is required')
    return value


def identifier(value):
    if not ID.fullmatch(text(value)):
        raise ControlError('Invalid control/lead/request/claim identifier')
    return value


def ids(value):
    if not isinstance(value, list) or len(value) > 100 or len(set(map(str, value))) != len(value):
        raise ControlError('Expected unique identifier list')
    return [identifier(x) for x in value]


def initialise(state):
    for key, default in {'leads': {}, 'requests': {}, 'controls': {}, 'history': [],
                         'scope_revision': 0, 'finish': None,
                         'budget_review_required': False}.items():
        state.setdefault(key, copy.deepcopy(default))


def scope_bytes(state):
    data = {k: state[k] for k in ['scope_revision', 'leads', 'requests', 'history', 'finish',
                                 'budget_review_required']}
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def scope_source(state):
    return dict(id='research_scope', locator='local:research-scope', origin='observed',
        role='primary', observed_at=state['scope_observed_at'], retrieval_status='recovered',
        content_kind='local_text', format='plain_text', artifact='research-scope.json',
        sha256=sha(scope_bytes(state)))


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        file.write(data)
        temporary = Path(file.name)
    temporary.replace(path)


def refresh(state):
    state['scope_revision'] += 1
    state['scope_observed_at'] = datetime.now(timezone.utc).isoformat()


def command_file(tool, args, cwd, root, script):
    if tool.rsplit('.', 1)[-1] not in {'Bash', 'exec_command', 'shell_command'} or not isinstance(args, dict):
        return None
    command = args.get('command', args.get('cmd', ''))
    if not isinstance(command, str) or any(c in command for c in '\n\r`$;|&<>'):
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if len(parts) != 4 or Path(parts[0]).name not in {'python', 'python3'} or parts[2] != 'control':
        return None
    if Path(parts[1]).resolve() != script.resolve():
        return None
    workdir = args.get('workdir', args.get('cwd', cwd))
    if not isinstance(workdir, str):
        raise ControlError('Invalid workdir')
    path = (Path(cwd) / workdir / parts[3]).resolve()
    if Path(root).resolve() not in path.parents or path.suffix != '.json':
        raise ControlError('Control action file must be a JSON file inside this evidence root')
    return path


def control_patch(tool, args, root, cwd):
    if tool.rsplit('.', 1)[-1] not in {'apply_patch', 'Edit', 'Write'} or not isinstance(args, dict):
        return False
    patch = args.get('command', args.get('input', ''))
    if not isinstance(patch, str) or not patch.startswith('*** Begin Patch\n'):
        return False
    headers = re.findall(r'^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$', patch, re.M)
    if not headers or any(kind in {'Delete File', 'Move to'} for kind, _ in headers):
        return False
    base = (Path(root) / 'control-actions').resolve()
    return all(base in (Path(cwd) / name).resolve().parents and Path(name).suffix == '.json'
               for _, name in headers)


def apply(state, raw, actor):
    envelope = load_json(raw)
    fields(envelope, {'id', 'actions'})
    key = identifier(envelope['id'])
    actions = envelope['actions']
    if not isinstance(actions, list) or not 1 <= len(actions) <= 16:
        raise ControlError('Supply 1–16 control actions')
    state = copy.deepcopy(state)
    initialise(state)
    previous = state['controls'].get(key)
    if previous:
        if previous['sha256'] != sha(raw):
            raise ControlError('A control ID cannot be reused for changed action contents')
        return state, previous['result']
    if actions == [{'op': 'status'}]:
        return state, result(state, key, ['status'])
    outcomes = []
    for action in actions:
        if not isinstance(action, dict):
            raise ControlError('Expected control object')
        op = action.get('op')
        if op in {'decide_extension', 'dispose_lead', 'finish'} and not actor['coordinator']:
            raise ControlError('Only the host-identified coordinator can make this decision')
        if op == 'register_lead':
            fields(action, {'op', 'id', 'locator', 'importance', 'next_check'})
            lead_id = identifier(action['id'])
            for field in ['locator', 'importance', 'next_check']: text(action[field])
            if lead_id in state['leads']:
                raise ControlError('A registered lead is retained; use a new ID for a different lead')
            state['leads'][lead_id] = dict(action, status='pending', registered_by=actor['identity'])
            state['finish'] = None
        elif op == 'request_extension':
            fields(action, {'op', 'id', 'units', 'question', 'next_action', 'expected_gain', 'lead_ids'})
            request_id = identifier(action['id'])
            if type(action['units']) is not int or not 1 <= action['units'] <= 20:
                raise ControlError('Request 1–20 additional units for a specific next stage')
            for field in ['question', 'next_action', 'expected_gain']: text(action[field])
            for lead in ids(action['lead_ids']):
                if lead not in state['leads']: raise ControlError('Register the referenced lead first')
            if request_id in state['requests']: raise ControlError('Request ID already exists')
            state['requests'][request_id] = dict(action, status='pending', requested_by=actor['identity'])
            state['finish'] = None
        elif op == 'decide_extension':
            fields(action, {'op', 'request_id', 'decision', 'basis', 'reason'})
            request = state['requests'].get(identifier(action['request_id']))
            if not request or request['status'] != 'pending': raise ControlError('No pending request with that ID')
            text(action['reason'])
            if action['decision'] == 'grant':
                if action['basis'] != 'decision_changing': raise ControlError('A grant needs a decision-changing next check')
                new_limit = state['limit'] + request['units']
                if state.get('ceiling') is not None and new_limit > state['ceiling']:
                    raise ControlError('Coordinator cannot exceed the user hard ceiling')
                state['limit'] = new_limit
                state['stage_units'] = request['units']
                state['reserve_notified'] = False
                state['completion_limit'] = state.get('completion_limit', 12) + 4
            elif action['decision'] == 'deny':
                if action['basis'] not in {'duplicate', 'outside_scope', 'adequate_evidence', 'access_blocked', 'user_hard_limit'}:
                    raise ControlError('Allowance exhaustion alone is not a valid reason to deny further useful work')
                if action['basis'] == 'user_hard_limit' and (state.get('ceiling') is None or state['limit'] < state['ceiling']):
                    raise ControlError('A smaller extension still fits below the user hard ceiling')
            else:
                raise ControlError('Decision must be grant or deny')
            request.update(status=action['decision'], decision=action, decided_by=actor['identity'])
            state['budget_review_required'] = False
            state['finish'] = None
        elif op == 'dispose_lead':
            fields(action, {'op', 'id', 'status', 'basis', 'reason', 'claim_ids'})
            lead = state['leads'].get(identifier(action['id']))
            if not lead: raise ControlError('Unknown lead')
            text(action['reason']); claim_ids = ids(action['claim_ids'])
            allowed = {'resolved': {'source_checked'}, 'dismissed': {'irrelevant', 'duplicate', 'superseded', 'contradicted'},
                       'deferred': {'access_blocked', 'user_input_needed', 'user_hard_limit'}}
            if action['status'] not in allowed or action['basis'] not in allowed[action['status']]:
                raise ControlError('A lead needs an evidence-based disposition; initial allowance is not a stopping reason')
            if action['status'] != 'dismissed' and not claim_ids:
                raise ControlError('Resolved/deferred leads must point to visible report claims')
            if action['basis'] == 'user_hard_limit' and (state.get('ceiling') is None or state['used'] < state['ceiling']):
                raise ControlError('The user hard ceiling has not been reached')
            lead.update(status=action['status'], disposition=action, decided_by=actor['identity'])
            state['finish'] = None
        elif op == 'finish':
            fields(action, {'op', 'outcome', 'reason', 'claim_id'})
            text(action['reason']); identifier(action['claim_id'])
            if action['outcome'] not in {'answered', 'qualified', 'blocked'}: raise ControlError('Invalid finish outcome')
            if state['budget_review_required']: raise ControlError('Coordinator must assess an extension request after exhaustion')
            if any(x['status'] == 'pending' for x in state['requests'].values()): raise ControlError('Pending extension request')
            if any(x['status'] == 'pending' for x in state['leads'].values()): raise ControlError('Pending valuable lead')
            if action['outcome'] == 'answered' and any(x['status'] == 'deferred' for x in state['leads'].values()):
                raise ControlError('Deferred material leads require qualified or blocked completion')
            state['finish'] = dict(action, used_at_finish=state['used'], coordinator=actor['identity'])
        else:
            raise ControlError('Unknown control operation')
        state['history'].append(dict(action=action, actor=actor['identity']))
        outcomes.append(op)
    refresh(state)
    response = result(state, key, outcomes)
    state['controls'][key] = {'sha256': sha(raw), 'result': response}
    return state, response


def result(state, key, outcomes):
    return dict(control_id=key, applied=outcomes, limit=state['limit'], used=state['used'],
        remaining=state['limit']-state['used'], ceiling=state.get('ceiling'),
        pending_requests=[k for k,v in state['requests'].items() if v['status']=='pending'],
        pending_leads=[k for k,v in state['leads'].items() if v['status']=='pending'],
        scope_revision=state['scope_revision'], scope_source=scope_source(state))


def scope_errors(state, snapshot_root=None):
    errors = []
    def issue(code): errors.append({'code':code,'location':'research_scope'})
    if state.get('budget_review_required'): issue('scope_budget_review_required')
    if not state.get('finish'): issue('scope_not_closed')
    if any(x['status']=='pending' for x in state.get('requests',{}).values()): issue('extension_pending')
    if any(x['status']=='pending' for x in state.get('leads',{}).values()): issue('lead_unresolved')
    try:
        root=Path(snapshot_root or state['root']); expected=scope_source(state)
        if (root/'research-scope.json').read_bytes()!=scope_bytes(state): issue('scope_snapshot_mismatch')
        manifest=load_json((root/'claims.json').read_bytes())
        source=next(x for x in manifest['sources'] if x['id']=='research_scope')
        if source!=expected: issue('scope_source_mismatch')
        claims={c['id']:c for c in manifest['claims']}
        scope_claim=claims.get((state.get('finish') or {}).get('claim_id'))
        if not scope_claim or scope_claim['status']=='unverified' or not any(c['source_id']=='research_scope' for c in scope_claim['citations']):
            issue('scope_claim_missing')
        for lead in state['leads'].values():
            if lead['status'] in {'resolved','deferred'}:
                for key in lead['disposition']['claim_ids']:
                    if key not in claims: issue('lead_claim_missing')
                    elif lead['status']=='deferred' and claims[key]['status']!='unverified': issue('lead_uncertainty_hidden')
    except (OSError,ValueError,TypeError,KeyError,StopIteration):
        issue('scope_record_missing')
    return errors
