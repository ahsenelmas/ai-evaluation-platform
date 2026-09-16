from pydantic import BaseModel


class LangfuseStatusResponse(BaseModel):
    configured: bool
    connected: bool
    host: str
    message: str
