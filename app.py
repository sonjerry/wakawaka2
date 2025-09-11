from flask import Flask, request, Response, send_from_directory, jsonify
import os
import urllib.parse
import requests


APP_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=APP_DIR,
    static_url_path=""
)


def cors_headers(resp: Response) -> Response:
    resp.headers.setdefault("Access-Control-Allow-Origin", "*")
    resp.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
    resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type,Accept")
    return resp


@app.after_request
def add_cors(resp):
    return cors_headers(resp)


@app.route("/")
def root():
    return send_from_directory(APP_DIR, "index.html")


@app.route("/whep-proxy", methods=["POST", "DELETE", "OPTIONS"])
def whep_proxy():
    if request.method == "OPTIONS":
        return cors_headers(Response(status=204))

    target = request.args.get("target", type=str)
    if not target:
        return jsonify({"error": "missing 'target' query"}), 400

    # Basic safety: only http(s)
    if not (target.startswith("http://") or target.startswith("https://")):
        return jsonify({"error": "invalid target url"}), 400

    try:
        if request.method == "POST":
            # Forward SDP offer to WHEP endpoint
            headers = {
                "Content-Type": request.headers.get("Content-Type", "application/sdp"),
                "Accept": "application/sdp",
            }
            resp = requests.post(target, data=request.get_data(), headers=headers, timeout=15)

            # Rewrite Location header (if any) to come back to this proxy so DELETE can be same-origin
            answer_sdp = resp.text
            proxied_location = None
            remote_location = resp.headers.get("Location")
            if remote_location:
                encoded_resource = urllib.parse.quote(remote_location, safe="")
                proxied_location = f"/whep-proxy?target={urllib.parse.quote(target, safe='')}&resource={encoded_resource}"

            flask_resp = Response(answer_sdp, status=resp.status_code, mimetype="application/sdp")
            if proxied_location:
                flask_resp.headers["Location"] = proxied_location
            return flask_resp

        if request.method == "DELETE":
            # Expect resource=<encoded remote resource URL>
            resource = request.args.get("resource", type=str)
            if not resource:
                return jsonify({"error": "missing 'resource' query to DELETE"}), 400
            remote_resource = urllib.parse.unquote(resource)
            del_resp = requests.delete(remote_resource, timeout=10)
            return Response(status=del_resp.status_code)

    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"error": "method not allowed"}), 405


if __name__ == "__main__":
    # Default: http://0.0.0.0:8000
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    app.run(host=host, port=port)


