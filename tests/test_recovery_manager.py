from recovery_manager import RecoveryConfig, RecoveryMode, evaluate_recovery
from risk_manager import AccountState


def test_recovery_stage_transitions() -> None:
    config = RecoveryConfig()
    normal = evaluate_recovery(AccountState(1000, 1000, 1000, 1000), 0.005, 3, config)
    warning = evaluate_recovery(AccountState(980, 980, 1000, 1000), 0.005, 3, config)
    defensive = evaluate_recovery(AccountState(950, 950, 1000, 1000), 0.005, 3, config)
    recovery = evaluate_recovery(AccountState(940, 940, 1000, 1000), 0.005, 3, config)
    shutdown = evaluate_recovery(AccountState(890, 890, 1000, 1000), 0.005, 3, config)
    assert normal.mode == RecoveryMode.NORMAL
    assert warning.mode == RecoveryMode.WARNING
    assert defensive.mode in {RecoveryMode.DEFENSIVE, RecoveryMode.RECOVERY}
    assert recovery.mode == RecoveryMode.RECOVERY
    assert shutdown.mode == RecoveryMode.SHUTDOWN


def test_shutdown_on_unsafe_recovery_config() -> None:
    config = RecoveryConfig(allow_martingale=True)
    state = evaluate_recovery(AccountState(1000, 1000, 1000, 1000), 0.005, 3, config)
    assert state.mode == RecoveryMode.SHUTDOWN
    assert state.shutdown_required
