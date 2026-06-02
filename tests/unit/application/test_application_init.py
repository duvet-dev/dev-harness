"""Tests for application/services/__init__.py and application/__init__.py."""

from harness.application import services as app_services
from harness.application.services import AgentService


class TestApplicationInit:
    def test_agent_service_exported(self):
        assert AgentService is not None

    def test_services_package_accessible(self):
        assert app_services is not None
