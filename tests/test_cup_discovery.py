from typing import Any, cast

from src.models import Event, EventDict, Race, Url
from src.utils.seeding import find_svenska_cupen_series_url


def test_find_svenska_cupen_series_url_from_event_objects() -> None:
    event_swe = Event(
        id="SWE_54359",
        name="Svenska Cupen MTBO 2026",
        start_time="2026-05-09",
        end_time="2026-05-09",
        status="Sanctioned",
        original_status="Sanctioned",
        races=[
            Race(
                race_number=1,
                name="Race 1",
                datetimez="2026-05-09T10:00:00+02:00",
                discipline="Middle",
            )
        ],
        urls=[
            Url(type="Eventor", url="Events/Show/54359"),
            Url(
                type="Series",
                url="/Standings/View/Series/1594",
                title="Svenska VeteranCupen MTBO 2026",
            ),
            Url(
                type="Series",
                url="/Standings/View/Series/1539",
                title="Svenska cupen MTBO 2026",
            ),
        ],
    )

    url = find_svenska_cupen_series_url([event_swe])
    assert url == "https://eventor.orientering.se/Standings/View/Series/1539"


def test_find_svenska_cupen_series_url_from_event_dicts() -> None:
    event_dict: dict[str, Any] = {
        "id": "SWE_54359",
        "name": "Svenska Cupen MTBO 2026",
        "start_time": "2026-05-09",
        "urls": [
            {
                "type": "Series",
                "url": "/Standings/View/Series/1594",
                "title": "Svenska VeteranCupen MTBO 2026",
            },
            {
                "type": "Series",
                "url": "https://eventor.orientering.se/Standings/View/Series/1539",
                "title": "Svenska Cupen MTBO 2026",
            },
        ],
    }

    url = find_svenska_cupen_series_url([cast(EventDict, event_dict)])
    assert url == "https://eventor.orientering.se/Standings/View/Series/1539"


def test_find_svenska_cupen_series_url_non_swe_ignored() -> None:
    event_iof: dict[str, Any] = {
        "id": "IOF_9017",
        "name": "World Cup Round",
        "start_time": "2026-05-09",
        "urls": [
            {
                "type": "Series",
                "url": "/Standings/View/Series/1539",
                "title": "Svenska Cupen MTBO 2026",
            }
        ],
    }

    url = find_svenska_cupen_series_url([cast(EventDict, event_iof)])
    assert url is None


def test_find_svenska_cupen_series_url_not_found() -> None:
    event_swe: dict[str, Any] = {
        "id": "SWE_12345",
        "name": "Local Training",
        "start_time": "2026-05-09",
        "urls": [],
    }

    url = find_svenska_cupen_series_url([cast(EventDict, event_swe)])
    assert url is None
