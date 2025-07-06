from pydantic import BaseModel
from typing import Optional

class ExportRequest(BaseModel):
    format: str  # pdf, docx, html
    template: Optional[str] = "default"

class ExportResponse(BaseModel):
    download_url: str
    filename: str
    format: str