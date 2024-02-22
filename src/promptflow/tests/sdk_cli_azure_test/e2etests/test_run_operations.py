# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import shutil
from logging import Logger
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from typing import Callable
from unittest.mock import MagicMock, patch

import pandas as pd
import pydash
import pytest

from promptflow._sdk._constants import DownloadedRun, RunStatus
from promptflow._sdk._errors import InvalidRunError, InvalidRunStatusError, RunNotFoundError
from promptflow._sdk._load_functions import load_run
from promptflow._sdk.entities import Run
from promptflow._utils.flow_utils import get_flow_lineage_id
from promptflow._utils.yaml_utils import load_yaml
from promptflow.azure import PFClient
from promptflow.azure._constants._flow import ENVIRONMENT, PYTHON_REQUIREMENTS_TXT
from promptflow.azure._entities._flow import Flow
from promptflow.exceptions import UserErrorException

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD
from ..recording_utilities import is_live

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"
EAGER_FLOWS_DIR = "./tests/test_configs/eager_flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


def create_registry_run(name: str, registry_name: str, runtime: str, pf: PFClient):
    return pf.run(
        flow=f"azureml://registries/{registry_name}/models/simple_hello_world/versions/202311241",
        data=f"{DATAS_DIR}/simple_hello_world.jsonl",
        column_mapping={"name": "${data.name}"},
        runtime=runtime,
        name=name,
    )


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures(
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
class TestFlowRun:
    def test_run_bulk(self, pf, runtime: str, randstr: Callable[[str], str]):
        name = randstr("name")
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=name,
        )
        assert isinstance(run, Run)
        assert run.name == name

    def test_run_bulk_from_yaml(self, pf, runtime: str, randstr: Callable[[str], str]):
        run_id = randstr("run_id")
        run = load_run(
            source=f"{RUNS_DIR}/sample_bulk_run_cloud.yaml",
            params_override=[{"name": run_id, "runtime": runtime}],
        )
        run = pf.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_basic_evaluation(self, pf, runtime: str, randstr: Callable[[str], str]):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=randstr("batch_run_name"),
        )
        assert isinstance(run, Run)
        run = pf.runs.stream(run=run.name)
        assert run.status == RunStatus.COMPLETED

        eval_run = pf.run(
            flow=f"{FLOWS_DIR}/eval-classification-accuracy",
            data=data_path,
            run=run,
            column_mapping={"groundtruth": "${data.answer}", "prediction": "${run.outputs.category}"},
            runtime=runtime,
            name=randstr("eval_run_name"),
        )
        assert isinstance(eval_run, Run)
        eval_run = pf.runs.stream(run=eval_run.name)
        assert eval_run.status == RunStatus.COMPLETED

    def test_basic_evaluation_without_data(self, pf, runtime: str, randstr: Callable[[str], str]):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification3.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=randstr("batch_run_name"),
        )
        assert isinstance(run, Run)
        run = pf.runs.stream(run=run.name)
        assert run.status == RunStatus.COMPLETED

        eval_run = pf.run(
            flow=f"{FLOWS_DIR}/eval-classification-accuracy",
            run=run,
            column_mapping={
                # evaluation reference run.inputs
                "groundtruth": "${run.inputs.url}",
                "prediction": "${run.outputs.category}",
            },
            runtime=runtime,
            name=randstr("eval_run_name"),
        )
        assert isinstance(eval_run, Run)
        eval_run = pf.runs.stream(run=eval_run.name)
        assert eval_run.status == RunStatus.COMPLETED

    def test_run_bulk_with_remote_flow(
        self, pf: PFClient, runtime: str, randstr: Callable[[str], str], created_flow: Flow
    ):
        """Test run bulk with remote workspace flow."""
        name = randstr("name")
        run = pf.run(
            flow=f"azureml:{created_flow.name}",
            data=f"{DATAS_DIR}/simple_hello_world.jsonl",
            column_mapping={"name": "${data.name}"},
            runtime=runtime,
            name=name,
        )
        assert isinstance(run, Run)
        assert run.name == name

    def test_run_bulk_with_registry_flow(
        self, pf: PFClient, runtime: str, randstr: Callable[[str], str], registry_name: str
    ):
        """Test run bulk with remote registry flow."""
        name = randstr("name")
        run = create_registry_run(name=name, registry_name=registry_name, runtime=runtime, pf=pf)
        assert isinstance(run, Run)
        assert run.name == name

        # test invalid registry flow
        with pytest.raises(UserErrorException, match="Invalid remote flow pattern, got"):
            pf.run(
                flow="azureml://registries/no-flow",
                data=f"{DATAS_DIR}/simple_hello_world.jsonl",
                column_mapping={"name": "${data.name}"},
                runtime=runtime,
                name=name,
            )

    def test_run_bulk_with_registry_flow_automatic_runtime(
        self, pf: PFClient, randstr: Callable[[str], str], registry_name: str
    ):
        """Test run bulk with remote registry flow."""
        name = randstr("name")
        run = create_registry_run(name=name, registry_name=registry_name, runtime=None, pf=pf)
        assert isinstance(run, Run)
        assert run.name == name
        run = pf.runs.stream(run=run.name)
        assert run.status == RunStatus.COMPLETED

    def test_run_with_connection_overwrite(self, pf, runtime: str, randstr: Callable[[str], str]):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            connections={"classify_with_llm": {"connection": "azure_open_ai", "model": "gpt-3.5-turbo"}},
            runtime=runtime,
            name=randstr("name"),
        )
        assert isinstance(run, Run)

    def test_run_with_env_overwrite(self, pf, runtime: str, randstr: Callable[[str], str]):
        run = load_run(
            source=f"{RUNS_DIR}/run_with_env.yaml",
            params_override=[{"runtime": runtime}],
        )
        run.name = randstr("name")
        run = pf.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_run_display_name_with_macro(self, pf, runtime: str, randstr: Callable[[str], str]):
        run = load_run(
            source=f"{RUNS_DIR}/run_with_env.yaml",
            params_override=[{"runtime": runtime}],
        )
        run.name = randstr("name")
        run.display_name = "my_display_name_${variant_id}_${timestamp}"
        run = pf.runs.create_or_update(run=run)
        assert run.display_name.startswith("my_display_name_variant_0_")
        assert "${timestamp}" not in run.display_name
        assert isinstance(run, Run)

    def test_default_run_display_name(self, pf, runtime: str, randstr: Callable[[str], str]):
        run = load_run(
            source=f"{RUNS_DIR}/run_with_env.yaml",
            params_override=[{"runtime": runtime}],
        )
        run.name = randstr("name")
        run = pf.runs.create_or_update(run=run)
        assert run.display_name == run.name
        assert isinstance(run, Run)

    def test_run_with_remote_data(
        self, pf, runtime: str, remote_web_classification_data, randstr: Callable[[str], str]
    ):
        # run with arm id
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"azureml:{remote_web_classification_data.id}",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=randstr("name1"),
        )
        assert isinstance(run, Run)
        # run with name version
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"azureml:{remote_web_classification_data.name}:{remote_web_classification_data.version}",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=randstr("name2"),
        )
        assert isinstance(run, Run)

    # TODO: confirm whether this test is a end-to-end test
    def test_run_bulk_not_exist(self, pf, runtime: str, randstr: Callable[[str], str]):
        test_data = f"{DATAS_DIR}/webClassification1.jsonl"
        with pytest.raises(UserErrorException) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                # data with file:/// prefix is not supported, should raise not exist error
                data=f"file:///{Path(test_data).resolve().absolute()}",
                column_mapping={"url": "${data.url}"},
                variant="${summarize_text_content.variant_0}",
                runtime=runtime,
                name=randstr("name"),
            )
        assert "does not exist" in str(e.value)

    def test_list_runs(self, pf):
        runs = pf.runs.list(max_results=10)
        for run in runs:
            print(json.dumps(run._to_dict(), indent=4))
        assert len(runs) == 10

    def test_show_run(self, pf: PFClient, created_eval_run_without_llm: Run):
        run = pf.runs.get(run=created_eval_run_without_llm.name)
        run_dict = run._to_dict()
        print(json.dumps(run_dict, indent=4))

        # it's hard to assert with precise value, so just assert existence, type and length
        expected_keys = [
            "name",
            "created_on",
            "status",
            "display_name",
            "description",
            "tags",
            "properties",
            "creation_context",
            "start_time",
            "end_time",
            "duration",
            "portal_url",
            "data",
            "output",
            "run",
        ]
        for expected_key in expected_keys:
            assert expected_key in run_dict
            if expected_key == "description":
                assert run_dict[expected_key] is None
            elif expected_key in {"tags", "properties", "creation_context"}:
                assert isinstance(run_dict[expected_key], dict)
            else:
                assert isinstance(run_dict[expected_key], str)
                assert len(run_dict[expected_key]) > 0

    def test_show_run_details(self, pf: PFClient, created_batch_run_without_llm: Run):
        # get first 2 results
        details = pf.get_details(run=created_batch_run_without_llm.name, max_results=2)
        assert details.shape[0] == 2

        # get first 10 results while it only has 3
        details = pf.get_details(run=created_batch_run_without_llm.name, max_results=10)
        assert details.shape[0] == 3

        # get all results
        details = pf.get_details(run=created_batch_run_without_llm.name, all_results=True)
        assert details.shape[0] == 3

        # get all results even if max_results is set to 2
        details = pf.get_details(
            run=created_batch_run_without_llm.name,
            max_results=2,
            all_results=True,
        )
        assert details.shape[0] == 3

    def test_show_metrics(self, pf: PFClient, created_eval_run_without_llm: Run):
        metrics = pf.runs.get_metrics(run=created_eval_run_without_llm.name)
        print(json.dumps(metrics, indent=4))
        # as we use unmatched data, we can assert the accuracy is 0
        assert metrics == {"accuracy": 0.0}

    def test_stream_invalid_run_logs(self, pf, randstr: Callable[[str], str]):
        # test get invalid run name
        non_exist_run = randstr("non_exist_run")
        with pytest.raises(RunNotFoundError, match=f"Run {non_exist_run!r} not found"):
            pf.runs.stream(run=non_exist_run)

    def test_stream_run_logs(self, pf: PFClient, created_batch_run_without_llm: Run):
        run = pf.runs.stream(run=created_batch_run_without_llm.name)
        assert run.status == RunStatus.COMPLETED

    def test_stream_failed_run_logs(self, pf: PFClient, created_failed_run: Run, capfd: pytest.CaptureFixture):
        # (default) raise_on_error=True
        with pytest.raises(InvalidRunStatusError):
            pf.stream(run=created_failed_run.name)
        # raise_on_error=False
        pf.stream(run=created_failed_run.name, raise_on_error=False)
        out, _ = capfd.readouterr()
        assert "The input for batch run is incorrect. Couldn't find these mapping relations: ${data.key}" in out

    def test_failed_run_to_dict_exclude(self, pf: PFClient, created_failed_run: Run):
        failed_run = pf.runs.get(run=created_failed_run.name)
        # Azure run object reference a dict, use deepcopy to avoid unexpected modification
        default = copy.deepcopy(failed_run._to_dict())
        exclude = failed_run._to_dict(exclude_additional_info=True, exclude_debug_info=True)
        assert "additionalInfo" in default["error"]["error"] and "additionalInfo" not in exclude["error"]["error"]
        assert "debugInfo" in default["error"]["error"] and "debugInfo" not in exclude["error"]["error"]

    @pytest.mark.skipif(
        condition=not is_live(),
        reason="cannot differ the two requests to run history in replay mode.",
    )
    def test_archive_and_restore_run(self, pf: PFClient, created_batch_run_without_llm: Run):
        from promptflow._sdk._constants import RunHistoryKeys

        run_meta_data = RunHistoryKeys.RunMetaData
        hidden = RunHistoryKeys.HIDDEN

        run_id = created_batch_run_without_llm.name

        # test archive
        pf.runs.archive(run=run_id)
        run_data = pf.runs._get_run_from_run_history(run_id, original_form=True)[run_meta_data]
        assert run_data[hidden] is True

        # test restore
        pf.runs.restore(run=run_id)
        run_data = pf.runs._get_run_from_run_history(run_id, original_form=True)[run_meta_data]
        assert run_data[hidden] is False

    def test_update_run(self, pf: PFClient, created_batch_run_without_llm: Run, randstr: Callable[[str], str]):
        run_id = created_batch_run_without_llm.name
        test_mark = randstr("test_mark")

        new_display_name = f"test_display_name_{test_mark}"
        new_description = f"test_description_{test_mark}"
        new_tags = {"test_tag": test_mark}

        run = pf.runs.update(
            run=run_id,
            display_name=new_display_name,
            description=new_description,
            tags=new_tags,
        )
        # sleep to wait for update to take effect
        sleep(3)
        assert run.display_name == new_display_name
        assert run.description == new_description
        assert run.tags["test_tag"] == test_mark

        # test wrong type of parameters won't raise error, just log warnings and got ignored
        run = pf.runs.update(
            run=run_id,
            tags={"test_tag": {"a": 1}},
        )
        # sleep to wait for update to take effect
        sleep(3)
        assert run.display_name == new_display_name
        assert run.description == new_description
        assert run.tags["test_tag"] == test_mark

    def test_cancel_run(self, pf, runtime: str, randstr: Callable[[str], str]):
        # create a run
        run_name = randstr("name")
        pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=run_name,
        )

        pf.runs.cancel(run=run_name)
        sleep(3)
        run = pf.runs.get(run=run_name)
        # the run status might still be cancel requested, but it should be canceled eventually
        assert run.status in [RunStatus.CANCELED, RunStatus.CANCEL_REQUESTED]

    @pytest.mark.skipif(
        condition=not is_live(), reason="request uri contains temp folder name, need some time to sanitize."
    )
    def test_run_with_additional_includes(self, pf, runtime: str, randstr: Callable[[str], str]):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification_with_additional_include",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            inputs_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=randstr("name"),
        )
        run = pf.runs.stream(run=run.name)
        assert run.status == RunStatus.COMPLETED

        # Test additional includes don't exist
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification_with_invalid_additional_include",
                data=f"{DATAS_DIR}/webClassification1.jsonl",
                inputs_mapping={"url": "${data.url}"},
                variant="${summarize_text_content.variant_0}",
                runtime=runtime,
                name=randstr("name_invalid"),
            )
        assert "Unable to find additional include ../invalid/file/path" in str(e.value)

    @pytest.mark.skip(reason="Cannot find tools of the flow with symbolic.")
    def test_run_with_symbolic(self, remote_client, pf, runtime, prepare_symbolic_flow):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification_with_symbolic",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            inputs_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        remote_client.runs.stream(run=run.name)

    def test_run_bulk_without_retry(self, remote_client):
        from azure.core.exceptions import ServiceResponseError
        from azure.core.pipeline.transport._requests_basic import RequestsTransport
        from azure.core.rest._requests_basic import RestRequestsTransportResponse
        from requests import Response

        from promptflow.azure._restclient.flow.models import SubmitBulkRunRequest
        from promptflow.azure._restclient.flow_service_caller import FlowRequestException, FlowServiceCaller
        from promptflow.azure.operations import RunOperations

        mock_run = MagicMock()
        mock_run._runtime = "fake_runtime"
        mock_run._to_rest_object.return_value = SubmitBulkRunRequest()
        mock_run._use_remote_flow = False

        with patch.object(RunOperations, "_resolve_data_to_asset_id"), patch.object(RunOperations, "_resolve_flow"):
            with patch.object(RequestsTransport, "send") as mock_request, patch.object(
                FlowServiceCaller, "_set_headers_with_user_aml_token"
            ):
                mock_request.side_effect = ServiceResponseError(
                    "Connection aborted.",
                    error=ConnectionResetError(10054, "An existing connection was forcibly closed", None, 10054, None),
                )
                with pytest.raises(ServiceResponseError):
                    remote_client.runs.create_or_update(run=mock_run)
                # won't retry connection error since POST without response code is not retryable according to
                # retry policy
                assert mock_request.call_count == 1

        with patch.object(RunOperations, "_resolve_data_to_asset_id"), patch.object(RunOperations, "_resolve_flow"):
            with patch.object(RequestsTransport, "send") as mock_request, patch.object(
                FlowServiceCaller, "_set_headers_with_user_aml_token"
            ):
                fake_response = Response()
                # won't retry 500
                fake_response.status_code = 500
                fake_response._content = b'{"error": "error"}'
                fake_response._content_consumed = True
                mock_request.return_value = RestRequestsTransportResponse(
                    request=None,
                    internal_response=fake_response,
                )
                with pytest.raises(FlowRequestException):
                    remote_client.runs.create_or_update(run=mock_run)
                assert mock_request.call_count == 1

        with patch.object(RunOperations, "_resolve_data_to_asset_id"), patch.object(RunOperations, "_resolve_flow"):
            with patch.object(RequestsTransport, "send") as mock_request, patch.object(
                FlowServiceCaller, "_set_headers_with_user_aml_token"
            ):
                fake_response = Response()
                # will retry 503
                fake_response.status_code = 503
                fake_response._content = b'{"error": "error"}'
                fake_response._content_consumed = True
                mock_request.return_value = RestRequestsTransportResponse(
                    request=None,
                    internal_response=fake_response,
                )
                with pytest.raises(FlowRequestException):
                    remote_client.runs.create_or_update(run=mock_run)
                assert mock_request.call_count == 4

    def test_pf_run_with_env_var(self, pf, randstr: Callable[[str], str]):
        from promptflow.azure.operations import RunOperations

        def create_or_update(run, **kwargs):
            # make run.flow a datastore path uri, so that it can be parsed by AzureMLDatastorePathUri
            run.flow = "azureml://datastores/workspaceblobstore/paths/LocalUpload/not/important/path"
            return run

        with patch.object(RunOperations, "create_or_update") as mock_create_or_update:
            mock_create_or_update.side_effect = create_or_update
            env_var = {"API_BASE": "${azure_open_ai_connection.api_base}"}
            run = pf.run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables=env_var,
                name=randstr("name"),
            )
            assert run._to_rest_object().environment_variables == env_var

    def test_automatic_runtime(self, pf, randstr: Callable[[str], str]):
        from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
        from promptflow.azure.operations import RunOperations

        def submit(*args, **kwargs):
            body = kwargs.get("body", None)
            assert body.runtime_name == "automatic"
            assert body.vm_size is None
            assert body.max_idle_time_seconds is None
            return body

        with patch.object(FlowServiceCaller, "submit_bulk_run") as mock_submit, patch.object(RunOperations, "get"):
            mock_submit.side_effect = submit
            # no runtime provided, will use automatic runtime
            pf.run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                name=randstr("name1"),
            )

        with patch.object(FlowServiceCaller, "submit_bulk_run") as mock_submit, patch.object(RunOperations, "get"):
            mock_submit.side_effect = submit
            # automatic is a reserved runtime name, will use automatic runtime if specified.
            pf.run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                runtime="automatic",
                name=randstr("name2"),
            )

    def test_automatic_runtime_with_resources(self, pf, randstr: Callable[[str], str]):
        from promptflow.azure._restclient.flow.models import SessionSetupModeEnum

        source = f"{RUNS_DIR}/sample_bulk_run_with_resources.yaml"
        run_id = randstr("run_id")
        run = load_run(
            source=source,
            params_override=[{"name": run_id}],
        )
        rest_run = run._to_rest_object()
        assert rest_run.vm_size == "Standard_D2"
        assert rest_run.session_setup_mode == SessionSetupModeEnum.SYSTEM_WAIT
        run = pf.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_run_data_not_provided(self, pf, randstr: Callable[[str], str]):
        with pytest.raises(UserErrorException) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                name=randstr("name"),
            )
        assert "at least one of data or run must be provided" in str(e)

    def test_run_without_dump(self, pf, runtime: str, randstr: Callable[[str], str]) -> None:
        from promptflow._sdk._errors import RunNotFoundError
        from promptflow._sdk._orm.run_info import RunInfo

        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
            name=randstr("name"),
        )
        # cloud run should not dump to database
        with pytest.raises(RunNotFoundError):
            RunInfo.get(run.name)

    def test_input_mapping_with_dict(self, pf, runtime: str, randstr: Callable[[str], str]):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=data_path,
            column_mapping=dict(key={"a": 1}, extra="${data.url}"),
            runtime=runtime,
            name=randstr("name"),
        )
        assert '"{\\"a\\": 1}"' in run.properties["azureml.promptflow.inputs_mapping"]
        run = pf.runs.stream(run=run)
        assert run.status == "Completed"

    def test_get_invalid_run_cases(self, pf, randstr: Callable[[str], str]):
        # test get invalid run type
        with pytest.raises(InvalidRunError, match="expected 'str' or 'Run' object"):
            pf.runs.get(run=object())

        # test get invalid run name
        non_exist_run = randstr("non_exist_run")
        with pytest.raises(RunNotFoundError, match=f"Run {non_exist_run!r} not found"):
            pf.runs.get(run=non_exist_run)

    # TODO: need to confirm whether this is an end-to-end test
    def test_exp_id(self):
        with TemporaryDirectory() as tmp_dir:
            shutil.copytree(f"{FLOWS_DIR}/flow_with_dict_input", f"{tmp_dir}/flow dir with space")
            run = Run(
                flow=Path(f"{tmp_dir}/flow dir with space"),
                data=f"{DATAS_DIR}/webClassification3.jsonl",
            )
            rest_run = run._to_rest_object()
            assert rest_run.run_experiment_name == "flow_dir_with_space"

            shutil.copytree(f"{FLOWS_DIR}/flow_with_dict_input", f"{tmp_dir}/flow-dir-with-dash")
            run = Run(
                flow=Path(f"{tmp_dir}/flow-dir-with-dash"),
                data=f"{DATAS_DIR}/webClassification3.jsonl",
            )
            rest_run = run._to_rest_object()
            assert rest_run.run_experiment_name == "flow_dir_with_dash"

    def test_tools_json_ignored(self, pf, randstr: Callable[[str], str]):
        from azure.ai.ml._artifacts._blob_storage_helper import BlobStorageClient

        from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
        from promptflow.azure.operations import RunOperations

        files_to_upload = []

        def fake_upload_file(storage_client, source: str, dest, *args, **kwargs):
            files_to_upload.append(source)
            storage_client.uploaded_file_count += 1

        with patch("azure.ai.ml._utils._asset_utils.upload_file") as mock_upload_file, patch.object(
            FlowServiceCaller, "submit_bulk_run"
        ), patch.object(BlobStorageClient, "_set_confirmation_metadata"), patch.object(RunOperations, "get"):
            mock_upload_file.side_effect = fake_upload_file
            data_path = f"{DATAS_DIR}/webClassification3.jsonl"

            pf.run(
                flow=f"{FLOWS_DIR}/flow_with_dict_input",
                data=data_path,
                column_mapping={"key": {"value": "1"}, "url": "${data.url}"},
                runtime="fake_runtime",
                name=randstr("name"),
            )

            # make sure .promptflow/flow.tools.json not uploaded
            for f in files_to_upload:
                if ".promptflow/flow.tools.json" in f:
                    raise Exception(f"flow.tools.json should not be uploaded, got {f}")

    def test_flow_id_in_submission(self, pf, runtime: str, randstr: Callable[[str], str]):
        from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
        from promptflow.azure.operations import RunOperations

        flow_path = f"{FLOWS_DIR}/print_env_var"
        flow_lineage_id = get_flow_lineage_id(flow_path)
        flow_session_id = pf._runs._get_session_id(flow_path)

        def submit(*args, **kwargs):
            body = kwargs.get("body", None)
            assert flow_session_id == body.session_id
            assert flow_lineage_id == body.flow_lineage_id
            return body

        # flow session id is same with or without session creation
        with patch.object(FlowServiceCaller, "submit_bulk_run") as mock_submit, patch.object(
            RunOperations, "get"
        ), patch.object(FlowServiceCaller, "create_flow_session"):
            mock_submit.side_effect = submit
            pf.run(
                flow=flow_path,
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                runtime=runtime,
                name=randstr("name1"),
            )

        with patch.object(FlowServiceCaller, "submit_bulk_run") as mock_submit, patch.object(
            RunOperations, "get"
        ), patch.object(FlowServiceCaller, "create_flow_session"):
            mock_submit.side_effect = submit
            # no runtime provided, will use automatic runtime
            pf.run(
                flow=flow_path,
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                name=randstr("name2"),
            )

    def test_run_submission_exception(self, pf):
        from azure.core.exceptions import HttpResponseError

        from promptflow.azure._restclient.flow.operations import BulkRunsOperations
        from promptflow.azure._restclient.flow_service_caller import FlowRequestException, FlowServiceCaller

        def fake_submit(*args, **kwargs):
            headers = kwargs.get("headers", None)
            request_id_in_headers = headers["x-ms-client-request-id"]
            # request id in headers should be same with request id in service caller
            assert request_id_in_headers == pf.runs._service_caller._request_id
            raise HttpResponseError("customized error message.")

        with patch.object(BulkRunsOperations, "submit_bulk_run") as mock_request, patch.object(
            FlowServiceCaller, "_set_headers_with_user_aml_token"
        ):
            mock_request.side_effect = fake_submit
            with pytest.raises(FlowRequestException) as e:
                original_request_id = pf.runs._service_caller._request_id
                pf.runs._service_caller.submit_bulk_run(
                    subscription_id="fake_subscription_id",
                    resource_group_name="fake_resource_group",
                    workspace_name="fake_workspace_name",
                )
                # request id has been updated
                assert original_request_id != pf.runs._service_caller._request_id

            # original error message should be included in FlowRequestException
            assert "customized error message" in str(e.value)
            # request id should be included in FlowRequestException
            assert f"request id: {pf.runs._service_caller._request_id}" in str(e.value)

    def test_get_detail_against_partial_fail_run(self, pf, runtime: str, randstr: Callable[[str], str]) -> None:
        run = pf.run(
            flow=f"{FLOWS_DIR}/partial_fail",
            data=f"{FLOWS_DIR}/partial_fail/data.jsonl",
            runtime=runtime,
            name=randstr("name"),
        )
        pf.runs.stream(run=run.name)
        detail = pf.get_details(run=run.name)
        assert len(detail) == 3

    # TODO: seems another unit test...
    def test_vnext_workspace_base_url(self):
        from promptflow.azure._restclient.service_caller_factory import _FlowServiceCallerFactory

        mock_workspace = MagicMock()
        mock_workspace.discovery_url = "https://promptflow.azure-api.net/discovery/workspaces/fake_workspace_id"
        service_caller = _FlowServiceCallerFactory.get_instance(
            workspace=mock_workspace, credential=MagicMock(), operation_scope=MagicMock()
        )
        assert service_caller.caller._client._base_url == "https://promptflow.azure-api.net/"

    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_download_run(self, pf: PFClient, created_batch_run_without_llm: Run):
        expected_files = [
            DownloadedRun.RUN_METADATA_FILE_NAME,
            DownloadedRun.LOGS_FILE_NAME,
            DownloadedRun.METRICS_FILE_NAME,
            f"{DownloadedRun.SNAPSHOT_FOLDER}/flow.dag.yaml",
        ]

        with TemporaryDirectory() as tmp_dir:
            pf.runs.download(run=created_batch_run_without_llm.name, output=tmp_dir)
            for file in expected_files:
                assert Path(tmp_dir, created_batch_run_without_llm.name, file).exists()

    def test_request_id_when_making_http_requests(self, pf, runtime: str, randstr: Callable[[str], str]):
        from azure.core.exceptions import HttpResponseError

        from promptflow.azure._restclient.flow.operations import BulkRunsOperations
        from promptflow.azure._restclient.flow_service_caller import FlowRequestException

        request_ids = set()

        def fake_submit(*args, **kwargs):
            headers = kwargs.get("headers", None)
            request_id_in_headers = headers["x-ms-client-request-id"]
            # request id in headers should be same with request id in service caller
            assert request_id_in_headers == pf.runs._service_caller._request_id
            # request id in request is same request id in collected logs
            assert request_id_in_headers in request_ids
            raise HttpResponseError("customized error message.")

        def check_inner_call(*args, **kwargs):
            if "extra" in kwargs:
                request_id = pydash.get(kwargs, "extra.custom_dimensions.request_id")
                request_ids.add(request_id)

        with patch.object(BulkRunsOperations, "submit_bulk_run") as mock_request, patch.object(
            Logger, "info"
        ) as mock_logger:
            mock_logger.side_effect = check_inner_call
            mock_request.side_effect = fake_submit
            with pytest.raises(FlowRequestException) as e:
                pf.run(
                    flow=f"{FLOWS_DIR}/print_env_var",
                    data=f"{DATAS_DIR}/env_var_names.jsonl",
                    runtime=runtime,
                    name=randstr("name1"),
                )
            # request id in service caller is same request id in collected logs
            assert pf.runs._service_caller._request_id in request_ids
            # only 1 request id generated in logs
            assert len(request_ids) == 1
            # request id should be included in FlowRequestException
            assert f"request id: {pf.runs._service_caller._request_id}" in str(e.value)

            old_request_id = request_ids.pop()
            with pytest.raises(FlowRequestException) as e:
                pf.run(
                    flow=f"{FLOWS_DIR}/print_env_var",
                    data=f"{DATAS_DIR}/env_var_names.jsonl",
                    runtime=runtime,
                    name=randstr("name1"),
                )
            # request id in service caller is same request id in collected logs
            assert pf.runs._service_caller._request_id in request_ids
            # request id is not same with before
            assert old_request_id not in request_ids
            # only 1 request id generated in logs
            assert len(request_ids) == 1
            # request id should be included in FlowRequestException
            assert f"request id: {pf.runs._service_caller._request_id}" in str(e.value)

    # it is a known issue that executor/runtime might write duplicate storage for line records,
    # this will lead to the lines that assert line count (`len(detail)`) fails.
    @pytest.mark.xfail(reason="BUG 2819328: Duplicate line in flow artifacts jsonl", run=True, strict=False)
    def test_get_details_against_partial_completed_run(
        self, pf: PFClient, runtime: str, randstr: Callable[[str], str]
    ) -> None:
        flow_mod2 = f"{FLOWS_DIR}/mod-n/two"
        flow_mod3 = f"{FLOWS_DIR}/mod-n/three"
        data_path = f"{DATAS_DIR}/numbers.jsonl"
        # batch run against data
        run1 = pf.run(
            flow=flow_mod2,
            data=data_path,
            column_mapping={"number": "${data.value}"},
            runtime=runtime,
            name=randstr("run1"),
        )
        pf.runs.stream(run1)
        details1 = pf.get_details(run1)
        assert len(details1) == 20
        assert len(details1[details1["outputs.output"].notnull()]) == 10
        # assert to ensure inputs and outputs are aligned
        for _, row in details1.iterrows():
            if pd.notnull(row["outputs.output"]):
                assert int(row["inputs.number"]) == int(row["outputs.output"])

        # batch run against previous run
        run2 = pf.run(
            flow=flow_mod3,
            run=run1,
            column_mapping={"number": "${run.outputs.output}"},
            runtime=runtime,
            name=randstr("run2"),
        )
        pf.runs.stream(run2)
        details2 = pf.get_details(run2)
        assert len(details2) == 10
        assert len(details2[details2["outputs.output"].notnull()]) == 4
        # assert to ensure inputs and outputs are aligned
        for _, row in details2.iterrows():
            if pd.notnull(row["outputs.output"]):
                assert int(row["inputs.number"]) == int(row["outputs.output"])

    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_auto_resolve_requirements(self, pf: PFClient, randstr: Callable[[str], str]):
        # will add requirements.txt to flow.dag.yaml if exists when submitting run.
        with TemporaryDirectory() as temp:
            temp = Path(temp)
            shutil.copytree(f"{FLOWS_DIR}/flow_with_requirements_txt", temp / "flow_with_requirements_txt")

            run = pf.run(
                flow=temp / "flow_with_requirements_txt",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                name=randstr("name"),
            )
            pf.runs.stream(run)

            pf.runs.download(run=run.name, output=temp)
            flow_dag = load_yaml(Path(temp, run.name, "snapshot/flow.dag.yaml"))
            assert "requirements.txt" in flow_dag[ENVIRONMENT][PYTHON_REQUIREMENTS_TXT]

            local_flow_dag = load_yaml(f"{FLOWS_DIR}/flow_with_requirements_txt/flow.dag.yaml")
            assert "environment" not in local_flow_dag

    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_requirements_in_additional_includes(self, pf: PFClient, randstr: Callable[[str], str]):
        run = pf.run(
            flow=f"{FLOWS_DIR}/flow_with_additional_include_req",
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            name=randstr("name"),
        )
        run = pf.runs.stream(run)
        assert run._error is None
        with TemporaryDirectory() as temp:
            pf.runs.download(run=run.name, output=temp)
            assert Path(temp, run.name, "snapshot/requirements").exists()

    @pytest.mark.skipif(
        condition=is_live(),
        reason="removed requirement.txt to avoid compliance check.",
    )
    def test_eager_flow_crud(self, pf: PFClient, randstr: Callable[[str], str], simple_eager_run: Run):
        run = simple_eager_run
        run = pf.runs.get(run)
        assert run.status == RunStatus.COMPLETED

        details = pf.runs.get_details(run)
        assert details.shape[0] == 1
        metrics = pf.runs.get_metrics(run)
        assert metrics == {}

        # TODO(2917923): cannot differ the two requests to run history in replay mode."
        # run_meta_data = RunHistoryKeys.RunMetaData
        # hidden = RunHistoryKeys.HIDDEN
        # run_id = run.name
        # # test archive
        # pf.runs.archive(run=run_id)
        # run_data = pf.runs._get_run_from_run_history(run_id, original_form=True)[run_meta_data]
        # assert run_data[hidden] is True
        #
        # # test restore
        # pf.runs.restore(run=run_id)
        # run_data = pf.runs._get_run_from_run_history(run_id, original_form=True)[run_meta_data]
        # assert run_data[hidden] is False

    @pytest.mark.skipif(
        condition=is_live(),
        reason="removed requirement.txt to avoid compliance check.",
    )
    def test_eager_flow_cancel(self, pf: PFClient, randstr: Callable[[str], str]):
        """Test cancel eager flow."""
        # create a run
        run_name = randstr("name")
        pf.run(
            flow=f"{EAGER_FLOWS_DIR}/long_running",
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            name=run_name,
        )

        pf.runs.cancel(run=run_name)
        sleep(3)
        run = pf.runs.get(run=run_name)
        # the run status might still be cancel requested, but it should be canceled eventually
        assert run.status in [RunStatus.CANCELED, RunStatus.CANCEL_REQUESTED]

    @pytest.mark.skipif(
        condition=is_live(),
        reason="removed requirement.txt to avoid compliance check.",
    )
    @pytest.mark.usefixtures("mock_isinstance_for_mock_datastore")
    def test_eager_flow_download(self, pf: PFClient, simple_eager_run: Run):
        run = simple_eager_run
        expected_files = [
            DownloadedRun.RUN_METADATA_FILE_NAME,
            DownloadedRun.LOGS_FILE_NAME,
            DownloadedRun.METRICS_FILE_NAME,
            f"{DownloadedRun.SNAPSHOT_FOLDER}/flow.dag.yaml",
        ]

        # test download
        with TemporaryDirectory() as tmp_dir:
            pf.runs.download(run=run.name, output=tmp_dir)
            for file in expected_files:
                assert Path(tmp_dir, run.name, file).exists()

    @pytest.mark.skipif(
        condition=not is_live(),
        reason="Enable this after fixed sanitizer.",
    )
    def test_run_with_compute_instance_session(
        self, pf: PFClient, compute_instance_name: str, randstr: Callable[[str], str]
    ):
        run = Run(
            flow=Path(f"{FLOWS_DIR}/print_env_var"),
            data=f"{DATAS_DIR}/env_var_names.jsonl",
            name=randstr("name"),
            resources={"compute": compute_instance_name},
        )
        rest_run = run._to_rest_object()
        assert rest_run.compute_name == compute_instance_name

        run = pf.runs.create_or_update(
            run=run,
        )
        assert isinstance(run, Run)

        run = pf.stream(run)
        assert run.status == RunStatus.COMPLETED

    @pytest.mark.skipif(
        condition=not is_live(),
        reason="Enable this after fixed sanitizer.",
    )
    def test_run_with_compute_instance_session_yml(
        self, pf: PFClient, compute_instance_name: str, randstr: Callable[[str], str]
    ):
        source = f"{RUNS_DIR}/sample_bulk_run_with_compute_instance.yaml"
        run_id = randstr("run_id")
        run = load_run(
            source=source,
            params_override=[{"name": run_id}],
        )
        rest_run = run._to_rest_object()
        assert rest_run.compute_name == "my_ci"

        # update ci to actual ci
        run._resources["compute"] = compute_instance_name
        run = pf.runs.create_or_update(run=run)
        assert isinstance(run, Run)

        run = pf.stream(run)
        assert run.status == RunStatus.COMPLETED
