class InfraError(Exception):
    def __init__(self, message, prod: bool, err_retry: bool = True, debug_str: str = "", dont_log: bool = False):
        self.message = message
        self.prod = prod
        self.err_retry = err_retry
        self.debug_str = debug_str
        self.dont_log = dont_log
        super().__init__(self.message)


class ProgrammingError(InfraError):
    def __init__(
        self,
        message,
        prod: bool,
        device_ids: list[str] = [],
        err_retry: bool = True,
        debug_str: str = "",
        dont_log: bool = False,
    ):
        self.device_ids = device_ids or []
        self.send = True
        super().__init__(message, prod, err_retry, debug_str, dont_log)


class InfraServerError(InfraError):
    def __init__(
        self,
        message,
        prod: bool,
        device_ids: list[str] = [],
        err_retry: bool = True,
        debug_str: str = "",
        dont_log: bool = False,
    ):
        self.device_ids = device_ids or []
        self.send = True
        super().__init__(message, prod, err_retry, debug_str, dont_log)


class InfraCheckError(InfraError):
    def __init__(
        self,
        message,
        prod: bool,
        device_ids: list[str],
        wished_actions_list: list,
        err_retry: bool = True,
        debug_str: str = "",
        dont_log: bool = False,
    ):
        self.device_ids = device_ids
        self.wished_actions_list = wished_actions_list
        super().__init__(message, prod, err_retry, debug_str, dont_log)


class DeviceOffline(InfraError):
    def __init__(
        self,
        message,
        prod: bool,
        device_ids: list[str],
        err_retry: bool = True,
        debug_str: str = "",
        dont_log: bool = False,
        send: bool = False,
    ):
        self.device_ids = device_ids
        self.send = send
        super().__init__(message, prod, err_retry, debug_str, dont_log)
