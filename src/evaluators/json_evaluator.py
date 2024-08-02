from src.evaluators.custom_string_evaluator import CustomStringEvaluator
from src.evaluators.fuzz_string_evaluator import FuzzStringEvaluator


class JsonEvaluator:

    class FieldEvaluatorWrapper:
        def __init__(self, evaluator_instance):
            self.name = evaluator_instance.__class__.__name__
            self.instance = evaluator_instance
            self.total_strings_compared = 0
            self.total_score = 0

        def calculate_ratio(self):
            return (
                self.total_score / self.total_strings_compared
                if self.total_strings_compared > 0
                else 0
            )

    def __init__(
        self,
        field_evaluators: list = [CustomStringEvaluator(), FuzzStringEvaluator()],
    ):
        self.eval_wrappers = []
        for evaluator in field_evaluators:
            self.eval_wrappers.append(self.FieldEvaluatorWrapper(evaluator))

        self.result = {}

    def __call__(self, ground_truth, actual, eval_schema={}):
        self.compare_dicts(ground_truth, actual, eval_schema)
        for wrapper in self.eval_wrappers:
            self.result[f"{wrapper.name}.ratio"] = (
                wrapper.calculate_ratio()
            )

        return self.result

    def compare_values(self, ground_truth, actual, eval_schema, curr_key):
        if isinstance(ground_truth, dict) and isinstance(actual, dict):
            return self.compare_dicts(ground_truth, actual, eval_schema, curr_key)
        elif isinstance(ground_truth, list) and isinstance(actual, list):
            return self.compare_lists(ground_truth, actual, eval_schema, curr_key)
        else:
            for wrapper in self.eval_wrappers:
                score = wrapper.instance(
                    ground_truth,
                    actual,
                    eval_schema.get(wrapper.name, None),
                )
                wrapper.total_strings_compared += 1
                self.result[f"{wrapper.name}.{curr_key}"] = score
                wrapper.total_score += score

    def compare_dicts(self, ground_truth_dict, actual_dict, eval_schema, curr_key=None):
        for key in ground_truth_dict:
            if key not in actual_dict:
                for string_evaluator in self.eval_wrappers:
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
