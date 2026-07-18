from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models.subscription import Subscription

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


def _plan_for_price(price_id: str) -> str:
    if price_id == settings.stripe_price_id_agency:
        return "agency"
    if price_id == settings.stripe_price_id_pro:
        return "pro"
    return "free"


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Stripe is the single source of truth for subscription state -- this
    is the only place `subscriptions` rows are written. Requires
    STRIPE_WEBHOOK_SECRET to be set to the signing secret for the endpoint
    registered in the Stripe dashboard (or `stripe listen` locally)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid webhook payload: {exc}") from exc

    obj = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        user_id = obj.get("client_reference_id")  # set to the Clerk user id at Checkout creation
        if user_id:
            existing = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
            if existing is None:
                db.add(
                    Subscription(
                        user_id=user_id,
                        stripe_customer_id=obj["customer"],
                        stripe_subscription_id=obj.get("subscription"),
                        plan="pro",
                        status="active",
                    )
                )
                await db.commit()

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.created"):
        price_id = obj["items"]["data"][0]["price"]["id"]
        customer_id = obj["customer"]
        sub = await _get_by_customer(db, customer_id)
        if sub:
            sub.plan = _plan_for_price(price_id)
            sub.status = obj["status"]
            period_end = obj.get("current_period_end")
            if period_end:
                sub.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        customer_id = obj["customer"]
        sub = await _get_by_customer(db, customer_id)
        if sub:
            sub.plan = "free"
            sub.status = "canceled"
            await db.commit()

    return {"received": True}


async def _get_by_customer(db: AsyncSession, stripe_customer_id: str) -> Subscription | None:
    return await db.scalar(select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id))
