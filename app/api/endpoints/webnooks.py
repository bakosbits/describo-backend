from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
import stripe
import logging
from typing import Optional
from app.api.deps import get_current_user, get_jwt_token
from app.models.subscription import (
    SubscriptionInfo,
    WebhookResponse,
)
from app.services.stripe_service import stripe_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature")
):
    """Handle Stripe webhooks"""
    try:
        # Log incoming webhook attempt
        logger.info(f"Received Stripe webhook request from {request.client.host if request.client else 'unknown'}")
        
        payload = await request.body()
        payload_size = len(payload)
        logger.info(f"Webhook payload size: {payload_size} bytes")
        
        # Verify webhook signature
        if not stripe_signature:
            logger.error("Webhook rejected: Missing Stripe signature header")
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        
        # Check if webhook secret is configured
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.error("Webhook rejected: STRIPE_WEBHOOK_SECRET not configured")
            raise HTTPException(status_code=500, detail="Webhook secret not configured")
        
        logger.info(f"Full webhook signature: {stripe_signature}")
        logger.info(f"Webhook secret configured (first 10 chars): {settings.STRIPE_WEBHOOK_SECRET[:10]}...")
        logger.info(f"Raw payload (first 200 bytes): {payload[:200]}")
        logger.info(f"Raw payload (last 200 bytes): {payload[-200:]}")
        
        # Manual signature verification with detailed logging
        try:
            import hmac
            import hashlib
            import time
            
            # Parse the signature header
            sig_parts = stripe_signature.split(',')
            timestamp = None
            signatures = []
            
            for part in sig_parts:
                if part.startswith('t='):
                    timestamp = part[2:]
                elif part.startswith('v1='):
                    signatures.append(part[3:])
            
            logger.info(f"Parsed timestamp: {timestamp}")
            logger.info(f"Parsed signatures: {signatures}")
            
            if timestamp:
                current_time = int(time.time())
                webhook_time = int(timestamp)
                time_diff = abs(current_time - webhook_time)
                logger.info(f"Time difference: {time_diff} seconds (current: {current_time}, webhook: {webhook_time})")
                
                # Check if timestamp is too old (Stripe default is 300 seconds)
                if time_diff > 300:
                    logger.warning(f"Webhook timestamp is {time_diff} seconds old (max allowed: 300)")
            
            # Create the signed payload
            signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
            logger.info(f"Signed payload length: {len(signed_payload)}")
            logger.info(f"Signed payload (first 100 chars): {signed_payload[:100]}")
            
            # Calculate expected signature
            expected_signature = hmac.new(
                settings.STRIPE_WEBHOOK_SECRET.encode('utf-8'),
                signed_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            logger.info(f"Expected signature: {expected_signature}")
            logger.info(f"Received signatures: {signatures}")
            
            # Check if any received signature matches
            signature_match = any(hmac.compare_digest(expected_signature, sig) for sig in signatures)
            logger.info(f"Signature match: {signature_match}")
            
        except Exception as debug_e:
            logger.error(f"Debug signature verification error: {str(debug_e)}")
        
        # Now try the official Stripe verification
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
            logger.info("Webhook signature verification successful")
        except ValueError as e:
            logger.error(f"Webhook rejected: Invalid payload format - {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook rejected: Signature verification failed - {str(e)}")
            logger.error(f"Full error details: {repr(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Handle the event
        event_type = event['type']
        event_data = event['data']['object']
        event_id = event.get('id', 'unknown')
        
        logger.info(f"Processing Stripe webhook: {event_type} (ID: {event_id})")
        
        if event_type == 'checkout.session.completed':
            logger.info(f"Handling checkout completion for session: {event_data.get('id', 'unknown')}")
            
            # For Pricing Table sessions, we need to expand the session to get line items
            session_id = event_data.get('id')
            if session_id:
                try:
                    # Retrieve the full session with line items
                    expanded_session = stripe.checkout.Session.retrieve(
                        session_id,
                        expand=['line_items']
                    )
                    logger.info(f"Expanded session line items: {expanded_session.get('line_items', {})}")
                    
                    # Convert to dict and merge with event data
                    session_dict = dict(expanded_session)
                    await stripe_service.handle_checkout_completed(session_dict)
                except Exception as e:
                    logger.error(f"Error expanding session {session_id}: {e}")
                    # Fallback to original event data
                    await stripe_service.handle_checkout_completed(event_data)
            else:
                await stripe_service.handle_checkout_completed(event_data)
            
        elif event_type == 'customer.subscription.updated':
            logger.info(f"Handling subscription update for: {event_data.get('id', 'unknown')}")
            await stripe_service.handle_subscription_updated(event_data)
            
        elif event_type == 'customer.subscription.deleted':
            logger.info(f"Handling subscription deletion for: {event_data.get('id', 'unknown')}")
            await stripe_service.handle_subscription_updated(event_data)
            
        elif event_type == 'invoice.payment_failed':
            logger.info(f"Handling payment failure for invoice: {event_data.get('id', 'unknown')}")
            await stripe_service.handle_invoice_payment_failed(event_data)
            
        else:
            logger.info(f"Unhandled webhook event type: {event_type} (ID: {event_id})")            
        
        logger.info(f"Successfully processed webhook: {event_type} (ID: {event_id})")
        return WebhookResponse(
            success=True,
            message=f"Webhook {event_type} processed successfully"
        )
        
    except HTTPException as e:
        logger.error(f"Webhook HTTP error: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")