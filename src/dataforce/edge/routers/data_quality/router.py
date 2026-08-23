"""TOOL · one APIRouter for /data-quality: the main endpoint, and one sub-endpoint per service.

A handler is thin -- it calls the service and maps the error. It names no stage sequence:
the main endpoint folds through ``run_phase`` and each sub-endpoint calls exactly one
service (Requirement 48, I17).
"""
