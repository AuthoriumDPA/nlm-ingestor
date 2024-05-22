import base64
import json
import tempfile
import os
import traceback
from werkzeug.utils import secure_filename
from nlm_ingestor.ingestor import ingestor_api
from nlm_utils.utils import file_utils
import subprocess
import os
import time
import threading
import requests


def parse_document(
    file_content,
    filename,
    render_format="all",
    use_new_indent_parser=False,
    apply_ocr=False,
):
    parse_options = {
        "parse_and_render_only": True,
        "render_format": render_format,
        "use_new_indent_parser": use_new_indent_parser,
        "parse_pages": (),
        "apply_ocr": apply_ocr,
    }
    try:
        # Create a temporary file to save the decoded content
        tempfile_handler, tmp_file_path = tempfile.mkstemp(
            suffix=os.path.splitext(filename)[1]
        )
        with os.fdopen(tempfile_handler, "wb") as tmp_file:
            tmp_file.write(file_content)

        # calculate the file properties
        props = file_utils.extract_file_properties(tmp_file_path)
        print(f"Parsing document: {filename}")
        return_dict, _ = ingestor_api.ingest_document(
            filename,
            tmp_file_path,
            props["mimeType"],
            parse_options=parse_options,
        )
        return return_dict or {}

    except Exception as e:
        traceback.print_exc()
        return {"status": "fail", "reason": str(e)}

    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def read_output(process):
    while True:
        output = process.stdout.readline()
        if output == "":
            break
        print(output.strip())


def start_tika():
    print(
        "see jar", os.path.exists("jars/tika-server-standard-nlm-modified-2.4.1_v6.jar")
    )
    tika_path = "jars/tika-server-standard-nlm-modified-2.4.1_v6.jar"
    java_path = "/usr/bin/java"  # Use the common path for Java
    process = subprocess.Popen(
        [java_path, "-jar", tika_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # thread = threading.Thread(target=read_output, args=(process,))
    # thread.start()
    # Main thread can perform other tasks here, or wait for the output thread to finish
    # thread.join()
    print("Tika Server process completed.")


# Call this function early in your Lambda handler
def test_tika():
    try:
        response = requests.get("http://localhost:9998/tika")
        if response.status_code == 200:
            print("Tika Server is reachable and ready!")
            return True
        else:
            print("Tika Server is not ready. Status Code:", response.status_code)
            return False
    except Exception as e:
        print("Failed to connect to Tika Server:", str(e))
        return False


def parse(event, context):
    # print(json.dumps(event, indent = 4))
    if "body" not in event:
        return {"statusCode": 400, "body": json.dumps({"message": "No data provided"})}
    parsed_body = json.loads(event["body"])
    if "url" not in parsed_body:
        return {"statusCode": 400, "body": json.dumps({"message": "No url provided"})}

    start_tika()

    working = test_tika()
    while not working:
        time.sleep(3)
        working = test_tika()

    file_content = requests.get(parsed_body["url"], timeout=300).content
    # file_content = base64.b64decode(event["body"])
    filename = "uploaded_document.pdf"  # This needs to be passed or inferred some way

    # Extract additional parameters
    params = event.get("queryStringParameters", {})
    render_format = params.get("render_format", "all")
    use_new_indent_parser = params.get("use_new_indent_parser", "yes") == "yes"
    apply_ocr = params.get("apply_ocr", "no") == "yes"

    # Process the document
    result = parse_document(
        file_content, filename, render_format, use_new_indent_parser, apply_ocr
    )

    return {"statusCode": 200, "body": result}
