import sys
from datetime import datetime

def _get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_info(message):
    """Displays standard informational messages."""
    print(f"[{_get_time()}] [INFO] {message}")

def log_success(message):
    """Displays messages when a process successfully completes."""
    print(f"[{_get_time()}] [SUCCESS] {message}")

def log_warning(message):
    """Displays warning messages."""
    print(f"[{_get_time()}] [WARNING] {message}")

def log_error(action_context, error_msg):
    """
    Displays error messages clearly without emojis, ensuring the context
    and technical details are communicated professionally.
    
    Parameters:
    - action_context: Description of the process being attempted before failure.
    - error_msg: The original Python exception object or custom string.
    """
    pesan = (
        f"\n[{_get_time()}] [FAILED]\n"
        f"Process Attempted : {action_context}\n"
        f"Error Details     : {str(error_msg)}\n"
        f"Suggestion        : Please verify the input data, file structures, or access permissions.\n"
        f"{'-'*50}"
    )
    print(pesan, file=sys.stderr)
