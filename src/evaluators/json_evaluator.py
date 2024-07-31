from src.evaluators.custom_string_evaluator import CustomStringEvaluator
from src.evaluators.fuzz_string_evaluator import FuzzStringEvaluator


class JsonEvaluator:

    class Config(CustomStringEvaluator.Config):
        pass

    def __init__(
        self,
        default_eval_config={}
    ):
        self.default_eval_config = default_eval_config
        self.result = {}
        self.string_evaluators = {
            "CustomStringEvaluator": {
                "instance": CustomStringEvaluator(),
                "total_strings_compared": 0,
                "total_score": 0,
                "ratio": 0,
            },
            "FuzzStringEvaluator": {
                "instance": FuzzStringEvaluator(),
                "total_strings_compared": 0,
                "total_score": 0,
                "ratio": 0,
            },
        }

    def __call__(self, ground_truth, actual, eval_schema={}):
        self.compare_dicts(ground_truth, actual, eval_schema)
        for string_evaluator_name, eval_dict in self.string_evaluators.items():
            self.string_evaluators[string_evaluator_name]["ratio"] = (
                self.string_evaluators[string_evaluator_name]["total_score"]
                / self.string_evaluators[string_evaluator_name]["total_strings_compared"]
                if self.string_evaluators[string_evaluator_name]["total_strings_compared"]
                > 0
                else 0
            )
            self.result[f"{string_evaluator_name}.ratio"] = eval_dict["ratio"]

        return self.result

    def compare_values(self, ground_truth, actual, eval_schema, curr_key):
        if isinstance(ground_truth, dict) and isinstance(actual, dict):
            return self.compare_dicts(ground_truth, actual, eval_schema, curr_key)
        elif isinstance(ground_truth, list) and isinstance(actual, list):
            return self.compare_lists(ground_truth, actual, eval_schema, curr_key)
        else:
            for string_evaluator_name in self.string_evaluators:
                string_evaluator = self.string_evaluators[string_evaluator_name]
                score = string_evaluator["instance"](
                    ground_truth,
                    actual,
                    eval_schema.get(string_evaluator_name, self.default_eval_config),
                )
                string_evaluator["total_strings_compared"] += 1
                self.result[f"{string_evaluator_name}.{curr_key}"] = score
                string_evaluator["total_score"] += score

    def compare_dicts(self, ground_truth_dict, actual_dict, eval_schema, curr_key = None):
        for key in ground_truth_dict:
            if key not in actual_dict:
                for string_evaluator_name in self.string_evaluators:
                    self.string_evaluators[string_evaluator_name]["total_strings_compared"] += 1
            else:
                next_key = f"{curr_key}.{key}" if curr_key is not None else key
                self.compare_values(
                    ground_truth_dict[key], actual_dict[key], eval_schema.get(key, {}), next_key
                )

    def compare_lists(self, ground_truth_list, actual_list, eval_schema, curr_key):
        if not eval_schema:
            eval_schema = [{}] * len(ground_truth_list)
        
        for i, (ground_truth_item, actual_item, schema) in enumerate(zip(ground_truth_list, actual_list, eval_schema)):
            self.compare_values(ground_truth_item, actual_item, schema, f"{curr_key}[{i}]")