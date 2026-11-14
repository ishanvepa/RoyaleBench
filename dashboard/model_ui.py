"""Provider logos for native Streamlit tables and model selections."""

from functools import lru_cache
from html import escape
import base64
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import streamlit as st

from cr_arena.site import LOGOS, _family


@lru_cache(maxsize=None)
def logo_uri(name: str) -> str | None:
    logo = LOGOS.get(_family(name, True))
    if logo is None:
        return None
    asset = Path(__file__).resolve().parents[1] / "cr_arena/assets/logos" / f"{logo[1]}.svg"
    # Bake the rounded tile into the asset so input backgrounds and table
    # images have the same corners as the dropdown menu icons.
    mark = ET.fromstring(asset.read_bytes())
    mark.attrib.update(x="4", y="4", width="20", height="20")
    tile = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28">'
            '<rect width="28" height="28" rx="6" fill="white"/>'
            + ET.tostring(mark, encoding="unicode") + '</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(tile.encode()).decode("ascii")


def model_label(name: str) -> str:
    uri = logo_uri(name)
    provider = LOGOS.get(_family(name, True), ("", ""))[0]
    image = (f'<img src="{uri}" alt="{provider} logo" width="22" height="22" '
             'style="vertical-align:middle;object-fit:contain;margin-right:8px">') if uri else ""
    return image + escape(name)


def model_dataframe(data, **kwargs):
    """Keep native sorting/selection, inserting image columns beside model names."""
    frame = data.copy()
    config = dict(kwargs.pop("column_config", {}) or {})
    for column in ("player", "model id", "blue", "red", "winner", "side"):
        if column not in frame:
            continue
        values = frame[column].map(lambda value: logo_uri(str(value).removeprefix("blue: ").removeprefix("red: ")))
        if not values.notna().any():
            continue
        key = f"{column} provider"
        frame.insert(frame.columns.get_loc(column), key, values)
        config[key] = st.column_config.ImageColumn("", width=40, help=f"{column} model provider")
    return st.dataframe(frame, column_config=config, **kwargs)


def model_selectbox(label, options, *, target=None, **kwargs):
    """Place provider marks inside the native input and its dropdown options."""
    host = target or st
    options = list(options)
    scope = "model-picker-" + hashlib.sha256(label.encode()).hexdigest()[:12]
    # Streamlit renders its popup in a portal, outside the keyed container.
    # Its listbox label and option keys come from the selectbox label/indices.
    # Keep the native widget so search, keyboard navigation and forms still work.
    rules = []
    for index, name in enumerate(options):
        uri = logo_uri(str(name))
        if not uri:
            continue
        value = json.dumps(str(name), ensure_ascii=True)
        popup = f'[role="listbox"][aria-label={json.dumps(label)}] [role="option"][data-key="{index}"]'
        rules.append(f'''
        .st-key-{scope} input[value={value}] {{
            padding-left:48px;
            background-image:url("{uri}");
            background-size:28px 28px;
            background-position:12px center;
            background-repeat:no-repeat;
        }}
        {popup}::before {{
            content:"";display:block;flex:0 0 28px;width:28px;height:28px;
            margin-left:8px;border-radius:6px;background:url("{uri}") center/28px 28px no-repeat;
        }}''')
    with host.container(key=scope):
        st.html("<style>" + "\n".join(rules) + "</style>")
        selected = st.selectbox(label, options, **kwargs)
    return selected
