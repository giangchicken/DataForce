"""TOOL · one APIRouter for /load-data: one service, so one route and nothing under it.

A handler is thin -- it calls the service and maps the error. It names no stage sequence:
the main endpoint folds through ``run_phase`` and each sub-endpoint calls exactly one
service (Requirement 48, I17).
"""
