"""UDA-prefix and LAN smoke test."""
from app import create_app

def test_uda_mount_and_lan():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    local = client.get("/")
    assert local.status_code == 200
    assert '<base href="/">' in local.get_data(as_text=True)
    headers = {"X-Forwarded-Prefix":"/apps/flask-spreadsheet",
               "X-Forwarded-Host":"tanyaanne.ddns.net",
               "X-Forwarded-Proto":"https"}
    remote = client.get("/",headers=headers)
    assert remote.status_code == 200
    html=remote.get_data(as_text=True)
    assert '<base href="/apps/flask-spreadsheet/">' in html
    assert '/apps/flask-spreadsheet/static/js/spreadsheet.js' in html
