import pytest
from eraleader.walkforward import walk_forward_split

DEC1="2024-01-01T17:00:00+09:00"
DEC2="2024-03-08T17:00:00+09:00"
DEC3="2024-04-05T17:00:00+09:00"
CUT="2024-03-01T17:00:00+09:00"
END="2024-05-01T17:00:00+09:00"
def signal(sec,decision, available=None):
    return {"security_id":sec,"as_of":decision,"features_available_at":available or decision,"feature_hash":sec+"-hash"}

def label(sec,decision,known,is_leader):
    return {"security_id":sec,"as_of":decision,
            "label_available_at":known,"is_future_leader":is_leader}

def test_walkforward_embargo_labels_are_not_visible_in_holdout():
    s=[signal("A",DEC1),signal("B",DEC2),signal("C",DEC3)]
    labels=[label("A",DEC1,"2024-02-02T17:00:00+09:00",True),
            label("B",DEC2,"2024-06-01T17:00:00+09:00",True),
            label("C",DEC3,"2024-06-01T17:00:00+09:00",False)]
    result=walk_forward_split(s,labels,train_ends_at=CUT,
                               test_ends_at=END,embargo_days=7)
    assert result["known_training_samples"]==1
    assert [v["security_id"] for v in result["test_candidates"]]==["B","C"]
    assert result["test_outcome_labels_revealed"] is False
    assert all("target" not in row for row in result["test_candidates"])

def test_future_available_feature_is_rejected():
    future=signal("A",DEC1,available="2024-01-02T10:00:00+09:00")
    with pytest.raises(ValueError,match="Future feature"):
        walk_forward_split([future],[],train_ends_at=CUT,test_ends_at=END)

def test_censored_label_does_not_train():
    s=[signal("A",DEC1)]
    later=[label("A",DEC1,"2024-06-01T17:00:00+09:00",True)]
    result=walk_forward_split(s,later,train_ends_at=CUT,test_ends_at=END)
    assert result["training"]==[]
    assert result["censored_training_samples"]==1

def test_dedup_and_invalid_dates_rejected():
    with pytest.raises(ValueError,match="Duplicated PIT"):
        walk_forward_split([signal("A",DEC1)]*2,[],train_ends_at=CUT,test_ends_at=END)
    with pytest.raises(ValueError,match="Invalid split"):
        walk_forward_split([],[],train_ends_at=END,test_ends_at=CUT)
