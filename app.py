from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

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
            start_odo REAL,
            end_odo REAL,
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
      ("rate_tier1", 0.45),  # Standard HMRC 45p rate
      ("rate_tier2", 0.25),  # 25p rate after threshold
      ("threshold_miles", 10000.0),
      ("passenger_rate", 0.05),  # 5p passenger top-up
  ]
  for key, val in default_settings:
    c.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val)
    )
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
st.set_page_config(
    page_title="UK Business Mileage & Tax Tracker", page_icon="🚗", layout="wide"
)

st.title("🚗 UK Business Mileage & Tax Tracker")
st.markdown(
    "HMRC-compliant mileage expense and tax claim manager designed for mobile"
    " use."
)

# Sidebar Navigation
st.sidebar.title("Menu")
menu = st.sidebar.radio(
    "Go to",
    [
        "📊 Dashboard & Summary",
        "➕ Add Journey",
        "🗑️ Manage / Delete Journeys",
        "⚙️ HMRC Rate Manager",
        "📑 Reports & Export",
    ],
)

RATE_TIER1 = get_setting("rate_tier1")
RATE_TIER2 = get_setting("rate_tier2")
THRESHOLD = get_setting("threshold_miles")
PASSENGER_RATE = get_setting("passenger_rate")

# --- 1. DASHBOARD & SUMMARY ---
if menu == "📊 Dashboard & Summary":
  st.header("Tax Year Mileage Dashboard")

  conn = sqlite3.connect(DB_NAME)
  df = pd.read_sql("SELECT * FROM journeys ORDER BY date DESC", conn)
  conn.close()

  if df.empty:
    st.info(
        "No journeys recorded yet. Tap **Add Journey** in the menu to log your"
        " first trip!"
    )
  else:
    total_miles = df["miles"].sum()

    if total_miles <= THRESHOLD:
      tier1_miles = total_miles
      tier2_miles = 0.0
      mileage_allowance = tier1_miles * RATE_TIER1
    else:
      tier1_miles = THRESHOLD
      tier2_miles = total_miles - THRESHOLD
      mileage_allowance = (
          (tier1_miles * RATE_TIER1) + (tier2_miles * RATE_TIER2)
      )

    df["passenger_allowance"] = (
        df["miles"] * df["passengers"] * PASSENGER_RATE
    )
    total_passenger_allowance = df["passenger_allowance"].sum()
    grand_total_claim = mileage_allowance + total_passenger_allowance

    # Metrics Layout (Mobile Stackable)
    col1, col2 = st.columns(2)
    col1.metric("Total Business Miles", f"{total_miles:,.1f} mi")
    col2.metric("Total Claimable Expense", f"£{grand_total_claim:,.2f}")

    col3, col4 = st.columns(2)
    col3.metric(
        "Tier 1 Allowance",
        f"£{mileage_allowance:,.2f}",
        help=f"First {int(THRESHOLD):,} miles @ £{RATE_TIER1}/mi",
    )
    col4.metric("Passenger Top-up", f"£{total_passenger_allowance:,.2f}")

    st.subheader("Journey History")
    # Display cleaner columns on mobile
    display_df = df[
        [
            "date",
            "origin",
            "destination",
            "purpose",
            "miles",
            "passengers",
        ]
    ]
    st.dataframe(display_df, use_container_width=True)

# --- 2. ADD JOURNEY ---
elif menu == "➕ Add Journey":
  st.header("Log a New Business Journey")

  with st.form("journey_form", clear_on_submit=True):
    j_date = st.date_input("Journey Date", datetime.today())
    origin = st.text_input("Origin (e.g., Melling, Liverpool)")
    destination = st.text_input(
        "Destination (e.g., Manchester Client Site)"
    )
    purpose = st.text_input("Business Purpose / Reason")
    vehicle_reg = st.text_input("Vehicle Registration (Optional)")

    col1, col2 = st.columns(2)
    with col1:
      start_odo = st.number_input(
          "Odometer Start (mi)", min_value=0.0, step=1.0, value=0.0
      )
    with col2:
      end_odo = st.number_input(
          "Odometer End (mi)", min_value=0.0, step=1.0, value=0.0
      )

    passengers = st.number_input(
        "Business Passengers Carried", min_value=0, max_value=5, step=1
    )

    # Live Preview Calculation inside form feedback
    if end_odo > start_odo:
      st.success(f"Preview: This trip is **{end_odo - start_odo} miles**.")

    submitted = st.form_submit_button("Save Journey")

    if submitted:
      if end_odo <= start_odo:
        st.error(
            "⚠️ Odometer End must be strictly greater than Odometer Start."
        )
      elif not origin or not destination:
        st.error("⚠️ Please fill in both origin and destination locations.")
      else:
        miles = end_odo - start_odo
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            """
                    INSERT INTO journeys (date, origin, destination, purpose, vehicle_reg, start_odo, end_odo, miles, passengers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            (
                str(j_date),
                origin,
                destination,
                purpose,
                vehicle_reg,
                start_odo,
                end_odo,
                miles,
                passengers,
            ),
        )
        conn.commit()
        conn.close()
        st.success(
            f"✅ Successfully logged trip: {miles} miles recorded and saved!"
        )

# --- 3. MANAGE / DELETE JOURNEYS ---
elif menu == "🗑️ Manage / Delete Journeys":
  st.header("Manage or Remove Entries")
  st.markdown(
      "Select a logged journey below to delete it if it was entered in error."
  )

  conn = sqlite3.connect(DB_NAME)
  df = pd.read_sql(
      "SELECT id, date, origin, destination, purpose, miles FROM journeys ORDER"
      " BY date DESC",
      conn,
  )
  conn.close()

  if df.empty:
    st.info("No journeys available to delete.")
  else:
    # Create descriptive labels for selection box
    df["label"] = (
        df["date"]
        + " | "
        + df["origin"]
        + " ➔ "
        + df["destination"]
        + " ("
        + df["miles"].astype(str)
        + " mi)"
    )
    journey_to_delete = st.selectbox(
        "Select Journey to Remove", options=df["label"].tolist()
    )

    if st.button("Delete Selected Journey", type="primary"):
      selected_id = df.loc[df["label"] == journey_to_delete, "id"].values[0]
      conn = sqlite3.connect(DB_NAME)
      c = conn.cursor()
      c.execute("DELETE FROM journeys WHERE id = ?", (selected_id,))
      conn.commit()
      conn.close()
      st.success("Successfully deleted the selected journey.")
      st.rerun()

# --- 4. HMRC RATE MANAGER ---
elif menu == "⚙️ HMRC Rate Manager":
  st.header("HMRC Allowance Rate Manager")
  st.markdown(
      "Update statutory AMAP rates whenever HMRC thresholds change."
  )

  with st.form("rate_form"):
    new_rate1 = st.number_input(
        "Tier 1 Rate (£/mile - First 10,000 miles)",
        value=RATE_TIER1,
        step=0.01,
        format="%.2f",
    )
    new_threshold = st.number_input(
        "Tier Threshold (miles)", value=THRESHOLD, step=500.0
    )
    new_rate2 = st.number_input(
        "Tier 2 Rate (£/mile - Over Threshold)",
        value=RATE_TIER2,
        step=0.01,
        format="%.2f",
    )
    new_passenger_rate = st.number_input(
        "Passenger Top-up Rate (£/mile per passenger)",
        value=PASSENGER_RATE,
        step=0.01,
        format="%.2f",
    )

    update_submitted = st.form_submit_button("Update Rates")

    if update_submitted:
      update_setting("rate_tier1", new_rate1)
      update_setting("threshold_miles", new_threshold)
      update_setting("rate_tier2", new_rate2)
      update_setting("passenger_rate", new_passenger_rate)
      st.success("HMRC rates updated successfully across the app!")
      st.rerun()

# --- 5. REPORTS & EXPORT ---
elif menu == "📑 Reports & Export":
  st.header("Generate HMRC-Ready Reports")
  st.markdown(
      "Download your complete mileage log formatted for Self Assessment."
  )

  conn = sqlite3.connect(DB_NAME)
  df = pd.read_sql("SELECT * FROM journeys", conn)
  conn.close()

  if df.empty:
    st.warning("No data available to export.")
  else:
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV Tax Report",
        data=csv_data,
        file_name=f"uk_mileage_report_{datetime.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
    )

    st.subheader("Data Preview")
    st.dataframe(df, use_container_width=True)
