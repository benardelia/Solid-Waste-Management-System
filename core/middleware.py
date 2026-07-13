from django.utils.deprecation import MiddlewareMixin
import threading

# Thread-local storage to hold the current request object
_thread_locals = threading.local()

def get_current_user():
    """
    Returns the current user based on the thread-local request.
    If there is no current request, or no authenticated user, returns None.
    """
    request = getattr(_thread_locals, 'request', None)
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None

class CurrentUserMiddleware(MiddlewareMixin):
    """
    Middleware to store the current request in thread-local storage.
    This allows models (like AuditableModel) to access the current user
    without having to pass it down explicitly through every function call.
    """
    def process_request(self, request):
        _thread_locals.request = request

    def process_response(self, request, response):
        # Clean up thread-local storage after the response is processed
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
        return response

    def process_exception(self, request, exception):
        # Also clean up on exceptions to prevent memory leaks across threads
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
