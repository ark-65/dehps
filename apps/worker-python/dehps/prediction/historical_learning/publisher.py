"""Readonly audited source export and independent registered-report bridge."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from dehps.execution.release import canonical
from dehps.prediction.forward_learning.publisher import append_bytes, audited_source, signed
from dehps.prediction.frozen_p3.calculation import validate_artifact
from dehps.prediction.frozen_p3.report import validate_notification_artifact
from .contract import Inputs, POLICY, digest, instant, require


def archive(root, data):
    identity = sha256(data).hexdigest()
    append_bytes(root/'sources'/identity, data)
    return identity


def source_references(connection, source_root, label, output):
    """Require a registered machine artifact, legal content digest and issue.

    The source connection is already in an audited read-only transaction. Never
    treat a Markdown path, a mail ledger or a successful process as registration.
    """
    issue = label['issue']
    types = ['M4P3ForwardPrequentialCheckpoint', 'M4P3ForwardPrequentialModelCandidateSet',
        'M4P3ForwardPrequentialModel', 'M4P3ForwardPrequentialPreDrawReport',
        'M4P3ForwardPrequentialSettlement', 'P3Top100PostReturnReportV1']
    rows = connection.execute('''SELECT artifact_digest, artifact_type, artifact_path, created_at, registration_json
        FROM research_os_mainline_artifacts WHERE artifact_type = ANY(%s)
          AND task_key LIKE %s ORDER BY created_at, artifact_digest''', (types, '%'+issue+'%')).fetchall()
    verified = []
    for artifact_digest, kind, relative, created_at, registration in rows:
        path = source_root/relative
        require(path.is_relative_to(source_root) and path.resolve() == path, 'source artifact path escaped root')
        data = path.read_bytes(); value = json.loads(data)
        if kind.startswith('P3Top100'):
            validate_notification_artifact(value)
        else:
            validate_artifact(value)
        require(value['artifact_digest'] == artifact_digest and value['artifact_type'] == kind,
                'registered source digest differs')
        body = value['body']
        require(body.get('target_issue', body.get('issue')) == issue, 'registered source issue differs')
        verified.append((kind, relative, created_at, value, data, registration))
    checkpoints = [v for kind, _, registered, v, _, _ in verified if kind.endswith('Checkpoint')
        and registered < instant(label['draw_at'])
        and instant(v['body']['sealed_at']) < instant(label['draw_at'])]
    original_digests = set()
    if issue != '2026104':
        for checkpoint in checkpoints:
            original_digests.add(checkpoint['artifact_digest'])
            original_digests.update(checkpoint['parent_digests'])
        for kind, _, registered, v, _, _ in verified:
            if kind.endswith('PreDrawReport') and registered < instant(label['draw_at']) and v['body']['checkpoint_digest'] in original_digests:
                original_digests.add(v['artifact_digest'])
    references = []
    for kind, relative, _, value, data, registration in verified:
        post = kind in {'M4P3ForwardPrequentialSettlement', 'P3Top100PostReturnReportV1'}
        if not post and value['artifact_digest'] not in original_digests:
            continue
        if kind.endswith('Settlement'):
            require(value['body']['actual_red_numbers'] == label['red'] and value['body']['actual_blue_number'] == label['blue'],
                    'registered settlement label conflicts')
        identity = archive(output, data)
        archive(output, canonical({'source': relative, 'registration': registration}))
        references.append({'kind': 'POST_DRAW_REPORT' if post else 'ORIGINAL_PREDICTION',
            'sha256': identity, 'source': relative, 'model': 'retained-formal-P3', 'issue': issue})
    # Duplicate canonical registrations of identical bytes remain one reference.
    return list({digest(r): r for r in references}.values())


def publish_dispatch(inputs, key, *, approved_until, reason):
    body = {'contract_sha256': inputs.contract_sha256, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'approved_until': approved_until, 'reason': reason}
    # Only this reconstructible signed readiness projection is replaceable.
    # Labels, source receipts, errors, checkpoints and reports use append_bytes.
    fd, temporary = tempfile.mkstemp(prefix='.dispatch-', dir=inputs.root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(signed(body, key, inputs.contract['export_public_key']))
            os.fchmod(stream.fileno(), 0o640); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, inputs.root/'dispatch.json')
        fd = os.open(inputs.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish_inputs(inputs, rows, receipt, key, *, approved_until, references):
    require(datetime.now(timezone.utc) < instant(approved_until), 'publisher authorization expired')
    by_issue = {r['issue']: r for r in rows}
    require(len(by_issue) == len(rows) and list(by_issue) == sorted(by_issue), 'source issue order differs')
    previous = inputs.history[-1]
    # Validate the ENTIRE consumed prefix on every poll; corrections never slide
    # past an already learned issue and silently contaminate its successors.
    consumed = list(inputs.history)
    index = len(consumed)
    while index < len(inputs.history)+POLICY['incremental_slots']:
        record = inputs.record(index)
        if record is None:
            break
        consumed.append(record); previous = record; index += 1
    for record in consumed:
        row = by_issue.get(record['label']['issue'])
        require(row is not None and all(row[k] == record['label'][k] for k in ('issue', 'draw_at', 'red', 'blue')),
                'source correction conflicts with consumed input')
    published = []
    for row in rows:
        if row['issue'] <= previous['label']['issue']:
            continue
        if index >= len(inputs.history)+POLICY['incremental_slots']:
            break
        refs = references(row)
        if not any(r['kind'] == 'POST_DRAW_REPORT' for r in refs):
            break  # wait for the first missing report, never skip an issue
        require(datetime.now(timezone.utc) < instant(approved_until), 'publisher authorization expired')
        record = {'label': row, 'references': refs}
        append_bytes(inputs.root/'receipts'/f'{digest(receipt)}.json', canonical(receipt))
        inputs.validate_record(record)
        body = {'contract_sha256': inputs.contract_sha256, 'index': index,
                'previous_sha256': digest(previous), 'record': record}
        append_bytes(inputs.root/'incremental'/f'{index:05d}.json', signed(body, key, inputs.contract['export_public_key']))
        previous = record; index += 1; published.append(row['issue'])
    return published


def publish_original_view(inputs, bundle):
    """Mirror already bound original bytes beside the reconstruction report.

    This is an audit view, not a new score, model update or completion fact.
    In particular an old arm named 'old_original' is still historical evidence.
    """
    if bundle['index'] == -1:
        return
    value = bundle['learn']['scientific']
    record = inputs.record(bundle['index'])
    require(record is not None and bundle['contract_sha256'] == inputs.contract_sha256
            and value['input_sha256'] == digest(record) and value['issue'] == record['label']['issue']
            and value['original_references'] == record['references']
            and digest(bundle['learn']) == bundle['learn_sha256']
            and digest(bundle['report']) == bundle['report_sha256'], 'original audit view binding differs')
    issue = value['issue']
    lines = [f'# 第 {issue} 期原始归档结果', '', 'ORIGINAL_ARCHIVED_EVIDENCE',
        f"原始开奖前预测状态：{value['original_prediction_status']}。",
        'HISTORICAL_EVALUATION 是此前历史评估，不能当作开奖前封存。',
        f"对应注册重建报告摘要：{bundle['report_sha256']}。", '',
        f'[本次历史重建报告](../../{issue}.md)', '']
    for reference in value['original_references']:
        data = inputs.blob(reference['sha256'])
        filename = reference['kind']+'-'+reference['sha256']+'.json'
        append_bytes(inputs.root/'reports/original'/issue/filename, data)
        original = json.loads(data); body = original.get('body', {})
        lines += [f"## {reference['kind']} · {reference['model']}",
            f"[完整原始机器产物与候选排名]({filename})", f"来源：{reference['source']}"]
        if original.get('artifact_type') == 'PredictionLearningIssue':
            lines += ['原始归档 log-loss：', '```json', json.dumps(body['log_loss_nats_per_number'], ensure_ascii=False, sort_keys=True), '```']
            for arm, result in body['arms'].items():
                lines += [f'### 归档分支 {arm}', f"首次遗漏：{result['first_rejection']}；全空间排名：{result['full_space_score_rank']}；"
                          f"原候选池排名：{result.get('local_pool_score_rank')}。",
                          '| 原顺序 | 原 lex_id | 原蓝球 |', '| ---: | ---: | ---: |']
                lines += [f'| {rank+1} | {identity} | {blue} |' for rank, (identity, blue) in
                          enumerate(zip(result['ticket_ids'], result['blue_by_rank'], strict=True))]
        elif original.get('artifact_type') == 'M4P3ForwardPrequentialModelCandidateSet':
            lines += ['| 原排名 | 红球 | 蓝球 | 原评分 |', '| ---: | --- | ---: | ---: |']
            lines += [f"| {t['rank']} | {t['red_numbers']} | {t['blue_number']} | {t['model_log2_score']} |" for t in body['tickets']]
        elif original.get('artifact_type') == 'M4P3ForwardPrequentialCheckpoint':
            lines += [f"原封存时间：{body['sealed_at']}；原训练截止期：{body['training_end_issue']}。"]
        elif original.get('artifact_type') == 'M4P3ForwardPrequentialSettlement':
            lines += [f"原模型 log2 score：{body['model_probability_log2_score']}；原均匀基线：{body['legal_uniform_log2_score']}。"]
    if not value['original_references']:
        lines.append('没有已核实原始机器报告；保留报告缺口。')
    append_bytes(inputs.root/'reports/original'/issue/'index.md', ('\n'.join(lines)+'\n').encode())


def publish_observations(inputs, learning_engine, key, *, approved_until):
    require(datetime.now(timezone.utc) < instant(approved_until), 'publisher authorization expired')
    published = []
    with learning_engine.store.verification_scope():
        manifest = learning_engine.replay(require_complete=False)
        producer_plan_digest = learning_engine.plan.digest
        by_index = {}
        for task in manifest.tasks:
            definition = json.loads(task.metric_contract)['historical']
            if definition['phase'] not in {'learn', 'report', 'summary'}:
                continue
            require(definition['contract_sha256'] == inputs.contract_sha256, 'producer historical contract differs')
            result = learning_engine.store.result(learning_engine.bindings[task.artifact_digest])
            if result:
                learning_engine.ledger.verify(result.task['id'])
                by_index.setdefault(definition['index'], {})[definition['phase']] = result
        for index, records in sorted(by_index.items()):
            require(datetime.now(timezone.utc) < instant(approved_until), 'publisher authorization expired')
            report = records.get('summary' if index == -1 else 'report')
            if report is None:
                continue
            learn = records.get('learn')
            require(index == -1 or learn is not None, 'report lost its committed learning parent')
            ledger = learning_engine.ledger.context(report.task['id'])
            body = {'contract_sha256': inputs.contract_sha256, 'index': index,
                'report': json.loads(report.data), 'learn': json.loads(learn.data) if learn else None,
                'report_sha256': report.artifact.sha256, 'learn_sha256': learn.artifact.sha256 if learn else None,
                'producer_committed_at': ledger['commit']['created_at'],
                'producer_execution_id': ledger['attempt']['authority_execution'],
                'producer_release_sha256': report.task['release_sha256'], 'producer_plan_digest': producer_plan_digest}
            path = inputs.root/'observations'/f'{index:05d}.json'
            existed = path.exists()
            append_bytes(path, signed(body, key, inputs.contract['export_public_key']))
            value = json.loads(report.data)['scientific']
            append_bytes(inputs.root/'reports'/('summary.md' if index == -1 else value['issue']+'.md'), value['text'].encode())
            publish_original_view(inputs, body)
            if not existed:
                published.append(index)
    return published
