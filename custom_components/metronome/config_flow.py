"""Configure independent named metronomes from the UI."""

import probatio as vol

from homeassistant import config_entries

from .const import DOMAIN


class MetronomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            name = user_input["name"].strip()
            if name:
                return self.async_create_entry(title=name, data={})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("name", default="Metronome"): str}),
            errors={"name": "name_required"} if user_input is not None else {},
        )
