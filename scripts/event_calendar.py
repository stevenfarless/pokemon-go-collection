"""Compatibility entry point for the collection-aware Event Calendar."""

try:
    from .event_calendar_impl import CALENDAR_VERSION, LOCAL_STATE_VERSION, build_calendar, publish, schema
except ImportError:
    from event_calendar_impl import CALENDAR_VERSION, LOCAL_STATE_VERSION, build_calendar, publish, schema

__all__ = ["CALENDAR_VERSION", "LOCAL_STATE_VERSION", "build_calendar", "schema", "publish"]
