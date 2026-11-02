#!/usr/bin/env python3
"""Check local citation records and bound review attestations, without network/LLM calls.

Hashes establish consistency, not source authenticity. Quote presence does not
establish entailment. Reviewer identities and judgements are recorded, not authenticated.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


MAX_BYTES = 20 * 1024 * 1024
ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
MARKER = re.compile(r'\[\[claim:([A-Za-z][A-Za-z0-9_.-]{0,63})\]\]')
ROLES = {'aggregator', 'seller', 'primary', 'secondary', 'other'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path):
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('File missing, not regular, or larger than 20 MiB')
    return path.read_bytes()


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON key: ' + key)
        obj[key] = value
    return obj


def parse_json(data):
    def invalid_constant(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def fields(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= obj.keys() or obj.keys() - set(required) - set(optional):
        raise ValueError('Missing, unknown, or invalid object fields')


def string(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Expected a non-empty string')
    return value


def identifier(value):
    if not ID.fullmatch(string(value)):
        raise ValueError('Invalid identifier')
    return value


def fingerprint(value):
    if not SHA.fullmatch(string(value)):
        raise ValueError('Expected a lowercase SHA-256 fingerprint')
    return value


def timestamp(value):
    parsed = datetime.fromisoformat(string(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Observation time requires a UTC offset')
    return parsed


def locator(value):
    value = string(value)
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Locator contains whitespace or control characters')
    parsed = urlsplit(value)
    if parsed.scheme in {'http', 'https'}:
        parsed.port  # Raises ValueError for malformed/out-of-range ports.
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError('Invalid web locator or embedded credentials')
    elif not value.startswith(('local:', 'attachment:')) or not value.split(':', 1)[1]:
        raise ValueError('Use an exact HTTP(S), local:, or attachment: locator')
    return value


def local_path(root, value):
    value = string(value)
    relative = Path(value)
    if relative.is_absolute() or '\\' in value or '..' in relative.parts:
        raise ValueError('Evidence paths must stay relative to the manifest directory')
    resolved = (root / relative).resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError('Path or symbolic link escapes the evidence directory')
    return resolved


def indexed(items):
    if not isinstance(items, list):
        raise ValueError('Expected a list')
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Expected object entries')
        key = identifier(item.get('id'))
        if key in result:
            raise ValueError('Duplicate identifier: ' + key)
        result[key] = item
    return result


def merge_locator(first, second):
    if first and second and first != second:
        raise ValueError('One MCP artifact contains conflicting source locators')
    return first or second


def mcp_piece(text, depth):
    if depth > 6:
        raise ValueError('Unsupported MCP nesting depth')
    try:
        nested = parse_json(text)
    except json.JSONDecodeError as exc:
        if text.lstrip().startswith(('{', '[')):
            raise ValueError('Malformed serialized MCP object or array') from exc
        return text, None, False
    if isinstance(nested, dict):
        return mcp_text(nested, depth)
    if isinstance(nested, list):
        return '', None, False  # Not a supported single-source text envelope.
    if isinstance(nested, str):
        return mcp_piece(nested, depth + 1)
    return text, None, False


def mcp_text(obj, depth=0):
    """Extract only documented text/result fields, never JSON metadata as evidence."""
    if depth > 6 or not isinstance(obj, dict):
        raise ValueError('Unsupported MCP text envelope')
    failed = obj.get('isError', False)
    if not isinstance(failed, bool):
        raise ValueError('Invalid MCP isError flag')
    status = obj.get('status')
    if status is not None:
        if type(status) is not int:
            raise ValueError('Expected an integer HTTP status in this envelope')
        failed = failed or not 200 <= status < 300
    observed_locator = obj.get('url')
    if observed_locator is not None:
        locator(observed_locator)
    pieces = []

    def include(piece):
        nonlocal observed_locator, failed
        text, resolved, inner_failed = piece
        observed_locator = merge_locator(observed_locator, resolved)
        failed = failed or inner_failed
        pieces.append(text)

    structured = obj.get('structuredContent')
    if structured is not None:
        if not isinstance(structured, dict):
            raise ValueError('Unsupported structured MCP content')
        include(mcp_text(structured, depth + 1))
    if obj.get('result') is not None:
        if not isinstance(obj['result'], str):
            raise ValueError('Unsupported MCP result field')
        include(mcp_piece(obj['result'], depth + 1))
    content = obj.get('content')
    if content is not None and not isinstance(content, list):
        raise ValueError('MCP response contains no supported text field')
    for block in content or []:
        if isinstance(block, str):
            text = block
        elif isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str):
            text = block['text']
        else:
            continue
        include(mcp_piece(text, depth + 1))
    return '\n'.join(pieces), observed_locator, failed


def substantive(text):
    without_urls = re.sub(r'https?://[^\s<>]+', '', text)
    return any(c.isalnum() for c in without_urls)


def validate(manifest_path, review_path=None, *, now=None):
    errors = []
    result = {'ok': False, 'validation_scope': 'local_records_and_review_attestations',
              'semantic_verification': 'not_performed', 'errors': errors,
              'limits': ['Artifacts, source metadata and reviewer identities are not authenticated.',
                         'Quote presence does not prove meaning, complete coverage or live availability.']}

    def issue(code, location):
        errors.append({'code': code, 'location': location})

    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    now = now or datetime.now(timezone.utc)
    try:
        raw = read_bytes(manifest_path)
        data = parse_json(raw)
        fields(data, {'schema_version', 'producer_id', 'report', 'sources', 'claims'})
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('Unsupported manifest version')
        producer = identifier(data['producer_id'])
        fields(data['report'], {'path', 'sha256'})
        fingerprint(data['report']['sha256'])
        sources = indexed(data['sources'])
        claims = indexed(data['claims'])
        if not claims:
            raise ValueError('Register at least one claim')
        for source in sources.values():
            fields(source, {'id', 'locator', 'origin', 'role', 'observed_at', 'retrieval_status',
                            'content_kind', 'format', 'artifact', 'sha256'})
            locator(source['locator'])
            fingerprint(source['sha256'])
            timestamp(source['observed_at'])
            if (source['origin'] not in {'retrieved', 'observed', 'constructed', 'unknown'} or
                    source['role'] not in ROLES or source['retrieval_status'] not in {'recovered', 'empty', 'failed'} or
                    source['content_kind'] not in {'body', 'rendered_text', 'local_text', 'metadata'} or
                    source['format'] not in {'plain_text', 'mcp_json'}):
                raise ValueError('Invalid source enum')
        for claim in claims.values():
            fields(claim, {'id', 'text', 'status', 'citations'}, {'as_of', 'freshness_hours'})
            if '\n' in string(claim['text']) or '\r' in claim['text'] or MARKER.search(claim['text']):
                raise ValueError('Claim text must occupy one marked line')
            if claim['status'] not in {'supported', 'historical', 'inference', 'unverified'}:
                raise ValueError('Invalid claim status')
            if not isinstance(claim['citations'], list):
                raise ValueError('Invalid citations')
            if 'as_of' in claim:
                date.fromisoformat(claim['as_of'])
            if 'freshness_hours' in claim:
                age = claim['freshness_hours']
                if type(age) not in (int, float) or not math.isfinite(age) or age <= 0:
                    raise ValueError('freshness_hours must be positive and finite')
            for citation in claim['citations']:
                fields(citation, {'source_id', 'locator', 'quote', 'expected_role'})
                identifier(citation['source_id'])
                locator(citation['locator'])
                if not isinstance(citation['quote'], str) or citation['expected_role'] not in ROLES | {'any'}:
                    raise ValueError('Invalid citation fields')
    except (ValueError, TypeError, OSError, UnicodeError, OverflowError):
        issue('invalid_manifest', 'manifest')
        return result
    result.update(manifest_sha256=sha256(raw), claim_count=len(claims))
    try:
        report_raw = read_bytes(local_path(root, data['report']['path']))
        report = report_raw.decode('utf-8')
    except (ValueError, OSError, UnicodeError):
        issue('report_unreadable', 'report')
        return result
    report_sha = sha256(report_raw)
    result['report_sha256'] = report_sha
    if report_sha != data['report']['sha256']:
        issue('report_hash_mismatch', 'report')
    marked = {}
    for line in report.splitlines():
        matches = list(MARKER.finditer(line))
        if '[[claim:' not in line:
            continue
        if len(matches) != 1 or not line.startswith(matches[0].group(0) + ' '):
            issue('report_claim_mismatch', 'report')
            continue
        key = matches[0].group(1)
        if key in marked:
            issue('report_claim_mismatch', key)
        marked[key] = line[len(matches[0].group(0)) + 1:]
    if set(marked) != set(claims) or any(marked.get(k) != c['text'] for k, c in claims.items()):
        issue('report_claim_mismatch', 'report')

    recovered = {}
    for key, source in sources.items():
        try:
            artifact = read_bytes(local_path(root, source['artifact']))
            text = artifact.decode('utf-8')
            if sha256(artifact) != source['sha256']:
                issue('artifact_hash_mismatch', key)
            failed = False
            resolved = None
            if source['format'] == 'mcp_json':
                text, resolved, failed = mcp_text(parse_json(text))
            usable = (source['retrieval_status'] == 'recovered' and source['content_kind'] != 'metadata'
                      and not failed and substantive(text))
            recovered[key] = (text, usable)
            if usable and resolved and resolved != source['locator']:
                issue('artifact_locator_mismatch', key)
            if timestamp(source['observed_at']) > now:
                issue('source_time_in_future', key)
        except (ValueError, TypeError, OSError, UnicodeError, OverflowError):
            issue('artifact_unreadable', key)

    for key, claim in claims.items():
        status = claim['status']
        if status in {'unverified', 'inference'}:
            label = 'Unverified:' if status == 'unverified' else 'Inference:'
            if not claim['text'].startswith(label):
                issue('qualification_missing', key)
        if status == 'historical' and (not claim.get('as_of') or claim['as_of'] not in claim['text']):
            issue('historical_date_missing', key)
        if status != 'unverified' and not claim['citations']:
            issue('citation_required', key)
        for citation in claim['citations']:
            source_id = citation['source_id']
            source = sources.get(source_id)
            if source is None:
                issue('unknown_source', key)
                continue
            if citation['locator'] != source['locator']:
                issue('citation_locator_mismatch', key)
            if citation['expected_role'] not in {'any', source['role']}:
                issue('source_role_mismatch', key)
            if status == 'unverified':
                continue
            if source['origin'] == 'unknown':
                issue('source_origin_unknown', key)
            text, usable = recovered.get(source_id, ('', False))
            if not usable:
                issue('source_content_unavailable', key)
            if not citation['quote'].strip() or citation['quote'] not in text:
                issue('quote_not_found', key)
            if 'freshness_hours' in claim:
                age_hours = (now - timestamp(source['observed_at'])).total_seconds() / 3600
                if age_hours > claim['freshness_hours']:
                    issue('source_too_old', key)

    result['mechanical_ok'] = not errors
    if review_path is None:
        issue('review_required', 'review')
    else:
        try:
            review = parse_json(read_bytes(Path(review_path)))
            fields(review, {'schema_version', 'reviewer_id', 'manifest_sha256', 'report_sha256',
                            'coverage_complete', 'claims'})
            if type(review['schema_version']) is not int or review['schema_version'] != 1:
                raise ValueError('Invalid review version')
            reviewer = identifier(review['reviewer_id'])
            fingerprint(review['manifest_sha256'])
            fingerprint(review['report_sha256'])
            if reviewer == producer:
                issue('review_not_independent', 'review')
            if review['manifest_sha256'] != sha256(raw):
                issue('review_manifest_mismatch', 'review')
            if review['report_sha256'] != report_sha:
                issue('review_report_mismatch', 'review')
            if review['coverage_complete'] is not True:
                issue('review_coverage_incomplete', 'review')
            decisions = indexed(review['claims'])
            if set(decisions) != set(claims):
                issue('review_claim_coverage', 'review')
            for key, decision in decisions.items():
                fields(decision, {'id', 'verdict', 'reason'})
                string(decision['reason'])
                expected = 'appropriately_qualified' if claims.get(key, {}).get('status') == 'unverified' else 'supported'
                if decision['verdict'] != expected:
                    issue('review_not_cleared', key)
        except (ValueError, TypeError, OSError, UnicodeError):
            issue('invalid_review', 'review')
    result['ok'] = not errors
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('check', 'render', 'review-template'):
        child = sub.add_parser(command)
        child.add_argument('manifest', type=Path)
        if command != 'review-template':
            child.add_argument('--review', type=Path)
    child = sub.add_parser('fingerprint')
    child.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'fingerprint':
            print(sha256(read_bytes(args.path)))
            return 0
        result = validate(args.manifest, getattr(args, 'review', None))
        if args.command == 'review-template':
            if not result.get('mechanical_ok'):
                print(json.dumps(result, indent=2), file=sys.stderr)
                return 1
            data = parse_json(read_bytes(args.manifest))
            template = {'schema_version': 1, 'reviewer_id': '', 'manifest_sha256': result['manifest_sha256'],
                        'report_sha256': result['report_sha256'], 'coverage_complete': False,
                        'claims': [{'id': c['id'], 'verdict': 'pending', 'reason': ''} for c in data['claims']]}
            print(json.dumps(template, ensure_ascii=False, indent=2))
        elif args.command == 'render':
            if not result['ok']:
                print(json.dumps(result, indent=2), file=sys.stderr)
                return 1
            data = parse_json(read_bytes(args.manifest))
            report = read_bytes(local_path(args.manifest.resolve().parent, data['report']['path'])).decode('utf-8')
            if sha256(report.encode('utf-8')) != result['report_sha256']:
                raise ValueError('Report changed while rendering')
            print(re.sub('^' + MARKER.pattern + ' ', '', report, flags=re.MULTILINE), end='')
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command == 'review-template' or result['ok'] else 1
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        print(json.dumps({'ok': False, 'errors': [{'code': 'input_error', 'detail': str(exc)}]}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
