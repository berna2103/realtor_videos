import { NextResponse } from 'next/server';
import Stripe from 'stripe';

export async function POST(req: Request) {
  try {
    // 1. Check for the key safely
    if (!process.env.STRIPE_SECRET_KEY) {
      throw new Error("Missing STRIPE_SECRET_KEY environment variable");
    }

    // 2. Initialize Stripe INSIDE the function to prevent build crashes
    const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2026-02-25.clover' });

    const { userId, priceId } = await req.json();

    if (!userId) {
      return NextResponse.json({ error: 'User ID is required' }, { status: 400 });
    }

    // Determine the base URL (uses localhost if env var is missing during local dev)
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';

    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: [{ price: priceId, quantity: 1 }],
      mode: 'payment',
      success_url: `${baseUrl}/?success=true`,
      cancel_url: `${baseUrl}/?canceled=true`,
      client_reference_id: userId, 
    });

    return NextResponse.json({ url: session.url });
  } catch (error: any) {
    console.error("🔥 Stripe Checkout Error:", error.message); 
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}