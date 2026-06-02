from pathlib import Path
import sys
import webview
from api import API


def _base() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def main():
    api = API()

    ui_path = _base() / "ui" / "index.html"

    window = webview.create_window(
        title="PDF Redactor",
        url=ui_path.as_uri(),
        js_api=api,
        width=1280,
        height=900,
        resizable=True,
        min_size=(800, 600),
    )
    assert window is not None
    api.set_window(window)

    webview.start(debug=False)


if __name__ == "__main__":
    main()
