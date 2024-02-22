# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.logger_utils import service_logger
from promptflow.executor._service.contracts.execution_request import FlowExecutionRequest, NodeExecutionRequest
from promptflow.executor._service.utils.process_utils import invoke_sync_function_in_process
from promptflow.executor._service.utils.service_utils import (
    get_log_context,
    get_service_log_context,
    set_environment_variables,
    update_and_get_operation_context,
)
from promptflow.executor.flow_executor import FlowExecutor, execute_flow
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter(prefix="/execution")


@router.post("/flow")
async def flow_execution(request: FlowExecutionRequest):
    with get_service_log_context(request):
        operation_context = update_and_get_operation_context(request.operation_context)
        service_logger.info(
            f"Received flow execution request, flow run id: {request.run_id}, "
            f"request id: {operation_context.get_request_id()}, executor version: {operation_context.get_user_agent()}."
        )
        try:
            result = await invoke_sync_function_in_process(
                flow_test, args=(request,), context_dict=request.operation_context
            )
            service_logger.info(f"Completed flow execution request, flow run id: {request.run_id}.")
            return result
        except Exception as ex:
            error_type_and_message = (f"({ex.__class__.__name__}) {ex}",)
            service_logger.error(
                f"Failed to execute flow, flow run id: {request.run_id}. Error: {error_type_and_message}"
            )
            raise ex


@router.post("/node")
async def node_execution(request: NodeExecutionRequest):
    with get_service_log_context(request):
        operation_context = update_and_get_operation_context(request.operation_context)
        service_logger.info(
            f"Received node execution request, node name: {request.node_name}, "
            f"request id: {operation_context.get_request_id()}, executor version: {operation_context.get_user_agent()}."
        )
        try:
            result = await invoke_sync_function_in_process(
                single_node_run, args=(request,), context_dict=request.operation_context
            )
            service_logger.info(f"Completed node execution request, node name: {request.node_name}.")
            return result
        except Exception as ex:
            error_type_and_message = (f"({ex.__class__.__name__}) {ex}",)
            service_logger.error(
                f"Failed to execute node, node name: {request.node_name}. Error: {error_type_and_message}"
            )
            raise ex


def flow_test(request: FlowExecutionRequest):
    # validate request
    request.validate_request()
    # resolve environment variables
    set_environment_variables(request)
    # execute flow
    storage = DefaultRunStorage(base_dir=request.working_dir, sub_dir=request.output_dir)
    with get_log_context(request):
        return execute_flow(
            request.flow_file,
            request.working_dir,
            request.output_dir,
            request.connections,
            request.inputs,
            run_id=request.run_id,
            storage=storage,
        )


def single_node_run(request: NodeExecutionRequest):
    # validate request
    request.validate_request()
    # resolve environment variables
    set_environment_variables(request)
    storage = DefaultRunStorage(base_dir=request.working_dir, sub_dir=request.output_dir)
    with _change_working_dir(request.working_dir), get_log_context(request):
        return FlowExecutor.load_and_exec_node(
            request.flow_file,
            request.node_name,
            flow_inputs=request.flow_inputs,
            dependency_nodes_outputs=request.dependency_nodes_outputs,
            connections=request.connections,
            working_dir=request.working_dir,
            storage=storage,
        )
