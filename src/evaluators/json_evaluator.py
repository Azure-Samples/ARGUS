from src.evaluators.string_evaluator import StringEvaluator


class JsonEvaluator:

    class Config(StringEvaluator.Config):
        pass

    def __init__(self, default_eval_config = {}):
        self.default_eval_config=default_eval_config
        self.string_evaluator = StringEvaluator()
        self.wrong_answers = []
        self.total_strings_compared = 0
        self.total_matches = 0

    def __call__(self, ground_truth, actual, eval_schema={}):
        self.compare_dicts(ground_truth, actual,eval_schema)
        ratio = (
            self.total_matches / self.total_strings_compared
            if self.total_strings_compared > 0
            else 0
        )

        return ratio

    def compare_values(self, ground_truth, actual, eval_schema):
        if isinstance(ground_truth, dict) and isinstance(actual, dict):
            return self.compare_dicts(ground_truth, actual, eval_schema)
        elif isinstance(ground_truth, list) and isinstance(actual, list):
            return self.compare_lists (ground_truth, actual, eval_schema)
        else:
            strings_considered_equal = self.string_evaluator(ground_truth, actual,eval_schema.get("MatchEvaluator", self.default_eval_config))
            self.total_strings_compared += 1
            if strings_considered_equal:
                self.total_matches += 1

    def compare_dicts(self, ground_truth_dict, actual_dict, eval_schema):
        for key in ground_truth_dict:
            if key not in actual_dict:
                self.total_strings_compared += 1
            else:
                self.compare_values (ground_truth_dict[key], actual_dict[key], eval_schema.get(key, {}))
                    

    def compare_lists(self, ground_truth_list, actual_list, eval_schema):
        for ground_truth_item, actual_item in zip(ground_truth_list, actual_list):
            self.compare_values(ground_truth_item, actual_item, eval_schema)
