import datetime
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

WEEKDAYS = ["0", "1", "2", "3", "4", "5", "6"]  # Monday–Sunday


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Setup Terneo schedule calendar."""

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    host = entry.data.get("host")
    serial = coordinator.serial

    async_add_entities([TerneoScheduleCalendar(coordinator, host, serial)], True)


class TerneoScheduleCalendar(CoordinatorEntity, CalendarEntity):
    def __init__(self, coordinator, host, serial):
        super().__init__(coordinator)
        self._host = host
        self._serial = serial
        self._attr_name = f"Terneo {host} Schedule"
        self._attr_unique_id = f"terneo_{serial}_schedule"
        self._current_event = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
            model="Terneo BX"
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the currently active event."""
        return self._current_event

    async def async_get_events(self, hass, start_date, end_date):
        """Return all schedule events in the given period."""
        events = []

        tz = datetime.datetime.now().astimezone().tzinfo
        schedule = self.coordinator.data.get("schedule", {})
        
        _LOGGER.debug("Terneo calendar: start=%s end=%s schedule=%s", start_date, end_date, schedule)

        if not schedule:
            _LOGGER.warning("No schedule data available")
            return events

        try:
            for day_index, day_schedule in schedule.items():
                if not day_schedule:
                    continue

                weekday = int(day_index)
                date_cursor = start_date

                # find first matching weekday ≥ start_date
                while date_cursor.weekday() != weekday:
                    date_cursor += timedelta(days=1)
                    if date_cursor > end_date:
                        break

                while date_cursor <= end_date:
                    for idx, entry in enumerate(day_schedule):
                        if len(entry) < 2:
                            continue
                            
                        minute, temp = entry[0], entry[1]

                        start = (
                            datetime.datetime.combine(
                                date_cursor.date(), datetime.time.min, tzinfo=tz
                            ) + timedelta(minutes=minute)
                        )

                        # END = next segment start OR end of day
                        if idx + 1 < len(day_schedule):
                            next_minute = day_schedule[idx + 1][0]
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
                    
        except Exception as e:
            _LOGGER.error(f"Error generating calendar events: {e}", exc_info=True)

        _LOGGER.debug(f"Generated {len(events)} calendar events")
        return events

    async def async_update(self):
        """Update calendar state."""
        await super().async_update()
        self._update_current_event()

    def _update_current_event(self):
        """Calculate currently active event."""
        now = datetime.datetime.now().astimezone()
        tz = now.tzinfo

        schedule = self.coordinator.data.get("schedule", {})
        day = str(now.weekday())
        today_schedule = schedule.get(day)

        if not today_schedule:
            self._current_event = None
            return

        try:
            minutes = now.hour * 60 + now.minute
            last_entry = None

            for entry in today_schedule:
                if len(entry) < 2:
                    continue
                start_min, temp = entry[0], entry[1]
                if minutes >= start_min:
                    last_entry = entry
                else:
                    break

            if last_entry:
                start_min, temp = last_entry[0], last_entry[1]

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
                
        except Exception as e:
            _LOGGER.error(f"Error updating current event: {e}", exc_info=True)
            self._current_event = None