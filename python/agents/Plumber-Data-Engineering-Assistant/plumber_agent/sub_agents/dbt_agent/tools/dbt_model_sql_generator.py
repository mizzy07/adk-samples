import io
from PIL import Image
import google.generativeai as genai

from agents.dbt_agent.constants import STORAGE_CLIENT, MODEL
from agents.dbt_agent.prompts import PARSING_INSTRUCTIONS

def generate_dbt_model_sql(gcs_url: str) -> dict:
    try:
        if not gcs_url.startswith('gs://'):
            return "Invalid gcs URL"
        
        bucket_name, file_path = gcs_url[5:].split('/', 1)
        dbt_project_name = file_path.split('/')[0]
        file_name = file_path.split('/')[-1].split('.')[0]
        file_type = file_path.split('/')[-1].split('.')[1]
        
        bucket = STORAGE_CLIENT.bucket(bucket_name)
        blob = bucket.blob(file_path)

        model = genai.GenerativeModel(MODEL)

        if not blob.exists():
            return 'Object not available at input path'
        
        bytes = blob.download_as_bytes()
        
        if file_type == 'csv':
            file_content = bytes.decode('utf-8')
            response = model.generate_content([PARSING_INSTRUCTIONS, file_content])
        else:
            image = Image.open(io.BytesIO(bytes))
            response = model.generate_content([PARSING_INSTRUCTIONS, image])

        output_sql = response.text.replace('```sql', '').replace('```', '')
        output_blob = bucket.blob(dbt_project_name + f'/models/{file_name}.sql')

        tags = {
            'author': 'dbt_adk_agent'
        }
        output_blob.metadata = tags

        with output_blob.open('w') as file:
            file.write(output_sql)

        return {
            'output_path': f'gs://{bucket_name}/{dbt_project_name}/models/{file_name}.sql',
            'output_sql': output_sql,
            'result': 'SUCCESS'
        }
    except Exception as err:
        return {
            'output_path': None,
            'output_sql': None,
            'result': f'error - {str(err)}'
        }
