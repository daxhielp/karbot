import yaml
import os

def load_execution_config(path: str = "src/config/execution_config.yaml") -> dict:
    """
    Loads and validates the execution configuration.
    
    :param path: Path to the yaml config file
    :return: Configuration dictionary
    :raises FileNotFoundError: If config file is missing
    :raises ValueError: If config is invalid
    """
    # Check if path exists relative to CWD
    if not os.path.exists(path):
        # Try finding it relative to this file's directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        alt_path = os.path.join(base_dir, "execution_config.yaml")
        
        if os.path.exists(alt_path):
            path = alt_path
        else:
            # Try one level up (src/) + path if path was relative
            # But the default is "src/config/..." so assume running from root.
            # If running from src/, it might be different.
            # Let's just raise if not found.
            raise FileNotFoundError(f"Configuration file not found at {path} or {alt_path}")
            
    with open(path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config: {e}")
            
    # Basic validation of required structure
    if "execution" not in config:
        raise ValueError("Invalid config: missing 'execution' root key")
        
    required_sections = ["thresholds", "timing", "validation"]
    for section in required_sections:
        if section not in config["execution"]:
             raise ValueError(f"Invalid config: missing 'execution.{section}' section")
             
    return config

def save_execution_config(config: dict, path: str = "src/config/execution_config.yaml"):
    """
    Saves the configuration dictionary to a yaml file.
    
    :param config: Configuration dictionary
    :param path: Path to the yaml config file
    """
    # Try finding it relative to this file's directory if the path doesn't exist
    if not os.path.exists(path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        alt_path = os.path.join(base_dir, "execution_config.yaml")
        if os.path.exists(alt_path):
            path = alt_path

    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
