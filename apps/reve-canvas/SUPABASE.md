# Supabase setup

Reve Canvas defaults to anonymous, in-memory mock mode. Persistence is activated only when both public Supabase variables are present; this project never needs a Reve API key in the browser.

## Hosted project

1. Create a new Supabase project in the Supabase dashboard.
2. Open the SQL Editor and run `supabase/migrations/0001_init.sql` in full.
3. In **Authentication → Providers → Email**, enable Email and enable Email OTP (magic link). Set the site URL to your deployed app origin and add `http://localhost:5182/auth/callback` for local development.
4. Copy the project URL and anon/publishable key into `.env.local`:

   ```dotenv
   REVE_MODE=mock
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
   ```

5. Restart the app. `/login` now sends magic links and the persistence module writes through owner-scoped RLS.

Never commit `.env.local`, production keys, or a Reve key.

## Local Supabase

1. Install the Supabase CLI, then from `apps/reve-canvas` run `supabase start`.
2. Run the migration with `supabase db reset` (or paste `supabase/migrations/0001_init.sql` into the local SQL editor).
3. Run `supabase status` and copy the local API URL and anon key to `.env.local` using the same variable names above.
4. Keep `REVE_MODE=mock`, then run `npm run dev`. The mock image pipeline remains local while auth and persistence use the local Supabase instance.

## Operational notes

- `credit_ledger` is append-only. The `debit_credits(amount, reason)` RPC is the only authenticated debit path; grants are an admin/service-role operation.
- Snapshots are append-only and form the project history DAG. Storage files live under `images/<user-id>/...` and are restricted by matching storage policies.
