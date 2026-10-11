from acc_telemetry.instance_lock import acquire_recorder_lock, recorder_running

PORT = 47392  # not the real one, so a recorder running on the machine doesn't interfere


def test_lock_is_exclusive_and_released_on_close():
    assert recorder_running(PORT) is False
    lock = acquire_recorder_lock(PORT)
    assert lock is not None
    assert recorder_running(PORT) is True
    assert acquire_recorder_lock(PORT) is None
    lock.close()
    assert recorder_running(PORT) is False
