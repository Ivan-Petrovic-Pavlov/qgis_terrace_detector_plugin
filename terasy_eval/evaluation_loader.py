"""Load a user-selected terrace evaluation script."""

import importlib.util
import os
import sys
import uuid


def bundled_evaluator_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vyhodnot.py")


def load_evaluator(script_path):
    script_path = os.path.abspath(os.path.expanduser(script_path))
    if not os.path.isfile(script_path) or not script_path.lower().endswith(".py"):
        raise ValueError(f"Evaluation script must be an existing .py file: {script_path}")

    module_name = f"terrace_evaluator_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create an import loader for {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise ImportError(f"Could not import {script_path}: {exc}") from exc

    evaluator = getattr(module, "vyhodnot", None)
    if not callable(evaluator):
        sys.modules.pop(module_name, None)
        raise ValueError("The script must define a callable vyhodnot(...).")
    return evaluator