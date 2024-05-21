from pydantic import BaseModel


class Config(BaseModel):
    max_images: int = 3
    gpt_vision_limit_mb: int = 20
