import base64, io
import time
import uuid
from flask import Flask, request, Response, stream_with_context
import requests as req_lib
from PIL import Image
import manager

app = Flask(__name__)


def generate_short_id():
    """Generate a short unique request ID."""
    return str(uuid.uuid4())[:8]


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
    req_id = generate_short_id()
    print(f"[Proxy] [REQ:{req_id}] Incoming {request.method} {request.path}")
    
    if request.method == 'OPTIONS':
        return '', 200
    
    # Get the best instance for this request
    target_port = manager.get_best_instance(req_id)
    if target_port is None:
        print(f"[Proxy] [REQ:{req_id}] ERROR: No instance available!")
        return "No instance available", 503
    
    manager.increment_active(target_port)
    print(f"[Proxy] [REQ:{req_id}] Routing to Instance:{target_port}")
    
    target_url = f"http://localhost:{target_port}/{path}"
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
    
    try:
        resp = req_lib.request(**kwargs)
        
        # Check if the client requested a stream (usually via JSON body)
        is_stream = False
        if request.is_json:
            is_stream = request.json.get("stream", False)
        elif "text/event-stream" in resp.headers.get("content-type", ""):
            is_stream = True

        if is_stream:
            # Logic cũ cho Streaming
            def generate():
                try:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk: yield chunk
                finally:
                    manager.decrement_active(target_port)
                    print(f"[Proxy] [REQ:{req_id}] Stream Completed. Releasing Instance:{target_port}")
            
            excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive']
            headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded]
            return Response(stream_with_context(generate()), status=resp.status_code, headers=headers)
        
        else:
            # Logic mới cho Non-Stream (Trường hợp Benchmark)
            try:
                # Đọc toàn bộ content
                content = resp.content
                excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive']
                headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded]
                return Response(content, status=resp.status_code, headers=headers)
            finally:
                # Giảm counter ngay sau khi lấy xong content
                manager.decrement_active(target_port)
                print(f"[Proxy] [REQ:{req_id}] Non-Stream Completed. Releasing Instance:{target_port}")

    except Exception as e:
        manager.decrement_active(target_port)
        print(f"[Proxy] [REQ:{req_id}] ERROR: {str(e)}")
        return str(e), 500