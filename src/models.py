from dataclasses import dataclass, field
from typing import TypedDict


class PositionDict(TypedDict):
    """Dictionary representation of a geographical position."""

    lat: float
    lng: float


class AreaDict(TypedDict):
    """Dictionary representation of a geographical area."""

    lat: float
    lng: float
    polygon: list[list[float]] | None


class UrlDict(TypedDict):
    """Dictionary representation of a URL resource."""

    type: str
    url: str
    title: str | None
    last_updated_at: str | None


class DocumentDict(TypedDict):
    """Dictionary representation of a document resource."""

    type: str
    title: str
    url: str
    published_time: str | None


class OfficialDict(TypedDict):
    """Dictionary representation of an event official."""

    role: str
    name: str


class OrganiserDict(TypedDict):
    """Dictionary representation of an event organiser."""

    name: str
    country_code: str | None


class EntryDeadlineDict(TypedDict):
    """Dictionary representation of an entry deadline."""

    type: str
    datetimez: str


class RaceDict(TypedDict):
    """Dictionary representation of a single race/stage."""

    race_number: int
    name: str
    datetimez: str
    discipline: str
    night_or_day: str | None
    position: PositionDict | None
    areas: list[AreaDict]
    urls: list[UrlDict]
    documents: list[DocumentDict]
    entry_counts: dict[str, int] | None
    start_counts: dict[str, int] | None
    result_counts: dict[str, int] | None
    fingerprints: list[str]


class EventDict(TypedDict):
    """Dictionary representation of an MTBO event."""

    id: str
    name: str
    start_time: str
    end_time: str
    status: str
    original_status: str
    types: list[str]
    tags: list[str]
    form: str | None
    organisers: list[OrganiserDict]
    officials: list[OfficialDict]
    classes: list[str]
    urls: list[UrlDict]
    information: str | None
    region: str | None
    punching_system: str | None
    races: list[RaceDict]
    documents: list[DocumentDict]
    entry_deadlines: list[EntryDeadlineDict]


class SourceDict(TypedDict):
    """Dictionary representation of a data source."""

    country_code: str
    name: str
    url: str


class MetaDict(TypedDict):
    """Dictionary representation of event list metadata."""

    sources: list[SourceDict]


class IndexPartitionDict(TypedDict):
    """Dictionary representation of an index partition entry."""

    path: str
    count: int
    last_updated_at: str


class IndexSourceDict(TypedDict):
    """Dictionary representation of an index source entry."""

    count: int
    last_updated_at: str


class IndexDict(TypedDict):
    """Dictionary representation of the Umbrella Index."""

    schema_version: str
    last_scraped_at: str
    data_root: str
    partitions: dict[str, IndexPartitionDict]
    sources: dict[str, IndexSourceDict]


class EventListWrapperDict(TypedDict):
    """Dictionary representation of the top-level event list wrapper."""

    schema_version: str
    create_time: str
    creator: str
    meta: MetaDict
    events: list[EventDict]


class ListCountDict(TypedDict):
    """Dictionary representation of list parsing counts."""

    total_count: int
    class_counts: dict[str, int]


class ParsedServiceLinkDict(TypedDict):
    """Internal dictionary for parsed service links."""

    race_index: int | None
    type: str
    url: str
    title: str


@dataclass
class Position:
    """Represents a geographical position."""

    lat: float
    lng: float


@dataclass
class Area:
    """Represents a geographical area, potentially with a polygon boundary."""

    lat: float
    lng: float
    polygon: list[list[float]] | None = None


@dataclass
class Url:
    """Represents a URL resource associated with an event or race."""

    # The type is one of the following:
    # IOF: Website, StartList, ResultList
    # Custom: EntryList, Livelox, Series, LocalStartList
    type: str
    url: str
    title: str | None = None
    last_updated_at: str | None = None


@dataclass
class Document:
    """Represents a document resource."""

    # Invitation, Bulletin, StartList, TechnicalInformation,
    # EmbargoMap, ResultList, Other
    type: str
    title: str
    url: str
    published_time: str | None = None  # ISO 8601 datetime


@dataclass
class Official:
    """Represents an event official."""

    role: str  # e.g., EventDirector, CourseSetter
    name: str


@dataclass
class Organiser:
    """Represents an event organiser."""

    name: str
    country_code: str | None = None


@dataclass
class EntryDeadline:
    """Represents an entry deadline."""

    type: str  # normal, late
    datetimez: str  # ISO 8601 datetime with offset (YYYY-MM-DDTHH:mm:ss+HH:MM)


@dataclass
class Race:
    """Represents a single race/stage within an event.

    Follows IOF 3.0 terminology with snake_case attributes.
    """

    race_number: int  # 1-based index
    name: str
    datetimez: str  # ISO 8601 datetime with offset (YYYY-MM-DDTHH:mm:ss+HH:MM)
    discipline: str  # Sprint, Middle, Long, Ultralong

    # Optional/Custom fields
    night_or_day: str | None = None  # day, night, combined

    # Position: Optional center point (lat, lng)
    position: Position | None = None

    # Areas: List of areas (center + polygon)
    areas: list[Area] = field(default_factory=list)

    urls: list[Url] = field(default_factory=list)
    # Documents specific to this race (e.g. start list if per race)
    documents: list[Document] = field(default_factory=list)

    # Participant fingerprints (SHA256 of Name|Club)
    fingerprints: list[str] = field(default_factory=list)

    # List counts (Class -> Count)
    entry_counts: dict[str, int] | None = None
    start_counts: dict[str, int] | None = None
    result_counts: dict[str, int] | None = None

    # Internal tracking
    _internal_eventor_id: str | None = None


@dataclass
class Event:
    """Represents an MTBO event.

    Follows IOF 3.0 terminology with snake_case attributes.
    """

    id: str  # {CountryCode}_{SourceId}
    name: str
    start_time: str  # YYYY-MM-DD (plain date)
    end_time: str  # YYYY-MM-DD (plain date)
    status: str  # IOF EventStatus: Planned, Applied, Proposed,
    # Sanctioned, Canceled, Rescheduled
    original_status: str  # Raw scraped status
    races: list[Race]  # minItems: 1

    # Optional fields
    types: list[str] = field(
        default_factory=list
    )  # Event types from Eventor (e.g., ["World Championships", "World Cup"])
    tags: list[str] = field(
        default_factory=list
    )  # Additional event tags: e.g. FootO, SkiO, TrailO, Indoor
    form: str | None = None  # Individual, Team, Relay
    organisers: list[Organiser] = field(default_factory=list)
    officials: list[Official] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    urls: list[Url] = field(default_factory=list)
    url: str | None = None  # Internal URL for scraping details
    # (not exposed in JSON usually)
    documents: list[Document] = field(default_factory=list)
    information: str | None = None
    region: str | None = None
    punching_system: str | None = None
    entry_deadlines: list[EntryDeadline] = field(default_factory=list)

    def to_dict(self) -> EventDict:
        """Converts the Event object to a dictionary matching the JSON Schema structure.

        Returns:
            A dictionary representation of the event.
        """
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "original_status": self.original_status,
            "types": self.types,
            "tags": self.tags,
            "form": self.form,
            "organisers": [
                OrganiserDict(name=o.name, country_code=o.country_code)
                for o in self.organisers
            ],
            "officials": [
                OfficialDict(role=o.role, name=o.name) for o in self.officials
            ],
            "classes": self.classes,
            "urls": [
                UrlDict(
                    type=u.type,
                    url=u.url,
                    title=u.title,
                    last_updated_at=u.last_updated_at,
                )
                for u in self.urls
            ],
            "documents": [
                DocumentDict(
                    type=d.type,
                    title=d.title,
                    url=d.url,
                    published_time=d.published_time,
                )
                for d in self.documents
            ],
            "information": self.information,
            "region": self.region,
            "punching_system": self.punching_system,
            "races": [
                RaceDict(
                    race_number=r.race_number,
                    name=r.name,
                    datetimez=r.datetimez,
                    discipline=r.discipline,
                    night_or_day=r.night_or_day,
                    position=PositionDict(lat=r.position.lat, lng=r.position.lng)
                    if r.position
                    else None,
                    areas=[
                        AreaDict(lat=a.lat, lng=a.lng, polygon=a.polygon)
                        for a in r.areas
                    ],
                    urls=[
                        UrlDict(
                            type=u.type,
                            url=u.url,
                            title=u.title,
                            last_updated_at=u.last_updated_at,
                        )
                        for u in r.urls
                    ],
                    documents=[
                        DocumentDict(
                            type=d.type,
                            title=d.title,
                            url=d.url,
                            published_time=d.published_time,
                        )
                        for d in r.documents
                    ],
                    entry_counts=r.entry_counts,
                    start_counts=r.start_counts,
                    result_counts=r.result_counts,
                    fingerprints=r.fingerprints,
                )
                for r in self.races
            ],
            "entry_deadlines": [
                EntryDeadlineDict(type=d.type, datetimez=d.datetimez)
                for d in self.entry_deadlines
            ],
        }


@dataclass
class Source:
    """Represents a data source."""

    country_code: str
    name: str
    url: str


@dataclass
class Meta:
    """Represents metadata for the event list."""

    sources: list[Source]


@dataclass
class EventListWrapper:
    """Top-level wrapper for the scraped event list."""

    schema_version: str
    create_time: str
    creator: str
    meta: Meta
    events: list[Event]

    def to_dict(self) -> EventListWrapperDict:
        """Converts the wrapper to a dictionary.

        Returns:
            A dictionary representation of the event list wrapper.
        """
        return {
            "schema_version": self.schema_version,
            "create_time": self.create_time,
            "creator": self.creator,
            "meta": MetaDict(
                sources=[
                    SourceDict(country_code=s.country_code, name=s.name, url=s.url)
                    for s in self.meta.sources
                ]
            ),
            "events": [e.to_dict() for e in self.events],
        }
