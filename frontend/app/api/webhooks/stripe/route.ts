import { NextResponse } from 'next/server';
import Stripe from 'stripe';
import { createClient } from '@supabase/supabase-js';

export async function POST(req: Request) {
  try {
    // 1. Safely check for missing environment variables
    if (!process.env.STRIPE_SECRET_KEY || !process.env.STRIPE_WEBHOOK_SECRET) {
      throw new Error("Missing Stripe Environment Variables");
    }
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.SUPABASE_SERVICE_ROLE_KEY) {
      throw new Error("Missing Supabase Environment Variables");
    }

    // Initialize clients INSIDE the function to prevent module-level crashes
    const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2026-02-25.clover' });
    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL,
      process.env.SUPABASE_SERVICE_ROLE_KEY
    );

    const body = await req.text();
    const signature = req.headers.get('stripe-signature');

    if (!signature) {
      console.error("⚠️ Webhook Error: Missing Stripe signature header.");
      return NextResponse.json({ error: 'Missing signature' }, { status: 400 });
    }

    let event: Stripe.Event;

    // 2. Verify the webhook signature
    try {
      event = stripe.webhooks.constructEvent(body, signature, process.env.STRIPE_WEBHOOK_SECRET);
    } catch (err: any) {
      console.error(`⚠️ Webhook Signature Verification Failed: ${err.message}`);
      // If the secret is wrong, it sends a 400, not a 500
      return NextResponse.json({ error: `Webhook Error: ${err.message}` }, { status: 400 });
    }

    // 3. Handle the successful checkout event
    if (event.type === 'checkout.session.completed') {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId = session.client_reference_id;
      
      const amountPaid = session.amount_total; // Note: 1500 means $15.00
      
      console.log(`✅ Payment received! User: ${userId}, Amount: ${amountPaid}`);

      // Determine how many credits to give based on the amount paid
      let creditsToAdd = 0;
      if (amountPaid === 1500) {
        creditsToAdd = 5;
      } else if (amountPaid === 2500) {
        creditsToAdd = 10;
      } else {
        // Fallback: If you are testing a different price, give 1 credit so it doesn't fail silently
        creditsToAdd = 1; 
      }

      if (userId && creditsToAdd > 0) {
        const { error } = await supabaseAdmin.rpc('increment_credits', {
          target_user_id: userId,
          amount: creditsToAdd
        });

        if (error) {
          console.error("🔥 Supabase Database Error:", error);
          throw error;
        }
        
        console.log(`🎉 Successfully added ${creditsToAdd} credits to user ${userId}`);
      } else {
         console.warn("⚠️ Could not add credits: Missing userId or unhandled payment amount.");
      }
    }

    return NextResponse.json({ received: true });

  } catch (err: any) {
    // THIS is the magic line. It will print the exact reason for the 500 error in your Next.js terminal!
    console.error("🔥 CRITICAL WEBHOOK ERROR:", err.message);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}