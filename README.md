# 🧭 SRM Lost & Found – Trichy Campus

An Ultimate-level, mobile-friendly campus lost-and-found application with a **Premium Modern SaaS** interface, built with **Streamlit** and **Supabase** (Email Auth, PostgreSQL, Row Level Security and Storage).

> **Notice:** This is a student-built project. It is not officially affiliated with, endorsed by, or operated by SRM Institute of Science and Technology unless authorized in writing.

## Project contents

- `app.py` – Streamlit application (authentication, dashboard, reports, claims, notifications, admin moderation, QR profile, student chat and Basic Smart Matching).
- `supabase_schema.sql` – database schema, triggers, RLS policies, safe public profile view, storage bucket and function hardening.
- `requirements.txt` – Python dependencies.
- `.streamlit/config.toml` – visual theme.
- `.streamlit/secrets.toml.example` – safe template; contains no API key.
- `.gitignore` – excludes real secrets and local files.

## Selected product configuration

- **Development level:** Ultimate
- **UI:** Premium Modern SaaS (responsive layout, polished cards, gradient hero, refined navigation and micro-interactions)
- **Matching:** Basic Smart Matching (explainable rule-based similarity using item title, description, category and campus location)
- Matching suggestions are recommendations only. Students and admins must verify ownership manually; this is not an AI model and does not prove an item belongs to a claimant.

## Supabase project configuration (required — no demo mode)

This project package is prepared for the connected Supabase project:

- Project reference: `dpnjzudrxbgeuewpxfnf`
- Project URL: `https://dpnjzudrxbgeuewpxfnf.supabase.co`

Run the complete `supabase_schema.sql` file in Supabase Dashboard → SQL Editor before launching the app. It creates/upgrades the app tables, registration fields, safe public profile view, RLS policies, triggers and Storage bucket. Existing users should update their register number and department from **My Profile** after applying the schema.

**Never put a Supabase `service_role` key or secret key in this app, GitHub, or Streamlit secrets.** Use only the publishable key (or legacy anon key) in the `anon_key` setting.

## Run locally

1. Extract the ZIP.
2. Install Python 3.11.
3. In a terminal opened in this folder, run:

   ```bash
   python -m venv .venv
   ```

   Windows:
   ```powershell
   .venv\Scripts\activate
   ```

   macOS/Linux:
   ```bash
   source .venv/bin/activate
   ```

4. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Run `supabase_schema.sql` in Supabase Dashboard → SQL Editor.
6. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace `YOUR_SUPABASE_PUBLISHABLE_KEY` with the publishable key from Supabase → Project Settings → API Keys. Never use a service-role/secret key.
7. Start the app. If Supabase credentials or connection are missing, the app stops with a setup error; it never switches to demo/local storage.

   ```bash
   streamlit run app.py
   ```

## Upload to GitHub

1. Create a **new empty GitHub repository** (do not add a README or license during creation).
2. Extract this ZIP on your computer.
3. Open a terminal in the extracted folder and run:

   ```bash
   git init
   git add .
   git status
   ```

4. Confirm `.streamlit/secrets.toml` is **not** listed. Then:

   ```bash
   git commit -m "SRM Lost and Found initial release"
   git branch -M main
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git
   git push -u origin main
   ```

Replace the repository URL with your own GitHub repository URL. Do not upload passwords, service-role keys, or `.streamlit/secrets.toml`.

## Deploy on Streamlit Community Cloud

1. Open <https://share.streamlit.io> and sign in with GitHub.
2. Create an app and select your repository, branch `main`, and main file `app.py`.
3. Open the app's **Settings → Secrets** and add:

   ```toml
   [supabase]
   url = "https://dpnjzudrxbgeuewpxfnf.supabase.co"
   anon_key = "YOUR_SUPABASE_PUBLISHABLE_KEY"
   ```

4. Save and deploy/reboot the app.
5. In Supabase → Authentication → URL Configuration, set the deployed Streamlit app URL as the Site URL and add any required redirect URL.

## First admin account

After registering your own account, promote the intended administrator from the Supabase SQL Editor. Replace the email with the exact account you registered:

```sql
update public.profiles
set role = 'admin'
where id = (
  select id from auth.users
  where email = 'YOUR_REGISTERED_EMAIL'
);
```

Do not make every student an administrator. The database trigger prevents ordinary users from changing their own role.

## Important security and launch notes

- RLS is enabled on all six public application tables.
- Trigger-only SECURITY DEFINER functions have direct API execution revoked; the `is_admin()` helper is SECURITY INVOKER.
- Item photos are stored in a **public-read** bucket. Anyone who obtains a photo URL may view that image. Do not upload photos showing ID numbers, register numbers, phone numbers or other private information.
- Registration domain filtering in the current app is a user-interface restriction, not a complete server-side institutional identity verification system.
- Login is maintained in the active Streamlit browser session; users may need to log in again after a server restart or a new session.
- The Supabase Security Advisor may still show policy-role warnings for some RLS policies. Review the live advisor and test access using both signed-out and signed-in accounts before opening this to the campus.
- This project has not yet been end-to-end tested with two real student accounts or deployed to a public URL.

## Acceptance test before campus use

- Register two test accounts and confirm email verification works.
- Sign in as both accounts on separate browser sessions.
- Create a lost/found report with a non-sensitive photo; verify the other account can browse and filter it.
- Send a claim and verify that only the item owner and claimant can view the claim.
- Verify the owner can respond and the claimant receives the notification.
- Confirm one student cannot edit or delete another student's report.
- Verify private chat messages are visible only to the two participants.
- Verify student role cannot be changed by a normal student.
- Test the app from a phone-sized browser and check image upload, QR download and logout.


## Student identity and privacy

- Registration requires full name, unique register number, department, email and password.
- Student profile details are stored in `public.profiles`; the register number is private to the student/admin profile view.
- Item cards and report details show the reporter's name, department and a masked register number (last four characters only).
- The `profiles_public` view exposes only the masked register number for public report/chat display. Do not remove this privacy projection or broaden the `profiles` SELECT policy.
