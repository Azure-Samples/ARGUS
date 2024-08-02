from abc import ABC, abstractmethod

class FieldEvaluatorBase(ABC):
    
    @abstractmethod
    def __call__(self, ground_truth: str, actual: str, config: dict = {}) -> int:
        raise NotImplementedError
