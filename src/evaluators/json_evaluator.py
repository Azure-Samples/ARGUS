from src.evaluators.custom_string_evaluator import CustomStringEvaluator
from src.evaluators.fuzz_string_evaluator import FuzzStringEvaluator


class JsonEvaluator:

    class Config(CustomStringEvaluator.Config):
        pass

    class StringEvaluatorWrapper:
        def __init__(self, name, evaluator_instance, default_eval_config={}):
            self.name = name
            self.instance = evaluator_instance
            self.total_strings_compared = 0
            self.total_score = 0
            self.default_eval_config = default_eval_config

        def calculate_ratio(self):
            return (
                self.total_score / self.total_strings_compared
                if self.total_strings_compared > 0
                else 0
            )

    def __init__(
        self,
        default_eval_config={
            "CustomStringEvaluator": {},
            "FuzzStringEvaluator": {},
        },
    ):
        self.default_eval_config = default_eval_config
        self.result = {}
        self.string_evaluators = [
            self.StringEvaluatorWrapper(
                "CustomStringEvaluator",
                CustomStringEvaluator(),
                default_eval_config["CustomStringEvaluator"],
            ),
            self.StringEvaluatorWrapper(
                "FuzzStringEvaluator",
                FuzzStringEvaluator(),
                default_eval_config["FuzzStringEvaluator"],
            ),
        ]

    def __call__(self, ground_truth, actual, eval_schema={}):
        self.compare_dicts(ground_truth, actual, eval_schema)
        for score_calculator in self.string_evaluators:
            self.result[f"{score_calculator.name}.ratio"] = (
                score_calculator.calculate_ratio()
            )

        return self.result

    def compare_values(self, ground_truth, actual, eval_schema, curr_key):
        if isinstance(ground_truth, dict) and isinstance(actual, dict):
            return self.compare_dicts(ground_truth, actual, eval_schema, curr_key)
        elif isinstance(ground_truth, list) and isinstance(actual, list):
            return self.compare_lists(ground_truth, actual, eval_schema, curr_key)
        else:
            for string_evaluator in self.string_evaluators:
                score = string_evaluator.instance(
                    ground_truth,
                    actual,
                    eval_schema.get(string_evaluator.name, self.default_eval_config),
                )
                string_evaluator.total_strings_compared += 1
                self.result[f"{string_evaluator.name}.{curr_key}"] = score
                string_evaluator.total_score += score

    def compare_dicts(self, ground_truth_dict, actual_dict, eval_schema, curr_key=None):
        for key in ground_truth_dict:
            if key not in actual_dict:
                for string_evaluator in self.string_evaluators:
                    string_evaluator.total_strings_compared += 1
            else:
                next_key = f"{curr_key}.{key}" if curr_key is not None else key
                self.compare_values(
                    ground_truth_dict[key],
                    actual_dict[key],
                    eval_schema.get(key, {}),
                    next_key,
                )

    def compare_lists(self, ground_truth_list, actual_list, eval_schema, curr_key):
        if not eval_schema:
            eval_schema = [{}] * len(ground_truth_list)

        for i, (ground_truth_item, actual_item, schema) in enumerate(
            zip(ground_truth_list, actual_list, eval_schema)
        ):
            self.compare_values(
                ground_truth_item, actual_item, schema, f"{curr_key}[{i}]"
            )
