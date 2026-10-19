import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Resource Calculator", page_icon="📊", layout="centered",
    initial_sidebar_state="expanded",
)
st.markdown(
    "<style>[data-testid='stAppDeployButton'], [data-testid='stMainMenu'], "
    "[data-testid='stToolbarActions'], #MainMenu "
    "{display:none !important;}"
    "[data-testid='stExpandSidebarButton'], [data-testid='stSidebarCollapsedControl']"
    "{visibility:visible !important;}"
    "[data-testid='stSidebarHeader']{height:2rem !important;padding:0 .5rem !important;}"
    "[data-testid='stSidebarUserContent']{padding-top:0 !important;padding-bottom:1rem !important;}"
    "[data-testid='stSidebar'] [data-testid='stVerticalBlock']{gap:.6rem !important;}"
    "[data-testid='stSidebar'] hr{margin:.9rem 0 1.1rem !important;}"
    "[data-testid='stSidebar'] h3{padding:.2rem 0 .9rem !important;font-size:1.15rem !important;"
    "line-height:1.6 !important;}"
    "[data-testid='stSidebar'] [data-testid='stHeading']{overflow:visible !important;}"
    "[data-testid='stSidebar'] label{margin-bottom:.25rem !important;line-height:1.4 !important;}"
    "[data-testid='stSidebar'] [data-testid='stFileUploaderDropzoneInstructions']{display:none !important;}"
    "[data-testid='stSidebar'] [data-testid='stFileUploaderDropzone']{padding:.5rem !important;"
    "min-height:0 !important;}"
    "[data-testid='stSidebar'] .stButton button,[data-testid='stSidebar'] .stDownloadButton button,"
    "[data-testid='stSidebar'] [data-testid='stLinkButton'] a{min-height:2.4rem !important;"
    "padding:.3rem .75rem !important;}"
    "[data-testid='stSidebar'] [data-testid='stCaptionContainer']{font-size:.75rem !important;"
    "line-height:1.45 !important;opacity:.75;}"
    "[data-testid='stSidebar'] [data-testid='stFileUploader'] label{font-size:.9rem !important;}"
    "</style>",
    unsafe_allow_html=True,
)

DEF = dict(
    res="Cash, Wood, Steel, Oil, Rubber, Wrenches", time=True, builds="Build 1, Build 2",
    use_alts=True, alts="farm 1, farm 2", pct=65, use_crates=True,
    denoms="500, 2000, 5000, 20000, 50000, 100000, 200000, 500000, 2000000, 5000000",
)

ss = st.session_state
ss.setdefault("cfg", None)
ss.setdefault("d", {})
ss.setdefault("edit", False)
ss.setdefault("ver", 0)
ss.setdefault("page", "welcome")


# ---------- Utilities ----------
def lst(s):
    out = []
    for x in s.split(","):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


def nums(s):
    out = []
    for x in lst(s):
        try:
            v = float(x.replace(".", "").replace(",", "."))
            if v > 0 and v not in out:
                out.append(v)
        except ValueError:
            pass
    return out


def fmt(v):
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def fit(df, idx, cols):
    base = df if df is not None else pd.DataFrame()
    return base.reindex(index=idx, columns=cols).fillna(0.0).astype(float)


TC = ["Days", "Hours"]  # time stored as days + hours
SPEEDS = {"5 min": 5, "30 min": 30, "1 h": 60, "3 h": 180, "8 h": 480}  # minutes per speedup
NO_BOX = {"wrenches"}   # resources that don't come in crates
# old (Portuguese) labels -> English, used when importing older files
REN = {"Dias": "Days", "Horas": "Hours", "Estoque": "Stock", "Quantidade": "Quantity",
       "Ficha Branca": "White Chip", "Ficha Azul": "Blue Chip", "Ficha Vermelha": "Red Chip"}
EVENTOS = {
    "🍹 Drinks Event": dict(
        key="ev",
        tokens={"Bar Token": 1, "Super Bar Token": 15},
        metas={"🥇 Gold": 1340, "🏆 All rewards": 2060},
    ),
    "🎰 Casino": dict(
        key="cas",
        tokens={"White Chip": 1, "Blue Chip": 5, "Red Chip": 10},
        metas={"🥇 Gold": 1300, "🏆 All rewards": 1700},
    ),
}


COL_ITENS = {"Box": 10, "Collection": 80, "Map": 200}  # points per item
COL_ROUNDS = [9000, 18000, 27000, 36000, 45000]  # points to complete each round
COL_BONUS = 21  # Collections earned when completing each round

CAL_INICIO = date(2025, 8, 10)  # start of the first week (Sunday)
CAL_CICLOS = [
    ("Week of", ["Core", "Elites", "SW", "Elites"]),
    ("Event 1", ["Technology Celebration", "African Collection", "Talent",
                 "American Collection", "Resources", "Asia-Pacific Collection"]),
    ("Event 2", ["Champion league", "Family challenge", "Training"]),
    ("Event 3", ["Drinking", "Stars", "Casino", "Technology"]),
    ("Event 4", ["Anchors", "Invasion", "Treasure", "Dice"]),
    ("Event 5", ["Building Enhancement", "New Tech", "Capo Enhancement"]),
]
# (duration in weeks, week index where the 1st event starts); default = (1, 0)
CAL_DUR = {"Event 4": (2, 59), "Event 5": (3, 58)}
CAL_GAP = {"Event 5": 1}  # gap weeks after each event


def semana(n):
    ini = CAL_INICIO + timedelta(weeks=n)
    row = {"Start": ini, "End": ini + timedelta(days=6)}
    for nome, ciclo in CAL_CICLOS:
        dur, off = CAL_DUR.get(nome, (1, 0))
        gap = CAL_GAP.get(nome, 0)
        i, r = divmod((n - off) % ((dur + gap) * len(ciclo)), dur + gap)
        row[nome] = ciclo[i] if r < dur else "—"
    return row


def get_cols(c):
    return lst(c["res"]) + (TC if c["time"] else [])


def box_cols(c):
    return [r for r in lst(c["res"]) if r.lower() not in NO_BOX]


NO_ALT = {"wrenches"}   # resources farms don't have


def alt_cols(c):
    return [r for r in lst(c["res"]) if r.lower() not in NO_ALT]


def sync_farm_crates(c, d):
    farms = [f"cf_{a}" for a in lst(c["alts"])]
    for k in [k for k in d if k.startswith("cf_") and k not in farms]:
        del d[k]
    for k in farms:
        d[k] = fit(d.get(k), nums(DEF["denoms"]), box_cols(c))


def fmt_t(h):
    m = int(round(h * 60))
    dd, m = divmod(m, 1440)
    hh, mm = divmod(m, 60)
    return f"{dd}d {hh}h {mm}m"


def nav_names():
    c = ss.cfg
    names = ["Summary", "Buildings", "Stock"]
    if c["time"]:
        names.append("Speedups")
    if c["use_alts"] and len(ss.d["a"]):
        names.append("Farms")
    if c["use_crates"] and len(ss.d["c"]):
        names.append("Crates")
    return names


# ---------- Sidebar: export / import ----------
with st.sidebar:
    if ss.page == "solo":
        st.radio("Menu", ["Event calendar", "Rewards"], key="menu_solo")
        if ss.cfg and st.button("📊 Calculator", use_container_width=True):
            ss.page = "app"
            ss.edit = False
            st.rerun()
    if ss.page in ("app", "solo"):
        if ss.page == "app" and ss.cfg and not ss.edit:
            names = nav_names()
            if ss.get("menu_w") not in names:
                ss.menu_w = ss.get("menu") if ss.get("menu") in names else names[0]
            ss.menu = st.radio("Menu", names, key="menu_w")
            if st.button("⚙️ Configure", use_container_width=True):
                ss.edit = True
                st.rerun()
        if st.button("🏠 Home", use_container_width=True):
            ss.page = "welcome"
            st.rerun()
    if ss.page != "solo":
        st.divider()
        st.subheader("🧰 Tools")
        for nome, ico in [("Event calendar", "📅"), ("Rewards", "🎁")]:
            if st.button(f"{ico} {nome}", key=f"tool_{nome}", use_container_width=True):
                ss.menu_solo = nome
                ss.page = "solo"
                st.rerun()
    st.divider()
    st.subheader("💾 Data")
    if ss.cfg:
        payload = {
            "cfg": ss.cfg,
            "d": {k: {"index": list(v.index), "columns": list(v.columns), "data": v.values.tolist()}
                  for k, v in ss.d.items()},
        }
        st.download_button("Export data", json.dumps(payload), "resources.json", "application/json")
    up = st.file_uploader("Import data", type="json")
    if up and st.button("Load file"):
        try:
            data = json.load(up)
            ss.cfg = data["cfg"]
            ss.d = {k: pd.DataFrame(v["data"], index=v["index"], columns=v["columns"])
                    .rename(index=REN, columns=REN)
                    for k, v in data["d"].items()}
            ss.cfg["denoms"] = DEF["denoms"]
            a0 = ss.d.get("a")
            ss.d["a"] = fit(a0, list(a0.index) if a0 is not None else [], alt_cols(ss.cfg))
            ss.d["c"] = fit(ss.d.get("c"), nums(DEF["denoms"]), box_cols(ss.cfg))
            sync_farm_crates(ss.cfg, ss.d)
            ss.edit = False
            ss.page = "app"
            ss.ver += 1
            st.rerun()
        except Exception as e:
            st.error(f"Invalid file: {e}")
    st.divider()
    st.link_button(
        "💖 Support with a donation",
        "https://buy.stripe.com/eVqfZh4gH6JX8Yb9eSg3600",
        use_container_width=True,
    )
    st.caption(
        "Unofficial fan-made tool. Not affiliated with or endorsed by the game's developers "
        "or publishers. Names and trademarks belong to their respective owners."
    )


# ---------- Configuration ----------
def config():
    c = ss.cfg or DEF
    st.title("⚙️ Configuration")
    with st.form("form_cfg"):
        res = st.text_input("Resources (comma-separated)", c["res"])
        time = st.checkbox("Track time", c["time"])
        builds = st.text_input("Buildings (comma-separated)", c["builds"])
        use_alts = st.checkbox("I have farms", c["use_alts"])
        alts = st.text_input("Farm names (comma-separated)", c["alts"])
        pct = st.number_input("% used from farms", 0, 100, int(c["pct"]))
        ok = st.form_submit_button("Build", type="primary")

    if ok:
        R = lst(res)
        if not R:
            st.error("Enter at least one resource")
            return
        ss.cfg = dict(res=res, time=time, builds=builds, use_alts=use_alts, alts=alts,
                      pct=pct, use_crates=True, denoms=DEF["denoms"])
        cols = R + (TC if time else [])
        d = ss.d
        d["b"] = fit(d.get("b"), lst(builds), cols)
        d["mx"] = fit(d.get("mx"), ["Stock"], R)
        d["a"] = fit(d.get("a"), lst(alts), alt_cols(ss.cfg))
        d["c"] = fit(d.get("c"), nums(DEF["denoms"]), box_cols(ss.cfg))
        sync_farm_crates(ss.cfg, d)
        ss.edit = False
        ss.ver += 1
        st.rerun()


# ---------- Welcome ----------
def welcome():
    st.title("👋 Welcome to the Resource Calculator")
    st.write("Plan your buildings and find out how much of each resource you're missing (or have left over).")
    itens = [
        ("⚙️", "Configure", "Set up resources, buildings, farms and crates your way."),
        ("✏️", "Fill in", "Enter costs, stock, farms and crates in the tables."),
        ("📊", "Track", "See in the Summary what's missing and what's left over."),
    ]
    for col, (ico, t, txt) in zip(st.columns(3), itens):
        col.markdown(
            '<div style="border:1px solid rgba(128,128,128,.3);border-radius:8px;'
            'padding:16px;height:150px;box-sizing:border-box;overflow:hidden;">'
            '<div style="font-size:1.4rem;font-weight:600;line-height:2rem;height:2rem;">'
            f'{ico} {t}</div>'
            '<div style="font-size:.85rem;opacity:.7;margin-top:8px;line-height:1.4;">'
            f'{txt}</div></div>',
            unsafe_allow_html=True,
        )
    st.divider()
    if st.button("Continue" if ss.cfg else "Configure", type="primary"):
        ss.page = "app"
        st.rerun()
    if ss.cfg and st.button("Configure"):
        ss.page = "app"
        ss.edit = True
        st.rerun()


if ss.page == "welcome":
    welcome()
    st.stop()


if ss.page == "app" and (ss.cfg is None or ss.edit):
    config()
    if ss.cfg and st.button("Cancel"):
        ss.edit = False
        st.rerun()
    st.stop()


# ---------- Main screen ----------
solo = ss.page == "solo"
c, d = ss.cfg or DEF, ss.d
if not solo:
    sync_farm_crates(c, d)
d["v"] = fit(d.get("v"), list(SPEEDS), ["Quantity"])
R = lst(c["res"])
cols = get_cols(c)
v = ss.ver

if solo:
    page = ss.get("menu_solo", "Event calendar")
else:
    names = nav_names()
    page = ss.get("menu") if ss.get("menu") in names else names[0]
st.title(f"📊 {page}")

if page == "Buildings":
    if len(d["b"]):
        d["b"] = st.data_editor(d["b"], key=f"ed_b_{v}", use_container_width=True)
    else:
        st.info("No buildings. Add them in ⚙️.")
if page == "Stock":
    d["mx"] = st.data_editor(d["mx"].reindex(columns=R, fill_value=0.0), key=f"ed_mx_{v}", use_container_width=True)
if page == "Farms":
    with st.container():
        st.caption(f"Used: {c['pct']}%")
        d["a"] = st.data_editor(d["a"], key=f"ed_a_{v}", use_container_width=True)
        a = d["a"]
        ap = a * c["pct"] / 100
        tabela = pd.concat([
            ap,
            a.sum().to_frame("Gross total").T,
            ap.sum().to_frame("Used total").T,
        ])
        tabela.index = [f"{i} (used)" for i in ap.index] + ["Gross total", "Used total"]
        st.subheader("Farm calculation")
        st.dataframe(tabela.style.format(fmt), use_container_width=True)
if page == "Crates":
    st.subheader("Main crates")
    st.caption("Number of crates of each value (fixed values)")
    d["c"] = st.data_editor(d["c"], key=f"ed_c_{v}", use_container_width=True)
    if c["use_alts"] and lst(c["alts"]):
        st.subheader("Farm crates")
        st.caption(f"Used: {c['pct']}%")
        farms = lst(c["alts"])
        for tab, fa in zip(st.tabs(farms), farms):
            with tab:
                d[f"cf_{fa}"] = st.data_editor(
                    d[f"cf_{fa}"], key=f"ed_cf_{fa}_{v}", use_container_width=True
                )

if page == "Speedups":
    st.caption("How many speedups of each duration you own")
    d["v"] = st.data_editor(d["v"], key=f"ed_v_{v}", use_container_width=True)

if page == "Event calendar":
    hoje = date.today()
    atual = (hoje - CAL_INICIO).days // 7
    qtd = st.slider("Future weeks shown", 4, 52, 4)
    df = pd.DataFrame([semana(n) for n in range(atual - 1, atual + qtd + 1)])
    df.insert(0, "Status", ["Previous", "Current"] + [""] * qtd)
    for k in ("Start", "End"):
        df[k] = df[k].map(lambda x: x.strftime("%d/%m/%Y"))
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.subheader("Next occurrence")
    todos = sorted({e for _, ciclo in CAL_CICLOS for e in ciclo})
    ev_sel = st.selectbox("Event", todos)
    for n in range(atual, atual + 13):
        s = semana(n)
        if ev_sel in [s[k] for k, _ in CAL_CICLOS]:
            quando = "this week" if n == atual else f"in {n - atual} week(s)"
            st.info(f"**{ev_sel}**: {s['Start']:%d/%m/%Y} to {s['End']:%d/%m/%Y} ({quando})")
            break

    st.subheader("Look up by date")
    dt = st.date_input("Date", hoje, format="DD/MM/YYYY")
    nd = (dt - CAL_INICIO).days // 7
    if nd < 0:
        st.warning(f"Date is before the calendar start ({CAL_INICIO:%d/%m/%Y}).")
    else:
        sd = semana(nd)
        st.info(f"Week of {sd['Start']:%d/%m/%Y} to {sd['End']:%d/%m/%Y}")
        st.dataframe(
            pd.DataFrame([(k, sd[k]) for k, _ in CAL_CICLOS], columns=["Category", "Event"]),
            hide_index=True, use_container_width=True,
        )
    st.stop()

if page == "Rewards":
    tabs = st.tabs(list(EVENTOS) + ["📚 Collections"])
    for tab, (titulo, ev) in zip(tabs, EVENTOS.items()):
        with tab:
            kev, toks = ev["key"], ev["tokens"]
            st.subheader(titulo)
            st.caption(" · ".join(f"{k} = {p} point{'s' if p > 1 else ''}" for k, p in toks.items()))
            d[kev] = fit(d.get(kev), ["Quantity"], list(toks))
            d[kev] = st.data_editor(d[kev], key=f"ed_{kev}_{v}", use_container_width=True)
            pts = sum(d[kev].loc["Quantity", k] * p for k, p in toks.items())
            st.metric("Total points", fmt(pts))
            for nome, meta in ev["metas"].items():
                falta = max(0, meta - pts)
                with st.container(border=True):
                    st.markdown(f"**{nome}** — {fmt(meta)} points")
                    st.progress(min(1.0, pts / meta))
                    if falta == 0:
                        st.success(f"Goal reached! {fmt(pts - meta)} points left over.")
                    else:
                        opc = " or ".join(f"{int(-(-falta // p))} {k}" for k, p in toks.items())
                        st.error(f"{fmt(falta)} points missing (≈ {opc}).")

    with tabs[-1]:
        bonus = COL_BONUS * COL_ITENS["Collection"]
        st.subheader("📚 Collections")
        st.caption(
            " · ".join(f"{k} = {p} points" for k, p in COL_ITENS.items())
            + f" · Completing each round earns you {COL_BONUS} Collections (added automatically)"
        )
        d["col"] = fit(d.get("col"), ["Quantity"], list(COL_ITENS))
        d["col"] = st.data_editor(d["col"], key=f"ed_col_{v}", use_container_width=True)
        pts = sum(d["col"].loc["Quantity", k] * p for k, p in COL_ITENS.items())

        # completed rounds in order; each bonus only counts after finishing its round
        done = 0
        for meta in COL_ROUNDS:
            if pts + bonus * done >= meta:
                done += 1
            else:
                break
        efetivo = pts + bonus * done

        m1, m2, m3 = st.columns(3)
        m1.metric("Entered points", fmt(pts))
        m2.metric("Bonus earned", fmt(bonus * done), help=f"{done * COL_BONUS} Collections")
        m3.metric("Total", fmt(efetivo), delta=f"final goal {fmt(COL_ROUNDS[-1])}", delta_color="off")

        for i, meta in enumerate(COL_ROUNDS, 1):
            with st.container(border=True):
                st.markdown(f"**Round {i}** — {fmt(meta)} points")
                if i <= done:
                    st.progress(1.0)
                    st.success(f"Completed! +{COL_BONUS} Collections ({fmt(bonus)} points) already added.")
                else:
                    falta = meta - efetivo
                    st.progress(min(1.0, max(0.0, efetivo / meta)))
                    opc = " or ".join(f"{int(-(-falta // p))} {k}" for k, p in COL_ITENS.items())
                    st.error(f"{fmt(falta)} points missing (≈ {opc}).")
    st.stop()

# ---------- Calculation ----------
zero = pd.Series(0.0, index=cols)
tot = d["b"].sum().reindex(cols, fill_value=0.0)

if c["use_alts"] and len(d["a"]):
    free = (d["a"].sum() * c["pct"] / 100).reindex(cols, fill_value=0.0)
else:
    free = zero

def crate_sum(df):
    return df.mul(df.index.to_numpy(dtype=float), axis=0).sum().reindex(cols, fill_value=0.0)


if c["use_crates"] and len(d["c"]):
    box = crate_sum(d["c"])
else:
    box = zero

fboxes = {}
if c["use_crates"] and c["use_alts"]:
    for fa in lst(c["alts"]):
        fboxes[fa] = crate_sum(d[f"cf_{fa}"]) * c["pct"] / 100
fbox = sum(fboxes.values(), zero)
box_all = box + fbox

has_crates = c["use_crates"] and len(d["c"]) > 0
if page == "Summary" and has_crates:
    if "add_w" not in ss:
        ss.add_w = ss.get("add", False)
    ss.add = st.toggle("Add crates to stock", key="add_w")
add = bool(ss.get("add", False)) and has_crates
have = d["mx"].iloc[0].reindex(cols, fill_value=0.0) + free + (box_all if add else zero)
need = tot - have

# total time in hours (days * 24 + hours), basis for speedups
tot_h = tot["Days"] * 24 + tot["Hours"] if c["time"] else 0.0
spd_h = sum(d["v"].loc[k, "Quantity"] * m for k, m in SPEEDS.items()) / 60
have_h = spd_h if c["time"] else 0.0

# ---------- Crate calculation ----------
if page == "Crates":
    st.subheader("Crate calculation")
    bc = box_cols(c)
    linhas = {"Main crates": box.reindex(bc, fill_value=0.0)}
    for fa, s in fboxes.items():
        linhas[f"{fa} (used)"] = s.reindex(bc, fill_value=0.0)
    df_cx = pd.DataFrame(linhas).T
    df_cx.loc["Total"] = df_cx.sum()
    st.dataframe(df_cx.style.format(fmt), use_container_width=True)
    st.stop()

# ---------- Speedups ----------
if page == "Speedups":
    st.subheader("Speedup calculation")
    dif = spd_h - tot_h
    m1, m2, m3 = st.columns(3)
    m1.metric("Building time", fmt_t(tot_h))
    m2.metric("Your speedups", fmt_t(spd_h))
    m3.metric("Surplus" if dif >= 0 else "Missing", fmt_t(abs(dif)))
    if dif >= 0:
        st.success("You have enough speedups to finish the buildings.")
    else:
        st.error(f"You're missing {fmt_t(-dif)} of speedups to finish the buildings.")
    linhas = {
        k: {"Quantity": d["v"].loc[k, "Quantity"], "Total time": fmt_t(d["v"].loc[k, "Quantity"] * m / 60)}
        for k, m in SPEEDS.items()
    }
    st.dataframe(pd.DataFrame(linhas).T, use_container_width=True)
    st.stop()

# ---------- Total stock ----------
if page == "Stock":
    st.subheader("Total stock")
    linhas = {"Manual stock": d["mx"].iloc[0].reindex(R, fill_value=0.0)}
    if c["use_alts"] and len(d["a"]):
        linhas["Farms (used)"] = free.reindex(R, fill_value=0.0)
    if has_crates:
        linhas["Crates"] = box.reindex(R, fill_value=0.0)
    if fboxes:
        linhas["Farm crates (used)"] = fbox.reindex(R, fill_value=0.0)
    df_tot = pd.DataFrame(linhas).T
    df_tot.loc["Total"] = df_tot.sum()
    st.dataframe(df_tot.style.format(fmt), use_container_width=True)
    st.stop()

# ---------- Summary ----------
if page != "Summary":
    st.stop()

st.subheader("Summary")
items = [(k, have[k], tot[k], False) for k in R]
if c["time"]:
    items.append(("Time", have_h, tot_h, True))
for i in range(0, len(items), 3):
    row = st.columns(3)
    for col, (k, h, t, is_t) in zip(row, items[i:i + 3]):
        ff = fmt_t if is_t else fmt
        with col.container(border=True):
            n = t - h
            delta = "0" if n == 0 else ("-" if n > 0 else "+") + ff(abs(n))
            st.metric(k, f"{ff(h)} / {ff(t)}", delta=delta)
            pr = h / t if t > 0 else 1.0
            st.progress(min(1.0, max(0.0, pr)))
            st.caption("Missing" if n > 0 else "Surplus" if n < 0 else "Exact")

if c["use_crates"] and len(d["c"]):
    with st.expander("Crate totals"):
        for k in R:
            st.write(f"**{k}:** {fmt(box_all[k])}")

if c["use_alts"] and len(d["a"]):
    with st.expander("Farm totals"):
        for k in alt_cols(c):
            bruto = d["a"][k].sum()
            st.write(f"**{k}:** {fmt(bruto)} gross → {fmt(bruto * c['pct'] / 100)} used")
