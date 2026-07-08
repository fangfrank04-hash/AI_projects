"""离线 Swagger UI 页面模板

把 FastAPI 默认从 CDN 加载的 Swagger UI 改为从本地加载，
这样内网（无法联网）也能正常访问 /docs 调试页面。

原理：FastAPI 默认的 /docs 页面引用了 CDN 上的 3 个文件：
  - https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css
  - https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js
  - https://fastapi.tiangolo.com/img/favicon.png
内网无法访问这些 CDN，页面就白屏。

解决方案：把这 3 个文件下载到 assets/swagger_ui/ 目录，
用自定义的 HTML 页面替换默认的 /docs。
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings


# 离线 Swagger UI 的 HTML 页面（所有资源从本地加载，不依赖 CDN）
SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link type="text/css" rel="stylesheet" href="/static/swagger_ui/swagger-ui.css">
<link rel="shortcut icon" href="/static/swagger_ui/favicon.png">
<title>{title} - Swagger UI</title>
</head>
<body>
<div id="swagger-ui">
</div>
<script src="/static/swagger_ui/swagger-ui-bundle.js"></script>
<script src="/static/swagger_ui/swagger-ui-standalone-preset.js"></script>
<script>
const ui = SwaggerUIBundle({
    url: '/openapi.json',
    dom_id: '#swagger-ui',
    layout: 'BaseLayout',
    deepLinking: true,
    showExtensions: true,
    showCommonExtensions: true,
    presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
    ],
    plugins: [
        SwaggerUIBundle.plugins.DownloadUrl
    ],
})
</script>
</body>
</html>
"""


def setup_offline_docs(app: FastAPI):
    """
    配置离线 Swagger UI。

    用法（在 main.py 里调用）：
        from app.core.offline_docs import setup_offline_docs
        setup_offline_docs(app)
    """
    # 挂载静态文件目录：/static/swagger_ui/xxx → assets/swagger_ui/xxx
    from pathlib import Path
    static_dir = Path(__file__).resolve().parent.parent.parent / "assets"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 用自定义的 /docs 替换默认的（默认的从 CDN 加载，内网打不开）
    # 注意：不能用 .format()，因为 JS 代码里的花括号会被误解析
    html = SWAGGER_UI_HTML.replace("{title}", settings.app_name)

    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    async def custom_docs():
        return html
