import streamlit as st
import pandas as pd
import requests
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(layout='wide')

# Define a secret password
PASSWORD = "1234"

# Create a session state variable for authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Login form
if not st.session_state.authenticated:
    st.title("🔒 Login Required")
    password_input = st.text_input("Enter the password:", type="password")

    if st.button("Login"):
        if password_input == PASSWORD:
            st.session_state.authenticated = True
            st.success("✅ Authentication successful!")
            st.rerun()  # ✅ Refresh to show the app
        else:
            st.error("❌ Incorrect password! Try again.")

    # 🚨 **IMPORTANT: Stop execution here if the user is not logged in**
    st.stop()

# ✅ If user is authenticated, display the app
#st.title("🎉 Welcome to the Drug Lookup App!")

 
 

drugs = pd.read_excel("RxNorm drug list.xlsx")
brands = pd.read_csv("brandname_rxcui.csv")

# ✅ Fetch Clinical Trials Data
def fetch_clinical_trials(drug_name):
    base_url = f'https://clinicaltrials.gov/api/v2/studies'
    
    params = {
        'query.term': drug_name,
        'pageSize': 100,  # Limit results for performance
        'format': 'json'
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        studies = data.get('studies', [])

        records = []
        for study in studies:
            protocol_section = study.get('protocolSection', {})
            identification_module = protocol_section.get('identificationModule', {})
            status_module = protocol_section.get('statusModule', {})
            conditions_module = protocol_section.get('conditionsModule', {})
            design_module = protocol_section.get('designModule', {})

            nct_id = identification_module.get('nctId', 'N/A')
            title = identification_module.get('briefTitle', 'N/A')
            study_url = f'https://clinicaltrials.gov/study/{nct_id}?term={nct_id}&rank=1'

            record = {
                'Drug Name': drug_name,
                'NCT ID': nct_id,
                'Study Title': title,
                'Title': study_url,  # Raw URL (formatted as a link)
                'Status': status_module.get('overallStatus', 'N/A'),
                'Start Date': status_module.get('startDateStruct', {}).get('date', 'N/A'),
                'Completion Date': status_module.get('completionDateStruct', {}).get('date', 'N/A'),
                'Conditions': ', '.join(conditions_module.get('conditions', [])),
                'Study Type': design_module.get('studyType', 'N/A'),
                'Phase': ', '.join(design_module.get('phases', [])),
                'Enrollment': design_module.get('enrollmentInfo', {}).get('count', 'N/A')
            }
            records.append(record)

        return pd.DataFrame(records)

    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Failed to fetch clinical trials for **{drug_name}**. Error: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Unexpected error while fetching trials for **{drug_name}**: {e}")
        return pd.DataFrame()
        
def fetch_openfda_details(drug_name):

    api_url = f'https://api.fda.gov/drug/label.json?search=openfda.generic_name:"{drug_name}"+OR+openfda.brand_name:"{drug_name}"&limit=10&sort=effective_time:desc'

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an error for non-200 responses

        data = response.json()

        if "results" in data and data["results"]:
            results_list = []

            for result in data["results"]:  # Iterate over all fetched records
                openfda = result.get("openfda", {})
                # Convert 'effective_time' to proper date format
                approval_date = result.get("effective_time", "N/A")
                if approval_date != "N/A":
                    try:
                        approval_date = pd.to_datetime(approval_date, format="%Y%m%d").date()  # Convert YYYYMMDD to date
                    except Exception:
                        approval_date = "Invalid Date"  # Handle errors gracefully

                results_list.append({
                    "Generic Name": openfda.get("generic_name", ["N/A"])[0],
                    "Brand Name": openfda.get("brand_name", ["N/A"])[0],
                    "Manufacturer": openfda.get("manufacturer_name", ["N/A"])[0],
                    "Approval Date": approval_date,
                    "Indication": result.get("indications_and_usage", ["N/A"])[0] if "indications_and_usage" in result else "N/A",
                    "Mechanism of Action": result.get("mechanism_of_action", ["N/A"])[0] if "mechanism_of_action" in result else "N/A",
                    "Dose/Strength": result.get("dosage_and_administration", ["N/A"])[0] if "dosage_and_administration" in result else "N/A",
                    "Formulation": result.get("dosage_form", "N/A"),
                    "Boxed Warning": result.get("boxed_warning", ["N/A"])[0] if "boxed_warning" in result else "N/A",
                    "Biosimilar": openfda.get("product_type", ["N/A"])[0],
                    "Pediatric Use": result.get("pediatric_use", ["N/A"])[0] if "pediatric_use" in result else "N/A",
                })

            return pd.DataFrame(results_list)  # ✅ Properly structured DataFrame
        
        else:
            return pd.DataFrame([{"Error": f"No data found for drug: {drug_name}"}])

    except requests.exceptions.RequestException as e:
        return pd.DataFrame([{"Error": f"Failed to fetch OpenFDA data for {drug_name}: {str(e)}"}])



# Load Therapeutic Class Mapping (Prevent Error if File is Missing)
try:
    tc_data = pd.read_csv('TCs.csv')
    tc_to_drugs = tc_data.groupby("Therapeutic Class")["Generic Name"].apply(lambda x: ", ".join(set(x))).to_dict()
except FileNotFoundError:
    st.warning("⚠️ Warning: 'tc_tims.csv' file not found. Tooltips may not work properly.")
    tc_to_drugs = {}

 
def fetch_rxcui(drug_name):
    url = f'https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get("idGroup", {}).get("rxnormId", [None])[0]
    
    
def fetch_therapeutic_class(rxcui, drug_name):
    url = f'https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&rela=has_therapeutic_class&classTypes=ATC1-4,VA'
    response = requests.get(url)
    therapeutic_classes = []
    if response.status_code == 200:
        data = response.json()
        for entry in data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []):
            class_type = entry.get("rxclassMinConceptItem", {}).get("classType", "N/A")
            if class_type in ["ATC1-4", "VA"]:  # Filter Only ATC1-4 & VA
                therapeutic_classes.append({
                    "Drug Name": drug_name,
                    "Therapeutic Class": entry.get("rxclassMinConceptItem", {}).get("className", "N/A"),
                    "Class Type": class_type
                })
    return pd.DataFrame(therapeutic_classes).drop_duplicates()

# Function to Display Therapeutic Classes using AgGrid with Tooltips
def display_therapeutic_classes_with_tooltip(df):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(groupable=True, value=True, enableRowGroup=True)

    # Ensure Tooltip Field is Correct
    df["Tooltip"] = df["Therapeutic Class"].map(tc_to_drugs).fillna("No data available")

    # Configure Tooltip Column
    gb.configure_column("Therapeutic Class", tooltipField="Tooltip")

    # Grid Configuration (Fixed Column Widths)
    grid_options = gb.build()
    grid_options["tooltipShowDelay"] = 0
    grid_options["tooltipHideDelay"] = 5000
    grid_options["suppressSizeToFit"] = False

    # Apply Custom CSS for Tooltips
    custom_css = {
        ".ag-tooltip": {
            "font-size": "15px",  # Increased Font Size
            "background-color": "#f9f9f9",  # Light Background
            "color": "#333333",  # Dark Text
            "padding": "5px",
            "border-radius": "16px",
            "max-width": "400px",
            "white-space": "pre-wrap",  # Proper Line Breaks
            "text-align": "left"
        }
    }

    # Display AgGrid with Fixed Width (Matches Other Tables)
    AgGrid(
        df,
        gridOptions=grid_options,
        enable_enterprise_modules=True,
        allow_unsafe_jscode=True,
        height=400,
        width=600,  # Same Width as Other Tables
        fit_columns_on_grid_load=False,
        custom_css=custom_css  # Applying tooltip styling
    )

def fetch_brand_names(rxcui, drug_name):
    url = f'https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/allrelated.json'
    response = requests.get(url)
    brands = []
    if response.status_code == 200:
        data = response.json()
        for group in data.get("allRelatedGroup", {}).get("conceptGroup", []):
            if group.get("tty") == "BN":  # BN = Brand Name
                for concept in group.get("conceptProperties", []):
                    brands.append({"Drug Name": drug_name, "Brand Name": concept.get("name", "N/A")})
    return pd.DataFrame(brands).drop_duplicates()

def fetch_moa(rxcui, drug_name):

    url = f'https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&rela=has_mechanism_of_action&classTypes=MOA'
    response = requests.get(url)
    moa = []
    if response.status_code == 200:
        data = response.json()
        for entry in data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []):
            if entry.get("rxclassMinConceptItem", {}).get("classType", "").upper() == "MOA":
                moa.append({"Drug Name": drug_name,
                    "Mechanism of Action": entry.get("rxclassMinConceptItem", {}).get("className", "N/A"),
                    "Class Type": entry.get("rxclassMinConceptItem", {}).get("classType", "N/A")
                })
    return pd.DataFrame(moa).drop_duplicates()

def fetch_indications(rxcui, drug_name):

    url = f'https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&rela=may_treat&classTypes=DISEASE'
    response = requests.get(url)
    indications = []
    if response.status_code == 200:
        data = response.json()
        for entry in data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []):
            if entry.get("rxclassMinConceptItem", {}).get("classType", "").upper() == "DISEASE":
                indications.append({"Drug Name": drug_name,
                    "Indication": entry.get("rxclassMinConceptItem", {}).get("className", "N/A"),
                    "Class Type": entry.get("rxclassMinConceptItem", {}).get("classType", "N/A")
                })
    return pd.DataFrame(indications).drop_duplicates()

def fetch_drug_details(drug_name):
    rxcui = fetch_rxcui(drug_name)
    if not rxcui:
        return None

    details = {
        "Brand Names": fetch_brand_names(rxcui, drug_name),
        "Mechanism of Action": fetch_moa(rxcui, drug_name),
        "Indications": fetch_indications(rxcui, drug_name),
        "Therapeutic Class": fetch_therapeutic_class(rxcui, drug_name)
    }
    return details
    
def run_app():


    st.title("Drug Database")
    #st.write("Search for drug details using ClinicalTrials and OpenFDA APIs.")
    
    # Add a radio button for search type selection
    search_type = st.radio("Search by:", ["Drug Name", "Brand Name"], horizontal=True)

    # Update options based on search type
    if search_type == "Drug Name":
        search_options = drugs["Drug name"].tolist()
    else:
            search_options = brands["Brand Name"].tolist()  # Assuming brand names are stored here

    # Search bar for the selected type
    selected_drugs = st.multiselect(
        f"Search for {search_type}s:",
        options=search_options,
        default=[]
    )

    # Tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["OpenFDA","Clinical Trials","RxNorm"])
    with tab2:

        if selected_drugs:
            all_clinical_trials = []
            for drug in selected_drugs:
                clinical_trials = fetch_clinical_trials(drug)
                if not clinical_trials.empty:
                    all_clinical_trials.append(clinical_trials)
    
            if all_clinical_trials:
                clinical_trials_df = pd.concat(all_clinical_trials, ignore_index=True)
    
                # ✅ Convert Date Columns to Datetime for Sorting
                #clinical_trials_df["Start Date"] = pd.to_datetime(clinical_trials_df["Start Date"], errors="coerce")
                #clinical_trials_df["Completion Date"] = pd.to_datetime(clinical_trials_df["Completion Date"], errors="coerce")
    
                # ✅ Arrange Filters in One Row
                col1, col2, col3 = st.columns(3)
    
                with col1:
                    status_filter = st.multiselect("Filter by Status", sorted(clinical_trials_df["Status"].dropna().unique().tolist()))
    
                with col2:
                    condition_filter = st.multiselect("Filter by Condition", sorted(clinical_trials_df["Conditions"].dropna().unique().tolist()))
    
                with col3:
                    phase_filter = st.multiselect("Filter by Phase", sorted(clinical_trials_df["Phase"].dropna().unique().tolist()))
    
                # ✅ Apply Multi-Select Filters
                if status_filter:
                    clinical_trials_df = clinical_trials_df[clinical_trials_df["Status"].isin(status_filter)]
                if condition_filter:
                    clinical_trials_df = clinical_trials_df[clinical_trials_df["Conditions"].isin(condition_filter)]
                if phase_filter:
                    clinical_trials_df = clinical_trials_df[clinical_trials_df["Phase"].isin(phase_filter)]
    
                # ✅ Display Clinical Trials Data
                st.write("### 📑 Clinical Trials Data")
                st.data_editor(
                    clinical_trials_df,
                    column_config={
                        "Title": st.column_config.LinkColumn("Study Link")
                    },
                    height=600,
                    use_container_width=True,
                    hide_index=True
                )
    
                # ✅ Add Space Before Download Button
                st.write("")
                st.write("")  # Extra spacing
    
                # ✅ Download Button
                st.download_button(
                    label="📥 Download Clinical Trials Data",
                    data=clinical_trials_df.to_csv(index=False),
                    file_name="clinical_trials_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ No clinical trials data found for the selected drugs.")
        else:
            st.warning("🔍 Please select drugs to fetch Clinical Trials data.")


    from st_aggrid import AgGrid, GridOptionsBuilder

    with tab1:
        if selected_drugs:
            all_openfda_data = []

            for drug in selected_drugs:
                openfda_df = fetch_openfda_details(drug)
                if not openfda_df.empty:
                    openfda_df["Drug Name"] = drug  # Ensure we keep track of drug names
                    all_openfda_data.append(openfda_df)

            if all_openfda_data:
                combined_openfda_df = pd.concat(all_openfda_data, ignore_index=True)

                # ✅ Fix column order
                expected_columns = ["Drug Name", "Generic Name", "Brand Name", "Manufacturer", "Approval Date",
                                    "Indication", "Mechanism of Action", "Dose/Strength", "Formulation",
                                    "Boxed Warning", "Biosimilar", "Pediatric Use"]
                for col in expected_columns:
                    if col not in combined_openfda_df.columns:
                        combined_openfda_df[col] = "N/A"  # Fill missing columns to avoid errors

                combined_openfda_df = combined_openfda_df[expected_columns]  # Reorder columns

                st.write("### OpenFDA Data")
                st.dataframe(combined_openfda_df)

                # ✅ Download Button
                st.download_button(
                    label="📥 Download OpenFDA Data",
                    data=combined_openfda_df.to_csv(index=False),
                    file_name="openfda_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ No OpenFDA data found for the selected drugs.")
        else:
            st.warning("🔍 Please select drugs to fetch OpenFDA data.")


    with tab3:
        
        if selected_drugs:
            all_brand_names = []
            all_moa = []
            all_indications = []
            all_therapeutic_classes = []

            for drug_name in selected_drugs:
                details = fetch_drug_details(drug_name.strip())
                if details:
                    all_brand_names.append(details["Brand Names"])
                    all_moa.append(details["Mechanism of Action"])
                    all_indications.append(details["Indications"])
                    all_therapeutic_classes.append(details["Therapeutic Class"])

            # Combine results for each table
            all_brand_names_df = pd.concat(all_brand_names, ignore_index=True)
            all_moa_df = pd.concat(all_moa, ignore_index=True)
            all_indications_df = pd.concat(all_indications, ignore_index=True)
            all_therapeutic_classes_df = pd.concat(all_therapeutic_classes, ignore_index=True)

            # Maintain 2x2 Grid Layout with Equal Width Tables
            st.write("### Results")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Brand Names")
                st.dataframe(all_brand_names_df, height=400, width=600)

                st.subheader("Mechanism of Action")
                st.dataframe(all_moa_df, height=400, width=600)

            with col2:
                st.subheader("Indications")
                st.dataframe(all_indications_df, height=400, width=600)

                st.subheader("Therapeutic Classes")
                display_therapeutic_classes_with_tooltip(all_therapeutic_classes_df)

        else:
            st.error("Please select at least one drug to search.")

 
if __name__ == "__main__":
    run_app()
