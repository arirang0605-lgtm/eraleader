import pytest
from eraleader.discovery_metrics import evaluate_early_discovery

def outcomes():
    return [
      {"security_id":"A","is_future_leader":True,"leader_start_at":"2024-05-01",
       "mature_on":"2024-08-01","outcome_available_at":"2024-08-02"},
      {"security_id":"B","is_future_leader":False,"leader_start_at":"2024-08-10",
       "mature_on":"2024-08-10","outcome_available_at":"2024-08-11"},
      {"security_id":"D","is_future_leader":True,"leader_start_at":"2024-05-01",
       "mature_on":"2024-08-01","outcome_available_at":"2024-08-02"},
      {"security_id":"E","is_future_leader":True,"leader_start_at":"2025-05-01",
       "mature_on":"2025-08-01","outcome_available_at":"2025-08-02"},
    ]

def test_precision_censored_and_lead_time_do_not_include_future_outcomes():
    signals=[{"security_id":"A","first_seen":"2024-02-01"},
             {"security_id":"A","first_seen":"2024-03-01"},
             {"security_id":"B","first_seen":"2024-02-10"},
             {"security_id":"C","first_seen":"2024-03-01"},
             {"security_id":"E","first_seen":"2024-04-01"}]
    result=evaluate_early_discovery(signals,outcomes(),
                                     evaluated_at="2024-10-01",horizon_days=180)
    assert result["signals"]==4
    assert result["true_early_discoveries"]==1
    assert result["false_discoveries"]==1
    assert result["censored"]==2
    assert result["precision_on_known_nonlate"]==0.5
    assert result["median_early_lead_days"]==90
    assert result["recall_certified_universe"] is None
    assert result["status"]=="RESEARCH_EVALUATION_ONLY_NOT_CERTIFIED"

def test_future_labels_cannot_be_used_until_available():
    data=[{"security_id":"A","first_seen":"2024-02-01"}]
    result=evaluate_early_discovery(data,outcomes(),
                                   evaluated_at="2024-07-01",horizon_days=180)
    assert result["censored"]==1 and result["evaluable"]==0
    assert result["precision_on_known_nonlate"] is None

def test_late_detection_not_counted_as_early():
    data=[{"security_id":"A","first_seen":"2024-06-01"}]
    result=evaluate_early_discovery(data,outcomes(),
                                   evaluated_at="2024-10-01",horizon_days=180)
    assert result["late_or_post_onset"]==1
    assert result["true_early_discoveries"]==0

def test_invalid_outcomes_and_future_signals_rejected():
    with pytest.raises(ValueError,match="Duplicate"):
        evaluate_early_discovery([],outcomes()+outcomes()[:1],
                                 evaluated_at="2024-10-01",horizon_days=180)
    with pytest.raises(ValueError,match="Future signal"):
        evaluate_early_discovery([{"security_id":"X","first_seen":"2025-01-01"}],
                                  outcomes(),evaluated_at="2024-10-01",horizon_days=180)
    bad=outcomes()
    bad[0]={**bad[0],"outcome_available_at":"2024-07-01"}
    with pytest.raises(ValueError,match="before its maturity"):
        evaluate_early_discovery([],bad,evaluated_at="2024-10-01",horizon_days=180)

def test_research_evaluation_cli_writes_report(tmp_path,capsys):
    import json
    from eraleader.cli import main
    signals=[{"security_id":"A","first_seen":"2024-02-01"}]
    (tmp_path/"signals.json").write_text(json.dumps(signals))
    (tmp_path/"outcomes.json").write_text(json.dumps(outcomes()))
    main(["validate-discovery","--signals",str(tmp_path/"signals.json"),
          "--outcomes",str(tmp_path/"outcomes.json"),
          "--evaluated-at","2024-10-01","--out",str(tmp_path)])
    stdout=json.loads(capsys.readouterr().out)
    assert stdout["true_early_discoveries"]==1
    saved=json.loads((tmp_path/"validation_research.json").read_text())
    assert saved["recall_certified_universe"] is None

def test_backdated_signal_uses_registration_date_instead_of_claimed_first_seen():
    signal=[{"security_id":"A","first_seen":"2024-01-01",
             "recorded_at":"2024-06-01"}]
    result=evaluate_early_discovery(signal,outcomes(),
                                     evaluated_at="2024-10-01",horizon_days=180)
    assert result["true_early_discoveries"]==0
    assert result["late_or_post_onset"]==1
    assert result["retrospective_unregistered_signals"]==0
    assert result["all_signal_dates_independently_registered"] is True

def test_registered_early_signal_and_censored_denominator():
    signals=[{"security_id":"A","first_seen":"2024-02-01",
              "recorded_at":"2024-02-15"},
             {"security_id":"C","first_seen":"2024-02-01"}]
    result=evaluate_early_discovery(signals,outcomes(),
                                     evaluated_at="2024-10-01",horizon_days=180)
    assert result["true_early_discoveries"]==1
    assert result["median_early_lead_days"]==76
    assert result["evaluable_fraction"]==0.5
    assert result["conservative_early_precision_floor"]==0.5
    assert result["retrospective_unregistered_signals"]==1

def test_forged_or_future_signal_registration_rejected():
    with pytest.raises(ValueError,match="precedes first_seen"):
        evaluate_early_discovery([
            {"security_id":"A","first_seen":"2024-02-01","recorded_at":"2024-01-01"}
        ],outcomes(),evaluated_at="2024-10-01",horizon_days=180)
    with pytest.raises(ValueError,match="Future signal"):
        evaluate_early_discovery([
            {"security_id":"A","first_seen":"2024-02-01","recorded_at":"2024-11-01"}
        ],outcomes(),evaluated_at="2024-10-01",horizon_days=180)

def test_invalid_onset_after_maturity_rejected():
    broken=outcomes()
    broken[0]={**broken[0],"leader_start_at":"2024-09-01"}
    with pytest.raises(ValueError,match="after label maturity"):
        evaluate_early_discovery([{"security_id":"A","first_seen":"2024-02-01"}],
                                 broken,evaluated_at="2024-10-01",horizon_days=180)
