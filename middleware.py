"""
Custom Middleware for X-Student-ID Header
Student ID: BSCS24121
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class StudentIDMiddleware(BaseHTTPMiddleware):
    """Middleware that adds X-Student-ID header to every response."""
    
    # YOUR ACTUAL STUDENT ID HERE
    STUDENT_ID = "12345"  # Replace with your actual student ID
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Student-ID"] = self.STUDENT_ID
        return response