from __future__ import annotations

import os
from dataclasses import dataclass

import stripe


@dataclass
class BillingConfig:
    secret_key: str | None
    webhook_secret: str | None


def get_billing_config() -> BillingConfig:
    return BillingConfig(
        secret_key=os.getenv("STRIPE_SECRET_KEY"),
        webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
    )


def create_checkout_session(customer_email: str, price_id: str, success_url: str, cancel_url: str) -> str:
    cfg = get_billing_config()
    if not cfg.secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")

    stripe.api_key = cfg.secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url
