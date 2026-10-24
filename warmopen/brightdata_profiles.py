"""Small, bounded Bright Data Scraper API client for consented own profiles."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_ENDPOINT = "https://api.brightdata.com/datasets/v3/scrape"
_DATASETS = {
    "linkedin": "gd_l1viktl72bvl7bjuj0",
    "x": "gd_lwxmeb2u1cniijd7t4",
}
_OUTPUT_FIELDS = {
    "linkedin": "position|about|current_company|experience|educations_details|courses|"
                "certifications|publications|patents|projects|organizations|honors_and_awards",
    "x": "biography|category_name",
}
_MAX_RESPONSE_BYTES = 1_000_000


class ProfileProviderError(Exception):
    """Sanitized provider failure; never carries response content or credentials."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def profile_client(api_key, timeout=45):
    """Build a callable client without doing I/O until it is invoked."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Bright Data API key is required")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
        raise ValueError("Invalid provider timeout")
    secret = api_key.strip()

    def scrape(platform, url):
        dataset_id = _DATASETS.get(platform)
        if not dataset_id or not isinstance(url, str):
            raise ValueError("Invalid profile request")
        query = urlencode({
            "dataset_id": dataset_id,
            "format": "json",
            "notify": "false",
            "include_errors": "true",
        })
        body = {
            "input": [{"url": url}],
            "custom_output_fields": _OUTPUT_FIELDS[platform],
            # Collect-by-URL uses a null limit; numeric limits belong to discovery.
            "limit_per_input": None,
        }
        request = Request(
            f"{_ENDPOINT}?{query}",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                if getattr(response, "status", 200) == 202:
                    # No undocumented polling or provider-returned URL following.
                    return {"status": "pending"}
                content = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError:
            raise ProfileProviderError("provider_http_error") from None
        except (URLError, TimeoutError, OSError):
            raise ProfileProviderError("provider_unavailable") from None
        if len(content) > _MAX_RESPONSE_BYTES:
            raise ProfileProviderError("provider_response_too_large")
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProfileProviderError("provider_invalid_response") from None
        if not isinstance(payload, (list, dict)):
            raise ProfileProviderError("provider_invalid_response")
        return payload

    return scrape
