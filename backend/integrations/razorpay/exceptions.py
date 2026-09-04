"""
Razorpay Integration Exceptions
Isolated exception hierarchy for Razorpay API calls and Webhook processing.
"""

class RazorpayIntegrationError(Exception):
    """Base exception for all Razorpay integration errors."""
    def __init__(self, message: str, status_code: int = 500, raw_error: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.raw_error = raw_error or {}

class RazorpayAuthenticationError(RazorpayIntegrationError):
    """Raised when authentication with Razorpay fails (401 Unauthorized)."""
    def __init__(self, message: str = "Invalid Razorpay Key ID or Key Secret"):
        super().__init__(message, status_code=401)

class RazorpayInvalidRequestError(RazorpayIntegrationError):
    """Raised when request payload or parameters are rejected by Razorpay (400 Bad Request)."""
    def __init__(self, message: str, raw_error: dict | None = None):
        super().__init__(message, status_code=400, raw_error=raw_error)

class RazorpayResourceNotFoundError(RazorpayIntegrationError):
    """Raised when a requested payment, order, or payment link is not found (404 Not Found)."""
    def __init__(self, resource_type: str, resource_id: str):
        message = f"Razorpay {resource_type} with ID '{resource_id}' was not found"
        super().__init__(message, status_code=404)

class RazorpayServerError(RazorpayIntegrationError):
    """Raised when Razorpay returns a 5xx server error."""
    def __init__(self, message: str = "Razorpay API server error"):
        super().__init__(message, status_code=502)

class RazorpayTimeoutError(RazorpayIntegrationError):
    """Raised when a request to Razorpay times out."""
    def __init__(self, message: str = "Razorpay API request timed out"):
        super().__init__(message, status_code=504)

class RazorpayWebhookSignatureError(RazorpayIntegrationError):
    """Raised when webhook signature verification fails."""
    def __init__(self, message: str = "Razorpay webhook signature verification failed"):
        super().__init__(message, status_code=400)
