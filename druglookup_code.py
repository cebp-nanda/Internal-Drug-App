import streamlit as st
import pandas as pd
import requests


st.set_page_config(layout='wide')

# Define a secret password
PASSWORD = "cebp"

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

def fetch_clinical_trials(drug_name):
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        'query.term': drug_name,
        'pageSize': 10000,
        'format': 'json'
    }
    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            studies = data.get('studies', [])
            records = []
            for study in studies:
                protocol_section = study.get('protocolSection', {})
                identification_module = protocol_section.get('identificationModule', {})
                status_module = protocol_section.get('statusModule', {})
                conditions_module = protocol_section.get('conditionsModule', {})
                design_module = protocol_section.get('designModule', {})

                record = {
                    'NCT ID': identification_module.get('nctId', 'N/A'),
                    'Title': identification_module.get('briefTitle', 'N/A'),
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
        else:
            st.error(f"Failed to fetch clinical trials for {drug_name}. Status code: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching clinical trials for {drug_name}: {e}")
        return pd.DataFrame()

def fetch_openfda_details(drug_name):
    api_url = f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{drug_name}&limit=1&sort=effective_time:desc"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if "results" in data:
                result = data["results"][0]
                openfda = result.get("openfda", {})
                return {
                    "Generic Name": openfda.get("generic_name", ["N/A"])[0],
                    "Brand Name": openfda.get("brand_name", ["N/A"])[0],
                    "Manufacturer": openfda.get("manufacturer_name", ["N/A"])[0],
                    "Approval Date": result.get("effective_time", "N/A"),
                    "Indication": result.get("indications_and_usage", ["N/A"])[0],
                    "Mechanism of Action": result.get("mechanism_of_action", ["N/A"])[0],
                    "Dose/Strength": result.get("dosage_and_administration", ["N/A"])[0],
                    "Formulation": result.get("dosage_form", "N/A"),
                    "Boxed Warning": result.get("boxed_warning", ["N/A"])[0],
                    "Biosimilar": openfda.get("product_type", ["N/A"])[0],
                    "Pediatric Use": result.get("pediatric_use", ["N/A"])[0],
                }
        else:
            st.error(f"Failed to fetch OpenFDA data for {drug_name}. Status Code: {response.status_code}")
    except Exception as e:
        st.error(f"Error fetching OpenFDA data for {drug_name}: {e}")
    return None
    
def fetch_rxcui(drug_name):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get("idGroup", {}).get("rxnormId", [None])[0]

def fetch_brand_names(rxcui, drug_name):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/allrelated.json"
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

    url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&rela=has_mechanism_of_action&classTypes=MOA"
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

    url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&rela=may_treat&classTypes=DISEASE"
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

def fetch_therapeutic_class(rxcui, drug_name):

    url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&rela=has_therapeutic_class&classTypes=ATC1-4,VA"
    response = requests.get(url)
    therapeutic_classes = []
    if response.status_code == 200:
        data = response.json()
        for entry in data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []):
            if entry.get("rxclassMinConceptItem", {}).get("classType", "").upper() in ["ATC1-4", "VA"]:
                therapeutic_classes.append({"Drug Name": drug_name,
                    "Therapeutic Class": entry.get("rxclassMinConceptItem", {}).get("className", "N/A"),
                    "Class Type": entry.get("rxclassMinConceptItem", {}).get("classType", "N/A")
                })
    return pd.DataFrame(therapeutic_classes).drop_duplicates()

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
    
    # Shared search bar for all tabs
    selected_drugs = st.multiselect(
        "Search for Drugs:",
        options=drugs["Drug name"].tolist(),
        default=[]
    )

    # Tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["RxNorm","Clinical Trials", "OpenFDA"])
    
    with tab2:
        #st.subheader("Clinical Trials Data")
        if selected_drugs:
            all_clinical_trials = []
            for drug in selected_drugs:
                clinical_trials = fetch_clinical_trials(drug)
                if clinical_trials is not None:
                    all_clinical_trials.append(clinical_trials)
            
            if all_clinical_trials:
                clinical_trials_df = pd.concat(all_clinical_trials, ignore_index=True)

                # Create a unique list of conditions
                all_conditions = set(
                    condition.strip() 
                    for conditions in clinical_trials_df["Conditions"].dropna() 
                    for condition in conditions.split(",")
                )

                # Use columns to place filters next to each other
                col1, col2 = st.columns([1, 2])
                with col1:
                    # Filter by Status
                    status_filter = st.selectbox(
                        "Filter by Study Status:",
                        options=["All"] + clinical_trials_df["Status"].dropna().unique().tolist()
                    )

                with col2:
                    # Filter by Conditions
                    condition_filter = st.multiselect(
                        "Filter by Conditions:",
                        options=["All"] + sorted(all_conditions),
                        default=["All"]
                    )

                # Apply Status filter
                if status_filter != "All":
                    filtered_trials_df = clinical_trials_df[clinical_trials_df["Status"] == status_filter]
                else:
                    filtered_trials_df = clinical_trials_df

                # Apply Condition filter
                if "All" not in condition_filter:
                    filtered_trials_df = filtered_trials_df[
                        filtered_trials_df["Conditions"].apply(
                            lambda x: any(cond.strip() in condition_filter for cond in x.split(","))
                        )
                    ]

                st.write("### Clinical Trials Data")
                st.dataframe(filtered_trials_df)

                # Download button
                st.download_button(
                    label="Download Clinical Trials Data",
                    data=filtered_trials_df.to_csv(index=False),
                    file_name="clinical_trials_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No clinical trials data found for the selected drugs.")
        else:
            st.warning("Please select drugs to fetch Clinical Trials data.")

    with tab3:
        #st.subheader("OpenFDA Data")
        if selected_drugs:
            openfda_data = []
            for drug in selected_drugs:
                openfda_details = fetch_openfda_details(drug)
                if openfda_details:
                    openfda_data.append(openfda_details)
            
            if openfda_data:
                openfda_df = pd.DataFrame(openfda_data)
                st.write("### OpenFDA Data")
                st.dataframe(openfda_df)

                st.download_button(
                    label="Download OpenFDA Data",
                    data=openfda_df.to_csv(index=False),
                    file_name="openfda_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No OpenFDA data found for the selected drugs.")
        else:
            st.warning("Please select drugs to fetch OpenFDA data.")
    with tab1:
        
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

            # Ensure consistent display with repeating drug names
            def format_table(df, column):
                return df.sort_values(by=column).reset_index(drop=True)

            all_brand_names_df = format_table(all_brand_names_df, "Drug Name")
            all_moa_df = format_table(all_moa_df, "Drug Name")
            all_indications_df = format_table(all_indications_df, "Drug Name")
            all_therapeutic_classes_df = format_table(all_therapeutic_classes_df, "Drug Name")

            # Set fixed table dimensions
            table_height = 400
            table_width = 600  # Adjust as needed for readability

            st.write("### Results")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Brand Names")
                st.dataframe(all_brand_names_df, height=table_height, width=table_width)

                st.subheader("Mechanism of Action")
                st.dataframe(all_moa_df, height=table_height, width=table_width)

            with col2:
                st.subheader("Indications")
                st.dataframe(all_indications_df, height=table_height, width=table_width)

                st.subheader("Therapeutic Classes")
                st.dataframe(all_therapeutic_classes_df, height=table_height, width=table_width)
        else:
            st.error("Please select at least one drug to search.")


if __name__ == "__main__":
    run_app()
