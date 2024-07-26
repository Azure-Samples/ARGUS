import unittest

from src.evaluators.match_evaluator import MatchEvaluator


class TestMatchEvaluator(unittest.TestCase):

    def test_match_evaluator(
        self
    ):
        ground_truth_data = {
            "key1": "value1",
            "key2": "value2",
        }

        actual_data = {
            "key1": "value1",
            "key2": "wrong_value"
        }

        correct_key = "key1"
        correct_key_evaluator = MatchEvaluator(key=correct_key)
        incorrect_key = "key2"
        incorrect_key_evaluator = MatchEvaluator(key=incorrect_key)
        assert correct_key_evaluator(actual_data, ground_truth_data)["output"] == True
        assert incorrect_key_evaluator(actual_data, ground_truth_data)["output"] == False

    def test_match_evaluator_nested_object(
        self
    ):
        ground_truth_data = {
            "key1": {
                "key1": "value1",
                "key2": "value2",
                "key3": {
                    "key1": "value3", 
                    "key2": "value4",
                    "key3": "value5",
                },
            }
        }

        actual_data = {
            "key1": {
                "key1": "value1",
                "key2": "wrong_value",
                "key3": {
                    "key1": "value3",
                    "key2": "wrong_value",
                    # key3 is missing
                },
            }
        }
        nested_key_correct = "key1.key1"
        nested_key_correct_evaluator = MatchEvaluator(key=nested_key_correct)
        assert nested_key_correct_evaluator(actual_data, ground_truth_data)["output"] == 1
        
        nested_key_wrong = "key1.key2"
        nested_key_wrong_evaluator = MatchEvaluator(key=nested_key_wrong)
        assert nested_key_wrong_evaluator(actual_data, ground_truth_data)["output"] == 0
        
        doubled_nested_key_correct = "key1.key3.key1"
        doubled_nested_key_correct_evaluator = MatchEvaluator(key=doubled_nested_key_correct)
        assert doubled_nested_key_correct_evaluator(actual_data, ground_truth_data)["output"] == 1

        doubled_nested_key_wrong = "key1.key3.key2"
        doubled_nested_key_wrong_evaluator = MatchEvaluator(key=doubled_nested_key_wrong)
        assert doubled_nested_key_wrong_evaluator(actual_data, ground_truth_data)["output"] == 0
        
        not_exist_key= "key1.key3.key3"
        not_exist_key_evaluator = MatchEvaluator(key=not_exist_key)
        assert not_exist_key_evaluator(actual_data, ground_truth_data)["output"] == 0
        assert not_exist_key_evaluator(actual_data, ground_truth_data)["error"] == MatchEvaluator.KEY_NOT_FOUND


        # TODO: add test for lists