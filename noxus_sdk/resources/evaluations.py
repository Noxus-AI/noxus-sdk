from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from noxus_sdk.resources.base import BaseResource, BaseService

# Arbitrary JSON blobs the eval API traffics in (evaluator config, test-case
# inputs/expected outputs, suite stats, evaluator JSON schemas).
JsonDict = dict[str, JsonValue]


class TestSuite(BaseResource):
    id: UUID
    group_id: UUID
    workflow_id: UUID | None = None
    agent_id: UUID | None = None
    name: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    stats: JsonDict | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class Evaluator(BaseResource):
    id: UUID
    test_suite_id: UUID
    type: str
    name: str
    display_name: str | None = None
    description: str | None = None
    config: JsonDict = {}
    created_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class TestCase(BaseResource):
    id: UUID
    test_suite_id: UUID
    group_id: UUID
    name: str
    inputs: JsonDict = {}
    expected_outputs: JsonDict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class EvaluationResult(BaseResource):
    id: UUID
    evaluator_id: UUID
    test_case_id: UUID
    score: float | None = None
    passed: bool | None = None
    feedback: str | None = None
    status: str

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class EvaluatorDefinition(BaseModel):
    type: str
    display_name: str
    description: str
    icon: str = ""
    config_schema: JsonDict = {}
    expected_schema: JsonDict | None = None
    category: str = ""
    group: str = ""

    model_config = ConfigDict(extra="allow")


class EvaluationService(BaseService[TestSuite]):
    # ---- evaluator definitions ----------------------------------------------
    def list_evaluator_definitions(
        self, category: str | None = None
    ) -> list[EvaluatorDefinition]:
        suffix = f"/{category}" if category else ""
        results = self.client.get(f"/v1/evaluator-definitions{suffix}")
        return [EvaluatorDefinition(**r) for r in results]

    async def alist_evaluator_definitions(
        self, category: str | None = None
    ) -> list[EvaluatorDefinition]:
        suffix = f"/{category}" if category else ""
        results = await self.client.aget(f"/v1/evaluator-definitions{suffix}")
        return [EvaluatorDefinition(**r) for r in results]

    # ---- test suites ---------------------------------------------------------
    def list_agent_test_suites(self, group_id: str, agent_id: str) -> list[TestSuite]:
        results = self.client.get(
            f"/v1/groups/{group_id}/agents/{agent_id}/test-suites"
        )
        return [TestSuite(client=self.client, **r) for r in results]

    async def alist_agent_test_suites(
        self, group_id: str, agent_id: str
    ) -> list[TestSuite]:
        results = await self.client.aget(
            f"/v1/groups/{group_id}/agents/{agent_id}/test-suites"
        )
        return [TestSuite(client=self.client, **r) for r in results]

    def list_workflow_test_suites(
        self, group_id: str, workflow_id: str
    ) -> list[TestSuite]:
        results = self.client.get(
            f"/v1/groups/{group_id}/workflows/{workflow_id}/test-suites"
        )
        return [TestSuite(client=self.client, **r) for r in results]

    async def alist_workflow_test_suites(
        self, group_id: str, workflow_id: str
    ) -> list[TestSuite]:
        results = await self.client.aget(
            f"/v1/groups/{group_id}/workflows/{workflow_id}/test-suites"
        )
        return [TestSuite(client=self.client, **r) for r in results]

    def get_test_suite(self, group_id: str, test_suite_id: str) -> TestSuite:
        result = self.client.get(f"/v1/groups/{group_id}/test-suites/{test_suite_id}")
        return TestSuite(client=self.client, **result)

    async def aget_test_suite(self, group_id: str, test_suite_id: str) -> TestSuite:
        result = await self.client.aget(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}"
        )
        return TestSuite(client=self.client, **result)

    def create_agent_test_suite(
        self, group_id: str, agent_id: str, name: str, description: str | None = None
    ) -> TestSuite:
        result = self.client.post(
            f"/v1/groups/{group_id}/agents/{agent_id}/test-suites",
            {"name": name, "description": description},
        )
        return TestSuite(client=self.client, **result)

    async def acreate_agent_test_suite(
        self, group_id: str, agent_id: str, name: str, description: str | None = None
    ) -> TestSuite:
        result = await self.client.apost(
            f"/v1/groups/{group_id}/agents/{agent_id}/test-suites",
            {"name": name, "description": description},
        )
        return TestSuite(client=self.client, **result)

    # ---- evaluators ----------------------------------------------------------
    def list_evaluators(self, group_id: str, test_suite_id: str) -> list[Evaluator]:
        results = self.client.get(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/evaluators"
        )
        return [Evaluator(client=self.client, **r) for r in results]

    async def alist_evaluators(
        self, group_id: str, test_suite_id: str
    ) -> list[Evaluator]:
        results = await self.client.aget(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/evaluators"
        )
        return [Evaluator(client=self.client, **r) for r in results]

    def create_evaluator(
        self,
        group_id: str,
        test_suite_id: str,
        type: str,
        name: str,
        config: JsonDict | None = None,
    ) -> Evaluator:
        result = self.client.post(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/evaluators",
            {"type": type, "name": name, "config": config or {}},
        )
        return Evaluator(client=self.client, **result)

    async def acreate_evaluator(
        self,
        group_id: str,
        test_suite_id: str,
        type: str,
        name: str,
        config: JsonDict | None = None,
    ) -> Evaluator:
        result = await self.client.apost(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/evaluators",
            {"type": type, "name": name, "config": config or {}},
        )
        return Evaluator(client=self.client, **result)

    # ---- test cases ----------------------------------------------------------
    def list_test_cases(self, group_id: str, test_suite_id: str) -> list[TestCase]:
        results = self.client.pget(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/test-cases"
        )
        return [TestCase(client=self.client, **r) for r in results]

    async def alist_test_cases(
        self, group_id: str, test_suite_id: str
    ) -> list[TestCase]:
        results = await self.client.apget(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/test-cases"
        )
        return [TestCase(client=self.client, **r) for r in results]

    def get_test_case(self, group_id: str, test_case_id: str) -> TestCase:
        result = self.client.get(f"/v1/groups/{group_id}/test-cases/{test_case_id}")
        return TestCase(client=self.client, **result)

    async def aget_test_case(self, group_id: str, test_case_id: str) -> TestCase:
        result = await self.client.aget(
            f"/v1/groups/{group_id}/test-cases/{test_case_id}"
        )
        return TestCase(client=self.client, **result)

    def create_test_case(
        self,
        group_id: str,
        test_suite_id: str,
        name: str,
        inputs: JsonDict,
        expected_outputs: JsonDict | None = None,
    ) -> TestCase:
        result = self.client.post(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/test-cases",
            {"name": name, "inputs": inputs, "expected_outputs": expected_outputs},
        )
        return TestCase(client=self.client, **result)

    async def acreate_test_case(
        self,
        group_id: str,
        test_suite_id: str,
        name: str,
        inputs: JsonDict,
        expected_outputs: JsonDict | None = None,
    ) -> TestCase:
        result = await self.client.apost(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/test-cases",
            {"name": name, "inputs": inputs, "expected_outputs": expected_outputs},
        )
        return TestCase(client=self.client, **result)

    # ---- runs & results ------------------------------------------------------
    def run_evaluation(
        self,
        group_id: str,
        test_suite_id: str,
        version_id: str | None = None,
        test_case_ids: list[str] | None = None,
        wait_for_completion: bool = False,
    ) -> JsonDict:
        return self.client.post(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/run-evaluation",
            {
                "version_id": version_id,
                "test_case_ids": test_case_ids,
                "wait_for_completion": wait_for_completion,
            },
        )

    async def arun_evaluation(
        self,
        group_id: str,
        test_suite_id: str,
        version_id: str | None = None,
        test_case_ids: list[str] | None = None,
        wait_for_completion: bool = False,
    ) -> JsonDict:
        return await self.client.apost(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/run-evaluation",
            {
                "version_id": version_id,
                "test_case_ids": test_case_ids,
                "wait_for_completion": wait_for_completion,
            },
        )

    def wait_evaluation_run(
        self, group_id: str, evaluation_run_id: str, max_wait_seconds: int = 60
    ) -> JsonDict:
        return self.client.post(
            f"/v1/groups/{group_id}/evaluation-runs/{evaluation_run_id}/wait"
            f"?max_wait_seconds={max_wait_seconds}",
            {},
        )

    async def await_evaluation_run(
        self, group_id: str, evaluation_run_id: str, max_wait_seconds: int = 60
    ) -> JsonDict:
        return await self.client.apost(
            f"/v1/groups/{group_id}/evaluation-runs/{evaluation_run_id}/wait"
            f"?max_wait_seconds={max_wait_seconds}",
            {},
        )

    def list_evaluation_results(
        self, group_id: str, test_suite_id: str
    ) -> list[EvaluationResult]:
        results = self.client.pget(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/evaluation-results"
        )
        return [EvaluationResult(client=self.client, **r) for r in results]

    async def alist_evaluation_results(
        self, group_id: str, test_suite_id: str
    ) -> list[EvaluationResult]:
        results = await self.client.apget(
            f"/v1/groups/{group_id}/test-suites/{test_suite_id}/evaluation-results"
        )
        return [EvaluationResult(client=self.client, **r) for r in results]

    def get_evaluation_result(
        self, group_id: str, evaluation_result_id: str
    ) -> EvaluationResult:
        result = self.client.get(
            f"/v1/groups/{group_id}/evaluation-results/{evaluation_result_id}"
        )
        return EvaluationResult(client=self.client, **result)

    async def aget_evaluation_result(
        self, group_id: str, evaluation_result_id: str
    ) -> EvaluationResult:
        result = await self.client.aget(
            f"/v1/groups/{group_id}/evaluation-results/{evaluation_result_id}"
        )
        return EvaluationResult(client=self.client, **result)
