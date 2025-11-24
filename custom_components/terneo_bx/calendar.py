from datetime import datetime, timedelta
import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.calendar.const import CalendarEntityFeature
from .const import DOMAIN

class TerneoCalendar(CalendarEntity):
    """Calendar mapping device schedule (tt) to HA local_calendar."""

    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host
        self._attr_name = f"Terneo {host} Schedule"
        self._attr_unique_id = f"terneo_{host}_schedule"
        self._attr_supported_features = (
            CalendarEntityFeature.CREATE_EVENT
            | CalendarEntityFeature.UPDATE_EVENT
            | CalendarEntityFeature.DELETE_EVENT
        )

    def _tt_to_events(self, start_date, end_date):
        events = []
        data = self.coordinator.data or {}
        schedule = (data.get("schedule") or {}).get("tt") or {}
        current = dt_util.start_of_local_day(start_date)
        while current <= end_date:
            wd = current.weekday()
            periods = schedule.get(str(wd), [])
            for period in periods:
                minute_of_day, temp_tenths = period
                event_start = current + timedelta(minutes=minute_of_day)
                if start_date <= event_start <= end_date:
                    summary = f"Terneo: {temp_tenths/10:.1f}°C"
                    events.append(
                        CalendarEvent(
                            start=event_start,
                            end=event_start + timedelta(minutes=30),
                            summary=summary,
                            description=str(temp_tenths),
                            uid=f"{wd}-{minute_of_day}-{temp_tenths}",
                        )
                    )
            current += timedelta(days=1)
        return events

    async def async_get_events(self, hass, start_date, end_date):
        return self._tt_to_events(start_date, end_date)

    async def async_create_event(self, **kwargs):
        start = kwargs.get("start_date_time") or kwargs.get("start_date")
        if start is None:
            return
        temp = None
        desc = kwargs.get("description")
        summary = kwargs.get("summary")
        if desc:
            try:
                temp = int(desc)
            except Exception:
                pass
        if temp is None and summary:
            try:
                temp = int(float(summary.split(":")[1].strip().rstrip("°C")) * 10)
            except Exception:
                pass
        if temp is None:
            return

        minutes = start.hour * 60 + start.minute
        wd = start.weekday()
        sn = self.coordinator.sn
        if sn is None:
            return

        cur = (self.coordinator.data.get("schedule") or {}).get("tt") or {}
        cur = {k: list(v) for k, v in cur.items()}
        cur.setdefault(str(wd), [])
        cur[str(wd)].append([minutes, temp])

        await self.coordinator.api.set_schedule(sn, cur)
        await self.coordinator.async_request_refresh()

    async def async_update_event(self, uid, **kwargs):
        await self.async_delete_event(uid)
        await self.async_create_event(**kwargs)

    async def async_delete_event(self, uid):
        parts = str(uid).split("-")
        if len(parts) < 3:
            return
        wd = parts[0]
        minute = int(parts[1])
        temp = int(parts[2])
        sn = self.coordinator.sn
        if sn is None:
            return

        cur = (self.coordinator.data.get("schedule") or {}).get("tt") or {}
        cur = {k: list(v) for k, v in cur.items()}
        if wd in cur:
            cur[wd] = [p for p in cur[wd] if not (p[0] == minute and p[1] == temp)]

        await self.coordinator.api.set_schedule(sn, cur)
        await self.coordinator.async_request_refresh()
