from enum import Enum
from typing import Union

from openai import AzureOpenAI, OpenAI

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import handle_openai_error
from promptflow.tools.exception import InvalidConnectionType


class EmbeddingModel(str, Enum):
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_SEARCH_ADA_DOC_001 = "text-search-ada-doc-001"
    TEXT_SEARCH_ADA_QUERY_001 = "text-search-ada-query-001"


@tool
@handle_openai_error()
def embedding(connection: Union[AzureOpenAIConnection, OpenAIConnection], input: str, deployment_name: str = "",
              model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_ADA_002):
    if isinstance(connection, AzureOpenAIConnection):
        client = AzureOpenAI(
            api_key=connection.api_key,
            api_version=connection.api_version,
            azure_endpoint=connection.api_base
        )
        return client.embeddings.create(
            input=input,
            model=deployment_name,
            extra_headers={"ms-azure-ai-promptflow-called-from": "aoai-tool"}
        )["data"][0]["embedding"]
    elif isinstance(connection, OpenAIConnection):
        client = OpenAI(
            api_key=connection.api_key,
            organization=connection.organization,
            base_url=connection.base_url
        )
        return client.embeddings.create(
            input=input,
            model=model
        )["data"][0]["embedding"]
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for embedding api. " \
                        f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        raise InvalidConnectionType(message=error_message)
