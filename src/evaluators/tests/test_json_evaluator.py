import unittest

from src.evaluators.json_evaluator import JsonEvaluator


class TestJsonEvaluator(unittest.TestCase):

    def test_json_evaluator(
        self
    ):
        ground_truth_data = {
            "key1": "value1", # value 1
            "key2": {
                "key1": "value2", # value 2
                "key2": {
                    "key1": "value3" # value 3
                },
                "key3": ["value4", "value5"], # Values 4 and 5
                "key4": {
                    "key1": [{
                        "key1": "value6", # value 6
                        "key2": "value7" # value 7
                    }]
                },
                "key5": "value8" # value 8
            },
            "key3": "value9", # value 9
            "key4": "value10" # value 10
        }
        # Total values = 10

        actual_data = {
            "key1": "wrong_value", # wrong 1 - Should be "value1"
            "key2": {
                "key1": "value2", # correct 1 - this should be marked correct as the ground truth int will be made a str in the string evaluator
                "key2": {
                    "key1": "value3" # wrong 2 - should be "5.0" - puctuation is ignored when word does NOT contains a number
                },
                "key3": [
                    "value4", # correct 2
                    "value5" # correct 3
                ],
                "key4": {
                    "key1": [{
                        "key1": "value6", # correct 4
                        "key2": "value7" # correct 5
                    }]
                }
                # key5 is missing
            },
            "key3": "value10" # correct 6
            # key2 is missing
        }
        # Total correct = 6 
        # ratio = 6/10 = 0.6

        json_evaluator = JsonEvaluator()
        ratio = json_evaluator(ground_truth_data, actual_data)
        assert ratio == 0.6
