#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读验收：复核发布物、节点内容、永久凭据与裁定入图覆盖；不调用模型或重建发布物。"""
import collections
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

def read_json(path):
    return json.loads((BASE / path).read_text())

def rows(path):
    return [json.loads(s) for s in (BASE / path).read_text().splitlines() if s.strip()]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    checks = {}
    original = BASE / '03_交付物/G_v1_模型裁定版'
    display = BASE / '03_交付物/G_v1_展示修正版'
    graph = json.loads((original / 'graph.json').read_text())
    nodes = {n['card_id']: n for n in graph['nodes']}
    edges = graph['edges']
    cards = {c['card_id']: c for c in rows('02_分析产物/p0_baseline/card_evidence.jsonl')}
    for label, folder in [('original', original), ('display', display)]:
        manifest = json.loads((folder / 'release_manifest.json').read_text())
        checks[label + '_hashes'] = all(sha(folder / name) == value for name, value in manifest['release']['artifact_hashes'].items())
    checks['frozen_data_unchanged'] = all((original / name).read_bytes() == (display / name).read_bytes() for name in ['graph.json', 'graph.graphml'])
    checks['nodes_match_cards'] = len(nodes) == len(cards) == 197 and nodes.keys() == cards.keys() and all(nodes[k]['canonical_name'] == cards[k]['canonical_name'] for k in nodes)
    required = ['认知层级', '精确定义', '常见误解', '典型案例', '反例', '深度上限', '安全与伦理边界', '来源依据']
    checks['node_required_fields_present'] = all(all(c['fields'].get(f) for f in required) for c in cards.values())
    counts = dict(collections.Counter(e['relation_type'] for e in edges))
    checks['graph_statistics'] = len(edges) == 1376 and counts == {'prerequisite': 75, 'related': 1301}
    checks['edge_identifiers_unique'] = len({e['pair_id'] for e in edges}) == len({e['edge_id'] for e in edges}) == len(edges)
    checks['endpoints_and_no_self_loops'] = all(e['effective_source'] in nodes and e['effective_target'] in nodes and e['effective_source'] != e['effective_target'] for e in edges)
    adj = collections.defaultdict(list)
    indegree = dict.fromkeys(nodes, 0)
    degree = collections.Counter()
    for e in edges:
        s, t = e['effective_source'], e['effective_target']
        degree.update([s, t])
        if e['relation_type'] == 'prerequisite':
            adj[s].append(t)
            indegree[t] += 1
    queue = collections.deque(n for n, d in indegree.items() if d == 0)
    seen = 0
    while queue:
        n = queue.popleft()
        seen += 1
        for t in adj[n]:
            indegree[t] -= 1
            if indegree[t] == 0:
                queue.append(t)
    checks['prerequisite_DAG'] = seen == len(nodes)
    ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
    tree = ET.parse(original / 'graph.graphml')
    ml = tree.findall('.//g:edge', ns)
    def signature(e):
        return (e['edge_id'], e['effective_source'], e['effective_target'], e['relation_type'])
    ml_sig = {(next(d.text for d in e if d.attrib.get('key') == 'eeid'), e.attrib['source'], e.attrib['target'], next(d.text for d in e if d.attrib.get('key') == 'erel')) for e in ml}
    checks['graphml_matches_json'] = {signature(e) for e in edges} == ml_sig and len(tree.findall('.//g:node', ns)) == 197
    accepted = rows('02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl')
    accepted_sig = {(e['edge_id'], e['target'] if e['relation_type'] == 'prerequisite' and e.get('direction') == 'target_to_source' else e['source'], e['source'] if e['relation_type'] == 'prerequisite' and e.get('direction') == 'target_to_source' else e['target'], e['relation_type']) for e in accepted}
    checks['accepted_edges_match_graph'] = accepted_sig == {signature(e) for e in edges}
    summaries = json.loads((display / 'node_summaries.json').read_text())
    edge_lookup = {e['edge_id']: e for e in edges}
    checks['display_summaries_match_graph_and_definition'] = len(summaries) == 197 and {s['card_id'] for s in summaries} == nodes.keys() and all(s['degree'] == degree[s['card_id']] and s['definition'] == cards[s['card_id']]['fields']['精确定义'] and len(s['in_edges']) + len(s['out_edges']) == s['degree'] and all(x['edge_id'] in edge_lookup and edge_lookup[x['edge_id']]['effective_target'] == s['card_id'] and edge_lookup[x['edge_id']]['effective_source'] == x['from'] and edge_lookup[x['edge_id']]['relation_type'] == x['rt'] for x in s['in_edges']) and all(x['edge_id'] in edge_lookup and edge_lookup[x['edge_id']]['effective_source'] == s['card_id'] and edge_lookup[x['edge_id']]['effective_target'] == x['to'] and edge_lookup[x['edge_id']]['relation_type'] == x['rt'] for x in s['out_edges']) for s in summaries)
    html = (display / 'graph.html').read_text()
    payload = re.search(r'const NODES=(.*?), EDGES=(.*?);\n', html)
    checks['html_embedded_data_matches'] = bool(payload) and json.loads(payload.group(1)) == graph['nodes'] and json.loads(payload.group(2)) == edges
    labels = ['K1 人类、智能与机器', 'K2 数据、表征与知识', 'K3 算法、模型与学习', 'K4 生成式AI、交互与智能体', 'K5 AI应用、工程与创新', 'K6 社会、伦理与未来']
    checks['display_labels_correct'] = all(label in html for label in labels) and '知识标签：' in html
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    node = shutil.which('node')
    if node:
        with tempfile.TemporaryDirectory() as folder:
            tmp = Path(folder) / 'graph.js'
            tmp.write_text(script)
            proc = subprocess.run([node, '--check', str(tmp)], capture_output=True, text=True)
            checks['javascript_syntax'] = proc.returncode == 0
    else:
        checks['javascript_syntax'] = None
    archive = BASE / '04_归档/图谱关系审计凭据'
    evidence = json.loads((archive / '保全清单.json').read_text())
    checks['permanent_evidence_hashes'] = all(sha(archive / name) == value for name, value in evidence['artifact_hashes'].items())
    original_raw = BASE / evidence['source_root']
    with zipfile.ZipFile(archive / 'P5-P6原始评审与裁定-20261001.zip') as z:
        checks['archive_matches_original_bytes'] = len(z.namelist()) == evidence['source_files'] and z.testzip() is None and all(z.read(name) == (original_raw / name).read_bytes() for name in z.namelist())
    records = rows('04_归档/图谱关系审计凭据/adjudications.jsonl')
    pairset = {e['pair_id'] for e in edges}
    record_map = {r['pair_id']: r for r in records}
    checks['published_edges_have_matching_adjudication'] = all(e['pair_id'] in record_map and record_map[e['pair_id']].get('adopted_relation') == e['relation_type'] and record_map[e['pair_id']]['final_status'] == 'ACCEPTED_MODEL_ADJUDICATED' and (e['relation_type'] != 'prerequisite' or record_map[e['pair_id']].get('direction') == e['direction']) for e in edges)
    missing = [r for r in records if 'adopted_relation' not in r]
    status_counts = dict(collections.Counter(r['final_status'] for r in records))
    summary = read_json('02_分析产物/p5_review/p6_close_summary.json')
    checks['current_p6_summary_matches'] = summary['final_status'] == status_counts and summary['edges'] == len(edges) and summary['structured_relation_missing'] == len(missing)
    findings = read_json('02_分析产物/p5_review/p75_findings.json')
    desired = {'F-001': ('prerequisite', '4-04', '3-37'), 'F-002': ('prerequisite', '4-02', '2-22')}
    checks['p75_fixed_edges_verified'] = all(all((edge_lookup[eid]['relation_type'], edge_lookup[eid]['effective_source'], edge_lookup[eid]['effective_target']) == desired[f['finding_id']] if f['finding_id'] in desired else edge_lookup[eid]['relation_type'] == 'related' for eid in f['edge_refs']) for f in findings['findings'] if f['finding_id'] != 'F-011')
    ctx = read_json('01_素材输入/课程背景资料/来源说明.json')
    checks['curriculum_snapshot_hash'] = sha(BASE / '01_素材输入/课程背景资料' / ctx['snapshot_file']) == ctx['sha256']
    queue_doc = read_json('02_分析产物/验收与记录收尾/裁定缺字段待核定清单.json')
    checks['followup_queue_complete'] = {r['pair_id'] for r in missing} == {r['pair_id'] for r in queue_doc['pairs']}
    return {'checked_at': '2026-10-01', 'graph_version': graph['meta']['graph_version'], 'checks': checks, 'structure_pass': all(v is True for v in checks.values()), 'counts': {'nodes': len(nodes), 'edges': len(edges), **counts, 'adjudications': len(records), 'missing_structured_relation': len(missing), 'accepted_missing_relation': sum(r['final_status'] == 'ACCEPTED_MODEL_ADJUDICATED' for r in missing), 'missing_pairs_in_graph': sum(r['pair_id'] in pairset for r in missing), 'permanent_evidence_files': evidence['source_files'], 'full_pairs': len(rows('02_分析产物/p5_review/full_pairs.jsonl')), 'light_pairs': len(rows('02_分析产物/p5_review/light_pairs.jsonl'))}, 'isolates': [{'card_id': n, 'name': nodes[n]['name']} for n in nodes if degree[n] == 0], 'node_fields': {f: sum(bool(c['fields'].get(f)) for c in cards.values()) for f in required + ['教学类比']}, 'node_field_dash_placeholders': {f: sum(c['fields'].get(f, '').strip() == '—' for c in cards.values()) for f in required + ['教学类比']}, 'undetermined_level': sum(c['fields']['认知层级'] == '待定' for c in cards.values()), 'semantic_content_acceptance': 'NOT_CLOSED: 260份缺结构化关系裁定，229份为已采纳；未自行补边或推断为无关系', 'current_render_acceptance': 'NOT_VERIFIED: 本会话浏览器安全策略已拒绝本地file协议，本轮未重试或绕过；语法和嵌入数据检查不等于渲染交互验收', 'human_acceptance': 'NOT_RECORDED_THIS_RUN', 'publication': '仅本地记录整改和展示修正版，未推送或部署'}

if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['structure_pass'] else 1)
