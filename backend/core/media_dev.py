"""Dev only: serve files that LocalStorage wrote, because <img> tags cannot send a bearer token.

Mounted only when ENV=dev and STORAGE_PROVIDER=local (circuit/api.py). Staging, demo and production use Supabase Storage
with signed URLs on private buckets.
"""

from django.http import Http404, HttpResponse
from ninja import Router

from core.storage import LocalStorage

router = Router()


@router.get("/{bucket}/{path:path}", auth=None, include_in_schema=False)
def serve(request, bucket: str, path: str):
    try:
        data = LocalStorage().get(bucket, path)
    except (FileNotFoundError, ValueError, IsADirectoryError):
        raise Http404 from None
    return HttpResponse(data, content_type="application/zip" if path.endswith(".zip") else "image/webp")
