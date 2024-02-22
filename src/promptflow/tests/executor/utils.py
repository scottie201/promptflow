import json
from pathlib import Path
from typing import Dict, Union

import opentelemetry
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.storage import AbstractRunStorage

TEST_ROOT = Path(__file__).parent.parent
DATA_ROOT = TEST_ROOT / "test_configs/datas"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"
EAGER_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"
WRONG_FLOW_ROOT = TEST_ROOT / "test_configs/wrong_flows"
EAGER_FLOWS_ROOT = TEST_ROOT / "test_configs/eager_flows"


def get_flow_folder(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_folder_path = Path(root) / folder_name
    return flow_folder_path


def get_yaml_file(folder_name, root: str = FLOW_ROOT, file_name: str = "flow.dag.yaml") -> Path:
    yaml_file = get_flow_folder(folder_name, root) / file_name
    return yaml_file


def get_entry_file(folder_name, root: str = EAGER_FLOW_ROOT, file_name: str = "entry.py") -> Path:
    entry_file = get_flow_folder(folder_name, root) / file_name
    return entry_file


def get_flow_from_folder(folder_name, root: str = FLOW_ROOT, file_name: str = "flow.dag.yaml"):
    flow_yaml = get_yaml_file(folder_name, root, file_name)
    with open(flow_yaml, "r") as fin:
        return Flow.deserialize(load_yaml(fin))


def get_flow_inputs_file(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.jsonl") -> Path:
    inputs_file = get_flow_folder(folder_name, root) / file_name
    return inputs_file


def get_flow_inputs(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.json"):
    inputs = load_json(get_flow_inputs_file(folder_name, root, file_name))
    return inputs[0] if isinstance(inputs, list) else inputs


def get_bulk_inputs_from_jsonl(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.jsonl"):
    inputs = load_jsonl(get_flow_inputs_file(folder_name, root, file_name))
    return inputs


def get_bulk_inputs(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.json"):
    inputs = load_json(get_flow_inputs_file(folder_name, root=root, file_name=file_name))
    return [inputs] if isinstance(inputs, dict) else inputs


def get_flow_sample_inputs(folder_name, root: str = FLOW_ROOT, sample_inputs_file="samples.json"):
    samples_inputs = load_json(get_flow_folder(folder_name, root) / sample_inputs_file)
    return samples_inputs


def get_flow_expected_metrics(folder_name):
    samples_inputs = load_json(get_flow_folder(folder_name) / "expected_metrics.json")
    return samples_inputs


def get_flow_expected_status_summary(folder_name):
    samples_inputs = load_json(get_flow_folder(folder_name) / "expected_status_summary.json")
    return samples_inputs


def get_flow_expected_result(folder_name):
    samples_inputs = load_json(get_flow_folder(folder_name) / "expected_result.json")
    return samples_inputs


def get_flow_package_tool_definition(folder_name):
    return load_json(get_flow_folder(folder_name) / "package_tool_definition.json")


def load_json(source: Union[str, Path]) -> dict:
    """Load json file to dict"""
    with open(source, "r") as f:
        loaded_data = json.load(f)
    return loaded_data


def load_jsonl(source: Union[str, Path]) -> list:
    """Load jsonl file to list"""
    with open(source, "r") as f:
        loaded_data = [json.loads(line.strip()) for line in f]
    return loaded_data


def load_content(source: Union[str, Path]) -> str:
    """Load file content to string"""
    return Path(source).read_text()


def is_jsonl_file(file_path: Path):
    return file_path.suffix.lower() == ".jsonl"


def is_image_file(file_path: Path):
    image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
    file_extension = file_path.suffix.lower()
    return file_extension in image_extensions


class MemoryRunStorage(AbstractRunStorage):
    def __init__(self):
        self._node_runs: Dict[str, NodeRunInfo] = {}
        self._flow_runs: Dict[str, FlowRunInfo] = {}

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._flow_runs[run_info.run_id] = run_info

    def persist_node_run(self, run_info: NodeRunInfo):
        self._node_runs[run_info.run_id] = run_info


def prepare_memory_exporter():
    tracer_provider = TracerProvider()
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    tracer_provider.add_span_processor(span_processor)
    opentelemetry.trace.set_tracer_provider(tracer_provider)
    return memory_exporter
