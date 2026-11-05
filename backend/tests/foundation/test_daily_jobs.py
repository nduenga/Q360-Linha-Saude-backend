"""O comando diário corre todas as tarefas, mesmo quando uma delas falha."""
from __future__ import annotations

from unittest import mock

import pytest
from django.core.management import CommandError, call_command, get_commands

from apps.foundation.management.commands.run_daily_jobs import DAILY_JOBS


def test_every_daily_job_is_a_real_command():
    assert set(DAILY_JOBS) <= set(get_commands())


@pytest.mark.django_db
def test_daily_jobs_run_against_the_database():
    call_command("run_daily_jobs")


def test_a_failing_job_does_not_stop_the_next_ones_and_the_command_fails():
    ran = []

    def fake(job, **kwargs):
        ran.append(job)
        if job == "premium_overdue_scan":
            raise RuntimeError("falhou")

    with mock.patch("apps.foundation.management.commands.run_daily_jobs.call_command", side_effect=fake):
        with pytest.raises(CommandError, match="premium_overdue_scan"):
            call_command("run_daily_jobs")
    assert ran == list(DAILY_JOBS)
