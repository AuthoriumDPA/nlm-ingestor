import logging
import os
import tempfile
import traceback

from flask import Flask, jsonify, make_response, request
from nlm_utils.utils import file_utils
from werkzeug.utils import secure_filename

import nlm_ingestor.ingestion_daemon.config as cfg
from nlm_ingestor.ingestor import ingestor_api

app = Flask(__name__)

# CVE-2025-48795 Mitigation: Limit file size to prevent OOM from large stream processing
# 50MB limit prevents the vulnerable Apache CXF code from exhausting memory
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB in bytes

# initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(cfg.log_level())


@app.route("/", methods=["GET"])
def health_check():
    return "Service is running", 200


@app.route("/api/parseDocument", methods=["POST"])
def parse_document(
    file=None,
    render_format: str = "all",
):
    render_format = request.args.get("renderFormat", "all")
    use_new_indent_parser = request.args.get("useNewIndentParser", "no")
    apply_ocr = request.args.get("applyOcr", "no")
    file = request.files["file"]
    tmp_file = None
    try:
        parse_options = {
            "parse_and_render_only": True,
            "render_format": render_format,
            "use_new_indent_parser": use_new_indent_parser == "yes",
            "parse_pages": (),
            "apply_ocr": apply_ocr == "yes",
        }
        # save the incoming file to a temporary location
        filename = secure_filename(file.filename)
        _, file_extension = os.path.splitext(file.filename)
        tempfile_handler, tmp_file = tempfile.mkstemp(suffix=file_extension)
        os.close(tempfile_handler)
        file.save(tmp_file)

        # CVE-2025-48795 Mitigation: File size validation
        # Verify file size even after Flask's MAX_CONTENT_LENGTH check
        file_size = os.path.getsize(tmp_file)
        max_size = app.config.get('MAX_CONTENT_LENGTH', 100 * 1024 * 1024)
        if file_size > max_size:
            logger.warning(
                f"File {filename} rejected: size {file_size} bytes exceeds "
                f"limit {max_size} bytes (CVE-2025-48795 protection)"
            )
            os.unlink(tmp_file)
            return make_response(
                jsonify({
                    "status": "fail",
                    "reason": f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds "
                             f"maximum allowed ({max_size / 1024 / 1024:.0f}MB)"
                }),
                413  # 413 Payload Too Large
            )

        # calculate the file properties
        props = file_utils.extract_file_properties(tmp_file)
        print(f"Parsing document: {filename}")
        return_dict, _ = ingestor_api.ingest_document(
            filename,
            tmp_file,
            props["mimeType"],
            parse_options=parse_options,
        )
        if tmp_file and os.path.exists(tmp_file):
            os.unlink(tmp_file)
        return make_response(
            jsonify({"status": 200, "return_dict": return_dict or {}}),
        )

    except Exception as e:
        print("error uploading file, stacktrace: ", traceback.format_exc())
        print(
            f"error uploading file, stacktrace: {traceback.format_exc()}",
            exc_info=True,
        )
        status, rc, msg = "fail", 500, str(e)

    finally:
        if tmp_file and os.path.exists(tmp_file):
            os.unlink(tmp_file)
    return make_response(jsonify({"status": status, "reason": msg}), rc)


def main():
    print("Starting ingestor service..")
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
