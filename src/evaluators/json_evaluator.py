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
        self.compare_values(ground_truth, actual, eval_schema, None)
        for wrapper in self.eval_wrappers:
            self.result[f"{wrapper.name}.ratio"] = (
                wrapper.calculate_ratio()
            )

        return self.result

    def compare_values(self, ground_truth, actual, eval_schema, curr_key):
        if isinstance(ground_truth, dict):
            return self.compare_dicts(ground_truth, actual, eval_schema, curr_key)
        elif isinstance(ground_truth, list):
            return self.compare_lists(ground_truth, actual, eval_schema, curr_key)
        else:
            for wrapper in self.eval_wrappers:
                if actual is None:
                    score = 0
                else:
                    score = wrapper.instance(
                        ground_truth,
                        actual,
                        eval_schema.get(wrapper.name, None),
                    )
                self.add_score(wrapper, score, curr_key)

    def compare_dicts(self, ground_truth_dict, actual_dict, eval_schema, curr_key=None):
        for key in ground_truth_dict:
            # handle defaults if is None
            next_key = f"{curr_key}.{key}" if curr_key is not None else key
            actual = actual_dict.get(key, None) if actual_dict is not None else None
            curr_eval_schema = eval_schema.get(key, {}) if eval_schema is not None else {}
            
            self.compare_values(
                ground_truth_dict[key],
                actual,
                curr_eval_schema,
                next_key,
            )

    def compare_lists(self, ground_truth_list, actual_list, eval_schema, curr_key):
        for i in range(len(ground_truth_list)):
            # handle defaults if is None
            next_key = f"{curr_key}[{i}]" if curr_key is not None else f"[{i}]"
            try:
                actual = actual_list[i]
            except Exception:
                actual = None
            try:
                curr_eval_schema = eval_schema[i]
            except Exception:
                curr_eval_schema = {}

            self.compare_values(
                ground_truth_list[i],
                actual,
                curr_eval_schema,
                next_key,
            )

    def add_score(self, wrapper, score, key):
        wrapper.total_strings_compared += 1
        self.result[f"{wrapper.name}.{key}"] = score
        wrapper.total_score += score
