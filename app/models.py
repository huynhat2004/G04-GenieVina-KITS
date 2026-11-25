from enum import Enum
from typing import Annotated, Generic, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator


class SignupMethod(str, Enum):
    EMAIL = 'EMAIL'
    GOOGLE = 'GOOGLE'
    MICROSOFT = 'MICROSOFT'


Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Country = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^[A-Z]{2}$')]


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'example': {
        'customerCode': 'DEMO-001', 'name': 'Khách giả lập 001', 'country': 'VN',
        'signupMethod': 'EMAIL', 'signedUpAt': '2026-11-24T09:00:00+07:00',
    }})
    customerCode: Code
    name: Name
    country: Country
    signupMethod: SignupMethod
    signedUpAt: AwareDatetime


class CustomerPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customerCode: Code | None = None
    name: Name | None = None
    country: Country | None = None
    signupMethod: SignupMethod | None = None
    signedUpAt: AwareDatetime | None = None

    @model_validator(mode='after')
    def require_nonempty_changes(self):
        if not self.model_fields_set:
            raise ValueError('Provide at least one field to update')
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Customer fields cannot be null')
        return self


class CustomerOut(BaseModel):
    id: int
    customerCode: str
    name: str
    country: str
    signupMethod: SignupMethod
    signedUpAt: AwareDatetime


class CustomerPage(BaseModel):
    items: list[CustomerOut]
    page: int
    size: int
    total: int
    totalPages: int


T = TypeVar('T')


class Envelope(BaseModel, Generic[T]):
    status: int
    message: str = 'success'
    data: T


class ValidationIssue(BaseModel):
    field: str
    message: str


class ValidationDetails(BaseModel):
    errors: list[ValidationIssue]


class ErrorEnvelope(BaseModel):
    status: int
    message: str
    data: ValidationDetails | None = None


class Principal(BaseModel):
    id: int
    role: str
