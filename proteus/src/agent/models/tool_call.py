from typing import Any, Dict
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """
    Represents a tool call with its name and parameters.
    """

    tool_name: str = Field(..., description="The name of the tool to call.")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the tool call."
    )