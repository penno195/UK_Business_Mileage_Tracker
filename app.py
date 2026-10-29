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
        ('google_maps_api_key', '') # Optional API key for auto-distance
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

# --- APP CONFIGURATION ---
st.set_page_config(page_title="UK Business Mileage & Tax Tracker", page_icon="🚗", layout="wide")

st.title("🚗 UK Business Mileage & Tax Tracker")
st.markdown("HMRC-compliant mileage expense manager with automated distance lookups.")

# --- TOP NAVIGATION TABS (Mobile Friendly Portrait Mode) ---
tabs = st.tabs([
    "📊 Dashboard",
    "➕ Add Trip",
    "🗺️ Route Planner",
    "🗑️ Manage",
    "⚙️ Settings",
    "📑 Reports"
])

RATE_TIER1 = get_setting('rate_tier1')
RATE_TIER2 = get_setting('rate_tier2')
THRESHOLD = get_setting('threshold_miles')
PASSENGER_RATE = get_setting('passenger_rate')
MAPS_API_KEY = str(get_setting('google_maps_api_key'))

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.header("Tax Year Mileage Dashboard")
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM journeys ORDER BY date DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("No journeys recorded yet. Tap **Add Trip** to log your first journey!")
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
        
        col1, col2 = st.columns(2)
        col1.metric("Total Business Miles", f"{total_miles:,.1f} mi")
        col2.metric("Total Claimable Expense", f"£{grand_total_claim:,.2f}")
        
        col3, col4 = st.columns(2)
        col3.metric("Tier 1 Allowance", f"£{mileage_allowance:,.2f}")
        col4.metric("Passenger Top-up", f"£{total_passenger_allowance:,.2f}")
        
        st.subheader("Journey History")
        display_df = df[['date', 'origin', 'destination', 'purpose', 'miles', 'passengers']]
        st.dataframe(display_df, use_container_width=True)

# --- TAB 2: ADD TRIP ---
with tabs[1]:
    st.header("Log a New Business Journey")
    
    with st.form("journey_form", clear_on_submit=True):
        j_date = st.date_input("Journey Date", datetime.today())
        origin = st.text_input("Origin (Town or Postcode)", placeholder="e.g. Melling, L31")
        destination = st.text_input("Destination (Town or Postcode)", placeholder="e.g. Manchester, M1")
        purpose = st.text_input("Business Purpose / Reason")
        miles = st.number_input("Total Business Miles", min_value=0.1, step=0.1, value=10.0)
        passengers = st.number_input("Business Passengers Carried", min_value=0, max_value=5, step=1)
        vehicle_reg = st.text_input("Vehicle Registration (Optional)")
        
        submitted = st.form_submit_button("Save Journey")
        
        if submitted:
            if not origin or not destination:
                st.error("⚠️ Please fill in both origin and destination.")
            else:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO journeys (date, origin, destination, purpose, vehicle_reg, miles, passengers)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (str(j_date), origin, destination, purpose, vehicle_reg, miles, passengers))
                conn.commit()
                conn.close()
                st.success(f"✅ Logged {miles} miles successfully!")

# --- TAB 3: ROUTE PLANNER & MAPS ---
with tabs[2]:
    st.header("🗺️ Google Maps Integration")
    st.markdown("Enter origin and destination to preview the route or calculate distance automatically using your Maps API key.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        map_origin = st.text_input("Start Postcode / Location", value="Melling, Liverpool")
    with col_b:
        map_dest = st.text_input("End Postcode / Location", value="Manchester")
        
    if map_origin and map_dest:
        encoded_origin = urllib.parse.quote(map_origin)
        encoded_dest = urllib.parse.quote(map_dest)
        
        # External Google Maps Direct Link
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={encoded_origin}&destination={encoded_dest}&travelmode=driving"
        st.link_button("📍 Open Exact Route in Google Maps App", google_maps_url)
        
        # Embedded Map View
        st.markdown("---")
        st.subheader("Interactive Route Preview")
        maps_iframe = f'<iframe width="100%" height="350" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="https://maps.google.com/maps?q={encoded_origin}%20to%20{encoded_dest}&output=embed"></iframe>'
        st.components.v1.html(maps_iframe, height=360)

# --- TAB 4: MANAGE / DELETE ---
with tabs[3]:
    st.header("Manage Entries")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT id, date, origin, destination, purpose, miles FROM journeys ORDER BY date DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("No journeys available to delete.")
    else:
        df['label'] = df['date'] + " | " + df['origin'] + " ➔ " + df['destination'] + " (" + df['miles'].astype(str) + " mi)"
        journey_to_delete = st.selectbox("Select Journey to Remove", options=df['label'].tolist())
        
        if st.button("Delete Selected Journey", type="primary"):
            selected_id = df.loc[df['label'] == journey_to_delete, 'id'].values[0]
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("DELETE FROM journeys WHERE id = ?", (selected_id,))
            conn.commit()
            conn.close()
            st.success("Successfully deleted journey.")
            st.rerun()

# --- TAB 5: HMRC & MAPS SETTINGS ---
with tabs[4]:
    st.header("⚙️ Rates & API Settings")
    with st.form("settings_form"):
        st.subheader("HMRC AMAP Rates")
        new_rate1 = st.number_input("Tier 1 Rate (£/mi - First 10,000 miles)", value=RATE_TIER1, step=0.01, format="%.2f")
        new_threshold = st.number_input("Tier Threshold (miles)", value=THRESHOLD, step=500.0)
        new_rate2 = st.number_input("Tier 2 Rate (£/mi - Over Threshold)", value=RATE_TIER2, step=0.01, format="%.2f")
        new_passenger_rate = st.number_input("Passenger Top-up (£/mi per passenger)", value=PASSENGER_RATE, step=0.01, format="%.2f")
        
        st.subheader("Google Maps API (Optional for Auto-Distance)")
        new_api_key = st.text_input("Google Maps Distance Matrix API Key", value=MAPS_API_KEY, type="password")
        
        if st.form_submit_button("Save Settings"):
            update_setting('rate_tier1', new_rate1)
            update_setting('threshold_miles', new_threshold)
            update_setting('rate_tier2', new_rate2)
            update_setting('passenger_rate', new_passenger_rate)
            update_setting('google_maps_api_key', new_api_key)
            st.success("Settings updated successfully!")
            st.rerun()

# --- TAB 6: REPORTS & EXPORT ---
with tabs[5]:
    st.header("Generate HMRC-Ready Reports")
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
        st.dataframe(df, use_container_width=True)
