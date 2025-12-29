from __future__ import annotations

import pytest

from debatebench.judge_parsing import extract_json_block, parse_json_scores


def test_extract_json_block_from_text():
    payload = extract_json_block("noise\n{\"scores\":{\"pro\":{\"a\":3},\"con\":{\"a\":4}}}\ntrailer")
    assert payload == {"scores": {"pro": {"a": 3}, "con": {"a": 4}}}


def test_extract_json_block_from_yaml():
    payload = extract_json_block("scores:\n  pro:\n    a: 5\n  con:\n    a: 6\n")
    assert payload == {"scores": {"pro": {"a": 5}, "con": {"a": 6}}}


def test_parse_json_scores_case_insensitive_and_clamped():
    payload = {"scores": {"pro": {"Persuasion": 11}, "con": {"persuasion": -2}}}
    pro, con = parse_json_scores(payload, ["persuasion"], 1, 10)
    assert pro == {"persuasion": 10}
    assert con == {"persuasion": 1}


def test_parse_json_scores_missing_dimension():
    payload = {"scores": {"pro": {"a": 3}, "con": {}}}
    with pytest.raises(ValueError):
        parse_json_scores(payload, ["a"], 1, 10)
