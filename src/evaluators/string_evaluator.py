import re


class StringEvaluator:

    class Config:
        IGNORE_DOLLAR_SIGN = "ignore_dollar_sign"
        ADDITIONAL_MATCHES = "additional_matches"
        IGNORE_PUNCTUATION_MARKS = "ignore_punctuation_marks"


    def __init__(self, config: dict = {}):
        self.config = config

    def __call__(self, ground_truth: str, actual: str):
        actual_processed = str(actual).lower()
        ground_truth_processed = str(ground_truth).lower()

        if self.config.get(self.Config.IGNORE_PUNCTUATION_MARKS, True):
            actual_processed = self.remove_punctuation(actual_processed)
            ground_truth_processed = self.remove_punctuation(
                ground_truth_processed
            )

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

    def remove_punctuation(self, sentence):
        # Regular expression to match numbers
        number_pattern = re.compile(r'\d+')
        
        # Split the sentence into words
        words = sentence.split()
        
        # Process each word
        processed_words = []
        for word in words:
            if number_pattern.search(word):
                # If the word contains a number, keep it as is
                processed_words.append(word)
            else:
                # Remove punctuation from the word
                processed_word = re.sub(r'[^\w\s]', '', word)
                processed_words.append(processed_word)
        
        # Join the processed words back into a sentence
        return ' '.join(processed_words)
