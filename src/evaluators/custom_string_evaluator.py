from src.evaluators.field_evaluator_base import FieldEvaluatorBase

class CustomStringEvaluator(FieldEvaluatorBase):

    class Config:
        IGNORE_DOLLAR_SIGN = "IGNORE_DOLLAR_SIGN"
        ADDITIONAL_MATCHES = "ADDITIONAL_MATCHES"
        IGNORE_DOTS = "IGNORE_DOTS"
        IGNORE_COMMAS = "IGNORE_COMMAS"
        IGNORE_PARENTHETHES = "IGNORE_PARENTHETHES"
        IGNORE_DASHES = "IGNORE_DASHES"

    def __init__(self, default_config = {}) -> None:
        self.default_config = default_config

    def __call__(self, ground_truth: str, actual: str, config: dict = None):
        if not config:
            config = self.default_config

        actual_processed = str(actual).lower()
        ground_truth_processed = str(ground_truth).lower()

        if config.get(self.Config.IGNORE_DOTS, False):
            actual_processed = actual_processed.replace('.', '')
            ground_truth_processed = ground_truth_processed.replace('.', '')

        if config.get(self.Config.IGNORE_COMMAS, False):
            actual_processed = actual_processed.replace(',', '')
            ground_truth_processed = ground_truth_processed.replace(',', '')

        if config.get(self.Config.IGNORE_DASHES, False):
            actual_processed = actual_processed.replace('-', '')
            ground_truth_processed = ground_truth_processed.replace('-', '')
        
        if config.get(self.Config.IGNORE_PARENTHETHES, False):
            actual_processed = actual_processed.replace('(', '')
            ground_truth_processed = ground_truth_processed.replace('(', '')
            actual_processed = actual_processed.replace(')', '')
            ground_truth_processed = ground_truth_processed.replace(')', '')

        if config.get(self.Config.IGNORE_DOLLAR_SIGN, False):
            # Remove leading dollar signs from both strings
            ground_truth_processed = ground_truth_processed.lstrip("$")
            actual_processed = actual_processed.lstrip("$")

        additional_matches = config.get(
            self.Config.ADDITIONAL_MATCHES, []
        )
        additional_matches.append(ground_truth_processed)

        if actual_processed in additional_matches:
            return 1

        return 0

