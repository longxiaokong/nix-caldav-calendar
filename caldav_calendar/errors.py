from __future__ import annotations


class CaldavCalendarError(Exception):
    code = "GENERAL_ERROR"
    exit_code = 1

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(CaldavCalendarError):
    code = "VALIDATION_ERROR"
    exit_code = 2


class ConfigError(CaldavCalendarError):
    code = "CONFIG_ERROR"
    exit_code = 3


class NotFoundError(CaldavCalendarError):
    code = "NOT_FOUND"
    exit_code = 4


class ConflictError(CaldavCalendarError):
    code = "CONFLICT_DETECTED"
    exit_code = 5


class ConfirmationRequiredError(CaldavCalendarError):
    code = "CONFIRMATION_REQUIRED"
    exit_code = 6


class SyncFailureError(CaldavCalendarError):
    code = "SYNC_FAILURE"
    exit_code = 7


class FilesystemWriteError(CaldavCalendarError):
    code = "FILESYSTEM_WRITE_FAILURE"
    exit_code = 8
