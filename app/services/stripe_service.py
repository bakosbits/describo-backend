import os
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.core.config import settings
from app.services.supabase_service import supabase_service

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_api_key
webhook_secret = settings.stripe_webhook_secret

class StripeService:

    def __init__(self):
        pass  # No longer need to store supabase instance

    PRICE_IDS = {
        'Maker': settings.stripe_price_id_maker,
        'Studio': settings.stripe_price_id_studio
    }

    async def create_stripe_customer(self, user_id: str, email: str, first_name: str = None, last_name: str = None, user_jwt: str = None) -> str:
        """Create Stripe customer for a user. Uses JWT if provided, otherwise uses service client."""
        try:
            # Create customer name from first and last name
            name = None
            if first_name and last_name:
                name = f"{first_name} {last_name}".strip()
            elif first_name:
                name = first_name
            elif last_name:
                name = last_name

            # Create new Stripe customer
            customer_data = {
                'email': email,
                'metadata': {'user_id': user_id}
            }
            if name:
                customer_data['name'] = name
                
            customer = stripe.Customer.create(**customer_data)
            
            # Store customer ID in database
            if user_jwt:
                # Use user's JWT token when available (respects RLS)
                client = supabase_service.get_client(user_jwt)
                client.table('profiles').update({
                    'stripe_customer_id': customer.id
                }).eq('id', user_id).execute()
            else:
                # Use service client only when no JWT available (e.g., during signup)
                service_client = supabase_service.get_service_client()
                service_client.table('profiles').update({
                    'stripe_customer_id': customer.id
                }).eq('id', user_id).execute()
            
            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id
            
        except Exception as e:
            logger.error(f"Error creating Stripe customer on signup: {e}")
            # Don't raise the error - signup should still succeed even if Stripe fails
            return None


    async def create_or_get_customer(self, user_id: str, email: str, user_jwt: str, name: str = None) -> str:
        """Create or retrieve Stripe customer for user"""
        try:
            # Check if user already has a Stripe customer ID
            client = supabase_service.get_client(user_jwt)
            result = client.table('profiles').select('stripe_customer_id').eq('id', user_id).single().execute()
            
            if result.data and result.data.get('stripe_customer_id'):
                return result.data['stripe_customer_id']
            
            # Create new Stripe customer
            customer_data = {
                'email': email,
                'metadata': {'user_id': user_id}
            }
            if name:
                customer_data['name'] = name
                
            customer = stripe.Customer.create(**customer_data)
            
            # Store customer ID in database
            client.table('profiles').update({
                'stripe_customer_id': customer.id
            }).eq('id', user_id).execute()
            
            return customer.id
            
        except Exception as e:
            logger.error(f"Error creating/getting Stripe customer: {e}")
            raise



    async def create_checkout_session(self, user_id: str, plan: str, success_url: str, cancel_url: str, user_jwt: str) -> str:
        """Create Stripe checkout session for subscription"""
        try:
            # Get user profile
            client = supabase_service.get_client(user_jwt)
            result = client.table('profiles').select('*').eq('id', user_id).single().execute()
            if not result.data:
                raise ValueError("User not found")
            
            user_profile = result.data
            
            # Create or get customer
            customer_id = await self.create_or_get_customer(
                user_id, 
                user_profile['email'], 
                user_jwt,
                f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}".strip()
            )
            
            # Get price ID for plan
            price_id = self.PRICE_IDS.get(plan)
            if not price_id:
                raise ValueError(f"Invalid plan: {plan}")
            
            # Create checkout session
            session_data = {
                'customer': customer_id,
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': price_id,
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'metadata': {
                    'user_id': user_id,
                    'plan': plan
                }
            }
            
            # For subscriptions, add trial period if needed
            if plan == 'covenant':
                session_data['subscription_data'] = {
                    'trial_period_days': 14,
                    'metadata': {
                        'user_id': user_id,
                        'plan': plan
                    }
                }
            
            session = stripe.checkout.Session.create(**session_data)
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise


    async def create_portal_session(self, user_id: str, configuration_id: str, return_url: str, user_jwt: str) -> str:
        """Create Stripe customer portal session"""
        try:
            # Get user's Stripe customer ID
            client = supabase_service.get_client(user_jwt)
            result = client.table('profiles').select('stripe_customer_id').eq('id', user_id).single().execute()
            
            if not result.data or not result.data.get('stripe_customer_id'):
                raise ValueError("User has no Stripe customer ID")
            
            customer_id = result.data['stripe_customer_id']
            
            # Create portal session
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                configuration=configuration_id,
                return_url=return_url,
            )
            
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating portal session: {e}")
            raise
    
    async def handle_checkout_completed(self, session: Dict[str, Any]) -> None:
        """Handle successful checkout completion"""
        try:

            # Use service client for webhook operations (bypasses RLS)
            service_client = supabase_service.get_service_client()
            
            # Get user_id - handle both Stripe customer IDs and direct user UUIDs
            client_ref = session.get('client_reference_id')
            metadata_user_id = session.get('metadata', {}).get('user_id')
            
            user_id = None
            
            if client_ref and client_ref.startswith('cus_'):
                result = service_client.table('profiles').select('id').eq('stripe_customer_id', client_ref).single().execute()
                
                if not result.data:
                    raise ValueError(f"No user found for Stripe customer ID: {client_ref}")

                user_id = result.data['id']
            
            elif metadata_user_id:
                # Direct user UUID from custom checkout
                user_id = metadata_user_id

            else:
                logger.error(f"No user identifier found in session {session.get('id')}. client_reference_id: {session.get('client_reference_id')}, metadata: {session.get('metadata')}")
                raise ValueError("No user identifier found in checkout session")
            
            # For Pricing Table, we need to determine the plan from the line items
            plan = None
            
            if 'metadata' in session and 'plan' in session['metadata']:
                # Custom checkout with plan in metadata
                plan = session['metadata']['plan']
            
            else:

                line_items = session.get('line_items', {}).get('data', [])
                if line_items:
                    price_id = line_items[0].get('price', {}).get('id')
                    plan_map = {v: k for k, v in self.PRICE_IDS.items()}
                    plan = plan_map.get(price_id)
            
            if not plan:
                logger.error(f"No plan found for session {session.get('id')}. Line items: {session.get('line_items')}")
                raise ValueError("No plan found in checkout session")
            
            update_data = {
                'plan_type': plan,
                'subscription_status': 'active',
                'subscription_start_date': datetime.now(timezone.utc).isoformat()
            }
            
            
            # For subscriptions, store subscription ID
            if session['mode'] == 'subscription':
                update_data['stripe_subscription_id'] = session['subscription']
                # Set reset date to 1st of next month
                next_month = datetime.now(timezone.utc).replace(day=1)
                if next_month.month == 12:
                    next_month = next_month.replace(year=next_month.year + 1, month=1)
                else:
                    next_month = next_month.replace(month=next_month.month + 1)
                update_data['analyses_reset_date'] = next_month.isoformat()
            
            # Update user profile using service client
            service_client.table('profiles').update(update_data).eq('id', user_id).execute()

        except Exception as e:
            logger.error(f"Error handling checkout completed: {e}")
            raise
    
    async def handle_subscription_updated(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription status changes, including upgrades and downgrades"""
        try:
            # Use service client for webhook operations (bypasses RLS)
            service_client = supabase_service.get_service_client()

            result = service_client.table('profiles').select('*').eq('stripe_subscription_id', subscription['id']).single().execute()

            if not result.data:
                logger.warning(f"No user found for subscription {subscription['id']}")
                return

            user_profile = result.data
            status = subscription['status']

            update_data = {
                'subscription_status': status,
                'stripe_subscription_id': subscription['id']  # Ensure subscription ID is current
            }

            # Reverse mapping of PRICE_IDS to find plan name
            plan_map = {v: k for k, v in self.PRICE_IDS.items()}

            # Handle different subscription statuses
            if status == 'active':
                # Get the new plan from the subscription item
                new_price_id = subscription['items']['data'][0]['price']['id']
                new_plan = plan_map.get(new_price_id)

                if not new_plan:
                    logger.error(f"Unknown price ID {new_price_id} in subscription {subscription['id']}")
                    return

                update_data['plan_type'] = new_plan
                
                # Reset analyses count based on the new plan

            # Update user profile using service client
            service_client.table('profiles').update(update_data).eq('id', user_profile['id']).execute()

        except Exception as e:
            logger.error(f"Error handling subscription update: {e}")
            raise
    
    async def handle_invoice_payment_failed(self, invoice: Dict[str, Any]) -> None:
        """Handle failed invoice payments"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return
            
            # Use service client for webhook operations (bypasses RLS)
            service_client = supabase_service.get_service_client()            
            result = service_client.table('profiles').select('id').eq('stripe_subscription_id', subscription_id).single().execute()
            
            if not result.data:
                return
            
            service_client.table('profiles').update({
                'subscription_status': 'past_due'
            }).eq('id', result.data['id']).execute()
            
        except Exception as e:
            logger.error(f"Error handling invoice payment failed: {e}")
            raise
    
    async def get_subscription_info(self, user_id: str, user_jwt: str) -> Dict[str, Any]:
        """Get user's subscription information"""
        try:
            client = supabase_service.get_client(user_jwt)
            result = client.table('profiles').select('*').eq('id', user_id).single().execute()
            
            if not result.data:
                raise ValueError("User not found")
            
            profile = result.data
            
            return {
                'plan': profile.get('plan_type', ''),
                'status': profile.get('subscription_status', 'active'),
                'subscription_start_date': profile.get('subscription_start_date'),
                'subscription_end_date': profile.get('subscription_end_date'),
                'has_stripe_customer': bool(profile.get('stripe_customer_id'))
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription info: {e}")
            raise


    def verify_webhook_signature(payload, sig_header):
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=webhook_secret
            )
            return event
        except ValueError as e:
            # Invalid payload
            raise e
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            raise e


# Global instance
stripe_service = StripeService()

