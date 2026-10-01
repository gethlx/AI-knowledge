#!/usr/bin/env python3
"""只读终审G_v2工件与裁定来源；只向标准输出写结果，不重建或发布。"""
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from pathlib import Path
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[2]

def read(name):
    return json.loads((ROOT / name).read_text())

def sha(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()

def audit():
    folder = '03_交付物/G_v2_模型裁定版'
    g = read(folder + '/graph.json')
    old = read('03_交付物/G_v1_模型裁定版/graph.json')
    split = read('02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json')
    e = {v['pair_id']: v for v in g['edges']}
    oe = {v['pair_id']: v for v in old['edges']}
    restores = {v['pair_id']: v for v in split['records'] if v['disposition'] == '应恢复入图'}
    excludes = {v['pair_id'] for v in split['records'] if v['disposition'] == '合理排除'}
    ids = {v['card_id'] for v in g['nodes']}
    typed_counts = dict(Counter(v['relation_type'] for v in g['edges']))
    new = set(e) - set(oe)
    bad_new = []
    for pid in new:
        if pid not in restores:
            bad_new.append(pid)
            continue
        edge, reviewed = e[pid], restores[pid]
        pre = reviewed['final_relation'] == 'prerequisite'
        endpoints = (reviewed['effective_source'], reviewed['effective_target']) if pre else tuple(pid.split('__'))
        if (edge['relation_type'] != reviewed['final_relation'] or
                edge['adjudicator'] != reviewed['adjudicator'] or edge['status'] != reviewed['final_status'] or
                edge['direction'] != (reviewed['direction_code'] if pre else None) or
                (edge['effective_source'], edge['effective_target']) != endpoints):
            bad_new.append(pid)
    adj, pre = defaultdict(set), defaultdict(list)
    indegree = {n: 0 for n in ids}
    bad_endpoints = []
    for edge in g['edges']:
        a, b = edge['effective_source'], edge['effective_target']
        if a not in ids or b not in ids or a == b:
            bad_endpoints.append(edge['edge_id'])
            continue
        adj[a].add(b); adj[b].add(a)
        if edge['relation_type'] == 'prerequisite':
            pre[a].append(b); indegree[b] += 1
    queue = deque(n for n in ids if indegree[n] == 0)
    topo = []
    while queue:
        n = queue.popleft(); topo.append(n)
        for v in pre[n]:
            indegree[v] -= 1
            if not indegree[v]: queue.append(v)
    seen, components = set(), []
    for n in ids:
        if n in seen: continue
        stack, comp = [n], []
        while stack:
            x = stack.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); stack.extend(adj[x] - seen)
        components.append(sorted(comp))
    version = hashlib.sha256(json.dumps({'nodes': g['nodes'], 'edges': g['edges']},
                                       sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    snapshot = read('04_归档/20261001-229对终审复核前快照/快照清单.json')
    preserved = {name: sha(name) == value for name, value in snapshot['protected_hashes'].items()}
    permanent = read('04_归档/图谱关系审计凭据/保全清单.json')
    permanent_ok = {name: sha('04_归档/图谱关系审计凭据/' + name) == value
                    for name, value in permanent['artifact_hashes'].items()}
    candidate = read('02_分析产物/验收与记录收尾/G_v2_候选图_186恢复/graph.json')
    checks = {'node_count_197': len(g['nodes']) == len(ids) == 197,
              'nodes_unchanged': g['nodes'] == old['nodes'],
              'edge_count_and_types': len(g['edges']) == 1562 and typed_counts == {'related': 1484, 'prerequisite': 78},
              'old_1376_edges_unchanged': set(oe) <= set(e) and all(e.get(pid) == edge for pid, edge in oe.items()),
              'new_edges_exactly_reviewed_186': len(restores) == 186 and new == set(restores) and not bad_new,
              '43_excluded_pairs_absent': len(excludes) == 43 and not excludes & set(e),
              'unique_pairs_and_edge_ids': len(e) == len(g['edges']) == len({v['edge_id'] for v in g['edges']}),
              'valid_endpoints_no_self_loops': not bad_endpoints,
              'prerequisite_DAG': len(topo) == len(ids),
              'one_component_zero_isolates': len(components) == 1 and all(adj[n] for n in ids),
              'graph_version_matches_content': version == g['meta']['graph_version'],
              'candidate_equals_formal_data': candidate['nodes'] == g['nodes'] and candidate['edges'] == g['edges'],
              'legacy_and_source_hashes_unchanged': all(preserved.values()) and all(permanent_ok.values())}
    summaries = read(folder + '/node_summaries.json')
    degree_mismatches, adjacency_mismatches = [], []
    for n in summaries:
        pid = n['card_id']
        incoming = [{'edge_id': v['edge_id'], 'from': v['effective_source'], 'rt': v['relation_type']}
                    for v in g['edges'] if v['effective_target'] == pid]
        outgoing = [{'edge_id': v['edge_id'], 'to': v['effective_target'], 'rt': v['relation_type']}
                    for v in g['edges'] if v['effective_source'] == pid]
        degree = len(incoming) + len(outgoing)
        if n['degree'] != degree:
            degree_mismatches.append({'card_id': pid, 'summary_degree': n['degree'], 'actual_degree': degree})
        if n['in_edges'] != incoming or n['out_edges'] != outgoing:
            adjacency_mismatches.append(pid)
    ns = {'m': 'http://graphml.graphdrawing.org/xmlns'}
    root = ET.parse(ROOT / (folder + '/graph.graphml')).getroot()
    graph = root.find('m:graph', ns)
    keys = {k.get('id'): k.get('attr.name') for k in root.findall('m:key', ns)}
    graphml_edges = graph.findall('m:edge', ns)
    byedgeid = {v['edge_id']: v for v in g['edges']}
    bad_numeric, wrongly_directed, bad_content, xml_ids = [], [], [], []
    for element in graphml_edges:
        data = {keys[x.get('key')]: x.text for x in element.findall('m:data', ns)}
        eid = data['edge_id']; xml_ids.append(eid)
        edge = byedgeid.get(eid)
        if edge is None or (element.get('source'), element.get('target'), data['relation_type'], data['status']) != (
                edge['effective_source'], edge['effective_target'], edge['relation_type'], edge['status']):
            bad_content.append(eid)
        if data['relation_type'] == 'related' and element.get('directed', graph.get('edgedefault')) in ('true', 'directed'):
            wrongly_directed.append(eid)
        try: float(data['model_confidence'])
        except (ValueError, TypeError): bad_numeric.append(eid)
    xml_nodes = graph.findall('m:node', ns)
    node_data = {element.get('id'): {keys[x.get('key')]: x.text for x in element.findall('m:data', ns)}
                 for element in xml_nodes}
    xml_nodes_match = len(xml_nodes) == len(node_data) == len(ids) and set(node_data) == ids
    xml_nodes_match = xml_nodes_match and all(node_data[n['card_id']] == {
        'label': n['canonical_name'], 'axis': n['axis'], 'level': n['level'], 'status': n['status']}
        for n in g['nodes'])
    xml_content_match = (xml_nodes_match and not bad_content and
                         len(xml_ids) == len(set(xml_ids)) == len(byedgeid) and set(xml_ids) == set(byedgeid))
    schema = read('03_交付物/p1_review_contract/edge_adjudication.schema.json')
    validator = Draft7Validator(schema)
    originals = [json.loads(line) for line in (ROOT / '04_归档/图谱关系审计凭据/adjudications.jsonl').read_text().splitlines()]
    schema_failures = []
    for rec in originals:
        errors = list(validator.iter_errors(rec))
        if errors:
            schema_failures.append({'pair_id': rec['pair_id'], 'first_error': errors[0].message})
    sample = {k: originals[0][k] for k in schema['required']}
    cases = {'missing_relation_and_direction_accepted': validator.is_valid(sample),
             'prerequisite_without_direction_accepted': validator.is_valid({**sample, 'adopted_relation': 'prerequisite'}),
             'valid_prerequisite_accepted': validator.is_valid({**sample, 'adopted_relation': 'prerequisite', 'adopted_direction': 'target_to_source'})}
    extra_checks = {'node_summaries_current': not degree_mismatches and not adjacency_mismatches,
                    'GraphML_content_counts_endpoints_match': xml_content_match,
                    'GraphML_related_edges_undirected': not wrongly_directed,
                    'GraphML_double_values_valid': not bad_numeric,
                    'schema_all_1907_records_compatible': not schema_failures,
                    'schema_new_structured_result_required': not cases['missing_relation_and_direction_accepted'],
                    'schema_prerequisite_direction_required': not cases['prerequisite_without_direction_accepted'],
                    'G_v2_HTML_present': (ROOT / (folder + '/graph.html')).exists()}
    return {'checked_at': '2026-10-01', 'baseline': g['meta']['graph_version'],
            'graph_data_checks': checks, 'graph_data_pass': all(checks.values()),
            'delivery_checks': extra_checks, 'final_delivery_pass': all(checks.values()) and all(extra_checks.values()),
            'counts': {'nodes': len(ids), 'edges': len(g['edges']), **typed_counts,
                       'components': len(components), 'isolates': sum(not adj[n] for n in ids)},
            'node_summary_degree_mismatches': degree_mismatches,
            'node_summary_adjacency_mismatches': adjacency_mismatches,
            'GraphML_errors': {'invalid_double_count': len(bad_numeric), 'related_directed_count': len(wrongly_directed),
                              'content_mismatches': bad_content},
            'schema': {'passed': len(originals)-len(schema_failures), 'failed': len(schema_failures),
                       'failure_samples': schema_failures[:5], 'cases': cases},
            'protected_hash_checks': preserved, 'permanent_evidence_hash_checks': permanent_ok,
            'current_browser_render': 'NOT_VERIFIED: G_v2 lacks graph.html; old HTML remains at G_v1',
            'semantic_review_scope': '恢复边与此前逐对裁定结果一致；不重新证明所有1562条关系的教学语义',
            'source_artifact_hashes': {folder + '/' + name: sha(folder + '/' + name)
                                      for name in ('graph.json', 'graph.graphml', 'node_summaries.json')}}

if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
