import enum
import re
import uuid
from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.module import LineItemFormat, SummaryMethod


# ── Module schemas ─────────────────────────────────────────────────────────────


class ConditionalFormatOperator(str, enum.Enum):
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    eq = "eq"
    neq = "neq"


class ConditionalNumberFormat(str, enum.Enum):
    number = "number"
    currency = "currency"
    percentage = "percentage"


class ConditionalFormatStyle(BaseModel):
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    number_format: Optional[ConditionalNumberFormat] = None
    icon: Optional[str] = None

    @field_validator("background_color", "text_color")
    @classmethod
    def validate_hex_color(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        color = value.strip()
        if color == "":
            return None
        if re.fullmatch(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", color) is None:
            raise ValueError("must be a hex color like #RRGGBB")
        return color.lower()

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        icon = value.strip()
        if icon == "":
            return None
        if len(icon) > 16:
            raise ValueError("icon must be 16 characters or less")
        return icon


class ConditionalFormatRule(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: Optional[str] = None
    enabled: bool = True
    operator: ConditionalFormatOperator = ConditionalFormatOperator.gt
    value: Union[bool, float, str]
    style: ConditionalFormatStyle = Field(default_factory=ConditionalFormatStyle)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        name = value.strip()
        if name == "":
            return None
        return name

    @model_validator(mode="after")
    def validate_has_style(self) -> "ConditionalFormatRule":
        has_style = any(
            [
                self.style.background_color is not None,
                self.style.text_color is not None,
                self.style.bold is not None,
                self.style.italic is not None,
                self.style.number_format is not None,
                self.style.icon is not None,
            ]
        )
        if not has_style:
            raise ValueError(
                "style must define at least one of background_color, text_color, bold, "
                "italic, number_format, or icon"
            )
        return self


class ModuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    conditional_format_rules: List[ConditionalFormatRule] = Field(default_factory=list)


class ModuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditional_format_rules: Optional[List[ConditionalFormatRule]] = None


class ModuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    model_id: uuid.UUID
    conditional_format_rules: List[ConditionalFormatRule] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModuleWithLineItemsResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    model_id: uuid.UUID
    conditional_format_rules: List[ConditionalFormatRule] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    line_items: List["LineItemResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ── LineItem schemas ───────────────────────────────────────────────────────────

class LineItemCreate(BaseModel):
    name: str
    format: LineItemFormat = LineItemFormat.number
    formula: Optional[str] = None
    summary_method: SummaryMethod = SummaryMethod.sum
    applies_to_dimensions: Optional[List[uuid.UUID]] = None
    sort_order: int = 0
    conditional_format_rules: List[ConditionalFormatRule] = Field(default_factory=list)


class LineItemUpdate(BaseModel):
    name: Optional[str] = None
    format: Optional[LineItemFormat] = None
    formula: Optional[str] = None
    summary_method: Optional[SummaryMethod] = None
    applies_to_dimensions: Optional[List[uuid.UUID]] = None
    sort_order: Optional[int] = None
    conditional_format_rules: Optional[List[ConditionalFormatRule]] = None


class LineItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    module_id: uuid.UUID
    format: LineItemFormat
    formula: Optional[str]
    summary_method: SummaryMethod
    applies_to_dimensions: Optional[List[uuid.UUID]]
    sort_order: int
    conditional_format_rules: List[ConditionalFormatRule] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Allow forward reference resolution
ModuleWithLineItemsResponse.model_rebuild()
