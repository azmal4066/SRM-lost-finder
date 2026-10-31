"""SRM Lost & Found - Trichy Campus. Student-built, NOT officially affiliated with SRM IST.

Streamlit + Supabase (Auth, PostgreSQL, Storage). Uses only the public anon key; all
authorization is enforced by Row Level Security in supabase_schema.sql.
Supabase credentials are required. The app fails closed when Supabase is unavailable; no demo or local data mode exists.
"""
from __future__ import annotations

import html
import io
import re
import uuid
from difflib import SequenceMatcher
from datetime import date, datetime, timezone

import streamlit as st
from PIL import Image, ImageOps
import qrcode

try:
    from supabase import create_client
except Exception:
    create_client = None

APP = "SRM Lost & Found – Trichy Campus"
BUCKET = "item-photos"
CATEGORIES = ["Electronics", "ID / Cards", "Books & Stationery", "Bags", "Clothing", "Keys",
              "Wallet / Money", "Accessories", "Bottles & Lunchboxes", "Sports", "Other"]
LOCATIONS = ["Main Gate", "Academic Block", "Library", "Food Court / Canteen", "Boys Hostel",
             "Girls Hostel", "Sports Ground", "Auditorium", "Parking", "Bus Stop / Transport",
             "Labs", "Other"]
NOTICE = ("This is a student-built platform. It is not officially affiliated with, endorsed by, or "
          "operated by SRM Institute of Science and Technology unless authorized in writing.")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENSITIVE = [
    (re.compile(r"\bRA\d{8,}\b", re.I), "a register number"),
    (re.compile(r"(?<!\d)\d{10,16}(?!\d)"), "a long number (phone, Aadhaar, card or ID number)"),
    (re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b"), "an Aadhaar-style number"),
    (re.compile(r"\b(password|passcode|passwd|pwd|otp|cvv|pin)\b\s*[:=\-]?\s*\S+", re.I), "a password, PIN or OTP"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "an email address"),
]

st.set_page_config(page_title=APP, page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@600;700;800&display=swap');
:root{--ink:#17233b;--muted:#71809a;--brand:#5b5ce2;--brand2:#8585ff;--surface:#ffffff;--canvas:#f5f7fc;--line:#e7ebf3;--good:#16865b;--bad:#c64a58}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
.stApp{background:radial-gradient(ellipse at 8% 0%,rgba(119,120,255,.10),transparent 34%),linear-gradient(180deg,#f8f9ff 0%,#f4f6fb 100%);color:var(--ink)}
#MainMenu,footer{visibility:hidden}
.block-container{padding:1.6rem 2.1rem 3rem;max-width:1280px}
h1,h2,h3{font-family:'Manrope','DM Sans',sans-serif;color:var(--ink);letter-spacing:-.035em}
h1{font-weight:800}h2,h3{font-weight:750}
p, label, .stMarkdown{color:var(--ink)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#171b3d 0%,#242957 100%);border-right:0}
[data-testid="stSidebar"] *{color:#f4f5ff!important}
[data-testid="stSidebar"] [data-testid="stButton"] button{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.09);color:#fff!important;text-align:left;border-radius:12px}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{background:rgba(132,132,255,.22);border-color:rgba(170,170,255,.35)}
.hero{position:relative;overflow:hidden;background:linear-gradient(120deg,#242653 0%,#4c4bc2 58%,#7777ed 100%);color:#fff;padding:1.65rem 1.8rem;border-radius:24px;margin-bottom:1.25rem;box-shadow:0 18px 45px rgba(55,57,135,.18);animation:rise .45s ease both}
.hero:after{content:"";position:absolute;width:270px;height:270px;border:1px solid rgba(255,255,255,.16);border-radius:50%;right:-65px;top:-125px;box-shadow:0 0 0 35px rgba(255,255,255,.04),0 0 0 75px rgba(255,255,255,.035)}
.hero h1{color:#fff;margin:0;font-size:clamp(1.6rem,3vw,2.35rem);font-weight:800}.hero p{color:rgba(255,255,255,.82);margin:.45rem 0 0;font-size:.98rem}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.9rem;margin:.9rem 0 1.5rem}
.stat{background:rgba(255,255,255,.88);border:1px solid var(--line);border-radius:18px;padding:1rem 1.15rem;text-align:left;box-shadow:0 7px 22px rgba(31,44,86,.045);animation:rise .5s ease both}
.stat b{display:block;font-size:2rem;line-height:1.15;color:var(--ink);font-family:'Manrope',sans-serif}.stat span{font-size:.8rem;color:var(--muted);font-weight:600}
.badge{display:inline-block;padding:.22rem .65rem;border-radius:99px;font-size:.7rem;font-weight:700;letter-spacing:.035em;margin-right:.35rem;text-transform:uppercase}
.badge.lost{background:#fff0f1;color:#b63f50}.badge.found{background:#e8f8f0;color:#14794e}.badge.open{background:#eeefff;color:#4e50c6}.badge.resolved{background:#edf0f5;color:#596579}.badge.removed{background:#fff4df;color:#9a6700}
.meta{color:var(--muted);font-size:.82rem;line-height:1.65;margin:.35rem 0}
.notice{background:#f0f1ff;border:1px solid #e0e2ff;border-left:4px solid var(--brand);padding:.8rem 1rem;border-radius:12px;font-size:.8rem;margin-top:2rem;color:#4c5272}
[data-testid="stVerticalBlockBorderWrapper"]{border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.9);box-shadow:0 8px 24px rgba(31,44,86,.045);animation:rise .35s ease both}
.stButton>button,.stFormSubmitButton>button{border-radius:12px;font-weight:700;min-height:2.65rem;border:1px solid #e3e6f0;transition:transform .15s,box-shadow .15s,background .15s}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:linear-gradient(110deg,#5354d5,#7777ed);border:0;color:#fff;box-shadow:0 7px 16px rgba(83,84,213,.18)}
.stButton>button:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);box-shadow:0 7px 18px rgba(40,48,100,.12)}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"]>div,[data-testid="stDateInput"] input{border-radius:11px!important}
[data-testid="stTabs"] button{font-weight:700}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media(max-width:700px){.block-container{padding:1rem .8rem 2rem}.stats{grid-template-columns:1fr}.hero{padding:1.25rem;border-radius:18px}}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- helpers
def esc(t) -> str:
    return html.escape(str(t or "")).replace("\n", "<br>")


def badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{html.escape(text)}</span>'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_err(e: Exception) -> str:
    m = str(e) or e.__class__.__name__
    low = m.lower()
    if "invalid login" in low:
        return "Incorrect email or password."
    if "not confirmed" in low:
        return "Please confirm your email (check your inbox) before logging in."
    if "already registered" in low or "already been registered" in low:
        return "That email is already registered. Try logging in."
    if "row-level security" in low or "permission denied" in low:
        return "You don't have permission to do that."
    if "rate limit" in low:
        return "Too many attempts. Please wait a minute and try again."
    return m[:200]


def attempt(fn, *a, **k):
    try:
        return True, fn(*a, **k)
    except Exception as e:  # show friendly message, never a stack trace
        st.error(clean_err(e))
        return False, None


def find_sensitive(*texts: str) -> list[str]:
    found = []
    for t in texts:
        for rx, label in SENSITIVE:
            if rx.search(t or "") and label not in found:
                found.append(label)
    return found


def process_photo(upload) -> bytes:
    """Validate, strip EXIF/GPS, downscale, and re-encode as JPEG."""
    if upload.size > 5 * 1024 * 1024:
        raise ValueError("Photo must be under 5 MB.")
    img = Image.open(io.BytesIO(upload.getvalue()))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1280, 1280))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def go(page: str, item_id: str | None = None):
    st.session_state.page = page
    st.session_state.item_id = item_id


def match(it: dict, f: dict) -> bool:
    q = (f.get("q") or "").lower().strip()
    if q and q not in f"{it['title']} {it['description']}".lower():
        return False
    for k in ("type", "category", "location", "status"):
        if f.get(k) and it[k] != f[k]:
            return False
    if f.get("date_from") and it["event_date"] < f["date_from"].isoformat():
        return False
    if f.get("date_to") and it["event_date"] > f["date_to"].isoformat():
        return False
    return True


def basic_match_score(source: dict, candidate: dict) -> int:
    """Explainable, rule-based Lost/Found matching; no external AI service required."""
    a_title = re.sub(r"[^a-z0-9 ]", " ", str(source.get("title", "")).lower())
    b_title = re.sub(r"[^a-z0-9 ]", " ", str(candidate.get("title", "")).lower())
    a_desc = re.sub(r"[^a-z0-9 ]", " ", str(source.get("description", "")).lower())
    b_desc = re.sub(r"[^a-z0-9 ]", " ", str(candidate.get("description", "")).lower())
    title_similarity = SequenceMatcher(None, a_title, b_title).ratio()
    a_words, b_words = set((a_title + " " + a_desc).split()), set((b_title + " " + b_desc).split())
    ignored = {"the", "and", "with", "for", "from", "this", "that", "item", "found", "lost"}
    a_words -= ignored; b_words -= ignored
    overlap = len(a_words & b_words) / max(1, len(a_words | b_words))
    same_location = source.get("location") == candidate.get("location")
    same_category = source.get("category") == candidate.get("category")
    score = 0.45 * title_similarity + 0.30 * overlap + 0.15 * same_location + 0.10 * same_category
    return round(score * 100)


# ----------------------------------------------------------------------------- backends
class Live:
    """Supabase-backed. One instance (and one client/session) per browser session."""
    mode = "live"

    def __init__(self, url: str, key: str):
        self.c = create_client(url, key)
        self.user = None
        self.profile = None

    @property
    def uid(self):
        return self.user.id if self.user else None

    @property
    def is_admin(self):
        return bool(self.profile and self.profile.get("role") == "admin")

    def sign_up(self, email, pw, name, register_number, department):
        r = self.c.auth.sign_up({"email": email, "password": pw, "options": {"data": {"full_name": name, "register_number": register_number, "department": department}}})
        if r.session:  # email confirmation disabled -> already logged in
            self.user = r.user
            self._load_profile()
            return True
        return False

    def sign_in(self, email, pw):
        r = self.c.auth.sign_in_with_password({"email": email, "password": pw})
        self.user = r.user
        self._load_profile()

    def update_profile(self, full_name, register_number, department):
        self.c.table("profiles").update({
            "full_name": full_name.strip(),
            "register_number": register_number.strip().upper(),
            "department": department,
        }).eq("id", self.uid).execute()
        self._load_profile()

    def sign_out(self):
        try:
            self.c.auth.sign_out()
        finally:
            self.user = self.profile = None

    def _load_profile(self):
        self.profile = self.c.table("profiles").select("*").eq("id", self.uid).single().execute().data


    # student QR + private one-to-one messaging
    def find_student(self, code):
        rows = self.c.table("profiles_public").select("id,full_name,department,student_code") \
            .eq("student_code", code.strip().upper()).limit(1).execute().data or []
        return rows[0] if rows else None

    def send_message(self, receiver_id, message):
        return self.c.table("direct_messages").insert({
            "sender_id": self.uid, "receiver_id": receiver_id, "message": message.strip()
        }).execute().data[0]

    def chat_messages(self, other_id, limit=100):
        q = f"and(sender_id.eq.{self.uid},receiver_id.eq.{other_id}),and(sender_id.eq.{other_id},receiver_id.eq.{self.uid})"
        return self.c.table("direct_messages").select("*").or_(q) \
            .order("created_at", desc=False).limit(limit).execute().data or []

    def chat_inbox(self):
        rows = self.c.table("direct_messages").select("*") \
            .or_(f"sender_id.eq.{self.uid},receiver_id.eq.{self.uid}") \
            .order("created_at", desc=True).limit(300).execute().data or []
        peers = []
        seen = set()
        for row in rows:
            peer = row["receiver_id"] if row["sender_id"] == self.uid else row["sender_id"]
            if peer != self.uid and peer not in seen:
                seen.add(peer)
                found = self.c.table("profiles_public").select("id,full_name,student_code") \
                    .eq("id", peer).limit(1).execute().data or []
                if found:
                    peers.append(found[0])
        return peers

    # items
    def list_items(self, f, limit=60):
        q = self.c.table("items").select("*, profiles_public(full_name,department,register_number_masked)").neq("status", "removed")
        for k in ("type", "category", "location", "status"):
            if f.get(k):
                q = q.eq(k, f[k])
        if f.get("date_from"):
            q = q.gte("event_date", f["date_from"].isoformat())
        if f.get("date_to"):
            q = q.lte("event_date", f["date_to"].isoformat())
        t = re.sub(r"[^\w\s\-]", " ", f.get("q") or "").strip()  # strip filter-syntax characters
        if t:
            q = q.or_(f"title.ilike.%{t}%,description.ilike.%{t}%")
        return q.order("created_at", desc=True).limit(limit).execute().data or []

    def get_item(self, iid):
        r = self.c.table("items").select("*, profiles_public(full_name,department,register_number_masked)").eq("id", iid).limit(1).execute().data
        return r[0] if r else None

    def my_items(self):
        return self.c.table("items").select("*, profiles_public(full_name,department,register_number_masked)").eq("reporter_id", self.uid) \
            .neq("status", "removed").order("created_at", desc=True).execute().data or []

    def create_item(self, d, photo):
        if photo:
            path = f"{self.uid}/{uuid.uuid4().hex}.jpg"
            self.c.storage.from_(BUCKET).upload(path, photo, {"content-type": "image/jpeg"})
            d["photo_url"] = self.c.storage.from_(BUCKET).get_public_url(path)
        d["reporter_id"] = self.uid
        return self.c.table("items").insert(d).execute().data[0]

    def update_item(self, iid, fields):
        self.c.table("items").update(fields).eq("id", iid).execute()

    def delete_item(self, iid):
        self.c.table("items").delete().eq("id", iid).execute()

    def _count(self, **flt):
        q = self.c.table("items").select("id", count="exact").neq("status", "removed")
        for k, v in flt.items():
            q = q.eq(k, v)
        return q.limit(1).execute().count or 0

    def stats(self):
        return self._count(type="lost"), self._count(type="found"), self._count(status="resolved")

    # claims
    def create_claim(self, iid, msg):
        self.c.table("claim_requests").insert({"item_id": iid, "claimant_id": self.uid, "message": msg}).execute()

    def claims_for_item(self, iid):  # RLS: owner sees all, claimant sees own, admin sees all
        return self.c.table("claim_requests").select("*, profiles_public(full_name,department,register_number_masked)").eq("item_id", iid) \
            .order("created_at", desc=True).execute().data or []

    def my_claims(self):
        return self.c.table("claim_requests").select("*, items(id,title,type,status)") \
            .eq("claimant_id", self.uid).order("created_at", desc=True).execute().data or []

    def respond_claim(self, cid, status, note):
        self.c.table("claim_requests").update(
            {"status": status, "owner_note": note or None, "responded_at": now_iso()}).eq("id", cid).execute()

    # notifications
    def notifications(self):
        return self.c.table("notifications").select("*").order("created_at", desc=True).limit(50).execute().data or []

    def unread(self):
        return self.c.table("notifications").select("id", count="exact").eq("is_read", False).limit(1).execute().count or 0

    def mark_read(self):
        self.c.table("notifications").update({"is_read": True}).eq("is_read", False).execute()

    # moderation
    def flag_item(self, iid, reason):
        self.c.table("content_reports").insert({"item_id": iid, "reporter_id": self.uid, "reason": reason}).execute()

    def flags(self):
        return self.c.table("content_reports").select("*, items(id,title,status,type)").eq("resolved", False) \
            .order("created_at", desc=True).execute().data or []

    def resolve_flag(self, fid):
        self.c.table("content_reports").update({"resolved": True}).eq("id", fid).execute()

    def all_items(self):
        return self.c.table("items").select("*, profiles_public(full_name,department,register_number_masked)").order("created_at", desc=True) \
            .limit(200).execute().data or []


def secrets_cfg():
    try:
        s = st.secrets["supabase"]
        url, key = str(s["url"]), str(s["anon_key"])
        if url and key and "YOUR" not in url.upper() and "YOUR" not in key.upper():
            return url, key
    except Exception:
        pass
    return None


def allowed_domains() -> list[str]:
    try:
        return [d.lower().lstrip("@") for d in st.secrets["app"]["allowed_email_domains"]]
    except Exception:
        return []


def backend():
    if "be" not in st.session_state:
        cfg = secrets_cfg()
        if not cfg:
            st.error("Supabase is not configured. Add [supabase] url and anon_key to .streamlit/secrets.toml (or Streamlit Cloud Secrets), then restart the app.")
            st.stop()
        if create_client is None:
            st.error("Supabase Python package is unavailable. Install requirements.txt and restart the app.")
            st.stop()
        try:
            st.session_state.be = Live(*cfg)
        except Exception as e:
            st.error("Could not connect to Supabase: " + clean_err(e))
            st.stop()
    return st.session_state.be


# ----------------------------------------------------------------------------- UI pieces
def notice():
    st.markdown(f'<div class="notice">ℹ️ <b>Student-built platform.</b> {html.escape(NOTICE)}</div>',
                unsafe_allow_html=True)


def mask_register(value):
    value = str(value or "")
    return ("••••" + value[-4:]) if len(value) > 4 else "••••"


def photo_src(it):
    return it.get("photo_url") or it.get("photo_bytes")


def item_card(it, prefix):
    with st.container(border=True):
        src = photo_src(it)
        if src:
            st.image(src)
        st.markdown(badge(it["type"].upper(), it["type"]) + badge(it["status"], it["status"]), unsafe_allow_html=True)
        st.markdown(f"**{html.escape(it['title'])}**")
        reporter = it.get("profiles_public") or {}
        st.markdown(f'<div class="meta">📍 {esc(it["location"])} · 🗓 {esc(str(it["event_date"])[:10])}<br>'
                    f'🏷 {esc(it["category"])}<br>👤 {esc(reporter.get("full_name", "Student"))} · {esc(reporter.get("department", "Department not set"))} · Register No: {esc(mask_register(reporter.get("register_number_masked")))}</div>', unsafe_allow_html=True)
        d = it["description"]
        st.markdown(f'<div class="meta">{esc(d[:110] + ("…" if len(d) > 110 else ""))}</div>', unsafe_allow_html=True)
        st.button("View details", key=f"{prefix}-{it['id']}", on_click=go, args=("detail", it["id"]))


def grid(items, prefix):
    if not items:
        st.info("No reports found.")
    for i in range(0, len(items), 2):
        for col, it in zip(st.columns(2), items[i:i + 2]):
            with col:
                item_card(it, prefix)


# ----------------------------------------------------------------------------- pages
def page_auth(be):
    st.markdown('<div class="hero"><h1>🧭 SRM Lost & Found</h1><p>Trichy Campus · A smarter, safer way to reunite students with their belongings</p></div>',
                unsafe_allow_html=True)
    t1, t2 = st.tabs(["Log in", "Register"])
    with t1:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            sub = st.form_submit_button("Log in", type="primary")
        if sub:
            ok, _ = attempt(be.sign_in, email.strip().lower(), pw)
            if ok:
                go("home")
                st.rerun()
    with t2:
        doms = allowed_domains()
        if doms:
            st.caption("Registration is limited to: " + ", ".join("@" + d for d in doms))
        with st.form("register"):
            name = st.text_input("Full name")
            register_number = st.text_input("Register number", max_chars=30, key="reg_number", placeholder="Enter your official register number")
            department = st.selectbox("Department", ["Select department", "CSE", "IT", "ECE", "EEE", "Mechanical", "Civil", "Biotechnology", "Chemical", "Other"])
            email = st.text_input("Email", key="reg_email")
            pw = st.text_input("Password (min 8 characters, letters + a number)", type="password", key="reg_pw")
            pw2 = st.text_input("Confirm password", type="password")
            agree = st.checkbox("I have read the Safety Guidelines and understand this is an unofficial student-built platform.")
            sub = st.form_submit_button("Create account", type="primary")
        if sub:
            email = email.strip().lower()
            errs = []
            if len(name.strip()) < 2:
                errs.append("Enter your full name.")
            if not re.fullmatch(r"[A-Za-z0-9/-]{4,30}", register_number.strip()):
                errs.append("Enter a valid register number (4–30 letters, numbers, / or -).")
            if department == "Select department":
                errs.append("Select your department.")
            if not EMAIL_RE.match(email):
                errs.append("Enter a valid email address.")
            elif doms and email.split("@")[1] not in doms:
                errs.append("Please use your campus email address.")
            if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
                errs.append("Password needs 8+ characters with letters and a number.")
            if pw != pw2:
                errs.append("Passwords don't match.")
            if not agree:
                errs.append("Please accept the safety notice.")
            for e in errs:
                st.error(e)
            if not errs:
                ok, logged_in = attempt(be.sign_up, email, pw, name.strip(), register_number.strip().upper(), department)
                if ok and logged_in:
                    go("home")
                    st.rerun()
                elif ok:
                    st.success("Account created. Check your email to confirm it, then log in.")


def page_home(be):
    st.markdown(f'<div class="hero"><h1>Hi, {html.escape(be.profile["full_name"].split()[0])} 👋</h1>'
                '<p>Your campus recovery hub · Report, discover and reconnect.</p></div>', unsafe_allow_html=True)
    ok, s = attempt(be.stats)
    lost, found, res = s if ok else (0, 0, 0)
    st.markdown(f'<div class="stats"><div class="stat"><b>{lost}</b><span>Lost items</span></div>'
                f'<div class="stat"><b>{found}</b><span>Found items</span></div>'
                f'<div class="stat"><b>{res}</b><span>Resolved</span></div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.button("📢 I lost something", on_click=go, args=("lost",), type="primary")
    c2.button("📦 I found something", on_click=go, args=("found",), type="primary")
    st.subheader("Latest reports")
    ok, items = attempt(be.list_items, {"status": "open"}, 6)
    grid(items or [], "home")


def page_report(be, kind):
    st.subheader("📢 Report a lost item" if kind == "lost" else "📦 Report a found item")
    st.info("🛡️ Don't include ID/register numbers, phone numbers, passwords, OTPs or card numbers — in text or photos.")
    with st.form(f"report_{kind}", clear_on_submit=False):
        title = st.text_input("Item name", max_chars=80, placeholder="e.g. Black Boat earphones case")
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", CATEGORIES)
        loc = c2.selectbox("Campus location", LOCATIONS)
        when = st.date_input("Date " + ("lost" if kind == "lost" else "found"), value=date.today(), max_value=date.today())
        desc = st.text_area("Description", max_chars=1000, height=120,
                            placeholder="Colour, brand, marks, where exactly… (keep one detail private for verification)")
        photo = st.file_uploader("Photo (optional, max 5 MB)", type=["jpg", "jpeg", "png", "webp"])
        sub = st.form_submit_button("Submit report", type="primary")
    if not sub:
        return
    errs = []
    if len(title.strip()) < 3:
        errs.append("Item name must be at least 3 characters.")
    if len(desc.strip()) < 10:
        errs.append("Description must be at least 10 characters.")
    bad = find_sensitive(title, desc)
    if bad:
        errs.append("Your text seems to contain " + ", ".join(bad) + ". Please remove it for your safety.")
    data = None
    if photo and not errs:
        try:
            data = process_photo(photo)
        except Exception as e:
            errs.append(f"Photo problem: {clean_err(e) if isinstance(e, ValueError) else 'not a valid image.'}")
    for e in errs:
        st.error(e)
    if errs:
        return
    d = {"type": kind, "title": title.strip(), "category": cat, "location": loc,
         "description": desc.strip(), "event_date": when.isoformat()}
    ok, it = attempt(be.create_item, d, data)
    if ok:
        st.success("Report submitted!")
        go("detail", it["id"])
        st.rerun()


def page_browse(be):
    st.subheader("🔎 Browse reports")
    q = st.text_input("Search", placeholder="Search item name or description…", label_visibility="collapsed")
    with st.expander("Filters"):
        kind = st.radio("Type", ["All", "Lost", "Found"], horizontal=True)
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", ["All"] + CATEGORIES)
        loc = c2.selectbox("Location", ["All"] + LOCATIONS)
        d1 = c1.date_input("From date", value=None)
        d2 = c2.date_input("To date", value=None)
        stat = st.radio("Status", ["Open", "Resolved", "All"], horizontal=True)
    f = {"q": q, "type": None if kind == "All" else kind.lower(),
         "category": None if cat == "All" else cat, "location": None if loc == "All" else loc,
         "status": None if stat == "All" else stat.lower(), "date_from": d1, "date_to": d2}
    ok, items = attempt(be.list_items, f)
    if ok:
        st.caption(f"{len(items)} result(s)")
        grid(items, "browse")


def page_detail(be):
    iid = st.session_state.get("item_id")
    st.button("← Back", on_click=go, args=("browse",))
    ok, it = attempt(be.get_item, iid)
    if not ok:
        return
    if not it:
        st.warning("This report doesn't exist or is no longer available.")
        return
    mine = it["reporter_id"] == be.uid
    src = photo_src(it)
    if src:
        st.image(src)
    st.markdown(badge(it["type"].upper(), it["type"]) + badge(it["status"], it["status"]), unsafe_allow_html=True)
    st.header(it["title"])
    reporter = it.get("profiles_public") or {}
    who = reporter.get("full_name", "A student")
    st.markdown(f'<div class="meta">📍 {esc(it["location"])} · 🗓 {esc(str(it["event_date"])[:10])} · '
                f'🏷 {esc(it["category"])}<br>Reported by {esc(who)} · {esc(reporter.get("department", "Department not set"))} · '
                f'Register No: {esc(mask_register(reporter.get("register_number_masked")))} · {esc(str(it["created_at"])[:10])}</div>',
                unsafe_allow_html=True)
    st.markdown(f"<div>{esc(it['description'])}</div>", unsafe_allow_html=True)
    st.divider()

    # Basic Smart Matching: compare this report with open reports of the opposite type.
    st.subheader("✨ Possible matches")
    st.caption("Basic Smart Matching compares item names, descriptions, category and campus location. Suggestions are not proof of ownership.")
    opposite = "found" if it["type"] == "lost" else "lost"
    ok_matches, candidates = attempt(be.list_items, {"type": opposite, "status": "open", "category": it["category"]}, 60)
    if ok_matches:
        ranked = sorted(
            [(basic_match_score(it, other), other) for other in (candidates or []) if other["id"] != it["id"]],
            key=lambda pair: pair[0], reverse=True
        )
        ranked = [(score, other) for score, other in ranked if score >= 20][:3]
        if ranked:
            for score, other in ranked:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if photo_src(other): st.image(photo_src(other), use_container_width=True)
                    with c2:
                        st.markdown(f"**{esc(other['title'])}**")
                        st.markdown(f"<div class='meta'>{esc(other['location'])} · {esc(other['category'])} · {esc(str(other['event_date'])[:10])}</div>", unsafe_allow_html=True)
                        st.progress(score / 100, text=f"{score}% similarity · review manually")
                        st.button("View suggested match", key=f"smart-match-{it['id']}-{other['id']}", on_click=go, args=("detail", other["id"]))
        else:
            st.info("No close suggestions yet. New matching reports may appear here later.")

    if mine:
        owner_panel(be, it)
    else:
        claim_panel(be, it)
        with st.expander("🚩 Report inappropriate content"):
            reason = st.text_input("Why is this report inappropriate?", key="flag_reason", max_chars=300)
            if st.button("Send to moderators"):
                if len(reason.strip()) < 5:
                    st.error("Please add a short reason.")
                else:
                    ok, _ = attempt(be.flag_item, it["id"], reason.strip())
                    if ok:
                        st.success("Thanks — moderators will review it.")
    if be.is_admin:
        st.markdown("**🛠️ Admin**")
        if it["status"] == "removed":
            st.button("Restore report", on_click=lambda: be.update_item(it["id"], {"status": "open"}))
        else:
            st.button("Remove report (moderation)", on_click=lambda: be.update_item(it["id"], {"status": "removed"}))


def owner_panel(be, it):
    st.markdown("**Manage your report**")
    c1, c2 = st.columns(2)
    if it["status"] == "open":
        if c1.button("✅ Mark as resolved"):
            if attempt(be.update_item, it["id"], {"status": "resolved"})[0]:
                st.rerun()
    elif it["status"] == "resolved":
        if c1.button("↩️ Reopen"):
            if attempt(be.update_item, it["id"], {"status": "open"})[0]:
                st.rerun()
    with st.expander("✏️ Edit report"):
        with st.form("edit"):
            t = st.text_input("Item name", it["title"], max_chars=80)
            d = st.text_area("Description", it["description"], max_chars=1000)
            cat = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(it["category"]) if it["category"] in CATEGORIES else 0)
            loc = st.selectbox("Location", LOCATIONS, index=LOCATIONS.index(it["location"]) if it["location"] in LOCATIONS else 0)
            sub = st.form_submit_button("Save changes", type="primary")
        if sub:
            bad = find_sensitive(t, d)
            if len(t.strip()) < 3 or len(d.strip()) < 10:
                st.error("Name needs 3+ and description 10+ characters.")
            elif bad:
                st.error("Please remove " + ", ".join(bad) + ".")
            elif attempt(be.update_item, it["id"], {"title": t.strip(), "description": d.strip(),
                                                    "category": cat, "location": loc})[0]:
                st.rerun()
    with st.expander("🗑 Delete report"):
        sure = st.checkbox("I understand this permanently deletes the report and its claims.")
        if st.button("Delete permanently", disabled=not sure):
            if attempt(be.delete_item, it["id"])[0]:
                go("mine")
                st.rerun()

    st.markdown("**Claim requests**")
    ok, claims = attempt(be.claims_for_item, it["id"])
    if ok and not claims:
        st.caption("No claim requests yet.")
    for c in claims or []:
        with st.container(border=True):
            st.markdown(f"**{html.escape((c.get('profiles_public') or {}).get('full_name', 'Student'))}** · "
                        f"{badge(c['status'], 'open' if c['status'] == 'pending' else ('found' if c['status'] == 'approved' else 'lost'))}",
                        unsafe_allow_html=True)
            st.markdown(f"<div class='meta'>{esc(c['message'])}</div>", unsafe_allow_html=True)
            if c["status"] == "pending":
                note = st.text_input("Note for claimant (e.g. 'Meet at the Library desk, 5 pm')",
                                     key=f"note-{c['id']}", max_chars=300)
                a, b = st.columns(2)
                bad = find_sensitive(note)
                if a.button("Approve", key=f"ap-{c['id']}", type="primary"):
                    if bad:
                        st.error("Remove " + ", ".join(bad) + " from the note.")
                    elif attempt(be.respond_claim, c["id"], "approved", note.strip())[0]:
                        st.rerun()
                if b.button("Reject", key=f"rj-{c['id']}"):
                    if attempt(be.respond_claim, c["id"], "rejected", note.strip())[0]:
                        st.rerun()


def claim_panel(be, it):
    ok, claims = attempt(be.claims_for_item, it["id"])
    mine = [c for c in (claims or []) if c["claimant_id"] == be.uid]
    verb = "This is mine" if it["type"] == "found" else "I found this item"
    if mine:
        c = mine[0]
        st.markdown(f"**Your claim request:** {badge(c['status'], 'open' if c['status'] == 'pending' else ('found' if c['status'] == 'approved' else 'lost'))}",
                    unsafe_allow_html=True)
        if c["status"] == "approved" and c.get("owner_note"):
            st.success("Message from the reporter: " + c["owner_note"])
        return
    if it["status"] != "open":
        st.caption("This report is no longer open for claims.")
        return
    st.markdown(f"**{verb}?** Send a claim request. Contact details are never shown publicly.")
    with st.form("claim"):
        msg = st.text_area("Proof / details only the real owner would know",
                           max_chars=500, placeholder="e.g. wallpaper, scratch on the left corner, what's inside…")
        sub = st.form_submit_button("Send claim request", type="primary")
    if sub:
        bad = find_sensitive(msg)
        if len(msg.strip()) < 10:
            st.error("Please give at least 10 characters of detail.")
        elif bad:
            st.error("Please remove " + ", ".join(bad) + ". Don't share private numbers.")
        elif attempt(be.create_claim, it["id"], msg.strip())[0]:
            st.success("Claim request sent. You'll get a notification when the reporter responds.")
            st.rerun()
    st.caption("Tip: hand over items at a public campus spot such as the security desk or library.")


def page_mine(be):
    st.subheader("📁 My reports")
    t1, t2, t3 = st.tabs(["Active", "Resolved", "My claims"])
    ok, items = attempt(be.my_items)
    items = items or []
    with t1:
        grid([i for i in items if i["status"] == "open"], "mine-open")
    with t2:
        grid([i for i in items if i["status"] == "resolved"], "mine-res")
    with t3:
        ok, claims = attempt(be.my_claims)
        if ok and not claims:
            st.info("You haven't sent any claim requests.")
        for c in claims or []:
            it = c.get("items") or {}
            with st.container(border=True):
                st.markdown(f"**{html.escape(it.get('title', 'Item'))}** · "
                            f"{badge(c['status'], 'open' if c['status'] == 'pending' else ('found' if c['status'] == 'approved' else 'lost'))}",
                            unsafe_allow_html=True)
                if c["status"] == "approved" and c.get("owner_note"):
                    st.success(c["owner_note"])
                if it.get("id"):
                    st.button("Open", key=f"mc-{c['id']}", on_click=go, args=("detail", it["id"]))


def page_notes(be):
    st.subheader("🔔 Notifications")
    ok, notes = attempt(be.notifications)
    if ok and not notes:
        st.info("No notifications yet.")
    for n in notes or []:
        with st.container(border=True):
            st.markdown(("🔵 " if not n["is_read"] else "") + f"**{html.escape(n['title'])}**")
            st.markdown(f"<div class='meta'>{esc(n.get('body'))}<br>{esc(str(n['created_at'])[:16].replace('T', ' '))}</div>",
                        unsafe_allow_html=True)
            if n.get("item_id"):
                st.button("View item", key=f"n-{n['id']}", on_click=go, args=("detail", n["item_id"]))
    if notes and any(not n["is_read"] for n in notes):
        if st.button("Mark all as read"):
            if attempt(be.mark_read)[0]:
                st.rerun()


def page_admin(be):
    st.subheader("🛠️ Admin dashboard")
    if not be.is_admin:
        st.error("Admins only.")
        return
    t1, t2 = st.tabs(["Flagged reports", "All reports"])
    with t1:
        ok, flags = attempt(be.flags)
        if ok and not flags:
            st.success("No open flags.")
        for f in flags or []:
            it = f.get("items") or {}
            with st.container(border=True):
                st.markdown(f"**{html.escape(it.get('title', 'Item'))}** · {badge(it.get('status', ''), it.get('status', 'open'))}",
                            unsafe_allow_html=True)
                st.markdown(f"<div class='meta'>Reason: {esc(f['reason'])}</div>", unsafe_allow_html=True)
                a, b, c = st.columns(3)
                a.button("View", key=f"fv-{f['id']}", on_click=go, args=("detail", f["item_id"]))
                if b.button("Remove", key=f"fr-{f['id']}", type="primary"):
                    if attempt(be.update_item, f["item_id"], {"status": "removed"})[0] and attempt(be.resolve_flag, f["id"])[0]:
                        st.rerun()
                if c.button("Dismiss", key=f"fd-{f['id']}"):
                    if attempt(be.resolve_flag, f["id"])[0]:
                        st.rerun()
    with t2:
        ok, items = attempt(be.all_items)
        for it in items or []:
            with st.container(border=True):
                st.markdown(badge(it["type"].upper(), it["type"]) + badge(it["status"], it["status"]) +
                            f" **{html.escape(it['title'])}**", unsafe_allow_html=True)
                a, b = st.columns(2)
                a.button("View", key=f"av-{it['id']}", on_click=go, args=("detail", it["id"]))
                if it["status"] == "removed":
                    if b.button("Restore", key=f"ars-{it['id']}") and attempt(be.update_item, it["id"], {"status": "open"})[0]:
                        st.rerun()
                elif b.button("Remove", key=f"arm-{it['id']}") and attempt(be.update_item, it["id"], {"status": "removed"})[0]:
                    st.rerun()


def make_student_qr(code: str) -> bytes:
    """Create a QR containing only the public random student code, never email/phone."""
    img = qrcode.make(f"SRM-LOST-FOUND:STUDENT:{code}")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def page_profile(be):
    st.subheader("👤 My student profile")
    profile = be.profile or {}
    code = profile.get("student_code")
    if not code:
        st.warning("Student QR code is not available yet. Run the updated Supabase SQL schema, then log out and log in.")
        return
    st.write(f"**Name:** {profile.get('full_name', 'Student')}")
    st.write(f"**Register number:** {profile.get('register_number', 'Not set')}")
    st.write(f"**Department:** {profile.get('department', 'Not set')}")
    st.write(f"**Student code:** `{code}`")
    qr = make_student_qr(code)
    st.image(qr, caption="Your private campus app QR code", width=230)
    st.download_button("⬇️ Download my QR code", data=qr, file_name=f"{code}.png", mime="image/png")
    st.caption("QR contains only your random app student code. It does not contain your email, phone number or register number.")


def page_chat(be):
    st.subheader("💬 Student-to-student chat")
    st.caption("Use a student's app code to start a private one-to-one conversation.")
    with st.form("find_student_form"):
        code = st.text_input("Enter student code", placeholder="e.g. STU-1A2B3C4D", max_chars=20)
        find = st.form_submit_button("Find student", type="primary")
    if find:
        if not re.fullmatch(r"STU-[A-F0-9]{8}", code.strip().upper()):
            st.error("Enter a valid student code.")
        else:
            ok, student = attempt(be.find_student, code.strip().upper())
            if ok and student:
                if student["id"] == be.uid:
                    st.info("This is your own profile.")
                else:
                    st.session_state.chat_peer = student["id"]
                    st.session_state.chat_peer_name = student["full_name"]
                    st.rerun()
            elif ok:
                st.warning("No student found with that code.")

    ok, inbox = attempt(be.chat_inbox)
    inbox = inbox or []
    if inbox:
        st.markdown("**Your conversations**")
        for peer in inbox:
            if st.button(f"💬 {peer['full_name']} · {peer.get('student_code', '')}",
                         key=f"chat-open-{peer['id']}"):
                st.session_state.chat_peer = peer["id"]
                st.session_state.chat_peer_name = peer["full_name"]
                st.rerun()

    peer_id = st.session_state.get("chat_peer")
    if not peer_id:
        st.info("Find a student by their app code or open an existing conversation.")
        return
    peer_name = st.session_state.get("chat_peer_name", "Student")
    st.divider()
    st.markdown(f"### Chat with {html.escape(peer_name)}")
    ok, messages = attempt(be.chat_messages, peer_id)
    if ok:
        for m in messages or []:
            own = m["sender_id"] == be.uid
            st.chat_message("user" if own else "assistant").write(m["message"])
            st.caption(("You" if own else peer_name) + " · " + str(m.get("created_at", ""))[:16].replace("T", " "))
    with st.form("send_direct_message", clear_on_submit=True):
        message = st.text_area("Message", max_chars=1000, placeholder="Write a respectful message…")
        send = st.form_submit_button("Send message", type="primary")
    if send:
        bad = find_sensitive(message)
        if len(message.strip()) < 1:
            st.error("Type a message first.")
        elif bad:
            st.error("Please remove " + ", ".join(bad) + ". Do not share private contact details or numbers.")
        elif attempt(be.send_message, peer_id, message.strip())[0]:
            st.rerun()
    st.caption("Keep chats respectful. Do not share passwords, OTPs, phone numbers, home addresses or financial details.")


def page_safety(be=None):
    st.subheader("🛡️ Safety guidelines")
    st.markdown("""
**Never post or send:**
- Register numbers, Aadhaar, PAN, library or ID card numbers
- Passwords, PINs, OTPs, CVV or card/bank details
- Phone numbers, personal emails or home addresses
- Photos where any of the above are readable (blur or cover them)

**Stay safe:**
- Keep one identifying detail private; ask claimants to describe it.
- Hand over items in public campus places (security desk, library, main gate).
- Never pay or transfer money to get an item back.
- Report suspicious or inappropriate posts with the 🚩 button.
- Lost a phone, wallet or ID card? Also inform campus security / the concerned office.

Posts that break these rules are removed by moderators. The app also blocks text that looks like private numbers or passwords.
""")


def page_about(be=None):
    st.subheader("ℹ️ About")
    st.markdown(f"**{APP}** helps students reunite lost items with their owners.\n\n> {NOTICE}")
    st.caption("Connected backend: Supabase (authentication, database and storage).")


PAGES_USER = {"home": ("🏠 Dashboard", page_home), "browse": ("🔎 Browse", page_browse),
              "lost": ("📢 Report Lost", lambda be: page_report(be, "lost")),
              "found": ("📦 Report Found", lambda be: page_report(be, "found")),
              "mine": ("📁 My Reports", page_mine), "notes": ("🔔 Notifications", page_notes),
              "profile": ("👤 My QR Profile", page_profile), "chat": ("💬 Student Chat", page_chat),
              "safety": ("🛡️ Safety", page_safety), "about": ("ℹ️ About", page_about)}


def sidebar(be):
    with st.sidebar:
        st.markdown("### 🧭 SRM Lost & Found")
        st.caption("Trichy Campus · student-built")
        if not be.user:
            st.button("🔑 Log in / Register", on_click=go, args=("auth",), key="s-auth")
            st.button("🛡️ Safety", on_click=go, args=("safety",), key="s-safe")
            st.button("ℹ️ About", on_click=go, args=("about",), key="s-about")
            return
        st.caption(f"Signed in as **{be.profile['full_name']}**")
        ok, n = attempt(be.unread)
        for key, (label, _) in PAGES_USER.items():
            if key == "notes" and ok and n:
                label += f" ({n})"
            st.button(label, key=f"s-{key}", on_click=go, args=(key,),
                      type="primary" if st.session_state.page == key else "secondary")
        if be.is_admin:
            st.button("🛠️ Admin", key="s-admin", on_click=go, args=("admin",),
                      type="primary" if st.session_state.page == "admin" else "secondary")
        if st.button("Log out", key="s-out"):
            be.sign_out()
            go("auth")
            st.rerun()


def main():
    be = backend()
    st.session_state.setdefault("page", "auth")
    sidebar(be)
    page = st.session_state.page
    if not be.user and page not in ("safety", "about"):
        page = "auth"
    if page == "auth":
        page_auth(be)
    elif page == "detail":
        page_detail(be)
    elif page == "admin":
        page_admin(be)
    else:
        PAGES_USER.get(page, PAGES_USER["home"])[1](be)
    notice()


main()
