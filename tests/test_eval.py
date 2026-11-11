from evals.run_eval import run_one


def test_eval_grades_a_report():
    result = run_one({"question": "What are facts A and B?", "must_cover": ["A", "B"]})
    assert result["overall"] == 0.8
