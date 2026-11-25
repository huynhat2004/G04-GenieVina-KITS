"""REST API thống kê (Thành viên C) – dùng chung auth, DB và định dạng phản hồi của backend.

Đăng ký trong app/main.py:
    from app.metrics_api import router as metrics_router
    app.include_router(metrics_router)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import Database, require_roles
from app.metrics_service import (
    InvalidRangeError,
    MetricsService,
    PostgresMetricsRepository,
    parse_range,
)
from pydantic import BaseModel, Field

from app.models import Envelope, ErrorEnvelope


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


# --------------------------------- endpoints -------------------------------- #
router = APIRouter(
    prefix="/api/metrics",
    tags=["Metrics"],
    dependencies=[Depends(require_roles("ADMIN", "OPERATOR", "VIEWER"))],
    responses={
        code: {"model": ErrorEnvelope, "description": text}
        for code, text in {
            400: "from/to thiếu, sai định dạng, from > to hoặc vượt 366 ngày",
            401: "Thiếu hoặc sai JWT",
            403: "Không đủ quyền",
            503: "Database không khả dụng",
        }.items()
    },
)

FROM_Q = Query(..., alias="from", description="Ngày bắt đầu (YYYY-MM-DD), bao gồm", examples=["2026-10-26"])
TO_Q = Query(..., description="Ngày kết thúc (YYYY-MM-DD), bao gồm", examples=["2026-11-24"])


def _period(from_value: str, to_value: str):
    try:
        return parse_range(from_value, to_value)
    except InvalidRangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/summary",
    response_model=Envelope[SummaryData],
    summary="Tổng hợp chỉ số 1·2·3 (mọi vai trò)",
    description="Khách trả phí (lần đầu / thanh toán lại), đăng ký mới + tăng trưởng "
    "so với kỳ trước cùng số ngày, doanh thu + trung bình ngày, hoàn tiền.",
)
def metrics_summary(connection: Database, from_: str = FROM_Q, to: str = TO_Q):
    period = _period(from_, to)
    data = MetricsService(PostgresMetricsRepository(connection)).summary(period)
    return {"status": 200, "message": "success", "data": data}


@router.get(
    "/daily",
    response_model=Envelope[DailyData],
    summary="Doanh thu theo ngày – chỉ số 4 (mọi vai trò)",
    description="Doanh thu từng ngày trong kỳ (giờ Việt Nam), ngày không có dữ liệu ghi 0.",
)
def metrics_daily(connection: Database, from_: str = FROM_Q, to: str = TO_Q):
    period = _period(from_, to)
    data = MetricsService(PostgresMetricsRepository(connection)).daily(period)
    return {"status": 200, "message": "success", "data": data}