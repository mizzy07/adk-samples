# dataflow_template_agent/utils.py

import os
import subprocess
import vertexai
from vertexai.generative_models import GenerativeModel
from .prompts import CORRECT_JAVA_FILE_INSTRUCTION
from .constants import MODEL
import pandas as pd
from google.cloud import storage

def find_all_java_files_in_dir(directory: str) -> list:
    """
    A utility function to find all .java files in a specific directory using the 'find' command.
    This is the "Python Finds" part of our pattern.
    """
    if not os.path.isdir(directory):
        print(f"Error: Search directory does not exist: {directory}")
        return []
    try:
        # Use find to recursively get all .java files in the specified directory
        find_cmd = f'find "{directory}" -name "*.java"'
        result = subprocess.run(find_cmd, capture_output=True, shell=True, text=True, check=True)
        # Return a clean list of file paths
        return result.stdout.strip().splitlines()
    except Exception as e:
        print(f"Error finding Java files in {directory}: {e}")
        return []

def find_template_source_file_with_llm(repo_root_path: str, template_name: str, template_path_in_repo: str) -> str:
    """
    Finds a template's main Java source file using an LLM to select the
    correct file from a list of REAL files found by Python.
    """
    try:
        # 1. Define the specific subdirectory for the template we want to customize.
        search_directory = os.path.join(repo_root_path, template_path_in_repo)
        
        # 2. Python does the searching. It gets a list of all possible candidate files.
        all_java_files = find_all_java_files_in_dir(search_directory)

        if not all_java_files:
            return ""

        # Optimization: If there's only one Java file, it must be the correct one.
        if len(all_java_files) == 1:
            return all_java_files[0]

        # 3. The LLM does the choosing from the real list provided by Python.
        vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))
        model = GenerativeModel(MODEL)
        prompt = CORRECT_JAVA_FILE_INSTRUCTION.format(
            template_name=template_name,
            java_files_list='\n'.join(all_java_files)
        )
        
        response = model.generate_content(prompt)
        correct_file_path = response.text.strip()

        # Final check to ensure the LLM's choice is valid and exists.
        if correct_file_path == "not_found" or not os.path.exists(correct_file_path):
            return ""
        
        return correct_file_path

    except Exception as e:
        print(f"An unexpected error occurred while finding source file for {template_name}: {e}")
        return ""

from .prompts import STTM_PARSING_INSTRUCTIONS_BEAM

def generate_beam_sql_query_from_sttm(gcs_path: str) -> str:
    """
    Reads a CSV file from a GCS path and generates a Beam SQL query using a generative model.
    """
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise FileNotFoundError(f"Object not found at GCS path: {gcs_path}")

        file_content = blob.download_as_text()

        vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))
        model = GenerativeModel(MODEL)
        response = model.generate_content([STTM_PARSING_INSTRUCTIONS_BEAM, file_content])
        
        output_sql = response.text.replace('```sql', '').replace('```', '').strip()
        return output_sql

    except Exception as e:
        print(f"An error occurred while generating the Beam SQL query: {e}")
        return ""
