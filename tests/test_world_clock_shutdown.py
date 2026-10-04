"""A stopping host must retain ownership until its in-flight tick finishes."""

from threading import Event, RLock, Thread

from server.world_core.realtime import WorldClock


def test_shutdown_waits_for_running_tick_before_releasing_world():
    entered = Event()
    release = Event()
    stopped = Event()

    class SlowSimulation:
        minute = 0

        def tick(self):
            entered.set()
            release.wait(15)
            self.minute += 1

    clock = WorldClock(SlowSimulation(), RLock(), interval=1)
    clock.start()

    def stop_host():
        clock.stop()
        stopped.set()

    stopper = Thread(target=stop_host, daemon=True)
    try:
        assert entered.wait(5), "Clock did not start the fixture tick"
        stopper.start()
        assert not stopped.wait(
            4
        ), "Host reported stopped while a tick still owned the world"
    finally:
        release.set()
        if stopper.ident is not None:
            stopper.join(5)
        clock.stop()
    assert stopped.is_set()
    assert clock.simulation.minute == 1
