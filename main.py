from pathlib import Path
import webview
from api import API


def main():
    api = API()

    # file:// URL — ui/lib/ altındaki PDF.js dosyalarına relative path çalışsın
    ui_path = Path(__file__).parent / "ui" / "index.html"

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
