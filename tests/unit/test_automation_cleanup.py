from imageset_generator.automation.api import sanitize_config
from imageset_generator.automation.scheduler import AutomationScheduler
from imageset_generator.app import app


class FakeScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, **kwargs):
        self.jobs.append(kwargs)


def _scheduler_instance():
    scheduler = object.__new__(AutomationScheduler)
    scheduler.scheduler_config = {"timezone": "UTC"}
    scheduler.scheduler = FakeScheduler()
    scheduler._run_with_window_check = lambda expected_window: expected_window
    return scheduler


def test_scheduler_month_window_helper_adds_expected_job():
    scheduler = _scheduler_instance()

    scheduler._schedule_month_window(
        day_range="22-31",
        expected_window="last-week",
        job_id="automation-last-week",
        job_name="ImageSet Automation (Last Week)",
        day_of_week=1,
        hour=2,
        minute=30,
    )

    job = scheduler.scheduler.jobs[0]
    assert job["func"] == scheduler._run_with_window_check
    assert job["args"] == ["last-week"]
    assert job["id"] == "automation-last-week"
    assert job["name"] == "ImageSet Automation (Last Week)"
    assert job["replace_existing"] is True
    assert str(job["trigger"].fields[2]) == "22-31"


def test_sanitize_config_redacts_nested_sensitive_keys_without_mutating_input():
    config = {
        "notifications": {
            "custom": {
                "api_token": "secret-token",
                "nested": {"Authorization": "Bearer secret"},
            }
        },
        "safe": "value",
    }

    sanitized = sanitize_config(config)

    assert sanitized["notifications"]["custom"]["api_token"] == "***"
    assert sanitized["notifications"]["custom"]["nested"]["Authorization"] == "***"
    assert sanitized["safe"] == "value"
    assert config["notifications"]["custom"]["api_token"] == "secret-token"


def test_automation_error_responses_use_standard_and_legacy_fields(monkeypatch):
    import imageset_generator.automation.api as automation_api

    monkeypatch.setattr(automation_api, "_scheduler", None)
    app.testing = True
    client = app.test_client()

    response = client.post("/api/automation/trigger")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Automation is not initialized"
    assert payload["error"] == payload["message"]
    assert payload["success"] is False
    assert "timestamp" in payload
