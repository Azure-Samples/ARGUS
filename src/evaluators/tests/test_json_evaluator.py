import unittest

from src.evaluators.custom_string_evaluator import CustomStringEvaluator
from src.evaluators.fuzz_string_evaluator import FuzzStringEvaluator
from src.evaluators.json_evaluator import JsonEvaluator


class TestJsonEvaluator(unittest.TestCase):

    def test_json_evaluator_no_eval_schema(self):
        ground_truth_data = {
            "key1": "value1",  # value 1
            "key2": {
                "key1": "value2",  # value 2
                "key2": {"key1": "value3"},  # value 3
                "key3": ["value4", "value5"],  # Values 4 and 5
                "key4": {
                    "key1": [{"key1": "value6", "key2": "value7"}]  # value 6  # value 7
                },
                "key5": "value8",  # value 8
            },
            "key3": "value9",  # value 9
            "key4": "value10",  # value 10
        }
        # Total values = 10

        actual_data = {
            "key1": "wrong_value",  # wrong 1 - Should be "value1"
            "key2": {
                "key1": "value2",  # correct 1 - this should be marked correct as the ground truth int will be made a str in the string evaluator
                "key2": {
                    "key1": "value,3"  # wrong 2 - should be "5.0" - puctuation is ignored when word does NOT contains a number
                },
                "key3": ["value4", "value5"],  # correct 2  # correct 3
                "key4": {
                    "key1": [
                        {"key1": "value6", "key2": "value7"}  # correct 4  # correct 5
                    ]
                },
                # key5 is missing
            },
            # key3 is missing
            "key4": "value10",  # correct 6
        }
        # Total correct = 6
        # ratio = 6/10 = 0.6

        json_evaluator = JsonEvaluator()
        result = json_evaluator(ground_truth_data, actual_data)
        assert result["CustomStringEvaluator.ratio"] == 0.6
        assert result['FuzzStringEvaluator.ratio'] == 0.782

    def test_json_evaluator_with_eval_schema(self):
        ground_truth_data = {
            "key1": "value1",  # value 1
            "key2": {
                "key1": "value2",  # value 2
                "key2": {"key1": "value3"},  # value 3
                "key3": ["value4", "value5"],  # Values 4 and 5
                "key4": {
                    "key1": [{"key1": "value6", "key2": "value7"}]  # value 6  # value 7
                },
                "key5": "value8",  # value 8
            },
            "key3": "value9",  # value 9
            "key4": "value10",  # value 10
        }
        # Total values = 10

        actual_data = {
            "key1": "wrong_value",  # wrong 1 - Should be "value1"
            "key2": {
                "key1": "value.2",  # correct 1 - this should be marked correct as the ground truth int will be made a str in the string evaluator
                "key2": {"key1": "$value3"},  # correct 2
                "key3": ["value4", "value,5"],  # correct 3
                "key4": {
                    "key1": [
                        {"key1": "value,6", "key2": "value7"}  # correct 4  # correct 5
                    ]
                },
                # key5 is missing
            },
            "key4": "value10",  # correct 6
            # key2 is missing
        }
        # Total correct = 6
        # ratio = 6/10 = 0.6

        eval_schema = {
            "key1": {},
            "key2": {
                "key1": {"CustomStringEvaluator": {"IGNORE_DOTS": "True"}},
                "key2": {
                    "key1": {"CustomStringEvaluator": {"IGNORE_DOLLAR_SIGN": "True"}}
                },
                "key3": {},
                "key4": {
                    "key1": [
                        {
                            "key1": {
                                "CustomStringEvaluator": {"IGNORE_COMMAS": "True"}
                            },
                            "key2": {},
                        }  # correct 4  # correct 5
                    ]
                },
                "key5": {},
            },
            "key3": {},
            "key4": {},
        }

        json_evaluator = JsonEvaluator()
        result = json_evaluator(ground_truth_data, actual_data, eval_schema)
        assert result['FuzzStringEvaluator.ratio'] == 0.764
        assert result["CustomStringEvaluator.ratio"] == 0.6

    def test_json_evaluator_no_eval_schema_with_default_config(self):
        ground_truth_data = {
            "key1": "value1",  # value 1
            "key2": {
                "key1": "value2",  # value 2
                "key2": {"key1": "value3"},  # value 3
                "key3": ["value4", "value5"],  # Values 4 and 5
                "key4": {
                    "key1": [{"key1": "value6", "key2": "value7"}]  # value 6  # value 7
                },
                "key5": "value8",  # value 8
            },
            "key3": "value9",  # value 9
            "key4": "value10",  # value 10
        }
        # Total values = 10

        actual_data = {
            "key1": "wrong_value",  # wrong 1 - Should be "value1"
            "key2": {
                "key1": "value.2",  # correct 1 - this should be marked correct as the ground truth int will be made a str in the string evaluator
                "key2": {"key1": "$value3"},  # correct 2
                "key3": ["value4", "value,5"],  # correct 3
                "key4": {
                    "key1": [
                        {"key1": "value,6", "key2": "value7"}  # correct 4  # correct 5
                    ]
                },
                # key5 is missing
            },
            "key4": "value10",  # correct 6
            # key2 is missing
        }
        # Total correct = 6
        # ratio = 6/10 = 0.6

        evaluators = [
            CustomStringEvaluator({
                CustomStringEvaluator.Config.IGNORE_DOLLAR_SIGN: True,
                CustomStringEvaluator.Config.IGNORE_DASHES: True,
                CustomStringEvaluator.Config.IGNORE_DOTS: True,
            }), 
            FuzzStringEvaluator(),
        ]

        # Total correct = 5
        # ratio = 5/10 = 0.5

        json_evaluator = JsonEvaluator(evaluators)
        result = json_evaluator(ground_truth_data, actual_data)
        assert result["CustomStringEvaluator.ratio"] == 0.5
        assert result['FuzzStringEvaluator.ratio'] == 0.764

    def test_json_evaluator_different_array_length_in_actual(self):
        ground_truth_data = {
            "key1": "value1",  # value 1
            "key2": ["test1", "test2", "test3"],  # Values 2, 3, 4
        }
        # Total values = 4

        actual_data = {
            "key1": "value1",   # correct 1
            "key2": ["test1"],  # correct 2, wrong 1, wrong 2 (missing index 1, 2)
        }

        evaluators = [CustomStringEvaluator()]

        # Total correct = 2
        # ratio = 2/4 = 0.5

        json_evaluator = JsonEvaluator(evaluators)
        result = json_evaluator(ground_truth_data, actual_data)
        assert result["CustomStringEvaluator.ratio"] == 0.5
        assert result['CustomStringEvaluator.key1'] == 1
        assert result['CustomStringEvaluator.key2[0]'] == 1
        assert result['CustomStringEvaluator.key2[1]'] == 0
        assert result['CustomStringEvaluator.key2[2]'] == 0

    def test_json_evaluator_handles_array_first_value(self):
        ground_truth_data = [
            {"key1": "value1"},  # value 1
            {"key2": ["1", "2", "3"]},
            "array_value_3"
        ]
        # Total values = 5

        actual_data = [
            {"key1": "value1"},  # correct 1
            {"key2": ["1", "wrong", "3"]}, # correct 2, wrong 1, correct 3
            "array_value_3" # correct 4
        ]

        # Total correct = 4
        # ratio = 4/5 = 0.8

        evaluators = [CustomStringEvaluator()]

        json_evaluator = JsonEvaluator(evaluators)
        result = json_evaluator(ground_truth_data, actual_data)
        assert result["CustomStringEvaluator.ratio"] == 0.8
        assert result['CustomStringEvaluator.[0].key1'] == 1
        assert result['CustomStringEvaluator.[1].key2[0]'] == 1
        assert result['CustomStringEvaluator.[1].key2[1]'] == 0
        assert result['CustomStringEvaluator.[1].key2[2]'] == 1
        assert result['CustomStringEvaluator.[2]'] == 1

    def test_json_evaluator_handles_array_dict_mismatch(self):
        ground_truth_data = [
            {"key1": "value1"},  # value 1
            {"key2": ["1", "2", "3"]},
            "array_value_3"
        ]
        # Total values = 5

        # all values should be wrong, as this is a dict and not an array
        actual_data = {
            "key1": "value1",
            "key2": ["1", "wrong", "3"],  
        }

        # Total correct = 0
        # ratio = 0/5 = 0

        evaluators = [CustomStringEvaluator()]

        json_evaluator = JsonEvaluator(evaluators)
        result = json_evaluator(ground_truth_data, actual_data)
        assert result["CustomStringEvaluator.ratio"] == 0
        assert result['CustomStringEvaluator.[0].key1'] == 0
        assert result['CustomStringEvaluator.[1].key2[0]'] == 0
        assert result['CustomStringEvaluator.[1].key2[1]'] == 0
        assert result['CustomStringEvaluator.[1].key2[2]'] == 0
        assert result['CustomStringEvaluator.[2]'] == 0