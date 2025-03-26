import json
import random
import string
import uuid
from django.http import JsonResponse

from django.urls import reverse
import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.generic import ListView, DetailView, View

from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm
from .models import Item, OrderItem, Order, Payment, Coupon, Refund, Address, UserProfile


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def is_valid_form(fields):
    return all(field != '' for field in fields)


class HomeView(ListView):
    model = Item
    paginate_by = 10  # Number of items per page
    template_name = "home.html"
    
def get_queryset(self):
        return Item.objects.all().order_by('id')  # Or any other field you prefer


class PayPalPaymentView(View):
    def get(self, request, *args, **kwargs):
        # This method handles GET requests
        try:
            order = Order.objects.get(user=request.user, ordered=False)
            context = {
                'order': order,
            }
            return render(request, 'payment.html', context)
        except ObjectDoesNotExist:
            messages.error(request, "You do not have an active order")
            return redirect("core:order-summary")
    
    def post(self, request, *args, **kwargs):
        # This method handles POST requests
        data = json.loads(request.body)
        paypal_order_id = data.get("orderID")
        django_order_id = data.get("djangoOrderId")
        order = get_object_or_404(Order, id=django_order_id, ordered=False)

        # Create the payment
        payment = Payment(
            user=request.user,
            amount=order.get_total(),
            transaction_id=str(uuid.uuid4()),
            payment_method="PayPal"
        )
        payment.save()

        # Update order status
        order.ordered = True
        order.payment = payment
        order.ref_code = create_ref_code()
        order.save()
        
        return JsonResponse({"status": "Payment Successful", "transaction_id": payment.transaction_id})

    


class CheckoutView(View):
    def get(self, request, *args, **kwargs):
        try:
            order = Order.objects.get(user=request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }

            # Find shipping and billing addresses
            shipping_address_qs = Address.objects.filter(user=request.user, address_type='S', default=True)
            billing_address_qs = Address.objects.filter(user=request.user, address_type='B', default=True)

            if shipping_address_qs.exists():
                context['default_shipping_address'] = shipping_address_qs[0]

            if billing_address_qs.exists():
                context['default_billing_address'] = billing_address_qs[0]

            return render(request, "checkout.html", context)

        except ObjectDoesNotExist:
            messages.info(request, "You do not have an active order")
            return redirect("core:checkout")

    def post(self, request, *args, **kwargs):
        form = CheckoutForm(request.POST or None)
        if form.is_valid():
            self.handle_checkout_form(form, request)
        else:
            messages.warning(request, "Invalid data received")
        return redirect("core:checkout")

    def handle_checkout_form(self, form, request):
        order = Order.objects.get(user=request.user, ordered=False)

        # Handle shipping address
        self.handle_shipping_address(form, order, request)

        # Handle billing address
        self.handle_billing_address(form, order, request)

        payment_option = form.cleaned_data.get('payment_option')
    
        if payment_option == 'S':
        # For Stripe - you would need a stripe-payment URL 
            return redirect(reverse('core:stripe-payment'))
        elif payment_option == 'P':
        # For PayPal - use the correct URL name
            return redirect(reverse('core:paypal-payment'))
        else:
            messages.warning(request, "Invalid payment option selected")
        return

    def handle_shipping_address(self, form, order, request):
        use_default_shipping = form.cleaned_data.get('use_default_shipping')
        if use_default_shipping:
            address_qs = Address.objects.filter(user=request.user, address_type='S', default=True)
            if address_qs.exists():
                order.shipping_address = address_qs[0]
                order.save()
            else:
                messages.info(request, "No default shipping address available")
        else:
            self.create_shipping_address(form, order, request)

    def create_shipping_address(self, form, order, request):
        shipping_address1 = form.cleaned_data.get('shipping_address')
        shipping_address2 = form.cleaned_data.get('shipping_address2')
        shipping_country = form.cleaned_data.get('shipping_country')
        shipping_zip = form.cleaned_data.get('shipping_zip')

        if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
            shipping_address = Address(
                user=request.user,
                street_address=shipping_address1,
                apartment_address=shipping_address2,
                country=shipping_country,
                zip=shipping_zip,
                address_type='S'
            )
            shipping_address.save()
            order.shipping_address = shipping_address
            order.save()

            if form.cleaned_data.get('set_default_shipping'):
                shipping_address.default = True
                shipping_address.save()
        else:
            messages.info(request, "Please fill in the required shipping address fields")

    def handle_billing_address(self, form, order, request):
        same_billing_address = form.cleaned_data.get('same_billing_address')
        use_default_billing = form.cleaned_data.get('use_default_billing')

        if same_billing_address:
            order.billing_address = self.create_billing_address_from_shipping(order, request)
        elif use_default_billing:
            self.use_default_billing_address(order, request)
        else:
            self.create_new_billing_address(form, order, request)

    def create_billing_address_from_shipping(self, order, request):
        billing_address = order.shipping_address
        billing_address.pk = None
        billing_address.address_type = 'B'
        billing_address.save()
        return billing_address

    def use_default_billing_address(self, order, request):
        address_qs = Address.objects.filter(user=request.user, address_type='B', default=True)
        if address_qs.exists():
            order.billing_address = address_qs[0]
            order.save()
        else:
            messages.info(request, "No default billing address available")
    
    def create_new_billing_address(self, form, order, request):
        billing_address1 = form.cleaned_data.get('billing_address')
        billing_address2 = form.cleaned_data.get('billing_address2')
        billing_country = form.cleaned_data.get('billing_country')
        billing_zip = form.cleaned_data.get('billing_zip')

        if is_valid_form([billing_address1, billing_country, billing_zip]):
            billing_address = Address(
                user=request.user,
                street_address=billing_address1,
                apartment_address=billing_address2,
                country=billing_country,
                zip=billing_zip,
                address_type='B'
            )
            billing_address.save()
            order.billing_address = billing_address
            order.save()

            if form.cleaned_data.get('set_default_billing'):
                billing_address.default = True
                billing_address.save()
        else:
            messages.info(request, "Please fill in the required billing address fields")


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            order = Order.objects.get(user=request.user, ordered=False)
            context = {'object': order}
            return render(request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(request, "You do not have an active order")
            return redirect("/")


class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated.")
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your cart.")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")

    return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(item=item, user=request.user, ordered=False)[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "This item was removed from your cart.")
        else:
            messages.info(request, "This item was not in your cart")
    else:
        messages.info(request, "You do not have an active order")

    return redirect("core:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "This item quantity was updated.")
        else:
            messages.info(request, "This item was not in your cart")
    else:
        messages.info(request, "You do not have an active order")

    return redirect("core:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("core:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            code = form.cleaned_data.get('code')
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
            except ObjectDoesNotExist:
                messages.info(self.request, "You do not have an active order")
        return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {'form': form}
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')

            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # Store the refund
                refund = Refund(order=order, reason=message, email=email)
                refund.save()

                messages.info(self.request, "Your request was received.")
            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exist.")
        return redirect("core:request-refund")
    
    
    
    
    
class PaymentSuccessView(View):
    def get(self, request, *args, **kwargs):
        transaction_id = request.GET.get('transaction_id')
        
        try:
            # Get the payment by transaction ID
            payment = Payment.objects.get(transaction_id=transaction_id)
            # Get the related order
            orders = Order.objects.filter(payment=payment)
            
            if orders.exists():
                order = orders[0]
                context = {
                    'transaction_id': transaction_id,
                    'order': order
                }
                return render(request, 'payment_success.html', context)
            else:
                messages.warning(request, "No order found for this transaction")
                return redirect("core:home")
                
        except Payment.DoesNotExist:
            messages.warning(request, "No payment found with this transaction ID")
            return redirect("core:home")