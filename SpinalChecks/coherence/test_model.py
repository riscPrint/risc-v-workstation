import unittest
from pathlib import Path
from model import State, explore, generate, invariant, relation, successors


class ModelTests(unittest.TestCase):
    def test_exhaustive_base(self):
        report, graph = explore()
        self.assertEqual(report['verdict'], 'pass')
        self.assertGreater(len(graph), 100)
        actions = {a for edges in graph.values() for a, _ in edges}
        for prefix in ('A.acquire.0', 'A.acquire.1', 'home.select.0', 'home.select.1',
                       'C.release.0', 'C.release.1', 'C.probe_ack.0', 'C.probe_ack.1',
                       'D.grant.0', 'D.grant.1', 'E.grant_ack.0', 'E.grant_ack.1'):
            self.assertTrue(any(a.startswith(prefix) for a in actions), prefix)
        self.assertTrue(any(s.memory != s.latest and 2 in s.permission for s in graph))
        self.assertTrue(any(s.permission == (1, 1) for s in graph))

    def test_mutations_have_replayable_witnesses(self):
        for bug, failure in [('grant_conflict', 'swmr'), ('stale_data', 'home_data'),
                             ('lost_ack', 'deadlock'), ('retry', 'livelock_cycle')]:
            with self.subTest(bug=bug):
                report, _ = explore(bug)
                self.assertEqual(report['verdict'], 'fail')
                self.assertEqual(report['failure'], failure)
                s = State()
                visited = [s]
                for action in report['witness']:
                    s = dict(successors(s, bug))[action]
                    visited.append(s)
                if failure in ('swmr', 'data_value', 'home_data'):
                    self.assertEqual(invariant(s), failure)
                elif failure == 'deadlock':
                    self.assertEqual(list(successors(s, bug)), [])
                else:
                    self.assertIn(s, visited[:-1])

    def test_budget_is_not_pass(self):
        self.assertEqual(explore(limit=1)[0]['verdict'], 'inconclusive')
        with self.assertRaises(ValueError):
            explore(limit=0)

    def test_projection_excludes_conflicting_owners(self):
        _, graph = explore()
        states, edges = relation(graph)
        self.assertNotIn((2, 2), states)
        self.assertNotIn((2, 1), states)
        self.assertNotIn((1, 2), states)
        self.assertIn(((2, 0), (0, 2)), edges)  # shrink and grant in one sample

    def test_generated_source_is_current(self):
        _, graph = explore()
        source = Path(__file__).parents[1] / 'src/main/scala/spinalchecks/coherence/PermissionRelation.scala'
        self.assertEqual(source.read_text(), generate(graph))


if __name__ == '__main__':
    unittest.main()
