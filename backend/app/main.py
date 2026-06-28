from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings


def error_response(code: str, message: str, details: list | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", "HTTP_ERROR")
            message = exc.detail.get("message", "Request failed")
            details = exc.detail.get("details", [])
        else:
            code = "HTTP_ERROR"
            message = exc.detail if isinstance(exc.detail, str) else "Request failed"
            details = []
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code, message, details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "VALIDATION_ERROR",
                "Invalid import payload",
                exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_response("INTERNAL_SERVER_ERROR", "Internal server error"),
        )

    @app.get("/health")
    async def health() -> dict:
        return {
            "data": {
                "status": "ok",
                "service": settings.project_name,
            },
            "meta": {},
        }

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
