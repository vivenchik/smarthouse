class YandexError(Exception):
    def __init__(self, message, prod: bool, err_retry: bool = True, debug_str: str = "", dont_log: bool = False):
        self.message = message
        self.prod = prod
        self.err_retry = err_retry
        self.debug_str = debug_str
        self.dont_log = dont_log
        super().__init__(self.message)


class ProgrammingError(YandexError):
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


class YandexServerError(YandexError):
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


class YandexCheckError(YandexError):
    def __init__(
        self,
        message,
        prod: bool,
        device_ids: list[str],
        err_retry: bool = True,
        debug_str: str = "",
        dont_log: bool = False,
    ):
        self.device_ids = device_ids
        super().__init__(message, prod, err_retry, debug_str, dont_log)


class DeviceOffline(YandexError):
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
