import unittest

from src.evaluators.match_evaluator import MatchEvaluator, load_match_evaluators


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

        evaluators, config = load_match_evaluators(ground_truth_data, {})

        correct_key_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1']
        assert correct_key_evaluator(actual_data, ground_truth_data)["output"] == True
        
        incorrect_key_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key2']
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

        evaluators, config = load_match_evaluators(ground_truth_data, {})
        nested_key_correct_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1.key1']
        assert nested_key_correct_evaluator(actual_data, ground_truth_data)["output"] == 1
        
        nested_key_wrong_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1.key2']
        assert nested_key_wrong_evaluator(actual_data, ground_truth_data)["output"] == 0
        
        doubled_nested_key_correct_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1.key3.key1']
        assert doubled_nested_key_correct_evaluator(actual_data, ground_truth_data)["output"] == 1

        doubled_nested_key_wrong_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1.key3.key2']
        assert doubled_nested_key_wrong_evaluator(actual_data, ground_truth_data)["output"] == 0
        
        not_exist_key_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1.key3.key3']
        assert not_exist_key_evaluator(actual_data, ground_truth_data)["output"] == 0
        assert not_exist_key_evaluator(actual_data, ground_truth_data)["error"] == MatchEvaluator.VALUE_NOT_FOUND


    # TODO: add test for lists
    def test_match_evaluator_list(
        self
    ):
        ground_truth_data = {
            "key1": [
                "value1",
                "value2",
            ],
            "key2": [
                {
                    "key1": ["value4", "value5", "value6"]
                }
            ]
        }

        actual_data = {
            "key1": [
                "value1",
                "wrong_value1",
            ],
            "key2": [
                {
                    "key1": ["value4", "wrong_value2"] # missing value6
                }
            ]
        }

        evaluators, config = load_match_evaluators(ground_truth_data, {})

        correct_key_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1[0]']        
        assert correct_key_evaluator(actual_data, ground_truth_data)["output"] == 1
        
        incorrect_key_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key1[1]']
        assert incorrect_key_evaluator(actual_data, ground_truth_data)["output"] == 0
        
        correct_key_nested_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key2[0].key1[0]']
        assert correct_key_nested_evaluator(actual_data, ground_truth_data)["output"] == 1

        incorrect_key_nested_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key2[0].key1[1]']
        assert incorrect_key_nested_evaluator(actual_data, ground_truth_data)["output"] == 0

        not_exist_key_evaluator = evaluators[f'{MatchEvaluator.MATCH_EVAL_PREFIX}.key2[0].key1[2]']
        assert not_exist_key_evaluator(actual_data, ground_truth_data)["output"] == 0
        assert not_exist_key_evaluator(actual_data, ground_truth_data)["error"] == MatchEvaluator.VALUE_NOT_FOUND
