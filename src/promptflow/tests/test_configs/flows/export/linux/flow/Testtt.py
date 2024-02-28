import os
import json

def list_files_in_directory(directory):
    """
    Recursively list all files and directories in the specified directory and its subdirectories.
    
    Args:
    - directory (str): The path to the directory
    
    Returns:
    - files (list): A list containing the paths of all files and directories in the specified directory and its subdirectories
    """
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files

# Path to the directory
directory_path = "/home/complete_excavation/NEW PROJECT/DATA"

# Get the contents of the directory and its subdirectories
contents = list_files_in_directory(directory_path)

# Save the contents to a single-row JSON file
output_file = "directory_contents.json"
with open(output_file, "w") as f:
    json.dump(contents, f)

print(f"Contents saved to '{output_file}'.")
