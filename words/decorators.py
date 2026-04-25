"""
装饰器
"""
from django.shortcuts import redirect
from functools import wraps


def parent_required(view_func):
    """要求用户是家长"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if not request.user.userprofile.is_parent:
                return redirect('child_dashboard')
        except:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def child_required(view_func):
    """要求用户是孩子"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if not request.user.userprofile.is_child:
                return redirect('parent_dashboard')
        except:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
