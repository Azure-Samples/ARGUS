# Evaluating ARGUS
### 

> This notebook illustrate how to double check a first run of the Solution against an expected output.


### Notebook instructions

Create a .env file in the notebook folder with these keys:

DOCUMENT_INTELLIGENCE_ENDPOINT=
DOCUMENT_INTELLIGENCE_KEY=
AZURE_OPENAI_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_MODEL_DEPLOYMENT_NAME=

> Notes:
> - The document-intelligence resource needs to use the markdown preview feature (limited regions: West EU and East US at the moment). 
> - The Azure OpenAI model needs to be vision capable i.e. GPT-4T-0125, 0409 or Omni

Install requirements.txt provided.


### Notebook flow

1. Run ARGUS on an Invoice sample from the demo/default-dataset folder
2. Saves the output in json format
3. Run evaluation using LLM as a judge without ground truth data
4. Run evaluation using ground truth

### Evaluation using ground truth data

This approach provides a way to evaluate actual JSON against ground truth data.
The ground truth data suppose to be manually verified by the human and adhere to the schema provided to Argus solution.
The end result is a combination of total summary (ratio) with detailed information of comparison for each field. The output is a JSON file stored in [outputs folder](./outputs).
[Json evaluator](../src/evaluators/json_evaluator.py) can use different mechanisms of comparing string values. For now we provide configurable [custom string evaluator](src/evaluators/custom_string_evaluator.py) and [fuzzy match evaluator](src/evaluators/fuzz_string_evaluator.py). It can be expanded to support other string evaluation techniques that might include LLM calls in combination with ground truth.
The ratio is calculated based on the total number of strings being matched between ground truth and actual divided by the total number of values being compared.


#### Evaluation data

The [prompt flow evaluation API](https://microsoft.github.io/promptflow/reference/python-library-reference/promptflow-evals/promptflow.evals.evaluate.html) is used for evaluating the ground truth against the actual data. The `evaluate` function accepts the evaluation data in the form of `jsonl` and contains the keys `ground_truth`, `actual`, and optionally `eval_schema`. The notebook compiles the ground truth, actual and evaluation schema data into the jsonl format using the `compile_jsonl` function.

The notebook will create the actual data. To update the [ground truth](../demo/default-dataset/ground_truth.json) and evaluation [schema](../), modify the respective files directly.


#### Evaluation schema

The [evaluation schema](../demo/default-dataset/evaluation_schema.json) is optional and used by the `JsonEvaluator` to configure how to evaluate each field in the ground truth with the actual value. If a field is not present in the evaluation schema that is present in the ground truth, then the default evaluators will be used. By default, each field will get a `CustomStringEvaluator` and `FuzzyMatchEvaluator`. If no default configuration and no evaluation schema provided for `CustomStringEvalaution` the evaluator will use exact match for value comparisons ignoring the case.

Each field evaluator must implement the following method with the same arguments:

```python
def __call__(self, ground_truth: str, actual: str, config: dict = None) -> int:
    # implementation here
```

Example of default configuration for `CustomStringEvaluator`. This configuration will be applied to all fields unless specified in evaluation schema for a particular field


```python
evaluators = [
    CustomStringEvaluator({
        CustomStringEvaluator.Config.IGNORE_COMMAS: True
    })
]
json_evaluator = JsonEvaluator(evaluators)
```

```python
ground_truth = {
    "name": "Smith, Bob",
    "phone": {
        "home_phone_number": "(555) 555-5555",
        "work_phone_number": "(555) 123-1234"
    },
    "address": "1234 Fake Street, FakeCity",
    "is_employed": "True"
}
```

```python
# evaluation_schema.json
# Each field will get CustomStringEvaluator evaluatation with commas ignored unless the configuration is provided. The evaluation schema will override the default values.

evaluation_schema = {
    # name is not provided so the default will be used, commas ignored
    "phone": {
        "home_phone_number": { # specific config for this field
            "CustomStringEvaluator": {
                "IGNORE_IGNORE_PARENTHETHES": "True",
                "IGNORE_DASHES": "True"
            }
        },
        "work_phone_number": {} # default config will be used for CustomStringEvaluator
    },
    "address": {}, # default config will be used for CustomStringEvaluator
    "is_employed": {
        "CustomStringEvaluator": {
            "ADDITIONAL_MATCHES": ["yes", "yup", "true"], # additional values that will be marked correct if any of these match the actual value
        }
    }
}
```

```python 
actual = {
    "name": "Smith Bob", # correct, commas are ignored by default config for all fields
    "phone": {
        "home_phone_number": "555 5555555", # correct, parentheses and dashes are ignored by evaluation shcema for this field
        "work_phone_number": "555 1231234," # incorrect, parentheses and dashes are NOT ignored for this field
    },
    "address": "1234 Fake Street, FakeCity", # correct, exact match
    "is_employed": "yes" # correct, has a matches in additonal matches
}
```

```python
result = json_evaluator(ground_truth, actual, evaluation_schema)
# result:
# {
#     'CustomStringEvaluator.name': 1,
#     'CustomStringEvaluator.phone.home_phone_number': 1,
#     'CustomStringEvaluator.phone.work_phone_number': 0,
#     'CustomStringEvaluator.address': 1,
#     'CustomStringEvaluator.is_employed': 1,
#     'CustomStringEvaluator.ratio': 0.8  # 4 correct fields / 5 total fields 
# }
```