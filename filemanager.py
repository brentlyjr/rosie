import os
import yaml
from rosie_utils import load_config



class FileManager:
    """
    Reads data from our file system
        - Use file tokens instead of knowing the actual path names (config.ini)
        - Can read various file formats - yaml, txt
        - Currently only used for prompt templates
    """

    def __init__(self) -> None:
        self.paths = load_config('Filepaths')
        self.prompt_directory = self.paths['prompt_directory']

    def read_data(self, file_token :str):
        if file_token in self.paths.keys():        
            filename = os.path.join(self.prompt_directory, self.paths[file_token])
        else:
            raise RuntimeError(f"No file_token {file_token} listed in config file.")
        
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                if filename.endswith(".yaml"):
                    data = yaml.safe_load(file)                
                elif filename.endswith(".txt"):
                    data = file.read()
                else:
                    data = file.read()
        except FileNotFoundError:
            print(f"The file {filename} was not found.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return data
    
