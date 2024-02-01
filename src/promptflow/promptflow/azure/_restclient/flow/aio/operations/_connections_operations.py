# coding=utf-8
# --------------------------------------------------------------------------
# Code generated by Microsoft (R) AutoRest Code Generator (autorest: 3.8.0, generator: @autorest/python@5.12.2)
# Changes may cause incorrect behavior and will be lost if the code is regenerated.
# --------------------------------------------------------------------------
import functools
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
import warnings

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
    map_error,
)
from azure.core.pipeline import PipelineResponse
from azure.core.pipeline.transport import AsyncHttpResponse
from azure.core.rest import HttpRequest
from azure.core.tracing.decorator_async import distributed_trace_async

from ... import models as _models
from ..._vendor import _convert_request
from ...operations._connections_operations import (
    build_create_connection_request,
    build_delete_connection_request,
    build_get_connection_request,
    build_get_connection_with_secrets_request,
    build_list_azure_open_ai_deployments_request,
    build_list_connection_specs_request,
    build_list_connections_request,
    build_update_connection_request,
)

T = TypeVar("T")
ClsType = Optional[Callable[[PipelineResponse[HttpRequest, AsyncHttpResponse], T, Dict[str, Any]], Any]]


class ConnectionsOperations:
    """ConnectionsOperations async operations.

    You should not instantiate this class directly. Instead, you should create a Client instance that
    instantiates it for you and attaches it as an attribute.

    :ivar models: Alias to model classes used in this operation group.
    :type models: ~flow.models
    :param client: Client for service requests.
    :param config: Configuration of service client.
    :param serializer: An object model serializer.
    :param deserializer: An object model deserializer.
    """

    models = _models

    def __init__(self, client, config, serializer, deserializer) -> None:
        self._client = client
        self._serialize = serializer
        self._deserialize = deserializer
        self._config = config

    @distributed_trace_async
    async def create_connection(
        self,
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
        connection_name: str,
        body: Optional["_models.CreateOrUpdateConnectionRequestDto"] = None,
        **kwargs: Any
    ) -> "_models.ConnectionDto":
        """create_connection.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param connection_name:
        :type connection_name: str
        :param body:
        :type body: ~flow.models.CreateOrUpdateConnectionRequestDto
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: ConnectionDto, or the result of cls(response)
        :rtype: ~flow.models.ConnectionDto
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType["_models.ConnectionDto"]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        content_type = kwargs.pop("content_type", "application/json")  # type: Optional[str]

        if body is not None:
            _json = self._serialize.body(body, "CreateOrUpdateConnectionRequestDto")
        else:
            _json = None

        request = build_create_connection_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            connection_name=connection_name,
            content_type=content_type,
            json=_json,
            template_url=self.create_connection.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("ConnectionDto", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    create_connection.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/{connectionName}"}  # type: ignore

    @distributed_trace_async
    async def update_connection(
        self,
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
        connection_name: str,
        body: Optional["_models.CreateOrUpdateConnectionRequestDto"] = None,
        **kwargs: Any
    ) -> "_models.ConnectionDto":
        """update_connection.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param connection_name:
        :type connection_name: str
        :param body:
        :type body: ~flow.models.CreateOrUpdateConnectionRequestDto
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: ConnectionDto, or the result of cls(response)
        :rtype: ~flow.models.ConnectionDto
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType["_models.ConnectionDto"]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        content_type = kwargs.pop("content_type", "application/json")  # type: Optional[str]

        if body is not None:
            _json = self._serialize.body(body, "CreateOrUpdateConnectionRequestDto")
        else:
            _json = None

        request = build_update_connection_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            connection_name=connection_name,
            content_type=content_type,
            json=_json,
            template_url=self.update_connection.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("ConnectionDto", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    update_connection.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/{connectionName}"}  # type: ignore

    @distributed_trace_async
    async def get_connection(
        self, subscription_id: str, resource_group_name: str, workspace_name: str, connection_name: str, **kwargs: Any
    ) -> "_models.ConnectionDto":
        """get_connection.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param connection_name:
        :type connection_name: str
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: ConnectionDto, or the result of cls(response)
        :rtype: ~flow.models.ConnectionDto
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType["_models.ConnectionDto"]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        request = build_get_connection_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            connection_name=connection_name,
            template_url=self.get_connection.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("ConnectionDto", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    get_connection.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/{connectionName}"}  # type: ignore

    @distributed_trace_async
    async def delete_connection(
        self, subscription_id: str, resource_group_name: str, workspace_name: str, connection_name: str, **kwargs: Any
    ) -> "_models.ConnectionDto":
        """delete_connection.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param connection_name:
        :type connection_name: str
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: ConnectionDto, or the result of cls(response)
        :rtype: ~flow.models.ConnectionDto
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType["_models.ConnectionDto"]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        request = build_delete_connection_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            connection_name=connection_name,
            template_url=self.delete_connection.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("ConnectionDto", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    delete_connection.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/{connectionName}"}  # type: ignore

    @distributed_trace_async
    async def get_connection_with_secrets(
        self, subscription_id: str, resource_group_name: str, workspace_name: str, connection_name: str, **kwargs: Any
    ) -> "_models.ConnectionDto":
        """get_connection_with_secrets.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param connection_name:
        :type connection_name: str
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: ConnectionDto, or the result of cls(response)
        :rtype: ~flow.models.ConnectionDto
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType["_models.ConnectionDto"]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        request = build_get_connection_with_secrets_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            connection_name=connection_name,
            template_url=self.get_connection_with_secrets.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("ConnectionDto", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    get_connection_with_secrets.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/{connectionName}/listsecrets"}  # type: ignore

    @distributed_trace_async
    async def list_connections(
        self, subscription_id: str, resource_group_name: str, workspace_name: str, **kwargs: Any
    ) -> List["_models.ConnectionDto"]:
        """list_connections.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: list of ConnectionDto, or the result of cls(response)
        :rtype: list[~flow.models.ConnectionDto]
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType[List["_models.ConnectionDto"]]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        request = build_list_connections_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            template_url=self.list_connections.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("[ConnectionDto]", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    list_connections.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections"}  # type: ignore

    @distributed_trace_async
    async def list_connection_specs(
        self, subscription_id: str, resource_group_name: str, workspace_name: str, **kwargs: Any
    ) -> List["_models.WorkspaceConnectionSpec"]:
        """list_connection_specs.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: list of WorkspaceConnectionSpec, or the result of cls(response)
        :rtype: list[~flow.models.WorkspaceConnectionSpec]
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType[List["_models.WorkspaceConnectionSpec"]]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        request = build_list_connection_specs_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            template_url=self.list_connection_specs.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("[WorkspaceConnectionSpec]", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    list_connection_specs.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/specs"}  # type: ignore

    @distributed_trace_async
    async def list_azure_open_ai_deployments(
        self, subscription_id: str, resource_group_name: str, workspace_name: str, connection_name: str, **kwargs: Any
    ) -> List["_models.AzureOpenAIDeploymentDto"]:
        """list_azure_open_ai_deployments.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param connection_name:
        :type connection_name: str
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: list of AzureOpenAIDeploymentDto, or the result of cls(response)
        :rtype: list[~flow.models.AzureOpenAIDeploymentDto]
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        cls = kwargs.pop("cls", None)  # type: ClsType[List["_models.AzureOpenAIDeploymentDto"]]
        error_map = {401: ClientAuthenticationError, 404: ResourceNotFoundError, 409: ResourceExistsError}
        error_map.update(kwargs.pop("error_map", {}))

        request = build_list_azure_open_ai_deployments_request(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            connection_name=connection_name,
            template_url=self.list_azure_open_ai_deployments.metadata["url"],
        )
        request = _convert_request(request)
        request.url = self._client.format_url(request.url)

        pipeline_response = await self._client._pipeline.run(request, stream=False, **kwargs)
        response = pipeline_response.http_response

        if response.status_code not in [200]:
            map_error(status_code=response.status_code, response=response, error_map=error_map)
            error = self._deserialize.failsafe_deserialize(_models.ErrorResponse, pipeline_response)
            raise HttpResponseError(response=response, model=error)

        deserialized = self._deserialize("[AzureOpenAIDeploymentDto]", pipeline_response)

        if cls:
            return cls(pipeline_response, deserialized, {})

        return deserialized

    list_azure_open_ai_deployments.metadata = {"url": "/flow/api/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.MachineLearningServices/workspaces/{workspaceName}/Connections/{connectionName}/AzureOpenAIDeployments"}  # type: ignore
