import base64, io
from flask import Flask, request, Response, stream_with_context
import requests as req_lib
from PIL import Image
import manager

app = Flask(__name__)


def convert_webp_to_jpeg(b64_string):
    try:
        if "base64," in b64_string:
            _, data = b64_string.split("base64,", 1)
        else:
            data = b64_string
        image_data = base64.b64decode(data)
        img = Image.open(io.BytesIO(image_data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=90)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except Exception as e:
        print(f"[Proxy] Image convert error: {e}")
        return b64_string


@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def proxy(path):
    import config
    if request.method == 'OPTIONS':
        return '', 200
    manager.ensure_llama_running()
    config.last_activity = __import__('time').time()
    target_url = f"{config.LLAMA_SERVER_URL}/{path}"
    kwargs = {
        "method": request.method,
        "url": target_url,
        "headers": {k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']},
        "stream": True
    }
    if request.method == 'POST' and request.is_json:
        data = request.json
        if path.endswith('v1/chat/completions'):
            for msg in data.get('messages', []):
                if isinstance(msg.get('content'), list):
                    for item in msg['content']:
                        if item.get('type') == 'image_url':
                            url = item['image_url'].get('url', '')
                            if 'image/webp' in url or 'webp' in url:
                                print("[Proxy] Converting WebP → JPEG...")
                                item['image_url']['url'] = convert_webp_to_jpeg(url)
        kwargs["json"] = data
    else:
        kwargs["data"] = request.get_data()
    resp = req_lib.request(**kwargs)
    def generate():
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                yield chunk
    excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive']
    headers  = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded]
    return Response(stream_with_context(generate()), status=resp.status_code, headers=headers)