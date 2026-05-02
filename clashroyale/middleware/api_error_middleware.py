# middleware/api_error_middleware.py
import logging
from django.conf import settings

class ClashRoyaleAPIErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(__name__)

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if 'clashroyale' in request.path:
            self.logger.error(f"Clash Royale API Error: {exception}")
        return None