import unittest
from src.decision_gate import decide

class DecisionGateTests(unittest.TestCase):
    def setUp(self):
        self.f = dict(student_only=False, online=True, free_entry=True,
                      first_prize_cash_usd=100, solo_allowed=True,
                      deadline='2026-11-10T23:59:00Z', requires_face_or_voice=False,
                      eligibility='Open worldwide, adults, solo or team')
    def test_all_pass(self): self.assertEqual(decide(self.f)['verdict'], 'PASS')
    def test_missing_prize_unknown(self):
        self.f['first_prize_cash_usd']=None
        self.assertEqual(decide(self.f)['verdict'], 'UNSURE')
    def test_explicit_profile_exclusion(self):
        self.f['eligibility']='Working professionals only.'
        self.assertEqual(decide(self.f)['verdict'], 'FAIL')
    def test_no_imagined_professional_exclusion(self):
        self.assertEqual(decide(self.f)['checks']['1'],'pass')
    def test_boolean_traps(self):
        for field in ('online','free_entry','solo_allowed'):
            with self.subTest(field=field):
                self.assertEqual(decide({**self.f,field:False})['verdict'],'FAIL')
        for field in ('student_only','requires_face_or_voice'):
            with self.subTest(field=field):
                self.assertEqual(decide({**self.f,field:True})['verdict'],'FAIL')
    def test_expired(self):
        self.assertEqual(decide({**self.f,'deadline':'2026-11-09'})['verdict'],'FAIL')
    def test_malformed_date_unknown(self):
        self.assertEqual(decide({**self.f,'deadline':'later'})['verdict'],'UNSURE')
    def test_null_boolean_unknown(self):
        self.assertEqual(decide({**self.f,'online':None})['verdict'],'UNSURE')
    def test_zero_cash_fail(self):
        self.assertEqual(decide({**self.f,'first_prize_cash_usd':0})['verdict'],'FAIL')
    def test_labels_do_not_affect_gate(self):
        self.assertEqual(decide({**self.f,'ground_truth':'FAIL','name':'trap'})['verdict'],'PASS')
