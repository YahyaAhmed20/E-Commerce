{% extends "base.html" %} {% load crispy_forms_tags %} {% block content %}
<h2>Checkout</h2>
<p>Total: ${{ order.get_total }}</p>

<!-- PayPal Button Container -->
<div id="paypal-button-container"></div>

{% include "order_snippet.html" %}

<!-- Load PayPal SDK -->
<script src="https://www.paypal.com/sdk/js?client-id=Ae4QLC_-2UYkbqVhXA6Lb-r9bB3lEW9byzjxZvKZxb5lIc4VN94eCJ9i07jlLVoOW2ns8RzN5vYUb2u3&currency=USD"></script>

<script>
  // Initialize PayPal button
  paypal
    .Buttons({
      createOrder: function (data, actions) {
        return actions.order.create({
          purchase_units: [
            {
              amount: {
                value: "{{ order.get_total }}",
              },
            },
          ],
        });
      },
      onApprove: function (data, actions) {
        return actions.order.capture().then(function (details) {
          fetch("{% url 'core:paypal-payment' %}", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": "{{ csrf_token }}",
            },
            body: JSON.stringify({ orderID: data.orderID }),
          })
            .then((response) => response.json())
            .then((data) => {
              alert(
                "Payment successful! Transaction ID: " + data.transaction_id
              );
              window.location.href = "/";
            });
        });
      },
    })
    .render("#paypal-button-container");
</script>

{% endblock content %} {% block extra_scripts %}
<script>
  // jQuery is required for this script
  var hideable_shipping_form = $(".hideable_shipping_form");
  var hideable_billing_form = $(".hideable_billing_form");

  var use_default_shipping = document.querySelector(
    "input[name=use_default_shipping]"
  );
  var use_default_billing = document.querySelector(
    "input[name=use_default_billing]"
  );

  // Toggle shipping form visibility
  use_default_shipping.addEventListener("change", function () {
    hideable_shipping_form.toggle(this.checked);
  });

  // Toggle billing form visibility
  use_default_billing.addEventListener("change", function () {
    hideable_billing_form.toggle(this.checked);
  });
</script>
{% endblock extra_scripts %}
















