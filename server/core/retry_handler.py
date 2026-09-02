"""
Intelligent Retry & Error Propagation Handler
Enforces strict policy:
- 429 / 503 / transient network drops: Retry with exponential backoff up to max_attempts
- 400 / 401 / 403 / 404: Fail-fast immediately, NO RETRIES, and raise descriptive domain exception
- NO SILENT DEATH, NO SILENT FALLBACKS
"""

import time
import logging
from typing import Callable, TypeVar, Any
from server.core.config import config
from server.core.exceptions import (
    QuotaExceededException,
    InvalidCredentialsException,
    InvalidInputException,
    ResourceNotFoundException,
    ServiceUnavailableException,
    FrameTalkException
)

logger = logging.getLogger("frametalk.retry")

T = TypeVar("T")

def execute_with_retry(
    action_name: str,
    fn: Callable[..., T],
    *args: Any,
    **kwargs: Any
) -> T:
    """
    Executes a callable with intelligent retry and strict error classification.
    """
    attempts = 0
    max_attempts = config.max_retry_attempts
    delay = config.initial_retry_delay_sec

    while attempts < max_attempts:
        attempts += 1
        try:
            return fn(*args, **kwargs)
        except Exception as ex:
            error_str = str(ex).lower()
            status_code = _extract_status_code(ex)

            # 1. Non-retriable: 401 Unauthorized / 403 Forbidden
            if status_code in (401, 403) or "401" in error_str or "unauthorized" in error_str or "forbidden" in error_str:
                logger.error(f"[{action_name}] Authentication/Authorization failure ({status_code}): {ex}. Failing fast.")
                raise InvalidCredentialsException(detail=str(ex)) from ex

            # 2. Non-retriable: 400 Bad Request / Invalid Argument
            if status_code == 400 or "400" in error_str or "invalid_argument" in error_str:
                logger.error(f"[{action_name}] Bad request ({status_code}): {ex}. Failing fast without retry.")
                raise InvalidInputException(message=f"Bad request in {action_name}: {ex}", detail=str(ex)) from ex

            # 3. Non-retriable: 404 Not Found
            if status_code == 404 or "404" in error_str or "not found" in error_str:
                logger.error(f"[{action_name}] Resource not found ({status_code}): {ex}. Failing fast.")
                raise ResourceNotFoundException(message=f"Asset not found in {action_name}: {ex}", detail=str(ex)) from ex

            # 4. Retriable: 429 Quota / Rate Limit
            is_quota = (status_code == 429) or ("429" in error_str) or ("quota" in error_str) or ("resource_exhausted" in error_str)
            is_overload = (status_code in (500, 502, 503, 504)) or ("503" in error_str) or ("overloaded" in error_str)

            if is_quota or is_overload:
                err_type = "Quota Limit (429)" if is_quota else f"Server Transient ({status_code})"
                if attempts < max_attempts:
                    logger.warning(
                        f"[{action_name}] {err_type} encountered on attempt {attempts}/{max_attempts}. "
                        f"Retrying in {delay:.1f}s... Error: {ex}"
                    )
                    time.sleep(delay)
                    delay *= config.backoff_multiplier
                    continue
                else:
                    logger.error(f"[{action_name}] Max retries exceeded for {err_type}. Raising transparent error.")
                    if is_quota:
                        raise QuotaExceededException(
                            message=f"Gemini API rate limit or credit quota exceeded during {action_name}.",
                            detail=f"Failed after {max_attempts} attempts. Upstream error: {ex}"
                        ) from ex
                    else:
                        raise ServiceUnavailableException(
                            message=f"Model service unavailable during {action_name}.",
                            detail=f"Failed after {max_attempts} attempts. Upstream error: {ex}"
                        ) from ex

            # 5. Any other unexpected error: log and raise immediately
            logger.error(f"[{action_name}] Non-retriable fatal error: {ex}")
            raise FrameTalkException(message=f"Fatal error in {action_name}: {ex}", status_code=500, detail=str(ex)) from ex

    raise FrameTalkException(message=f"Operation {action_name} failed unexpectedly after {max_attempts} attempts.")

def _extract_status_code(ex: Exception) -> int:
    """Attempts to extract HTTP status code from standard SDK and requests exceptions."""
    if hasattr(ex, "status_code") and isinstance(ex.status_code, int):
        return ex.status_code
    if hasattr(ex, "code") and isinstance(ex.code, int):
        return ex.code
    if hasattr(ex, "response") and hasattr(ex.response, "status_code"):
        return int(ex.response.status_code)
    
    # Check for HTTP status code numbers in string representation
    import re
    match = re.search(r'\b(400|401|403|404|429|500|502|503|504)\b', str(ex))
    if match:
        return int(match.group(1))
    return 500
