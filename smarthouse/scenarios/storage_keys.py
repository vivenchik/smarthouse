from enum import Enum


class SysSKeys(Enum):
    retries = "retries"
    last_human_detected = "last_human_detected"
    max_run_queue_size = "max_run_queue_size"
    max_check_and_run_queue_size = "max_check_and_run_queue_size"
    quarantine_notifications = "__quarantine_notifications"
