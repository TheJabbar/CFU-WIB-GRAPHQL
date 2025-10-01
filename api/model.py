from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatHistoryInput(BaseModel):
    chat_history: Optional[str] = None

class QueryInput(ChatHistoryInput):
    query: str

class ChatResponse(BaseModel):
    output: str
    chart: Optional[str] = None
    chart_type: Optional[str] = None
    chart_library: Optional[str] = None
    data_columns: Optional[List[str]] = None
    data_rows: Optional[List[Dict[str, Any]]] = None