import os

def load_environment_variable(str):

    envVar = os.environ.get(str)
    if envVar is None:
        raise EnvironmentError(f"Error: Environment variable {str} is not set.")

    return envVar
