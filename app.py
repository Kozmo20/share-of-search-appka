import streamlit as st
import pandas as pd
from pytrends.request import TrendReq
import plotly.express as px
from datetime import date
import pycountry

# --- Konfigurácia stránky ---
st.set_page_config(page_title="Share of Search Analýza", layout="wide")

# --- Funkcie na získanie zoznamov krajín a jazykov ---
@st.cache_data
def get_countries():
    """Vráti zoznam krajín s ich kódmi pre pytrends."""
    countries = {}
    for country in pycountry.countries:
        countries[country.name] = country.alpha_2
    return countries

@st.cache_data
def get_languages():
    """Vráti zoznam jazykov s ich kódmi pre pytrends."""
    languages = {}
    for lang in pycountry.languages:
        if hasattr(lang, 'alpha_2'):
            languages[lang.name] = f"{lang.alpha_2}-{lang.alpha_2.upper()}"
    languages['Slovak'] = 'sk-SK'
    languages['Czech'] = 'cs-CZ'
    languages['English'] = 'en-US'
    return dict(sorted(languages.items()))

# --- KĽÚČOVÁ ZMENA: Funkcia pre sťahovanie dát s CACHOVANÍM ---
# Tento "dekorátor" hovorí Streamlitu, aby si pamätal výsledok tejto funkcie.
# ttl="6h" znamená, že si bude výsledok pamätať maximálne 6 hodín, potom stiahne čerstvé dáta.
@st.cache_data(ttl="6h")
def fetch_trends_data(keywords, timeframe, country_code, lang_code):
    """
    Sťahuje dáta z Google Trends. Výsledky sú cachované.
    """
    st.info("Sťahujem čerstvé dáta z Google Trends... Tento proces môže chvíľu trvať.")
    pytrends = TrendReq(hl=lang_code, tz=360, timeout=(10, 25))
    pytrends.build_payload(kw_list=list(keywords), cat=0, timeframe=timeframe, geo=country_code, gprop='')
    return pytrends.interest_over_time()

# --- Úvod aplikácie ---
st.title("📊 Pokročilá Share of Search Analýza")
st.markdown("Verzia 2.1 - S inteligentným cachovaním na zníženie chýb.")

# --- Vstupné polia v bočnom paneli ---
with st.sidebar:
    st.header("⚙️ Nastavenia analýzy")

    keywords_input = st.text_area(
        "Zadajte kľúčové slová (oddelené čiarkou)", 
        "Adidas, Nike, Reebok, Puma"
    )
    keyword_list = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]

    country_dict = get_countries()
    lang_dict = get_languages()
    
    selected_country_name = st.selectbox(
        "Zvoľte krajinu",
        options=list(country_dict.keys()),
        index=list(country_dict.keys()).index("Slovakia")
    )
    country_code = country_dict[selected_country_name]

    selected_lang_name = st.selectbox(
        "Zvoľte jazyk",
        options=list(lang_dict.keys()),
        index=list(lang_dict.keys()).index("Slovak")
    )
    lang_code = lang_dict[selected_lang_name]

    st.markdown("### Časové obdobie")
    start_date = st.date_input("Dátum od", date(date.today().year - 5, 1, 1))
    end_date = st.date_input("Dátum do", date.today())
    timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    
    run_button = st.button(label="Spustiť analýzu")

# --- Hlavná časť aplikácie ---
if run_button:
    if not keyword_list:
        st.warning("Prosím, zadajte aspoň jedno kľúčové slovo.")
    elif len(keyword_list) > 5:
        st.warning("Google Trends umožňuje priame porovnanie maximálne 5 kľúčových slov naraz.")
    else:
        try:
            # Volanie našej novej cachovanej funkcie
            # Dôležité: keyword_list meníme na tuple(), lebo listy nie sú pre cache "hashable"
            interest_over_time_df = fetch_trends_data(tuple(keyword_list), timeframe, country_code, lang_code)

            if interest_over_time_df.empty:
                st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte kľúčové slová alebo skúste iné časové obdobie.")
            else:
                st.success("Dáta úspešne spracované!")
                if 'isPartial' in interest_over_time_df.columns:
                    interest_over_time_df = interest_over_time_df.drop(columns=['isPartial'])
                
                interest_over_time_df['Total'] = interest_over_time_df.sum(axis=1)
                sos_df = pd.DataFrame(index=interest_over_time_df.index)
                for kw in keyword_list:
                    sos_df[kw] = interest_over_time_df.apply(
                        lambda row: (row[kw] / row['Total']) * 100 if row['Total'] > 0 else 0, axis=1
                    )
                sos_df.dropna(inplace=True)

                st.header("Porovnanie Share of Search: Aktuálny vs. Predošlý Rok")
                current_year = end_date.year
                previous_year = current_year - 1
                sos_current_year = sos_df[sos_df.index.year == current_year].mean()
                sos_previous_year = sos_df[sos_df.index.year == previous_year].mean()

                col1, col2 = st.columns(2)
                with col1:
                    if not sos_current_year.empty and sos_current_year.sum() > 0:
                        fig_pie_current = px.pie(values=sos_current_year.values, names=sos_current_year.index, title=f'Priemerný SoS za rok {current_year}', hole=.4)
                        st.plotly_chart(fig_pie_current, use_container_width=True)
                    else:
                        st.info(f"Pre rok {current_year} nie sú k dispozícii žiadne dáta.")
                with col2:
                    if not sos_previous_year.empty and sos_previous_year.sum() > 0:
                        fig_pie_previous = px.pie(values=sos_previous_year.values, names=sos_previous_year.index, title=f'Priemerný SoS za rok {previous_year}', hole=.4)
                        st.plotly_chart(fig_pie_previous, use_container_width=True)
                    else:
                        st.info(f"Pre rok {previous_year} nie sú k dispozícii žiadne dáta.")

                st.header("Vývoj Share of Search v čase (Mesačne)")
                sos_monthly = sos_df.resample('M').mean()
                fig_bar = px.bar(sos_monthly, x=sos_monthly.index, y=sos_monthly.columns, title=f'Mesačný vývoj SoS pre "{keywords_input}"', labels={'value': 'Share of Search (%)', 'index': 'Mesiac', 'variable': 'Kľúčové slovo'}, template='plotly_white')
                st.plotly_chart(fig_bar, use_container_width=True)

                st.header("Ročný vývoj a medziročné porovnanie (YoY)")
                sos_yearly = sos_df.resample('Y').mean()
                sos_yearly.index = sos_yearly.index.year
                yoy_change = sos_yearly.pct_change() * 100
                display_df = pd.DataFrame()
                for year in sos_yearly.index:
                    display_df[f'SoS {year}'] = sos_yearly.loc[year]
                    if year in yoy_change.index:
                         display_df[f'YoY {year}'] = yoy_change.loc[year]
                    else:
                         display_df[f'YoY {year}'] = None
                sorted_columns = sorted(display_df.columns, key=lambda x: (x.split(' ')[1], x.split(' ')[0]), reverse=True)
                display_df = display_df[sorted_columns]
                sos_cols = [col for col in display_df.columns if 'SoS' in col]
                yoy_cols = [col for col in display_df.columns if 'YoY' in col]
                st.dataframe(display_df.style.background_gradient(cmap='Greens', subset=sos_cols, vmin=0).background_gradient(cmap='RdYlGn', subset=yoy_cols, vmin=-100, vmax=100).format("{:.2f}%", subset=yoy_cols, na_rep="-").format("{:.2f}", subset=sos_cols))
                st.caption("SoS = priemerný ročný Share of Search. YoY = medziročná percentuálna zmena oproti predošlému roku.")

        except Exception as e:
            st.error(f"Vyskytla sa chyba: {e}")
            if '429' in str(e):
                st.warning("Chyba 429 (príliš veľa požiadaviek) je pretrvávajúci problém na zdieľaných IP adresách. Vďaka cachovaniu by sa mala objavovať menej často. Ak pretrváva, skúste to znova neskôr, alebo reštartujte aplikáciu ('...' -> 'Reboot').")
