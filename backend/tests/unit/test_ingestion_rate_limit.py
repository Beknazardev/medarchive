from app.ingestion.rate_limit import HostRateLimiter


class FakeTime:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def test_rate_limiter_enforces_minimum_host_delay():
    fake_time = FakeTime()
    limiter = HostRateLimiter(clock=fake_time.monotonic, sleeper=fake_time.sleep)

    with limiter.slot("prices.example.kz", minimum_delay_seconds=5, max_concurrency=1):
        pass
    fake_time.value = 1
    with limiter.slot("prices.example.kz", minimum_delay_seconds=5, max_concurrency=1):
        pass

    assert fake_time.sleeps == [4]


def test_rate_limiter_keeps_hosts_independent():
    fake_time = FakeTime()
    limiter = HostRateLimiter(clock=fake_time.monotonic, sleeper=fake_time.sleep)

    with limiter.slot("first.example.kz", minimum_delay_seconds=10, max_concurrency=1):
        pass
    with limiter.slot("second.example.kz", minimum_delay_seconds=10, max_concurrency=1):
        pass

    assert fake_time.sleeps == []
