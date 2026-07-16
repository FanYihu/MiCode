import pytest

from micode import models


def test_create_run_defaults():
    run = models.Run()

    assert run.id != ""
    assert run.status == models.RunStatus.CREATED
    assert run.created_at is not None


def test_create_step_belongs_to_run():
    run = models.Run()
    step = models.Step(run_id=run.id)

    assert step.id != ""
    assert step.run_id == run.id


def test_create_event_belongs_to_step():
    run = models.Run()
    step = models.Step(run_id=run.id)
    event = models.Event(run_id=run.id, step_id=step.id)

    assert event.id != ""
    assert event.run_id == run.id
    assert event.step_id == step.id


def test_run_can_start_from_created():
    run = models.Run()
    old_updated_at = run.updated_at

    run.start()

    assert run.status == models.RunStatus.RUNNING
    assert run.updated_at >= old_updated_at


def test_run_can_complete_from_running():
    run = models.Run()
    run.start()

    run.complete()

    assert run.status == models.RunStatus.COMPLETED


def test_run_cannot_complete_before_start():
    run = models.Run()

    with pytest.raises(models.InvalidRunStatusTransition):
        run.complete()


def test_completed_run_cannot_start_again():
    run = models.Run()
    run.start()
    run.complete()

    with pytest.raises(models.InvalidRunStatusTransition):
        run.start()


def test_cancel_created_run():
    run = models.Run()

    run.cancel()

    assert run.status == models.RunStatus.CANCELLED
