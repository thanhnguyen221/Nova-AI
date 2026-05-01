"""
Custom template tags for Pro subscription features
"""
from django import template

register = template.Library()


@register.filter
def is_pro_user(user):
    """Check if user has active Pro subscription"""
    if not user or not user.is_authenticated:
        return False
    try:
        if hasattr(user, 'profile'):
            return user.profile.is_pro_active
        return False
    except:
        return False


@register.filter
def pro_days_remaining(user):
    """Get number of days remaining for Pro subscription"""
    if not user or not user.is_authenticated:
        return 0
    try:
        if hasattr(user, 'profile') and user.profile.pro_expiry_date:
            from django.utils import timezone
            remaining = user.profile.pro_expiry_date - timezone.now()
            return max(0, remaining.days)
        return 0
    except:
        return 0


@register.filter
def pro_expiry_date(user):
    """Get formatted Pro expiry date"""
    if not user or not user.is_authenticated:
        return None
    try:
        if hasattr(user, 'profile') and user.profile.pro_expiry_date:
            return user.profile.pro_expiry_date.strftime('%d/%m/%Y')
        return None
    except:
        return None
