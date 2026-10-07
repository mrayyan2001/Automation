"""Application configuration loading and environment-variable substitution."""

import copy
import os
import re
from pathlib import (
    Path,
)

import yaml
from dotenv import (
    load_dotenv,
)

CONFIG_DIR = Path(__file__).resolve().parent
"""Directory containing the package's YAML configuration files."""

VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?}")
"""Pattern matching required and defaulted environment-variable references."""

COMMON_CONFIG_FILE_NAME = "common.yaml"
"""Name of the configuration file shared by all environments."""

ENV_CONFIG_FILE_NAME = "{env}.yaml"
"""Template used to locate an environment-specific configuration file."""

ENV_REPLACE_KEY = "{env}"
"""Placeholder replaced with the normalized application environment."""

ENV_FILE_NAME = ".env"
"""Name of the dotenv file loaded before YAML configuration."""

ENVIRONMENT_KEY = "APP_ENV"
"""Environment variable selecting the environment-specific YAML file."""


def replace_variable(
    match: re.Match[str],
) -> str:
    """Resolve a YAML environment-variable reference.

    Args:
        match: Match containing the variable name and optional default value.

    Returns:
        The environment value or the supplied default value.

    Raises:
        RuntimeError: If the variable is required but not set.
    """
    name = match.group(1)
    default = match.group(2)
    value = os.getenv(name)
    if value is not None:
        return value
    if default is not None:
        return default
    raise RuntimeError(f"Missing required environment variable: {name}")


def deep_merge(
    base: dict,
    overrides: dict,
) -> dict:
    """Recursively merge overrides into a copy of the base mapping.

    Nested dictionaries are merged recursively; all other override values
    replace the corresponding base value.

    Args:
        base: Base configuration mapping.
        overrides: Values that take precedence over ``base``.

    Returns:
        A merged mapping. The input mappings are not modified.
    """
    result = copy.deepcopy(base)
    for (
        key,
        value,
    ) in overrides.items():
        if (
            isinstance(
                value,
                dict,
            )
            and key in result
            and isinstance(
                result[key],
                dict,
            )
        ):
            result[key] = deep_merge(
                result[key],
                value,
            )
        else:
            result[key] = value
    return result


def load_yaml(
    path: Path,
    required: bool = True,
) -> dict:
    """Load a YAML file and resolve environment-variable references.

    Args:
        path: YAML file to load.
        required: Whether a missing file should raise an exception.

    Returns:
        The parsed mapping, or an empty mapping for an optional missing or
        empty file.

    Raises:
        FileNotFoundError: If ``path`` is missing and required.
        RuntimeError: If a required environment variable is missing.
    """
    if not path.is_file():
        if required:
            relative_path = os.path.relpath(
                path,
                Path.cwd(),
            )
            raise FileNotFoundError(
                f"Required configuration file missing: {relative_path}"
            )
        return {}

    content = path.read_text(encoding="utf-8")
    resolved_content = VARIABLE_PATTERN.sub(
        replace_variable,
        content,
    )
    return yaml.safe_load(resolved_content) or {}


def load_config() -> dict:
    """Load and merge the common and active-environment configuration.

    The dotenv file is loaded first, ``APP_ENV`` selects the environment file,
    and environment-specific values override values from ``common.yaml``.

    Returns:
        The fully merged configuration mapping.

    Raises:
        RuntimeError: If ``APP_ENV`` or a required YAML variable is missing.
        FileNotFoundError: If the common or environment configuration file is
            missing.
    """
    load_dotenv(ENV_FILE_NAME)
    env = os.getenv(ENVIRONMENT_KEY)
    if env is None:
        raise RuntimeError(f"Missing required environment variable: {ENVIRONMENT_KEY}")
    else:
        env = env.lower().strip()

    common_config = load_yaml(CONFIG_DIR / COMMON_CONFIG_FILE_NAME)
    env_config = load_yaml(
        CONFIG_DIR
        / ENV_CONFIG_FILE_NAME.replace(
            ENV_REPLACE_KEY,
            env,
        )
    )

    return deep_merge(
        common_config,
        env_config,
    )
