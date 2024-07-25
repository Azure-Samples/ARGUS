from src.evaluators.string_evaluator import StringEvaluator


class JsonEvaluator:

    class Config(StringEvaluator.Config):
        pass

    def __init__(self, config = {}):
        # self.config = config
        self.string_evaluator = StringEvaluator(config)
        self.wrong_answers = []
        self.total_strings_compared = 0
        self.total_matches = 0

    def __call__(self, ground_truth, actual):
        self.compare_dicts(ground_truth, actual)
        ratio = (
            self.total_matches / self.total_strings_compared
            if self.total_strings_compared > 0
            else 0
        )

        return ratio

    def compare_values(self, ground_truth, actual):
        if isinstance(ground_truth, dict) and isinstance(actual, dict):
            return self.compare_dicts(ground_truth, actual)
        elif isinstance(ground_truth, list) and isinstance(actual, list):
            return self.compare_lists(ground_truth, actual)
        elif isinstance(ground_truth, str) and isinstance(actual, str):
            strings_considered_equal = self.string_evaluator(ground_truth, actual)
            self.total_strings_compared += 1
            if strings_considered_equal:
                self.total_matches += 1
        else:
            return False

    def compare_dicts(self, ground_truth_dict, actual_dict):
        for key in ground_truth_dict:
            if key not in actual_dict:
                self.total_strings_compared += 1
            else:
                try:
                    actual_value = actual_dict[key]
                except Exception as e:
                    actual_value = None
                self.compare_values(ground_truth_dict[key], actual_value)
                    

    def compare_lists(self, ground_truth_list, actual_list):
        for ground_truth_item, actual_item in zip(ground_truth_list, actual_list):
            self.compare_values(ground_truth_item, actual_item)
