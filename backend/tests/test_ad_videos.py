"""Ad videos. Claude is replaced by a fixed storyboard: no network, no cost."""

import pytest

from app.services import ad_videos
from app.services.ad_videos import AdBuildError, Scene, Storyboard, tidy
from tests.conftest import make_settings


def scene(kind, duration=3.0, **fields):
    base = dict(
        kind=kind,
        duration=duration,
        headline=f"{kind} headline",
        subline="",
        items=[],
        price_amount="",
        price_currency="",
        price_period="",
    )
    return Scene(**{**base, **fields})


STORY = Storyboard(
    title="Growth package ad",
    palette="sunset",
    brand="Amman Social",
    scenes=[
        scene("hook", headline="Your feed, finally working"),
        scene("list", items=["20 posts", "8 reels", "Ad management"]),
        scene(
            "price",
            headline="Starting at",
            price_amount="450",
            price_currency="JOD",
            price_period="/month",
        ),
        scene("cta", headline="Book a free call", subline="30-minute consultation"),
    ],
    facts_used=["Growth: 450 JOD per month, 20 posts, 8 reels, ad management"],
)


@pytest.fixture
def writer(monkeypatch):
    calls = []

    def fake(knowledge_text, business, brief, *, config):
        calls.append({"knowledge": knowledge_text, "business": business, "brief": brief})
        return STORY, 4000, 600

    monkeypatch.setattr(ad_videos, "write_storyboard", fake)
    monkeypatch.setattr(ad_videos, "get_settings", lambda: make_settings(anthropic_api_key="test"))
    return calls


def add_article(client):
    client.post(
        "/api/v1/knowledge", json={"title": "Packages", "content": "Growth: 450 JOD per month."}
    )


def create(client, brief=None):
    created = client.post("/api/v1/ad-videos", json={"brief": brief})
    assert created.status_code == 202
    return client.get(f"/api/v1/ad-videos/{created.json()['id']}").json()


def test_an_ad_is_written_from_the_knowledge_base(client, writer):
    add_article(client)

    ad = create(client, brief="the Growth package")

    assert ad["status"] == "ready"
    assert ad["title"] == "Growth package ad"
    assert ad["aspect"] == "9:16" and ad["language"] == "en"
    board = ad["storyboard"]
    assert [s["kind"] for s in board["scenes"]] == ["hook", "list", "price", "cta"]
    assert board["palette"] == "sunset"
    assert board["duration"] == 12.0
    assert "450 JOD per month" in writer[0]["knowledge"]
    assert writer[0]["brief"] == "the Growth package"
    assert ad["input_tokens"] == 4000


def test_an_empty_knowledge_base_is_explained(client, writer):
    ad = create(client)

    assert ad["status"] == "failed"
    assert "Knowledge Base is empty" in ad["error"]
    assert writer == []


def test_missing_api_key_is_explained(client, monkeypatch):
    monkeypatch.setattr(ad_videos, "get_settings", lambda: make_settings())
    add_article(client)

    ad = create(client)

    assert ad["status"] == "failed"
    assert "ANTHROPIC_API_KEY" in ad["error"]


def test_claude_errors_are_recorded(client, monkeypatch):
    monkeypatch.setattr(ad_videos, "get_settings", lambda: make_settings(anthropic_api_key="test"))

    def broken(*_args, **_kwargs):
        raise AdBuildError("Anthropic rate limit reached. Try again in a minute.")

    monkeypatch.setattr(ad_videos, "write_storyboard", broken)
    add_article(client)

    ad = create(client)

    assert ad["status"] == "failed"
    assert "rate limit" in ad["error"]


def test_ads_are_listed_newest_first_and_can_be_deleted(client, writer):
    add_article(client)
    first = create(client, "first")
    second = create(client, "second")

    listed = [a["id"] for a in client.get("/api/v1/ad-videos").json()["items"]]
    assert listed == [second["id"], first["id"]]

    assert client.delete(f"/api/v1/ad-videos/{first['id']}").status_code == 204
    assert [a["id"] for a in client.get("/api/v1/ad-videos").json()["items"]] == [second["id"]]


# --- Keeping storyboards safe to animate -------------------------------------------------


def test_a_long_storyboard_is_squeezed_to_15_seconds():
    long = STORY.model_copy(
        update={"scenes": [scene(k, 4.5) for k in ("hook", "feature", "feature", "price", "cta")]}
    )

    board = tidy(long)

    assert board["duration"] <= 15.0
    assert all(s["duration"] >= 2.5 for s in board["scenes"])


def test_a_short_storyboard_is_stretched_to_a_watchable_length():
    short = STORY.model_copy(update={"scenes": [scene(k, 1.0) for k in ("hook", "feature", "cta")]})

    board = tidy(short)

    assert 9.0 <= board["duration"] <= 15.0


def test_at_most_six_scenes_and_short_text():
    many = STORY.model_copy(
        update={
            "scenes": [
                scene("feature", 2.0, headline="x" * 200, items=["a" * 80] * 5) for _ in range(9)
            ]
        }
    )

    board = tidy(many)

    assert len(board["scenes"]) == 6
    assert len(board["scenes"][0]["headline"]) <= 48
    assert len(board["scenes"][0]["items"]) == 3
    assert all(len(i) <= 34 for i in board["scenes"][0]["items"])


def test_prices_keep_digits_only():
    board = tidy(
        STORY.model_copy(
            update={
                "scenes": [
                    scene("hook"),
                    scene("price", price_amount="JOD 450!"),
                    scene("cta"),
                ]
            }
        )
    )

    assert board["scenes"][1]["price_amount"] == "450"


def test_too_few_scenes_is_refused():
    with pytest.raises(AdBuildError):
        tidy(STORY.model_copy(update={"scenes": [scene("hook"), scene("cta")]}))
