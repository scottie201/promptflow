from typing import Union

from openai import AzureOpenAI as AzureOpenAIClient, OpenAI as OpenAIClient
from promptflow.tools.common import render_jinja_template, handle_openai_error, parse_chat, \
    preprocess_template_string, find_referenced_image_set, convert_to_chat_list, normalize_connection_config, \
    post_process_chat_api_response, validate_functions, process_function_call
from promptflow.tools.exception import InvalidConnectionType

# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.tools.aoai_gpt4v import _get_credential, _parse_resource_id, ListDeploymentsError, _build_deployment_dict
from typing import List, Dict

def list_deployment_names(
    subscription_id,
    resource_group_name,
    workspace_name,
    connection: AzureOpenAIConnection = None,
) -> List[Dict[str, str]]:
    res = []
    try:
        # Does not support dynamic list for local.
        from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
        from promptflow.azure.operations._arm_connection_operations import \
            ArmConnectionOperations, OpenURLFailedUserError
    except ImportError:
        return res
    # For local, subscription_id is None. Does not suppot dynamic list for local.
    if not subscription_id:
        return res

    try:
        credential = _get_credential()
        try:
            conn = ArmConnectionOperations._build_connection_dict(
                name=connection,
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                credential=credential
            )
            resource_id = conn.get("value").get('resource_id', "")
            if not resource_id:
                return res
            conn_sub, conn_rg, conn_account = _parse_resource_id(resource_id)
        except OpenURLFailedUserError:
            return res
        except ListDeploymentsError as e:
            raise e
        except Exception as e:
            msg = f"Parsing connection with exception: {e}"
            raise ListDeploymentsError(msg=msg) from e

        client = CognitiveServicesManagementClient(
            credential=credential,
            subscription_id=conn_sub,
        )
        deployment_collection = client.deployments.list(
            resource_group_name=conn_rg,
            account_name=conn_account,
        )

        for item in deployment_collection:
            deployment = _build_deployment_dict(item)
            cur_item = {
                "value": deployment.name,
                "display_value": deployment.name,
            }
            res.append(cur_item)

    except Exception as e:
        if hasattr(e, 'status_code') and e.status_code == 403:
            msg = f"Failed to list deployments due to permission issue: {e}"
            raise ListDeploymentsError(msg=msg) from e
        else:
            msg = f"Failed to list deployments with exception: {e}"
            raise ListDeploymentsError(msg=msg) from e

    return res


@tool
@handle_openai_error()
def chat(
    connection: Union[AzureOpenAIConnection, OpenAIConnection], 
    prompt: str,
    deployment_name: str = "", model: str = "",
    temperature: float = 1.0,
    top_p: float = 1.0,
    # stream is a hidden to the end user, it is only supposed to be set by the executor.
    stream: bool = False,
    stop: list = None,
    max_tokens: int = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    logit_bias: dict = {},
    # function_call can be of type str or dict.
    function_call: object = None,
    functions: list = None,
    response_format: object = None,
    **kwargs,
):
    # 1. init client
    if isinstance(connection, AzureOpenAIConnection):
        client = AzureOpenAIClient(**normalize_connection_config(connection))
    elif isinstance(connection, OpenAIConnection):
        client = OpenAIClient(**normalize_connection_config(connection))
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for embedding api. " \
                        f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        raise InvalidConnectionType(message=error_message)

    # 2. deal with prompt
    # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
    prompt = preprocess_template_string(prompt)
    referenced_images = find_referenced_image_set(kwargs)

    # convert list type into ChatInputList type
    converted_kwargs = convert_to_chat_list(kwargs)
    chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs)
    messages = parse_chat(chat_str, list(referenced_images))

    # 3. prepare params
    params = {
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "n": 1,
        "stream": stream,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
    }

    # to avoid gptv model validation error for empty param values.
    if stop:
        params["stop"] = stop
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    if logit_bias:
        params["logit_bias"] = logit_bias
    if response_format:
        params["response_format"] = response_format

    if functions is not None:
        validate_functions(functions)
        params["functions"] = functions
        params["function_call"] = process_function_call(function_call)

    if isinstance(connection, AzureOpenAIConnection):
        params["model"] = deployment_name
        params["extra_headers"] = {"ms-azure-ai-promptflow-called-from": "aoai-tool"}
    elif isinstance(connection, OpenAIConnection):
        params["model"] = model

    # 4. call chat api
    completion = client.chat.completions.create(**params)
    return post_process_chat_api_response(completion, stream, None)
