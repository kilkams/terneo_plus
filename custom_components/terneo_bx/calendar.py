import datetime
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

WEEKDAYS = ["0", "1", "2", "3", "4", "5", "6"]  # Monday–Sunday


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Setup Terneo schedule calendar."""

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    name = f"{entry.title} Schedule"
    device_id = coordinator.serial

    async_add_entities([TerneoScheduleCalendar(coordinator, name, device_id)], True)


class TerneoScheduleCalendar(CoordinatorEntity, CalendarEntity):
    def __init__(self, coordinator, name, device_id):
        super().__init__(coordinator)
        self._attr_name = name
        self._device_id = device_id
        self._attr_unique_id = f"Terneo_{self._attr_name}_schedule"
        self._current_event = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the currently active event."""
        return self._current_event

async def async_get_events(self, hass, start_date, end_date):
    """Return all schedule events in the given period."""
    events = []

    tz = datetime.datetime.now().astimezone().tzinfo
    tt = self.coordinator.data.get("tt", {})
    _LOGGER.warning("Terneo calendar: start=%s end=%s tt=%s", start_date, end_date, tt)

    for day_index, day in tt.items():
        if not day:
            continue

        weekday = int(day_index)
        date_cursor = start_date

        # find first matching weekday ≥ start_date
        while date_cursor.weekday() != weekday:
            date_cursor += timedelta(days=1)

        while date_cursor <= end_date:
            for idx, entry in enumerate(day):
                minute, temp = entry

                start = (
                    datetime.datetime.combine(
                        date_cursor.date(), datetime.time.min, tzinfo=tz
                    ) + timedelta(minutes=minute)
                )

                # END = next segment start OR end of day
                if idx + 1 < len(day):
                    next_minute = day[idx + 1][0]
                    end = (
                        datetime.datetime.combine(
                            date_cursor.date(), datetime.time.min, tzinfo=tz
                        ) + timedelta(minutes=next_minute)
                    )
                else:
                    # last segment → end of day
                    end = datetime.datetime.combine(
                        date_cursor.date(), datetime.time.max, tzinfo=tz
                    )

                events.append(
                    CalendarEvent(
                        summary=f"{temp / 10:.1f}°C",
                        start=start,
                        end=end,
                    )
                )

            date_cursor += timedelta(days=7)

    return events

    async def async_update(self):
        await super().async_update()
        self._update_current_event()

    def _update_current_event(self):
        """Calculate currently active event."""
        now = datetime.datetime.now().astimezone()
        tz = now.tzinfo

        tt = self.coordinator.data.get("tt", {})
        day = str(now.weekday())
        today_schedule = tt.get(day)

        if not today_schedule:
            self._current_event = None
            return

        minutes = now.hour * 60 + now.minute
        last_entry = None

        for entry in today_schedule:
            start_min, temp = entry
            if minutes >= start_min:
                last_entry = entry
            else:
                break

        if last_entry:
            start_min, temp = last_entry

            start = (
                datetime.datetime.combine(
                    now.date(),
                    datetime.time.min,
                    tzinfo=tz
                ) + timedelta(minutes=start_min)
            )

            # determine end
            next_index = today_schedule.index(last_entry) + 1

            if next_index < len(today_schedule):
                next_start = today_schedule[next_index][0]
                end = (
                    datetime.datetime.combine(
                        now.date(),
                        datetime.time.min,
                        tzinfo=tz
                    ) + timedelta(minutes=next_start)
                )
            else:
                end = datetime.datetime.combine(
                    now.date(),
                    datetime.time.max,
                    tzinfo=tz
                )

            self._current_event = CalendarEvent(
                summary=f"{temp / 10:.1f}°C",
                start=start,
                end=end,
            )
        else:
            self._current_event = None
