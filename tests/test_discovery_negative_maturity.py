"""PIT research evaluator negative horizon regression tests."""
from datetime import date, timedelta
from eraleader.discovery_metrics import evaluate_early_discovery


def _negative(first_seen="2025-01-01", recorded_at=None, maturity_days=30):
    signal={"security_id":"SYNTH-1","first_seen":first_seen}
    if recorded_at is not None:
        signal["recorded_at"]=recorded_at
    mature=(date.fromisoformat(first_seen)+timedelta(days=maturity_days)).isoformat()
    label={"security_id":"SYNTH-1","is_future_leader":False,
           "mature_on":mature,"outcome_available_at":mature}
    return evaluate_early_discovery([signal],[label],
                                    evaluated_at="2025-12-31",horizon_days=180)

def test_short_negative_label_stays_censored_after_available():
    result=_negative(maturity_days=30)
    assert result["false_discoveries"]==0
    assert result["censored"]==1
    assert result["evaluable"]==0
    assert result["premature_negative_labels_censored"]==1


def test_negative_exact_horizon_is_evaluable():
    result=_negative(maturity_days=180)
    assert result["false_discoveries"]==1
    assert result["censored"]==0
    assert result["premature_negative_labels_censored"]==0


def test_negative_maturity_uses_actual_registration():
    result=_negative(first_seen="2025-01-01",recorded_at="2025-04-01",maturity_days=180)
    assert result["false_discoveries"]==0
    assert result["premature_negative_labels_censored"]==1
