from datetime import datetime
import io
import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE SETUP ---
DB_NAME = "mileage_tracker.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Journeys Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS journeys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            origin TEXT,
            destination TEXT,
            purpose TEXT,
            vehicle_reg TEXT,
            start_odo REAL,
            end_odo REAL,
            miles REAL,
            passengers INTEGER
        )
    """)
    # Settings Table for HMRC Rates (allows future-proofing updates)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value REAL
        )
    """)
    # Insert default 2026/27 HMRC rates if not present
    default_settings = [
        ('rate_tier1', 0.55),       # 55p per mile for first 10,000 miles
        ('rate_tier2', 0.25),       # 25p per mile thereafter
        ('threshold_miles', 10000.0),
        ('passenger_rate', 0.05)    # 5p per passenger per mile
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

st.title("🚗 UK Business Mileage & HMRC Tax Claim App")
st.markdown("Track your business journeys, calculate exact tax reliefs using HMRC AMAP thresholds, and generate reports instantly.")

# Sidebar Navigation
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Go to", [
    "📊 Dashboard & Summary",
    "➕ Add Journey",
    "⚙️ HMRC Rate Manager",
    "📑 Reports & Export"
])

# Fetch current HMRC Rates from DB
RATE_TIER1 = get_setting('rate_tier1')
RATE_TIER2 = get_setting('rate_tier2')
THRESHOLD = get_setting('threshold_miles')
PASSENGER_RATE = get_setting('passenger_rate')

# --- 1. DASHBOARD & SUMMARY ---
if menu == "📊 Dashboard & Summary":
    st.header("Tax Year Mileage Dashboard")
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM journeys ORDER BY date DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("No journeys recorded yet. Head over to **Add Journey** to log your first trip!")
    else:
        total_miles = df['miles'].sum()
        
        # Calculate tiered allowance
        if total_miles <= THRESHOLD:
            tier1_miles = total_miles
            tier2_miles = 0.0
            mileage_allowance = tier1_miles * RATE_TIER1
        else:
            tier1_miles = THRESHOLD
            tier2_miles = total_miles - THRESHOLD
            mileage_allowance = (tier1_miles * RATE_TIER1) + (tier2_miles * RATE_TIER2)
            
        # Calculate passenger allowance
        df['passenger_allowance'] = df['miles'] * df['passengers'] * PASSENGER_RATE
        total_passenger_allowance = df['passenger_allowance'].sum()
        grand_total_claim = mileage_allowance + total_passenger_allowance
        
        # Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Business Miles", f"{total_miles:,.1f} mi")
        col2.metric("Tier 1 Allowance (45p/55p)", f"£{mileage_allowance:,.2f}")
        col3.metric("Passenger Top-up", f"£{total_passenger_allowance:,.2f}")
        col4.metric("Total Claimable Expense", f"£{grand_total_claim:,.2f}")
        
        st.subheader("Recent Journey Logs")
        st.dataframe(df, use_container_width=True)

# --- 2. ADD JOURNEY ---
elif menu == "➕ Add Journey":
    st.header("Log a New Business Journey")
    
    with st.form("journey_form"):
        col1, col2 = st.columns(2)
        with col1:
            j_date = st.date_input("Journey Date", datetime.today())
            origin = st.text_input("Origin (e.g., Melling, Liverpool)")
            destination = st.text_input("Destination (e.g., Manchester Client Site)")
            vehicle_reg = st.text_input("Vehicle Registration (Optional)")
        with col2:
            purpose = st.text_input("Business Purpose / Reason")
            start_odo = st.number_input("Odometer Start (miles)", min_value=0.0, step=1.0)
            end_odo = st.number_input("Odometer End (miles)", min_value=0.0, step=1.0)
            passengers = st.number_input("Business Passengers Carried", min_value=0, max_value=5, step=1)
            
        submitted = st.form_submit_button("Save Journey")
        
        if submitted:
            if end_odo <= start_odo:
                st.error("Odometer End must be greater than Odometer Start.")
            else:
                miles = end_odo - start_odo
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO journeys (date, origin, destination, purpose, vehicle_reg, start_odo, end_odo, miles, passengers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(j_date), origin, destination, purpose, vehicle_reg, start_odo, end_odo, miles, passengers))
                conn.commit()
                conn.close()
                st.success(f"Successfully logged journey: {miles} miles recorded and saved!")

# --- 3. HMRC RATE MANAGER ---
elif menu == "⚙️ HMRC Rate Manager":
    st.header("HMRC Allowance Rate Manager")
    st.markdown("Update tax rates whenever the UK government or HMRC releases new AMAP thresholds.")
    
    with st.form("rate_form"):
        new_rate1 = st.number_input("Tier 1 Rate (£ per mile - First 10,000 miles)", value=RATE_TIER1, step=0.01, format="%.2f")
        new_threshold = st.number_input("Tier Threshold (miles)", value=THRESHOLD, step=500.0)
        new_rate2 = st.number_input("Tier 2 Rate (£ per mile - Over Threshold)", value=RATE_TIER2, step=0.01, format="%.2f")
        new_passenger_rate = st.number_input("Passenger Top-up Rate (£ per mile per passenger)", value=PASSENGER_RATE, step=0.01, format="%.2f")
        
        update_submitted = st.form_submit_button("Update Rates")
        
        if update_submitted:
            update_setting('rate_tier1', new_rate1)
            update_setting('threshold_miles', new_threshold)
            update_setting('rate_tier2', new_rate2)
            update_setting('passenger_rate', new_passenger_rate)
            st.success("HMRC allowance rates updated successfully across the entire application!")
            st.rerun()

# --- 4. REPORTS & EXPORT ---
elif menu == "📑 Reports & Export":
    st.header("Generate HMRC-Ready Reports")
    st.markdown("Download your complete mileage log formatted for Self Assessment or corporate accounting.")
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM journeys", conn)
    conn.close()
    
    if df.empty:
        st.warning("No data available to export.")
    else:
        # CSV Export Button
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV Report",
            data=csv_data,
            file_name=f"uk_mileage_report_{datetime.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )
        
        # Summary View for Reviewing
        st.subheader("Export Preview")
        st.dataframe(df, use_container_width=True)
