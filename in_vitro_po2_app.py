import streamlit as st

# ---------- Constants ----------
PATM_DEFAULT = 760.0          # mmHg
H_DEFAULT = 771.6             # mmHg / mM (Henry constant at 37°C for culture medium)
WV_37C_DEFAULT = 0.062        # 6.2% water vapor at 37°C
D_DEFAULT = 2.69e-5           # cm^2/s (O2 diffusion coefficient in medium)

# ---------- Helper functions ----------

def incubator_po2(percent_o2_dry, percent_co2, percent_h2o, patm=PATM_DEFAULT):
    """Compute incubator PO2 (mmHg) from dry O2 fraction and gas fractions."""
    frac_o2_dry = percent_o2_dry / 100.0
    frac_co2 = percent_co2 / 100.0
    frac_h2o = percent_h2o / 100.0
    po2 = frac_o2_dry * (1.0 - frac_co2 - frac_h2o) * patm
    return po2  # mmHg


def dissolved_o2_from_po2(po2, H=H_DEFAULT):
    """Henry's law: returns dissolved O2 in mM given PO2 in mmHg."""
    return po2 / H  # mM


def po2_from_dissolved_o2(C_mM, H=H_DEFAULT):
    """Convert dissolved O2 (mM) to PO2 (mmHg)."""
    return C_mM * H  # mmHg


def pericellular_concentration(C_top_mM, ocr_amol_per_cell_s, cell_density_per_cm2,
                                medium_height_cm, H=H_DEFAULT, D=D_DEFAULT):
    """
    Compute pericellular dissolved O2 (mM) and pericellular PO2 (mmHg).
    Uses 1D steady-state diffusion with constant flux from OCR.
    """
    # Convert mM to mol/cm^3
    # 1 mM = 1e-3 mol/L and 1 L = 1000 cm^3 -> 1 mM = 1e-6 mol/cm^3
    C_top = C_top_mM * 1e-6  # mol/cm^3

    # OCR: amol/s/cell -> mol/s/cell
    ocr_cell = ocr_amol_per_cell_s * 1e-18  # amol -> mol
    F = ocr_cell * cell_density_per_cm2  # mol/cm^2/s

    # Steady-state concentration at cell layer
    C_pericell = C_top - (F * medium_height_cm) / D  # mol/cm^3

    # Prevent negative concentrations
    if C_pericell < 0.0:
        C_pericell = 0.0

    # Convert back to mM
    C_pericell_mM = C_pericell * 1e6  # mol/cm^3 -> mM

    P_pericell_mmHg = po2_from_dissolved_o2(C_pericell_mM, H)
    return C_pericell_mM, F, P_pericell_mmHg


def required_incubator_o2_for_target_pericell_po2(target_po2_pericell,
                                                   ocr_amol_per_cell_s, cell_density_per_cm2,
                                                   medium_height_cm,
                                                   percent_co2=5.0, percent_h2o=WV_37C_DEFAULT * 100.0,
                                                   patm=PATM_DEFAULT, H=H_DEFAULT, D=D_DEFAULT):
    """
    Given a target pericellular PO2 (mmHg), compute the required incubator dry O2 (%).
    Returns (percent_o2_incubator_dry, po2_top_mmHg, C_top_mM, flux_F).
    """
    # Target pericellular concentration in mM
    C_pericell_mM = target_po2_pericell / H  # mM
    # Convert to mol/cm^3
    C_pericell = C_pericell_mM * 1e-6  # mol/cm^3

    # Flux from OCR
    ocr_cell = ocr_amol_per_cell_s * 1e-18  # mol/s/cell
    F = ocr_cell * cell_density_per_cm2  # mol/cm^2/s

    # Solve for C_top (mol/cm^3)
    C_top = C_pericell + (F * medium_height_cm) / D  # mol/cm^3

    # Convert C_top back to mM
    C_top_mM = C_top * 1e6  # mM

    # Convert C_top to PO2 (mmHg)
    po2_top = po2_from_dissolved_o2(C_top_mM, H=H)

    # Solve for dry O2 percent in incubator accounting for CO2 and H2O
    percent_o2_incubator = (po2_top / patm) * 100.0

    return percent_o2_incubator, po2_top, C_top_mM, F


# ---------- Streamlit UI ----------
st.title("Pericellular O₂ Calculator")

st.write ("This calculator was created by the Rodier Lab. Its purpose is to estimate the partial pressure of oxygen (PO₂) at the cell level in vitro setups from the known oxygen concentration in the incubator. It can also be used in reverse mode to estimate the percent of oxygen required in the incubator to achieve a desired pericellular PO₂."
"If you use this tool, please cite: xxxxxxxxxxxxxxx. The original code is available on GitHub:xxxxxxxxxxxx."
"If you have any questions about its use, please contact Erwan Goy at erwan.goy@gmail.com.")

st.sidebar.header("Global parameters")
patm = st.sidebar.number_input("Atmospheric pressure (mmHg)", value=PATM_DEFAULT)
percent_co2 = st.sidebar.number_input("Incubator CO₂ (%)", value=5.0)
percent_h2o = st.sidebar.number_input("Water vapor (%)", value=WV_37C_DEFAULT * 100.0)
st.sidebar.caption("6.2% if you work with 100% humidity condition")
H = H_DEFAULT
D = st.sidebar.number_input("Diffusion coefficient D (cm²/s)", value=D_DEFAULT, format="%.2e")
st.sidebar.caption("this coefficient depend on medium composition. "
"Unfortunatly, there is no references for cell culture medium. "
"The default value come from human serum measurment by Goldstick TK et al. Adv Exp Med Biol. 1976")
st.sidebar.header("Medium Depth & OCR")
choice2 = st.sidebar.radio(
    "Do you know the medium height?",
    ["Yes", "No, let's calculate it"]
)

if choice2 == "Yes":
    medium_height_cm = st.sidebar.number_input("Medium height (cm)", value=0.3)
    #area_cm2 = st.sidebar.number_input("Flask area (cm²)", value=1.0)
else:
    medium_volume = st.sidebar.number_input("Enter Media Volume (mL)", value=1.0)
    area_cm2 = st.sidebar.number_input("Flask area (cm²)", value=1.0)
    # Convert mL to cm^3 (1 mL = 1 cm^3), height = volume(cm^3) / area(cm^2)
    medium_height_cm = (medium_volume if medium_volume is not None else 0.0) / (area_cm2 if area_cm2 else 1.0)

cell_density = st.sidebar.number_input("Cell density (cells/cm²)", value=0.0)
ocr_amol = st.sidebar.number_input("Oxygen Consumption Rate (amol/s/cell)", value=0.0)
st.sidebar.caption(
    "This value depends on the cell type."
    "If you have no idea, you can look at Wagner et al. Free Radical Biology & Medicine, 2011."
)

mode = st.radio("Mode", ["Forward: incubator O₂ concentration → pericellular PO₂", "Reverse: target pericellular PO₂ → incubator O₂ Percent"])

if mode == "Forward: incubator O₂ concentration → pericellular PO₂":
    choice1 = st.radio(
        "How do you want to enter incubator oxygen concentratration?",
        ["Enter dry O₂ (%)", "Enter monitored O₂ (%)", "Enter PO₂ (mmHg)"]
    )

    if choice1 == "Enter dry O₂ (%)":
        percent_o2_dry = st.number_input("Incubator O₂ (% dry gas)", value=21.0)
        po2_inc = incubator_po2(percent_o2_dry, percent_co2, percent_h2o, patm)
    elif choice1 == "Enter monitored O₂ (%)":
        percent_o2_monitored = st.number_input("Incubator O₂ (%) (monitored)", value=21.0)
        # Monitored O2 is typically the fraction of total gas O2; convert to PO2 directly
        po2_inc = percent_o2_monitored * patm / 100.0
    else:  # "Enter PO₂ (mmHg)"
        po2_inc = st.number_input("Incubator PO₂ (mmHg)", value=141.0)

    st.subheader("Forward calculation")

    C_top_mM = dissolved_o2_from_po2(po2_inc, H)
    C_pericell_mM, F, po2_pericell = pericellular_concentration(
        C_top_mM, ocr_amol, cell_density, medium_height_cm, H, D
    )

    st.markdown(f"**Incubator PO₂:** {po2_inc:.1f} mmHg")
    st.markdown(f"**Surface dissolved O₂ (C_top):** {C_top_mM:.6f} mM")
    st.markdown(f"**Pericellular dissolved O₂ (C_pericell):** {C_pericell_mM:.6f} mM")
    st.markdown(f"**Pericellular PO₂:** {po2_pericell:.2f} mmHg")
    st.markdown(f"**Flux F:** {F:.2e} mol/cm²/s")

elif mode == "Reverse: target pericellular PO₂ → incubator O₂ Percent":
    st.subheader("Reverse calculation")
    target_po2 = st.number_input("Target pericellular PO₂ (mmHg)", value=38.0)

    percent_o2_incubator, po2_top, C_top_mM, F = required_incubator_o2_for_target_pericell_po2(
        target_po2, ocr_amol, cell_density, medium_height_cm,
        percent_co2=percent_co2, percent_h2o=percent_h2o,
        patm=patm, H=H, D=D
    )

    st.markdown(f"**Required incubator O₂ (% dry gas):** {percent_o2_incubator:.2f} %")
    st.markdown(f"**Surface PO₂ (top):** {po2_top:.2f} mmHg")
    st.markdown(f"**Surface dissolved O₂ (C_top):** {C_top_mM:.6f} mM")
    st.markdown(f"**Flux F:** {F:.2e} mol/cm²/s")
