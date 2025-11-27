from __future__ import annotations
from datetime import timedelta
import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.calendar.const import CalendarEntityFeature
from .const import DOMAIN, LOGGER
from .coordinator import TerneoCoordinator

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]['coordinator']
    host = entry.data.get('host')
    async_add_entities([TerneoCalendar(coordinator, host)])

class TerneoCalendar(CalendarEntity):
    def __init__(self, coordinator: TerneoCoordinator, host: str):
        self.coordinator = coordinator
        self._host = host
        self._attr_name = f"Terneo {host} Schedule"
        self._attr_unique_id = f"terneo_{host}_schedule"
        self._attr_supported_features = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.UPDATE_EVENT | CalendarEntityFeature.DELETE_EVENT

    def _read_schedule(self):
        data = (self.coordinator.data or {}).get('schedule') or {}
        return {k: list(v) for k,v in (data.items() if isinstance(data, dict) else [])}

    def _tt_to_events(self, start_date, end_date):
        events = []
        schedule = self._read_schedule()
        current = dt_util.start_of_local_day(start_date)
        while current <= end_date:
            wd = str(current.weekday())
            periods = schedule.get(wd, [])
            for minute,temp in periods:
                event_start = current + timedelta(minutes=minute)
                if start_date <= event_start <= end_date:
                    events.append(CalendarEvent(start=event_start, end=event_start+timedelta(minutes=30), summary=f"{temp/10:.1f}°C", description=str(temp), uid=f"{wd}-{minute}-{temp}" ))
            current += timedelta(days=1)
        return events

    async def async_get_events(self, hass, start_date, end_date):
        return self._tt_to_events(start_date, end_date)

    async def async_create_event(self, **kwargs):
        start = kwargs.get('start_date_time') or kwargs.get('start_date')
        if start is None:
            return
        temp = None
        if (desc := kwargs.get('description')):
            try:
                temp = int(desc)
            except:
                pass
        if temp is None and (summary := kwargs.get('summary')):
            try:
                temp = int(float(summary.rstrip('°C'))*10)
            except:
                pass
        if temp is None:
            return
        wd = str(start.weekday())
        minute = start.hour*60 + start.minute
        tt = self._read_schedule()
        tt.setdefault(wd, [])
        tt[wd].append([minute,temp])
        await self.coordinator.api.set_schedule(int(wd), tt[wd], sn=self.coordinator.serial)
        await self.coordinator.async_request_refresh()

    async def async_update_event(self, uid, **kwargs):
        await self.async_delete_event(uid)
        await self.async_create_event(**kwargs)

    async def async_delete_event(self, uid):
        try:
            wd, minute_str, temp_str = uid.split('-')
            minute = int(minute_str); temp = int(temp_str)
        except:
            return
        tt = self._read_schedule()
        if wd in tt:
            tt[wd] = [p for p in tt[wd] if not (p[0]==minute and p[1]==temp)]
        await self.coordinator.api.set_schedule(int(wd), tt.get(wd, []), sn=self.coordinator.serial)
        await self.coordinator.async_request_refresh()
