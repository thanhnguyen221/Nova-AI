"""
Payment Views for Pro Subscription using PayOS
"""
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from payos import PayOS

from .models import UserProfile


# Initialize PayOS client
payos_client = None
if settings.PAYOS_CLIENT_ID and settings.PAYOS_API_KEY and settings.PAYOS_CHECKSUM_KEY:
    payos_client = PayOS(
        client_id=settings.PAYOS_CLIENT_ID,
        api_key=settings.PAYOS_API_KEY,
        checksum_key=settings.PAYOS_CHECKSUM_KEY
    )


def get_payos_client():
    """Get PayOS client instance"""
    if payos_client is None:
        raise Exception("PayOS chưa được cấu hình. Vui lòng kiểm tra PAYOS_CLIENT_ID, PAYOS_API_KEY và PAYOS_CHECKSUM_KEY trong file .env")
    return payos_client


# Plan pricing configuration (VND) - Updated prices
PLAN_CONFIG = {
    '1month': {'days': 30, 'price': 2000, 'name': '1 tháng'},
    '6months': {'days': 180, 'price': 12000, 'name': '6 tháng'},
    '1year': {'days': 365, 'price': 24000, 'name': '1 năm'}
}


@login_required
@require_http_methods(["POST"])
def create_payment(request):
    """
    Create a payment link for Pro subscription
    Supports plans: 1month, 6months, 1year
    Returns: { success: bool, checkoutUrl: string, error?: string }
    """
    try:
        client = get_payos_client()

        # Get selected plan from request (default to 1month for backward compatibility)
        import json
        try:
            body = json.loads(request.body) if request.body else {}
            plan = body.get('plan', '1month')
        except json.JSONDecodeError:
            plan = '1month'

        # Validate plan
        if plan not in PLAN_CONFIG:
            plan = '1month'

        plan_config = PLAN_CONFIG[plan]

        # Generate unique order code
        order_code = int(uuid.uuid4().int % 10000000000)

        # Get user's profile
        profile, created = UserProfile.objects.get_or_create(user=request.user)

        # Create payment data as dict
        payment_data = {
            "orderCode": order_code,
            "amount": plan_config['price'],
            "description": f"NovaAI Pro {plan_config['name']}",
            "cancelUrl": request.build_absolute_uri(reverse('payment_cancel')),
            "returnUrl": request.build_absolute_uri(reverse('payment_return')),
            "buyerName": request.user.get_full_name() or request.user.username,
            "buyerEmail": request.user.email or "",
            "buyerPhone": "",
            "buyerAddress": ""
        }

        # Create payment link using v2 API
        payment_link = client.payment_requests.create(payment_data)

        # Store order info in session for verification
        request.session['payos_order_code'] = order_code
        request.session['payos_user_id'] = request.user.id
        request.session['payos_plan'] = plan

        return JsonResponse({
            'success': True,
            'checkoutUrl': payment_link.checkout_url,
            'orderCode': order_code,
            'plan': plan,
            'days': plan_config['days']
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def payment_return(request):
    """
    Handle successful payment return from PayOS
    User is redirected here after payment completion
    """
    try:
        # Get payment status from query params
        code = request.GET.get('code')
        id = request.GET.get('id')
        cancel = request.GET.get('cancel', 'false')
        status = request.GET.get('status')
        order_code = request.GET.get('orderCode')

        # Verify the payment was successful
        if code == '00' and status == 'PAID' and cancel == 'false':
            # Get user's profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Get plan from session (default to 1month if not found)
            plan = request.session.get('payos_plan', '1month')
            plan_config = PLAN_CONFIG.get(plan, PLAN_CONFIG['1month'])
            days = plan_config['days']

            # Activate Pro subscription with correct days
            profile.activate_pro(days=days)

            # Clear session
            if 'payos_order_code' in request.session:
                del request.session['payos_order_code']
            if 'payos_user_id' in request.session:
                del request.session['payos_user_id']
            if 'payos_plan' in request.session:
                del request.session['payos_plan']

            return render(request, 'chat/payment_success.html', {
                'pro_expiry_date': profile.pro_expiry_date,
                'days': days,
                'plan_name': plan_config['name']
            })
        else:
            # Payment was cancelled or failed
            return render(request, 'chat/payment_cancel.html', {
                'error': 'Thanh toán không thành công hoặc đã bị hủy.'
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return render(request, 'chat/payment_cancel.html', {
            'error': str(e)
        })


@login_required
def payment_cancel(request):
    """Handle cancelled payment"""
    return render(request, 'chat/payment_cancel.html', {
        'error': 'Bạn đã hủy thanh toán.'
    })


@csrf_exempt
@require_http_methods(["POST"])
def payment_webhook(request):
    """
    Handle PayOS webhook for payment status updates
    This is called by PayOS server when payment status changes
    """
    try:
        # Get webhook data
        data = json.loads(request.body)

        # Verify webhook signature (PayOS provides signature verification)
        # Note: In production, you should verify the webhook signature

        # Extract payment info
        order_code = data.get('orderCode')
        status = data.get('status')  # PAID, CANCELLED, PENDING

        if status == 'PAID':
            # Payment successful - activate Pro
            # Note: In webhook, we need to identify user from order data
            # This is why we store user_id in the order description or custom data
            # For now, we'll skip webhook activation as Return URL handles it
            pass

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def check_pro_status(request):
    """
    API to check user's Pro subscription status
    Returns: { is_pro: bool, expiry_date: string|null, days_remaining: int }
    """
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)

        is_pro = profile.is_pro_active
        expiry_date = profile.pro_expiry_date.isoformat() if profile.pro_expiry_date else None

        # Calculate days remaining
        days_remaining = 0
        if profile.pro_expiry_date:
            from django.utils import timezone
            from datetime import timedelta
            remaining = profile.pro_expiry_date - timezone.now()
            days_remaining = max(0, remaining.days)

        return JsonResponse({
            'is_pro': is_pro,
            'expiry_date': expiry_date,
            'days_remaining': days_remaining
        })

    except Exception as e:
        return JsonResponse({
            'is_pro': False,
            'error': str(e)
        }, status=500)
