import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.customers import router
from app.metrics_api import router as metrics_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()  # Fail startup rather than run with an empty JWT secret.
    yield


app = FastAPI(title='Genie Vina – Customer API', version='1.0.0', lifespan=lifespan,
              description='Phần A: CRUD khách hàng. Bearer JWT; ADMIN / OPERATOR / VIEWER.')
app.include_router(router)
app.include_router(metrics_router)


def error(status, message, data=None, headers=None):
    return JSONResponse(status_code=status, content={'status': status, 'message': message, 'data': data}, headers=headers)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error(exc.status_code, str(exc.detail), headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo raw request bodies or sensitive input in validation errors.
    issues = [{'field': '.'.join(map(str, issue['loc'])), 'message': issue['msg']} for issue in exc.errors()]
    return error(400, 'Invalid input', {'errors': issues})


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, exc: psycopg.Error):
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return error(409, 'Customer code already exists')
    if isinstance(exc, psycopg.errors.ForeignKeyViolation):
        return error(409, 'Customer has related orders or AI results and cannot be deleted')
    if isinstance(exc, psycopg.errors.CheckViolation):
        return error(409, 'Customer signup date conflicts with existing events')
    if isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)):
        logger.error('Database unavailable: %s', type(exc).__name__)
        return error(503, 'Database unavailable')
    logger.error('Database operation failed (SQLSTATE=%s)', exc.sqlstate)
    return error(500, 'Internal server error')


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error('Unhandled API error: %s', type(exc).__name__)
    return error(500, 'Internal server error')


# Validation is normalized to HTTP 400; keep generated OpenAPI consistent.
original_openapi = app.openapi


def customer_openapi():
    schema = original_openapi()
    for path, operations in schema['paths'].items():
        if path.startswith(('/api/customers', '/api/metrics')):
            for operation in operations.values():
                if isinstance(operation, dict):
                    operation.get('responses', {}).pop('422', None)
    return schema


app.openapi = customer_openapi
