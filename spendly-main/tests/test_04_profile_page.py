"""
Tests for Step 4: Profile Page
Spec: .claude/specs/04-profile-page.md

Covers the spec's definition of done plus the design polish:
- GET /profile auth guard (unauthenticated → 302 /login)
- GET /profile authenticated → 200
- User info card (name + email), summary stat labels
- Transaction table rows and category breakdown bars
- Category empty state when the user has no expenses
- Navbar logged-in state (username + Sign out)
- Template hygiene: no hex colours, no inline styles, Lucide icons present
"""

import pathlib
import re

import pytest

import database.db as db_module
from app import app as flask_app
from database.db import init_db
from database.queries import insert_expense


TEMPLATE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "templates" / "profile.html"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Return the path to a fresh, isolated SQLite database file."""
    return str(tmp_path / "test_spendly.db")


@pytest.fixture
def app(db_path, monkeypatch):
    """Flask app configured for testing with an isolated SQLite DB."""
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with flask_app.app_context():
        init_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(client):
    """Register a fresh test user and return (user_id, email, password)."""
    email = "testuser@example.com"
    password = "testpass123"
    client.post(
        "/register",
        data={
            "name": "Test User",
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"], email, password


@pytest.fixture
def auth_client(client, registered_user):
    """A test client with a valid session already injected."""
    user_id, _email, _password = registered_user
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Test User"
    return client


@pytest.fixture
def seeded_expenses(registered_user):
    """Insert three expenses in three different categories."""
    user_id = registered_user[0]
    return [
        insert_expense(user_id, 250.0, "Food", "2026-04-02", "Lunch"),
        insert_expense(user_id, 120.0, "Transport", "2026-04-05", "Metro card"),
        insert_expense(user_id, 900.0, "Bills", "2026-04-10", "Electricity"),
    ]


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_returns_200_when_logged_in(auth_client):
    assert auth_client.get("/profile").status_code == 200


# ---------------------------------------------------------------------------
# Page sections
# ---------------------------------------------------------------------------

def test_user_info_card_shows_name_and_email(auth_client, registered_user):
    html = auth_client.get("/profile").get_data(as_text=True)
    assert 'class="profile-name">Test User<' in html
    assert registered_user[1] in html


def test_summary_stat_labels_present(auth_client):
    html = auth_client.get("/profile").get_data(as_text=True)
    for label in ("Total Spent", "Transactions", "Top Category"):
        assert label in html


def test_transaction_table_lists_rows(auth_client, seeded_expenses):
    html = auth_client.get("/profile").get_data(as_text=True)
    for expense_id in seeded_expenses:
        assert f'action="/expenses/{expense_id}/delete"' in html
    for description in ("Lunch", "Metro card", "Electricity"):
        assert description in html


def test_category_breakdown_renders_progress_bars(auth_client, seeded_expenses):
    html = auth_client.get("/profile").get_data(as_text=True)
    assert "By Category" in html
    assert html.count("<progress") >= 3
    for category in ("food", "transport", "bills"):
        assert f"cat-bar--{category}" in html


def test_category_empty_state_without_expenses(auth_client):
    html = auth_client.get("/profile").get_data(as_text=True)
    assert "No spending in this period." in html
    assert "<progress" not in html


# ---------------------------------------------------------------------------
# Navbar
# ---------------------------------------------------------------------------

def test_navbar_shows_username_and_sign_out(auth_client):
    html = auth_client.get("/profile").get_data(as_text=True)
    assert re.search(r'class="nav-username">\s*Test User\s*<', html)
    assert 'href="/logout"' in html


@pytest.mark.parametrize("path", ["/", "/login", "/register"])
def test_logged_in_user_redirected_to_profile(auth_client, path):
    response = auth_client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_logout_then_landing_renders(auth_client):
    auth_client.get("/logout")
    response = auth_client.get("/")
    assert response.status_code == 200


def test_navbar_hides_username_when_logged_out(client):
    html = client.get("/").get_data(as_text=True)
    assert "nav-username" not in html


# ---------------------------------------------------------------------------
# Template hygiene
# ---------------------------------------------------------------------------

def test_template_has_no_hex_colours_or_inline_styles():
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", source)
    assert "style=" not in source


def test_profile_renders_lucide_icons(auth_client):
    html = auth_client.get("/profile").get_data(as_text=True)
    assert "data-lucide=" in html
