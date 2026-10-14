"""MinIO adapter tests run with an in-memory fake; no network involved."""
from io import BytesIO
from test_api import client, create_case, setup, headers
from app.routers import evidence_files


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        return {"Body": FakeBody(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


class FakeBody:
    def __init__(self, data): self.reader = BytesIO(data)
    def iter_chunks(self, chunk_size=65536):
        while chunk := self.reader.read(chunk_size): yield chunk
    def close(self): self.reader.close()


def test_file_evidence_upload_hash_download_isolation(client, monkeypatch):
    store = FakeS3()
    monkeypatch.setattr(evidence_files, "storage_client", lambda: store)
    monkeypatch.setenv("NEXUS_S3_BUCKET", "test-evidence")
    csrf = setup(client)
    a, b = create_case(client, csrf, "Case A"), create_case(client, csrf, "Case B")
    data = b"example document bytes"
    r = client.post(f"/api/v1/cases/{a}/evidence/files", headers=headers(csrf),
                    files={"file": ("contract.pdf", data, "application/pdf")})
    assert r.status_code == 201, r.text
    record = r.json()
    assert record["byte_count"] == len(data)
    assert len(record["sha256"]) == 64
    assert len(client.get(f"/api/v1/cases/{a}/evidence/files").json()) == 1
    assert client.get(f"/api/v1/cases/{b}/evidence/files").json() == []
    assert client.get(f"/api/v1/cases/{b}/evidence/files/{record['id']}/download").status_code == 404
    downloaded = client.get(f"/api/v1/cases/{a}/evidence/files/{record['id']}/download")
    assert downloaded.status_code == 200 and downloaded.content == data
    assert "attachment" in downloaded.headers["content-disposition"]
    assert downloaded.headers["cache-control"] == "no-store"


def test_file_evidence_rejects_unsafe_and_large_upload(client, monkeypatch):
    monkeypatch.setattr(evidence_files, "storage_client", lambda: FakeS3())
    csrf = setup(client)
    case = create_case(client, csrf)
    assert client.post(f"/api/v1/cases/{case}/evidence/files", headers=headers(csrf),
                       files={"file": ("evil.html", b"<script>alert(1)</script>", "text/html")}).status_code == 422
    assert client.post(f"/api/v1/cases/{case}/evidence/files", headers=headers(csrf),
                       files={"file": ("test.pdf", b"x" * (20 * 1024 * 1024 + 1), "application/pdf")}).status_code == 413
    assert client.post(f"/api/v1/cases/{case}/evidence/files",
                       files={"file": ("ok.pdf", b"ok", "application/pdf")}).status_code == 403
