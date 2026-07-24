"""
Application lifecycle tests.
"""


from fastapi.testclient import TestClient

from app.main import app


def test_startup_creates_job_manager():

    with TestClient(app):

        assert hasattr(
            app.state,
            "job_manager",
        )


def test_shutdown_cleanup():

    with TestClient(app):

        manager = (
            app.state.job_manager
        )

        assert (
            manager is not None
        )