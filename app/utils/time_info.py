"""
Time Utility Functions
Provides current date and time formatting for Natasha's system prompt context.
"""
from datetime import datetime

def get_current_time() -> str:
    """Returns the current time in 12-hour format (e.g., 03:45 PM)."""
    return datetime.now().strftime("%I:%M %p")

def get_current_date() -> str:
    """Returns the current date (e.g., March 01, 2026)."""
    return datetime.now().strftime("%B %d, %Y")

def get_current_datetime() -> str:
    """Returns the full date and time string."""
    return datetime.now().strftime("%B %d, %Y at %I:%M %p")

def get_day_of_week() -> str:
    """Returns the current day of the week (e.g., Sunday)."""
    return datetime.now().strftime("%A")

def get_timestamp() -> str:
    """Returns the ISO formatted timestamp for logging and saving sessions."""
    return datetime.now().isoformat()

# Expose these functions to be easily imported in other files
__all__ = [
    "get_current_time", 
    "get_current_date", 
    "get_current_datetime", 
    "get_day_of_week", 
    "get_timestamp"
]