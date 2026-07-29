from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def ok(data: Any = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"data": data, "error": None}),
    )


def fail(code: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"data": None, "error": {"code": code, "message": message}}),
    )
