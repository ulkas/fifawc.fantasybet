from .services.identity import get_current_player


def current_player(request):
    return {"current_player": get_current_player(request)}
