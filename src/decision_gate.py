"""Deterministic consistency gate over Scout facts, never fixture labels.

RedTeam advice remains visible but cannot turn missing evidence into a proven
violation. This checks extracted facts, not authenticity or full page accuracy.
"""
from datetime import date
import re


def decide(facts: dict, evaluation_date: str = '2026-11-10') -> dict:
    checks = {}
    def boolean(key, field, required):
        value = facts.get(field)
        checks[key] = 'unknown' if not isinstance(value, bool) else ('pass' if value == required else 'fail')
    boolean('1', 'student_only', False)
    eligibility = str(facts.get('eligibility') or '').lower()
    if re.search(r'working professionals? only|only (?:to )?working professionals?', eligibility):
        checks['1'] = 'fail'  # fixed benchmark profile is a non-employed hobbyist
    boolean('2', 'online', True)
    boolean('3', 'free_entry', True)
    cash = facts.get('first_prize_cash_usd')
    checks['4'] = 'unknown' if not isinstance(cash, (float, int)) or isinstance(cash, bool) else ('pass' if cash >= 100 else 'fail')
    boolean('5', 'solo_allowed', True)
    try:
        deadline = date.fromisoformat(str(facts.get('deadline'))[:10])
        checks['6'] = 'pass' if deadline >= date.fromisoformat(evaluation_date) else 'fail'
    except ValueError:
        checks['6'] = 'unknown'
    boolean('7', 'requires_face_or_voice', False)
    verdict = 'FAIL' if 'fail' in checks.values() else ('UNSURE' if 'unknown' in checks.values() else 'PASS')
    return {'verdict': verdict, 'checks': checks, 'basis': 'structured Scout facts; RedTeam advisory only'}
