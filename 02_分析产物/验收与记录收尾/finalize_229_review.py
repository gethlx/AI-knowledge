#!/usr/bin/env python3
"""校验明确逐对复核数据；不推断关系，不调用模型或改图。默认只检查，--write重建分流与材料。"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
ADJ = ROOT / '04_归档/图谱关系审计凭据/adjudications.jsonl'
EDGES = ROOT / '02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl'
GRAPH = ROOT / '03_交付物/G_v1_模型裁定版/graph.json'
REVIEW = BASE / '229对裁定结论复核证据-20261001.json'
OUT = BASE / '229对按最终裁定分流-20261002.json'
MATERIAL = BASE / '229对终审材料-20261002.txt'
RELATIONS = {'related', 'prerequisite', 'no_relation', 'insufficient_evidence'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build():
    evidence = json.loads(REVIEW.read_text())
    require(digest(ADJ.read_bytes()) == evidence['source_sha256'], '原始裁定已变化，须重新核对')
    original = {}
    for line, raw in enumerate(ADJ.read_text().splitlines(), 1):
        rec = json.loads(raw)
        require(rec['pair_id'] not in original, '原始裁定 pair_id 重复')
        original[rec['pair_id']] = (line, rec)
    expected = {pid for pid, (_, rec) in original.items()
                if rec['final_status'] == 'ACCEPTED_MODEL_ADJUDICATED' and 'adopted_relation' not in rec}
    reviews = evidence['records']
    ids = [rec['pair_id'] for rec in reviews]
    require(len(ids) == len(set(ids)), '复核数据重复')
    require(set(ids) == expected, '复核数据缺项或越界，不能默认归为 related')
    rows = [json.loads(raw) for raw in EDGES.read_text().splitlines()]
    published = {rec['pair_id'] for rec in rows}
    graph = json.loads(GRAPH.read_text())
    graph_ids = {rec['pair_id'] for rec in graph['edges']}
    require(len(published) == len(rows) and published == graph_ids, '边台账与当前图不一致')
    results = []
    material = ['229 对原始裁定结论复核材料（完整原文版）',
                f"复核日期：{evidence['reviewed_at']}；文件名保留既有日期便于引用。",
                '本文件是模型复核记录，不代表用户人工接受、候选图验证或正式图已恢复。',
                '关系取自明确逐对复核数据；包含证据原句和完整 rationale，不截断尾部。',
                f'原始凭据：{ADJ}', '']
    for reviewed in sorted(reviews, key=lambda rec: rec['pair_id']):
        pid = reviewed['pair_id']
        line, rec = original[pid]
        rat = rec['rationale']
        require(reviewed['source_line'] == line, f'{pid} 来源行号变化')
        require(reviewed['rationale_sha256'] == digest(rat.encode()), f'{pid} 原文变化')
        quote = reviewed['evidence_sentence']
        require(quote and quote in rat, f'{pid} 证据不是原文连续片段')
        require(reviewed['review_status'] == 'MODEL_REVIEWED', f'{pid} 尚未复核')
        rel, direction = reviewed['final_relation'], reviewed['direction']
        require(rel in RELATIONS, f'{pid} 关系未知')
        a, b = pid.split('__')
        effective_source = effective_target = direction_code = None
        if rel == 'prerequisite':
            require(isinstance(direction, str) and direction.count('→') == 1, f'{pid} 缺明确先修方向')
            effective_source, effective_target = direction.split('→')
            require({effective_source, effective_target} == {a, b}, f'{pid} 方向端点越界')
            compact = re.sub(r'\s+', '', rat)
            require(direction in compact or
                    (f'source={effective_source}' in compact and f'target={effective_target}' in compact),
                    f'{pid} 方向未见于原文')
            direction_code = 'source_to_target' if effective_source == a else 'target_to_source'
        else:
            require(direction is None, f'{pid} 非先修关系应使用 JSON null')
        in_graph = pid in published
        disposition = ('已入图无需动作' if in_graph else '应恢复入图') if rel in {
            'related', 'prerequisite'} else '合理排除'
        reason = {'related': '原裁定明确采纳相关关系', 'prerequisite': '原裁定明确采纳先修关系及方向',
                  'no_relation': '原裁定明确不建立关系',
                  'insufficient_evidence': '原裁定保留证据不足，暂不入图；不等于已证明无关系'}[rel]
        item = {'pair_id': pid, 'final_relation': rel, 'direction': direction,
                'source': f'adjudications.jsonl 行{line}', 'source_file': evidence['source_file'],
                'source_line': line, 'in_graph': in_graph, 'disposition': disposition,
                'disposition_reason': reason, 'evidence_sentence': quote,
                'rationale_sha256': reviewed['rationale_sha256'],
                'review_method': reviewed['review_method'], 'review_status': reviewed['review_status'],
                'adjudicator': rec['adjudicator'], 'adopted_by': rec.get('adopted_by'),
                'final_status': rec['final_status']}
        if rel == 'prerequisite':
            item.update(direction_code=direction_code, effective_source=effective_source,
                        effective_target=effective_target)
        results.append(item)
        material.extend([f'### {len(results):3d}/{len(reviews)} {pid} 行{line}',
                         f"复核关系={rel}；方向={direction or 'null'}；当前入图={in_graph}；处置={disposition}",
                         f'处置理由：{reason}', f'证据原文：{quote}', '原始 rationale 全文：', rat, ''])
    count = Counter(rec['final_relation'] for rec in results)
    restore = {rel: sum(rec['final_relation'] == rel and rec['disposition'] == '应恢复入图'
                       for rec in results) for rel in ('related', 'prerequisite')}
    payload = {'generated': evidence['reviewed_at'],
               'basis': '逐对核对原裁定结论并保留证据原句；弱证据及异常条目回读全文。仅恢复已有裁定含义，不重新裁定关系；不代表用户人工验收或正式图已恢复。85条历史解析回归不作为本次229条语义正确性的证明。',
               'source_sha256': evidence['source_sha256'], 'review_evidence': str(REVIEW.relative_to(ROOT)),
               'total': len(results),
               'stats': {'restore_related': restore['related'], 'restore_prerequisite': restore['prerequisite'],
                         'exclude_no_relation': count['no_relation'],
                         'exclude_insufficient_evidence': count['insufficient_evidence']},
               'prerequisite_edges': [{'pair_id': rec['pair_id'], 'direction': rec['direction']}
                                      for rec in results if rec['final_relation'] == 'prerequisite'],
               'records': results}
    return payload, '\n'.join(material) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='验证后重建分流JSON和完整材料')
    args = parser.parse_args()
    payload, material = build()
    if args.write:
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
        MATERIAL.write_text(material)
    else:
        require(json.loads(OUT.read_text()) == payload, '分流JSON与复核数据不一致')
        require(MATERIAL.read_text() == material, '复核材料与原文不一致')
    print(json.dumps({'total': payload['total'], 'stats': payload['stats'],
                      'evidence_and_source_checks': 'PASS', 'wrote': args.write}, ensure_ascii=False))


if __name__ == '__main__':
    main()
