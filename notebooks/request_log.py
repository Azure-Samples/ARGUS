from datetime import datetime
import json

class RequestLog:
    def __init__(self, request_id, request_filename, request_timestamp, total_time_seconds, classification, accuracy, model_output):
        """
        Initialize the RequestLog Record.
        
        :param request_filename: str - The name of the file associated with the request.
        :param request_timestamp: datetime - The timestamp when the request was made.
        :param total_time_seconds: float - Total processing time in seconds.
        :param classification: float - Classification decided by the model
        :param accuracy: float - The ration between the data seen in the imgaes / doc vs the one filled in the output schema.
        :param model_output: str - The textual output from the model.
        """
        self.id = request_id
        self.request_filename = request_filename
        self.request_timestamp = request_timestamp
        self.total_time_seconds = total_time_seconds
        self.classification = classification
        self.accuracy = accuracy
        self.model_output = model_output

    def to_dict(self):
        """
        Converts the log record to a dictionary for easier serialization or processing.
        
        :return: dict - A dictionary representation of the log record.
        """
        return {
            'id': self.id,
            'request_filename': self.request_filename,
            'request_timestamp': self.request_timestamp.isoformat(),
            'total_time_seconds': self.total_time_seconds,
            'classification': self.classification,
            'accuracy': self.accuracy,
            'model_output': self.model_output
        }

    def to_json(self):
        """
        Converts the log record to a JSON string.
        
        :return: str - A JSON string representation of the log record.
        """
        return json.dumps(self.to_dict())

    def __str__(self):
        """
        String representation of the SystemLogRecord.
        
        :return: str - A human-readable string representation of the log record.
        """
        return f"RequestLog(Request Filename: {self.request_filename}, " \
               f"Timestamp: {self.request_timestamp}, " \
               f"Processing Time: {self.total_time_seconds} seconds, " \
               f"Classification: {self.classification} seconds, " \
               f"Accuracy: {self.accuracy} seconds, " \
               f"Model Output: {self.model_output})"
