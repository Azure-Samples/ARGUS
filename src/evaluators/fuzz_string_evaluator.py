from thefuzz import fuzz 

class FuzzStringEvaluator:

    def __call__(self, ground_truth: str, actual: str, config: dict = {}):
        return fuzz.partial_token_set_ratio(ground_truth,actual)/100.0

