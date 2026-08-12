"""Foydalanuvchi tizimi testlari — plan, store, limits."""

from __future__ import annotations

import pytest

from uzlegal.users.limits import FeatureNotAllowedError, check_access, record_and_check
from uzlegal.users.models import (
    DuplicateUserError,
    QuotaExceededError,
    UserNotFoundError,
    generate_api_key,
    hash_api_key,
)
from uzlegal.users.plans import PLANS, PlanTier, get_plan, has_feature
from uzlegal.users.store import UserStore

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def store() -> UserStore:
    return UserStore(":memory:")


# ── Plans ───────────────────────────────────────────────────────────────


class TestPlans:
    def test_barcha_rejalar_mavjud(self) -> None:
        assert len(PLANS) == 4
        for tier in PlanTier:
            assert tier in PLANS

    def test_bepul_cheklovlari(self) -> None:
        plan = get_plan(PlanTier.BEPUL)
        assert plan.limits.daily_queries == 5
        assert plan.limits.monthly_queries == 100
        assert plan.features.consult is True
        assert plan.features.integrity is False
        assert plan.features.litigation is False
        assert plan.price_uzs == 0

    def test_professional_imkoniyatlari(self) -> None:
        plan = get_plan(PlanTier.PROFESSIONAL)
        assert plan.features.integrity is True
        assert plan.features.batch_api is True
        assert plan.features.stream is True
        assert plan.limits.daily_queries == 200

    def test_tashkilot_eng_katta(self) -> None:
        plan = get_plan(PlanTier.TASHKILOT)
        assert plan.limits.daily_queries == 1000
        assert plan.limits.max_batch_size == 100

    def test_has_feature(self) -> None:
        assert has_feature(PlanTier.BEPUL, "consult") is True
        assert has_feature(PlanTier.BEPUL, "integrity") is False
        assert has_feature(PlanTier.PROFESSIONAL, "integrity") is True

    def test_narx_tartibi(self) -> None:
        prices = [PLANS[t].price_uzs for t in PlanTier]
        assert prices == sorted(prices)

    def test_cheklov_tartibi(self) -> None:
        limits = [PLANS[t].limits.daily_queries for t in PlanTier]
        assert limits == sorted(limits)


# ── API Key ─────────────────────────────────────────────────────────────


class TestApiKey:
    def test_generate_format(self) -> None:
        key = generate_api_key()
        assert key.startswith("uzl_")
        assert len(key) > 20

    def test_hash_deterministic(self) -> None:
        key = "uzl_test123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_hash_unique(self) -> None:
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert hash_api_key(k1) != hash_api_key(k2)


# ── Store CRUD ──────────────────────────────────────────────────────────


class TestStoreCRUD:
    def test_create_and_get(self, store: UserStore) -> None:
        user, key = store.create_user("u1", name="Test")
        assert user.user_id == "u1"
        assert user.name == "Test"
        assert user.plan == PlanTier.BEPUL
        assert user.is_active is True
        assert key.startswith("uzl_")

        fetched = store.get_user("u1")
        assert fetched.user_id == "u1"

    def test_create_with_plan(self, store: UserStore) -> None:
        user, _ = store.create_user("u2", plan=PlanTier.PROFESSIONAL)
        assert user.plan == PlanTier.PROFESSIONAL

    def test_create_with_telegram(self, store: UserStore) -> None:
        _user, _ = store.create_user("u3", telegram_id="123456")
        fetched = store.get_by_telegram("123456")
        assert fetched.user_id == "u3"

    def test_duplicate_user(self, store: UserStore) -> None:
        store.create_user("u1")
        with pytest.raises(DuplicateUserError):
            store.create_user("u1")

    def test_duplicate_telegram(self, store: UserStore) -> None:
        store.create_user("u1", telegram_id="111")
        with pytest.raises(DuplicateUserError):
            store.create_user("u2", telegram_id="111")

    def test_user_not_found(self, store: UserStore) -> None:
        with pytest.raises(UserNotFoundError):
            store.get_user("nonexistent")

    def test_get_by_api_key(self, store: UserStore) -> None:
        _, key = store.create_user("u1")
        user = store.get_by_api_key(key)
        assert user.user_id == "u1"

    def test_invalid_api_key(self, store: UserStore) -> None:
        with pytest.raises(UserNotFoundError):
            store.get_by_api_key("uzl_wrong_key")

    def test_update_plan(self, store: UserStore) -> None:
        store.create_user("u1")
        updated = store.update_plan("u1", PlanTier.ASOSIY)
        assert updated.plan == PlanTier.ASOSIY

    def test_deactivate(self, store: UserStore) -> None:
        _, key = store.create_user("u1")
        store.deactivate("u1")
        user = store.get_user("u1")
        assert user.is_active is False
        with pytest.raises(UserNotFoundError):
            store.get_by_api_key(key)

    def test_regenerate_key(self, store: UserStore) -> None:
        _, old_key = store.create_user("u1")
        new_key = store.regenerate_key("u1")
        assert new_key != old_key
        assert new_key.startswith("uzl_")
        user = store.get_by_api_key(new_key)
        assert user.user_id == "u1"
        with pytest.raises(UserNotFoundError):
            store.get_by_api_key(old_key)

    def test_list_users(self, store: UserStore) -> None:
        store.create_user("u1")
        store.create_user("u2")
        store.create_user("u3")
        store.deactivate("u2")

        active = store.list_users(active_only=True)
        assert len(active) == 2

        all_users = store.list_users(active_only=False)
        assert len(all_users) == 3


# ── Usage Tracking ──────────────────────────────────────────────────────


class TestUsage:
    def test_record_and_count(self, store: UserStore) -> None:
        store.create_user("u1")
        store.record_usage("u1", "consult")
        store.record_usage("u1", "consult")
        store.record_usage("u1", "court_analyze")

        assert store.daily_usage("u1") == 3

    def test_monthly_usage(self, store: UserStore) -> None:
        store.create_user("u1")
        store.record_usage("u1", "consult")
        store.record_usage("u1", "consult")

        assert store.monthly_usage("u1") >= 2

    def test_usage_summary(self, store: UserStore) -> None:
        store.create_user("u1")
        store.record_usage("u1", "consult")

        summary = store.usage_summary("u1")
        assert summary.today_used == 1
        assert summary.today_limit == 5
        assert summary.remaining_today == 4
        assert summary.plan == PlanTier.BEPUL

    def test_zero_usage(self, store: UserStore) -> None:
        store.create_user("u1")
        assert store.daily_usage("u1") == 0
        assert store.monthly_usage("u1") == 0

    def test_usage_different_dates(self, store: UserStore) -> None:
        store.create_user("u1")
        store._conn.execute(
            "INSERT INTO usage (user_id, date, endpoint, count) VALUES (?, ?, ?, ?)",
            ("u1", "2025-01-01", "consult", 10),
        )
        store._conn.execute(
            "INSERT INTO usage (user_id, date, endpoint, count) VALUES (?, ?, ?, ?)",
            ("u1", "2025-01-02", "consult", 5),
        )
        store._conn.commit()

        assert store.daily_usage("u1", "2025-01-01") == 10
        assert store.daily_usage("u1", "2025-01-02") == 5
        assert store.monthly_usage("u1", "2025-01") == 15


# ── Limits ──────────────────────────────────────────────────────────────


class TestLimits:
    def test_check_access_ok(self, store: UserStore) -> None:
        store.create_user("u1")
        check_access(store, "u1", "consult")

    def test_feature_not_allowed(self, store: UserStore) -> None:
        store.create_user("u1", plan=PlanTier.BEPUL)
        with pytest.raises(FeatureNotAllowedError):
            check_access(store, "u1", "integrity_check")

    def test_feature_allowed_with_plan(self, store: UserStore) -> None:
        store.create_user("u1", plan=PlanTier.PROFESSIONAL)
        check_access(store, "u1", "integrity_check")

    def test_daily_quota_exceeded(self, store: UserStore) -> None:
        store.create_user("u1", plan=PlanTier.BEPUL)
        for _ in range(5):
            store.record_usage("u1", "consult")

        with pytest.raises(QuotaExceededError) as exc_info:
            check_access(store, "u1", "consult")
        assert exc_info.value.period == "kunlik"

    def test_monthly_quota_exceeded(self, store: UserStore) -> None:
        from datetime import datetime, timedelta

        from uzlegal.users.models import today_str

        store.create_user("u1", plan=PlanTier.BEPUL)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if yesterday[:7] != today_str()[:7]:
            pytest.skip("Oyning 1-kuni — kechagi oy boshqa")
        store._conn.execute(
            "INSERT INTO usage (user_id, date, endpoint, count) VALUES (?, ?, ?, ?)",
            ("u1", yesterday, "consult", 100),
        )
        store._conn.commit()

        with pytest.raises(QuotaExceededError) as exc_info:
            check_access(store, "u1", "consult")
        assert exc_info.value.period == "oylik"

    def test_record_and_check(self, store: UserStore) -> None:
        store.create_user("u1")
        record_and_check(store, "u1", "consult")
        assert store.daily_usage("u1") == 1

    def test_record_and_check_blocks_at_limit(self, store: UserStore) -> None:
        store.create_user("u1", plan=PlanTier.BEPUL)
        for _ in range(5):
            store.record_usage("u1", "consult")

        with pytest.raises(QuotaExceededError):
            record_and_check(store, "u1", "consult")
        assert store.daily_usage("u1") == 5

    def test_unknown_endpoint_passes(self, store: UserStore) -> None:
        store.create_user("u1")
        check_access(store, "u1", "health")

    def test_higher_plan_higher_limit(self, store: UserStore) -> None:
        store.create_user("u1", plan=PlanTier.PROFESSIONAL)
        for _ in range(50):
            store.record_usage("u1", "consult")
        check_access(store, "u1", "consult")


# ── Edge cases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_close_and_reopen(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name

        store1 = UserStore(path)
        store1.create_user("u1", name="Persistent")
        store1.close()

        store2 = UserStore(path)
        user = store2.get_user("u1")
        assert user.name == "Persistent"
        store2.close()

        import os

        os.unlink(path)

    def test_plan_upgrade_resets_access(self, store: UserStore) -> None:
        store.create_user("u1", plan=PlanTier.BEPUL)
        with pytest.raises(FeatureNotAllowedError):
            check_access(store, "u1", "integrity_check")

        store.update_plan("u1", PlanTier.PROFESSIONAL)
        check_access(store, "u1", "integrity_check")

    def test_deactivated_user_no_api_access(self, store: UserStore) -> None:
        _, key = store.create_user("u1")
        store.deactivate("u1")
        with pytest.raises(UserNotFoundError):
            store.get_by_api_key(key)
