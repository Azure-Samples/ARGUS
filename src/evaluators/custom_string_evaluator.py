
class CustomStringEvaluator:

    class Config:
        IGNORE_DOLLAR_SIGN = "ignore_dollar_sign"
        ADDITIONAL_MATCHES = "additional_matches"
        IGNORE_DOTS = "ignore_dots"
        IGNORE_COMAS = "ignore_comas"
        IGNORE_PARENTHETHIS = "ignore_parenthesis"
        IGNORE_DASHES = "ignore_dashes"


    def __call__(self, ground_truth: str, actual: str, config: dict = {}):
        actual_processed = str(actual).lower()
        ground_truth_processed = str(ground_truth).lower()

        if config.get(self.Config.IGNORE_DOTS, False):
            actual_processed = actual_processed.replace('.', '')
            ground_truth_processed = ground_truth_processed.replace('.', '')

        if config.get(self.Config.IGNORE_COMAS, False):
            actual_processed = actual_processed.replace(',', '')
            ground_truth_processed = ground_truth_processed.replace(',', '')

        if config.get(self.Config.IGNORE_DASHES, False):
            actual_processed = actual_processed.replace('-', '')
            ground_truth_processed = ground_truth_processed.replace('-', '')
        
        if config.get(self.Config.IGNORE_PARENTHETHIS, False):
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
            return True

        return False

