"""Offline behavioural regressions for the bundled claim/source gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/deep-research-circuit/scripts/validate_claims.py'
FIXTURES = Path(__file__).parent / 'fixtures'
CATALOG = 'https://catalog.example/search/ITEM-42'
SELLER = 'https://seller.example/products/ITEM-42'
NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClaimValidatorTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Claim validator not implemented yet')
        spec = importlib.util.spec_from_file_location('claim_validator', SCRIPT)
        self.validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.validator)
        self.folder = tempfile.TemporaryDirectory(prefix='claim-validator-')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.report = self.root / 'report.md'
        self.artifact = self.root / 'catalog.txt'
        shutil.copyfile(FIXTURES / 'catalog-capture.txt', self.artifact)
        self.claim_text = 'On 2026-01-15, Sample Catalog displayed $10.00 for Widget-42; delivery terms remained unverified.'
        self.report.write_text('Recorded comparison\n\n[[claim:price]] ' + self.claim_text + '\n')
        self.manifest = {
            'schema_version': 1, 'producer_id': 'researcher-1',
            'report': {'path': 'report.md', 'sha256': digest(self.report)},
            'sources': [{'id': 'catalog', 'locator': CATALOG, 'origin': 'observed',
                         'role': 'aggregator', 'observed_at': '2026-01-15T19:31:44+11:00',
                         'retrieval_status': 'recovered', 'content_kind': 'rendered_text',
                         'format': 'plain_text', 'artifact': 'catalog.txt', 'sha256': digest(self.artifact)}],
            'claims': [{'id': 'price', 'text': self.claim_text, 'status': 'historical',
                        'as_of': '2026-01-15', 'citations': [{'source_id': 'catalog', 'locator': CATALOG,
                            'quote': '$10.00', 'expected_role': 'aggregator'}]}],
        }
        self.manifest_path = self.root / 'claims.json'
        self.review_path = self.root / 'review.json'

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2))

    def approve(self):
        self.write_manifest()
        review = {'schema_version': 1, 'reviewer_id': 'synthetic-test-reviewer',
                  'manifest_sha256': digest(self.manifest_path), 'report_sha256': digest(self.report),
                  'coverage_complete': True,
                  'claims': [{'id': c['id'], 'verdict': 'appropriately_qualified' if c['status'] == 'unverified' else 'supported',
                              'reason': 'Synthetic test fixture only; no independent semantic review occurred.'}
                             for c in self.manifest['claims']]}
        self.review_path.write_text(json.dumps(review))
        return review

    def result(self):
        return self.validator.validate(self.manifest_path, self.review_path, now=NOW)

    def assert_blocked(self, code):
        result = self.result()
        self.assertFalse(result['ok'], result)
        self.assertIn(code, [e['code'] for e in result['errors']], result)

    def test_catalog_snapshot_supports_historical_display(self):
        self.approve()
        result = self.result()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['semantic_verification'], 'not_performed')

    def test_empty_seller_responses_cannot_support_seller_quote(self):
        for fixture in ['empty-seller-crawl.json', 'empty-seller-browser.json']:
            with self.subTest(fixture=fixture):
                shutil.copyfile(FIXTURES / fixture, self.root / 'seller.json')
                source = self.manifest['sources'][0]
                source.update(locator=SELLER, role='seller', origin='constructed', format='mcp_json',
                              artifact='seller.json', sha256=digest(self.root / 'seller.json'))
                self.manifest['claims'][0]['citations'][0].update(locator=SELLER, expected_role='seller')
                self.approve()
                self.assert_blocked('source_content_unavailable')

    def test_false_quote_and_false_citation_locator_are_blocked(self):
        self.manifest['claims'][0]['citations'][0]['quote'] = 'Includes free delivery on every order'
        self.approve()
        self.assert_blocked('quote_not_found')
        self.manifest['claims'][0]['citations'][0].update(quote='$10.00', locator=SELLER)
        self.approve()
        self.assert_blocked('citation_locator_mismatch')

    def test_catalog_display_cannot_be_relabelled_as_seller_evidence(self):
        self.manifest['claims'][0]['citations'][0]['expected_role'] = 'seller'
        self.approve()
        self.assert_blocked('source_role_mismatch')

    def test_unknown_source_and_unknown_origin_are_blocked(self):
        self.manifest['claims'][0]['citations'][0]['source_id'] = 'invented-doi'
        self.approve()
        self.assert_blocked('unknown_source')
        self.manifest['claims'][0]['citations'][0]['source_id'] = 'catalog'
        self.manifest['sources'][0]['origin'] = 'unknown'
        self.approve()
        self.assert_blocked('source_origin_unknown')

    def test_body_edit_is_detected_even_if_quote_still_exists(self):
        self.approve()
        self.artifact.write_text(self.artifact.read_text() + '\nInvented extra facts')
        self.assert_blocked('artifact_hash_mismatch')

    def test_changed_draft_or_manifest_invalidates_review(self):
        self.approve()
        self.report.write_text(self.report.read_text() + '\nNew conclusion\n')
        self.assert_blocked('report_hash_mismatch')
        self.manifest['report']['sha256'] = digest(self.report)
        self.write_manifest()
        self.assert_blocked('review_manifest_mismatch')
        self.assert_blocked('review_report_mismatch')

    def test_metadata_url_only_and_error_body_cannot_support_claim(self):
        for text, kind, status in [('Sample Store', 'metadata', 'recovered'),
                                   ('# ' + CATALOG + '\n', 'body', 'recovered'),
                                   ('$10.00', 'body', 'failed')]:
            with self.subTest(text=text):
                self.artifact.write_text(text)
                self.manifest['sources'][0].update(sha256=digest(self.artifact), content_kind=kind, retrieval_status=status)
                self.approve()
                self.assert_blocked('source_content_unavailable')

    def test_missing_and_rejected_semantic_review_block_release(self):
        self.write_manifest()
        result = self.validator.validate(self.manifest_path, now=NOW)
        self.assertFalse(result['ok'])
        self.assertIn('review_required', [e['code'] for e in result['errors']])
        review = self.approve()
        review['claims'][0].update(verdict='unsupported', reason='The source does not establish the claimed scope.')
        self.review_path.write_text(json.dumps(review))
        self.assert_blocked('review_not_cleared')

    def test_missing_claim_review_same_producer_and_incomplete_coverage_block(self):
        for update, code in [({'claims': []}, 'review_claim_coverage'),
                             ({'reviewer_id': 'researcher-1'}, 'review_not_independent'),
                             ({'coverage_complete': False}, 'review_coverage_incomplete')]:
            review = self.approve()
            review.update(update)
            self.review_path.write_text(json.dumps(review))
            self.assert_blocked(code)

    def test_report_claim_markers_must_match_manifest_exactly(self):
        for report in ['[[claim:other]] ' + self.claim_text,
                       '[[claim:price]] ' + self.claim_text + '\n[[claim:price]] ' + self.claim_text,
                       '[[claim:price]] Sample Store confirmed free delivery.']:
            self.report.write_text(report + '\n')
            self.manifest['report']['sha256'] = digest(self.report)
            self.approve()
            self.assert_blocked('report_claim_mismatch')

    def test_unverified_lead_must_stay_visibly_qualified(self):
        claim = self.manifest['claims'][0]
        claim.update(status='unverified', citations=[])
        self.approve()
        self.assert_blocked('qualification_missing')
        claim['text'] = 'Unverified: delivery terms and seller price remain unknown.'
        self.report.write_text('[[claim:price]] ' + claim['text'] + '\n')
        self.manifest['report']['sha256'] = digest(self.report)
        self.approve()
        self.assertTrue(self.result()['ok'], self.result())

    def test_independent_seller_route_and_local_document_are_accepted(self):
        for locator, role, origin in [(SELLER, 'seller', 'constructed'),
                                      ('local:catalog-sheet.pdf#page=2', 'primary', 'observed')]:
            with self.subTest(locator=locator):
                self.artifact.write_text('Selected product: Widget-42. $10.00 before delivery.')
                self.manifest['sources'][0].update(locator=locator, role=role, origin=origin,
                        content_kind='local_text' if locator.startswith('local:') else 'rendered_text', sha256=digest(self.artifact))
                self.manifest['claims'][0]['citations'][0].update(locator=locator, expected_role=role)
                self.approve()
                self.assertTrue(self.result()['ok'], self.result())

    def test_historical_snapshot_survives_later_failed_attempt(self):
        self.manifest['sources'].append(dict(self.manifest['sources'][0], id='later',
                                            retrieval_status='failed', content_kind='metadata'))
        self.approve()
        self.assertTrue(self.result()['ok'], self.result())

    def test_requested_freshness_and_future_capture_are_checked(self):
        claim = self.manifest['claims'][0]
        claim.update(status='supported', freshness_hours=1)
        self.approve()
        self.assert_blocked('source_too_old')
        self.manifest['sources'][0]['observed_at'] = '2027-01-01T00:00:00+11:00'
        self.approve()
        self.assert_blocked('source_time_in_future')

    def test_malformed_json_duplicate_ids_and_path_escape_fail_closed(self):
        self.manifest_path.write_text('{"schema_version":1,"schema_version":2}')
        self.assert_blocked('invalid_manifest')
        self.manifest['sources'].append(dict(self.manifest['sources'][0]))
        self.approve()
        self.assert_blocked('invalid_manifest')
        self.manifest['sources'].pop()
        self.manifest['sources'][0]['artifact'] = '../outside.txt'
        self.approve()
        self.assert_blocked('artifact_unreadable')

    def test_cli_check_and_render_use_the_actual_gate(self):
        self.approve()
        checked = subprocess.run([sys.executable, str(SCRIPT), 'check', str(self.manifest_path),
                                  '--review', str(self.review_path)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertTrue(json.loads(checked.stdout)['ok'])
        rendered = subprocess.run([sys.executable, str(SCRIPT), 'render', str(self.manifest_path),
                                   '--review', str(self.review_path)], capture_output=True, text=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertIn(self.claim_text, rendered.stdout)
        self.assertNotIn('[[claim:', rendered.stdout)
        self.review_path.unlink()
        blocked = subprocess.run([sys.executable, str(SCRIPT), 'render', str(self.manifest_path)],
                                 capture_output=True, text=True)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(blocked.stdout, '')

    def test_review_template_is_bound_but_not_preapproved(self):
        self.write_manifest()
        run = subprocess.run([sys.executable, str(SCRIPT), 'review-template', str(self.manifest_path)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        template = json.loads(run.stdout)
        self.assertEqual(template['manifest_sha256'], digest(self.manifest_path))
        self.assertEqual(template['report_sha256'], digest(self.report))
        self.assertFalse(template['coverage_complete'])
        self.assertEqual(template['claims'][0]['verdict'], 'pending')

    def mcp_artifact(self, payload):
        self.artifact.write_text(json.dumps(payload))
        self.manifest['sources'][0].update(format='mcp_json', sha256=digest(self.artifact))

    def test_nested_metadata_json_cannot_become_body_evidence(self):
        metadata = json.dumps({'title': '$10.00', 'url': CATALOG})
        for payload in [{'content': [{'type': 'text', 'text': metadata}]},
                        {'content': [metadata]}, {'result': metadata},
                        {'structuredContent': {'result': metadata}}]:
            with self.subTest(payload=payload):
                self.mcp_artifact(payload)
                self.approve()
                self.assert_blocked('source_content_unavailable')

    def test_mcp_blocks_cannot_mix_quote_and_identity_from_different_sources(self):
        for payload in [
                {'content': [json.dumps({'url': SELLER, 'content': ['Seller response contained no price details.']}),
                             json.dumps({'url': CATALOG, 'content': ['$10.00']})]},
                {'url': SELLER, 'structuredContent': {'url': CATALOG, 'content': ['$10.00']}}]:
            with self.subTest(payload=payload):
                self.mcp_artifact(payload)
                self.approve()
                self.assert_blocked('artifact_unreadable')

    def test_render_preserves_every_unmarked_space(self):
        self.report.write_text('  Intro\n[[claim:price]] ' + self.claim_text + '\n\n    code = 1\n  continuation\n')
        self.manifest['report']['sha256'] = digest(self.report)
        self.approve()
        run = subprocess.run([sys.executable, str(SCRIPT), 'render', str(self.manifest_path),
                              '--review', str(self.review_path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, '  Intro\n' + self.claim_text + '\n\n    code = 1\n  continuation\n')

    def test_invalid_http_port_is_rejected(self):
        invalid = 'https://catalog.example:wrong/search/ITEM-42'
        self.manifest['sources'][0]['locator'] = invalid
        self.manifest['claims'][0]['citations'][0]['locator'] = invalid
        self.approve()
        self.assert_blocked('invalid_manifest')

    def test_malformed_nested_json_is_not_promoted_to_evidence(self):
        for text in ['{"url":"' + CATALOG + '","url":"' + SELLER + '","content":["$10.00"]}',
                     '{"title":"$10.00","title":"$10.00"}',
                     '{"title":"$10.00",}',
                     '{"content":["$10.00"],"status":NaN}']:
            with self.subTest(text=text):
                self.mcp_artifact({'content': [{'type': 'text', 'text': text}]})
                self.approve()
                self.assert_blocked('artifact_unreadable')

    def test_sibling_mcp_channels_cannot_hide_source_conflict_or_error(self):
        for sibling, code in [({'url': SELLER, 'content': ['Seller inaccessible']}, 'artifact_unreadable'),
                              ({'url': CATALOG, 'isError': True, 'content': ['$10.00']}, 'source_content_unavailable')]:
            with self.subTest(sibling=sibling):
                self.mcp_artifact({'structuredContent': {'url': CATALOG, 'content': ['$10.00']},
                                  'content': [{'type': 'text', 'text': json.dumps(sibling)}]})
                self.approve()
                self.assert_blocked(code)

    def test_consistent_mcp_siblings_and_ordinary_text_remain_usable(self):
        self.mcp_artifact({'structuredContent': {'url': CATALOG, 'content': ['$10.00']},
                          'content': [{'type': 'text', 'text': 'Widget-42 lists $10.00; delivery is extra.'}]})
        self.approve()
        self.assertTrue(self.result()['ok'], self.result())

    def test_json_string_wrapping_cannot_hide_metadata_or_source_conflict(self):
        for obj in [{'title': '$10.00', 'url': CATALOG},
                    {'url': SELLER, 'content': ['$10.00']}]:
            with self.subTest(obj=obj):
                self.mcp_artifact({'url': CATALOG, 'content': [json.dumps(json.dumps(obj))]})
                self.approve()
                self.assertFalse(self.result()['ok'], self.result())
        self.mcp_artifact({'url': CATALOG, 'content': [json.dumps('Widget-42 is listed for $10.00.')]})
        self.approve()
        self.assertTrue(self.result()['ok'], self.result())


if __name__ == '__main__':
    unittest.main()
