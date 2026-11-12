import json
import unittest
from unittest.mock import Mock
from src.crew import Crew
from src.metrics import verdict_accuracy

class BenchmarkTests(unittest.TestCase):
    def test_candidate_scope_shared_across_agents(self):
        meko = Mock()
        meko.conversation_create.side_effect = ['scope-cid', 'scout-cid', 'verifier-cid']
        meko.memory_search.return_value = '{"results": []}'
        crew = Crew(Mock(), meko, 'meko')
        crew._candidate_id = 'candidate-a'
        scope = crew._memory_conversation()
        crew._context('scout', {'name': 'A'}, 1)
        crew._context('verifier', {'name': 'A'}, 1)
        self.assertEqual([c.kwargs['run_id'] for c in meko.memory_search.call_args_list], [scope, scope])

    def test_unknown_not_accepted(self):
        self.assertEqual(Crew._final_verdict({'verifier': {'verdict': 'UNSURE'}}), 'UNSURE')

    def test_accuracy_labels(self):
        self.assertEqual(verdict_accuracy([{'candidate':'x', 'verdict':'UNSURE'}], {'x':'UNSURE'})['accuracy'],1)

if __name__ == '__main__': unittest.main()
