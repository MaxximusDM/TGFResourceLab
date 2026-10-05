import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Calculadora de Recursos", page_icon="📊", layout="centered")

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


# ---------- Utilitários ----------
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
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fit(df, idx, cols):
    base = df if df is not None else pd.DataFrame()
    return base.reindex(index=idx, columns=cols).fillna(0.0).astype(float)


TC = ["Dias", "Horas"]  # tempo guardado em dias + horas
SPEEDS = {"5 min": 5, "30 min": 30, "1 h": 60, "3 h": 180, "8 h": 480}  # minutos de cada velocidade
NO_BOX = {"wrenches"}   # recursos que não existem em caixas
EVENTOS = {
    "🍹 Evento de bebidas": dict(
        key="ev",
        tokens={"Bar Token": 1, "Super Bar Token": 15},
        metas={"🥇 Ouro": 1340, "🏆 Todas as recompensas": 2060},
    ),
    "🎰 Cassino": dict(
        key="cas",
        tokens={"Ficha Branca": 1, "Ficha Azul": 5, "Ficha Vermelha": 10},
        metas={"🥇 Ouro": 1300, "🏆 Todas as recompensas": 1700},
    ),
}


CAL_INICIO = date(2025, 8, 10)  # início da primeira semana (domingo)
CAL_CICLOS = [
    ("Semana do", ["Core", "Elites", "SW", "Elites"]),
    ("Evento 1", ["Technology Celebration", "African Collection", "Talent",
                  "American Collection", "Resources", "Asia-Pacific Collection"]),
    ("Evento 2", ["Champion league", "Family challenge", "Training"]),
    ("Evento 3", ["Drinking", "Stars", "Casino", "Technology"]),
    ("Evento 4", ["Anchors", "Invasion", "Treasure", "Dice"]),
    ("Evento 5", ["Building Enhancement", "New Tech", "Capo Enhancement"]),
]
# (duração em semanas, semana-índice em que o 1º evento começa); padrão = (1, 0)
CAL_DUR = {"Evento 4": (2, 59), "Evento 5": (3, 58)}
CAL_GAP = {"Evento 5": 1}  # semanas de intervalo após cada evento


def semana(n):
    ini = CAL_INICIO + timedelta(weeks=n)
    row = {"Início": ini, "Fim": ini + timedelta(days=6)}
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


NO_ALT = {"wrenches"}   # recursos que as fazendas não possuem


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
    names = ["Resumo", "Construções", "Estoque"]
    if c["time"]:
        names.append("Velocidades")
    if c["use_alts"] and len(ss.d["a"]):
        names.append("Fazendas")
    if c["use_crates"] and len(ss.d["c"]):
        names.append("Caixas")
    names += ["Calendário de eventos", "Recompensas"]
    return names


# ---------- Barra lateral: exportar / importar ----------
with st.sidebar:
    if ss.page == "solo":
        st.radio("Menu", ["Calendário de eventos", "Recompensas"], key="menu_solo")
    if ss.page in ("app", "solo"):
        if ss.page == "app" and ss.cfg and not ss.edit:
            names = nav_names()
            if ss.get("menu_w") not in names:
                ss.menu_w = ss.get("menu") if ss.get("menu") in names else names[0]
            ss.menu = st.radio("Menu", names, key="menu_w")
            if st.button("⚙️ Configurar", use_container_width=True):
                ss.edit = True
                st.rerun()
        if st.button("🏠 Início", use_container_width=True):
            ss.page = "welcome"
            st.rerun()
    st.divider()
    st.header("💾 Dados")
    if ss.cfg:
        payload = {
            "cfg": ss.cfg,
            "d": {k: {"index": list(v.index), "columns": list(v.columns), "data": v.values.tolist()}
                  for k, v in ss.d.items()},
        }
        st.download_button("Exportar dados", json.dumps(payload), "recursos.json", "application/json")
    up = st.file_uploader("Importar dados", type="json")
    if up and st.button("Carregar arquivo"):
        try:
            data = json.load(up)
            ss.cfg = data["cfg"]
            ss.d = {k: pd.DataFrame(v["data"], index=v["index"], columns=v["columns"])
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
            st.error(f"Arquivo inválido: {e}")


# ---------- Configuração ----------
def config():
    c = ss.cfg or DEF
    st.title("⚙️ Configuração")
    with st.form("form_cfg"):
        res = st.text_input("Recursos (separados por vírgula)", c["res"])
        time = st.checkbox("Controlar tempo", c["time"])
        builds = st.text_input("Construções (separadas por vírgula)", c["builds"])
        use_alts = st.checkbox("Tenho fazendas", c["use_alts"])
        alts = st.text_input("Nomes das fazendas (separadas por vírgula)", c["alts"])
        pct = st.number_input("% aproveitada das fazendas", 0, 100, int(c["pct"]))
        ok = st.form_submit_button("Montar", type="primary")

    if ok:
        R = lst(res)
        if not R:
            st.error("Informe ao menos um recurso")
            return
        ss.cfg = dict(res=res, time=time, builds=builds, use_alts=use_alts, alts=alts,
                      pct=pct, use_crates=True, denoms=DEF["denoms"])
        cols = R + (TC if time else [])
        d = ss.d
        d["b"] = fit(d.get("b"), lst(builds), cols)
        d["mx"] = fit(d.get("mx"), ["Estoque"], R)
        d["a"] = fit(d.get("a"), lst(alts), alt_cols(ss.cfg))
        d["c"] = fit(d.get("c"), nums(DEF["denoms"]), box_cols(ss.cfg))
        sync_farm_crates(ss.cfg, d)
        ss.edit = False
        ss.ver += 1
        st.rerun()


# ---------- Boas-vindas ----------
def welcome():
    st.title("👋 Bem-vindo à Calculadora de Recursos")
    st.write("Planeje suas construções e descubra quanto falta (ou sobra) de cada recurso.")
    itens = [
        ("⚙️", "Configure", "Defina recursos, construções, fazendas e caixas do seu jeito."),
        ("✏️", "Preencha", "Informe custos, estoque, fazendas e caixas nas tabelas."),
        ("📊", "Acompanhe", "Veja no Resumo o que falta e o que sobra."),
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
    st.write("")
    st.subheader("Acesso rápido")
    st.caption("Use sem precisar configurar seus recursos.")
    b1, b2 = st.columns(2)
    if b1.button("📅 Calendário de eventos", use_container_width=True):
        ss.menu_solo = "Calendário de eventos"
        ss.page = "solo"
        st.rerun()
    if b2.button("🎁 Recompensas", use_container_width=True):
        ss.menu_solo = "Recompensas"
        ss.page = "solo"
        st.rerun()
    st.divider()
    if st.button("Continuar" if ss.cfg else "Configurar", type="primary"):
        ss.page = "app"
        st.rerun()
    if ss.cfg and st.button("Configurar"):
        ss.page = "app"
        ss.edit = True
        st.rerun()


if ss.page == "welcome":
    welcome()
    st.stop()


if ss.page == "app" and (ss.cfg is None or ss.edit):
    config()
    if ss.cfg and st.button("Cancelar"):
        ss.edit = False
        st.rerun()
    st.stop()


# ---------- Tela principal ----------
solo = ss.page == "solo"
c, d = ss.cfg or DEF, ss.d
if not solo:
    sync_farm_crates(c, d)
d["v"] = fit(d.get("v"), list(SPEEDS), ["Quantidade"])
R = lst(c["res"])
cols = get_cols(c)
v = ss.ver

if solo:
    page = ss.get("menu_solo", "Calendário de eventos")
else:
    names = nav_names()
    page = ss.get("menu") if ss.get("menu") in names else names[0]
st.title(f"📊 {page}")

if page == "Construções":
    if len(d["b"]):
        d["b"] = st.data_editor(d["b"], key=f"ed_b_{v}", use_container_width=True)
    else:
        st.info("Nenhuma construção. Adicione em ⚙️.")
if page == "Estoque":
    d["mx"] = st.data_editor(d["mx"].reindex(columns=R, fill_value=0.0), key=f"ed_mx_{v}", use_container_width=True)
if page == "Fazendas":
    with st.container():
        st.caption(f"Aproveitado: {c['pct']}%")
        d["a"] = st.data_editor(d["a"], key=f"ed_a_{v}", use_container_width=True)
        a = d["a"]
        ap = a * c["pct"] / 100
        tabela = pd.concat([
            ap,
            a.sum().to_frame("Total bruto").T,
            ap.sum().to_frame("Total aproveitado").T,
        ])
        tabela.index = [f"{i} (aproveitado)" for i in ap.index] + ["Total bruto", "Total aproveitado"]
        st.subheader("Cálculo das fazendas")
        st.dataframe(tabela.style.format(fmt), use_container_width=True)
if page == "Caixas":
    st.subheader("Caixas principais")
    st.caption("Quantidade de caixas de cada valor (valores fixos)")
    d["c"] = st.data_editor(d["c"], key=f"ed_c_{v}", use_container_width=True)
    if c["use_alts"] and lst(c["alts"]):
        st.subheader("Caixas das fazendas")
        st.caption(f"Aproveitado: {c['pct']}%")
        farms = lst(c["alts"])
        for tab, fa in zip(st.tabs(farms), farms):
            with tab:
                d[f"cf_{fa}"] = st.data_editor(
                    d[f"cf_{fa}"], key=f"ed_cf_{fa}_{v}", use_container_width=True
                )

if page == "Velocidades":
    st.caption("Quantidade de velocidades que você possui de cada tempo")
    d["v"] = st.data_editor(d["v"], key=f"ed_v_{v}", use_container_width=True)

if page == "Calendário de eventos":
    hoje = date.today()
    atual = (hoje - CAL_INICIO).days // 7
    qtd = st.slider("Semanas futuras exibidas", 4, 52, 12)
    df = pd.DataFrame([semana(n) for n in range(atual - 1, atual + qtd + 1)])
    df.insert(0, "Status", ["Anterior", "Atual"] + [""] * qtd)
    for k in ("Início", "Fim"):
        df[k] = df[k].map(lambda x: x.strftime("%d/%m/%Y"))
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.subheader("Próxima ocorrência")
    todos = sorted({e for _, ciclo in CAL_CICLOS for e in ciclo})
    ev_sel = st.selectbox("Evento", todos)
    for n in range(atual, atual + 13):
        s = semana(n)
        if ev_sel in [s[k] for k, _ in CAL_CICLOS]:
            quando = "nesta semana" if n == atual else f"em {n - atual} semana(s)"
            st.info(f"**{ev_sel}**: {s['Início']:%d/%m/%Y} a {s['Fim']:%d/%m/%Y} ({quando})")
            break

    st.subheader("Consultar por data")
    dt = st.date_input("Data", hoje, format="DD/MM/YYYY")
    nd = (dt - CAL_INICIO).days // 7
    if nd < 0:
        st.warning(f"Data anterior ao início do calendário ({CAL_INICIO:%d/%m/%Y}).")
    else:
        sd = semana(nd)
        st.info(f"Semana de {sd['Início']:%d/%m/%Y} a {sd['Fim']:%d/%m/%Y}")
        st.dataframe(
            pd.DataFrame([(k, sd[k]) for k, _ in CAL_CICLOS], columns=["Categoria", "Evento"]),
            hide_index=True, use_container_width=True,
        )
    st.stop()

if page == "Recompensas":
    for tab, (titulo, ev) in zip(st.tabs(list(EVENTOS)), EVENTOS.items()):
        with tab:
            kev, toks = ev["key"], ev["tokens"]
            st.subheader(titulo)
            st.caption(" · ".join(f"{k} = {p} ponto{'s' if p > 1 else ''}" for k, p in toks.items()))
            d[kev] = fit(d.get(kev), ["Quantidade"], list(toks))
            d[kev] = st.data_editor(d[kev], key=f"ed_{kev}_{v}", use_container_width=True)
            pts = sum(d[kev].loc["Quantidade", k] * p for k, p in toks.items())
            st.metric("Pontos totais", fmt(pts))
            for nome, meta in ev["metas"].items():
                falta = max(0, meta - pts)
                with st.container(border=True):
                    st.markdown(f"**{nome}** — {fmt(meta)} pontos")
                    st.progress(min(1.0, pts / meta))
                    if falta == 0:
                        st.success(f"Meta atingida! Sobram {fmt(pts - meta)} pontos.")
                    else:
                        opc = " ou ".join(f"{int(-(-falta // p))} {k}" for k, p in toks.items())
                        st.error(f"Faltam {fmt(falta)} pontos (≈ {opc}).")
    st.stop()

# ---------- Cálculo ----------
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
if page == "Resumo" and has_crates:
    if "add_w" not in ss:
        ss.add_w = ss.get("add", False)
    ss.add = st.toggle("Somar caixas ao estoque", key="add_w")
add = bool(ss.get("add", False)) and has_crates
have = d["mx"].iloc[0].reindex(cols, fill_value=0.0) + free + (box_all if add else zero)
need = tot - have

# tempo total em horas (dias * 24 + horas), base para as velocidades
tot_h = tot["Dias"] * 24 + tot["Horas"] if c["time"] else 0.0
spd_h = sum(d["v"].loc[k, "Quantidade"] * m for k, m in SPEEDS.items()) / 60
have_h = spd_h if c["time"] else 0.0

# ---------- Cálculo das caixas ----------
if page == "Caixas":
    st.subheader("Cálculo das caixas")
    bc = box_cols(c)
    linhas = {"Caixas principais": box.reindex(bc, fill_value=0.0)}
    for fa, s in fboxes.items():
        linhas[f"{fa} (aproveitado)"] = s.reindex(bc, fill_value=0.0)
    df_cx = pd.DataFrame(linhas).T
    df_cx.loc["Total"] = df_cx.sum()
    st.dataframe(df_cx.style.format(fmt), use_container_width=True)
    st.stop()

# ---------- Velocidades ----------
if page == "Velocidades":
    st.subheader("Cálculo das velocidades")
    dif = spd_h - tot_h
    m1, m2, m3 = st.columns(3)
    m1.metric("Tempo das construções", fmt_t(tot_h))
    m2.metric("Suas velocidades", fmt_t(spd_h))
    m3.metric("Sobra" if dif >= 0 else "Falta", fmt_t(abs(dif)))
    if dif >= 0:
        st.success("Você tem velocidades suficientes para concluir as construções.")
    else:
        st.error(f"Faltam {fmt_t(-dif)} de velocidades para concluir as construções.")
    linhas = {
        k: {"Quantidade": d["v"].loc[k, "Quantidade"], "Tempo total": fmt_t(d["v"].loc[k, "Quantidade"] * m / 60)}
        for k, m in SPEEDS.items()
    }
    st.dataframe(pd.DataFrame(linhas).T, use_container_width=True)
    st.stop()

# ---------- Estoque total ----------
if page == "Estoque":
    st.subheader("Estoque total")
    linhas = {"Estoque manual": d["mx"].iloc[0].reindex(R, fill_value=0.0)}
    if c["use_alts"] and len(d["a"]):
        linhas["Fazendas (aproveitado)"] = free.reindex(R, fill_value=0.0)
    if has_crates:
        linhas["Caixas"] = box.reindex(R, fill_value=0.0)
    if fboxes:
        linhas["Caixas das fazendas (aproveitado)"] = fbox.reindex(R, fill_value=0.0)
    df_tot = pd.DataFrame(linhas).T
    df_tot.loc["Total"] = df_tot.sum()
    st.dataframe(df_tot.style.format(fmt), use_container_width=True)
    st.stop()

# ---------- Resumo ----------
if page != "Resumo":
    st.stop()

st.subheader("Resumo")
items = [(k, have[k], tot[k], False) for k in R]
if c["time"]:
    items.append(("Tempo", have_h, tot_h, True))
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
            st.caption("Falta" if n > 0 else "Sobra" if n < 0 else "Exato")

if c["use_crates"] and len(d["c"]):
    with st.expander("Total das caixas"):
        for k in R:
            st.write(f"**{k}:** {fmt(box_all[k])}")

if c["use_alts"] and len(d["a"]):
    with st.expander("Total das fazendas"):
        for k in alt_cols(c):
            bruto = d["a"][k].sum()
            st.write(f"**{k}:** {fmt(bruto)} bruto → {fmt(bruto * c['pct'] / 100)} aproveitado")
