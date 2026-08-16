"""Password authentication and persistent sessions."""
import hashlib
import hmac
import re
import secrets
from http import cookies
from typing import Optional

from .database import connect, now, row_to_dict


SESSION_COOKIE = "traveler_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30


class Auth:
    """User and session management."""

    @staticmethod
    def users_count() -> int:
        with connect() as db:
            return db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]

    @staticmethod
    def register(username: str, password: str):
        username = Auth._normalize_username(username)
        Auth._validate_password(password)
        password_hash = Auth._hash_password(password)

        with connect() as db:
            try:
                cur = db.execute(
                    "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, password_hash, now()),
                )
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    raise ValueError("Пользователь с таким именем уже существует")
                raise

            user_id = cur.lastrowid
            first_user = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 1
            if first_user:
                db.execute("UPDATE trips SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
                db.execute(
                    """
                    INSERT OR IGNORE INTO trip_users(trip_id, user_id, role, created_at)
                    SELECT id, ?, 'owner', ? FROM trips WHERE owner_user_id = ?
                    """,
                    (user_id, now(), user_id),
                )

            return Auth._public_user({"id": user_id, "username": username})

    @staticmethod
    def login(username: str, password: str):
        username = Auth._normalize_username(username)

        with connect() as db:
            user = row_to_dict(
                db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            )

        if not user or not Auth._verify_password(password, user["password_hash"]):
            raise ValueError("Неверное имя пользователя или пароль")

        return Auth._public_user(user)

    @staticmethod
    def create_session(user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = Auth._hash_token(token)

        with connect() as db:
            db.execute(
                "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, datetime('now'), datetime('now', '+30 days'))",
                (token_hash, user_id),
            )

        return token

    @staticmethod
    def user_from_cookie(cookie_header: str | None) -> Optional[dict]:
        token = Auth._session_token_from_header(cookie_header)
        if not token:
            return None

        token_hash = Auth._hash_token(token)
        with connect() as db:
            session = row_to_dict(
                db.execute(
                    """
                    SELECT s.id AS session_id, u.id, u.username
                    FROM sessions s
                    JOIN users u ON u.id = s.user_id
                    WHERE s.token_hash = ? AND s.expires_at > datetime('now')
                    """,
                    (token_hash,),
                ).fetchone()
            )

        if not session:
            return None

        return Auth._public_user(session)

    @staticmethod
    def logout(cookie_header: str | None):
        token = Auth._session_token_from_header(cookie_header)
        if not token:
            return

        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (Auth._hash_token(token),))

    @staticmethod
    def session_cookie(token: str) -> str:
        return (
            f"{SESSION_COOKIE}={token}; Max-Age={SESSION_TTL_SECONDS}; "
            "Path=/; HttpOnly; SameSite=Lax"
        )

    @staticmethod
    def clear_cookie() -> str:
        return f"{SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax"

    @staticmethod
    def _normalize_username(username: str) -> str:
        username = str(username or "").strip().lower()
        if not re.match(r"^[\w.-]{3,32}$", username, re.UNICODE):
            raise ValueError("Имя пользователя: 3-32 символа, буквы, цифры, точка, _ или -")
        return username

    @staticmethod
    def _validate_password(password: str):
        if len(str(password or "")) < 6:
            raise ValueError("Пароль должен быть не короче 6 символов")

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
        return f"pbkdf2_sha256$200000${salt}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        try:
            algorithm, iterations, salt, expected = stored_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(digest, expected)
        except Exception:
            return False

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _session_token_from_header(cookie_header: str | None) -> str | None:
        if not cookie_header:
            return None
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    @staticmethod
    def _public_user(user: dict) -> dict:
        return {"id": user["id"], "username": user["username"]}
