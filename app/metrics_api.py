"""REST API thống kê (Thành viên C) – FastAPI, tự sinh Swagger tại /docs.

Gắn vào app chính:
    from app.metrics_api import router as metrics_router
    app.include_router(metrics_router)

Hai hàm get_db / require_member bên dưới là ĐIỂM NỐI với phần của thành viên D
(JWT, phân quyền) và kết nối DB chung: thay bằng bản của nhóm hoặc dùng
app.dependency_overrides[...]. Mọi vai trò (ADMIN/OPERATOR/VIEWER) đều được xem thống kê.
"""
from __future__ import annotations

import os
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.metrics_service import (
    InvalidRangeError,
    MetricsService,
    PostgresMetricsRepository,
    parse_range,
)


# ----------------------------- điểm nối với nhóm ---------------------------- #
def get_db() -> Iterator:
    """Mở kết nối PostgreSQL (thay bằng hàm dùng chung của nhóm nếu có)."""
    import psycopg

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        yield conn


def require_member():
    """Thay bằng dependency JWT của thành viên D (cho phép ADMIN/OPERATOR/VIEWER)."""
    raise HTTPException(status_code=401, detail="Chưa cấu hình xác thực JWT")


# ------------------------------ schema Swagger ------------------------------ #
class PeriodOut(BaseModel):
    from_: str = Field(alias="from", examples=["2026-10-26"])
    to: str = Field(examples=["2026-11-24"])
    days: int = Field(examples=[30])


class PayingCustomersOut(BaseModel):
    total: int
    firstTime: int
    returning: int


class NewSignupsOut(BaseModel):
    count: int
    previousCount: int
    growthRate: float | None = Field(description="% so với kỳ trước; null nếu kỳ trước = 0")


class RevenueOut(BaseModel):
    total: float
    averagePerDay: float


class RefundsOut(BaseModel):
    totalAmount: float
    orderCount: int


class SummaryData(BaseModel):
    period: PeriodOut
    previousPeriod: PeriodOut
    payingCustomers: PayingCustomersOut
    newSignups: NewSignupsOut
    revenue: RevenueOut
    refunds: RefundsOut


class DailyItem(BaseModel):
    date: str
    revenue: float


class DailyData(BaseModel):
    period: PeriodOut
    items: list[DailyItem]


class SummaryResponse(BaseModel):
    status: int = 200
    message: str = "success"
    data: SummaryData


class DailyResponse(BaseModel):
    status: int = 200
    message: str = "success"
    data: DailyData


# --------------------------------- endpoints -------------------------------- #
router = APIRouter(prefix="/api/metrics", tags=["Thống kê"])

FROM_Q = Query(..., alias="from", description="Ngày bắt đầu (YYYY-MM-DD), bao gồm", examples=["2026-10-26"])
TO_Q = Query(..., description="Ngày kết thúc (YYYY-MM-DD), bao gồm", examples=["2026-11-24"])
ERRORS = {
    400: {"description": "from/to sai định dạng, from > to hoặc vượt 366 ngày"},
    401: {"description": "Thiếu hoặc sai JWT"},
    403: {"description": "Không đủ quyền"},
}


def _period(from_value: str, to_value: str):
    try:
        return parse_range(from_value, to_value)
    except InvalidRangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/summary",
    response_model=SummaryResponse,
    responses=ERRORS,
    summary="Tổng hợp chỉ số 1·2·3",
    description="Khách trả phí (lần đầu / thanh toán lại), đăng ký mới + tăng trưởng "
    "so với kỳ trước cùng số ngày, doanh thu + trung bình ngày, hoàn tiền.",
)
def metrics_summary(
    from_: str = FROM_Q, to: str = TO_Q, conn=Depends(get_db), _member=Depends(require_member)
):
    period = _period(from_, to)
    data = MetricsService(PostgresMetricsRepository(conn)).summary(period)
    return {"status": 200, "message": "success", "data": data}


@router.get(
    "/daily",
    response_model=DailyResponse,
    responses=ERRORS,
    summary="Doanh thu theo ngày (chỉ số 4)",
    description="Doanh thu từng ngày trong kỳ (giờ Việt Nam), ngày không có dữ liệu ghi 0.",
)
def metrics_daily(
    from_: str = FROM_Q, to: str = TO_Q, conn=Depends(get_db), _member=Depends(require_member)
):
    period = _period(from_, to)
    data = MetricsService(PostgresMetricsRepository(conn)).daily(period)
    return {"status": 200, "message": "success", "data": data}