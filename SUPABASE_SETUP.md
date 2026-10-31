# Supabase connection checklist

This application is Supabase-only. There is no demo backend or local fallback.

## 1. Apply the database schema

1. Open the Supabase project `dpnjzudrxbgeuewpxfnf`.
2. Open **SQL Editor → New query**.
3. Paste the complete contents of `supabase_schema.sql` and run it.
4. Confirm that the tables `profiles`, `items`, `claim_requests`, `content_reports`, `notifications`, and `direct_messages` exist, along with the `item-photos` Storage bucket.

The SQL adds the `register_number` field, a unique index, the `profiles_public` safe view, registration trigger, RLS policies, and storage policies. It is written to be re-runnable. Existing students must update their register number and department from **My Profile** after the migration.

## 2. Configure the app key

For local development, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then set:

```toml
[supabase]
url = "https://dpnjzudrxbgeuewpxfnf.supabase.co"
anon_key = "YOUR_SUPABASE_PUBLISHABLE_KEY"
```

Get the publishable key from **Supabase → Project Settings → API Keys**. A legacy anon key is also acceptable. Never use the `service_role` key or a secret key.

For Streamlit Community Cloud, paste the same TOML block into **App → Settings → Secrets**. Do not commit `.streamlit/secrets.toml` to GitHub.

## 3. Run and verify

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Register a test account with full name, unique register number, department, email and password. Verify that the profile row appears in `public.profiles`, then create a Lost report and a Found report. Verify the report rows in `public.items` and uploaded images in Storage → `item-photos`.

If the publishable key is missing or Supabase cannot be initialized, the app displays a configuration error and stops. It does not switch to temporary demo data.

## Privacy

Full register numbers are stored in `profiles` and shown only on the student's own profile (and to administrators). Item cards and report details show a masked value via `profiles_public`. Do not remove that view or make the full `profiles` table publicly readable.

## Basic Smart Matching

The app ranks opposite-type open reports in the same category using title similarity, shared description keywords and whether the campus location matches. It reads report rows from Supabase and does not require an external AI API or additional database table. Scores are suggestions only and must never be treated as proof of ownership.

## Fix: “Database error saving new user” during registration

This usually means the database trigger that creates the matching `profiles` row failed while Supabase Auth was creating the account. The schema in this ZIP fixes the student-code generator so it does not depend on `pgcrypto` being available on the function search path.

After uploading this updated project, you must also update the **remote Supabase database**:

1. Open the correct Supabase project → **SQL Editor** → **New query**.
2. Paste the complete updated `supabase_schema.sql` from this ZIP and run it. The script is designed to be re-runnable.
3. Check **Logs → Postgres Logs** if registration still fails; look for the `on_auth_user_created` trigger error.
4. Try registering again with a register number that is not already used.

Updating the app files or redeploying alone does not change the database trigger. Do not delete existing users or disable the profile trigger as a workaround.
