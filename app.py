import streamlit as st
import pandas as pd
from pytrends.request import TrendReq
import plotly.express as px
from datetime import date, timedelta

# --- Konfigurácia stránky a základný popis ---
st.set_page_config(page_title="Share of Search Analýza", layout="wide")

st.title("🚀 Automatizovaná Share of Search Analýza")
st.markdown("""
Táto aplikácia využíva neoficiálne API pre Google Trends (`pytrends`) na stiahnutie dát o popularite hľadania. 
Následne vypočíta a vizualizuje "Share of Search" pre zadané kľúčové slová.

**Upozornenie:** Keďže Google Trends nemá oficiálne API, pri príliš častom používaní môže Google dočasne zablokovať vašu IP adresu (chyba 429).
""")

# --- Vstupné polia v bočnom paneli (sidebar) ---
with st.sidebar:
    st.header("⚙️ Nastavenia analýzy")

    # Vstup pre kľúčové slová
    keywords_input = st.text_area(
        "Zadajte kľúčové slová (oddelené čiarkou)", 
        "Fakty o počasí, predpoveď počasia, meteoradar"
    )
    keyword_list = [kw.strip() for kw in keywords_input.split(',')]

    # Vstup pre krajinu
    country = st.text_input("Kód krajiny (napr. SK, CZ, US)", "SK").upper()

    # Vstup pre jazyk
    language = st.text_input("Kód jazyka (napr. sk-SK, cs-CZ)", "sk-SK")

    # Vstup pre časové obdobie
    st.markdown("### Časové obdobie")
    start_date = st.date_input("Dátum od", date.today() - timedelta(days=365))
    end_date = st.date_input("Dátum do", date.today())
    timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"

    # Vstup pre granularitu
    granularity = st.selectbox(
        "Zvoľte granularitu zobrazenia",
        ('Mesačne', 'Štvrťročne', 'Ročne'),
        index=0 # Predvolená hodnota je Mesačne
    )

    # Tlačidlo na spustenie analýzy
    run_button = st.button(label="Spustiť analýzu")


# --- Hlavná časť aplikácie ---

if run_button:
    if not keyword_list or keyword_list == ['']:
        st.warning("Prosím, zadajte aspoň jedno kľúčové slovo.")
    elif len(keyword_list) > 5:
        st.warning("Google Trends umožňuje priame porovnanie maximálne 5 kľúčových slov naraz.")
    else:
        try:
            with st.spinner('Sťahujem a spracovávam dáta z Google Trends...'):
                # Inicializácia pytrends
                pytrends = TrendReq(hl=language, tz=360) # tz=360 je pre UTC

                # Vytvorenie požiadavky na dáta
                pytrends.build_payload(
                    kw_list=keyword_list,
                    cat=0,
                    timeframe=timeframe,
                    geo=country,
                    gprop=''
                )

                # Získanie dát o záujme v čase
                interest_over_time_df = pytrends.interest_over_time()

                if interest_over_time_df.empty:
                    st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte kľúčové slová alebo skúste iné časové obdobie.")
                else:
                    # Odstránenie stĺpca 'isPartial', ak existuje
                    if 'isPartial' in interest_over_time_df.columns:
                        interest_over_time_df = interest_over_time_df.drop(columns=['isPartial'])

                    # --- VÝPOČET SHARE OF SEARCH ---
                    # 1. Súčet všetkých hodnôt v riadku
                    interest_over_time_df['Total'] = interest_over_time_df.sum(axis=1)

                    # 2. Vytvorenie nového DataFrame pre Share of Search
                    sos_df = pd.DataFrame(index=interest_over_time_df.index)
                    for kw in keyword_list:
                        sos_df[kw] = (interest_over_time_df[kw] / interest_over_time_df['Total']) * 100

                    # 3. Odstránenie riadkov, kde bol súčet 0, aby sa predišlo NaN hodnotám
                    sos_df.dropna(inplace=True)

                    # --- Zmena granularity dát (resampling) ---
                    resample_map = {
                        'Mesačne': 'M',
                        'Štvrťročne': 'Q',
                        'Ročne': 'A'
                    }
                    resample_code = resample_map[granularity]

                    # Priemerovanie dát podľa zvolenej granularity
                    sos_resampled_df = sos_df.resample(resample_code).mean()


                    st.success("Dáta úspešne spracované!")

                    # --- VIZUALIZÁCIA ---
                    st.header("Graf Share of Search")

                    # Vytvorenie grafu pomocou Plotly Express
                    fig = px.area(
                        sos_resampled_df,
                        x=sos_resampled_df.index,
                        y=sos_resampled_df.columns,
                        title=f'Share of Search pre "{keywords_input}" v krajine {country}',
                        labels={'value': 'Share of Search (%)', 'index': 'Dátum', 'variable': 'Kľúčové slovo'},
                        template='plotly_white'
                    )
                    fig.update_layout(yaxis_range=[0, 100]) # Os Y bude vždy od 0 do 100

                    st.plotly_chart(fig, use_container_width=True)

                    # --- ZOBRAZENIE DÁT ---
                    st.header("Podkladové dáta (Share of Search %)")
                    st.dataframe(sos_resampled_df.style.format("{:.2f} %"))

                    st.download_button(
                        label="Stiahnuť dáta ako CSV",
                        data=sos_resampled_df.to_csv().encode('utf-8'),
                        file_name=f'share_of_search_{country}.csv',
                        mime='text/csv',
                    )

        except Exception as e:
            st.error(f"Vyskytla sa chyba: {e}")
            st.info("Najčastejšou chybou je 'response code 429'. To znamená, že ste odoslali príliš veľa požiadaviek v krátkom čase. Skúste to znova o pár minút.")
