from jsonpath_ng import parse
from src.evaluators.string_evaluator import StringEvaluator

class MatchEvaluator:

    VALUE_NOT_FOUND = "Value Not Found"
    MATCH_EVAL_PREFIX = "match_evaluator"

    class Config(StringEvaluator.Config):
        pass

    def __init__(self, key: str, config = {}):
        self._key = key
        self._string_evaluator = StringEvaluator(config)

    def get_value(data, key):
        try:
            return data[key]
        except Exception as e:
            return Exception(e)

    def get_values(self, data):
        jsonpath_xpr = parse(self._key)
        matches = jsonpath_xpr.find(data)
        if len(matches) > 0:
            return matches[0].value
        return None


    def __call__(self, actual, ground_truth, **kwargs):
        result = {"output": 0}
        try:
            gt_value = self.get_values(ground_truth)
            actual_value = self.get_values(actual)
            if actual_value is None:
                result["error"] = self.VALUE_NOT_FOUND
                return result

            if self._string_evaluator(gt_value, actual_value):
                result['output'] = 1
            else:
                result['output'] = 0
        except Exception as e:
            result["error"] = f"{type(e)} - {str(e)}"

        return result


def load_match_evaluators(ground_truth, collumn_mapping: dict, config = {}):

    def load_recursive(ground_truth, config = {}, evaluators = {}, evaluator_config = {}, prev_key = None, prev_eval_output_key = None):
        if isinstance(ground_truth, dict):
            for k in ground_truth.keys():
                # add '' to the key to handle special characters
                updated_key = f"{prev_key}.'{k}'" if prev_key else f"'{k}'"
                # updated_eval_output_key removes the '' from the key
                updated_eval_output_key = f"{prev_eval_output_key}.{k}" if prev_eval_output_key else k
                evaluators, evaluator_config = load_recursive(ground_truth[k], config, evaluators, evaluator_config, updated_key, updated_eval_output_key)
        elif isinstance(ground_truth, list):
            for i, item in enumerate(ground_truth):
                evaluators, evaluator_config = load_recursive(item, config, evaluators, evaluator_config, f"{prev_key}[{i}]", f"{prev_eval_output_key}[{i}]")
        else:
            eval_name = f"{MatchEvaluator.MATCH_EVAL_PREFIX}.{prev_eval_output_key}"
            match_evaluator = MatchEvaluator(key=prev_key, config=config)
            evaluators[eval_name] = match_evaluator
            evaluator_config[eval_name] = collumn_mapping

        return evaluators, evaluator_config

    return load_recursive(ground_truth, config)
