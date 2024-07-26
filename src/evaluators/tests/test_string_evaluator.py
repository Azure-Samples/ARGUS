import unittest

from src.evaluators.string_evaluator import StringEvaluator


class TestStringEvaluator(unittest.TestCase):

    def test_string_evaluator_exact_match(
        self
    ):
        evaluator = StringEvaluator(config={})
        exact_match = evaluator("value", "value")
        no_match = evaluator("value", "not_value")
        assert exact_match == True
        assert no_match == False

    def test_string_evaluator_puctuation_ignored(
        self
    ):
        evaluator = StringEvaluator(config={StringEvaluator.Config.IGNORE_PUNCTUATION_MARKS: True})
        match_1 = evaluator("value", "va.lue")
        # when contains a number, punctuation is NOT ignored
        match_2 = evaluator("1.0", "10")
        assert match_1 == True
        assert match_2 == False


    def test_string_evaluator_puctuation_not_ignored(
        self
    ):
        evaluator = StringEvaluator(config={StringEvaluator.Config.IGNORE_PUNCTUATION_MARKS: False})
        match_1 = evaluator("value", "value")
        match_2 = evaluator("value", "va.lue")
        assert match_1 == True
        assert match_2 == False

    def test_string_evaluator_puctuation_not_ignored(
        self
    ):
        evaluator = StringEvaluator(config={StringEvaluator.Config.IGNORE_PUNCTUATION_MARKS: False})
        match_1 = evaluator("value", "va.lue")
        assert match_1 == False


    def test_string_evaluator_dollar_sign_ignored(
        self
    ):
        evaluator = StringEvaluator(config={StringEvaluator.Config.IGNORE_DOLLAR_SIGN: True})
        match_1 = evaluator("$10", "10")
        assert match_1 == True


    def test_string_evaluator_dollar_sign_not_ignored(
        self
    ):
        evaluator = StringEvaluator(config={StringEvaluator.Config.IGNORE_DOLLAR_SIGN: False})
        match_1 = evaluator("$10", "10")
        assert match_1 == False


    def test_string_evaluator_additional_matches(
        self
    ):
        evaluator = StringEvaluator(config={StringEvaluator.Config.ADDITIONAL_MATCHES: ["yes", "true"]})
        match_1 = evaluator("correct", "correct")
        match_2 = evaluator("correct", "yes")
        match_3 = evaluator("correct", "true")
        match_4 = evaluator("correct", "false")
        assert match_1 == True
        assert match_2 == True
        assert match_3 == True
        assert match_4 == False
