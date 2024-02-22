# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import datetime
import json
import typing
from dataclasses import dataclass

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._constants import (
    DEFAULT_SPAN_TYPE,
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._constants import CumulativeTokenCountFieldName
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._utils import (
    convert_time_unix_nano_to_timestamp,
    flatten_pb_attributes,
    parse_otel_span_status_code,
)


class Span:
    """Span is exactly the same as OpenTelemetry Span."""

    def __init__(
        self,
        name: str,
        context: typing.Dict[str, str],
        kind: str,
        start_time: str,
        end_time: str,
        status: str,
        attributes: typing.Dict[str, str],
        resource: typing.Dict,
        # should come from attributes
        span_type: str,
        session_id: str,
        # optional fields
        parent_span_id: typing.Optional[str] = None,
        events: typing.Optional[typing.List] = None,
        links: typing.Optional[typing.List] = None,
        # prompt flow concepts
        path: typing.Optional[str] = None,
        run: typing.Optional[str] = None,
        experiment: typing.Optional[str] = None,
    ):
        self.name = name
        self.span_id = context[SpanContextFieldName.SPAN_ID]
        self.trace_id = context[SpanContextFieldName.TRACE_ID]
        self.span_type = span_type
        self.parent_span_id = parent_span_id
        self.session_id = session_id
        self.path = path
        self.run = run
        self.experiment = experiment
        self._content = {
            SpanFieldName.NAME: self.name,
            SpanFieldName.CONTEXT: copy.deepcopy(context),
            SpanFieldName.KIND: kind,
            SpanFieldName.PARENT_ID: self.parent_span_id,
            SpanFieldName.START_TIME: start_time,
            SpanFieldName.END_TIME: end_time,
            SpanFieldName.STATUS: status,
            SpanFieldName.ATTRIBUTES: copy.deepcopy(attributes),
            SpanFieldName.EVENTS: copy.deepcopy(events),
            SpanFieldName.LINKS: copy.deepcopy(links),
            SpanFieldName.RESOURCE: copy.deepcopy(resource),
        }

    def _persist(self) -> None:
        self._to_orm_object().persist()

    @staticmethod
    def _from_orm_object(obj: ORMSpan) -> "Span":
        content = json.loads(obj.content)
        return Span(
            name=obj.name,
            context=content[SpanFieldName.CONTEXT],
            kind=content[SpanFieldName.KIND],
            start_time=content[SpanFieldName.START_TIME],
            end_time=content[SpanFieldName.END_TIME],
            status=content[SpanFieldName.STATUS],
            attributes=content[SpanFieldName.ATTRIBUTES],
            resource=content[SpanFieldName.RESOURCE],
            span_type=obj.span_type,
            session_id=obj.session_id,
            parent_span_id=obj.parent_span_id,
            events=content[SpanFieldName.EVENTS],
            links=content[SpanFieldName.LINKS],
            path=obj.path,
            run=obj.run,
            experiment=obj.experiment,
        )

    def _to_orm_object(self) -> ORMSpan:
        return ORMSpan(
            name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            span_type=self.span_type,
            session_id=self.session_id,
            content=json.dumps(self._content),
            path=self.path,
            run=self.run,
            experiment=self.experiment,
        )

    @staticmethod
    def _from_protobuf_object(obj: PBSpan, resource: typing.Dict) -> "Span":
        span_dict: dict = json.loads(MessageToJson(obj))
        span_id = obj.span_id.hex()
        trace_id = obj.trace_id.hex()
        context = {
            SpanContextFieldName.TRACE_ID: trace_id,
            SpanContextFieldName.SPAN_ID: span_id,
            SpanContextFieldName.TRACE_STATE: obj.trace_state,
        }
        parent_span_id = obj.parent_span_id.hex()
        start_time = convert_time_unix_nano_to_timestamp(obj.start_time_unix_nano)
        end_time = convert_time_unix_nano_to_timestamp(obj.end_time_unix_nano)
        status = {
            SpanStatusFieldName.STATUS_CODE: parse_otel_span_status_code(obj.status.code),
        }
        # we have observed in some scenarios, there is not `attributes` field
        attributes = flatten_pb_attributes(span_dict.get(SpanFieldName.ATTRIBUTES, dict()))
        # `span_type` are not standard fields in OpenTelemetry attributes
        # for example, LangChain instrumentation, as we do not inject this;
        # so we need to get it with default value to avoid KeyError
        span_type = attributes.get(SpanAttributeFieldName.SPAN_TYPE, DEFAULT_SPAN_TYPE)

        # parse from resource.attributes: session id, experiment
        resource_attributes: dict = resource[SpanResourceFieldName.ATTRIBUTES]
        session_id = resource_attributes[SpanResourceAttributesFieldName.SESSION_ID]
        experiment = resource_attributes.get(SpanResourceAttributesFieldName.EXPERIMENT_NAME, None)

        return Span(
            name=obj.name,
            context=context,
            kind=obj.kind,
            start_time=start_time,
            end_time=end_time,
            status=status,
            attributes=attributes,
            resource=resource,
            span_type=span_type,
            session_id=session_id,
            parent_span_id=parent_span_id,
            experiment=experiment,
        )


@dataclass
class _LineRunData:
    """Basic data structure for line run, no matter if it is a main or evaluation."""

    line_run_id: str
    trace_id: str
    root_span_id: str
    inputs: typing.Dict
    outputs: typing.Dict
    start_time: str
    end_time: str
    status: str
    latency: float
    display_name: str
    kind: str
    cumulative_token_count: typing.Optional[typing.Dict[str, int]]

    def _from_root_span(span: Span) -> "_LineRunData":
        attributes: dict = span._content[SpanFieldName.ATTRIBUTES]
        if SpanAttributeFieldName.LINE_RUN_ID in attributes:
            line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
        elif SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes:
            line_run_id = attributes[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID]
        else:
            # eager flow/arbitrary script
            line_run_id = span.trace_id
        start_time = datetime.datetime.fromisoformat(span._content[SpanFieldName.START_TIME])
        end_time = datetime.datetime.fromisoformat(span._content[SpanFieldName.END_TIME])
        # calculate `cumulative_token_count`
        completion_token_count = int(attributes.get(SpanAttributeFieldName.COMPLETION_TOKEN_COUNT, 0))
        prompt_token_count = int(attributes.get(SpanAttributeFieldName.PROMPT_TOKEN_COUNT, 0))
        total_token_count = int(attributes.get(SpanAttributeFieldName.TOTAL_TOKEN_COUNT, 0))
        # if there is no token usage, set `cumulative_token_count` to None
        if total_token_count > 0:
            cumulative_token_count = {
                CumulativeTokenCountFieldName.COMPLETION: completion_token_count,
                CumulativeTokenCountFieldName.PROMPT: prompt_token_count,
                CumulativeTokenCountFieldName.TOTAL: total_token_count,
            }
        else:
            cumulative_token_count = None
        return _LineRunData(
            line_run_id=line_run_id,
            trace_id=span.trace_id,
            root_span_id=span.span_id,
            # for standard OpenTelemetry traces, there won't be `inputs` and `outputs` in attributes
            inputs=json.loads(attributes.get(SpanAttributeFieldName.INPUTS, "{}")),
            outputs=json.loads(attributes.get(SpanAttributeFieldName.OUTPUT, "{}")),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            status=span._content[SpanFieldName.STATUS][SpanStatusFieldName.STATUS_CODE],
            latency=(end_time - start_time).total_seconds(),
            display_name=span.name,
            kind=attributes.get(SpanAttributeFieldName.SPAN_TYPE, span.span_type),
            cumulative_token_count=cumulative_token_count,
        )


@dataclass
class LineRun:
    """Line run is an abstraction of spans related to prompt flow."""

    line_run_id: str
    trace_id: str
    root_span_id: str
    inputs: typing.Dict
    outputs: typing.Dict
    start_time: str
    end_time: str
    status: str
    latency: float
    display_name: str
    kind: str
    cumulative_token_count: typing.Optional[typing.Dict[str, int]] = None
    evaluations: typing.Optional[typing.List[typing.Dict]] = None

    @staticmethod
    def _from_spans(spans: typing.List[Span]) -> typing.Optional["LineRun"]:
        main_line_run_data: _LineRunData = None
        evaluations = []
        for span in spans:
            if span.parent_span_id:
                continue
            attributes = span._content[SpanFieldName.ATTRIBUTES]
            if (
                SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes  # test scenario
                or SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID in attributes  # batch run scenario
            ):
                evaluations.append(_LineRunData._from_root_span(span))
            elif SpanAttributeFieldName.LINE_RUN_ID in attributes:
                main_line_run_data = _LineRunData._from_root_span(span)
            else:
                # eager flow/arbitrary script
                main_line_run_data = _LineRunData._from_root_span(span)
        # main line run span is absent, ignore this line run
        # this may happen when the line is still executing, or terminated;
        # or the line run is killed before the traces exported
        if main_line_run_data is None:
            return None

        return LineRun(
            line_run_id=main_line_run_data.line_run_id,
            trace_id=main_line_run_data.trace_id,
            root_span_id=main_line_run_data.root_span_id,
            inputs=main_line_run_data.inputs,
            outputs=main_line_run_data.outputs,
            start_time=main_line_run_data.start_time,
            end_time=main_line_run_data.end_time,
            status=main_line_run_data.status,
            latency=main_line_run_data.latency,
            display_name=main_line_run_data.display_name,
            kind=main_line_run_data.kind,
            cumulative_token_count=main_line_run_data.cumulative_token_count,
            evaluations=evaluations,
        )
