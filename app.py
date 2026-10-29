from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st
import urllib.parse

# --- DATABASE SETUP ---
DB_NAME = "mileage_tracker.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS journeys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            origin TEXT,
            destination TEXT,
            purpose TEXT,
            vehicle_reg TEXT,
            miles REAL,
            passengers INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value REAL
        )
    """)
    default_settings = [
        ('rate_tier1', 0.45),       # HMRC 45p rate
        ('rate_tier2', 0.25),       # 25p rate after threshold
        ('threshold_miles', 10000.0),
        ('passenger_rate', 0.05),   # 5p passenger top-up
    ]
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0.0

def update_setting(key, val):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = ?", (val, key))
    conn.commit()
    conn.close()

# --- APP CONFIGURATION & MODERN STYLING ---
st.set_page_config(page_title="UK Business Mileage & Tax Tracker", page_icon="🚗", layout="wide")

# Modern CSS Styling Injection (Sleek dark/light minimal UI, card shadows, rounded buttons)
st.markdown("""
    <style>
    /* Global Styling */
    .main {
        background-color: #0e1117;
        color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    h1, h2, h3 {
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        padding: 16px 20px;
        border-radius: 14px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    div[data-testid="stMetric"] label {
        color: #9ca3af !important;
        font-weight: 500;
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #f3f4f6 !important;
        font-size: 1.6rem !important;
        font-weight: 700;
    }
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #1f2937;
        padding: 6px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        color: #9ca3af;
        border-radius: 8px;
        font-weight: 600;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: white !important;
    }
    /* Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
    }
    /* Inputs */
    .stTextInput input, .stDateInput input, .stNumberInput input {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
        color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)

# App Header
st.markdown("<h1 style='text-align: center; margin-bottom: 0px;'>🚗 MileTrack UK</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #9ca3af; margin-top: 5px; margin-bottom: 25px;'>Sleek, HMRC-compliant business mileage & tax claim manager</p>", unsafe_allow_html=True)

# --- TOP NAVIGATION TABS (Mobile Optimized) ---
tabs = st.tabs([
    "📊 Dashboard",
    "➕ Log Trip",
    "🗺️ Route Planner",
    "🗑️ Manage",
    "⚙️ Rates",
    "📑 Reports"
])

RATE_TIER1 = float(get_setting('rate_tier1'))
RATE_TIER2 = float(get_setting('rate_tier2'))
THRESHOLD = float(get_setting('threshold_miles'))
PASSENGER_RATE = float(get_setting('passenger_rate'))

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("Tax Year Overview")
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM journeys ORDER BY date DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("👋 No journeys logged yet. Tap **Log Trip** above to get started!")
    else:
        total_miles = df['miles'].sum()
        
        if total_miles <= THRESHOLD:
            tier1_miles = total_miles
            tier2_miles = 0.0
            mileage_allowance = tier1_miles * RATE_TIER1
        else:
            tier1_miles = THRESHOLD
            tier2_miles = total_miles - THRESHOLD
            mileage_allowance = (tier1_miles * RATE_TIER1) + (tier2_miles * RATE_TIER2)
            
        df['passenger_allowance'] = df['miles'] * df['passengers'] * PASSENGER_RATE
        total_passenger_allowance = df['passenger_allowance'].sum()
        grand_total_claim = mileage_allowance + total_passenger_allowance
        
        # Sleek Metrics Grid
        col1, col2 = st.columns(2)
        col1.metric("Total Business Miles", f"{total_miles:,.1f} mi")
        col2.metric("Total Claimable Tax Relief", f"£{grand_total_claim:,.2f}")
        
        col3, col4 = st.columns(2)
        col3.metric("Standard AMAP Allowance", f"£{mileage_allowance:,.2f}")
        col4.metric("Passenger Top-up", f"£{total_passenger_allowance:,.2f}")
        
        st.markdown("---")
        st.subheader("Recent Journey History")
        display_df = df[['date', 'origin', 'destination', 'purpose', 'miles', 'passengers']]
        st.dataframe(display_df, use_container_width=True)

# --- TAB 2: ADD TRIP ---
with tabs[1]:
    st.subheader("Log a New Business Journey")
    st.markdown("Record your business travel details quickly and accurately.")
    
    with st.form("journey_form", clear_on_submit=True):
        j_date = st.date_input("Journey Date", datetime.today())
        origin = st.text_input("Origin (Town or Postcode)", placeholder="e.g. Melling, L31")
        destination = st.text_input("Destination (Town or Postcode)", placeholder="e.g. Manchester, M1")
        purpose = st.text_input("Business Purpose / Reason", placeholder="e.g. Client site meeting & assessment")
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            miles = st.number_input("Total Business Miles", min_value=0.1, step=0.1, value=15.0)
        with col_m2:
            is_return = st.checkbox("Return Trip (Double Mileage)", value=False)
            
        passengers = st.number_input("Business Passengers Carried", min_value=0, max_value=5, step=1)
        vehicle_reg = st.text_input("Vehicle Registration (Optional)", placeholder="e.g. AB12 CDE")
        
        submitted = st.form_submit_button("✨ Save Business Journey")
        
        if submitted:
            final_miles = miles * 2 if is_return else miles
            if not origin or not destination:
                st.error("⚠️ Please fill in both origin and destination locations.")
            else:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO journeys (date, origin, destination, purpose, vehicle_reg, miles, passengers)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (str(j_date), origin, destination, purpose, vehicle_reg, final_miles, passengers))
                conn.commit()
                conn.close()
                st.success(f"✅ Successfully logged {final_miles} miles to your business tax tracker!")

# --- TAB 3: ROUTE PLANNER ---
with tabs[2]:
    st.subheader("🗺️ Map & Route Verification")
    st.markdown("Verify your route and check driving distances before logging.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        map_origin = st.text_input("Start Location / Postcode", value="Melling, Liverpool", key="mo")
    with col_b:
        map_dest = st.text_input("End Location / Postcode", value="Manchester", key="md")
        
    if map_origin and map_dest:
        encoded_origin = urllib.parse.quote(map_origin)
        encoded_dest = urllib.parse.quote(map_dest)
        
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={encoded_origin}&destination={encoded_dest}&travelmode=driving"
        st.link_button("📍 Launch Route in Google Maps App", google_maps_url)
        
        st.markdown("<br>", unsafe_allow_html=True)
        maps_iframe = f'<iframe width="100%" height="380" style="border:0; border-radius:12px;" allowfullscreen="" loading="lazy" src="https://maps.google.com/maps?q={encoded_origin}%20to%20{encoded_dest}&output=embed"></iframe>'
        st.components.v1.html(maps_iframe, height=390)

# --- TAB 4: MANAGE ---
with tabs[3]:
    st.subheader("Manage Logged Entries")
    st.markdown("Select and remove incorrect or accidental entries.")
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT id, date, origin, destination, purpose, miles FROM journeys ORDER BY date DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("No journeys available to manage.")
    else:
        df['label'] = df['date'] + " | " + df['origin'] + " ➔ " + df['destination'] + " (" + df['miles'].astype(str) + " mi)"
        journey_to_delete = st.selectbox("Select Journey to Remove", options=df['label'].tolist())
        
        if st.button("🗑️ Delete Selected Journey", type="primary"):
            selected_id = df.loc[df['label'] == journey_to_delete, 'id'].values[0]
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("DELETE FROM journeys WHERE id = ?", (selected_id,))
            conn.commit()
            conn.close()
            st.success("Successfully deleted journey.")
            st.rerun()

# --- TAB 5: RATES & SETTINGS ---
with tabs[4]:
    st.subheader("⚙️ HMRC Allowance & Rate Settings")
    st.markdown("Customize statutory allowance rates and thresholds whenever HMRC updates them.")
    
    with st.form("settings_form"):
        new_rate1 = st.number_input("Tier 1 Rate (£/mi - First 10,000 miles)", value=RATE_TIER1, step=0.01, format="%.2f")
        new_threshold = st.number_input("Tier Threshold (miles)", value=THRESHOLD, step=500.0)
        new_rate2 = st.number_input("Tier 2 Rate (£/mi - Over Threshold)", value=RATE_TIER2, step=0.01, format="%.2f")
        new_passenger_rate = st.number_input("Passenger Top-up (£/mi per passenger)", value=PASSENGER_RATE, step=0.01, format="%.2f")
        
        if st.form_submit_button("💾 Save Settings"):
            update_setting('rate_tier1', new_rate1)
            update_setting('threshold_miles', new_threshold)
            update_setting('rate_tier2', new_rate2)
            update_setting('passenger_rate', new_passenger_rate)
            st.success("Settings updated successfully!")
            st.rerun()

# --- TAB 6: REPORTS & EXPORT ---
with tabs[5]:
    st.subheader("📑 HMRC-Ready Export")
    st.markdown("Download your complete, structured mileage log formatted for Self Assessment or company accounting.")
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM journeys", conn)
    conn.close()
    
    if df.empty:
        st.warning("No data available to export.")
    else:
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV Tax Report",
            data=csv_data,
            file_name=f"uk_mileage_report_{datetime.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
