"""Shared RoyaleBench dashboard shell and leaderboard-inspired styles."""

import streamlit as st


def _toggle_theme():
    st.session_state["dark_mode"] = not st.session_state.get("dark_mode", True)


def render_shell():
    dark = st.session_state.get("dark_mode", True)
    palette = ("--rb-bg:#171716;--rb-surface:#222220;--rb-ink:#e9e8e3;--rb-muted:#969891;--rb-border:#393a35;--rb-secondary:#b1b2ab;--rb-selected:#34352f;--rb-focus:#5b5e51;color-scheme:dark" if dark else
               "--rb-bg:#f4f3f0;--rb-surface:#faf9f7;--rb-ink:#4a4d55;--rb-muted:#8a8d93;--rb-border:#e2e0db;--rb-secondary:#6f7279;--rb-selected:#eae8e2;--rb-focus:#c7c4bb;color-scheme:light")
    css = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap');
:root{PALETTE}
[data-testid="stAppViewContainer"]{background:var(--rb-bg);color:var(--rb-ink);font-family:'Geist',sans-serif}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none}
.stMainBlockContainer{max-width:1360px;padding:2.5rem 2rem 5rem}
.rb-brand{text-align:center;padding:12px 0 30px}
.rb-brand a{font-family:'Plus Jakarta Sans',sans-serif;font-size:26px;font-weight:600;letter-spacing:-.7px;text-decoration:none;color:var(--rb-ink)}
.rb-brand a span{font-weight:400}
.rb-brand p{font-size:14px;color:var(--rb-secondary);margin:9px 0 0}
h1,h2,h3{font-family:'Plus Jakarta Sans',sans-serif!important;color:var(--rb-ink);letter-spacing:-.5px}
h1{font-size:28px!important;font-weight:500!important;padding-top:18px!important}
h2{font-size:21px!important;font-weight:500!important}
h3{font-size:18px!important;font-weight:500!important}
[data-testid="stCaptionContainer"]{color:var(--rb-muted);font-size:13px;line-height:1.6}
[data-baseweb="tab-list"]{gap:28px;border-bottom:1px solid var(--rb-border);background:transparent}
[data-baseweb="tab"]{padding:12px 2px;color:var(--rb-muted);font-weight:400;font-size:14px}
[data-baseweb="tab"][aria-selected="true"]{color:var(--rb-ink);font-weight:600}
[data-baseweb="tab-highlight"]{background:#8a8d93;height:2px}
[data-baseweb="tab-border"]{display:none}
.st-key-main_navigation [data-baseweb="tab-list"]{justify-content:center}
[data-testid="stTabs"] [data-baseweb="tab-panel"]{padding-top:24px}
.st-key-page_controls{border-bottom:1px solid var(--rb-border);padding-bottom:16px;margin-bottom:12px}
[data-testid="stWidgetLabel"] p{font-size:13px;font-weight:500;color:var(--rb-secondary)}
[data-testid="stSelectbox"]>div,[data-testid="stNumberInput"]>div,[data-baseweb="input"],[data-baseweb="select"]>div{border-radius:8px!important}
[data-testid="stSelectbox"] input,[data-testid="stNumberInput"] input{font-size:14px!important}
[data-testid="stForm"]{background:var(--rb-surface);border:1px solid var(--rb-border);border-radius:12px;padding:24px}
[data-testid="stMetric"]{background:var(--rb-surface);border:1px solid var(--rb-border);border-radius:10px;padding:18px 20px}
[data-testid="stMetricValue"]{font-family:'Plus Jakarta Sans',sans-serif;font-size:28px;font-weight:500}
[data-testid="stMetricLabel"]{color:var(--rb-muted);font-size:12px}
[data-testid="stDataFrame"]{border-radius:8px;overflow:hidden;border:1px solid var(--rb-border)}
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button,[data-testid="stLinkButton"] a{border-radius:7px;font-weight:500;font-size:13px;min-height:40px;padding:8px 18px;box-shadow:none}
button[kind="primary"],button[kind="primaryFormSubmit"]{background:var(--rb-ink);border-color:var(--rb-ink);color:var(--rb-bg)}
button[kind="primary"]:hover,button[kind="primaryFormSubmit"]:hover{background:var(--rb-ink);border-color:var(--rb-ink);color:var(--rb-bg);opacity:.85}
[data-testid="stAlert"]{border-radius:8px;font-size:14px}
[data-testid="stExpander"]{background:var(--rb-surface);border-radius:8px;border-color:var(--rb-border)}
.st-key-play_mode [role="radiogroup"]{gap:8px;margin:2px 0 12px}
.st-key-play_mode [role="radiogroup"] label{padding:8px 16px;border:1px solid var(--rb-border);border-radius:7px;margin:0;background:var(--rb-surface)}
.st-key-play_mode [role="radiogroup"] label:has(input:checked){background:var(--rb-selected);border-color:var(--rb-focus)}
.st-key-play_mode [role="radiogroup"] label>div:first-child{display:none}
.st-key-play_content{background:var(--rb-surface);border:1px solid var(--rb-border);border-radius:12px;padding:24px}
.st-key-play_content [data-testid="stForm"]{border:0;padding:0}
.rb-footer{border-top:1px solid var(--rb-border);text-align:center;padding-top:24px;margin-top:40px;color:var(--rb-muted);font-size:12px;letter-spacing:.3px}
@media(max-width:640px){.stMainBlockContainer{padding:1.5rem 1rem 3rem}.rb-brand{padding-bottom:20px}[data-baseweb="tab-list"]{gap:18px;justify-content:flex-start!important;overflow-x:auto}[data-baseweb="tab"]{white-space:nowrap}h1{font-size:24px!important}[data-testid="stForm"],.st-key-play_content{padding:16px}}
[data-testid="stApp"],[data-testid="stMain"]{background:var(--rb-bg);color:var(--rb-ink)}
[data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"],[data-testid="stMetricValue"]{color:var(--rb-ink)}
button[kind="primary"] [data-testid="stMarkdownContainer"],button[kind="primaryFormSubmit"] [data-testid="stMarkdownContainer"]{color:var(--rb-bg)}
[data-testid="stSelectbox"] input,[data-testid="stNumberInput"] input,[data-baseweb="input"],input{background-color:var(--rb-surface)!important;color:var(--rb-ink)!important}
[data-testid="stSelectbox"] [data-focus-within]{border-color:var(--rb-border)}
[data-testid="stSelectbox"]>div>div,[data-testid="stNumberInput"]>div>div,[data-baseweb="select"]>div,[data-testid="stNumberInput"] button{background-color:var(--rb-surface);color:var(--rb-ink);border-color:var(--rb-border)}
[role="listbox"],[role="option"],[data-testid="stSelectboxVirtualDropdown"]{background-color:var(--rb-surface)!important;color:var(--rb-ink)!important}
[role="option"][data-focused] [data-item-hl],[role="option"][data-hovered] [data-item-hl]{background:var(--rb-selected)!important}
button[kind="secondary"],button[kind="secondaryFormSubmit"],[data-testid="stLinkButton"] a{background:var(--rb-surface);color:var(--rb-ink);border-color:var(--rb-border)}
[data-testid="stExpander"] details,[data-testid="stExpander"] summary{background:var(--rb-surface);color:var(--rb-ink);border-color:var(--rb-border)}
.st-key-theme_toggle [data-testid="stButton"]{display:flex;justify-content:center;align-items:center}
.st-key-theme_toggle [data-testid="stButton"] button{display:flex;align-items:center;justify-content:center;gap:0;width:40px;height:40px;padding:0;color:var(--rb-ink)!important;background:transparent!important;border:0!important;box-shadow:none!important;opacity:.75}
.st-key-theme_toggle [data-testid="stButton"] button:hover{opacity:1}
.st-key-theme_toggle [data-testid="stButton"] button p{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.rb-loading{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--rb-bg) 75%,transparent);backdrop-filter:blur(3px);cursor:progress}
.rb-loading-card{display:flex;align-items:center;gap:14px;max-width:calc(100vw - 40px);padding:22px 28px;border:1px solid var(--rb-border);border-radius:12px;background:var(--rb-surface);color:var(--rb-ink);font:500 14px 'Geist',sans-serif;box-shadow:0 12px 48px #0002}
.rb-loading-spinner{display:block;flex:0 0 24px;width:24px;height:24px;border:2px solid var(--rb-border);border-top-color:var(--rb-ink);border-radius:50%;animation:rb-spin .8s linear infinite}
@keyframes rb-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.rb-loading-spinner{animation:none}}
</style>
'''
    st.html(css.replace("PALETTE", palette))
    _, brand, control = st.columns([1, 4, 1], vertical_alignment="center")
    with brand:
        st.html('''<div class="rb-brand"><a href="?page=Leaderboard" target="_self">Royale<span>Bench</span></a>
<p>A Clash Royale Benchmark for Language Models</p></div>
''')
    with control.container(key="theme_toggle"):
        action = "Switch to light mode" if dark else "Switch to dark mode"
        st.button(action, icon=":material/light_mode:" if dark else ":material/dark_mode:",
                  key="theme_button", on_click=_toggle_theme)
