# utils/clash_api.py
import requests
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def fetch_player_data(player_tag, use_cache=True):
    """
    Fetch player data from Clash Royale API
    Args:
        player_tag: Player tag (with or without #)
        use_cache: Use cached data if available (5 minutes)
    """
    # Remove # from tag if present and URL encode it
    tag = player_tag.strip().replace('#', '')

    # Cache key
    cache_key = f'clash_player_{tag}'

    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Using cached data for player {tag}")
            return cached_data

    try:
        headers = {
            'Authorization': f'Bearer {settings.CLASH_ROYALE_API_KEY}',
            'Accept': 'application/json'
        }

        # Note: %23 is URL-encoded # symbol
        url = f'{settings.CLASH_ROYALE_API_URL}/players/%23{tag}'

        logger.info(f"Fetching Clash Royale data for tag: {tag}")
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            # Cache for 5 minutes (300 seconds)
            cache.set(cache_key, data, 300)
            return data

        elif response.status_code == 404:
            raise Exception(f'Player with tag #{tag} not found')

        elif response.status_code == 403:
            # Check for specific error messages
            error_msg = response.json().get('message', '')
            if 'invalid token' in error_msg.lower():
                raise Exception('Invalid API token. Please check your API key.')
            elif 'ip' in error_msg.lower():
                raise Exception('IP not whitelisted. Add your server IP to developer portal.')
            else:
                raise Exception(f'Access denied: {error_msg}')

        elif response.status_code == 429:
            raise Exception('Rate limit exceeded. Please wait before trying again.')

        else:
            error_msg = response.json().get('message', 'Unknown error')
            raise Exception(f'API Error {response.status_code}: {error_msg}')

    except requests.exceptions.Timeout:
        raise Exception('Request timed out. Please try again.')
    except requests.exceptions.ConnectionError:
        raise Exception('Network connection error. Please check your internet.')
    except Exception as e:
        logger.error(f"API fetch error for tag {tag}: {str(e)}")
        raise