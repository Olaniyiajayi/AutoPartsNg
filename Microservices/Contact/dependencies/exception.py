"""
Exception handling
"""

# standard imports
from functools import wraps
from os import getenv
from threading import local
from typing import Callable

# third party imports
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import ValidationError
from sentry_sdk import capture_exception, init
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

# local imports
from validations import (
    DatabaseError,
    EventBridgeError,
)

# Logger
base_logger = Logger()
# Thread-local storage for log buffer
log_buffer = local()


class BufferedLogger:
    """
    Logger wrapper that buffers INFO level logs and only outputs them when an error occurs.
    WARN and ERROR logs are always output immediately.
    """

    def __init__(self, base_logger):
        self._logger = base_logger

    def get_buffer(self):
        """Get or create thread-local log buffer"""
        if not hasattr(log_buffer, "info_logs"):
            log_buffer.info_logs = []
        return log_buffer.info_logs

    def get_incoming_event(self):
        """Get or create thread-local incoming event storage"""
        if not hasattr(log_buffer, "incoming_event"):
            log_buffer.incoming_event = None
        return log_buffer.incoming_event

    def set_incoming_event(self, event):
        """Store incoming event in thread-local storage"""
        log_buffer.incoming_event = event

    def clear_buffer(self):
        """Clear the thread-local log buffer and incoming event"""
        if hasattr(log_buffer, "info_logs"):
            log_buffer.info_logs = []
        if hasattr(log_buffer, "incoming_event"):
            log_buffer.incoming_event = None

    def flush_buffer(self):
        """Flush all buffered INFO logs"""
        # Log incoming event/payload first if available
        incoming_event = self.get_incoming_event()
        if incoming_event is not None:
            self._logger.warning("=== Incoming Event/Payload ===")
            self._logger.warning("Event: %s", incoming_event)
            self._logger.warning("=== End of Incoming Event/Payload ===")
        
        buffer = self.get_buffer()
        if buffer:
            self._logger.warning("=== Flushing buffered INFO logs due to error ===")
            for log_entry in buffer:
                # log_entry is a tuple: (message, args_tuple, kwargs_dict)
                # Replay the original logger call with all parameters
                message, args, kwargs = log_entry
                # Output as WARNING level so it gets logged with full payload
                self._logger.warning(message, *args, **kwargs)
            self._logger.warning("=== End of buffered INFO logs ===")
            self.clear_buffer()

    def info(self, message, *args, **kwargs):
        """Buffer INFO level logs instead of outputting them"""
        # Store the original call parameters so we can replay them with full payload
        # Store as tuple: (message, args_tuple, kwargs_dict)
        self.get_buffer().append((message, args, kwargs))

    def warning(self, *args, **kwargs):
        """Always output WARNING logs immediately"""
        return self._logger.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        """Output ERROR logs immediately and flush buffered INFO logs"""
        self.flush_buffer()
        return self._logger.error(*args, **kwargs)

    def debug(self, *args, **kwargs):
        """Buffer DEBUG logs (if needed)"""
        return self._logger.debug(*args, **kwargs)

    def critical(self, *args, **kwargs):
        """Output CRITICAL logs immediately and flush buffered INFO logs"""
        self.flush_buffer()
        return self._logger.critical(*args, **kwargs)

    def exception(self, *args, **kwargs):
        """Output exception logs immediately and flush buffered INFO logs"""
        self.flush_buffer()
        return self._logger.exception(*args, **kwargs)

    # Delegate other methods and attributes to the base logger
    def __getattr__(self, name):
        return getattr(self._logger, name)


logger = BufferedLogger(base_logger)

# environment variables
stage = getenv("Stage")
SENTRY_DNS = getenv("SENTRY_DNS")
DEBUG = False
RELEASE = getenv("RELEASE")
TRACES_SENTRY_SAMPLE_RATE = float(getenv("TRACES_SENTRY_SAMPLE_RATE"))
PROFILE_SAMPLE_RATE = float(getenv("PROFILE_SAMPLE_RATE"))


def handle_validation_error(status_code: int, message: str, error: Exception) -> dict:
    """Handle validation error
    Args:
        status_code (int): The status code
        message (str): The message
        error (Exception): The error
    Returns:
        dict: The response
    """
    # Log the error
    logger.error(message + ": " + str(error))

    # Initialize Sentry only if in production
    if stage == "prod-v5":
        init(
            dsn=SENTRY_DNS,
            debug=DEBUG,
            release=RELEASE,
            traces_sample_rate=TRACES_SENTRY_SAMPLE_RATE,
            environment=stage,
            profiles_sample_rate=PROFILE_SAMPLE_RATE,
            integrations=[AwsLambdaIntegration(timeout_warning=True)],
        )

        capture_exception(error)

    return {
        "statusCode": status_code,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": f"{message}: {error}",
    }


def handle_exceptions(func: Callable) -> Callable:
    """Handle exceptions in the function
    Args:
        func (Callable): The function to handle exceptions for
    Returns:
        dict: The response
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Clear any existing buffer at the start of each function call
        if hasattr(log_buffer, "info_logs"):
            log_buffer.info_logs = []
        # Capture incoming event (first arg is typically the event in Lambda handlers)
        if args and len(args) > 0:
            logger.set_incoming_event(args[0])
        try:
            result = func(*args, **kwargs)
            # Clear buffer on successful completion (don't log INFO on success)
            if hasattr(log_buffer, "info_logs"):
                log_buffer.info_logs = []
            if hasattr(log_buffer, "incoming_event"):
                log_buffer.incoming_event = None
            return result
        except ValidationError as error:
            # Handle validation error
            return handle_validation_error(400, "Validation error", error)
        except ValueError as error:
            # Handle value error
            return handle_validation_error(400, "Value error", error)
        except DatabaseError as error:
            # Handle database error
            return handle_validation_error(500, "Database error", error)
        except EventBridgeError as error:
            # Handle event bridge error
            return handle_validation_error(500, "Event bridge error", error)
        except Exception as error:
            # Handle unexpected error
            return handle_validation_error(500, "Unexpected error", error)

    return wrapper
