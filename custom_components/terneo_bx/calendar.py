import datetime
from datetime import timedelta
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity

WEEKDAYS = ["0", "1", "2", "3", "4", "5", "6"]  # Monday–Sunday


class TerneoScheduleCalendar(CoordinatorEntity, CalendarEntity):
    def __init__(self, coordinator, name, device_id):
        super().__init__(coordinator)
        self._attr_name = name
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_schedule"
        self._current_event = None

    # -------------------------------
    # Required: return current active event or None
    # -------------------------------
    @property
    def event(self) -> CalendarEvent | None:
        """Return the currently active event."""
        return self._current_event

    # -------------------------------
    # Required: return list of events for UI calendar view
    # -------------------------------
    async def async_get_events(self, hass, start_date, end_date):
        """Return all schedule events in the given period."""
        events = []

        tt = self.coordinator.data.get("tt", {})

        for day_index, day in tt.items():
            if not day:
                continue

            weekday = int(day_index)

            # find first date matching this weekday >= start_date
            date_cursor = start_date
            while date_cursor.weekday() != weekday:
                date_cursor += timedelta(days=1)

            while date_cursor <= end_date:
                for entry in day:
                    minute, temp = entry
                    start = datetime.datetime.combine(
                        date_cursor.date(), datetime.time.min
                    ) + timedelta(minutes=minute)

                    # End is beginning of next entry or end of day
                    events.append(
                        CalendarEvent(
                            summary=f"{temp/10:.1f}°C",
                            start=start,
                            end=start + timedelta(minutes=1),
                        )
                    )

                date_cursor += timedelta(days=7)

        return events

    # -------------------------------
    # Handle coordinator updates
    # -------------------------------
    async def async_update(self):
        await super().async_update()
        self._update_current_event()

    def _update_current_event(self):
        """Calculate currently active event."""
        now = datetime.datetime.now()
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
            start = datetime.datetime.combine(
                now.date(), datetime.time.min
            ) + timedelta(minutes=start_min)

            # End of event → next entry or end-of-day
            next_index = today_schedule.index(last_entry) + 1
            if next_index < len(today_schedule):
                next_start = today_schedule[next_index][0]
                end = datetime.datetime.combine(
                    now.date(), datetime.time.min
                ) + timedelta(minutes=next_start)
            else:
                end = datetime.datetime.combine(
                    now.date(), datetime.time.max
                )

            self._current_event = CalendarEvent(
                summary=f"{temp / 10:.1f}°C",
                start=start,
                end=end,
            )
        else:
            self._current_event = None
