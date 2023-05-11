import time
from collections import deque


class Block:
    def __init__(self, block_type: bool, block_time: float):
        self.type = block_type
        self.time = block_time


class GapStat:
    def __init__(self, gap_len=20 * 60) -> None:
        self._gap_len = gap_len

        self._dq = deque((Block(False, time.time()),))
        self._sum = 0.0
        self._last_time = time.time()
        self._count_true = 0

    def add(self, block_type: bool):
        block_time = time.time()
        left_time = self._last_time - self._gap_len
        added_time = block_time - self._last_time
        self._dq.append(Block(block_type, block_time))
        self._last_time = block_time
        if block_type:
            self._sum += added_time
            self._count_true += 1

        removed_block = None
        while added_time > 0:
            removed_block = self._dq.popleft()
            removed_time = removed_block.time - left_time
            left_time = removed_block.time
            added_time -= removed_time
            if removed_block.type:
                self._sum -= removed_time
                self._count_true -= 1

        if added_time < 0 and removed_block:
            self._dq.appendleft(removed_block)
            if removed_block.type:
                new_left_time = self._last_time - self._gap_len
                self._sum += removed_block.time - new_left_time
                self._count_true += 1

        if self._count_true == 0:
            self._sum = 0

        return self._sum

    def stats(self, current_block_type: bool):
        return self.add(current_block_type) / self._gap_len
