import logging


logger = logging.getLogger(__name__)


def safe_serpapi_error(error: Exception) -> str:
    response = getattr(error, 'response', None)
    status_code = getattr(response, 'status_code', None)
    if status_code is None:
        status_code = getattr(error, 'status_code', None)

    if status_code == 401:
        message = (
            'SerpAPI rejected the API key (HTTP 401). Check that SERPAPI_API_KEY '
            'is an active SerpAPI key. The request URL and key were omitted.'
        )
    elif status_code == 429:
        message = (
            'SerpAPI rate limit or account quota reached (HTTP 429). '
            'Check the SerpAPI account quota.'
        )
    elif status_code is not None:
        message = f'SerpAPI request failed (HTTP {status_code}). The request URL and key were omitted.'
    else:
        message = (
            f'SerpAPI request failed ({type(error).__name__}). '
            'The request URL and key were omitted.'
        )

    logger.warning(message)
    return message