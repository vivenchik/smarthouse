from enum import Enum


class SysSKeys(Enum):
    retries = "retries"
    startup = "startup"
    clear_log = "clear_log"
    last_human_detected = "last_human_detected"
    max_run_queue_size = "max_run_queue_size"
    max_check_and_run_queue_size = "max_check_and_run_queue_size"
    quarantine_notifications = "__quarantine_notifications"
