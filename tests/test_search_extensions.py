"""Necessary hook-level extension and source-retention contracts; no live search."""
import test_research_guard as baseline
import hashlib
import json
from pathlib import Path
import unittest
from contextlib import closing
import os
import sqlite3
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, str(baseline.GUARD.parent))
import guard
import research_control


GUARD = baseline.GUARD


class SearchExtensionTests(baseline.ResearchGuardTests):
    # Reuse fixture helpers without rerunning the inherited baseline test methods.
    def hook(self, event, **fields):
        fields.setdefault('transcript_path', str(self.root / 'parent.jsonl'))
        return super().hook(event, **fields)

    def control(self, name, actions, actor='parent', transcript=None):
        path=self.evidence/f'{name}.json'
        path.write_text(json.dumps({'id':name,'actions':actions}))
        result=self.hook('PreToolUse', session_id=actor,
            transcript_path=transcript or str(self.root/f'{actor}.jsonl'),
            tool_name='Bash',tool_use_id=f'control-{name}',
            tool_input={'command':f'python3 "{GUARD}" control "{path}"'})
        return result

    def arm(self, calls=0, ceiling=None):
        prompt=f'$deep-research-circuit [calls={calls}]'
        if ceiling is not None:prompt+=f' [ceiling={ceiling}]'
        data=self.hook('UserPromptSubmit',prompt=prompt+'\nQuestion')
        self.evidence=Path(json.loads(data['hookSpecificOutput']['additionalContext'])['evidence_root'])

    def request(self, name='req', units=2, leads=None):
        return {'op':'request_extension','id':name,'units':units,
            'question':'Does the actual listing describe a completed house?',
            'next_action':'Open the actual seller listing',
            'expected_gain':'Could exclude a misleading affordable candidate',
            'lead_ids':leads or []}

    def decision(self, request='req', decision='grant', basis='decision_changing'):
        return {'op':'decide_extension','request_id':request,'decision':decision,
            'basis':basis,'reason':'A primary listing can resolve the accommodation constraint.'}

    def test_worker_cannot_self_approve_and_coordinator_can_extend_without_reset(self):
        self.arm(1)
        self.hook('SubagentStart',agent_id='child',agent_type='researcher')
        self.tool('first')
        self.assertFalse(self.denied(self.control('request',[self.request()],actor='child')))
        self.assertTrue(self.denied(self.control('self-approve',[self.decision()],actor='child')))
        self.assertTrue(self.denied(self.control('shared-session-spoof',[self.decision()],transcript=str(self.root/'child.jsonl'))))
        self.assertFalse(self.denied(self.control('approve',[self.decision()])))
        self.assertFalse(self.denied(self.tool('second')))
        self.assertFalse(self.denied(self.tool('third')))
        self.assertTrue(self.denied(self.tool('fourth')))

    def test_duplicate_approval_cannot_double_grant_and_hard_ceiling_holds(self):
        self.arm(0,ceiling=2)
        self.control('request',[self.request()])
        self.assertFalse(self.denied(self.control('approve',[self.decision()])))
        # New delivery ID, same exact action is idempotent.
        self.assertFalse(self.denied(self.control('approve',[self.decision()])))
        self.control('more',[self.request('req2')])
        self.assertTrue(self.denied(self.control('too-many',[self.decision('req2')])))
        self.tool('a');self.tool('b')
        self.assertTrue(self.denied(self.tool('c')))

    def test_pending_lead_survives_denial_and_budget_is_not_a_disposition(self):
        self.arm()
        lead={'op':'register_lead','id':'listing','locator':'https://example.com/listing',
              'importance':'Could reverse the recommendation','next_check':'Read actual seller description'}
        self.control('register',[lead,self.request(leads=['listing'])])
        self.assertFalse(self.denied(self.control('reject',[self.decision(decision='deny',basis='adequate_evidence')])))
        self.assertTrue(self.denied(self.control('finish-early',[{'op':'finish','outcome':'answered','reason':'Enough searches','claim_id':'scope'}])))
        bad={'op':'dispose_lead','id':'listing','status':'deferred','basis':'budget_exhausted',
             'reason':'Used allowance','claim_ids':['gap']}
        self.assertTrue(self.denied(self.control('budget-excuse',[bad])))
        scope=json.loads((self.evidence/'research-scope.json').read_text())
        self.assertEqual(scope['leads']['listing']['status'],'pending')

    def test_approval_without_host_transcript_is_denied(self):
        self.arm()
        self.control('request',[self.request()])
        path=self.evidence/'approval.json';path.write_text(json.dumps({'id':'approval','actions':[self.decision()]}))
        result=self.hook('PreToolUse',transcript_path=None,tool_name='Bash',tool_use_id='missing-identity',
            tool_input={'command':f'python3 "{GUARD}" control "{path}"'})
        self.assertTrue(self.denied(result))

    def test_empty_request_and_changed_action_identity_are_rejected(self):
        self.arm()
        empty=self.request();empty['expected_gain']=''
        self.assertTrue(self.denied(self.control('empty',[empty])))
        self.assertFalse(self.denied(self.control('request',[self.request()])))
        altered=self.request();altered['units']=10
        self.assertTrue(self.denied(self.control('request',[altered])))

    def test_native_parent_session_child_metadata_cannot_approve(self):
        self.arm()
        self.control('request',[self.request()])
        path=self.evidence/'native-child.json'
        path.write_text(json.dumps({'id':'native-child','actions':[self.decision()]}))
        # Shape observed in the 2026-10-23 native probe: child has parent session_id,
        # host agent_id, agent_type and its own transcript, not an environment token.
        result=self.hook('PreToolUse',session_id='parent',agent_id='child',agent_type='researcher',
            transcript_path=str(self.root/'child.jsonl'),tool_name='Bash',tool_use_id='native-child',
            tool_input={'command':f'python3 "{GUARD}" control "{path}"'})
        self.assertTrue(self.denied(result))
        # Empty-but-present child metadata must not authenticate as coordinator.
        result=self.hook('PreToolUse',agent_id='',agent_type='',tool_name='Bash',tool_use_id='empty-child',
            tool_input={'command':f'python3 "{GUARD}" control "{path}"'})
        self.assertTrue(self.denied(result))

    def test_control_cli_requires_matching_hook_receipt(self):
        self.arm()
        path=self.evidence/'receipt.json'
        path.write_text(json.dumps({'id':'receipt','actions':[self.request()]}))
        command=[sys.executable,str(GUARD),'control',str(path)]
        before=subprocess.run(command,capture_output=True,text=True,env=self.env,timeout=5)
        self.assertEqual(before.returncode,1)
        self.assertFalse(self.denied(self.control('receipt',[self.request()])))
        after=subprocess.run(command,capture_output=True,text=True,env=self.env,timeout=5)
        self.assertEqual(after.returncode,0,after.stdout)
        path.write_text(path.read_text().replace('seller listing','invented listing'))
        changed=subprocess.run(command,capture_output=True,text=True,env=self.env,timeout=5)
        self.assertEqual(changed.returncode,1)

    def test_scope_review_becomes_stale_after_new_work(self):
        self.arm(1)
        rendered=self.make_valid_report(self.evidence)
        self.assertIn('DRC CLEARED:',self.hook('Stop',last_assistant_message=rendered)['systemMessage'])
        self.assertFalse(self.denied(self.tool('new-work')))
        stale=self.hook('Stop',last_assistant_message=rendered)
        self.assertEqual(stale['decision'],'block')
        codes={x['code'] for x in json.loads((self.evidence/'guard-check.json').read_text())['errors']}
        self.assertIn('scope_not_closed',codes)
        self.assertIn('scope_source_mismatch',codes)

    def test_exhaustion_requires_decision_and_deferred_lead_stays_visible(self):
        self.arm(0,ceiling=0)
        self.assertTrue(self.denied(self.tool('exhausted')))
        finish={'op':'finish','outcome':'qualified','reason':'Hard limit leaves the listing unverified.','claim_id':'scope'}
        self.assertTrue(self.denied(self.control('premature',[finish])))
        lead={'op':'register_lead','id':'listing','locator':'https://example.com/listing',
              'importance':'May change the choice','next_check':'Open the primary listing'}
        self.control('lead',[lead,self.request(leads=['listing'])])
        defer={'op':'dispose_lead','id':'listing','status':'deferred','basis':'user_hard_limit',
               'reason':'Explicit hard ceiling reached; listing needs inspection.','claim_ids':['gap']}
        self.assertFalse(self.denied(self.control('close',[
            self.decision(decision='deny',basis='user_hard_limit'),defer,finish])))
        with closing(sqlite3.connect(self.root/'data/research-guard.sqlite3')) as db:
            state=json.loads(db.execute('SELECT state FROM runs').fetchone()[0])
        scope_claim={'id':'scope','status':'supported','citations':[{'source_id':'research_scope'}]}
        manifest={'sources':[research_control.scope_source(state)],'claims':[scope_claim]}
        (self.evidence/'claims.json').write_text(json.dumps(manifest))
        self.assertIn('lead_claim_missing',{e['code'] for e in research_control.scope_errors(state)})
        manifest['claims'].append({'id':'gap','status':'supported'})
        (self.evidence/'claims.json').write_text(json.dumps(manifest))
        self.assertIn('lead_uncertainty_hidden',{e['code'] for e in research_control.scope_errors(state)})
        manifest['claims'][1]['status']='unverified'
        (self.evidence/'claims.json').write_text(json.dumps(manifest))
        self.assertEqual(research_control.scope_errors(state),[])
        self.assertEqual(state['leads']['listing']['locator'],lead['locator'])
        self.assertEqual(len(state['history']),5)

    def test_control_path_remains_open_after_both_budgets(self):
        self.arm(0)
        for i in range(12):self.tool(f'edit{i}',tool='apply_patch',command='patch')
        path=self.evidence/'control-actions/request.json'
        command=f'*** Begin Patch\n*** Add File: {path}\n+{{}}\n*** End Patch'
        self.assertFalse(self.denied(self.tool('control-edit',tool='apply_patch',command=command)))
        self.assertFalse(self.denied(self.tool('read-at-limit',tool='Bash',
            command=f'cat "{self.evidence}/research-scope.json"')))
        for name in ['collaborationsend_message','collaborationwait_agent','collaborationlist_agents']:
            self.assertFalse(self.denied(self.tool(name,tool=name)))
        self.assertFalse(self.denied(self.control('request',[self.request()])))
        self.assertFalse(self.denied(self.control('grant',[self.decision()])))
        self.assertFalse(self.denied(self.tool('after-extension',tool='apply_patch',command='patch')))
        outside=command.replace(str(path),str(self.root/'outside.json'))
        self.assertFalse(research_control.control_patch('apply_patch',{'command':outside},str(self.evidence),str(self.root)))

    def test_scope_change_during_unlocked_validation_cannot_clear(self):
        self.arm(1)
        rendered=self.make_valid_report(self.evidence)
        original=guard.check_final
        def concurrently_changed(state,message):
            self.assertTrue(original(state,message))
            self.assertFalse(self.denied(self.tool('concurrent-new-work')))
            return True
        with patch.dict(os.environ,self.env),patch.object(guard,'check_final',side_effect=concurrently_changed):
            result=guard.handle({'session_id':'parent','cwd':str(self.root),'hook_event_name':'Stop',
                'transcript_path':str(self.root/'parent.jsonl'),'last_assistant_message':rendered})
        self.assertEqual(result['decision'],'block')
        errors=json.loads((self.evidence/'guard-check.json').read_text())['errors']
        self.assertIn({'code':'scope_changed_during_validation'},errors)

    def test_validation_uses_frozen_files_and_rejects_live_manifest_replacement(self):
        self.arm(1)
        rendered=self.make_valid_report(self.evidence)
        original=guard.check_snapshot
        def replace_live(state,message,snapshot):
            self.assertNotEqual(Path(snapshot),self.evidence)
            (self.evidence/'claims.json').write_text('{}')
            ok,receipt=original(state,message,snapshot)
            self.assertTrue(ok,receipt)
            return ok,receipt
        with patch.dict(os.environ,self.env),patch.object(guard,'check_snapshot',side_effect=replace_live):
            result=guard.handle({'session_id':'parent','cwd':str(self.root),'hook_event_name':'Stop',
                'transcript_path':str(self.root/'parent.jsonl'),'last_assistant_message':rendered})
        self.assertEqual(result['decision'],'block')
        errors=json.loads((self.evidence/'guard-check.json').read_text())['errors']
        self.assertIn({'code':'evidence_changed_during_validation'},errors)

    def test_more_than_500_free_callbacks_do_not_block_an_approved_stage(self):
        self.arm(0)
        with patch.dict(os.environ,self.env):
            for i in range(505):
                result=guard.handle({'session_id':'parent','cwd':str(self.root),'hook_event_name':'PreToolUse',
                    'transcript_path':str(self.root/'parent.jsonl'),'tool_name':'functions.exec',
                    'tool_use_id':f'wrapper-{i}','tool_input':{'code':'await tools.search()'}})
                self.assertFalse(self.denied(result))
        # Retained audit history must not impose a second hidden allowance.
        # Synthetic historical receipts isolate this capacity boundary cheaply.
        with closing(sqlite3.connect(self.root/'data/research-guard.sqlite3')) as db:
            state=json.loads(db.execute('SELECT state FROM runs').fetchone()[0])
            state['controls']={f'previous-{i}':{'sha256':'0'*64,'result':{}} for i in range(1000)}
            db.execute('UPDATE runs SET state=?',(json.dumps(state),));db.commit()
        self.control('request',[self.request()])
        self.control('approve',[self.decision()])
        self.assertFalse(self.denied(self.tool('approved-retrieval')))
        self.assertFalse(self.denied(self.tool('approved-retrieval')))
        self.assertFalse(self.denied(self.tool('second-retrieval')))
        self.assertFalse(self.denied(self.control('finish-after-large-audit',[{
            'op':'finish','outcome':'answered','reason':'Specific evidence is sufficient.','claim_id':'scope'}])))
        self.assertTrue(self.denied(self.tool('third-retrieval')))


# Only the new extension contracts belong to this class's suite.
for _name in list(vars(baseline.ResearchGuardTests)):
    if _name.startswith('test_'):
        setattr(SearchExtensionTests,_name,None)

if __name__=='__main__':unittest.main()
