from pydantic import BaseModel


class Config(BaseModel):
    max_images: int = 10
    gpt_vision_limit_mb: int = 20
