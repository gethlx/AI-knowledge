#!/usr/bin/env python3
"""只用临时输出及本地假裁定复验实际编排入口；不调用模型，不写正式图。"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '02_分析产物'))
import test_orchestrator as fixtures
import multi_model_review as mmr
import build_graph


def adjudication(pair_id, relation, direction):
    return {'pair_id': pair_id, 'adjudicator': 'gpt-5.6-sol(via-subagent)',
            'final_status': mmr.ST_ACCEPTED, 'adopted_relation': relation,
            'adopted_direction': direction, 'adopted_by': 'orchestrator',
            'rationale': '本地假数据：校验最终裁定覆盖评审意见，不是新增业务关系。',
            'residual_risks': ['本地测试'], 'reviewer_agreement': '测试中的意见与裁定可不同',
            'escalation_reason': None, 'schema_version': 'p1-contract-v2'}


class CannedAdjudicator(mmr.AdjudicationProvider):
    def __init__(self, decisions):
        self.decisions = decisions

    def adjudicate(self, pair, bundle, graph_state):
        return adjudication(pair.pair_id, *self.decisions[pair.pair_id])


def edge(a, b, direction):
    return {'edge_id': a + '__' + b, 'pair_id': a + '__' + b,
            'source': a, 'target': b, 'relation_type': 'prerequisite',
            'direction': direction, 'adopted_direction': direction}


def audit():
    result = []
    with tempfile.TemporaryDirectory(prefix='gv2_final_local_') as folder:
        tmp = Path(folder)
        for index, (relation, direction) in enumerate([
            ('related', None), ('prerequisite', 'target_to_source'),
            ('no_relation', None), ('insufficient_evidence', None)
        ]):
            pid = '1-01__1-02'
            # 评审意见刻意与最终裁定不同，以验证真实process_pair没有回取评审投票。
            reviewers = fixtures.unanimous_provider_set(pid, 'prerequisite', 'source_to_target')
            orch = fixtures.build_orch(tmp / str(index), reviewers,
                CannedAdjudicator({pid: (relation, direction)}))
            orch.run([fixtures.make_pair(pid)])
            accepted = fixtures.read_jsonl(orch.paths['accepted'])
            rejected = fixtures.read_jsonl(orch.paths['rejected'])
            if relation in ('no_relation', 'insufficient_evidence'):
                passed = not accepted and len(rejected) == 1 and rejected[0].get('adopted_relation') == relation
            else:
                passed = (len(accepted) == 1 and accepted[0]['relation_type'] == relation and
                    accepted[0]['direction'] == direction and
                    build_graph.normalize(accepted[0]) == (('1-02', '1-01') if direction == 'target_to_source' else ('1-01', '1-02')))
            result.append({'case': 'actual_process_pair_' + relation,
                           'pass': passed, 'accepted_count': len(accepted), 'negative_count': len(rejected)})
        cycles = [edge('1-01', '1-02', 'source_to_target'),
                  edge('1-02', '1-03', 'source_to_target'),
                  edge('1-01', '1-03', 'target_to_source')]
        state = mmr.GraphState()
        for e in cycles: state.add(e)
        violations = mmr.check_dag(state)
        result.append({'case': 'reverse_prerequisite_cycle_detected',
            'pass': bool(build_graph.dag_check(cycles)) and any(x['type'] == 'prerequisite_cycle' for x in violations),
            'violations': violations})
        # 原始顺序可形成环，但生效方向无环：不能误报。
        acyclic = [edge('1-01', '1-02', 'source_to_target'),
                   edge('1-02', '1-03', 'source_to_target'),
                   edge('1-03', '1-01', 'target_to_source')]
        state = mmr.GraphState()
        for e in acyclic: state.add(e)
        result.append({'case': 'effective_acyclic_graph_not_falsely_rejected',
                       'pass': not mmr.check_dag(state) and not build_graph.dag_check(acyclic)})
        # 实际批次入口：三条新假边形成反向环时，正式accepted临时文件不得留下环边。
        decisions = {e['pair_id']: ('prerequisite', e['direction']) for e in cycles}
        reviewers = [fixtures.CannedReviewProvider(r,
            lambda pair, reviewer: fixtures.make_opinion(pair.pair_id, reviewer, 'related', None))
            for r in mmr.REVIEWERS]
        orch = fixtures.build_orch(tmp / 'batch_cycle', reviewers, CannedAdjudicator(decisions))
        summary = orch.run([fixtures.make_pair(pid) for pid in decisions])
        result.append({'case': 'actual_batch_cycle_escalates_instead_of_retaining_edges',
                       'pass': bool(summary['dag_violations']) and not fixtures.read_jsonl(orch.paths['accepted']) and
                               len(fixtures.read_jsonl(orch.paths['escalation'])) == 3})
    return {'checked_at': '2026-10-01', 'all_pass': all(x['pass'] for x in result),
            'cases': result, 'scope': '真实编排入口、本地假裁定、临时输出；零模型调用，正式数据不变'}


if __name__ == '__main__':
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['all_pass'] else 1)
