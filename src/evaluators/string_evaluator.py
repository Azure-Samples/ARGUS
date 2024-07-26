import re


class StringEvaluator:

    class Config:
        IGNORE_DOLLAR_SIGN = "ignore_dollar_sign"
        ADDITIONAL_MATCHES = "additional_matches"
        IGNORE_DOTS = "ignore_dots"
        IGNORE_COMAS = "ignore_comas"


    def __init__(self, config: dict = {}):
        self.config = config

    def __call__(self, ground_truth: str, actual: str):
        actual_processed = str(actual).lower()
        ground_truth_processed = str(ground_truth).lower()

        if self.config.get(self.Config.IGNORE_DOTS, True):
            actual_processed = actual_processed.replace('.', '')
            ground_truth_processed = ground_truth_processed.replace('.', '')

        if self.config.get(self.Config.IGNORE_COMAS, True):
            actual_processed = actual_processed.replace(',', '')
            ground_truth_processed = ground_truth_processed.replace(',', '')

        if self.config.get(self.Config.IGNORE_DOLLAR_SIGN, True):
            # Remove leading dollar signs from both strings
            ground_truth_processed = ground_truth_processed.lstrip("$")
            actual_processed = actual_processed.lstrip("$")

        additional_matches = self.config.get(
            self.Config.ADDITIONAL_MATCHES, []
        )
        additional_matches.append(ground_truth_processed)

        if actual_processed in additional_matches:
            return True

        return False

